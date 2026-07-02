# Preview Revision Report — Tiny Pilot v1, Preview Revision 2

**Session date:** 2026-06-14 (17:16 UTC)
**Scope:** improve prompt quality and FEHU safety of `generation_requests_preview.jsonl` after manual review of revision 1.
**Constraint honoured:** no API, no training, no augmented samples, no modification of the prior preview folder.

---

## 1. What changed (and why)

| # | Issue from manual review | Change applied | Why |
|---|---|---|---|
| 1 | Some canonical actor names are very long / unnatural (e.g. "Identitarian and Far-Right Activists (including Génération Identitaire, youth nationalists, supporters of Marine Le Pen, and affiliated online communities)"). Forcing them verbatim into content is unrealistic. | Added `derive_actor_mentions(canonical)` helper. Every paraphrase / rare-positive request now carries `canonical_actor_name`, `actor_aliases`, `suggested_actor_mentions`. Prompts require `actor_mention` (any natural surface form: canonical, primary, alias) to appear verbatim in `content`, while `actor_name` echoes the canonical identifier. `actor_id` remains in metadata. | Restores natural news prose while keeping a stable identity key for the augmented sample. |
| 2 | Seed excerpts were truncated mid-sentence. | Added `smart_truncate(text, max_len)` that cuts at the last sentence-terminating punctuation when possible; otherwise at the last whitespace with an ellipsis. Returns a `was_truncated` flag, which is stored in metadata and surfaced in the user prompt as a warning ("do NOT invent facts beyond the provided context"). | Cleaner inputs and an explicit guardrail against hallucinated extensions of the truncated seed. |
| 3 | Output schema was too small — no echo of label IDs, direction, or `is_positive`. | `expected_output_schema(req_type)` now defines 14 fields: `title`, `content`, `actor_name`, `actor_mention`, `evidence_sentence`, `explanation`, `l1_value_id`, `l1_value_name`, `l2_value_id`, `l2_value_name`, `direction`, `direction_name`, `is_positive`, plus a `_type_specific_rule` reminder. | Makes the generator's commitment explicit and easier for the augmented-data guard to validate downstream. |
| 4 | "Do NOT introduce a second clearly-expressed value" is too strict — FEHU is multi-label. | Replaced with: **"Do not make any other human value more salient than the target value."** (Located in `SAFETY_FOOTER` so it propagates to every request type.) | Aligns the constraint with FEHU's actual annotation rules while still preventing label-noise samples. |
| 5 | Paraphrase prompt needed stronger actor-specific evidence. | `EVIDENCE_REQUIREMENT_PARAPHRASE` rewritten to require: (1) verbatim presence in rewritten content, (2) description of the SAME actor's action/stance, (3) support for the same value+direction. Also new explicit rule: "do not over-generalise the actor (e.g. do not replace a specific NGO with 'a group')". | Forces the paraphrase to remain actor-specific, the core unit of FEHU evaluation. |
| 6 | Hard-negative prompt did not separate topic relevance from actor-specific value expression. | `build_hard_negative_request` and `EVIDENCE_REQUIREMENT_HARD_NEG` rewritten to enforce: TOPIC relevance (same domain as target value) AND the requirement that the TARGET ACTOR's actions/stance do not support either direction of the target value. `explanation` must specifically state why the target label does not apply to the actor (not just that the topic is different). | Produces genuinely hard negatives rather than ambiguous ones. |

Additional structural changes:

- **`preview_revision = 2`** stamped on every request object and on `generation_preview_config.json`.
- **Quality checklists and rejection rules** rewritten per request type with the new constraints (e.g. "is_positive = true; direction matches seed", "another L1 value made more salient than the target").
- **Direction-contrastive** prompt re-emphasises "the contrast is between actors' stances, not lexical direction words" and explicitly forbids both pair members sharing the same actor name.
- **README.md** gained a Preview-revision-history table.

---

## 2. New preview output folder

```
output/research_generation_preview/20260614_171644/
├── generation_preview_config.json    (preview_revision: 2)
├── generation_preview_report.md
├── generation_requests_preview.csv
├── generation_requests_preview.jsonl   (18 requests; 114 KB, up from 68 KB in rev 1 due to richer prompts + schema)
├── human_review_sheet.csv               (review_status: pending for every row)
├── request_summary_by_label.csv
├── request_summary_by_type.csv
├── selected_preview_seed_instances.jsonl
└── figures/
    ├── request_budget_vs_plan.png
    ├── requests_by_augmentation_type.png
    └── requests_by_label.png
```

**Old folder `output/research_generation_preview/20260614_163649/` is untouched** (file mtimes confirm).

---

## 3. Request counts (unchanged structure, richer content)

| Type | Target | Actual |
|---|---:|---:|
| paraphrase | 4 | 4 |
| rare_positive | 4 | 4 |
| hard_negative | 4 | 4 |
| direction_contrastive | 8 (4 pairs) | 6 (3 pairs)¹ |
| **TOTAL** | 20 | **18** |

¹ Same as revision 1: only 3 labels in the plan carry the `direction_contrastive` flag. The script honours the plan rather than padding.

