# Phase-2 Report — Controlled Augmentation × Supervision Ablation

**Date:** 2026-07-20
**Follows:** Phase-0 and Phase-1 reports under `new_check/`
**Workspace:** all code, inputs, checkpoints, predictions, probabilities, logs, and outputs are under `new_check/phase2/`; no existing artifact was modified or overwritten. Nine local training runs were executed (authorized for this phase); no API calls.

---

## 1. Design

Three cells × three seeds (42/43/44), all trained with the **unmodified frozen masked trainer** (`output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_deberta_masked_v2.py`), which with an empty supervision map is behavior-identical to the original `src/train_deberta.py`:

| Cell | Training data | Supervision of synthetic labels |
|---|---|---|
| **A** | official only (1,228 articles / 3,335 actor examples) | — (empty map ⇒ original trainer) |
| **B** | official + 900 round-2 records (2,128 articles / 4,235 examples) | **assume-negative** (unlisted classes = negatives) |
| **C** | official + 900 round-2 records (same files as B) | **masked** (450 `target_only` records supervised only on known classes; 450 `full_multilabel` fully supervised) |

Everything else is identical across cells by construction (same trainer binary, LoRA config, lr/schedule/batch, ≤15 epochs, patience 4 on dev 1b micro-F1, threshold 0.3). The round-1 340 records are **excluded everywhere** — this phase isolates the 900. No negative down-sampling or other new variables were introduced.

**Input integrity** (`inputs/inputs_manifest.json`): the official portion of the combined files is byte-identical to the dataset files; exactly 900 `aug2_r2_*` records (450 full / 450 target_only; 36 with known negatives); every guid appears exactly once.

