#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_augmentation_v1/build_augmentation_plan.py

Diagnosis-driven planner for the FEHU augmentation pipeline (v1, planning stage).

Reads an existing label-diagnosis output and produces a plan: which L1 labels
to target, which augmentation types to apply, what budget to allocate, and
which TRAIN gold instances to use as seeds. DOES NOT GENERATE ANY DATA.

Run from project root:
    python research/fehu_augmentation_v1/build_augmentation_plan.py \
        --diagnosis_dir output/research_label_diagnosis/20260613_145847 \
        --max_labels 20 \
        --budget_profile pilot

Output: output/research_augmentation_plan/YYYYMMDD_HHMMSS/
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ============================================================
# PATHS
# ============================================================

TRAIN_ARTICLES = PROJECT_ROOT / "dataset/train/train_event_base.json"
TRAIN_LABELS   = PROJECT_ROOT / "dataset/gold_labels/train/train_human_values.json"

L1_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level1_values.json"
L2_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_PATH  = PROJECT_ROOT / "dataset/hv_categories/level_1_to_level_2.json"
DIR_MAP_PATH   = PROJECT_ROOT / "dataset/hv_categories/direction_mapping.json"

# ============================================================
# BUDGET POLICIES
# ============================================================

BUDGET_PROFILES: Dict[str, Dict[str, int]] = {
    "pilot":  {"rare_positive": 3,  "paraphrase_per_seed": 3,  "paraphrase_per_label_max": 9,  "hard_negative": 3,  "direction_contrastive_pairs": 2},
    "medium": {"rare_positive": 8,  "paraphrase_per_seed": 6,  "paraphrase_per_label_max": 20, "hard_negative": 8,  "direction_contrastive_pairs": 5},
    "full":   {"rare_positive": 20, "paraphrase_per_seed": 8,  "paraphrase_per_label_max": 50, "hard_negative": 20, "direction_contrastive_pairs": 10},
}

PRIORITY_WEIGHTS = {
    "rare_score":            0.40,
    "low_recall_score":      0.25,
    "direction_error_score": 0.20,
    "false_positive_score":  0.15,
}

# ============================================================
# IO
# ============================================================

