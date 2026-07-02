# 06 — Next Step Recommendation

## Readiness Decisions

| Question | Answer |
|---|---|
| Is the project ready to prepare a tiny ablation experiment? | **YES** — as a separate, explicitly-reviewed preparation task |
| Is it ready to run training immediately? | **NO** — ablation input construction must be reviewed first |
| Is it ready to scale generation? | **NO** — only 5 verified candidates exist; scaling is premature |

## What Should Happen Next
The project is ready for a **separate ablation-preparation task**, not direct training.
The next task should prepare a **controlled tiny ablation plan** using the 5 verified
candidates, while clearly handling the **incomplete L1=12 Have success**
direction_contrastive pair. Training should still wait until the ablation input
construction is explicitly reviewed.

## Options

### Option A — Ablate now with what we have
Run a tiny ablation with the **5 accepted verified candidates only**, while documenting
that the **L1=12 direction pair is incomplete** (aligned present, contradictory missing).
- Pros: fastest; no dependency on new generation.
- Cons: L1=12 lacks a contradictory counterpart, so any direction-sensitive result for
  L1=12 is confounded and must be reported as such.

### Option B — Complete the pair first (safer)
Before ablation, **generate a cleaner replacement** for the rejected L1=12 contradictory
candidate (per the spec in `04_pair_completeness_and_rerequest_plan.md`), **verify it**
through the same AI-assisted + human-decision workflow, then run ablation with complete
pairs.
- Pros: removes the L1=12 confound; both direction_contrastive pairs (L1=38, L1=12)
  complete; cleaner, more interpretable ablation.
- Cons: requires an additional generation + verification round before ablation.

## Recommendation
**Option B is the safer choice** when a clean direction-contrastive comparison for L1=12
matters, because it removes the confound before any measurement. If the immediate goal is
only to exercise the ablation *pipeline* (not to draw direction conclusions for L1=12),
**Option A is acceptable** provided the incomplete pair is explicitly documented in the
ablation results. In all cases, **do not run training until the ablation input
construction is explicitly reviewed.**
