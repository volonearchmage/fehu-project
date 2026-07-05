# Risk Control Checklist — DRA-FEHU Ablation Preparation

| Risk | Description | Control |
|------|-------------|---------|
| Direction inversion | A contradictory sample could be written with direction=1 (or vice versa), corrupting the DRR signal. | Explicit, frozen mapping `{"1 aligned":"1","0 contradictory":"0"}`; no silent inversion; a build-time check asserts each derived `direction` equals the mapped value of the candidate's `target_direction`. |
| Synthetic data leakage | Synthetic articles could accidentally enter the dev/test eval split or duplicate an official guid. | Synthetic guids are namespaced `aug_<candidate_id>`; a build-time check forbids any synthetic guid colliding with an official train/dev/test guid; augmented data added to TRAIN only, never to dev/test. |
| Official data pollution | Derived files could be written under `dataset/`, or official files overwritten. | Derived files written only under `output/research_ablation_inputs/<timestamp>/`; official dataset files sha256-verified byte-identical before/after; `dataset/` never opened for writing. |
| Overclaiming | Reporting improvements as significant/general from a tiny augmentation set. | Plan states no improvement claims before running both conditions; results framed as small-sample directional signal only; no significance claims from 6 examples. |
| Small-sample instability | 6 augmented examples may shift metrics by noise. | Fix seed and eval split across A and B; change only the augmentation factor; report per-label deltas with explicit small-sample caveat; consider repeated seeds in a later run. |
| Duplicate candidate | The same candidate could be counted twice, inflating the augmentation set. | Build-time uniqueness check on `candidate_id` and on synthetic guid/actor id; manifest lists exactly 6 unique ids. |
| Label mapping | An (l1_value, l2_value) pair could be inconsistent with the taxonomy. | Every derived label's L1->L2 pair validated against `dataset/hv_categories`; mismatch stops the build (no fallback). |
| Source-code dirty state | Pre-existing modified/untracked hybrid-pipeline files could be mistaken for task changes or accidentally committed. | Pre-existing dirty set recorded before the task and re-verified after; this task modifies no source files and does not commit; only the new output folder is written. |
