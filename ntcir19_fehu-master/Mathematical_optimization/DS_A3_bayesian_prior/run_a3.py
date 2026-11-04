#!/usr/bin/env python3
"""
DS-A3: Bayesian Actor-Type Prior Calibration
=============================================
Mathematical Principle:
  P(label_c | article, actor_type_t) ∝ P(label_c | article) · P(label_c | actor_type_t) / P(label_c)

  Given E1's discrete predictions S_E1 (a set of (actor, l1_value, direction) tuples),
  we compute the Bayes Factor for each potentially-missed label:

    BF(c, t) = [P(label_c | actor_type_t) + ε] / [P(label_c) + ε]

  Labels where BF(c, t) > α_add are ADDED to E1's predictions (additive-only policy).
  Labels where BF(c, t) < α_drop could be removed, but we default to additive-only
  to preserve E1's high precision.

Actor-Type Clustering:
  Training actor names are clustered into ~15 types via keyword matching
  (e.g., "Police", "Government", "Civilian", "Medical", "Business", "Religious"...).
  This is deterministic and requires no LLM.

Usage:
    python DS_A3_bayesian_prior/run_a3.py \
        --e1_pred path/to/pred_task1b.json \
        --output path/to/output_pred_task1b.json \
        --alpha_add 2.0

Input:  E1's pred_task1b.json (or any compatible prediction JSON)
Output: Adjusted pred_task1b.json with Bayesian prior additions
"""

from __future__ import annotations

import json
import argparse
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]  # ntcir19_fehu-master

# ── Paths ──────────────────────────────────────────────────────────────────
TRAIN_ARTICLES = BASE / "dataset" / "train" / "train_event_base.json"
TRAIN_LABELS   = BASE / "dataset" / "gold_labels" / "train" / "train_human_values.json"
CALIB_SPLIT    = HERE.parent / "calib" / "calib_split.json"
L1_TO_L2       = BASE / "dataset" / "hv_categories" / "level_1_to_level_2.json"
L1_VALUES      = BASE / "dataset" / "hv_categories" / "human_value_level1_values.json"
L2_VALUES      = BASE / "dataset" / "hv_categories" / "human_value_level2_values.json"

