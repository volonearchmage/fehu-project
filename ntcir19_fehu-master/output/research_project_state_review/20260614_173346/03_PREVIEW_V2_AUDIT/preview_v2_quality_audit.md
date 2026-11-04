# Preview v2 Quality Audit

**Target preview:** `output/research_generation_preview/20260614_171644/`
**Stamp on every request:** `preview_revision: 2`
**Audit performed:** read-only, no API, no mutation of the preview folder.

## 1. Totals

| Metric | Value |
|---|---:|
| Total preview requests | 18 |
| Pass (no warnings) | 12 |
| Warn (non-blocking) | 6 |
| Fail (blocking) | **0** |
| Distinct TRAIN seed instances used | 8 |
| Seed reuse collisions | 0 |
| Direction-contrastive pair linkage | 100 % (3/3 pairs resolve) |

## 2. By augmentation type

| Type | Count | Notes |
|---|---:|---|
| paraphrase | 4 | All have TRAIN seed, canonical_actor_name, suggested_actor_mentions; all flagged `seed_excerpt_truncated: True` (smart-cut at sentence boundary, prompt explicitly warns generator) |
| rare_positive | 4 | All default direction `"1"` (aligned); 4 of 4 piggyback on the seed actor where one exists |
| hard_negative | 4 | `direction = null` (correct for negatives); 2 of 4 have `alternative_label_id = null` because the selected target is the only L1 in its L2 family inside the 20-label subset — prompt instructs the generator to pick one |
| direction_contrastive | 6 | 3 pairs (29 Be holding religious faith, 12 Have success, 38 Be honest); each request has a resolvable `paired_request_id` |

## 3. Human-review priority distribution

| Priority | Count | Rationale |
|---|---:|---|
| low | 4 | Paraphrase requests in pass+warn state, seed available |
| medium | 14 | Either explicit warn flag OR no seed (hard_negative + direction_contrastive let the generator invent the actor — needs human eyes) |
| high | 0 | No request is currently blocked |

## 4. Findings on the six conditions you asked us to check

| # | Condition | Result |
|---|---|---|
| 1 | `actor_name` / `canonical_actor_name` stable for downstream identity | ✅ Pass. Every paraphrase request carries the full canonical name + `actor_id`. Rare-positive piggy-backs on the seed's canonical name. Hard-negative and direction-contrastive intentionally leave `canonical_actor_name = null` because the generator invents the actor; prompts require setting `actor_name = actor_mention` for those. |
| 2 | `actor_mention` natural / suitable for generated content | ✅ Pass. `derive_actor_mentions()` extracts a short primary (first NP before `(`) and aliases from parenthetical enumerations and `X and Y` constructs. Example: a 200-char canonical name is reduced to primary `"Identitarian and Far-Right Activists"` plus six natural aliases. Prompts require any one of `[canonical, primary, alias]` to appear verbatim in content; `actor_name` echoes the canonical identifier. |
| 3 | Seed excerpt not misleading or cut mid-sentence | ✅ Pass. `smart_truncate()` cuts at the last `.` / `!` / `?` followed by whitespace within the window; falls back to whitespace + ellipsis. When truncated, the request carries `seed_excerpt_truncated: True` and the user prompt explicitly states *"do NOT invent facts beyond the provided context"*. |
| 4 | Output schema includes the expected fields | ✅ Pass. `expected_output_schema(req_type)` defines **14 fields** for every request: `title, content, actor_name, actor_mention, evidence_sentence, explanation, l1_value_id, l1_value_name, l2_value_id, l2_value_name, direction, direction_name, is_positive, _type_specific_rule`. Independent matrix check passed for all 18 requests (no missing schema keys). |
| 5 | `l1`/`l2`/`direction`/`is_positive` internally consistent | ✅ Pass. `l1_value_id`↔`l2_value_id` correctly mapped via `level_1_to_level_2.json`. `target_direction_name` matches the authoritative mapping for every request. `is_positive` expected value (paraphrase/rare_positive/direction_contrastive → True; hard_negative → False) is encoded in the schema's `_type_specific_rule` field. |
| 6 | Direction follows `aligned="1"`, `contradictory="0"` | ✅ Pass. See dedicated audit at `04_SAFETY_AND_SUBMISSION_GATES/direction_mapping_audit.md`. The v2 preview script declares `DIRECTION_NAME = {"1": "aligned", "0": "contradictory"}` (line 59). The matrix CSV confirms every request's `target_direction_name` is derived from this mapping. |

## 5. Per-type quality verdict

### Paraphrase (4)
- ✅ Same actor / value / direction enforced explicitly in system prompt.
- ✅ Evidence requirement: verbatim in rewritten content, describes same actor's action/stance, supports same L1 + direction.
- ✅ Explicit "do not over-generalise the actor" guard.
- ⚠ All 4 seed excerpts were smart-truncated to fit the 1500-char window. Non-blocking; prompts warn generator about it.

### Rare-positive (4)
- ✅ Default direction `"1"` (aligned).
- ✅ Prompt requires actor to be the SUBJECT of the value-bearing action.
- ✅ Replaces rev-1 strict "no second value" with "do not make any other value more salient than the target" — FEHU-compatible.
- ✅ Generic moral-slogan risk explicitly addressed via "concrete factual news style; no editorial".

### Hard-negative (4)
- ✅ Clear topic-vs-actor distinction in system prompt: "TOPIC relevance" plus actor-specific NON-expression.
- ✅ `explanation` MUST cite actor's stance, not topic difference.
- ✅ Rejection rule for ambiguous negatives present.
- ⚠ 2 of 4 have `alternative_label_id = null` (limit of the 20-label confusable pool); prompt instructs generator to pick from same L2 family. Non-blocking; recorded as medium priority.

### Direction-contrastive (6 = 3 pairs)
- ✅ All `paired_request_id` values resolve within the preview file.
- ✅ Both members of each pair share L1 value, differ in `direction`.
- ✅ Rejection rule "pair shares the same actor name" is in place.
- ✅ Rejection rule "pair differs only in surface direction words" is in place.

## 6. Files produced by this audit

- `preview_v2_request_matrix.csv` — one row per request, 19 columns, includes pass/warn/fail and human_review_priority.
- `preview_v2_warning_items.csv` — flattened list of 6 warnings.
- `preview_v2_quality_audit.md` — this document.

## 7. Verdict

**The v2 preview is ready for human review.** No request is blocked; the 6 warnings are all "expected by design" and the matrix correctly elevates them to `medium` review priority. The preview is **NOT yet authorised for API generation** — that requires the human-review step.
