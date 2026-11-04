# E4: Actor evidence decomposition and verification

Prompt-only Task-1 experiment built on the **frozen E1 pipeline** (imported
read-only, never modified). Goal: exceed the best reported Task-1b dev
Micro-F1 (0.5657) while staying directly runnable on the official Task-1
test input (`guid`, `title`, `content`, `actors` only — no subevents, no
Task-2 data, no fine-tuning, no dev-derived label rules).

Full design, validation results, risks, and run instructions:
**`reports/E4_IMPLEMENTATION_AND_HANDOFF_REPORT.md`**.

## Variants

| Variant | Stages | API calls/article | Output |
|---|---|---|---|
| E4a | evidence → frozen E1 + evidence units | 2 | raw E1-format items via frozen `process_results` |
| E4b | + 4 taxonomy-family scans | 6 | union of global + family candidates (fixed conflict rule) |
| E4c | + independent verifier | 7 | aggregation per `config/aggregation_rules.json` |

## Layout

```
implementation/  run_e4.py (CLI) + stage modules + freeze_check.py
prompts/         stage prompt templates (<<VAR>> placeholders)
config/          model config, taxonomy families, sibling map,
                 aggregation rules, frozen-file hash snapshot
tests/           offline unit tests (58, mocked model; no API)
runs/            per-run caches, prompt snapshots, predictions, logs
reports/         implementation + handoff report
```

## Commands

```bash
cd RH_test/E4_actor_evidence_decomposition_and_verification

# offline validation (no API):
(cd tests && python3 -m unittest discover)
python3 implementation/freeze_check.py            # E1/E2/E3/E3a untouched
python3 implementation/run_e4.py --variant e4c --mode dev --dry_run

# later, real experiments (needs DEEPSEEK_API_KEY; NOT run in this session):
export E4_RUN_TS=<timestamp>          # pin one run dir; enables resume
python3 implementation/run_e4.py --variant e4a --mode dev
python3 implementation/run_e4.py --variant e4b --mode dev   # reuses e4a caches
python3 implementation/run_e4.py --variant e4c --mode dev --evaluate
python3 implementation/run_e4.py --variant e4c --mode test  # submission files
```

Status: implementation + offline validation complete (2026-07-23). **No API
inference, no dev/test evaluation, no training has been performed.**
