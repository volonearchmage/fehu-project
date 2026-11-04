#!/usr/bin/env python3
"""Phase 1 — export dev actor-level 108-class sigmoid probabilities from the
frozen OFFICIAL-ONLY DeBERTa baseline checkpoint (read-only).

Protocol is a faithful adaptation of the v2 export
(output/research_hybrid_deberta_v2_liu_flash/20260714_184515/scripts/
03_export_probabilities.py), pointed at the baseline checkpoint:
  * same architecture (ValueClassifier over DeBERTa-v3-base + PEFT adapter,
    linear 108-way head from classifier.pt);
  * same tokenization (text, actor_name; truncation only_first; max_length
    512; padding max_length);
  * same dev example construction as the trainer (actors enumerated from the
    gold labels file, gold-file order -> 456 trainer-parity examples), plus
    the 3 article-listed actors absent from gold, exported with a flag and
    NOT bit-validated (the frozen run never inferred them);
  * same batch size 8 and example order as the trainer for kernel parity;
  * same index rule: idx = int(l1)*2 + int(direction), "1" = aligned.

HARD VALIDATION: thresholding the exported probabilities at 0.30 must
reproduce the frozen baseline predictions
(output/research_ablation_smoke_runs/20260704_201355/baseline/output/
pred_task1b.json) EXACTLY per (guid, actor). Any mismatch aborts with no
output written. No fallbacks.

Run with the training environment's interpreter:
    /home/szf-4090/miniconda3/envs/fehu/bin/python export_baseline_probabilities.py

This performs local GPU inference only — no training, no API calls, and no
writes outside new_check/phase1/.
"""

import datetime
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModel
from peft import PeftModel

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]                      # ntcir19_fehu-master/
OUT = HERE.parent / "outputs"
LOGS = HERE.parent / "logs"

CKPT = BASE / "output/research_ablation_smoke_runs/20260704_201355/baseline/checkpoints"
FROZEN_PRED = BASE / "output/research_ablation_smoke_runs/20260704_201355/baseline/output/pred_task1b.json"
DEV_ARTICLES = BASE / "dataset/dev/dev_event_base.json"
DEV_GOLD = BASE / "dataset/gold_labels/dev/dev_human_values.json"

MODEL_NAME = "microsoft/deberta-v3-base"
NUM_LABELS = 108
MAX_LENGTH = 512
THRESH_FROZEN = 0.30

for p in (CKPT, FROZEN_PRED, DEV_ARTICLES, DEV_GOLD):
    if not p.exists():
        sys.exit(f"ABORT: required input missing: {p}")


class ValueClassifier(nn.Module):
    def __init__(self, encoder, hidden_size):
        super().__init__()
        self.encoder = encoder
        self.classifier = nn.Linear(hidden_size, NUM_LABELS)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        kw = dict(input_ids=input_ids, attention_mask=attention_mask)
        if token_type_ids is not None:
            kw["token_type_ids"] = token_type_ids
        cls = self.encoder(**kw).last_hidden_state[:, 0, :]
        return self.classifier(cls.to(self.classifier.weight.dtype))


class DevSet(Dataset):
    def __init__(self, examples, tok):
        self.examples, self.tok = examples, tok

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, i):
        ex = self.examples[i]
        enc = self.tok(ex["text"], ex["actor_name"], truncation="only_first",
                       max_length=MAX_LENGTH, padding="max_length",
                       return_tensors="pt")
        item = {"input_ids": enc["input_ids"].squeeze(0),
                "attention_mask": enc["attention_mask"].squeeze(0),
                "guid": ex["guid"], "actor_id": ex["actor_id"]}
        if "token_type_ids" in enc:
            item["token_type_ids"] = enc["token_type_ids"].squeeze(0)
        return item


def build_dev_examples():
    arts = json.loads(DEV_ARTICLES.read_text(encoding="utf-8"))
    gold_order = defaultdict(list)
    for item in json.loads(DEV_GOLD.read_text(encoding="utf-8")):
        seen = set()
        for hv in item.get("article_human_values", []):
            a = str(hv["actor"])
            if a not in seen:
                seen.add(a)
                gold_order[str(item["guid"])].append(a)
    trainer_ex, extra_ex = [], []
    for art in arts:
        guid = str(art["guid"])
        text = f"Title: {art.get('title', '')}\n{art.get('content', '')}"
        id2name = {str(aid): name for d in art.get("actors", [])
                   for name, aid in d.items()}
        for actor_id in gold_order[guid]:
            trainer_ex.append(dict(guid=guid, actor_id=actor_id,
                                   actor_name=id2name.get(actor_id, actor_id),
                                   text=text))
        gold_set = set(gold_order[guid])
        for actor_id, name in id2name.items():
            if actor_id not in gold_set:
                extra_ex.append(dict(guid=guid, actor_id=actor_id,
                                     actor_name=name, text=text))
    return trainer_ex, extra_ex


