#!/usr/bin/env python3
"""Phase 3 — export + hard-validate dev probabilities for named runs under
new_check/phase3/runs/. Same protocol as Phase 1/2 exports.

Usage:  <fehu-python> export_probs_phase3.py Fp_seed42 Gp_seed42 ...
Each run must contain checkpoints/ and output/pred_task1b.json; thresholding
the exported probabilities at 0.30 must reproduce that file exactly or the
whole export aborts.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "phase2" / "scripts"))

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402
from peft import PeftModel  # noqa: E402

from export_probs_phase2 import (  # noqa: E402  (reused verbatim)
    ValueClassifier, DevSet, build_gold_examples, MODEL_NAME,
)

RUNS = HERE.parent / "runs"


def main():
    names = sys.argv[1:]
    if not names:
        sys.exit("usage: export_probs_phase3.py <run_name> [<run_name> ...]")
    if not torch.cuda.is_available():
        sys.exit("ABORT: CUDA unavailable")
    device = torch.device("cuda")
    examples = build_gold_examples()
    assert len(examples) == 456

    for name in names:
        run = RUNS / name
        ckpt = run / "checkpoints"
        pred_file = run / "output" / "pred_task1b.json"
        if not ckpt.is_dir() or not pred_file.is_file():
            sys.exit(f"ABORT: incomplete run {name}")

        tok = AutoTokenizer.from_pretrained(str(ckpt))
        base = AutoModel.from_pretrained(MODEL_NAME)
        enc = PeftModel.from_pretrained(base, str(ckpt))
        model = ValueClassifier(enc, base.config.hidden_size).to(device)
        model.classifier.load_state_dict(
            torch.load(ckpt / "classifier.pt", map_location=device,
                       weights_only=True))
        model.eval()

        dl = DataLoader(DevSet(examples, tok), batch_size=8,
                        num_workers=4, pin_memory=True)
        probs = {}
        with torch.no_grad():
            for batch in dl:
                ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                tt = batch.get("token_type_ids")
                if tt is not None:
                    tt = tt.to(device)
                p = torch.sigmoid(model(ids, mask, tt)).cpu()
                for i, (g, a) in enumerate(zip(batch["guid"],
                                               batch["actor_id"])):
                    probs[(g, a)] = p[i].tolist()

        frozen = defaultdict(set)
        for art in json.loads(pred_file.read_text()):
            for hv in art["article_human_values"]:
                frozen[(str(art["guid"]), str(hv["actor"]))].add(
                    f"{hv['direction']}:{hv['l1_value']}")
        mism = sum(
            1 for key, pv in probs.items()
            if {f"{i % 2}:{i // 2}" for i, v in enumerate(pv) if v >= 0.30}
            != frozen.get(key, set()))
        if mism:
            sys.exit(f"ABORT: {name}: {mism} instances fail 0.30 reproduction")

        with open(run / "probabilities.jsonl", "w") as f:
            for ex in examples:
                key = (ex["guid"], ex["actor_id"])
                f.write(json.dumps({
                    "guid": ex["guid"], "actor_id": ex["actor_id"],
                    "probabilities_108": [round(v, 6) for v in probs[key]],
                }) + "\n")
        print(f"{name}: exported + validated")
        del model, enc, base
        torch.cuda.empty_cache()
    print("ALL EXPORTS VALIDATED")


if __name__ == "__main__":
    main()
