#!/usr/bin/env python3
"""
Regenerate DeBERTa-only predictions, saved to output/task1_deberta/.

Matches the inference step at the end of train_deberta.py exactly:
  - same load_ckpt() call
  - same build_examples(DEV_ARTICLES, DEV_LABELS)  ← labeled actors only
  - same infer() with THRESHOLD=0.3 (override via --threshold)
  - same to_submission() conversion

Post-audit additions:
  - run_config.json written next to predictions (provenance).
  - --output_dir / --threshold / --force_overwrite CLI args.

Run from project root:
    python src/regenerate_deberta_predictions.py
    python src/regenerate_deberta_predictions.py --threshold 0.2
"""

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from train_deberta import (
    MODEL_NAME, CHECKPOINT_DIR,
    DEV_ARTICLES, DEV_LABELS,
    load_l1_to_l2, load_ckpt,
    build_examples, FehuDataset,
    infer, to_submission,
)
import train_deberta as td  # to tweak THRESHOLD before infer()

from evaluation import (
    parse_task1a, parse_task1b, evaluate,
    l2_universe, l1_dir_universe, direction_reverse_rate_gold_excl,
)

DEFAULT_OUTPUT_DIR = BASE_DIR / "output" / "task1_deberta"


def _safe_output_dir(base: Path, force: bool):
    p1a = base / "pred_task1a.json"
    p1b = base / "pred_task1b.json"
    if base.exists() and (p1a.exists() or p1b.exists()) and not force:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = base.parent / f"{base.name}_{ts}"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback, True
    base.mkdir(parents=True, exist_ok=True)
    return base, False


def _git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(BASE_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def parse_args():
    ap = argparse.ArgumentParser(description="Regenerate DeBERTa-only predictions (post-audit).")
    ap.add_argument("--output_dir", type=str, default=None,
                    help="Override output dir (default: output/task1_deberta/).")
    ap.add_argument("--threshold", type=float, default=td.DEFAULT_THRESHOLD,
                    help=f"Sigmoid threshold (default: {td.DEFAULT_THRESHOLD}).")
    ap.add_argument("--force_overwrite", action="store_true",
                    help="Overwrite existing predictions instead of writing to a timestamped sibling.")
    return ap.parse_args()


def main():
    args = parse_args()
    td.THRESHOLD = args.threshold  # override module-level constant before infer()

    out_root = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    if not out_root.is_absolute():
        out_root = BASE_DIR / out_root
    OUTPUT_DIR, used_fallback = _safe_output_dir(out_root, args.force_overwrite)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device:    {device}")
    print(f"Output:    {OUTPUT_DIR}")
    if used_fallback:
        print("  [INFO] Target folder existed → wrote to timestamped sibling.")
    print(f"Threshold: {args.threshold}")

    l1l2 = load_l1_to_l2()

    print("Loading DeBERTa model from checkpoint...")
    model = load_ckpt(device)

    # Match train_deberta.py exactly: use DEV_LABELS so only gold-labeled actors
    # are included — this is identical to how dev_dl was built during training.
    print("Building dev examples (gold-labeled actors)...")
    dev_ex = build_examples(DEV_ARTICLES, DEV_LABELS)
    print(f"  {len(dev_ex)} (article, actor) examples")

    # Load tokenizer from the checkpoint directory (saved there by save_ckpt).
    tok = AutoTokenizer.from_pretrained(str(CHECKPOINT_DIR))

    dev_dl = DataLoader(
        FehuDataset(dev_ex, tok),
        batch_size=16, shuffle=False, num_workers=4, pin_memory=True,
    )

    print("Running inference (threshold=0.3)...")
    raw = infer(model, dev_dl, device)

    print("Converting to submission format...")
    t1a, t1b = to_submission(raw, l1l2)

    out_1a = OUTPUT_DIR / "pred_task1a.json"
    out_1b = OUTPUT_DIR / "pred_task1b.json"
    out_1a.write_text(json.dumps(t1a, ensure_ascii=False, indent=2), encoding="utf-8")
    out_1b.write_text(json.dumps(t1b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {OUTPUT_DIR}/")

    # ── run_config.json (post-audit provenance) ────────────────────────────────
    run_config = {
        "script":          "src/regenerate_deberta_predictions.py",
        "method":          "deberta_lora_inference",
        "base_model":      MODEL_NAME,
        "checkpoint_dir":  str(CHECKPOINT_DIR),
        "threshold":       args.threshold,
        "output_dir":      str(OUTPUT_DIR),
        "command_line":    " ".join(shlex.quote(a) for a in sys.argv),
        "git_commit":      _git_commit(),
        "device":          str(device),
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "notes": (
            "Inference re-run using DeBERTa+LoRA checkpoint. Predictions cover "
            "gold-labeled actors only (mirrors train_deberta.py eval setup)."
        ),
    }
    (OUTPUT_DIR / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Evaluate immediately so the user can verify correctness.
    print("\nEvaluating DeBERTa-only predictions...")
    g1a = parse_task1a(str(DEV_LABELS))
    r1a = evaluate(g1a, parse_task1a(str(out_1a)), l2_universe())
    g1b = parse_task1b(str(DEV_LABELS))
    r1b = evaluate(g1b, parse_task1b(str(out_1b)), l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b, parse_task1b(str(out_1b)))

    print("\nDeBERTa-only dev results:")
    print(f"  Task-1a  micro={r1a['micro_f1']:.4f}  macro={r1a['macro_f1']:.4f}"
          f"  P={r1a['micro_precision']:.4f}  R={r1a['micro_recall']:.4f}")
    print(f"  Task-1b  micro={r1b['micro_f1']:.4f}  macro={r1b['macro_f1']:.4f}"
          f"  P={r1b['micro_precision']:.4f}  R={r1b['micro_recall']:.4f}")
    print(f"  DRR={drr:.4f}  (rev={rev}/{den}  amb={amb})")


if __name__ == "__main__":
    main()
