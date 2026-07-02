#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_experiment_management/experiment_registry.py

Local-only safe scanner over `output/` that produces a single registry of
every method folder, its provenance, and a trustworthiness label.

Run from project root:
    python research/fehu_experiment_management/experiment_registry.py

Output: output/research_experiment_registry/YYYYMMDD_HHMMSS/
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEV_EVENT_BASE = PROJECT_ROOT / "dataset/dev/dev_event_base.json"

# Canonical-vs-legacy decisions are encoded here. Keys are paths relative to
# PROJECT_ROOT. Tags are stable identifiers consumed by downstream tools.
KNOWN_FOLDERS = [
    ("output/task1",
        "legacy_duplicate_ambiguous",
        "Legacy ambiguous: was written by both run_pipeline.py and train_deberta.py. "
        "Current bytes match output/task1_prompt/. Do not use as a method source."),
    ("output/task1_prompt",
        "canonical_prompt_oai",
        "Prompt-only OpenAI (legacy; no run_config). Likely gpt-4o-mini."),
    ("output/task1_prompt_deepseek_v4_flash",
        "canonical_prompt_ds_flash",
        "Prompt-only DeepSeek V4 Flash. Full run_config + metrics."),
    ("output/task1_prompt_deepseek_v4_flash_limit5",
        "limit_debug_run",
        "Limit (debug) run of Prompt DS Flash with N=5. Exclude from full-dev comparisons."),
    ("output/task1_deberta",
        "canonical_deberta",
        "DeBERTa-only predictions. Regenerated from checkpoint."),
    ("output/task1_hybrid",
        "canonical_hybrid_v1",
        "Hybrid v1 (DeBERTa cand + LLM keep/remove)."),
    ("output/task1_hybrid_v2",
        "orphan_legacy_hybrid_v2",
        "Orphan: predates provider-aware naming in hybrid_v2.py. "
        "Canonical OAI v2 path output/task1_hybrid_v2_openai_gpt_4o_mini/ does not exist."),
    ("output/task1_hybrid_v2_limit20",
        "limit_debug_run",
        "Limit (debug) run of Hybrid v2 with N=20."),
    ("output/task1_hybrid_v2_deepseek_deepseek_v4_pro",
        "canonical_hybrid_v2_ds_pro",
        "Hybrid v2 DeepSeek V4 Pro. Full provenance."),
    ("output/task1_hybrid_v2_deepseek_deepseek_v4_flash",
        "canonical_hybrid_v2_ds_flash",
        "Hybrid v2 DeepSeek V4 Flash. Full provenance."),
    ("output/task1_hybrid_v2_openai_gpt_4o_mini",
        "canonical_hybrid_v2_oai_mini",
        "Expected canonical Hybrid v2 OAI folder. Currently missing."),
]


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def safe_load_run_config(d: Path) -> Dict:
    rc = d / "run_config.json"
    if not rc.exists():
        return {}
    try:
        return load_json(rc)
    except Exception:
        return {}


def collect_dev_universe() -> tuple[set, set]:
    """Return (dev_guids, dev_actor_ids) for sanity-checking predictions."""
    if not DEV_EVENT_BASE.exists():
        return set(), set()
    arts = load_json(DEV_EVENT_BASE)
    guids = {str(a["guid"]) for a in arts}
    actors = set()
    for a in arts:
        for d in a.get("actors", []):
            for _, aid in d.items():
                actors.add(str(aid))
    return guids, actors


