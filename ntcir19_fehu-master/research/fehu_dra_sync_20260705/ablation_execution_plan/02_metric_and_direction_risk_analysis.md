# Metric & Direction-Convention Risk Analysis — DRA-FEHU (Task-1b)

**Created at:** 2026-07-02T20:08:24
**Status:** ANALYSIS ONLY. No evaluator run here; conclusions from first-principles reading of code and data.

## Direction convention across the pipeline

| Source | Convention | Evidence |
|--------|-----------|----------|
| Official mapping file `dataset/hv_categories/direction_mapping.json` | `1`=aligned, `0`=contradictory | File content: `{"aligned":"1","contradictory":"0"}` |
| Official gold labels (train/dev) | `1`=aligned, `0`=contradictory | Observed codes `{"0","1"}`; distributions consistent with mapping file |
| Verified candidates | `1 aligned` / `0 contradictory` | `target_direction` field values |
| Derived ablation inputs | code `1`=aligned, `0`=contradictory | `direction_mapping_used = {"1 aligned":"1","0 contradictory":"0"}` in input manifest |
| `evaluation.py` DRR **internal variable naming** | `0`=aligned, `1`=contradictory (**inverted**) | Docstring line ~36 and DRR code: `if d == "0": G_aligned.add(v) else: G_contra.add(v)` |

**A direction mapping file exists** (`dataset/hv_categories/direction_mapping.json`) and it agrees with
the gold labels, the verified candidates, and the derived inputs. Only `evaluation.py`'s DRR *internal
naming* disagrees.

## evaluation.py F1 behavior
`parse_task1b` encodes each label as the exact string `"{direction}:{l1}"` (e.g. `"0:12"`). `evaluate()`
computes micro-F1 and gold-supported macro-F1 by set intersection of these strings between gold and
pred. **F1 never interprets which code means "aligned"** — it only checks string equality.

## evaluation.py DRR behavior
`direction_reverse_rate_gold_excl` buckets each gold/pred value by direction code, excludes values that
appear in *both* directions in gold (ambiguous), and counts a "reversal" when a prediction carries the
opposite direction code from a direction-unique gold value:
`flips = (P_aligned & G_only_contra) | (P_contra & G_only_aligned)`.
All reported quantities — `direction_reverse_rate`, `direction_reverse_count`,
`direction_reverse_denom_gold_excl`, `ambiguous_gold_values_filtered` — are **direction-symmetric
aggregates**.

## Is F1 affected by the convention mismatch?
**No.** Gold and predictions are produced by the same pipeline under the same convention
(`1`=aligned/`0`=contradictory), and F1 is exact-string matching. As long as gold and pred use the same
code for the same meaning (they do), micro/macro-F1 are semantically correct. The evaluator's internal
naming is irrelevant to F1.

## Is DRR affected by the convention mismatch?
**The aggregate DRR value is not affected; the directional *interpretation* is.**
- The reversal count is symmetric: it counts "pred direction code ≠ gold direction code for the same
  L1 value" and excludes values that are ambiguous in gold. Swapping the names "aligned"/"contradictory"
  does not change which (value, instance) pairs are counted, nor the ambiguous set. So the **DRR rate,
  count, denominator, and ambiguous count are numerically correct** regardless of the naming.
- What *is* mislabeled is any attempt to read a **directional decomposition** from the code's variable
  names (i.e., "how many aligned→contradictory vs contradictory→aligned flips"). `evaluation.py` does
  not emit such a decomposition, so its reported outputs remain correct — but a human narrating the
  code's `G_aligned`/`G_contra` names would invert the direction meaning relative to
  `direction_mapping.json`.

## Recommended thesis reporting language
- Report DRR as: *"the rate at which the model predicts the opposite direction of a gold-exclusive
  Level-1 value (ambiguous both-direction gold values excluded)."* This definition is convention-neutral
  and matches what the code computes.
- When mapping codes to words, cite `dataset/hv_categories/direction_mapping.json`
  (`1`=aligned, `0`=contradictory) as the authoritative source — **not** the `evaluation.py` DRR
  variable names.
- State explicitly that F1 and the aggregate DRR are unaffected by the evaluator's internal naming.

## Unresolved caveats
1. `evaluation.py` DRR internal naming contradicts `direction_mapping.json`. **Do not fix** it in this
   workflow (evaluation.py must not be modified); document and narrate around it.
2. Any *per-direction* error breakdown must be computed from raw labels using the authoritative mapping,
   not from the evaluator's internal variable names.
3. **Do not overclaim DRR improvement until real prediction errors are inspected.** With identical
   gold/pred the DRR is trivially 0; only real model predictions on dev will reveal direction behavior,
   and L1=12 contradictory dev support is only 7 instances (high variance).
