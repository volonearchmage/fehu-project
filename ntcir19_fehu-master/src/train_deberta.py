#!/usr/bin/env python3
"""
DeBERTa-v3-base + LoRA fine-tuning for FEHU Task-1 human value classification.

108-class multi-label binary classification:
  label index = int(l1_value) * 2 + int(direction)
  direction: "0"=contradictory, "1"=aligned

Run from project root:
    python src/train_deberta.py
"""

import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_cosine_schedule_with_warmup
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent

MODEL_NAME   = "microsoft/deberta-v3-base"
NUM_LABELS   = 108      # 54 L1 values × 2 directions
MAX_LENGTH   = 512
BATCH_SIZE   = 8
GRAD_ACCUM   = 4
MAX_EPOCHS   = 15
LR           = 2e-4
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
PATIENCE     = 4
THRESHOLD    = 0.3

CHECKPOINT_DIR = BASE_DIR / "checkpoints" / "best_model"
OUTPUT_DIR     = BASE_DIR / "output" / "task1"

TRAIN_ARTICLES = BASE_DIR / "dataset/train/train_event_base.json"
TRAIN_LABELS   = BASE_DIR / "dataset/gold_labels/train/train_human_values.json"
DEV_ARTICLES   = BASE_DIR / "dataset/dev/dev_event_base.json"
DEV_LABELS     = BASE_DIR / "dataset/gold_labels/dev/dev_human_values.json"
L1_FILE        = BASE_DIR / "dataset/hv_categories/human_value_level1_values.json"
L2_FILE        = BASE_DIR / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_FILE  = BASE_DIR / "dataset/hv_categories/level_1_to_level_2.json"


# ── Taxonomy ───────────────────────────────────────────────────────────────────
def load_l1_to_l2():
    """Return {l1_id_str: l2_id_str}."""
    l1 = json.loads(L1_FILE.read_text())
    l2 = json.loads(L2_FILE.read_text())
    raw = json.loads(L1_TO_L2_FILE.read_text())["level_1_to_level_2"]
    return {l1[k]: l2[v] for k, v in raw.items()}


# ── Data ───────────────────────────────────────────────────────────────────────
def build_examples(articles_path, labels_path=None):
    """
    Returns list of dicts: guid, actor_id, actor_name, text, labels.
    labels is float32 tensor of shape (108,) when labels_path is given, else None.
    """
    articles = json.loads(Path(articles_path).read_text())

    gold = defaultdict(lambda: defaultdict(list))  # guid → actor_id → [(l1, dir)]
    if labels_path:
        for item in json.loads(Path(labels_path).read_text()):
            for hv in item.get("article_human_values", []):
                gold[str(item["guid"])][str(hv["actor"])].append(
                    (int(hv["l1_value"]), int(hv["direction"]))
                )

    examples = []
    for art in articles:
        guid = str(art["guid"])
        text = f"Title: {art.get('title', '')}\n{art.get('content', '')}"
        id2name = {
            str(aid): name
            for d in art.get("actors", [])
            for name, aid in d.items()
        }

        if labels_path:
            for actor_id, pairs in gold[guid].items():
                lv = torch.zeros(NUM_LABELS)
                for l1, d in pairs:
                    lv[l1 * 2 + d] = 1.0
                examples.append(dict(
                    guid=guid, actor_id=actor_id,
                    actor_name=id2name.get(actor_id, actor_id),
                    text=text, labels=lv,
                ))
        else:
            for actor_id, actor_name in id2name.items():
                examples.append(dict(
                    guid=guid, actor_id=actor_id,
                    actor_name=actor_name, text=text, labels=None,
                ))
    return examples


class FehuDataset(Dataset):
    def __init__(self, examples, tokenizer):
        self.examples = examples
        self.tok = tokenizer

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, i):
        ex = self.examples[i]
        enc = self.tok(
            ex["text"], ex["actor_name"],
            truncation="only_first", max_length=MAX_LENGTH,
            padding="max_length", return_tensors="pt",
        )
        item = {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "guid":           ex["guid"],
            "actor_id":       ex["actor_id"],
        }
        if "token_type_ids" in enc:
            item["token_type_ids"] = enc["token_type_ids"].squeeze(0)
        if ex["labels"] is not None:
            item["labels"] = ex["labels"]
        return item


# ── Model ──────────────────────────────────────────────────────────────────────
class ValueClassifier(nn.Module):
    def __init__(self, encoder, hidden_size):
        super().__init__()
        self.encoder    = encoder
        self.classifier = nn.Linear(hidden_size, NUM_LABELS)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        kw = dict(input_ids=input_ids, attention_mask=attention_mask)
        if token_type_ids is not None:
            kw["token_type_ids"] = token_type_ids
        cls = self.encoder(**kw).last_hidden_state[:, 0, :]
        return self.classifier(cls.to(self.classifier.weight.dtype))