def inspect_folder(folder_rel: str, tag: str, note: str, dev_guids: set) -> Dict:
    d = PROJECT_ROOT / folder_rel
    row: Dict[str, Any] = {
        "output_dir":             folder_rel,
        "tag":                    tag,
        "exists":                 d.exists(),
        "pred_task1a_exists":     False,
        "pred_task1b_exists":     False,
        "metrics_exists":         False,
        "run_config_exists":      False,
        "comparison_table_exists": False,
        "detected_method":        "unknown",
        "detected_provider":      "unknown",
        "detected_model":         "unknown",
        "detected_version":       "unknown",
        "detected_limit":         "unknown",
        "likely_full_dev":        False,
        "total_task1a_predictions": None,
        "total_task1b_predictions": None,
        "guid_count_task1a":      None,
        "guid_count_task1b":      None,
        "risk_notes":             note,
    }
    if not d.exists():
        row["risk_notes"] = "Directory does not exist. " + note
        return row

    p1a = d / "pred_task1a.json"
    p1b = d / "pred_task1b.json"
    row["pred_task1a_exists"]     = p1a.exists()
    row["pred_task1b_exists"]     = p1b.exists()
    row["metrics_exists"]         = (d / "metrics.json").exists()
    row["run_config_exists"]      = (d / "run_config.json").exists()
    row["comparison_table_exists"] = (d / "comparison_table.txt").exists()

    rc = safe_load_run_config(d)
    if rc:
        row["detected_method"]   = str(rc.get("method", "unknown"))
        row["detected_provider"] = str(rc.get("provider", rc.get("llm_provider", "unknown")))
        row["detected_model"]    = str(rc.get("model", rc.get("llm_model", "unknown")))
        row["detected_version"]  = str(rc.get("version", "unknown"))
        row["detected_limit"]    = str(rc.get("limit", "null"))

    n1a = n1b = 0
    g1a: set = set()
    g1b: set = set()
    if p1a.exists():
        try:
            d1a = load_json(p1a)
            for art in d1a:
                g1a.add(str(art["guid"]))
                n1a += len(art.get("article_human_values", []))
        except Exception:
            pass
    if p1b.exists():
        try:
            d1b = load_json(p1b)
            for art in d1b:
                g1b.add(str(art["guid"]))
                n1b += len(art.get("article_human_values", []))
        except Exception:
            pass
    row["total_task1a_predictions"] = n1a
    row["total_task1b_predictions"] = n1b
    row["guid_count_task1a"]        = len(g1a)
    row["guid_count_task1b"]        = len(g1b)

    # Determine full-dev: covers the full dev split AND limit not set
    is_full_dev_guids = (len(g1a) == 177 and len(g1b) == 177 and g1a == dev_guids if dev_guids else False)
    limit_is_null = row["detected_limit"] in ("null", "None", "unknown")
    row["likely_full_dev"] = bool(is_full_dev_guids and limit_is_null)

    return row


def write_csv(rows: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_trustworthiness_notes(rows: List[Dict], path: Path) -> None:
    lines = ["# Result Trustworthiness Notes", "",
             "Each method folder is categorised into one of the canonical tags.", ""]
    by_tag: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        by_tag[r["tag"]].append(r)

    for tag in [
        "canonical_prompt_oai", "canonical_prompt_ds_flash",
        "canonical_deberta", "canonical_hybrid_v1",
        "canonical_hybrid_v2_ds_pro", "canonical_hybrid_v2_ds_flash",
        "canonical_hybrid_v2_oai_mini",
        "legacy_duplicate_ambiguous", "orphan_legacy_hybrid_v2",
        "limit_debug_run", "unknown",
    ]:
        if tag not in by_tag:
            continue
        lines.append(f"## `{tag}`")
        lines.append("")
        for r in by_tag[tag]:
            arts = r.get("guid_count_task1a") or 0
            lines.append(
                f"- **`{r['output_dir']}`**"
                f"  arts={arts}  pred_1a={r['total_task1a_predictions']}"
                f"  pred_1b={r['total_task1b_predictions']}"
                f"  full_dev={r['likely_full_dev']}"
            )
            lines.append(f"    - run_config: {'yes' if r['run_config_exists'] else 'no'}"
                         f"   metrics: {'yes' if r['metrics_exists'] else 'no'}")
            lines.append(f"    - model: {r['detected_model']}   provider: {r['detected_provider']}"
                         f"   limit: {r['detected_limit']}")
            lines.append(f"    - notes: {r['risk_notes']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "output" / "research_experiment_registry" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Experiment Registry]")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Output dir:   {out_dir}")
    print()

    dev_guids, _ = collect_dev_universe()
    print(f"Dev split has {len(dev_guids)} guids.")
    print()

    rows: List[Dict] = []
    for folder_rel, tag, note in KNOWN_FOLDERS:
        row = inspect_folder(folder_rel, tag, note, dev_guids)
        rows.append(row)
        status = "OK" if row["exists"] else "MISSING"
        print(f"  [{tag:38}] {folder_rel:60} {status}")

    # registry CSV + JSON
    write_csv(rows, out_dir / "experiment_registry.csv")
    (out_dir / "experiment_registry.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # smaller inventory CSV with only the most-used columns
    inv_cols = [
        "output_dir", "tag", "exists",
        "pred_task1a_exists", "pred_task1b_exists",
        "run_config_exists", "metrics_exists",
        "detected_provider", "detected_model", "detected_limit",
        "likely_full_dev",
    ]
    inv_rows = [{k: r[k] for k in inv_cols} for r in rows]
    write_csv(inv_rows, out_dir / "output_folder_inventory.csv")

    write_trustworthiness_notes(rows, out_dir / "result_trustworthiness_notes.md")

    print()
    print(f"Registry written to {out_dir}")


if __name__ == "__main__":
    main()
