#!/usr/bin/env python3
"""Phase 2 — export dev probabilities from each of the 9 run checkpoints.

Identical protocol to the Phase-1 export (same architecture, tokenization,
gold-file-order examples, batch size, index rule). For every run:
  * HARD validation: thresholding at 0.30 must reproduce that run's own
    frozen output/pred_task1b.json exactly; any mismatch aborts everything.
  * writes <run>/probabilities.jsonl (456 gold-actor rows; the 3 article-only
    actors are irrelevant to Phase-2 metrics and are not exported).

Run with the fehu env interpreter after run_all_cells.sh completes.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer
from peft import PeftModel

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
RUNS = HERE.parent / "runs"

MODEL_NAME = "microsoft/deberta-v3-base"
NUM_LABELS = 108
MAX_LENGTH = 512
DEV_ARTICLES = BASE / "dataset/dev/dev_event_base.json"
DEV_GOLD = BASE / "dataset/gold_labels/dev/dev_human_values.json"

CELLS = [f"{c}_seed{s}" for s in (42, 43, 44) for c in "ABC"]


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


def build_gold_examples():
    arts = json.loads(DEV_ARTICLES.read_text())
    order = defaultdict(list)
    for item in json.loads(DEV_GOLD.read_text()):
        seen = set()
        for hv in item.get("article_human_values", []):
            a = str(hv["actor"])
            if a not in seen:
                seen.add(a)
                order[str(item["guid"])].append(a)
    out = []
    for art in arts:
        guid = str(art["guid"])
        text = f"Title: {art.get('title', '')}\n{art.get('content', '')}"
        id2name = {str(aid): n for d in art.get("actors", [])
                   for n, aid in d.items()}
        for a in order[guid]:
            out.append(dict(guid=guid, actor_id=a,
                            actor_name=id2name.get(a, a), text=text))
    return out


def main():
    if not torch.cuda.is_available():
        sys.exit("ABORT: CUDA unavailable")
    device = torch.device("cuda")
    examples = build_gold_examples()
    assert len(examples) == 456

    for cell in CELLS:
        run = RUNS / cell
        ckpt = run / "checkpoints"
        pred_file = run / "output" / "pred_task1b.json"
        if not ckpt.is_dir() or not pred_file.is_file():
            sys.exit(f"ABORT: incomplete run {cell}: missing checkpoint or predictions")

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
            sys.exit(f"ABORT: {cell}: {mism} instances fail 0.30 reproduction")

        with open(run / "probabilities.jsonl", "w") as f:
            for ex in examples:
                key = (ex["guid"], ex["actor_id"])
                f.write(json.dumps({
                    "guid": ex["guid"], "actor_id": ex["actor_id"],
                    "probabilities_108": [round(v, 6) for v in probs[key]],
                }) + "\n")
        print(f"{cell}: exported + validated")
        del model, enc, base
        torch.cuda.empty_cache()

    print("ALL EXPORTS VALIDATED")


if __name__ == "__main__":
    main()