def detect_lora_targets(base_model):
    all_linear = [n for n, m in base_model.named_modules() if isinstance(m, nn.Linear)]
    print(f"Linear modules ({len(all_linear)} total, first 20):")
    for n in all_linear[:20]:
        print(f"  {n}")
    if len(all_linear) > 20:
        print(f"  ... (+{len(all_linear) - 20} more)")

    targets = {
        n.split(".")[-1] for n in all_linear
        if "query" in n.split(".")[-1] or "value" in n.split(".")[-1]
    }
    if not targets:
        print("Could not detect targets, falling back to ['q_proj', 'v_proj']")
        return ["q_proj", "v_proj"]
    print(f"LoRA target modules: {sorted(targets)}")
    return list(targets)


def build_model(device):
    tok  = AutoTokenizer.from_pretrained(MODEL_NAME)
    base = AutoModel.from_pretrained(MODEL_NAME)
    cfg  = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.1,
        target_modules=detect_lora_targets(base),
        task_type=TaskType.SEQ_CLS,
    )
    enc = get_peft_model(base, cfg)
    enc.print_trainable_parameters()
    model = ValueClassifier(enc, base.config.hidden_size).to(device)
    return model, tok


# ── Loss weight ────────────────────────────────────────────────────────────────
def compute_pos_weight(examples, device):
    n = len(examples)
    counts = torch.stack([ex["labels"] for ex in examples]).sum(0)
    w = ((n - counts) / counts.clamp(min=1)).sqrt().clamp(1.0, 10.0)
    return w.to(device)


# ── Training ───────────────────────────────────────────────────────────────────
def train_epoch(model, loader, optimizer, scheduler, criterion, device):
    model.train()
    optimizer.zero_grad()
    total = 0.0
    for step, batch in enumerate(tqdm(loader, desc="  train", leave=False)):
        ids   = batch["input_ids"].to(device)
        mask  = batch["attention_mask"].to(device)
        labs  = batch["labels"].to(device)
        ttids = batch.get("token_type_ids")
        if ttids is not None:
            ttids = ttids.to(device)

        loss = criterion(model(ids, mask, ttids), labs) / GRAD_ACCUM
        loss.backward()
        total += loss.item() * GRAD_ACCUM

        if (step + 1) % GRAD_ACCUM == 0:
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step(); scheduler.step(); optimizer.zero_grad()

    if len(loader) % GRAD_ACCUM:
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step(); scheduler.step(); optimizer.zero_grad()

    return total / len(loader)


# ── Inference ──────────────────────────────────────────────────────────────────
@torch.no_grad()
def infer(model, loader, device):
    model.eval()
    out = {}
    for batch in tqdm(loader, desc="  infer", leave=False):
        ids   = batch["input_ids"].to(device)
        mask  = batch["attention_mask"].to(device)
        ttids = batch.get("token_type_ids")
        if ttids is not None:
            ttids = ttids.to(device)
        probs = torch.sigmoid(model(ids, mask, ttids)).cpu()
        for i, (g, a) in enumerate(zip(batch["guid"], batch["actor_id"])):
            out[(g, a)] = probs[i].ge(THRESHOLD).nonzero(as_tuple=True)[0].tolist()
    return out


def to_submission(raw, l1l2):
    """Convert {(guid, actor_id): [label_indices]} to task1a/1b submission lists."""
    by_guid = defaultdict(list)
    for (g, a), idxs in raw.items():
        by_guid[g].append((a, idxs))

    t1a, t1b = [], []
    for guid, actor_list in by_guid.items():
        va, vb, seen = [], [], set()
        for actor, idxs in actor_list:
            for idx in sorted(idxs):
                l1, dr = str(idx // 2), str(idx % 2)
                l2 = l1l2.get(l1, "0")
                vb.append({"actor": actor, "l1_value": l1, "direction": dr})
                if (actor, l2) not in seen:
                    seen.add((actor, l2))
                    va.append({"actor": actor, "l2_value": l2})
        t1a.append({"guid": guid, "article_human_values": va})
        t1b.append({"guid": guid, "article_human_values": vb})
    return t1a, t1b


# ── Evaluation ─────────────────────────────────────────────────────────────────
def eval_dev(model, loader, device, l1l2, best_so_far):
    from evaluation import (
        parse_task1a, parse_task1b, evaluate,
        l2_universe, l1_dir_universe, direction_reverse_rate_gold_excl,
    )
    raw = infer(model, loader, device)
    t1a, t1b = to_submission(raw, l1l2)

    with tempfile.TemporaryDirectory() as tmp:
        pa = os.path.join(tmp, "t1a.json")
        pb = os.path.join(tmp, "t1b.json")
        json.dump(t1a, open(pa, "w"))
        json.dump(t1b, open(pb, "w"))

        g1a = parse_task1a(str(DEV_LABELS))
        r1a = evaluate(g1a, parse_task1a(pa), l2_universe())
        g1b = parse_task1b(str(DEV_LABELS))
        r1b = evaluate(g1b, parse_task1b(pb), l1_dir_universe())
        drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b, parse_task1b(pb))

    print(f"  1a  micro={r1a['micro_f1']:.4f}  macro={r1a['macro_f1']:.4f}")
    print(f"  1b  micro={r1b['micro_f1']:.4f}  macro={r1b['macro_f1']:.4f}"
          f"  P={r1b['micro_precision']:.4f}  R={r1b['micro_recall']:.4f}")
    print(f"  DRR={drr:.4f}  (rev={rev}/{den}  amb={amb})"
          f"  best_1b_micro={max(best_so_far, r1b['micro_f1']):.4f}")
    return r1b["micro_f1"]


