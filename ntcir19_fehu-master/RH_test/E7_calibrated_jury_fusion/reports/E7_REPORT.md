# E7 — Calibrated Jury Fusion: RESULTS

**Status: EXECUTED on full dev. Grid run `20260725_004522` (primary E6b; jury E6, E6c, E1, Liu;
DeBERTa-v2 probabilities as features).** Date: 2026-07-25.
Method pre-registered in `docs/FEHU_TEST_TRANSFER_AND_LIU_MARGIN_METHOD_20260724.md` §3;
E6/E6b/E6c reports under their own experiment dirs. All members are **article-only**
(no dataset subevents anywhere in any eval path) — the whole stack is test-legal.

## 1. Systems

| member | config | 1b micro | 1b macro | 1a micro | DRR | role |
|---|---|---|---|---|---|---|
| E1 | frozen `20260722_152456` | 0.5480 | 0.3719 | 0.6574 | 0.0347 | balanced juror |
| Liu frozen | `targeted_more_shot_balanced` | 0.5347 | 0.3385 | 0.6447 | 0.0230 | high-precision juror |
| E6 | self-seg (median 12), flash | 0.5412 | 0.4079 | 0.6535 | 0.0504 | recall juror |
| **E6b** | self-seg 6–9 (median 8), flash | 0.5496 | 0.4124 | 0.6621 | 0.0459 | **primary** |
| E6c | E6b segs, **deepseek-v4-pro non-thinking** | 0.5343 | 0.3725 | **0.6774** | 0.0657 | value-evidence juror |
| DeBERTa-v2 | probabilities only | — | — | — | — | continuous feature |

E6c confirms the user-reported pro profile on our scaffold: best Task-1a of any single system
(0.6774) but weakest 1b direction handling (DRR 0.0657) — ideal as a value-level juror and
direction-disagreement flagger, never as a direction source.

