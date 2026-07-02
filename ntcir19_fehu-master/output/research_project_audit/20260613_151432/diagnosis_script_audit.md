# Diagnosis Script Audit

Target: `research/fehu_label_diagnosis/label_diagnosis.py`

## 1. Static review against requirements

| Requirement | Status | Evidence |
|---|---|---|
| Loads train + dev gold from official paths | ✓ | Lines 50-52 (GOLD_TRAIN, GOLD_DEV) |
| Computes label frequency from train gold | ✓ | `compute_label_frequency()` lines 261-330 |
| Distinguishes value-level from direction-aware metrics | ✓ | `compute_per_label_metrics()` builds `gold_val` and `gold_dir` separately |
| Computes 108-class (l1 × direction) metrics | ✓ | `compute_108_class_metrics()` lines 410-475 |
| Groups frequent/medium/rare by tertile AND threshold | ✓ | Tertile (top-18/mid-18/bot-18); threshold (0 / 1-5 / 6-15 / 16-40 / >40) |
| Skips limit/debug results | ✓ | `build_method_inventory` checks `limit != null` and `< 177`; records in inventory CSV |
| Does NOT overwrite older diagnosis outputs | ✓ | Output path is `output/research_label_diagnosis/{YYYYMMDD_HHMMSS}/` |
| Does NOT modify existing files | ✓ | No writes outside its timestamped folder |
| Does NOT call APIs | ✓ | No HTTP libraries imported; pure local IO + numpy-free math |
| Does NOT train models | ✓ | No torch / training code |
| Uses UTF-8 throughout | ✓ | All `open(...)` and `Path.write_text` pass `encoding="utf-8"` |
| Runnable from project root | ✓ | `sys.path.insert(0, PROJECT_ROOT)` before `from evaluation import ...` |

## 2. Mathematical correctness — verified

### Sanity check A — micro aggregation matches official scorer

Independent recomputation for `Prompt_DS_Flash`:

| Metric | Diagnosis output | Official `evaluation.evaluate()` | Match |
|---|---|---|---|
| Task-1b micro-F1 | 0.4964 | 0.4964 | ✓ |
| Task-1b micro-precision | 0.5899 | 0.5899 | ✓ |
| Task-1b micro-recall | 0.4285 | 0.4285 | ✓ |
| DRR | 0.0279 | 0.0279 | ✓ |

### Sanity check B — per-L1 sum-aggregation reproduces official µF1

```python
# In the audit: sum TP_dir, FP_dir, FN_dir over all 54 L1 labels
# then compute micro-P / micro-R / micro-F1
# Result: µF1 = 0.4964, P = 0.5899, R = 0.4285
# Same as official Task-1b — confirms the per-label decomposition is exact.
```

This is a meaningful internal-consistency check, because it confirms:
1. The L1 splits are mutually exclusive and exhaustive (no double-count, no missed labels).
2. Direction-aware TP/FP/FN per label sum to the official Task-1b counts.

### Sanity check C — spot-check on label "Be responsible" (L1=42)

| | Diagnosis CSV | Independent recompute |
|---|---|---|
| TP_dir | 217 | 217 |
| FP_dir | 85 | 85 |
| FN_dir | 65 | 65 |
| recall_dir | 0.7695 | 0.7695 |

Exact match.

## 3. Direction semantics

The script uses `DIR_NAME = {"1": "aligned", "0": "contradictory"}` (line 60) — matches `dataset/hv_categories/direction_mapping.json` authoritatively, and is robust to evaluation.py's misleading variable names.

## 4. Direction-reversal computation

The per-label direction reversal count uses the **unambiguous-gold rule** (correct):

```python
# label_diagnosis.py: compute_per_label_metrics
for ga_key, g_dirs in gold_ga_dirs.get(l1_id, {}).items():
    if len(g_dirs) == 1:           # skip ambiguous (both directions in gold)
        g_d = next(iter(g_dirs))
        opp = "0" if g_d == "1" else "1"
        if opp in pred_ga_dirs.get(l1_id, {}).get(ga_key, set()):
            rev_count += 1
```

This matches the official `direction_reverse_rate_gold_excl` philosophy of excluding ambiguous (both-direction) gold instances. The numerator only counts reversals on direction-unique gold; the denominator (`max(dev_gold_count_l1, 1)`) uses **all** dev gold for that L1, which is an intentional approximation — slightly different from the official global denominator. **Not a bug**, but worth recording: this means `direction_reverse_rate_label` is a *per-label* indicator, not directly comparable to the global DRR.

## 5. Report conclusions vs. computed data

Inspected: `output/research_label_diagnosis/20260613_145847/diagnosis_report.md`

| Conclusion in report | Verified by computed data? |
|---|---|
| "Best Task-1b Micro-F1: Prompt_DS_Flash = 0.4964" | ✓ matches `overall_metrics.csv` and re-verified |
| "Best rare-label avg direction-recall: Prompt_DS_Flash" | ✓ `frequency_group_summary.csv` confirms |
| "DeBERTa_only is recall-focused with DRR=0.2376" | ✓ matches `overall_metrics.csv` |
| "Rare labels mostly have recall_dir=0" | ✓ `rare_low_recall_labels.csv` lists 101 rows |
| Constraint "No augmentation performed yet" | ✓ no augmentation artifacts in output |

All claims in the report are backed by the underlying CSVs.

## 6. Issues found

| Severity | Issue |
|---|---|
| LOW | `direction_reverse_rate_label` uses a *per-label* denominator approximation — clearly documented in the CSV header and report, but readers should not confuse it with the global DRR in `overall_metrics`. |
| LOW | When matplotlib is unavailable, the script silently degrades to skipping figures. This was reported via a `UserWarning` and is recoverable by `pip install matplotlib`. Acceptable. |

No HIGH or CRITICAL issues. The diagnosis script is correct, safe, and reproducible.