def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def read_csv(p: Path) -> List[Dict]:
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(rows: List[Dict], p: Path, fieldnames: Optional[List[str]] = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_jsonl(items: List[Dict], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def safe_float(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def safe_int(s, default=0):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


# ============================================================
# TAXONOMY
# ============================================================

def load_taxonomy() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]:
    """Return (l1_id_to_name, l2_id_to_name, l1_id_to_l2_id, direction_mapping)."""
    l1_name_to_id = load_json(L1_VALUES_PATH)
    l2_name_to_id = load_json(L2_VALUES_PATH)
    raw           = load_json(L1_TO_L2_PATH)["level_1_to_level_2"]
    dir_map       = load_json(DIR_MAP_PATH)  # {"aligned": "1", "contradictory": "0"}

    l1_id_to_name = {v: k for k, v in l1_name_to_id.items()}
    l2_id_to_name = {v: k for k, v in l2_name_to_id.items()}
    l1_id_to_l2_id = {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}
    return l1_id_to_name, l2_id_to_name, l1_id_to_l2_id, dir_map


# ============================================================
# DIAGNOSIS INGESTION
# ============================================================

@dataclass
class LabelAggregates:
    """Aggregated stats per L1 label from the diagnosis CSVs."""
    l1_id: str
    l1_name: str
    train_count: int
    dev_count: int
    tertile_group: str
    threshold_group: str
    rank_by_train: int
    n_rare_low_recall_rows: int            # appears in rare_low_recall_labels.csv
    n_fp_rows: int                          # appears in high_false_positive_labels.csv
    n_dir_err_rows: int                     # appears in high_direction_error_labels.csv
    mean_recall_dir: float                  # over methods present
    min_recall_dir: float
    mean_direction_reverse_rate: float
    max_direction_reverse_rate: float
    mean_precision_value: float
    min_precision_value: float
    suggested_actions: List[str]


def ingest_diagnosis(diag_dir: Path) -> Dict[str, LabelAggregates]:
    label_freq      = read_csv(diag_dir / "label_frequency_l1.csv")
    rare_low_recall = read_csv(diag_dir / "rare_low_recall_labels.csv")
    high_fp         = read_csv(diag_dir / "high_false_positive_labels.csv")
    high_de         = read_csv(diag_dir / "high_direction_error_labels.csv")

    if not label_freq:
        raise SystemExit(f"label_frequency_l1.csv not found in {diag_dir}")

    label_meta: Dict[str, LabelAggregates] = {}
    for r in label_freq:
        l1 = r["l1_value_id"]
        label_meta[l1] = LabelAggregates(
            l1_id=l1,
            l1_name=r["l1_value_name"],
            train_count=safe_int(r["train_gold_count_l1"]),
            dev_count=safe_int(r["dev_gold_count_l1"]),
            tertile_group=r.get("tertile_group", "unknown"),
            threshold_group=r.get("threshold_group", "unknown"),
            rank_by_train=safe_int(r.get("rank_by_train_frequency", 99)),
            n_rare_low_recall_rows=0,
            n_fp_rows=0,
            n_dir_err_rows=0,
            mean_recall_dir=1.0,
            min_recall_dir=1.0,
            mean_direction_reverse_rate=0.0,
            max_direction_reverse_rate=0.0,
            mean_precision_value=1.0,
            min_precision_value=1.0,
            suggested_actions=[],
        )

    # Aggregate over diagnosis tables
    recall_dirs_by_l1: Dict[str, List[float]] = defaultdict(list)
    drr_by_l1: Dict[str, List[float]] = defaultdict(list)
    precision_by_l1: Dict[str, List[float]] = defaultdict(list)
    actions_by_l1: Dict[str, set] = defaultdict(set)

    for r in rare_low_recall:
        l1 = r["l1_value_id"]
        if l1 in label_meta:
            label_meta[l1].n_rare_low_recall_rows += 1
            recall_dirs_by_l1[l1].append(safe_float(r["recall_dir"]))
            if "suggested_future_action" in r:
                actions_by_l1[l1].add(r["suggested_future_action"])

    for r in high_fp:
        l1 = r["l1_value_id"]
        if l1 in label_meta:
            label_meta[l1].n_fp_rows += 1
            precision_by_l1[l1].append(safe_float(r["precision_value"]))
            actions_by_l1[l1].add("hard_negative_needed")

    for r in high_de:
        l1 = r["l1_value_id"]
        if l1 in label_meta:
            label_meta[l1].n_dir_err_rows += 1
            drr_by_l1[l1].append(safe_float(r["direction_reverse_rate_label"]))
            actions_by_l1[l1].add("direction_contrastive_augmentation")

    for l1, m in label_meta.items():
        if recall_dirs_by_l1[l1]:
            m.mean_recall_dir = sum(recall_dirs_by_l1[l1]) / len(recall_dirs_by_l1[l1])
            m.min_recall_dir  = min(recall_dirs_by_l1[l1])
        if drr_by_l1[l1]:
            m.mean_direction_reverse_rate = sum(drr_by_l1[l1]) / len(drr_by_l1[l1])
            m.max_direction_reverse_rate  = max(drr_by_l1[l1])
        if precision_by_l1[l1]:
            m.mean_precision_value = sum(precision_by_l1[l1]) / len(precision_by_l1[l1])
            m.min_precision_value  = min(precision_by_l1[l1])
        m.suggested_actions = sorted(actions_by_l1[l1])

    return label_meta


# ============================================================
# PRIORITY SCORING
# ============================================================

def compute_priority_scores(label_meta: Dict[str, LabelAggregates]) -> List[Dict]:
    """Return list of per-label scoring rows (one per L1 label that has any flag)."""
    if not label_meta:
        return []

    # Robust normalisation: use max train count for rare_score.
    max_train = max(m.train_count for m in label_meta.values()) or 1
    max_drr   = max((m.max_direction_reverse_rate for m in label_meta.values()), default=0.0) or 1.0

    rows = []
    for l1, m in label_meta.items():
        # Only score labels that appear in at least one diagnostic table
        if (m.n_rare_low_recall_rows + m.n_fp_rows + m.n_dir_err_rows) == 0:
            continue

        rare_score = 1.0 - min(m.train_count / max_train, 1.0)
        low_recall_score = max(0.0, 1.0 - m.mean_recall_dir) if m.n_rare_low_recall_rows > 0 else 0.0
        direction_error_score = (m.max_direction_reverse_rate / max_drr) if m.n_dir_err_rows > 0 else 0.0
        false_positive_score = max(0.0, 1.0 - m.mean_precision_value) if m.n_fp_rows > 0 else 0.0

        priority = (
            PRIORITY_WEIGHTS["rare_score"]            * rare_score +
            PRIORITY_WEIGHTS["low_recall_score"]      * low_recall_score +
            PRIORITY_WEIGHTS["direction_error_score"] * direction_error_score +
            PRIORITY_WEIGHTS["false_positive_score"]  * false_positive_score
        )

        # Determine augmentation types triggered for this label
        types: List[str] = []
        if m.n_rare_low_recall_rows > 0:
            types.extend(["rare_positive", "paraphrase"])
        if m.n_fp_rows > 0:
            types.append("hard_negative")
        if m.n_dir_err_rows > 0:
            types.append("direction_contrastive")
        # de-dup preserving order
        seen = set(); types = [t for t in types if not (t in seen or seen.add(t))]

        rows.append({
            "l1_value_id":              l1,
            "l1_value_name":            m.l1_name,
            "tertile_group":            m.tertile_group,
            "threshold_group":          m.threshold_group,
            "rank_by_train_frequency":  m.rank_by_train,
            "train_gold_count_l1":      m.train_count,
            "dev_gold_count_l1":        m.dev_count,
            "n_rare_low_recall_rows":   m.n_rare_low_recall_rows,
            "n_high_fp_rows":           m.n_fp_rows,
            "n_high_direction_err_rows": m.n_dir_err_rows,
            "mean_recall_dir":          round(m.mean_recall_dir, 4),
            "min_recall_dir":           round(m.min_recall_dir,  4),
            "mean_direction_reverse_rate": round(m.mean_direction_reverse_rate, 4),
            "max_direction_reverse_rate":  round(m.max_direction_reverse_rate,  4),
            "mean_precision_value":     round(m.mean_precision_value, 4),
            "rare_score":               round(rare_score, 4),
            "low_recall_score":         round(low_recall_score, 4),
            "direction_error_score":    round(direction_error_score, 4),
            "false_positive_score":     round(false_positive_score, 4),
            "priority_score":           round(priority, 4),
            "augmentation_types":       "|".join(types),
            "suggested_actions":        "|".join(m.suggested_actions),
        })

    rows.sort(key=lambda r: -r["priority_score"])
    return rows


# ============================================================
# SEED EXTRACTION  (TRAIN gold only)
# ============================================================

def extract_seeds(selected_l1_ids: List[str],
                  l1_id_to_name: Dict[str, str],
                  l2_id_to_name: Dict[str, str],
                  l1_id_to_l2_id: Dict[str, str],
                  max_seeds_per_label: int = 10,
                  seed: int = 42) -> Tuple[List[Dict], Dict[str, str]]:
    """
    Returns (seed_records, seed_status_by_l1).

    seed_status: 'has_seeds' | 'no_article_seed'
    """
    rng = random.Random(seed)

    train_articles = load_json(TRAIN_ARTICLES)
    train_labels   = load_json(TRAIN_LABELS)
    article_by_guid = {str(a["guid"]): a for a in train_articles}

    # Build actor_id → name map per article
    def actor_name_for(article: Dict, actor_id: str) -> str:
        for d in article.get("actors", []):
            for name, aid in d.items():
                if str(aid) == actor_id:
                    return name
        return ""

    # Group train gold items by (l1_id) — one record per (guid, actor, l1)
    items_by_l1: Dict[str, List[Dict]] = defaultdict(list)
    for entry in train_labels:
        guid = str(entry["guid"])
        article = article_by_guid.get(guid, {})
        for hv in entry.get("article_human_values", []):
            l1 = str(hv["l1_value"])
            if l1 not in selected_l1_ids:
                continue
            actor_id = str(hv["actor"])
            l2 = str(hv.get("l2_value", l1_id_to_l2_id.get(l1, "?")))
            direction = str(hv["direction"])
            content   = article.get("content", "")
            items_by_l1[l1].append({
                "guid":             guid,
                "title":            article.get("title", ""),
                "content_excerpt":  content[:2000],
                "actor_id":         actor_id,
                "actor_name":       actor_name_for(article, actor_id),
                "l1_value_id":      l1,
                "l1_value_name":    l1_id_to_name.get(l1, f"L1_{l1}"),
                "l2_value_id":      l2,
                "l2_value_name":    l2_id_to_name.get(l2, "?"),
                "direction":        direction,
                "direction_name":   "aligned" if direction == "1" else "contradictory",
                "explanation":      hv.get("explanation", ""),
                "source":           "train_article_human_values",
            })

    seed_records: List[Dict] = []
    seed_status: Dict[str, str] = {}
    for l1 in selected_l1_ids:
        pool = items_by_l1.get(l1, [])
        if not pool:
            seed_status[l1] = "no_article_seed"
            continue
        seed_status[l1] = "has_seeds"
        # Take up to max_seeds_per_label, sampled deterministically
        if len(pool) > max_seeds_per_label:
            sampled = rng.sample(pool, max_seeds_per_label)
        else:
            sampled = list(pool)
        # Also try to include both directions if available
        sampled.sort(key=lambda x: x["direction"])
        seed_records.extend(sampled)

    return seed_records, seed_status


# ============================================================
# BUDGET PLANNING
# ============================================================

def build_label_plan(scored_rows: List[Dict],
                     seed_status: Dict[str, str],
                     budget: Dict[str, int]) -> List[Dict]:
    plan_rows: List[Dict] = []
    for r in scored_rows:
        l1 = r["l1_value_id"]
        triggered = set(r["augmentation_types"].split("|")) if r["augmentation_types"] else set()
        status = seed_status.get(l1, "no_article_seed")

        n_rare_positive = budget["rare_positive"] if "rare_positive" in triggered else 0
        n_paraphrase    = budget["paraphrase_per_label_max"] if "paraphrase" in triggered and status == "has_seeds" else 0
        n_hard_negative = budget["hard_negative"] if "hard_negative" in triggered else 0
        n_dir_pairs     = budget["direction_contrastive_pairs"] if "direction_contrastive" in triggered else 0

        # If no seed, paraphrase falls back to 0 and we suggest definition-guided generation
        fallback_note = ""
        if "paraphrase" in triggered and status == "no_article_seed":
            fallback_note = "no_train_seed_for_paraphrase__use_definition_guided_generation"

        total_samples = n_rare_positive + n_paraphrase + n_hard_negative + (n_dir_pairs * 2)
        plan_rows.append({
            "l1_value_id":               l1,
            "l1_value_name":             r["l1_value_name"],
            "priority_score":            r["priority_score"],
            "tertile_group":             r["tertile_group"],
            "threshold_group":           r["threshold_group"],
            "train_gold_count_l1":       r["train_gold_count_l1"],
            "augmentation_types":       r["augmentation_types"],
            "seed_status":              status,
            "n_rare_positive":           n_rare_positive,
            "n_paraphrase":              n_paraphrase,
            "n_hard_negative":           n_hard_negative,
            "n_direction_contrastive_pairs": n_dir_pairs,
            "n_total_samples":           total_samples,
            "fallback_note":             fallback_note,
        })
    return plan_rows


def budget_summary(plan_rows: List[Dict], budget_name: str) -> List[Dict]:
    by_type = {
        "rare_positive":         sum(r["n_rare_positive"] for r in plan_rows),
        "paraphrase":            sum(r["n_paraphrase"] for r in plan_rows),
        "hard_negative":         sum(r["n_hard_negative"] for r in plan_rows),
        "direction_contrastive": sum(r["n_direction_contrastive_pairs"] for r in plan_rows) * 2,
    }
    grand = sum(by_type.values())
    rows = [
        {"category": k, "n_samples": v, "budget_profile": budget_name}
        for k, v in by_type.items()
    ]
    rows.append({"category": "TOTAL", "n_samples": grand, "budget_profile": budget_name})
    return rows


# ============================================================
# TARGET LABEL DEFINITIONS  (for use in prompt blueprints)
# ============================================================

def build_definitions(selected_rows: List[Dict],
                      label_meta: Dict[str, LabelAggregates],
                      l1_id_to_name: Dict[str, str],
                      l2_id_to_name: Dict[str, str],
                      l1_id_to_l2_id: Dict[str, str]) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for r in selected_rows:
        l1 = r["l1_value_id"]
        m = label_meta[l1]
        out[l1] = {
            "l1_value_id":         l1,
            "l1_value_name":       l1_id_to_name.get(l1, f"L1_{l1}"),
            "l2_value_id":         l1_id_to_l2_id.get(l1, "?"),
            "l2_value_name":       l2_id_to_name.get(l1_id_to_l2_id.get(l1, "?"), "?"),
            "train_count":         m.train_count,
            "dev_count":           m.dev_count,
            "tertile_group":       m.tertile_group,
            "threshold_group":     m.threshold_group,
            "mean_recall_dir":     round(m.mean_recall_dir, 4),
            "mean_direction_reverse_rate": round(m.mean_direction_reverse_rate, 4),
            "augmentation_types":  r["augmentation_types"].split("|") if r["augmentation_types"] else [],
            "suggested_actions":   r["suggested_actions"].split("|") if r["suggested_actions"] else [],
            "augmentation_rationale": _build_rationale(m),
        }
    return out


def _build_rationale(m: LabelAggregates) -> str:
    bits = []
    if m.threshold_group in ("zero_train", "very_rare", "rare") or m.tertile_group == "rare":
        bits.append(f"rare (train={m.train_count}, group={m.threshold_group})")
    if m.mean_recall_dir < 0.30:
        bits.append(f"low recall (mean_recall_dir={m.mean_recall_dir:.3f})")
    if m.max_direction_reverse_rate > 0.30:
        bits.append(f"high direction error (max_drr_label={m.max_direction_reverse_rate:.3f})")
    if m.mean_precision_value < 0.30 and m.n_fp_rows > 0:
        bits.append(f"low precision / over-predicted (mean_prec={m.mean_precision_value:.3f})")
    return "; ".join(bits) if bits else "diagnosis-flagged label"


# ============================================================
# PROMPT BLUEPRINTS  (just templates; not run here)
# ============================================================

PROMPT_BLUEPRINTS_MD = """\
# FEHU Augmentation Prompt Blueprints (planning stage)

These are **templates only**. No prompt below has been executed.
Direction encoding follows `direction_mapping.json`: `"1"` = aligned, `"0"` = contradictory.

---

## 1. Label-preserving paraphrase

### System
You are a careful news-style rewriter. You will be given a news article, a single actor mentioned in it, and a human value with a direction. Your job is to rewrite the article so the actor and the same value/direction relationship remain clearly expressed, but the surface wording, sentence order, and incidental details change. Do NOT change the actor identity. Do NOT change the value or direction. Do NOT introduce a new value relationship.

### User
```
Original title: {title}
Original article: {content}
Actor of interest: {actor_name} (ID: {actor_id})
L1 value to preserve: {l1_value_id} ({l1_value_name})
Direction to preserve: {direction_name}  ({direction})
Evidence sentence from the original: {explanation}

Rewrite the article (≤ 1500 chars) while preserving the actor and the value/direction relationship. Output JSON only.
```

### Expected JSON
```json
{
  "title":          "...",
  "content":        "...",
  "actor_name":     "...",
  "evidence_sentence": "...",
  "explanation":    "<one sentence why the new content expresses the same value+direction>"
}
```

### Rejection rules (verifier)
- actor_name missing from new content
- evidence_sentence absent from content
- value clearly drifted to a different L1
- direction inverted
- length < 50 chars or > 8000 chars

### Quality checklist
1. The actor's behaviour is the *subject* of the evidence sentence.
2. The new content avoids verbatim copying of the original (no >50 % token overlap).
3. The new content is plausibly news-like (not first-person narrative).

---

## 2. Rare-positive generation

### System
You are a synthetic news writer for a research benchmark. Given an L1 human value, a direction, and an actor archetype, write a short, news-style article in which the named actor's behaviour clearly expresses (or contradicts, depending on direction) the value. Keep the article ≤ 1500 chars. Use a concrete factual style; avoid first-person narration; avoid editorial commentary.

### User
```
L1 value: {l1_value_id} ({l1_value_name})
L2 category: {l2_value_id} ({l2_value_name})
Direction: {direction_name} ({direction})
Actor archetype: {actor_archetype}   (e.g. "city council member", "humanitarian NGO", "tech CEO")
Suggested actor name: {suggested_actor_name}
Definition / what this value means: {value_definition}
Optional related training seed (for style only, do not copy): {optional_seed_excerpt}
Generate a short news-style article. Output JSON only.
```

### Expected JSON
```json
{
  "title":          "...",
  "content":        "...",
  "actor_name":     "...",
  "evidence_sentence": "<verbatim sentence from content that demonstrates the value>",
  "explanation":    "..."
}
```

### Rejection rules (verifier)
- actor_name not in content
- value not actually expressed
- direction inverted
- content references real, identifiable individuals or organisations in defamatory contexts
- content too short or too long

### Quality checklist
1. The article reports an *action* by the actor, not just an opinion.
2. The direction is unambiguous (no reader would flip it).
3. The value is the *primary* one expressed by the action.

---

## 3. Hard-negative generation

### System
You are creating a near-miss training example. The actor's behaviour will be related to the target topic but should NOT be labelled with the target L1 value. A different, related value is the real label.

### User
```
Target L1 value (do NOT predict for this actor): {target_l1_id} ({target_l1_name})
Actually-correct L1 value (this IS expressed): {alternative_l1_id} ({alternative_l1_name})
Direction (for the alternative value): {direction_name} ({direction})
Suggested actor name: {suggested_actor_name}
Suggested topic: {topic_hint}
Write a short news-style article where the actor expresses the alternative value, but a careless reader might assume the target value applies. Output JSON only.
```

### Expected JSON
```json
{
  "title":          "...",
  "content":        "...",
  "actor_name":     "...",
  "evidence_sentence": "<sentence supporting the alternative L1 value>",
  "explanation":    "<why the target L1 value does NOT apply here>"
}
```

### Rejection rules (verifier)
- Article actually expresses the target value too (would be a positive)
- Article expresses neither the target nor the alternative value
- Direction inverted

### Quality checklist
1. The "near miss" is plausible — a naive model would over-predict the target.
2. The alternative value's evidence is concrete.
3. The article does NOT contain any statement that clearly expresses the target value.

---

## 4. Direction-contrastive pair

### System
You will write a PAIR of short news-style articles for the same L1 human value. The two articles must share topic and rough length, but one must clearly express the value in the **aligned** direction and the other in the **contradictory** direction. Use different actors for the two articles so the direction is the discriminating signal, not the actor name.

### User
```
L1 value: {l1_value_id} ({l1_value_name})
Topic hint: {topic_hint}   (e.g. "court ruling on freedom of assembly")
Actor A name: {actor_a_name}     (aligned)
Actor B name: {actor_b_name}     (contradictory)
Output a JSON object with two fields: "aligned" and "contradictory", each containing {title, content, actor_name, evidence_sentence, explanation}.
```

### Expected JSON
```json
{
  "aligned":       { "title":"...", "content":"...", "actor_name":"...", "evidence_sentence":"...", "explanation":"..." },
  "contradictory": { "title":"...", "content":"...", "actor_name":"...", "evidence_sentence":"...", "explanation":"..." }
}
```

### Rejection rules (verifier)
- Pair differs only in surface direction words (e.g. swapping "supports" ↔ "violates")
- Actor names identical
- Topics differ entirely (defeats the contrastive design)

### Quality checklist
1. The aligned article shows the actor *acting in support* of the value.
2. The contradictory article shows the actor *acting against* the value.
3. Both articles are plausible news; neither is a thought-experiment.

---

## 5. Teacher verification prompt

### System
You are an expert annotator for the FEHU benchmark. Decide whether the given synthetic sample is well-formed enough to enter the training pool. Be strict.

### User
```
Sample (JSON):
{sample}

Target label: {l1_value_id} ({l1_value_name}), direction = {direction_name}
Augmentation type: {augmentation_type}

Reject if:
- The actor named in sample.actor_name does not appear in sample.content.
- The evidence_sentence does not support the labelled L1 value with the labelled direction.
- The direction is ambiguous (could be flipped without changing the text much).
- The content also expresses a different value for the same actor with equal weight.
- The content contains real-world defamation, slurs, or PII.

Return JSON:
{
  "verdict": "accept" | "reject" | "needs_human_review",
  "reason":  "<one-sentence justification>"
}
```

### Quality checklist
1. Reject if the actor is unnamed or generic ("a man", "officials").
2. Reject if the article reads like an opinion piece rather than news.
3. Accept only when the value-direction relationship is unambiguous.
"""

# ============================================================
# FIGURES
# ============================================================

def make_figures(scored_rows: List[Dict], plan_rows: List[Dict], fig_dir: Path) -> None:
    if not HAS_MPL:
        return
    fig_dir.mkdir(parents=True, exist_ok=True)

    # Figure: priority score per selected label (top 30)
    top = scored_rows[:30]
    fig, ax = plt.subplots(figsize=(11, 6))
    names = [r["l1_value_name"] for r in top]
    vals = [r["priority_score"] for r in top]
    y = list(range(len(top)))
    ax.barh(y, vals, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Priority score")
    ax.set_title("Augmentation Priority Score by L1 Label (top 30)")
    plt.tight_layout(); plt.savefig(fig_dir / "priority_score_by_label.png", dpi=150); plt.close()

    # Figure: budget allocation by type
    by_type = {
        "rare_positive":  sum(r["n_rare_positive"] for r in plan_rows),
        "paraphrase":     sum(r["n_paraphrase"] for r in plan_rows),
        "hard_negative":  sum(r["n_hard_negative"] for r in plan_rows),
        "dir_contrast":   sum(r["n_direction_contrastive_pairs"] for r in plan_rows) * 2,
    }
    fig, ax = plt.subplots(figsize=(7, 5))
    keys = list(by_type.keys())
    vals = [by_type[k] for k in keys]
    bars = ax.bar(range(len(keys)), vals, alpha=0.85)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.5, str(v),
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(keys, rotation=15, ha="right")
    ax.set_ylabel("Planned augmented sample count")
    ax.set_title("Augmentation Budget Allocation (pilot)")
    plt.tight_layout(); plt.savefig(fig_dir / "budget_allocation.png", dpi=150); plt.close()

    # Figure: train count vs priority score scatter
    fig, ax = plt.subplots(figsize=(8, 6))
    xs = [r["train_gold_count_l1"] for r in scored_rows]
    ys = [r["priority_score"] for r in scored_rows]
    ax.scatter(xs, ys, alpha=0.75)
    for r in scored_rows[:8]:
        ax.annotate(r["l1_value_name"],
                    (r["train_gold_count_l1"], r["priority_score"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=7)
    ax.set_xscale("symlog")
    ax.set_xlabel("Train count (log)")
    ax.set_ylabel("Priority score")
    ax.set_title("Train Frequency vs Augmentation Priority")
    plt.tight_layout(); plt.savefig(fig_dir / "train_count_vs_priority.png", dpi=150); plt.close()


# ============================================================
# REPORT
# ============================================================

def write_report(scored_rows: List[Dict], plan_rows: List[Dict], summary_rows: List[Dict],
                 seed_status: Dict[str, str], n_seeds: int,
                 args, ts: str, out_dir: Path, diag_dir: Path) -> None:
    by_type_total = {r["category"]: r["n_samples"] for r in summary_rows}

    lines = [
        "# FEHU Augmentation Plan Report (Pilot)",
        "",
        f"**Generated:** {ts}  ",
        f"**Source diagnosis:** `{diag_dir}`  ",
        f"**Budget profile:** `{args.budget_profile}`  ",
        f"**Max labels:** {args.max_labels}",
        "",
        "> No augmented data has been generated. This is a planning artifact.",
        "",
        "## Method weights",
        "",
        f"- rare_score: {PRIORITY_WEIGHTS['rare_score']}",
        f"- low_recall_score: {PRIORITY_WEIGHTS['low_recall_score']}",
        f"- direction_error_score: {PRIORITY_WEIGHTS['direction_error_score']}",
        f"- false_positive_score: {PRIORITY_WEIGHTS['false_positive_score']}",
        "",
        "## Selected labels (top by priority)",
        "",
        "| Rank | L1 ID | Label | Train | Group | Types | Priority |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(scored_rows[:args.max_labels], 1):
        lines.append(
            f"| {i} | {r['l1_value_id']} | {r['l1_value_name']} | "
            f"{r['train_gold_count_l1']} | {r['threshold_group']} | "
            f"{r['augmentation_types']} | {r['priority_score']:.4f} |"
        )

    no_seed = [l1 for l1, s in seed_status.items() if s == "no_article_seed"]
    has_seed = [l1 for l1, s in seed_status.items() if s == "has_seeds"]

    lines += [
        "",
        "## Seed pool",
        "",
        f"- Selected labels: {len(seed_status)}",
        f"- With TRAIN article seeds: {len(has_seed)}",
        f"- Without article seeds: {len(no_seed)}",
        f"- Total seed instances written: {n_seeds}",
        "",
        "## Budget (pilot)",
        "",
        "| Category | Samples |",
        "|---|---|",
        f"| rare_positive | {by_type_total.get('rare_positive', 0)} |",
        f"| paraphrase | {by_type_total.get('paraphrase', 0)} |",
        f"| hard_negative | {by_type_total.get('hard_negative', 0)} |",
        f"| direction_contrastive (samples) | {by_type_total.get('direction_contrastive', 0)} |",
        f"| **TOTAL** | **{by_type_total.get('TOTAL', 0)}** |",
        "",
        "## Outputs",
        "",
        f"All artifacts written to `{out_dir}`:",
        "",
        "- `augmentation_target_labels.csv` — scored labels (full table)",
        "- `augmentation_plan_by_label.csv` — per-label budget allocation",
        "- `augmentation_budget_summary.csv` — totals by type",
        "- `selected_seed_instances.jsonl` — TRAIN seeds (one per line)",
        "- `target_label_definitions.json` — definitions + rationale per selected label",
        "- `augmentation_prompt_blueprints.md` — templates (NOT executed)",
        "- `augmentation_plan_config.json` — run config",
        "- `figures/` — three diagnostic PNGs",
        "",
        "## What this plan does NOT do",
        "",
        "- No LLM was called.",
        "- No augmented samples were written.",
        "- No training was started.",
        "- No existing files were modified.",
        "",
        "The next step (not authorised in this session) would be `run_generation.py` —",
        "consuming `selected_seed_instances.jsonl` + the prompt blueprints to produce",
        "actual augmented data, then validating it via `validate_augmented_data.py`",
        "against `augmentation_schema.json`.",
    ]
    (out_dir / "augmentation_plan_report.md").write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# MAIN
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser(description="Build a diagnosis-driven FEHU augmentation plan (no API).")
    ap.add_argument("--diagnosis_dir", type=str, required=True,
                    help="Path to an existing output/research_label_diagnosis/YYYYMMDD_HHMMSS/ folder.")
    ap.add_argument("--max_labels", type=int, default=20,
                    help="Maximum number of labels to include in the plan.")
    ap.add_argument("--budget_profile", choices=list(BUDGET_PROFILES.keys()), default="pilot")
    ap.add_argument("--max_seeds_per_label", type=int, default=10,
                    help="Max train-gold seed instances extracted per label.")
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for seed sampling.")
    return ap.parse_args()


def main():
    args = parse_args()

    diag_dir = Path(args.diagnosis_dir)
    if not diag_dir.is_absolute():
        diag_dir = PROJECT_ROOT / diag_dir
    if not diag_dir.exists():
        print(f"ERROR: diagnosis_dir does not exist: {diag_dir}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "output" / "research_augmentation_plan" / ts
    fig_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FEHU Augmentation Planner (NO GENERATION)")
    print("=" * 60)
    print(f"diagnosis_dir : {diag_dir}")
    print(f"out_dir       : {out_dir}")
    print(f"max_labels    : {args.max_labels}")
    print(f"budget_profile: {args.budget_profile}")
    print()

    # ── Taxonomy ─────────────────────────────────────────────────────────────
    l1_id_to_name, l2_id_to_name, l1_id_to_l2_id, dir_map = load_taxonomy()

    # ── Ingest diagnosis ─────────────────────────────────────────────────────
    label_meta = ingest_diagnosis(diag_dir)
    print(f"Ingested {len(label_meta)} L1 labels from label_frequency_l1.csv")

    # ── Score + select ───────────────────────────────────────────────────────
    scored = compute_priority_scores(label_meta)
    print(f"Flagged labels: {len(scored)}")
    selected = scored[:args.max_labels]
    selected_ids = [r["l1_value_id"] for r in selected]
    print(f"Selected top {len(selected)} for the plan")

    # ── Seeds ────────────────────────────────────────────────────────────────
    seed_records, seed_status = extract_seeds(
        selected_ids, l1_id_to_name, l2_id_to_name, l1_id_to_l2_id,
        max_seeds_per_label=args.max_seeds_per_label, seed=args.seed,
    )
    print(f"Extracted {len(seed_records)} seed instances "
          f"({sum(1 for s in seed_status.values() if s == 'has_seeds')} labels with seeds, "
          f"{sum(1 for s in seed_status.values() if s == 'no_article_seed')} without)")

    # ── Budget plan ──────────────────────────────────────────────────────────
    budget = BUDGET_PROFILES[args.budget_profile]
    plan_rows = build_label_plan(selected, seed_status, budget)
    summary_rows = budget_summary(plan_rows, args.budget_profile)
    print(f"Planned total samples: {sum(r['n_samples'] for r in summary_rows if r['category'] != 'TOTAL')}")

    # ── Write outputs ────────────────────────────────────────────────────────
    write_csv(scored, out_dir / "augmentation_target_labels.csv")
    write_csv(plan_rows, out_dir / "augmentation_plan_by_label.csv")
    write_csv(summary_rows, out_dir / "augmentation_budget_summary.csv")
    write_jsonl(seed_records, out_dir / "selected_seed_instances.jsonl")

    defs = build_definitions(selected, label_meta, l1_id_to_name, l2_id_to_name, l1_id_to_l2_id)
    (out_dir / "target_label_definitions.json").write_text(
        json.dumps(defs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (out_dir / "augmentation_prompt_blueprints.md").write_text(PROMPT_BLUEPRINTS_MD, encoding="utf-8")

    config = {
        "timestamp":     ts,
        "diagnosis_dir": str(diag_dir),
        "max_labels":    args.max_labels,
        "budget_profile": args.budget_profile,
        "budget":        budget,
        "priority_weights": PRIORITY_WEIGHTS,
        "max_seeds_per_label": args.max_seeds_per_label,
        "random_seed":   args.seed,
        "n_selected_labels": len(selected),
        "n_seed_records": len(seed_records),
        "no_seed_labels": [l1 for l1, s in seed_status.items() if s == "no_article_seed"],
        "notes":         "Planning stage only. No augmented data generated.",
    }
    (out_dir / "augmentation_plan_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    make_figures(scored, plan_rows, fig_dir)
    write_report(scored, plan_rows, summary_rows, seed_status,
                 len(seed_records), args, ts, out_dir, diag_dir)

    print()
    print("=" * 60)
    print("PLAN SUMMARY")
    print("=" * 60)
    print(f"{'Rank':<5} {'L1':<4} {'Label':<35} {'Train':>6} {'Group':<10} {'Pri':>6} {'Types':<40}")
    print("-" * 120)
    for i, r in enumerate(selected, 1):
        print(f"{i:<5} {r['l1_value_id']:<4} {r['l1_value_name']:<35} "
              f"{r['train_gold_count_l1']:>6} {r['threshold_group']:<10} "
              f"{r['priority_score']:>6.4f} {r['augmentation_types']:<40}")

    print()
    print("Budget allocation:")
    for r in summary_rows:
        print(f"  {r['category']:<25} {r['n_samples']:>6}")
    print()
    print(f"All artifacts written to {out_dir}")


if __name__ == "__main__":
    main()
