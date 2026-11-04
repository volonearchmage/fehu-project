# E2 — Prompt Bias Control: Changes from E1

**Date:** 2026-07-22
**Status:** **prepared, not executed.** No API call, no inference, no training, no evaluation has been run. The only local execution was a `--dry_run` prompt preview (exits before any API client is created) to snapshot and verify the final prompt.
**Baseline:** the completed E1 pipeline (`RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py`, frozen; dev result 1b micro 0.5480 / macro 0.3719, run `20260722_152456`). Neither the Liu original nor any E1 file was modified.

## How E2 is built

`scripts/build_e2_pipeline.py` reads the frozen E1 pipeline and applies **5 string replacements, each asserted to match exactly once**, producing `scripts/run_pipeline_e2.py`. The complete E1→E2 diff is auditable from the build script alone. (One anchoring subtlety is documented in the script: the bare `OUTPUT FORMAT:` line occurs twice in the source — in the prompt template and as the search pattern of the DeepSeek object-format rewrite — so the insertion anchors on the B1 replacement tail, which is unique to the template.)

## What changed (prompt instructions only)

- **B1 — role-prior guideline replaced.** The inherited "Common patterns" guideline explicitly taught role-prior associations ("Law enforcement/authorities: often aligned with *Be just*(45)…"; victims, organizations, criminals likewise) — the exact bias E2 targets. It is replaced by: role, profession, institution, or group identity is **context only, never evidence**; every value must be grounded in what *this* actor concretely does, says, or causes in *this* article.
- **B2 — new `EVIDENCE AND BIAS CONTROL` block** (5 rules, inserted before OUTPUT FORMAT), covering each required behavior:
  1. *Evidence test* — output a value only if a specific action/statement/outcome of that actor supports it (unsupported labels).
  2. *Closely related values* — re-read exact names in the value list; keep only values each supported by its own evidence; named confusable pairs 26/27, 37/42, 19/20, 45/42 (adjacent-value discrimination).
  3. *No semantic expansion* — never add adjacent/broader/generic values to "round out" a profile (adjacent-value over-prediction).
  4. *Direction discipline* — aligned vs. contradictory from actual actions, statements, outcomes; never from authority/victim/sympathy status; both directions for one value only with distinct evidence each (direction reversals, role bias).
  5. *Victim rule* — suffering harm is not evidence of the victim's own values (a role-prior special case the old prompt actively encouraged).
- **B3 — bookkeeping only:** env var `E2_RUN_TS`, run-config experiment name and delta list. No behavioral change.

## What is inherited from E1 unchanged

Deterministic multi-label few-shot demos with complete gold label sets (verified byte-identical: `0-4349-1-t`, 15 labels; `0-4352-3-1`, 10 labels), full demo content, no numeric label caps, model `deepseek-v4-flash`, temperature 0.1, max_tokens 8000, JSON mode, retries, parser, dedup/format conversion, the `targeted_more_shot_balanced` variant text as modified by E1, and the official evaluation path. Outputs are isolated under `RH_test/E2_prompt_bias_control/runs/<timestamp>/`.

## Verification performed (all local, no credits)

- Build asserts passed (5/5 deltas matched exactly once); `py_compile` clean.
- Dry-run snapshot (`runs/dryrun_preview/system_prompt_snapshot.txt`): bias-control block present; "Common patterns"/role-prior list absent; DeepSeek JSON-object rewrite intact downstream of the insertion; no numeric caps; `fewshot_meta.json` identical to E1's.

## Expected effect and how E2 will be judged (when executed later)

E1 bought recall (+0.050) at precision −0.027 and DRR 0.023→0.035. E2 aims to claw back precision and reversals while keeping E1's recall: success = 1b micro-P and macro-P up vs. E1 with micro-R held within ~0.01, DRR back toward ≤0.03, and target-18 FPs (131 in E1) reduced; failure mode to watch = the evidence test suppressing tail recall (non-target-90 macro-R falling back toward Liu's 0.348).

## To execute later (not run now)

```bash
set -a && . ./.env && set +a
export E2_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E2_prompt_bias_control/scripts/run_pipeline_e2.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E2_prompt_bias_control/scripts/analyze_e2.py $E2_RUN_TS   # (to be created; E1's analyze script pattern applies)
```
