#!/usr/bin/env python3
"""
Augmented DeBERTa v2-Unfiltered trainer — masked-loss copy of src/train_deberta.py.

This file is a copy of src/train_deberta.py (which is NOT modified) with ONE
functional addition: supervision-mode-aware loss masking.

  • --supervision_map (required): JSON {guid: {"supervision_mode": str,
    "known_negative": ["d:l1", ...]}}. Guids absent from the map (all official
    training articles) and guids with supervision_mode == "full_multilabel"
    are fully supervised: every one of the 108 classes contributes to the BCE
    loss exactly as in the original trainer (unspecified = negative).
  • Guids with supervision_mode == "target_only" are supervised ONLY on their
    explicitly known classes: the gold label entries (positives) and any
    known_negative classes (label 0). Every other class is UNKNOWN: its loss
    element is masked to zero and contributes no gradient.
  • Loss = sum(BCEWithLogits_elementwise * mask) / sum(mask)  per batch.
    With an all-ones mask this equals the original mean reduction exactly.
  • pos_weight uses the same formula as the original, generalized to count
    only supervised elements: w = sqrt(neg_supervised / pos_supervised)
    .clamp(1, 10). With all-ones masks it reduces to the original value.

Everything else — model (microsoft/deberta-v3-base), LoRA config (r=16,
alpha=32, dropout=0.1, query/value targets), optimizer (AdamW lr=2e-4,
wd=0.01), cosine schedule with 10% warmup, batch 8 x grad-accum 4, max 15
epochs, patience 4 on dev Task-1b micro-F1, threshold 0.3 default, seeding,
checkpoint format, inference, submission conversion, and evaluation — is
byte-identical to src/train_deberta.py.

108-class multi-label binary classification:
  label index = int(l1_value) * 2 + int(direction)
  direction: "0"=contradictory, "1"=aligned
"""

import argparse
import json
import math
import os
import re
import random
import shlex
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_cosine_schedule_with_warmup, set_seed as hf_set_seed
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from tqdm import tqdm

# This script lives in <run>/scripts/, not src/, so the project root is pinned
# explicitly to keep evaluation.py imports and official dataset paths identical
# to the original trainer.
BASE_DIR = Path("/home/szf-4090/projects/fehu-project/ntcir19_fehu-master")
sys.path.insert(0, str(BASE_DIR))

# ── Config ─────────────────────────────────────────────────────────────────────

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

# Default inference threshold; can be overridden by --threshold.
DEFAULT_THRESHOLD = 0.3
THRESHOLD         = DEFAULT_THRESHOLD   # global, set in main()

CHECKPOINT_DIR = BASE_DIR / "checkpoints" / "best_model"

# Canonical DeBERTa-only output (was output/task1/ before the audit fix).
DEFAULT_OUTPUT_DIR = BASE_DIR / "output" / "task1_deberta"

# OUTPUT_DIR is set in main() after CLI parsing.
OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def _safe_output_dir(base: Path, force_overwrite: bool):
    """Return (dir, used_timestamped_fallback)."""
    p1a = base / "pred_task1a.json"
    p1b = base / "pred_task1b.json"
    if base.exists() and (p1a.exists() or p1b.exists()) and not force_overwrite:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = base.parent / f"{base.name}_{ts}"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback, True
    base.mkdir(parents=True, exist_ok=True)
    return base, False


