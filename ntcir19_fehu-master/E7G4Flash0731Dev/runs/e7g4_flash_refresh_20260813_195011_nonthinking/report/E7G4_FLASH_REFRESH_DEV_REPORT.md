# E7G4 current-Flash DEV refresh

Run: `e7g4_flash_refresh_20260813_195011_nonthinking`  
Started: 2026-08-13 19:50:23 +08:00  
Completed: 2026-08-13 20:46:01 +08:00  
Data: full frozen DEV, 177 articles  
Current API response: `deepseek-v4-flash`, system fingerprint
`a26a7955944dc5c60445bff77fac9c8e`

## Result in one sentence

The refreshed run is substantially weaker than the July E7G4 run: G4 drops from
0.5817/0.4308 to **0.5232/0.3367** in Task-1b micro/macro F1. The fusion layer still
provides a statistically clear gain over the refreshed E6b member, but it cannot recover
the much weaker and more volatile current member predictions. These numbers should be
treated as an exploratory current-backend result, not as a replacement for the frozen
submission result.

## Final member results

| Member | 1b micro | P | R | 1b macro | 1a micro | 1a macro | DRR | labels |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E1 | 0.4831 | 0.4885 | 0.4778 | 0.2652 | 0.6207 | 0.4258 | 0.0378 | 2,338 |
| Liu | 0.4907 | 0.6303 | 0.4017 | 0.2515 | 0.6112 | 0.4110 | **0.0252** | 1,523 |
| E6 | **0.5086** | 0.4625 | 0.5649 | **0.3248** | **0.6529** | **0.4996** | 0.0545 | 2,919 |
| E6b | 0.4832 | 0.4298 | 0.5519 | 0.3110 | 0.6387 | 0.4748 | 0.0549 | 3,069 |
| E6c | 0.4361 | 0.3320 | **0.6351** | 0.2977 | 0.6206 | 0.4708 | 0.0707 | 4,572 |

E6c still behaves as a recall-heavy value-evidence juror, but its very large prediction
set makes it unsuitable as the primary system. Liu remains the precision-heavy member.
Among the Flash members, E6 now outperforms the intended E6b primary.

## Fusion grid

| Cell | 1b micro | P | R | 1b macro | 1a micro | DRR | Actions |
|---|---:|---:|---:|---:|---:|---:|---|
| G0 E6b | 0.4832 | 0.4298 | 0.5519 | 0.3110 | 0.6387 | 0.0549 | none |
| G1 veto | 0.5023 | 0.4769 | 0.5305 | 0.3221 | 0.6421 | 0.0491 | 410 remove |
| G2 veto, no Liu | 0.5027 | 0.4797 | 0.5280 | 0.3219 | 0.6426 | 0.0473 | 438 remove |
| G3 veto + add | 0.5196 | 0.4589 | 0.5987 | **0.3371** | **0.6609** | 0.0527 | 410 remove, 459 add |
| G4 direction QA | 0.5232 | 0.4622 | **0.6029** | 0.3367 | **0.6609** | 0.0482 | 84 flips / 261 flagged |
| G5 veto, no gate | **0.5384** | **0.5551** | 0.5226 | 0.3262 | 0.6596 | **0.0468** | 819 remove |

G4 improves G3 micro by 0.0036 and reduces DRR by 0.0045, but macro decreases by
0.0004. This is unlike the July run, where direction QA improved all three measures.
G5 has the highest refreshed micro score, but selecting it after inspecting DEV would be
post-hoc model selection; it is reported diagnostically and should not replace the frozen
G4 submission.

## Old versus current

| System | July micro | Current micro | Delta | July macro | Current macro | Delta |
|---|---:|---:|---:|---:|---:|---:|
| E1 | 0.5480 | 0.4831 | -0.0649 | 0.3719 | 0.2652 | -0.1067 |
| Liu | 0.5347 | 0.4907 | -0.0440 | 0.3385 | 0.2515 | -0.0870 |
| E6 | 0.5412 | 0.5086 | -0.0326 | 0.4079 | 0.3248 | -0.0831 |
| E6b | 0.5496 | 0.4832 | -0.0664 | 0.4124 | 0.3110 | -0.1014 |
| E6c | 0.5343 | 0.4361 | -0.0982 | 0.3725 | 0.2977 | -0.0748 |
| G3 | 0.5790 | 0.5196 | -0.0594 | 0.4266 | 0.3371 | -0.0895 |
| G4 | **0.5817** | **0.5232** | **-0.0585** | **0.4308** | **0.3367** | **-0.0942** |
| G5 | 0.5703 | 0.5384 | -0.0319 | 0.3900 | 0.3262 | -0.0638 |

The change is not small sampling noise. E6b changes on 175 of 177 articles; its old and
current prediction-cell Jaccard similarity is only 0.4144. G4 also changes on 175 articles,
with Jaccard 0.5019. Current E6b emits 3,069 labels versus 2,894 previously, yet loses both
precision and macro F1. The refreshed behavior is therefore broader but less calibrated,
especially for the long tail.

## What still works

The hybrid fusion layer remains useful under this shift. Relative to refreshed E6b, G4
gains +0.0400 micro F1; paired article bootstrap gives a 95% interval of
[+0.0261, +0.0529] with `P(delta <= 0) = 0`. It also outperforms refreshed Liu by +0.0326,
95% interval [+0.0045, +0.0593]. This supports the role of the frozen DeBERTa probabilities
and jury evidence as a stabilizer, although it does not show that the current Flash backend
is better.

Absolute bootstrap for current G4 is 0.5232, 95% interval [0.4907, 0.5547]. Its estimated
probability of exceeding the reported Liu reference 0.5657 is only 0.0028, compared with
0.9685 for the July G4 run.

## API compatibility and comparability caveat

The first time-classified attempt, `e7g4_flash_refresh_20260813_190658`, used the old calls
without an explicit thinking switch. The current API consumed the 4k/8k output budget in
reasoning for some articles and repeatedly returned an empty final body. That attempt was
stopped and preserved with `metadata/ABORTED_REASON.txt`.

The completed run explicitly pins `thinking: disabled` for every Flash call. It also adds
fail-loud retry feedback for over-fine or malformed segmentations and doubles the output
budget only after a member JSON truncation. These changes prevent incomplete predictions,
but mean this is not a perfectly frozen one-variable replication. The July run did not
record an explicit thinking mode or a system fingerprint, so its exact server-side mode
cannot be reconstructed. Current DeepSeek documentation states that V4 thinking mode is
enabled by default:

- https://api-docs.deepseek.com/guides/thinking_mode
- https://api-docs.deepseek.com/api/create-chat-completion/

For the paper, retain the frozen July E7G4 and official submission results. If this refresh
is mentioned, describe it only as a post-submission robustness observation: an unversioned
hosted backend can drift substantially, and explicit inference-mode pinning is necessary
for reproducibility.

## Validation and records

- All five member caches contain 177 DEV records. E1 has one twice-confirmed genuine empty
  prediction (`2-34752-6-1`); all other member caches have zero empty entries.
- Both segmentation files contain all 177 articles. E6 has median 15 units (mean 15.83),
  while E6b has median 10 (mean 11.11).
- Every member and G4 prediction file has 177 article records and zero unknown actor IDs.
- G4 direction QA processed 261 flags, flipped 84, kept 177, and had zero API failures.
- SHA-256 hashes for 22 prediction files are in `metadata/output_sha256.txt`; frozen inputs
  are recorded in `metadata/input_sha256.txt`.
- `validation.json`, `members.json`, `bootstrap.json`, all fusion manifests, actions,
  annotations, QA decisions, caches, and logs are stored under this run directory.

