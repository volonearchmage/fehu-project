# Pre-Ablation Approval Checklist — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T20:08:24
**Purpose:** Every item must be satisfied and explicitly human-approved BEFORE any controlled ablation
(training) task is started. This is a gate, not an execution step.

| # | Checklist item | Required state | Status |
|---|----------------|----------------|--------|
| 1 | Verified pool reviewed | 6 candidates, all human_decision=ACCEPT, all training_ready=false | PENDING HUMAN |
| 2 | Ablation inputs reviewed | baseline 1228/1228, augmented 1234/1234, augmented == baseline ++ 6 synthetic | PENDING HUMAN |
| 3 | Dry-run reviewed | schema 43/43 PASS; parse_task1b accepts format; F1=1.0, DRR=0 for identical gold/pred | PENDING HUMAN |
| 4 | Direction mapping caveat reviewed | direction_mapping.json = {1=aligned,0=contradictory}; evaluation.py DRR internal naming inverted but symmetric aggregates unaffected; F1 unaffected | PENDING HUMAN |
| 5 | Evaluator invocation method approved | use official functions programmatically; NOT the CLI (DEBUG=True); do not modify evaluation.py | PENDING HUMAN |
| 6 | Dirty working tree resolved or path-isolated | pre-existing hybrid-pipeline files (src/*.py, HYBRID_ROADMAP.md, research/) either committed elsewhere or confirmed path-isolated so ablation writes only under output/research_ablation_runs/<timestamp>/ | PENDING HUMAN |
| 7 | No official data modifications | all dataset/ files sha256-verified unchanged | PENDING HUMAN |
| 8 | No source-code modifications unless explicitly approved | ablation run must not edit src/ or evaluation.py; any needed training-driver goes under output/ or is explicitly approved | PENDING HUMAN |
| 9 | No fallback implementations | any missing dependency/schema must stop and be reported, not patched around | PENDING HUMAN |
| 10 | Explicit human approval before training | Peiyang records explicit ACCEPT to proceed to the controlled ablation execution task | PENDING HUMAN |

## Notes
- Items 1–5 are satisfiable from existing artifacts and only await human sign-off.
- Item 6 is the main operational blocker: the working tree currently carries pre-existing, unrelated
  modified/untracked files from prior hybrid-pipeline work. The ablation run must be path-isolated to a
  new `output/research_ablation_runs/<timestamp>/` folder (output/ is gitignored) so these files are
  neither touched nor confused with ablation artifacts.
- No item may be self-approved by the agent; all require explicit human decision.