Fusion rule (per method doc): plug-in expected-F1 — remove a primary cell iff cross-fitted
calibrated P(gold) < θ = F1_primary/2 (θ ≈ 0.27), add a juror-supported cell iff calibrated
P(gold) ≥ θ; evidence score = jury exact votes + 0.25·value-only votes + v2 score, PAV-calibrated
per fold (md5(guid) % 2 — an article's own gold never touches its own decision); removal barred
outside the 38 frequent classes (official-train count > 130) and can never empty an actor;
additions capped at 2/actor and never fight the primary's direction. G4 adds targeted
direction-QA (flash, one value per call) only on cells where ≥1 juror holds the opposite
direction and the fused set doesn't hold both.

## 2. Grid results (dev, one scorer for everything)

| cell | 1b micro | 1b P / R | 1b macro | 1a micro | DRR | t18 | nt90 | actions |
|---|---|---|---|---|---|---|---|---|
| G0 = E6b anchor | 0.5496 | 0.502/0.608 | 0.4124 | 0.6621 | 0.0459 | 0.3145 | 0.5656 | none (byte-equal enforced) |
| G1 veto | 0.5608 | 0.559/0.563 | 0.4146 | 0.6587 | 0.0374 | 0.3145 | 0.5794 | 484 removals |
| G2 veto, no Liu | 0.5619 | 0.561/0.562 | 0.4135 | 0.6582 | 0.0369 | 0.3145 | 0.5806 | 500 removals |
| **G3 veto+add** | 0.5790 | 0.539/0.626 | 0.4266 | 0.6874 | 0.0450 | 0.3145 | 0.5975 | 484 rm + 364 add |
| **G4 = G3 + dirQA** | **0.5817** | 0.542/0.629 | **0.4308** | **0.6874** | 0.0419 | **0.3264** | **0.5995** | +46 flips (176 flagged, 7 QA-fail kept) |
| G5 veto, no gate | 0.5703 | 0.576/0.564 | 0.3900 | 0.6707 | 0.0410 | 0.3241 | 0.5842 | 553 removals |

Reference points: E3a (dataset subevents, **not test-legal**) 0.5666/0.4173; H3 0.5474/0.3382;
**Liu best (reported)** 1b 0.5657/0.3870, 1a 0.6555/0.5044, P 0.6149/R 0.5067, DRR 0.0279.

## 3. Statistical validation (paired article bootstrap, 10k resamples, seed 20260725)

| comparison | Δ point | 95% CI | P(Δ ≤ 0) |
|---|---|---|---|
| **G4 − E1** | +0.0338 | [+0.0201, +0.0475] | **0.0000** |
| G4 − Liu frozen | +0.0470 | [+0.0323, +0.0615] | 0.0000 |
| G3 − E1 | +0.0310 | [+0.0177, +0.0444] | 0.0000 |
| **G4 − E6b (fusion layer alone)** | +0.0321 | [+0.0209, +0.0433] | **0.0000** |

Absolute: G4 point 0.5817, CI95 [0.5647, 0.5990]; **P(G4 > Liu-reported 0.5657) = 0.9685**.
(The reported Liu number has no per-article predictions locally, so it enters only as a
constant; the paired tests use the locally reproducible Liu run.)

## 4. Findings

1. **The fusion layer itself is significant** — G4−E6b = +0.032 with CI excluding zero.
   Contrast with E5, where the same decision rule with only the weak DeBERTa auxiliary produced
   a null: what changed is the *evidence*, not the theory. Jury votes from strong, diverse LLM
   systems give the calibrator real signal on both sides (484 justified removals, 364 justified
   additions).
2. **The addition arm — dead in E5 — is the biggest single contributor here** (+0.018 micro,
   +0.029 1a from G1→G3): cells that ≥2 jurors support clear θ ≈ 0.27 comfortably. This is the
   ambiguity-decomposition prediction realized: heterogeneous members (recall-heavy E6-family,
   precision-heavy Liu, balanced E1, value-strong E6c) recover each other's misses.
3. **Direction-QA delivers the predicted double-dip**: 46 flips → micro +0.0027, macro +0.0042,
   DRR 0.0450→0.0419, t18 +0.012 — small but everything moves the right way with ~170 cheap calls.
4. **Liu is not load-bearing as a juror** (G2 ≈ G1): the E6-family + E1 carry the veto evidence.
   Liu still contributes via additions in G3 (its precision profile feeds the addition arm).
5. **The frequent-class gate does its job**: G5 (no gate) trades −0.041 macro for +0.010 micro
   vs G1 — the pre-registered artifact, documented and rejected.
6. **Best system: G4 leads Liu's reported best on 1b micro (+0.016), 1b macro (+0.044),
   1a micro (+0.032), and both group metrics**, with target-18 at an all-time best 0.3264.
   The single remaining loss is DRR (0.0419 vs 0.0279).

## 5. Honest caveats

- **Single pass per member.** No ×3 replication yet of E6b/E6/E6c (standing requirement); the
  bootstrap quantifies article-sampling noise, not run-to-run noise (documented ±0.004 for this
  config class — small relative to the +0.032 fusion margin, but replication remains the
  pre-registered gate before any final claim).
- **Design-on-dev**: grid pre-registered in the method doc and cross-fitted; but θ, the score
  weights (0.25), and the gate were designed after seeing dev-era analyses. Final judgment is
  the test run (`fit`→`apply` path; all members article-only).
- **P(G4 > 0.5657) = 0.9685**, not ≥ 0.999: the absolute CI lower bound (0.5647) sits just
  under the reported constant. The *paired* margins are unambiguous; the absolute claim vs a
  number we cannot audit locally is strong but not airtight.
- 7 of 176 direction-QA cells failed all retries and kept their original direction (logged in
  `dir_qa_decisions.jsonl`, never silent).

## 6. Records (all under `RH_test/E7_calibrated_jury_fusion/`)

- `runs/20260725_004522_G*/`: `pred_task1{a,b}.json`, `fusion_manifest.json` (sha256 of every
  member input, calibration record incl. per-fold θ and cell counts), `actions.jsonl` (every
  removal/addition with calibrated p and jury votes), `annotations.jsonl` (per-cell jury
  evidence), `metrics.json` + `per_class_metrics.csv` (E5 scorer), G4 adds
  `dir_qa_decisions.jsonl` + QA cache.
- `runs/20260725_004522_bootstrap.json`: full bootstrap report.
- `baselines_eval/Liu_frozen/`: Liu frozen predictions re-scored under the same scorer.
- `scripts/`: `run_fusion_e7.py`, `run_direction_qa_e7.py`, `bootstrap_e7.py`.
- Member experiment records: `RH_test/E6_e3a_self_segmentation/`, `RH_test/E6b_granularity_control/`,
  `RH_test/E6c_pro_nonthinking/` (each with runs/, reports/, offline checks).

## 7. Next steps

1. **×3 replication** of E6b (and optionally E6/E6c) with fusion re-run per replicate — the
   pre-registered gate; report min-of-3.
2. **Test flow** once frozen: run E6b/E6/E6c/E1/Liu pipelines on `test_article_event_base.json`
   (all article-only), export v2 test probabilities (validated E5 path), fit calibrators on dev
   (`fit`), apply to test (`apply`), G4 direction-QA on flagged test cells (no gold needed).
3. DRR remains the one Liu-favored metric — extending G4's flag rule (e.g., QA on all
   jury-unsupported directions, not just explicit disagreements) is the obvious pre-registerable
   extension.