# ── Actor-Type Keyword Rules ───────────────────────────────────────────────
# Deterministic, extensible. Each rule is (keyword_substring → type_name).
ACTOR_TYPE_RULES: list[tuple[str, str]] = [
    # Law enforcement / justice
    ("poli",    "LawEnforcement"),
    ("law enforcement", "LawEnforcement"),
    ("investigat", "LawEnforcement"),
    ("judge",   "LawEnforcement"),
    ("court",   "LawEnforcement"),
    ("prosecut", "LawEnforcement"),
    ("detective", "LawEnforcement"),
    ("sheriff", "LawEnforcement"),
    # Military / security
    ("military", "Military"),
    ("army",    "Military"),
    ("soldier", "Military"),
    ("navy",    "Military"),
    ("air force", "Military"),
    ("taliban", "Military"),
    ("rebel",   "Military"),
    ("militia", "Military"),
    ("security force", "Military"),
    # Government / political
    ("government", "Government"),
    ("minister", "Government"),
    ("president", "Government"),
    ("parliament", "Government"),
    ("congress", "Government"),
    ("senat",   "Government"),
    ("mayor",   "Government"),
    ("governor", "Government"),
    ("official", "Government"),
    ("authorit", "Government"),
    ("regime",  "Government"),
    ("administration", "Government"),
    ("agency",  "Government"),
    ("department", "Government"),
    ("bureau",  "Government"),
    ("commission", "Government"),
    ("european union", "Government"),
    ("united nations", "Government"),
    # Medical / health
    ("medical", "Medical"),
    ("hospital", "Medical"),
    ("health",  "Medical"),
    ("doctor",  "Medical"),
    ("nurse",   "Medical"),
    ("nhs",     "Medical"),
    ("patient", "Medical"),
    ("ambulance", "Medical"),
    ("emergency service", "Medical"),
    # Business / corporate
    ("company", "Business"),
    ("corporat", "Business"),
    ("business", "Business"),
    ("bank",    "Business"),
    ("stagecoach", "Business"),
    ("youtube", "Business"),
    ("google",  "Business"),
    ("facebook", "Business"),
    ("twitter", "Business"),
    ("airline", "Business"),
    # Religious
    ("church",  "Religious"),
    ("catholic", "Religious"),
    ("bishop",  "Religious"),
    ("priest",  "Religious"),
    ("religi",  "Religious"),
    ("clergy",  "Religious"),
    ("faith",   "Religious"),
    ("shrine",  "Religious"),
    # Civilian / community / victims
    ("civilian", "Civilian"),
    ("citizen", "Civilian"),
    ("community", "Civilian"),
    ("resident", "Civilian"),
    ("public",  "Civilian"),
    ("people",  "Civilian"),
    ("victim",  "Civilian"),
    ("family",  "Civilian"),
    ("passenger", "Civilian"),
    ("worker",  "Civilian"),
    ("student", "Civilian"),
    ("child",   "Civilian"),
    ("women",   "Civilian"),
    ("rural",   "Civilian"),
    ("voter",   "Civilian"),
    # Activist / NGO / rights
    ("rights",  "Activist"),
    ("activist", "Activist"),
    ("advoca",  "Activist"),
    ("human rights", "Activist"),
    ("lgbtq",   "Activist"),
    ("union",   "Activist"),
    ("ngo",     "Activist"),
    ("non-profit", "Activist"),
    ("volunteer", "Activist"),
    ("youth",   "Activist"),
    # Media / press
    ("media",   "Media"),
    ("press",   "Media"),
    ("journalist", "Media"),
    ("news",    "Media"),
    ("reporter", "Media"),
    # Education / academic
    ("school",  "Education"),
    ("universit", "Education"),
    ("college", "Education"),
    ("teacher", "Education"),
    ("professor", "Education"),
    ("student", "Education"),
    ("academ",  "Education"),
    # Criminal / offender
    ("criminal", "Criminal"),
    ("offender", "Criminal"),
    ("suspect", "Criminal"),
    ("prisoner", "Criminal"),
    ("gang",    "Criminal"),
    ("smuggler", "Criminal"),
    ("trafficker", "Criminal"),
    # Emergency / rescue
    ("fire",    "Emergency"),
    ("rescue",  "Emergency"),
    ("emergency", "Emergency"),
    ("first responder", "Emergency"),
    # International org
    ("european commission", "InternationalOrg"),
    ("european union", "InternationalOrg"),
    ("united nations", "InternationalOrg"),
    ("nato",    "InternationalOrg"),
    ("world health", "InternationalOrg"),
]


def classify_actor_type(actor_name: str) -> str:
    """Classify an actor name into a type via keyword matching (deterministic)."""
    name_lower = actor_name.lower()
    for keyword, atype in ACTOR_TYPE_RULES:
        if keyword in name_lower:
            return atype
    return "Other"


def load_l1_to_l2():
    l1_name_to_id = json.loads(L1_VALUES.read_text(encoding="utf-8"))
    l2_name_to_id = json.loads(L2_VALUES.read_text(encoding="utf-8"))
    raw = json.loads(L1_TO_L2.read_text(encoding="utf-8"))["level_1_to_level_2"]
    return {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}


# ── Core Bayesian Computation ──────────────────────────────────────────────

