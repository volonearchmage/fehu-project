#!/usr/bin/env python3
"""Export 108-dim dev/test probabilities from the augmented DeBERTa-v2 LoRA
checkpoint for every actor of an event_base articles file.

Same architecture/tokenization protocol as the validated Phase-2/3 exports
(microsoft/deberta-v3-base + LoRA adapter + linear classifier head;
text = "Title: {title}\n{content}", tokenized as (text, actor_name) pair,
truncation only_first, max_length 512).

Checkpoint default: the frozen augmented-v2 run
  output/research_augmented_deberta_v2_unfiltered/20260714_032758/checkpoint

Validation:
  --validate_against <pred_task1b.json>   thresholding the exported
  probabilities at 0.30 must reproduce that file exactly on the keys it
  contains, else the export aborts and writes nothing. Use this on dev
  (against the frozen v2 predictions). Not available for test (no frozen
  reference) — there the script instead hard-checks row count == number of
  actors in the articles file.

Run with the fehu env interpreter:
  /home/szf-4090/miniconda3/envs/fehu/bin/python export_v2_probs.py \
      --articles dataset/test/test_article_event_base.json \
      --out <exp>/inputs/test_v2_probabilities.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402
from peft import PeftModel  # noqa: E402

MODEL_NAME = "microsoft/deberta-v3-base"
NUM_LABELS = 108
MAX_LENGTH = 512
DEFAULT_CKPT = (ROOT / "output/research_augmented_deberta_v2_unfiltered/"
                "20260714_032758/checkpoint")


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


class ActorSet(Dataset):
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
                "idx": i}
        if "token_type_ids" in enc:
            item["token_type_ids"] = enc["token_type_ids"].squeeze(0)
        return item


def build_examples(articles_path: Path):
    arts = json.loads(articles_path.read_text())
    out = []
    for art in arts:
        guid = str(art["guid"])
        text = f"Title: {art.get('title', '')}\n{art.get('content', '')}"
        for d in art.get("actors", []):
            for name, aid in d.items():
                out.append(dict(guid=guid, actor_id=str(aid),
                                actor_name=name, text=text))
    if not out:
        sys.exit(f"ABORT: no actors in {articles_path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--articles", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, default=DEFAULT_CKPT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--validate_against", type=Path, default=None,
                    help="frozen pred_task1b.json that probs@0.30 must "
                         "reproduce on its keys")
    ap.add_argument("--batch_size", type=int, default=8)
    args = ap.parse_args()

    if not torch.cuda.is_available():
        sys.exit("ABORT: CUDA unavailable")
    if not (args.checkpoint / "adapter_model.safetensors").is_file():
        sys.exit(f"ABORT: no LoRA adapter in {args.checkpoint}")
    if args.out.exists():
        sys.exit(f"ABORT: {args.out} already exists — refusing to overwrite")

    device = torch.device("cuda")
    examples = build_examples(args.articles)
    print(f"{len(examples)} actor examples from {args.articles.name}")

    tok = AutoTokenizer.from_pretrained(str(args.checkpoint))
    base = AutoModel.from_pretrained(MODEL_NAME)
    enc = PeftModel.from_pretrained(base, str(args.checkpoint))
    model = ValueClassifier(enc, base.config.hidden_size).to(device)
    model.classifier.load_state_dict(
        torch.load(args.checkpoint / "classifier.pt", map_location=device,
                   weights_only=True))
    model.eval()

    dl = DataLoader(ActorSet(examples, tok), batch_size=args.batch_size,
                    num_workers=4, pin_memory=True)
    probs = [None] * len(examples)
    with torch.no_grad():
        for batch in dl:
            idxs = batch.pop("idx")
            batch = {k: v.to(device) for k, v in batch.items()}
            out = torch.sigmoid(model(**batch)).cpu()
            for j, i in enumerate(idxs.tolist()):
                probs[i] = [round(float(x), 6) for x in out[j]]
    if any(p is None for p in probs):
        sys.exit("ABORT: some examples were not scored")

    if args.validate_against:
        from collections import defaultdict
        frozen = defaultdict(set)
        for item in json.loads(args.validate_against.read_text()):
            for hv in item.get("article_human_values", []):
                frozen[(str(item["guid"]), str(hv["actor"]))].add(
                    f"{hv['direction']}:{hv['l1_value']}")
        derived = defaultdict(set)
        for ex, p in zip(examples, probs):
            key = (ex["guid"], ex["actor_id"])
            for i, x in enumerate(p):
                if x >= 0.30:
                    derived[key].add(f"{i % 2}:{i // 2}")
        bad = [k for k in frozen
               if derived.get(k, set()) != frozen[k]]
        if bad:
            sys.exit(f"ABORT: probs@0.30 do not reproduce "
                     f"{args.validate_against} on {len(bad)} keys "
                     f"(first: {bad[:3]}) — nothing written")
        print(f"[ok] validated against {args.validate_against.name} "
              f"({len(frozen)} keys)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for ex, p in zip(examples, probs):
            f.write(json.dumps({
                "guid": ex["guid"], "actor_id": ex["actor_id"],
                "actor_name": ex["actor_name"],
                "actor_source": "articles_file",
                "probabilities_108": p}) + "\n")
    print(f"[done] {len(examples)} rows -> {args.out}")


if __name__ == "__main__":
    main()
