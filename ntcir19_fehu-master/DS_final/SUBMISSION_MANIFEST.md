# FEHU Task-1 Submission Manifest

Generated and validated on 2026-07-26 (Asia/Shanghai).

## Submission files

| File | Articles | Predictions | SHA-256 |
|---|---:|---:|---|
| `submission/pred_task1a.json` | 175 | 1,834 | `be4573ff447960b1b8b4381020b58f98397d12b15ae1958908cf25db0616ed54` |
| `submission/pred_task1b.json` | 175 | 2,260 | `d820c65f92ba01b51830954620ea026acc6a84fdc9cdef20abddf94b7ec28d77` |
| `FEHU_Task1_DS_final_20260726.zip` | — | — | `11d025b1c6553ab76e0943d1d536521a47d235a8db06d3eab9398e1393fc3a42` |

The ZIP contains exactly `pred_task1a.json` and `pred_task1b.json` at its root.

## Validation

- Official test event-base coverage: 175/175 guids.
- Actor coverage: 479/479 actors have predictions.
- Strict schema guard: CLEAN (exit 0).
- Invalid guid, actor, L1, L2, or direction: 0.
- Duplicate official prediction tuples: 0.
- Empty articles: 0.
- Task-1a equals the deterministic L1→L2 projection of Task-1b.
- Repository unit tests: 124 passed.

The eight cases where an actor/L1 pair has both direction labels are legal
direction-aware labels under the official schema and are retained from the
validated dev-optimal ensemble policy.

`outputs/dev_metrics.json` contains dev-set evaluation only. There is no local
test score because official test gold labels are not available.