# ── Checkpoint ─────────────────────────────────────────────────────────────────
def save_ckpt(model, tok):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    model.encoder.save_pretrained(str(CHECKPOINT_DIR))
    tok.save_pretrained(str(CHECKPOINT_DIR))
    torch.save(model.classifier.state_dict(), CHECKPOINT_DIR / "classifier.pt")


def load_ckpt(device):
    base  = AutoModel.from_pretrained(MODEL_NAME)
    enc   = PeftModel.from_pretrained(base, str(CHECKPOINT_DIR))
    model = ValueClassifier(enc, base.config.hidden_size).to(device)
    model.classifier.load_state_dict(
        torch.load(CHECKPOINT_DIR / "classifier.pt", map_location=device, weights_only=True)
    )
    return model


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    l1l2 = load_l1_to_l2()

    print("Loading model...")
    model, tok = build_model(device)

    print("Loading data...")
    train_ex = build_examples(TRAIN_ARTICLES, TRAIN_LABELS)
    dev_ex   = build_examples(DEV_ARTICLES,   DEV_LABELS)
    print(f"  train={len(train_ex)}  dev={len(dev_ex)}")

    kw = dict(batch_size=BATCH_SIZE, num_workers=4, pin_memory=True)
    train_dl = DataLoader(FehuDataset(train_ex, tok), shuffle=True,  **kw)
    dev_dl   = DataLoader(FehuDataset(dev_ex,   tok), shuffle=False, **kw)

    criterion = nn.BCEWithLogitsLoss(pos_weight=compute_pos_weight(train_ex, device))
    optimizer = AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    total_steps  = math.ceil(len(train_dl) / GRAD_ACCUM) * MAX_EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)
    sched = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    best_f1, no_imp = 0.0, 0
    for epoch in range(1, MAX_EPOCHS + 1):
        print(f"\n=== Epoch {epoch}/{MAX_EPOCHS} ===")
        loss = train_epoch(model, train_dl, optimizer, sched, criterion, device)
        print(f"  loss={loss:.4f}")

        f1 = eval_dev(model, dev_dl, device, l1l2, best_f1)

        if f1 > best_f1:
            best_f1, no_imp = f1, 0
            save_ckpt(model, tok)
            print(f"  checkpoint saved  (micro_f1={best_f1:.4f})")
        else:
            no_imp += 1
            print(f"  no improvement {no_imp}/{PATIENCE}")
            if no_imp >= PATIENCE:
                print("  early stop")
                break

    print(f"\nBest dev Task-1b micro_F1: {best_f1:.4f}")

    # Final predictions from best checkpoint
    print("\nGenerating final predictions from best model...")
    best = load_ckpt(device)
    raw  = infer(best, dev_dl, device)
    t1a, t1b = to_submission(raw, l1l2)
    (OUTPUT_DIR / "pred_task1a.json").write_text(
        json.dumps(t1a, ensure_ascii=False, indent=2)
    )
    (OUTPUT_DIR / "pred_task1b.json").write_text(
        json.dumps(t1b, ensure_ascii=False, indent=2)
    )
    print(f"Written to {OUTPUT_DIR}/")

    # Final evaluation
    from evaluation import (
        parse_task1a, parse_task1b, evaluate,
        l2_universe, l1_dir_universe, direction_reverse_rate_gold_excl,
    )
    g1a = parse_task1a(str(DEV_LABELS))
    r1a = evaluate(g1a, parse_task1a(str(OUTPUT_DIR / "pred_task1a.json")), l2_universe())
    g1b = parse_task1b(str(DEV_LABELS))
    pred_1b_path = str(OUTPUT_DIR / "pred_task1b.json")
    r1b = evaluate(g1b, parse_task1b(pred_1b_path), l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b, parse_task1b(pred_1b_path))

    print("\nFinal dev results:")
    print(f"  Task-1a  micro={r1a['micro_f1']:.4f}  macro={r1a['macro_f1']:.4f}")
    print(f"  Task-1b  micro={r1b['micro_f1']:.4f}  macro={r1b['macro_f1']:.4f}"
          f"  P={r1b['micro_precision']:.4f}  R={r1b['micro_recall']:.4f}")
    print(f"  DRR={drr:.4f}  (rev={rev}/{den}  amb={amb})")


if __name__ == "__main__":
    main()
