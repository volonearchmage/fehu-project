# Task 2 research protocol v2 pilot

Authoritative protocol: `d9d070ba1290c30520f8a56c053fb753fe30e956`, documents 05 and 06.
The main branch supplied documents only. Run the existing Linux research branch and local CUDA Python.

T/J/S share ModernBERT-base, revision `8949b909ec900327062f0ebf497f51aef5e6f0c8`,
full semantic input, mean pooling, shared 108-head, seed11, order and three-epoch AdamW schedule.
T applies event BCE only. J adds independent article BCE. S reuses the original gold-aware article loss.
P multiplies raw sigmoid probabilities from the selected J checkpoint and only chooses its own tune threshold.
The old failed eight-bag diagnosis is preserved. There is no new minimum F1 training gate.

`inputs.py` removes interpolated opaque IDs; semantic text is unchanged. IDs remain metadata.
It builds fit/tune caches only. Original body ownership and weighted scope aggregation from v1 are unchanged:
8192-token windows, overlap256, no truncation, complete event lists, one article loss per original bag.
The long fit bag now has 9585 original tokens and 8192/1985 windows.

`metrics.py` scans all global tune score boundaries with tied scores together, `>=`, empty threshold2.0,
then higher threshold and earlier epoch as tie breakers. Probabilities originate in float32, are serialized
without decimal rounding, and compared in float64 both during scanning and export.
`score.py` exports every tune candidate and runs the pinned official evaluator, checking TP/FP/FN.
Its official gold is reconstructed from the hash-verified, TRAIN-derived **tune-only** supervision cache.
No held-out gold, paid calls or training downloads are permitted by these entry points.

The reproducible local run is `output/task2_scope_local_v2/pilot_20261105-023648/execution`.
Its parent preserves the first failed bitwise recovery acceptance and its diagnosis. The training run
uses process-local deterministic algorithms and cuBLAS workspace settings uniformly across methods;
GPU backward non-determinism was isolated without changing any system or installed package.
It contains pinned reference documents, source/config snapshots, input manifests, real GPU receipt,
logs, epoch checkpoints, raw probabilities, selections, official scoring commands and results.
Large local outputs and weights must not be committed.

The completed [PILOT_RESULTS.md](../../output/task2_scope_local_v2/pilot_20261105-023648/execution/PILOT_RESULTS.md)
reports tune Task2b F1 T10.58%, J10.92%, S11.28%, P11.37%; these remain weak
development results. All three trained methods completed the fixed budget.
No holdout/DEV/TEST model scores, extension or additional seed were run.
`report.py` generates tables and figures; the delivered narrative also contains
reviewed metric-denominator and mechanism-scope notes. Raw results are immutable.

From the Git root, with the usual offline/thread environment recorded in `launcher.json`:

```bash
FEHU_PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
FEHU_RUN=ntcir19_fehu-master/output/task2_scope_local_v2/pilot_20261105-023648/execution
export PYTHONPATH=ntcir19_fehu-master PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_PROGRESS_BARS=1
"$FEHU_PY" -m research.task2_scope_local_v2.driver --run "$FEHU_RUN"
```

The run directory must contain an immutable matching `frozen.json` and new `preflight/receipt.json`;
the per-method output directories must not already exist. Do not launch this command concurrently.
The finite driver runs T, J, S then tune scoring and stops at the first actual failure.
It does not implement a daemon, automatic retries, automatic resume or extra training budget.

Explicit recovery from a **complete epoch** into a new output directory:

```bash
"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method J \
  --resume "$FEHU_RUN/J/epoch_1.pt" --out "$FEHU_RUN/J_recovered_new"
```

Preserved state includes model, AdamW, scheduler, Python/NumPy/Torch/CUDA RNG, epoch/step,
best checkpoint/threshold selection, history and binding. Recovery continues the original total498-step
schedule; it does not restart warmup or add epochs. It cannot resume halfway through accumulation.
If recovery uses a new directory, scoring must explicitly reference it, for example:

```bash
"$FEHU_PY" -m research.task2_scope_local_v2.score --run "$FEHU_RUN" \
  --j-dir "$FEHU_RUN/J_recovered_new" --out "$FEHU_RUN/tune_evaluation_recovered_new"
```

`epoch_sources` in the checkpoint and selection record locates selected epochs from before recovery.
The finite driver does not discover recovered runs automatically.

Focused changed-behavior checks:
`PYTHONPATH=ntcir19_fehu-master "$FEHU_PY" -m unittest research.task2_scope_local_v2.test_changes -v`.
They cover exact threshold boundaries, export precision, ID invariance of tokens/spans and T gradients.
The existing47-test suite is not repeated or presented as evidence of model quality.
