# Patch Summary — src/train_deberta.py

**Created at:** 2026-07-04T20:03:42

## Exact CLI args added (in `parse_args`)
| Arg | Type | Default | Purpose |
|-----|------|---------|---------|
| `--train_articles` | str | `str(TRAIN_ARTICLES)` (official train event_base) | Path to train event_base JSON |
| `--train_labels` | str | `str(TRAIN_LABELS)` (official train gold) | Path to train human_values (gold) JSON |
| `--seed` | int | `None` | Deterministic seeding when set; None preserves prior behavior |
| `--checkpoint_dir` | str | `None` (→ existing `CHECKPOINT_DIR` constant) | Per-condition checkpoint isolation |

## Exact behavior of each new arg
- **`--train_articles` / `--train_labels`**: resolved in `main()` to `Path(...)`. Both are validated
  with `if not p.is_file(): raise SystemExit(...)`. When omitted, they default to the official train
  constants (unchanged behavior). When explicitly set to a missing/invalid path, the run **fails loudly**
  — it never reverts to the official file.
- **`--seed`**: when not `None`, `set_seed(seed)` seeds Python `random`, NumPy, PyTorch, CUDA
  (`manual_seed_all` when available), and Transformers (`transformers.set_seed`). Seeding the global
  torch generator also makes `DataLoader(shuffle=True)` sampler order deterministic. When `None`, no
  seeding occurs — identical to prior behavior.
- **`--checkpoint_dir`**: when provided, reassigns the module global `CHECKPOINT_DIR` (absolute path
  used as-is; relative resolved under `BASE_DIR`). `save_ckpt`/`load_ckpt` read this global, so the whole
  active flow uses the resolved dir. When omitted, the original constant is used unchanged.

## Where train path loading now uses the args
- `main()`: `train_ex = build_examples(train_articles, train_labels)` (was
  `build_examples(TRAIN_ARTICLES, TRAIN_LABELS)`). Dev loading is unchanged (official dev is the
  intended invariant).
- `run_config.json` provenance now records the actually-used `train_articles`/`train_labels` and the
  `seed`, so reported runs trace to their real inputs.

## Where checkpoint_dir is applied
- `main()` reassigns `global CHECKPOINT_DIR` from `--checkpoint_dir`; `save_ckpt`/`load_ckpt`
  (best-model save at line ~425 and final `load_ckpt(device)` before prediction) consume that global.
  `run_config.json["checkpoint_dir"]` reflects the resolved dir.

## How seed is set (`set_seed` helper)
```python
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    hf_set_seed(seed)   # transformers.set_seed
```
Added imports: `import random`, `import numpy as np`, and `set_seed as hf_set_seed` from `transformers`.

## No-fallback behavior
Invalid explicit `--train_articles`/`--train_labels` raise `SystemExit` with the offending flag and path.
There is no `try/except` that substitutes the official constants, no alternate hidden loading path, and
no wrapper script. Defaults are applied only when the argument is omitted entirely (argparse default),
never as a recovery after an explicit invalid path.

## Backward compatibility
Running `python src/train_deberta.py` with no new arguments is behaviorally identical to before: train
paths default to the official constants, `--seed` defaults to `None` (unseeded), and `--checkpoint_dir`
defaults to the original constant. The only externally visible change is the added `--help` entries.
Verified: `py_compile` OK and `--help` lists all four new args (see `04_cli_help_after.txt`).

## Note on git numstat
`git diff --numstat` reports 183/6 for this file because it compares against HEAD and therefore includes
pre-existing (already-uncommitted) modifications to `train_deberta.py` from prior work. The edits made by
*this* task are the additions listed above (imports, `set_seed`, four CLI args, seed/path/checkpoint
resolution in `main`, and provenance fields).