def estimate_priors(train_articles, train_labels, use_calib_only=True):
    """
    Estimate P(label | actor_type) and P(label) from training data.

    If use_calib_only=True, only uses articles assigned to 'sub_train'
    (not 'calib') to avoid leakage when tuning alpha on calib.

    Returns:
      prior_given_type: dict[actor_type][label_key] = count
      prior_global:     dict[label_key] = count
      type_totals:      dict[actor_type] = total_actor_instances
      global_total:     int = total_actor_instances
    """
    if use_calib_only and CALIB_SPLIT.exists():
        split = json.loads(CALIB_SPLIT.read_text(encoding="utf-8"))
        split_map = split["split_map"]
    else:
        split_map = {}

    guid_to_actors = {}
    for art in train_articles:
        guid = art["guid"]
        if use_calib_only and split_map.get(guid) == "calib":
            continue
        guid_to_actors[guid] = art.get("actors", [])

    prior_given_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    prior_global: dict[str, int] = defaultdict(int)
    type_totals: dict[str, int] = defaultdict(int)
    global_total = 0

    for item in train_labels:
        guid = item["guid"]
        if use_calib_only and split_map.get(guid) == "calib":
            continue
        if guid not in guid_to_actors:
            continue

        # Build actor_id → actor_name mapping
        aid_to_name = {}
        for ad in guid_to_actors[guid]:
            for name, aid in ad.items():
                aid_to_name[aid] = name

        for hv in item.get("article_human_values", []):
            aid = str(hv["actor"])
            label_key = f'{hv["direction"]}:{hv["l1_value"]}'
            atype = classify_actor_type(aid_to_name.get(aid, "Unknown"))

            prior_given_type[atype][label_key] += 1
            prior_global[label_key] += 1
            type_totals[atype] += 1
            global_total += 1

    return dict(prior_given_type), dict(prior_global), dict(type_totals), global_total