def main():
    started = datetime.datetime.now().isoformat(timespec="seconds")
    if not torch.cuda.is_available():
        sys.exit("ABORT: CUDA unavailable; the frozen protocol ran on GPU")
    device = torch.device("cuda")

    tok = AutoTokenizer.from_pretrained(str(CKPT))
    base = AutoModel.from_pretrained(MODEL_NAME)
    enc = PeftModel.from_pretrained(base, str(CKPT))
    model = ValueClassifier(enc, base.config.hidden_size).to(device)
    model.classifier.load_state_dict(
        torch.load(CKPT / "classifier.pt", map_location=device,
                   weights_only=True))
    model.eval()

    trainer_ex, extra_ex = build_dev_examples()
    print(f"trainer-parity examples: {len(trainer_ex)}  "
          f"extra article-only actors: {len(extra_ex)}")

    def infer(examples):
        dl = DataLoader(DevSet(examples, tok), batch_size=8,
                        num_workers=4, pin_memory=True)
        out = {}
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
                    out[(g, a)] = p[i].tolist()
        return out

    probs = infer(trainer_ex)
    extra_probs = infer(extra_ex) if extra_ex else {}
    print(f"inferred {len(probs)} + {len(extra_probs)} actor examples")

    # ---- HARD validation vs frozen baseline predictions at 0.30 ----
    frozen = defaultdict(set)
    for art in json.loads(FROZEN_PRED.read_text(encoding="utf-8")):
        for hv in art["article_human_values"]:
            frozen[(str(art["guid"]), str(hv["actor"]))].add(
                f"{hv['direction']}:{hv['l1_value']}")
    mism = 0
    for (g, a), pv in probs.items():
        rep = {f"{i % 2}:{i // 2}" for i, v in enumerate(pv)
               if v >= THRESH_FROZEN}
        if rep != frozen.get((g, a), set()):
            mism += 1
            if mism <= 3:
                print("MISMATCH", g, a, "reproduced:", sorted(rep),
                      "frozen:", sorted(frozen.get((g, a), set())))
    if mism:
        sys.exit(f"ABORT: {mism} actor instances do not reproduce the frozen "
                 f"0.30 baseline predictions — nothing written")
    print("VALIDATED: thresholded probabilities reproduce the frozen baseline "
          "pred_task1b.json exactly")

    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "baseline_actor_probabilities.jsonl"
    with open(out_path, "w") as f:
        for ex, src, pp in ([(e, "gold_actor_trainer_parity", probs)
                             for e in trainer_ex]
                            + [(e, "article_only_actor_not_in_frozen_run",
                                extra_probs) for e in extra_ex]):
            key = (ex["guid"], ex["actor_id"])
            f.write(json.dumps({
                "guid": ex["guid"], "actor_id": ex["actor_id"],
                "actor_name": ex["actor_name"], "actor_source": src,
                "probabilities_108": [round(v, 6) for v in pp[key]],
                "index_rule": "idx = int(l1)*2 + int(direction); "
                              "direction 1=aligned, 0=contradictory",
            }) + "\n")

    def sha(p):
        h = hashlib.sha256()
        h.update(Path(p).read_bytes())
        return h.hexdigest()

    manifest = {
        "phase": 1,
        "step": "export_baseline_probabilities",
        "started": started,
        "finished": datetime.datetime.now().isoformat(timespec="seconds"),
        "checkpoint": str(CKPT.relative_to(BASE)),
        "checkpoint_sha256": {p.name: sha(p) for p in sorted(CKPT.iterdir())},
        "frozen_pred_sha256": sha(FROZEN_PRED),
        "validation": "thresholding at 0.30 reproduces frozen baseline "
                      "pred_task1b.json exactly on all trainer-parity instances",
        "n_trainer_parity": len(trainer_ex),
        "n_extra_actors": len(extra_ex),
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "output": str(out_path.relative_to(BASE)),
        "constraints": {"no_training": True, "no_api_calls": True,
                        "no_existing_artifact_modified": True},
    }
    (OUT / "export_manifest.json").write_text(json.dumps(manifest, indent=2))
    (LOGS / "export_baseline.log").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
