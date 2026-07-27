# E6c — deepseek-v4-pro (non-thinking) on the E6b scaffold

**Status: EXECUTED on full dev (run `20260725_002408`).** Date: 2026-07-25.

## Design

Byte-copy of the E6b pipeline (offline checks 4/4: pipeline identical modulo three declared
deltas; scaffold system prompt byte-identical to the frozen E3a snapshot). Deltas:
model `deepseek-v4-pro` with **thinking disabled** via
`extra_body={"thinking": {"type": "disabled"}}` (API probe 2026-07-24: reasoning_content None,
5 completion tokens vs 42 with thinking). Consumes **E6b's segments file** — model is the only
variable vs E6b. Clean run: 177/177, zero empty responses.

## Results (same scorer as all systems)

| metric | E6b (flash) | **E6c (pro non-thinking)** | Δ |
|---|---|---|---|
| 1a micro-F1 | 0.6621 | **0.6774** | **+0.0153** (best 1a of any system to date) |
| 1b micro-F1 | 0.5496 | 0.5343 | −0.0153 |
| 1b macro-F1 | 0.4124 | 0.3725 | −0.0399 |
| 1b micro P / R | 0.5017 / 0.6075 | 0.4748 / 0.6109 | P −0.027 |
| DRR | 0.0459 | **0.0657** | +0.0198 (worst LLM DRR) |
| target-18 micro | 0.3145 | 0.2618 | −0.0527 |

## Finding

The user-reported production observation is **reproduced under controlled conditions**: pro
(non-thinking) is decisively better at Task-1a (value identification; recall 0.7442) and
decisively worse at Task-1b (direction assignment; DRR 0.0657, precision 0.4748) than flash on
the identical prompt/segments. Consequence adopted in E7: E6c serves as a **value-evidence
juror and direction-disagreement flagger** — its exact/value votes feed the calibrated arms and
the G4 QA flag rule — and is never used as a direction source. Its 1a strength contributes to
G3/G4's 1a micro 0.6874 (best ever) via the addition arm.

## Records

`runs/20260725_002408/`: pred files, cache, run_config, system prompt snapshot, metrics.json,
per_class_metrics.csv. Scripts + offline checks under `scripts/`.