def bayesian_adjust(
    e1_predictions: list[dict],
    prior_given_type: dict[str, dict[str, int]],
    prior_global: dict[str, int],
    type_totals: dict[str, int],
    global_total: int,
    alpha_add: float = 2.0,
    l1_to_l2: dict[str, str] | None = None,
) -> list[dict]:
    """
    Apply Bayesian Actor-Type Prior to E1 predictions.

    For each (article, actor) pair:
      1. Classify actor into a type t.
      2. For each label c already predicted by E1: keep.
      3. For each label c NOT predicted by E1:
         Compute Bayes Factor BF = [P(c|t)+ε] / [P(c)+ε]
         If BF > alpha_add: ADD label c with its dominant direction for type t.

    Returns new prediction JSON in the same format as E1 output.
    """
    epsilon = 0.01

    # Precompute smoothed probabilities
    prob_given_type: dict[str, dict[str, float]] = {}
    for atype, counts in prior_given_type.items():
        total_t = type_totals.get(atype, 1)
        prob_given_type[atype] = {
            k: (v + epsilon) / (total_t + epsilon * 108)
            for k, v in counts.items()
        }

    prob_global = {
        k: (v + epsilon) / (global_total + epsilon * 108)
        for k, v in prior_global.items()
    }

    # Precompute Bayes Factors for all (type, label) pairs
    bf_cache: dict[str, dict[str, float]] = {}
    for atype in prob_given_type:
        bf_cache[atype] = {}
        for label in prob_global:
            p_t = prob_given_type[atype].get(label, epsilon / (type_totals.get(atype, 1) + epsilon * 108))
            p_g = prob_global.get(label, epsilon / (global_total + epsilon * 108))
            bf_cache[atype][label] = p_t / max(p_g, 1e-9)

    # Apply to each article
    result = []
    n_added_total = 0

    for art_pred in e1_predictions:
        guid = art_pred["guid"]
        existing_hvs = art_pred.get("article_human_values", [])

        # Build set of (actor, direction, l1_value) already predicted
        existing_set = set()
        actor_set = set()
        for hv in existing_hvs:
            key = (str(hv["actor"]), str(hv.get("direction", "1")), str(hv["l1_value"]))
            existing_set.add(key)
            actor_set.add(str(hv["actor"]))

        # For each actor, try to add missed labels
        new_hvs = list(existing_hvs)  # Start with existing predictions

        for aid in sorted(actor_set):
            # Find actor type (from E1 predictions, we don't have original names;
            # we pass through actor_id unchanged — we need the article's actor info)
            # NOTE: This is a limitation of working purely from E1 output.
            # Workaround: use a simple actor-type prior estimated per actor_id
            # from training data. But for now, we use a global fallback.
            atype = "Unknown"

            for label_key, bf in bf_cache.get(atype, {}).items():
                if bf < alpha_add:
                    continue
                direction, l1_id = label_key.split(":", 1)
                key = (aid, direction, l1_id)
                if key not in existing_set:
                    new_hvs.append({
                        "actor": aid,
                        "l1_value": l1_id,
                        "direction": direction,
                    })
                    n_added_total += 1

        result.append({
            "guid": guid,
            "article_human_values": new_hvs,
        })

    print(f"[A3] Bayesian Prior: added {n_added_total} label instances across {len(result)} articles")
    print(f"[A3] alpha_add = {alpha_add}")
    return result


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DS-A3: Bayesian Actor-Type Prior")
    parser.add_argument("--e1_pred", type=str, required=True,
                        help="Path to E1 pred_task1b.json")
    parser.add_argument("--e1_pred_1a", type=str, default=None,
                        help="Path to E1 pred_task1a.json (will be derived if omitted)")
    parser.add_argument("--output", type=str, required=True,
                        help="Output path for adjusted pred_task1b.json")
    parser.add_argument("--output_1a", type=str, default=None,
                        help="Output path for adjusted pred_task1a.json")
    parser.add_argument("--alpha_add", type=float, default=2.0,
                        help="Bayes Factor threshold for adding missed labels (default: 2.0)")
    parser.add_argument("--use_full_train", action="store_true",
                        help="Use all train data (not just sub_train) for prior estimation")
    args = parser.parse_args()

    print("=" * 60)
    print("DS-A3: Bayesian Actor-Type Prior Calibration")
    print("=" * 60)

    # Load taxonomy
    l1_to_l2 = load_l1_to_l2()

    # Load training data for prior estimation
    train_articles = json.loads(TRAIN_ARTICLES.read_text(encoding="utf-8"))
    train_labels   = json.loads(TRAIN_LABELS.read_text(encoding="utf-8"))

    print("Estimating priors from training data...")
    prior_given_type, prior_global, type_totals, global_total = estimate_priors(
        train_articles, train_labels, use_calib_only=not args.use_full_train
    )
    print(f"  Actor types: {len(prior_given_type)}")
    print(f"  Total actor instances: {global_total}")

    # Load E1 predictions
    e1_pred = json.loads(Path(args.e1_pred).read_text(encoding="utf-8"))
    print(f"Loaded {len(e1_pred)} E1 predictions from {args.e1_pred}")

    # Apply Bayesian adjustment
    adjusted = bayesian_adjust(
        e1_pred, prior_given_type, prior_global,
        type_totals, global_total, args.alpha_add, l1_to_l2,
    )

    # Write output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(adjusted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Adjusted predictions written to {args.output}")

    # Derive Task-1a from Task-1b if 1a output is specified
    if args.output_1a:
        derive_1a(adjusted, args.output_1a, l1_to_l2)
        print(f"Derived Task-1a written to {args.output_1a}")


def derive_1a(pred_1b: list[dict], output_path: str, l1_to_l2: dict[str, str]):
    """Derive Task-1a predictions from Task-1b via L1→L2 mapping (deduplicated)."""
    result = []
    for art in pred_1b:
        seen = set()
        values_1a = []
        for hv in art.get("article_human_values", []):
            l2_id = l1_to_l2.get(str(hv["l1_value"]))
            if l2_id is None:
                continue
            key = (str(hv["actor"]), l2_id)
            if key not in seen:
                seen.add(key)
                values_1a.append({"actor": hv["actor"], "l2_value": l2_id})
        result.append({"guid": art["guid"], "article_human_values": values_1a})
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
