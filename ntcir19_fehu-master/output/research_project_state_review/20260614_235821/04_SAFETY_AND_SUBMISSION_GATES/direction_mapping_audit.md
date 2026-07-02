# Direction-Mapping Audit

**Authoritative source:** `dataset/hv_categories/direction_mapping.json`

```json
{"aligned": "1", "contradictory": "0"}
```

So: **`"1"` = aligned**, **`"0"` = contradictory**. Every consumer must obey this.

## Cross-project check (re-verified this session)

| Location | What it says | Consistent? |
|---|---|---|
| `dataset/hv_categories/direction_mapping.json` | aligned=1, contradictory=0 | ✅ (authoritative) |
| `CLAUDE.md` | `"1"` = aligned, `"0"` = contradictory | ✅ |
| `research/fehu_augmentation_generation_preview_v1/run_generation_preview.py:59` | `DIRECTION_NAME = {"1": "aligned", "0": "contradictory"}` | ✅ |
| `research/fehu_augmentation_v1/augmentation_schema.json:60` | `"description": "Per direction_mapping.json: '1' = aligned, '0' = contradictory."` | ✅ |
| `research/fehu_submission_safety/fehu_prediction_format_guard.py:39` | `DIR_VALID = {"0", "1"}  # contradictory / aligned` | ✅ |
| `research/fehu_submission_safety/augmented_training_data_guard.py:212-215` | `"1"` ⇒ expects `"aligned"`; `"0"` ⇒ expects `"contradictory"` | ✅ |
| `src/run_pipeline.py:329` (post-repair) | `direction = "0" if direction_str == "contradictory" else "1"` | ✅ |
| `src/run_pipeline_deepseek_flash.py:303` | same | ✅ |
| `src/train_deberta.py` | label-index comment "0=contradictory, 1=aligned" | ✅ |
| `src/hybrid_v2.py:488` | `"1" if dir_word == "aligned" else "0"` | ✅ |
| `research/fehu_label_diagnosis/label_diagnosis.py:60` | `DIR_NAME = {"1": "aligned", "0": "contradictory"}` | ✅ |
| **`evaluation.py:36` docstring** | "direction: `"0"` (aligned) or `"1"` (contradictory)" — **INVERTED** | ❌ documented hazard |
| **`evaluation.py:65-72` variable names** | `G_aligned` for `d=="0"`, `G_contra` for `d=="1"` — **INVERTED** | ❌ documented hazard |

## Effect of the `evaluation.py` inversion

The variable names mislead the reader, but the DRR computation is symmetric:

```python
flips = (P_aligned & G_only_contra) | (P_contra & G_only_aligned)
```

The metric counts any direction *flip*, regardless of which direction is which. So:

- **Numerical scores are correct** (DRR, micro/macro F1, precision/recall).
- **Reader semantics are wrong**: someone reading `evaluation.py:65-72` will believe `d=="0"` means aligned.

User has instructed: **do not modify `evaluation.py`.** This audit honours that constraint. The inversion is therefore recorded as a *documented hazard*, not a fix-this-now item. Every downstream consumer in the project follows the authoritative mapping directly (verified above).

## v2 preview cross-check (matrix re-run this session)

Every one of the 18 v2 preview requests was checked: `target_direction_name` always matches `DIRECTION_NAME[target_direction]`. `is_positive_expected` per type:

| Type | Expected `is_positive` | Expected `direction` |
|---|---|---|
| paraphrase | True | inherits seed direction, ∈ {"0","1"} |
| rare_positive | True | "1" (aligned) |
| hard_negative | False | null |
| direction_contrastive | True | THIS member's direction, ∈ {"0","1"} |

Matrix CSV (`preview_v2_request_matrix.csv`) confirms all 18 requests comply with these per-type expectations.

## Verdict

✅ **PASS** — every downstream consumer follows the authoritative mapping. The `evaluation.py` inversion is the only known deviation; (a) the file is forbidden to modify, (b) the metric value is mathematically unaffected.
