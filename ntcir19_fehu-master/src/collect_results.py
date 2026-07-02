#!/usr/bin/env python3
"""
Results collection script for FEHU Task-1.

Gathers DeBERTa-only, Hybrid, and Prompt-only results, evaluates each against
dev gold labels, prints a comparison table, and saves per-category analysis.

Run from project root:
    python src/collect_results.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from evaluation import (
    parse_task1a, parse_task1b, evaluate,
    l2_universe, l1_dir_universe, direction_reverse_rate_gold_excl,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
DEV_ARTICLES  = BASE_DIR / "dataset/dev/dev_event_base.json"
DEV_LABELS    = BASE_DIR / "dataset/gold_labels/dev/dev_human_values.json"
L1_FILE       = BASE_DIR / "dataset/hv_categories/human_value_level1_values.json"
L2_FILE       = BASE_DIR / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_FILE = BASE_DIR / "dataset/hv_categories/level_1_to_level_2.json"

# Canonical prompt-only caches (post-audit). The bare `cache_dev.json` is the
# legacy non-model-keyed cache from the pre-audit run_pipeline.py; it stays in
# the candidate list as a last-resort fallback so existing results remain
# regeneratable, but model-keyed caches are preferred.
PROMPT_CACHE_PATHS = [
    BASE_DIR / "logs/cache_dev_openai_gpt_4o_mini.json",
    BASE_DIR / "logs/cache_dev_openai_gpt_4o.json",
    BASE_DIR / "logs/cache_dev_openai.json",
    BASE_DIR / "logs/cache_dev.json",
]

# Canonical method folders. `output/task1/` is INTENTIONALLY OMITTED — it is a
# legacy ambiguous folder (run_pipeline.py and the older train_deberta.py both
# used to write there; current contents are a duplicate of task1_prompt/).
PROMPT_OUT  = BASE_DIR / "output/task1_prompt"
DEBERTA_OUT = BASE_DIR / "output/task1_deberta"
HYBRID_OUT  = BASE_DIR / "output/task1_hybrid"
OUTPUT_DIR  = BASE_DIR / "output"

# Legacy folder kept for reference only. Not used as a method source.
_LEGACY_AMBIGUOUS_OUT = BASE_DIR / "output/task1"


# ── Taxonomy ──────────────────────────────────────────────────────────────────
def load_taxonomy():
    """Return (l1_id_to_l2_id, l2_id_to_name)."""
    l1_name_to_id = json.loads(L1_FILE.read_text(encoding="utf-8"))
    l2_name_to_id = json.loads(L2_FILE.read_text(encoding="utf-8"))
    raw = json.loads(L1_TO_L2_FILE.read_text(encoding="utf-8"))["level_1_to_level_2"]
    l1_id_to_l2_id = {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}
    l2_id_to_name  = {v: k for k, v in l2_name_to_id.items()}
    return l1_id_to_l2_id, l2_id_to_name


# ── Prompt-only cache → submission format ─────────────────────────────────────
def find_prompt_cache():
    for p in PROMPT_CACHE_PATHS:
        if p.exists():
            return p
    return None


def convert_prompt_cache(cache_path, l1_id_to_l2_id):
    """
    Convert logs/cache_dev*.json to output/task1_prompt/pred_task1a.json and
    pred_task1b.json.  Cache format: {guid: [{actor_id, l1_value_id,
    direction ("aligned"/"contradictory"), reasoning}]}
    """
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    articles = json.loads(DEV_ARTICLES.read_text(encoding="utf-8"))
    article_by_guid = {str(a["guid"]): a for a in articles}

    t1a_all, t1b_all = [], []
    for guid_raw, gpt_results in cache.items():
        guid = str(guid_raw)
        article = article_by_guid.get(guid)
        if article is None:
            continue

        valid_actor_ids = {
            str(aid)
            for d in article.get("actors", [])
            for _, aid in d.items()
        }

        va, vb = [], []
        seen_1a, seen_1b = set(), set()

        for item in gpt_results:
            actor_id    = str(item.get("actor_id", ""))
            l1_id       = str(item.get("l1_value_id", ""))
            dir_word    = item.get("direction", "aligned")

            if actor_id not in valid_actor_ids:
                continue
            if not l1_id.isdigit() or not (0 <= int(l1_id) <= 53):
                continue

            direction = "1" if dir_word != "contradictory" else "0"
            l2_id = l1_id_to_l2_id.get(l1_id)
            if l2_id is None:
                continue

            if (actor_id, l2_id) not in seen_1a:
                seen_1a.add((actor_id, l2_id))
                va.append({"actor": actor_id, "l2_value": l2_id})

            if (actor_id, direction, l1_id) not in seen_1b:
                seen_1b.add((actor_id, direction, l1_id))
                vb.append({"actor": actor_id, "l1_value": l1_id, "direction": direction})

        t1a_all.append({"guid": guid, "article_human_values": va})
        t1b_all.append({"guid": guid, "article_human_values": vb})

    PROMPT_OUT.mkdir(parents=True, exist_ok=True)
    (PROMPT_OUT / "pred_task1a.json").write_text(
        json.dumps(t1a_all, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PROMPT_OUT / "pred_task1b.json").write_text(
        json.dumps(t1b_all, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Prompt-only predictions written to {PROMPT_OUT}/")
    return PROMPT_OUT / "pred_task1a.json", PROMPT_OUT / "pred_task1b.json"


# ── Evaluation ────────────────────────────────────────────────────────────────
def eval_result_set(pred_1a_path, pred_1b_path):
    """Return metrics dict, or None if either file is missing."""
    if not pred_1a_path.exists() or not pred_1b_path.exists():
        return None

    g1a = parse_task1a(str(DEV_LABELS))
    p1a = parse_task1a(str(pred_1a_path))
    r1a = evaluate(g1a, p1a, l2_universe())

    g1b = parse_task1b(str(DEV_LABELS))
    p1b = parse_task1b(str(pred_1b_path))
    r1b = evaluate(g1b, p1b, l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b, p1b)

    total_1a = sum(len(v) for v in p1a.values())
    total_1b = sum(len(v) for v in p1b.values())
    n_articles = len(json.loads(pred_1a_path.read_text(encoding="utf-8")))

    return {
        "task1a": {
            "micro_f1":  r1a["micro_f1"],
            "macro_f1":  r1a["macro_f1"],
            "precision": r1a["micro_precision"],
            "recall":    r1a["micro_recall"],
        },
        "task1b": {
            "micro_f1":  r1b["micro_f1"],
            "macro_f1":  r1b["macro_f1"],
            "precision": r1b["micro_precision"],
            "recall":    r1b["micro_recall"],
            "drr":       drr,
        },
        "total_predictions_1a":      total_1a,
        "total_predictions_1b":      total_1b,
        "avg_labels_per_article_1a": round(total_1a / max(n_articles, 1), 2),
    }


# ── Comparison table ──────────────────────────────────────────────────────────
def format_table(all_metrics):
    """Return the formatted comparison table as a string."""
    col_w = [16, 14, 14, 14, 14, 11, 8, 8]
    header = ["Method", "Task-1a MiF1", "Task-1a MaF1",
              "Task-1b MiF1", "Task-1b MaF1", "Precision", "Recall", "DRR"]

    def row(cells):
        return "| " + " | ".join(str(c).ljust(w - 2) for c, w in zip(cells, col_w)) + " |"

    sep = "+" + "+".join("-" * w for w in col_w) + "+"
    lines = [sep, row(header), sep]

    order = [("Prompt-only", "prompt_only"),
             ("DeBERTa-only", "deberta_only"),
             ("Hybrid", "hybrid")]

    for label, key in order:
        m = all_metrics.get(key)
        if m is None:
            lines.append(row([label] + ["N/A"] * 7))
        else:
            a, b = m["task1a"], m["task1b"]
            lines.append(row([
                label,
                f"{a['micro_f1']:.4f}",
                f"{a['macro_f1']:.4f}",
                f"{b['micro_f1']:.4f}",
                f"{b['macro_f1']:.4f}",
                f"{b['precision']:.4f}",
                f"{b['recall']:.4f}",
                f"{b['drr']:.4f}",
            ]))

    lines.append(sep)
    return "\n".join(lines)


# ── Per-category analysis ─────────────────────────────────────────────────────
def per_category_analysis(pred_1a_path, l2_id_to_name):
    """
    For each of the 20 L2 categories compute:
      gold_count, pred_count, recall_ratio (pred/gold)
    Uses Task-1a predictions (L2 labels).
    """
    g1a = parse_task1a(str(DEV_LABELS))
    p1a = parse_task1a(str(pred_1a_path))

    gold_counts = defaultdict(int)
    pred_counts = defaultdict(int)

    for labels in g1a.values():
        for lab in labels:
            gold_counts[lab] += 1

    for labels in p1a.values():
        for lab in labels:
            pred_counts[lab] += 1

    analysis = {}
    for l2_id in sorted(l2_universe(), key=int):
        gc = gold_counts[l2_id]
        pc = pred_counts[l2_id]
        analysis[l2_id] = {
            "l2_name":      l2_id_to_name.get(l2_id, f"category_{l2_id}"),
            "gold_count":   gc,
            "pred_count":   pc,
            "recall_ratio": round(pc / gc, 4) if gc > 0 else None,
        }
    return analysis


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("FEHU Task-1 Results Collection")
    print("=" * 60)

    l1_id_to_l2_id, l2_id_to_name = load_taxonomy()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Collect / convert result sets ─────────────────────────────────
    print("\n[Step 1] Collecting result sets...")

    result_paths = {
        "deberta_only": (DEBERTA_OUT / "pred_task1a.json",
                         DEBERTA_OUT / "pred_task1b.json"),
        "hybrid":       (HYBRID_OUT  / "pred_task1a.json",
                         HYBRID_OUT  / "pred_task1b.json"),
    }

    # Prompt-only: check for cache, convert if needed
    cache_path = find_prompt_cache()
    if cache_path:
        print(f"  Found prompt-only cache: {cache_path.name}")
        p1a, p1b = convert_prompt_cache(cache_path, l1_id_to_l2_id)
        result_paths["prompt_only"] = (p1a, p1b)
    else:
        print("  No prompt-only cache found (checked cache_dev_openai.json, cache_dev.json)")
        result_paths["prompt_only"] = (PROMPT_OUT / "pred_task1a.json",
                                       PROMPT_OUT / "pred_task1b.json")

    for name, (p1a, p1b) in result_paths.items():
        exists = p1a.exists() and p1b.exists()
        print(f"  {name:15s}: {'found' if exists else 'missing'}")

    # ── Step 2: Evaluate ──────────────────────────────────────────────────────
    print("\n[Step 2] Evaluating result sets...")
    all_metrics = {}
    for name, (p1a, p1b) in result_paths.items():
        m = eval_result_set(p1a, p1b)
        if m is None:
            print(f"  {name:15s}: skipped (files missing)")
        else:
            all_metrics[name] = m
            print(f"  {name:15s}: 1a micro={m['task1a']['micro_f1']:.4f}"
                  f"  1b micro={m['task1b']['micro_f1']:.4f}"
                  f"  DRR={m['task1b']['drr']:.4f}")

    # ── Step 3: Save comparison JSON ──────────────────────────────────────────
    print("\n[Step 3] Saving results_comparison.json...")
    comp_path = OUTPUT_DIR / "results_comparison.json"
    comp_path.write_text(
        json.dumps(all_metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Saved to {comp_path}")

    # ── Step 4: Print and save comparison table ───────────────────────────────
    print("\n[Step 4] Comparison table:\n")
    table = format_table(all_metrics)
    print(table)

    table_path = OUTPUT_DIR / "results_comparison_table.txt"
    table_path.write_text(table + "\n", encoding="utf-8")
    print(f"\n  Table saved to {table_path}")

    # ── Step 5: Per-category analysis ─────────────────────────────────────────
    print("\n[Step 5] Per-category analysis...")
    # Choose best available result set: hybrid > deberta_only > prompt_only
    best_key = next(
        (k for k in ("hybrid", "deberta_only", "prompt_only") if k in all_metrics),
        None,
    )
    if best_key is None:
        print("  No result sets available for per-category analysis.")
    else:
        pred_1a_path = result_paths[best_key][0]
        print(f"  Using {best_key} predictions for per-category analysis")
        cat_analysis = per_category_analysis(pred_1a_path, l2_id_to_name)

        cat_path = OUTPUT_DIR / "per_category_analysis.json"
        cat_path.write_text(
            json.dumps(cat_analysis, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Saved to {cat_path}")

        print("\n  L2 Category breakdown (gold → predicted, recall ratio):")
        for l2_id, stats in cat_analysis.items():
            rr = f"{stats['recall_ratio']:.3f}" if stats["recall_ratio"] is not None else " N/A"
            print(f"    [{l2_id:>2}] {stats['l2_name']:<35s}"
                  f"  gold={stats['gold_count']:>4}  pred={stats['pred_count']:>4}  ratio={rr}")

    print("\nDone.")


if __name__ == "__main__":
    main()