Top labels included (same as rev 1, by design — the v2 changes are about prompt quality, not selection):

| L1 | Label | # requests |
|---:|---|---:|
| 29 | Be holding religious faith | 3 |
| 32 | Be behaving properly | 3 |
| 51 | Have the wisdom to accept others | 3 |
| 7  | Have an exciting life | 3 |
| 12 | Have success | 2 |
| 24 | Be neat and tidy | 2 |
| 38 | Be honest | 2 |

---

## 4. Spot-check (revision 2 fields on the first paraphrase request)

```
preview_revision: 2
canonical_actor_name: Identitarian and Far-Right Activists (including Génération Identitaire,
                      youth nationalists, supporters of Marine Le Pen, and affiliated online
                      communities)
actor_aliases: ['Génération Identitaire', 'youth nationalists',
                'supporters of Marine Le Pen', 'affiliated online communities',
                'Identitarian', 'Far-Right Activists']
suggested_actor_mentions: [<primary>, <each alias>]
seed_excerpt_truncated: True   ← honest signal; prompt now warns generator about it
evidence_requirement: "(1) appear verbatim in the rewritten content;
                       (2) describe the SAME actor's action/stance as the seed;
                       (3) support the SAME L1 value and direction…"
expected_output_schema: 14 fields including is_positive, l1_value_id,
                        direction, direction_name, actor_mention
_type_specific_rule: "paraphrase: is_positive=true; direction MUST match target direction."
```

Inspector confirms pair linkage is OK and surfaces the same `2 hard_negative requests missing alternative_label_id` warning as rev 1 — that is a planner-side observation (only 8 hard-negative labels in the plan; some lack a same-L2 sibling within the 20-label subset). The prompt explicitly tells the generator to pick a plausible alternative in that case, so this is a documented allowed condition, not a regression.

---

## 5. Safety / scope statement

| Check | Result |
|---|---|
| Any API call? | **NO** |
| Any training run? | **NO** |
| Any augmented sample generated? | **NO** |
| Any official dataset file modified? | **NO** |
| Any existing prediction file modified? | **NO** |
| Any existing cache file modified? | **NO** |
| Prior preview folder modified? | **NO** (mtime preserved) |
| `evaluation.py` modified? | **NO** |
| Files changed in this revision | **2**: `run_generation_preview.py` + `README.md` |
| Files created in this revision | **2**: this report + the new preview folder |

`git status --short` after this session should show only the two patched files plus the previous untracked research folders — no new tracked changes elsewhere.

---

## 6. Is the new preview safer than the previous one?

**Yes**, on five concrete axes:

1. **Identity stability.** Every paraphrase/rare-positive request now decouples "canonical actor identity" (stored in `canonical_actor_name` + `actor_id`) from "natural surface mention" (`actor_mention` + `actor_aliases`). The downstream training pipeline can deduplicate / link by identity, while the LLM can write natural prose.
2. **Honest truncation.** When the seed excerpt has been cut, the request carries `seed_excerpt_truncated: True` and the prompt explicitly says "do not invent facts beyond the provided context". This makes hallucination beyond the seed less likely.
3. **Self-describing output.** The expanded `expected_output_schema` requires the LLM to echo the label IDs and `is_positive`. The augmented-training-data guard (`research/fehu_submission_safety/augmented_training_data_guard.py`) can then cross-check that the generator agreed with the request — a request that asked for L1=32 direction=0 but received `direction: 1` is immediately rejectable.
4. **FEHU-compatible multi-label phrasing.** Rev 1's "do not introduce a second clearly-expressed value" would have rejected genuinely FEHU-style samples (FEHU articles routinely express multiple values). Rev 2's "do not make any other value more salient than the target" is faithful to the benchmark.
5. **Cleaner hard negatives.** The new hard-negative prompt separates topic relevance from actor-specific value expression and demands that `explanation` cite the actor's stance, not topic difference. This should reduce ambiguous negatives that the verifier would otherwise have to reject.

No safety regressions were introduced: the `preview_only`/`do_not_execute` flags, TRAIN-only seed policy, no-defamation rule, and content-length caps are all preserved.

---

## 7. Suggested next actions

1. Open the new `human_review_sheet.csv` (`output/research_generation_preview/20260614_171644/human_review_sheet.csv`) and mark each row `approved` / `rejected` / `needs_changes`.
2. For requests with `risk_level = "medium-high (no train seed)"` (hard-negatives + direction-contrastive), give the prompts a closer manual read since the generator has more freedom.
3. After approval, authorise creation of `research/fehu_augmentation_v1/run_generation.py` — that script should:
   - refuse to run on a folder whose requests have `do_not_execute: true`, **unless** invoked with `--approved` + a path to an approved manifest;
   - record `preview_revision` in each generated `augmented_samples.jsonl` record;
   - run `augmented_training_data_guard.py --strict` automatically before exiting.
4. No earlier than that: kick off the tiny-pilot generation.

**No augmented data exists yet. No API has been called. The next step still requires explicit user approval.**