**Execution integrity:** all 9 runs completed (logs in `logs/`); supervision splits printed by the trainer match the design in every run (A: 3335/0 masked; B: 4235/0; C: 3785/450). Cell A seed 42 **exactly reproduces the frozen historical baseline** (dev 1b micro-F1 0.3023, identical to `output/research_ablation_smoke_runs/20260704_201355/baseline/`) — a strong end-to-end replication anchor. Dev probabilities were exported from all 9 best checkpoints with the Phase-1 protocol, each **hard-validated** (0.30-thresholding reproduces that run's own frozen predictions exactly; any mismatch would have aborted).

Metrics follow the Phase-0 conventions exactly (official instance rule, safe-div, gold-supported macro; per-target AUC/oracle from the Phase-1 code, imported not copied). Full tables: `outputs/per_run_metrics.csv`, `per_target_per_run.csv`, `cell_aggregates.csv`, `paired_contrasts.csv`, `summary.json`.

## 2. Results

### 2.1 Per-cell aggregates (mean ± SD over 3 seeds, dev)

**Target-18 group:**

| Cell | micro-P | micro-R | micro-F1 | macro-P | macro-R | macro-F1 | ΣTP | ΣFP | AUC (mean over targets) | oracle-F1 (dev-tuned) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 0.000±0.000 | 0.000±0.000 | 0.000±0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0.513±0.030 | 0.048±0.010 |
| **B** | 0.045±0.040 | 0.033±0.046 | 0.032±0.036 | 0.008±0.007 | 0.025±0.032 | 0.011±0.010 | 4.7±6.4 | 69±90 | **0.624±0.011** | 0.095±0.014 |
| C | 0.027±0.046 | 0.005±0.008 | 0.008±0.014 | 0.002±0.003 | 0.003±0.005 | 0.002±0.004 | 0.7±1.2 | 7.7±13 | 0.577±0.028 | 0.080±0.019 |

**Non-target-90 group (75 gold-supported):**

| Cell | micro-P | micro-R | micro-F1 | macro-P | macro-R | macro-F1 |
|---|---|---|---|---|---|---|
| A | 0.292±0.030 | 0.336±0.042 | 0.310±0.003 | 0.026±0.005 | 0.077±0.016 | 0.035±0.002 |
| **B** | 0.232±0.019 | 0.527±0.101 | 0.319±0.005 | 0.076±0.031 | 0.216±0.086 | **0.108±0.044** |
| C | 0.269±0.011 | 0.396±0.066 | 0.318±0.017 | 0.045±0.016 | 0.113±0.033 | 0.058±0.022 |

**All-108:**

| Cell | micro-P | micro-R | micro-F1 | macro-P | macro-R | macro-F1 | DRR | best epoch | distinct classes |
|---|---|---|---|---|---|---|---|---|---|
| A | 0.292±0.030 | 0.316±0.039 | 0.301±0.004 | 0.021±0.004 | 0.062±0.013 | 0.028±0.002 | 0.158±0.061 | 3.3 | 7 |
| **B** | 0.230±0.020 | 0.498±0.096 | 0.311±0.004 | 0.063±0.026 | 0.179±0.074 | **0.089±0.037** | 0.282±0.051 | 10.3 | 36 |
| C | 0.269±0.012 | 0.373±0.063 | 0.310±0.017 | 0.037±0.013 | 0.092±0.027 | 0.047±0.018 | 0.220±0.037 | 7.0 | 16 |

### 2.2 Paired per-seed contrasts (`paired_contrasts.csv`)

| Contrast | Metric | Δ per seed (42/43/44) | Mean Δ | Sign-consistent? |
|---|---|---|---|---|
| **B−A** (augment., assume-neg) | mean target AUC | +0.076 / +0.154 / +0.103 | **+0.111** | yes (3/3) |
| **B−A** | all-108 macro-F1 | +0.016 / +0.080 / +0.086 | +0.061 | yes |
| **B−A** | target-18 TP | 0 / +2 / +12 | +4.7 | yes (weak) |
| **C−A** (augment., masked) | mean target AUC | +0.047 / +0.068 / +0.077 | **+0.064** | yes (3/3) |
| **C−A** | all-108 macro-F1 | +0.019 / 0.000 / +0.037 | +0.019 | yes (weak) |
| **C−B** (masking at fixed data) | mean target AUC | −0.030 / −0.086 / −0.026 | **−0.047** | yes — negative (3/3) |
| **C−B** | all-108 macro-F1 | +0.003 / −0.080 / −0.049 | −0.042 | no (2/3 negative) |
| **C−B** | target-18 TP | 0 / −2 / −10 | −4.0 | yes — negative |

## 3. Answers to the three questions

**Q1 — Do the 900 samples improve the 18 target labels?** **Yes, weakly but consistently at the score level; barely and unstably at the frozen threshold.** Cell A never predicts a single target instance in any seed (target AUC ≈ chance, 0.513 — replicating the Phase-1 finding across seeds). Adding the 900 raises mean target AUC in **6 of 6** augmented runs (B: +0.111, C: +0.064, sign-consistent in every seed) and dev-oracle F1 roughly doubles. At threshold 0.30, however, target true positives are tiny and seed-dominated (B: 0/2/12; C: 0/0/2). The 900 records genuinely move target scores; they do not yet produce a usable target classifier, and most of the induced macro gain again lands on **non-target** classes (B−A non-target macro +0.073 vs. target-18 macro +0.011) — the diffuse-improvement pattern Phase 0 saw in v2.

**Q2 — Is masked supervision the main source of improvement?** **No — this hypothesis is refuted.** At fixed data (C−B), masking makes things *worse*: mean target AUC −0.047 (negative in 3/3 seeds), target TP −4, all-108 macro −0.042 (negative in 2/3). The improvement comes from the **data**, and assume-negative supervision extracts more of it than masking. This overturns the working interpretation carried since the v2 run (and the earlier critical review's reading) that the masked loss was the likely active ingredient. A plausible mechanism, offered as interpretation: a `target_only` masked record supervises only ~1–2 of 108 classes and thus contributes almost no gradient, while assume-negative supervision of short single-value vignettes supplies 100+ approximately-correct negative labels per record; masked training is also visibly less stable (C seed 43 never improved past epoch 1 and behaved like cell A).

**Q3 — Are the improvements stable across seeds?** **Score-level effects, yes; thresholded metrics, no.** The AUC deltas are sign-consistent 3/3 with small SDs. Every fixed-threshold quantity is noisy: overall micro-F1 seed ranges overlap across cells (A 0.297–0.304, B 0.306–0.315, C 0.291–0.322), B's target TPs range 0–12, and single-seed comparisons at 0.30 would have supported *any* conclusion depending on the seed drawn. This retroactively invalidates single-seed threshold-level claims anywhere in the project, and confirms AUC/oracle readouts as the right instruments for tail progress.

## 4. What this proves, and what it does not

**Proved (within this protocol):**
1. The official-only model's total target failure is a property of the condition, not a seed accident (0 target predictions, chance AUC, 3/3 seeds).
2. The 900 records cause a real, reproducible score-level improvement on the targets under *either* supervision policy.
3. Masked supervision is not the enabler; at fixed data it *reduces* the benefit. The late-best-epoch phenomenon (v2's epoch 11) is reproduced by added data alone (B mean epoch 10.3) and is not specific to masking.
4. Augmentation costs direction accuracy (DRR 0.158 → 0.22–0.28), reproducing v2's DRR worsening.

**Not proved / open:**
- Neither B nor C approaches Augmented v2's results (macro 0.130, 12 target TPs, 50 classes at seed 42): v2 additionally trained on the **340 round-1 records**. Whether the 340, the extra volume, or a 340×900 interaction closes that gap is the next factorization (the missing D–G cells).
- Dev-based early stopping/model selection (shared by all cells for comparability with historical runs) may interact with condition; C's instability could partly be a selection artifact. An internal-split protocol would need a re-run to check.
- Whether B's assume-negative advantage would survive semantic screening of the 900 (its false-negative supervision is only *approximately* correct), and whether it holds for the 340 (whose single-label records motivated masking originally).
- All conclusions are dev-set; supports of 3–21 per target make per-target statements fragile even with 3 seeds.

## 5. Next experiment

The single most informative follow-up is completing the data factorization at 3 seeds under the same protocol:
- **F′**: official + 340 + 900, masked (= v2's configuration; checks whether v2's stronger result replicates across seeds and how much the 340 adds over C);
- **G′**: official + 340 + 900, assume-negative (tests whether B's policy advantage persists at full data — if yes, the project's best student config to date was never trained);
- optionally **E′**: official + 340 only, both policies (isolates the 340).

Given Phase 2's finding, G′ is the highest-value single run: it is the configuration the B result predicts to be best, and it has never existed.

## 6. Reproduction

```bash
python  new_check/phase2/scripts/prepare_phase2_inputs.py      # inputs (validated)
bash    new_check/phase2/scripts/run_all_cells.sh              # 9 trainings (~80 min, RTX 4090)
/home/szf-4090/miniconda3/envs/fehu/bin/python \
        new_check/phase2/scripts/export_probs_phase2.py        # probabilities + hard validation
python  new_check/phase2/scripts/analyze_phase2.py             # all tables
```