def _current_git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(BASE_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def set_seed(seed: int):
    """Deterministically seed Python, NumPy, PyTorch, CUDA, and Transformers.

    Only invoked when --seed is explicitly provided; otherwise the prior (unseeded)
    behavior is preserved exactly. Seeding the global torch generator also makes the
    DataLoader(shuffle=True) sampler order deterministic.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    hf_set_seed(seed)


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
def build_examples(articles_path, labels_path=None, supervision_map=None):
    """
    Returns list of dicts: guid, actor_id, actor_name, text, labels, loss_mask.
    labels is float32 tensor of shape (108,) when labels_path is given, else None.

    v2 masked-loss addition: loss_mask is a float32 tensor of shape (108,).
    For guids absent from supervision_map, or mapped to "full_multilabel",
    the mask is all ones (original fully-supervised behavior). For
    "target_only" guids the mask is 1 only at the gold-positive indices and
    any known_negative indices; every other class is unknown (mask 0).
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
            sup = (supervision_map or {}).get(guid)
            for actor_id, pairs in gold[guid].items():
                lv = torch.zeros(NUM_LABELS)
                for l1, d in pairs:
                    lv[l1 * 2 + d] = 1.0
                if sup is not None and sup["supervision_mode"] == "target_only":
                    mask = torch.zeros(NUM_LABELS)
                    for l1, d in pairs:
                        mask[l1 * 2 + d] = 1.0            # known positives
                    for key in sup.get("known_negative", []):
                        d_str, l1_str = key.split(":")
                        idx = int(l1_str) * 2 + int(d_str)
                        mask[idx] = 1.0                    # known negatives
                        assert lv[idx] == 0.0, (guid, key)  # never also a positive
                else:
                    mask = torch.ones(NUM_LABELS)          # fully supervised
                examples.append(dict(
                    guid=guid, actor_id=actor_id,
                    actor_name=id2name.get(actor_id, actor_id),
                    text=text, labels=lv, loss_mask=mask,
                ))
        else:
            for actor_id, actor_name in id2name.items():
                examples.append(dict(
                    guid=guid, actor_id=actor_id,
                    actor_name=actor_name, text=text, labels=None,
                    loss_mask=None,
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
            item["loss_mask"] = ex["loss_mask"]
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
    """Original formula generalized to supervised elements only.

    Original: w = sqrt((n - pos) / pos).clamp(1, 10), where every example
    supervises every class (n = len(examples)). Here positives and negatives
    are counted only where loss_mask == 1; with all-ones masks (fully
    supervised data) this reduces exactly to the original value.
    """
    labels = torch.stack([ex["labels"] for ex in examples])
    masks = torch.stack([ex["loss_mask"] for ex in examples])
    pos = (labels * masks).sum(0)
    neg = ((1.0 - labels) * masks).sum(0)
    w = (neg / pos.clamp(min=1)).sqrt().clamp(1.0, 10.0)
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
        lmask = batch["loss_mask"].to(device)
        ttids = batch.get("token_type_ids")
        if ttids is not None:
            ttids = ttids.to(device)

        # masked BCE: unknown label elements (mask 0) contribute no loss and
        # no gradient; with all-ones masks this equals the original mean.
        elementwise = criterion(model(ids, mask, ttids), labs)
        loss = (elementwise * lmask).sum() / lmask.sum().clamp(min=1.0) / GRAD_ACCUM
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


# ── CLI ────────────────────────────────────────────────────────────────────────
def parse_args():
    ap = argparse.ArgumentParser(description="DeBERTa-v3 + LoRA training for FEHU Task-1 (post-audit).")
    ap.add_argument("--output_dir", type=str, default=None,
                    help="Override prediction output dir. "
                         "Default: output/task1_deberta/  (was output/task1/ before audit fix).")
    ap.add_argument("--version", type=str, default=None,
                    help="Optional version tag appended to the output dir.")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help=f"Sigmoid threshold for final inference (default: {DEFAULT_THRESHOLD}).")
    ap.add_argument("--force_overwrite", action="store_true",
                    help="Overwrite existing predictions; otherwise a timestamped "
                         "sibling folder is used.")
    ap.add_argument("--train_articles", type=str, default=str(TRAIN_ARTICLES),
                    help="Path to the train event_base JSON (default: official train). "
                         "If explicitly set to a missing/invalid path, the run fails loudly; "
                         "there is no silent fallback to the official file.")
    ap.add_argument("--train_labels", type=str, default=str(TRAIN_LABELS),
                    help="Path to the train human_values (gold) JSON (default: official train). "
                         "If explicitly set to a missing/invalid path, the run fails loudly; "
                         "there is no silent fallback to the official file.")
    ap.add_argument("--seed", type=int, default=None,
                    help="If set, deterministically seed Python/NumPy/PyTorch/CUDA/Transformers. "
                         "Default None preserves the prior (unseeded) behavior.")
    ap.add_argument("--checkpoint_dir", type=str, default=None,
                    help=f"Override checkpoint dir (default: {CHECKPOINT_DIR}). Use per-condition "
                         "dirs to isolate baseline vs augmented checkpoints.")
    ap.add_argument("--supervision_map", type=str, required=True,
                    help="Required JSON map {guid: {supervision_mode, known_negative}} controlling "
                         "loss masking. Guids absent from the map are fully supervised (official).")
    ap.add_argument("--neg_sample_targets", type=str, default=None,
                    help="Phase-3 addition: path to a JSON list of direction-aware class keys "
                         "(\"d:l1\") whose supervised training NEGATIVES are randomly down-sampled. "
                         "Requires --neg_pos_ratio. Positives and known negatives from "
                         "hard-negative records are never removed; masked (unknown) slots are "
                         "never eligible.")
    ap.add_argument("--neg_pos_ratio", type=float, default=None,
                    help="Phase-3 addition: keep at most ceil(ratio * supervised_positives) "
                         "supervised negatives per listed class (e.g. 3.0 for 1:3, 1.0 for 1:1). "
                         "Sampling uses a dedicated RNG seeded from --seed, so the training "
                         "example stream is unchanged relative to a run without down-sampling.")
    return ap.parse_args()


def downsample_negatives(train_ex, class_keys, ratio, seed):
    """Phase-3 addition: per-class negative down-sampling via loss masks.

    For each listed class: among examples where the class is a SUPERVISED
    NEGATIVE (loss_mask==1, label==0), keep a random ceil(ratio * n_pos)
    subset and set loss_mask=0 on the rest. Positives are untouched;
    already-masked (unknown) slots are untouched. Deterministic per seed via
    a dedicated RNG (does not perturb the global random stream). Fails hard
    on an invalid class key or a class with zero supervised positives
    (ratio would be degenerate)."""
    rng = random.Random(0 if seed is None else seed)
    summary = []
    for key in class_keys:
        d_str, l1_str = key.split(":")
        if d_str not in ("0", "1") or not (0 <= int(l1_str) <= 53):
            raise SystemExit(f"ERROR: invalid --neg_sample_targets key: {key}")
        idx = int(l1_str) * 2 + int(d_str)
        neg_i, n_pos = [], 0
        for i, ex in enumerate(train_ex):
            if ex["loss_mask"][idx] == 1.0:
                if ex["labels"][idx] == 1.0:
                    n_pos += 1
                else:
                    neg_i.append(i)
        if n_pos == 0:
            raise SystemExit(f"ERROR: class {key} has no supervised positives; "
                             f"down-sampling ratio is undefined")
        keep = math.ceil(ratio * n_pos)
        if keep < len(neg_i):
            kept = set(rng.sample(neg_i, keep))
            for i in neg_i:
                if i not in kept:
                    train_ex[i]["loss_mask"][idx] = 0.0
            summary.append((key, n_pos, len(neg_i), keep))
        else:
            summary.append((key, n_pos, len(neg_i), len(neg_i)))
    print("  negative down-sampling (class, pos, neg_before, neg_kept):")
    for row in summary:
        print(f"    {row[0]}: pos={row[1]} neg={row[2]} -> kept={row[3]}")
    return summary


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    global THRESHOLD, OUTPUT_DIR, CHECKPOINT_DIR
    args = parse_args()
    THRESHOLD = args.threshold

    # Deterministic seeding — only when explicitly requested; default None preserves prior behavior.
    if args.seed is not None:
        set_seed(args.seed)

    # Resolve training input paths (defaults = official constants). No silent fallback: an explicitly
    # provided missing/invalid path fails loudly rather than reverting to the official train file.
    train_articles = Path(args.train_articles)
    train_labels   = Path(args.train_labels)
    supervision_path = Path(args.supervision_map)
    for flag, p in (("--train_articles", train_articles), ("--train_labels", train_labels),
                    ("--supervision_map", supervision_path)):
        if not p.is_file():
            raise SystemExit(f"ERROR: {flag} path does not exist or is not a file: {p}")
    supervision_map = json.loads(supervision_path.read_text())

    # Resolve checkpoint dir (default = CHECKPOINT_DIR constant) so baseline/augmented runs can
    # isolate their checkpoints. Applied to the module global used by save_ckpt/load_ckpt.
    if args.checkpoint_dir:
        cp = Path(args.checkpoint_dir)
        CHECKPOINT_DIR = cp if cp.is_absolute() else (BASE_DIR / cp)

    # Resolve output dir (overwrite-safe).
    if args.output_dir:
        out_root = Path(args.output_dir)
        if not out_root.is_absolute():
            out_root = BASE_DIR / out_root
    else:
        suffix = f"_{args.version}" if args.version else ""
        out_root = DEFAULT_OUTPUT_DIR if not suffix else (
            BASE_DIR / "output" / f"task1_deberta{suffix}"
        )
    OUTPUT_DIR, used_fallback = _safe_output_dir(out_root, args.force_overwrite)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device:    {device}")
    print(f"Output:    {OUTPUT_DIR}")
    if used_fallback:
        print("  [INFO] Target folder existed → wrote to timestamped sibling.")
    print(f"Threshold: {THRESHOLD}")

    l1l2 = load_l1_to_l2()

    print("Loading model...")
    model, tok = build_model(device)

    print("Loading data...")
    train_ex = build_examples(train_articles, train_labels, supervision_map)
    dev_ex   = build_examples(DEV_ARTICLES,   DEV_LABELS)
    n_masked = sum(1 for ex in train_ex if ex["loss_mask"].sum().item() < NUM_LABELS)
    n_full   = len(train_ex) - n_masked
    print(f"  train={len(train_ex)}  dev={len(dev_ex)}")
    print(f"  supervision: fully_supervised={n_full}  target_only_masked={n_masked}")

    # Phase-3 addition: optional per-class negative down-sampling (before
    # pos_weight computation, which already respects masks).
    if (args.neg_sample_targets is None) != (args.neg_pos_ratio is None):
        raise SystemExit("ERROR: --neg_sample_targets and --neg_pos_ratio must be "
                         "given together")
    if args.neg_sample_targets is not None:
        ns_path = Path(args.neg_sample_targets)
        if not ns_path.is_file():
            raise SystemExit(f"ERROR: --neg_sample_targets path does not exist: {ns_path}")
        class_keys = json.loads(ns_path.read_text())
        if not isinstance(class_keys, list) or not class_keys:
            raise SystemExit("ERROR: --neg_sample_targets must be a non-empty JSON list")
        if args.neg_pos_ratio <= 0:
            raise SystemExit("ERROR: --neg_pos_ratio must be positive")
        downsample_negatives(train_ex, class_keys, args.neg_pos_ratio, args.seed)

    kw = dict(batch_size=BATCH_SIZE, num_workers=4, pin_memory=True)
    train_dl = DataLoader(FehuDataset(train_ex, tok), shuffle=True,  **kw)
    dev_dl   = DataLoader(FehuDataset(dev_ex,   tok), shuffle=False, **kw)

    # reduction="none" + explicit masked mean in train_epoch; identical to the
    # original mean-reduction loss whenever every mask element is 1.
    criterion = nn.BCEWithLogitsLoss(pos_weight=compute_pos_weight(train_ex, device),
                                     reduction="none")
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

    # ── run_config.json (post-audit provenance) ────────────────────────────────
    run_config = {
        "script":      "scripts/train_deberta_masked_v2.py (masked-loss copy of src/train_deberta.py)",
        "method":      "deberta_lora_masked_supervision",
        "supervision_map": str(supervision_path),
        "supervision_counts": {"fully_supervised_examples": n_full,
                               "target_only_masked_examples": n_masked},
        "base_model":  MODEL_NAME,
        "num_labels":  NUM_LABELS,
        "max_length":  MAX_LENGTH,
        "lora_config": {
            "r": 16, "lora_alpha": 32, "lora_dropout": 0.1,
            "task_type": "SEQ_CLS",
        },
        "threshold":   THRESHOLD,
        "seed":        args.seed,
        "hyperparameters": {
            "batch_size":   BATCH_SIZE,
            "grad_accum":   GRAD_ACCUM,
            "max_epochs":   MAX_EPOCHS,
            "lr":           LR,
            "weight_decay": WEIGHT_DECAY,
            "warmup_ratio": WARMUP_RATIO,
            "patience":     PATIENCE,
        },
        "best_dev_task1b_micro_f1": best_f1,
        "output_dir":    str(OUTPUT_DIR),
        "checkpoint_dir": str(CHECKPOINT_DIR),
        "version":       args.version,
        "command_line":  " ".join(shlex.quote(a) for a in sys.argv),
        "git_commit":    _current_git_commit(),
        "device":        str(device),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "dataset_paths": {
            "train_articles": str(train_articles),
            "train_labels":   str(train_labels),
            "dev_articles":   str(DEV_ARTICLES),
            "dev_labels":     str(DEV_LABELS),
            "l1_file":        str(L1_FILE),
            "l2_file":        str(L2_FILE),
            "l1_to_l2_file":  str(L1_TO_L2_FILE),
        },
        "notes": (
            "DeBERTa-v3 + LoRA training (post-audit). Default output dir is "
            "output/task1_deberta/. Pass --threshold to control inference cutoff."
        ),
    }
    (OUTPUT_DIR / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

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
