# Preview v2 Quality Audit

**Target preview:** `output/research_generation_preview/20260614_171644/`
**Stamp on every request:** `preview_revision: 2`
**Audit performed:** read-only, no API, no mutation of the preview folder.
**Independent re-execution:** this is the second project-state review (the first was `20260614_173346`); numbers re-derived from the JSONL by this session reproduce the prior matrix exactly.

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
| `preview_only: true` on every request | yes |
| `do_not_execute: true` on every request | yes |
| Distinct `preview_revision` values | `{2}` |

## 2. By augmentation type

| Type | Count | Notes |
|---|---:|---|
| paraphrase | 4 | All have TRAIN seed + `canonical_actor_name` + non-empty `suggested_actor_mentions`. All 4 are flagged `seed_excerpt_truncated: True` (smart-cut at sentence boundary; prompt warns generator). |
| rare_positive | 4 | All default `target_direction = "1"` (aligned). 4 of 4 carry a seed actor from the planner. |
| hard_negative | 4 | `target_direction = null` (correct). 2 of 4 have `alternative_label_id = null` because the selected target is the only L1 in its L2 family inside the 20-label subset; the prompt instructs the generator to pick from the same L2 family. |
| direction_contrastive | 6 | 3 pairs (29 Be holding religious faith, 12 Have success, 38 Be honest). Every member's `paired_request_id` resolves to a sibling in the preview. |

## 3. Human-review priority distribution

| Priority | Count | Rationale |
|---|---:|---|
| low | 4 | Pass + warn paraphrase requests (seed available) |
| medium | 14 | warn-flagged OR no-seed requests (hard-negative / direction-contrastive let the generator invent the actor → needs human eyes) |
| high | 0 | No blocked request |

## 4. Per-condition findings

| # | Condition | Result |
|---|---|---|
| 1 | `actor_name` / `canonical_actor_name` stable for downstream identity | ✅ Pass. Paraphrase carries full canonical name + `actor_id`. Rare-positive reuses seed's canonical name. Hard-negative + direction-contrastive intentionally leave `canonical_actor_name = null` because the LLM invents the actor; prompts require `actor_name = actor_mention` for those. |
| 2 | `actor_mention` natural / suitable for generated content | ✅ Pass. `derive_actor_mentions()` extracts a short primary (first NP before `(`) and aliases from parenthetical enumerations and "X and Y" constructs. Prompt requires any one of `[canonical, primary, alias]` to appear verbatim in `content`; `actor_name` output echoes the canonical identifier. |
| 3 | Seed excerpt not misleading or cut mid-sentence | ✅ Pass. `smart_truncate()` cuts at the last `.` / `!` / `?` followed by whitespace; falls back to whitespace + ellipsis. Truncation flag is in metadata; user prompt explicitly says "do NOT invent facts beyond the provided context". |
| 4 | Output schema includes the expected fields | ✅ Pass. `expected_output_schema(req_type)` defines **14 fields** for every request: `title, content, actor_name, actor_mention, evidence_sentence, explanation, l1_value_id, l1_value_name, l2_value_id, l2_value_name, direction, direction_name, is_positive, _type_specific_rule`. Matrix verifies all 18 requests have these keys (0 schema-key misses). |
| 5 | `l1`/`l2`/`direction`/`is_positive` internally consistent | ✅ Pass. `target_l1_value_id ↔ target_l2_value_id` correctly mapped via `level_1_to_level_2.json`. `target_direction_name` matches authoritative mapping. `is_positive` expected (paraphrase / rare_positive / direction_contrastive → True; hard_negative → False) encoded in `_type_specific_rule`. |
| 6 | Direction follows `aligned="1"`, `contradictory="0"` | ✅ Pass. See `04_SAFETY_AND_SUBMISSION_GATES/direction_mapping_audit.md`. v2 preview script declares `DIRECTION_NAME = {"1": "aligned", "0": "contradictory"}` (line 59). |
| 7 | Paraphrase preserves same actor / value / direction / evidence | ✅ Pass. System prompt enforces all four; evidence requirement demands verbatim sentence in rewritten content describing the SAME actor's action/stance supporting the SAME value+direction; explicit "do not over-generalise the actor" guard present. |
| 8 | Rare-positive not generic moral slogans | ✅ Pass. System prompt requires concrete factual news style, actor as SUBJECT of value-bearing action, no first-person, no editorial. |
| 9 | Hard-negative topic-relevant but actor-specific target-value-negative | ✅ Pass. System prompt explicitly distinguishes TOPIC relevance from ACTOR-specific value expression; `explanation` MUST cite actor's stance (not topic difference); rejection rule for ambiguous negatives present. |
| 10 | Direction-contrastive pairs differ primarily in direction (not actor or topic) | ✅ Pass. System prompt requires (a) same domain, (b) different actor names, (c) difference in substance not surface words. Rejection rule "pair shares the same actor name" present. Every pair partner resolves. |
| 11 | Evidence requirement demands verbatim-in-content sentence supporting actor-specific value/direction | ✅ Pass. All four `EVIDENCE_REQUIREMENT_*` constants enforce: (1) verbatim presence in content, (2) actor-specific action/stance description, (3) support of the target value+direction (or alternative value for hard-negative). |

## 5. Per-type quality verdict

### Paraphrase (4)
- ✅ Same actor / value / direction enforced.
- ✅ Evidence requirement: verbatim in rewritten content, describes same actor's action, supports same L1 + direction.
- ✅ Explicit "do not over-generalise the actor" guard.
- ⚠ All 4 seed excerpts were smart-truncated to fit 1500-char window. Non-blocking; prompts warn generator.

### Rare-positive (4)
- ✅ Default direction `"1"` (aligned).
- ✅ Actor must be SUBJECT of value-bearing action.
- ✅ "Do not make any other value more salient" replaces rev-1 strict no-second-value rule → FEHU-compatible multi-label phrasing.

### Hard-negative (4)
- ✅ Clear topic-vs-actor distinction.
- ✅ `explanation` must cite actor's stance.
- ✅ Rejection rule for ambiguous negatives.
- ⚠ 2 of 4 have `alternative_label_id = null` (20-label confusable pool limit); prompt tells generator to pick. Non-blocking.

### Direction-contrastive (6 = 3 pairs)
- ✅ All `paired_request_id` resolve in preview.
- ✅ Both members share L1, differ in `direction`.
- ✅ Rejection rules for shared-actor or surface-only differences in place.

## 6. Files this audit produced (this session)

- `preview_v2_request_matrix.csv` — 18 rows × 19 cols.
- `preview_v2_warning_items.csv` — 6 design-justified warnings.
- `preview_v2_quality_audit.md` — this document.

## 7. Verdict

**The v2 preview remains ready for human review.** No request is blocked. The 6 warnings are all "expected by design" and correctly elevate the affected rows to `medium` review priority. **NOT yet authorised for API generation** — that step requires the human-review stage.
