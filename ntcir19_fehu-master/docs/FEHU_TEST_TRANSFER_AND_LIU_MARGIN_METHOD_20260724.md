# Test-Transfer & Liu-Margin Method — E6 (E3a-self) + E7 (calibrated jury fusion)

**Date:** 2026-07-24
**Inputs:** `RH_test/E3a_task1_only_subevent/reports/E3a_REPORT.md` (run `20260723_141123`), `RH_test/E3_subevent_decomposition/reports/E3_REPORT_vs_E3a.md` (run `20260723_162944`), `RH_test/E5_deberta_auxiliary_fusion/reports/E5_RESULTS_REPORT.md` (grid `20260724_125935`), `RH_test/E1_fewshot_repair/runs/20260722_152456/`, Liu frozen `targeted_more_shot_balanced` run, `dataset/test/test_article_event_base.json`.
**Status:** method specification only — no new code, no runs. Defines the gate experiment (E6) and the fusion stage (E7), with the math and the decision tree.

---

## 1. The two facts that reset the plan

**Fact 1 — the real Liu bar is 0.5657, not 0.5347.** Liu's best results (user-supplied,
2026-07-24): Task-1a micro 0.6555 / macro 0.5044; **Task-1b micro 0.5657 / macro 0.3870,
P 0.6149 / R 0.5067, DRR 0.0279**. Against this, our best single system E3a
(1b micro 0.5666 / macro 0.4173, P ≈ 0.522 / R ≈ 0.621, DRR 0.0414) **ties** 1b micro
(+0.0009 — inside any noise band), wins both macros and both 1a metrics, and **loses**
precision and DRR. The profiles are opposite: Liu is precision-heavy, E3a recall-heavy.

**Fact 2 — Task-1 test has no subevents.** `dataset/test/test_article_event_base.json`
(175 articles) carries only `{guid, title, content, actors}` — no `subevents` field — and its
guid set has **zero overlap** with the 175 articles of `test_subevent_event_base.json`
(verified 2026-07-24). Official subevents are therefore unobtainable for Task-1 test. But E3a
reads `article.get("subevents")` from the dataset
(`RH_test/E3a_task1_only_subevent/scripts/run_pipeline_e3a.py:344`): its dev score used the
**official dev segmentation** as input. Run unchanged on test, E3a silently degenerates to an
E1-like prompt with an empty SUBEVENTS block and instructions referring to nothing. The same
holds for E3's per-subevent union (its generator literally iterates official units).

**Consequence.** Our current best dev number is not test-defensible, and even if it were, its
margin over Liu is zero. The plan must (a) make the subevent gain test-transferable or prove it
isn't, then (b) build the margin from components that are article-only by construction.

## 2. E6 — E3a-self: the gate experiment

### 2.1 Question

Is E3a's gain (+0.019 micro / +0.045 macro over E1) a **procedural** effect of per-unit
reading — which survives when the model segments the article itself — or an **annotation**
effect leaking from the official segmentation's quality? Only the procedural part transfers to
test.

### 2.2 Design (one variable, E1→E2→E3a discipline)

Identical to E3a **byte-for-byte** except the source of the SUBEVENTS block:

- **Stage 0 (new): self-segmentation.** For each article, one API call asks the model to
  split the article into numbered subevents (event units), format-matched to the official
  ones (`id`, one-sentence description). No value taxonomy, no actors in this prompt —
  segmentation must not see the label space (prevents the segmenter from smuggling in value
  hints). Cache raw responses; parse fail-fast.
  - Target granularity: instruct "6–12 units, one event per unit" (dev official median = 9);
    record the achieved distribution.
- **Stage 1: E3a scaffold, unchanged.** Same system prompt, same two demos (which keep their
  *official* subevent texts — demos are training articles, whose subevents exist and are
  legitimately available at all times), same guideline 7, same output contract, same parser,
  same dedup. The only difference: the user prompt's SUBEVENTS block is filled from Stage 0
  instead of `dev_event_base.json`.
- **Model/params:** same as E3a run `20260723_141123` (same model, temperature, token
  budgets), so the E3a-self vs E3a comparison is one-variable.

Offline checks before any API call (E-series standard): demos byte-identical to E3a's; no
read of `subevents` from the eval articles file anywhere in the eval path; no
`subevents_human_values` anywhere; dry-run on 2 articles; outputs isolated under
`RH_test/E6_e3a_self_segmentation/`.

### 2.3 Readout and decision tree (pre-registered)

Run on full dev (177 articles), score with the E5-style evaluator (micro/macro P/R/F1, DRR,
t18/nt90, per-class). Three pre-registered outcomes:

| Outcome | Dev 1b micro | Interpretation | Action |
|---|---|---|---|
| **Transfers** | ≥ 0.560 (≈ E3a − noise) | scaffold effect is procedural | E3a-self becomes the generator; replicate ×3 |
| **Partial** | 0.550–0.560 | some annotation leakage | E3a-self still ≥ E1 → keep as generator; report both numbers honestly |
| **Collapses** | ≤ ~0.548 (E1 level) | dev gain was the official annotation | drop the scaffold; E1 is the generator; margin must come from E7 alone |

Secondary readouts: does the target-18 gain (+0.068 micro) survive; does the unit-support
signal (E3's monotone precision curve) survive when computed over *self-generated* units —
this determines whether unit support may be used as an E7 feature at test time.

**Replication note:** the standing ×3 replication requirement moves to **E3a-self** (or E1 if
E6 collapses). Replicating dataset-subevent E3a is moot — it has no test path.

## 3. E7 — calibrated jury fusion: building the margin over 0.5657

All members and signals below are **article-only** and have validated test paths.

### 3.1 Members (the jury)

| Member | Dev 1b (micro, P/R) | Role | Test path |
|---|---|---|---|
| E3a-self ×3 (or E1 ×3) | from E6 | recall-heavy generators | same pipeline, test articles |
| E1 frozen | 0.5480, 0.541/0.556 | balanced anchor | rerun on test |
| Liu frozen prompt | 0.5347, 0.568/0.505 | **high-precision juror** | article-only by construction |
| DeBERTa-v2 probs | 0.3306 alone | feature-only (never predicts) | `export_v2_probs.py` test flow, validated in E5 §7 |

Why Liu belongs inside: the ambiguity decomposition E_ens = Ē − Ā says ensemble gain is the
members' disagreement; a P 0.61/R 0.51 system paired with P 0.52/R 0.62 systems is maximal
diversity on this task by construction. Liu-agreement on a generator cell is strong precision
evidence; Liu-only cells are recall candidates with known precision.

### 3.2 Decision rule (same theory E5 used, now with veto mass to act on)

Plug-in expected-F1 maximization: a cell is worth predicting iff its calibrated posterior
**P(gold | evidence) ≥ θ = F/2** (Lewis 1995; Ye et al., ICML 2012; Lipton et al. 2014), and
symmetrically a predicted cell should be **removed iff P(gold) < θ**. With F ≈ 0.57, θ ≈ 0.28.

- **Evidence vector per cell** (all computable on test): vote count across the ×3 generator
  replicates; E1 agreement; **Liu agreement**; unit-support count over self-generated units
  (only if E6 validates the signal); DeBERTa-v2 exact probability and direction-agnostic
  value score (the E5 annotation layer, TP-vs-FP AUC 0.68).
- **Calibration:** cross-fitted isotonic (PAV) on dev exactly as E5 (`crossfit` for dev
  experiments, `fit`→`apply` for test; an article's own gold never influences its own
  decision). The E5 code is reused, with the evidence vector replacing the single v2 score
  (multi-feature: calibrate a monotone score such as a tiny logistic on the features, then
  PAV — keep it that simple).
- **Why E5's null does not predict a null here.** E5's veto found only 25 actionable cells
  because E1 is precision-balanced (P 0.54) and the only evidence was v2's weak score. The
  E7 veto operates on a recall-heavy generator (E3a-self carries ≈ 1,360 FPs at P ≈ 0.52,
  so far more mass sits below θ) with strictly stronger evidence (cross-run votes +
  Liu-agreement dominate v2's AUC 0.68 signal). Frontier arithmetic: at fixed R 0.621,
  lifting P 0.522 → 0.581 gives F1 ≈ 0.600; a conservative FDR-controlled veto removing
  ~100 cells at 75% removal-precision lands ≈ 0.575–0.58 — a real margin over 0.5657.
- **Rare-class guard, macro version.** For macro-F1 the optimal thresholds are per-class,
  θ_k = F_k/2 (Koyejo et al., NeurIPS 2015): tiny for rare classes. Structurally: the veto
  keeps E5's frequent-tier gate (official-train count > 130); rare/target-18 cells are never
  removed. This is what protects the macro lead (0.4173 vs Liu 0.3870) while micro is
  repaired.

### 3.3 Certified veto threshold (conformal risk control)

Instead of hand-picking the veto operating point on dev, choose it with a finite-sample
guarantee: treat dev articles as exchangeable calibration units and select the threshold λ by
Conformal Risk Control / Learn-Then-Test (Angelopoulos & Bates et al., ICLR 2024) such that
**E[fraction of removed cells that were gold] ≤ α** (α pre-registered, e.g. 0.25). This
converts the veto from a tuned dial into a certified mechanism and directly answers the
standing dev-triple-duty critique — the guarantee is distribution-free and holds on held-out
data by construction.

### 3.4 Direction repair (the double-dip)

Each direction reversal is simultaneously one FP and one FN; flipping it to gold converts both
into a TP: **ΔTP +1, ΔFP −1, ΔFN −1 per fix** — the most F1-efficient single edit available,
and it attacks the one metric where Liu clearly wins (DRR 0.0279 vs our 0.0414).

- **Scope:** only cells where jury members disagree on direction for an agreed value, or
  where the (validated) unit-support / annotation signals flag low direction confidence —
  a few dozen targeted QA queries per split, not a rerun (idea P6; E2 proved in-prompt
  direction exhortation is inert, so this must be a post-hoc stage seeing one candidate at
  a time — the same lesson as verification).
- **Never** from DeBERTa-v2 (E5 refuted it decisively: net −270 at margin ≥ 0).
- Arithmetic: E3a-class output has ~90+ reversals; fixing half ⇒
  (TP 1482, FP 1360, FN 908) → (1527, 1315, 863) ⇒ F1 ≈ 0.584 *and* DRR toward ≤ 0.028.

### 3.5 Ablation grid (pre-registered, E5 style — report all cells)

| Cell | Contents | Question |
|---|---|---|
| G0 | best single generator, pass-through | anchor |
| G1 | + calibrated veto (jury evidence, frequent gate, CRC-λ) | main precision repair |
| G2 | G1 without Liu-agreement feature | is Liu load-bearing as juror? |
| G3 | G1 + calibrated addition of Liu-only / vote-supported cells | recall from the jury |
| G4 | G3 + direction-QA repair | full system |
| G5 | G1 with no frequent gate | documents the macro artifact (expected harm) |
| REF | Liu frozen alone; each generator replicate alone | references |

## 4. Statistical requirement — what "make sure we beat Liu" means

1. **Pre-register** this grid and the decision rules (this document + a frozen E7 config)
   **before** the ×3 replicates are generated. With a +0.0009 baseline margin, any
   post-hoc-selected ensemble win is correctly dismissed as dev-fishing.
2. **×3 replicates** of the generator; fusion is deterministic given predictions, so it is
   rerun per replicate. Report mean **and min**.
3. **Paired article-level bootstrap** (10k resamples of the 177 dev articles) for the fused
   system vs Liu's 0.5657 reference; report Δ with 95% CI.
4. The target sentence: *"the worst of three replicates of the fused system exceeds Liu's
   best reported ensemble (1b micro 0.5657) with a bootstrap 95% CI excluding zero, while
   also leading macro-1b, both 1a metrics, and matching DRR."*
5. **Test-time flow** (only after the dev grid freezes a winner): generator ×1 on test
   articles, `export_v2_probs.py` test export, E7 `fit`(dev)→`apply`(test), direction-QA on
   the flagged subset. No gold is needed at apply time anywhere in the path.

## 5. Run order and cost

1. **E6 dev** (gate): ~177 segmentation calls + 177 scaffold calls, one pass. Decides the
   generator.
2. **E7 offline sizing** (free, minutes): Liu∩E3a agreement-tier precision and veto-mass
   below θ from existing dev prediction files — confirms the §3.2 arithmetic before any
   further spend.
3. **×3 generator replicates** on dev (the standing requirement, now pointed at the
   transferable variant).
4. **E7 dev grid** (offline except the direction-QA arm's few dozen queries).
5. Freeze → test.

Expected end state if E6 transfers and E7 behaves per §3.2: dev 1b micro ≈ 0.58–0.60 with
macro ≥ 0.41, DRR ≤ 0.03 — clearing 0.5657 on the metric Liu is strongest at, with the
margins certified rather than asserted.

## 6. Risks

- **E6 collapses to E1** — the plan survives (E7 over E1-class generators + direction repair),
  but the expected micro lands nearer 0.56–0.57 and the bootstrap CI becomes the decider.
- **Self-segmentation variance** — different runs segment differently; treated as a feature
  (structural diversity for the jury) but must be bounded by the ×3 replication.
- **Liu frozen run's provenance** — the 0.5657 target itself is not locally reproducible
  (`docs/liu_method_pipeline3_audit.md`); we compare against the *reported* number, and
  additionally against the locally reproducible 0.5347 run, stating both.
- **Design-on-dev** — mitigated exactly as E5: cross-fitted calibration, CRC guarantee,
  pre-registered grid, min-of-replicates reporting, final judgment on test.
