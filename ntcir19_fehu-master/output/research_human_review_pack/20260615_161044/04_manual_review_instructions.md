# Manual Review Instructions — Human Review Pack v1

> **The DRAFT candidate manifest is not a permission slip.** No request is APPROVED yet. The reviewer's task is to read each candidate, decide APPROVE / DEFER / REJECT per row in `01_request_review_table.csv`, and produce a manually-approved successor manifest.

This pack is local-only. No script in it imports any API or HTTP client. Reading any file in this folder triggers no network activity.

## Files you will work with

| File | Role |
|---|---|
| `01_request_review_table.csv` | Review checklist with one row per request — **edit `reviewer_decision` and `reviewer_notes` here** |
| `02_low_risk_candidate_manifest_DRAFT.jsonl` | Computer-proposed shortlist (7 rows). Reference only; the reviewer is not bound by it |
| `03_deferred_or_rejected_requests.md` | Why each non-candidate was held back |
| `05_risk_scoring_rules.md` | How the risk score was computed |
| `output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl` | The full original requests (system prompt, user prompt, schema) |

## Step-by-step

### 1. Read the full original request

For any `request_id`, extract the full request:

```bash
python3 - <<'PY'
import json, sys
RID = "PUT_REQUEST_ID_HERE"
PATH = "output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl"
for line in open(PATH):
    r = json.loads(line)
    if r["request_id"] == RID:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        break
PY
```

For the candidate manifest specifically, all 7 IDs are listed in `02_low_risk_candidate_manifest_DRAFT.jsonl`.

### 2. Verify actor identity

- `canonical_actor_name` should refer to a single, identifiable entity (named individual, organisation, government body, named community).
- `suggested_actor_mentions` should include at least one short, natural mention.
- For invented-actor types (`hard_negative`, `direction_contrastive`), confirm the prompt clearly tells the generator to invent a named actor.

### 3. Verify L1 / L2 mapping

- `target_l1_value_id` must be in `"0".."53"`.
- `target_l2_value_id` must be the L2 to which the L1 maps in `dataset/hv_categories/level_1_to_level_2.json`.
- `target_l1_value_name` and `target_l2_value_name` must match the IDs in `human_value_level1_values.json` / `human_value_level2_values.json`.

### 4. Verify direction

- `direction == "1"` ⇒ `direction_name == "aligned"`.
- `direction == "0"` ⇒ `direction_name == "contradictory"`.
- `hard_negative` ⇒ `direction == null` AND `direction_name == null`.
- This convention is authoritative per `dataset/hv_categories/direction_mapping.json` (also documented in `output/research_project_state_review/20260614_235821/04_SAFETY_AND_SUBMISSION_GATES/direction_mapping_audit.md`). Do NOT infer direction from `evaluation.py` comments — those are inverted (DRR symmetric, scores unaffected).

### 5. Verify evidence requirement

The `evidence_requirement` field should demand:

- a sentence that appears **verbatim in the generated `content`**, AND
- one that describes the **target actor's** action / stance / decision / behavior, AND
- one that **supports the target L1 value in the target direction** (or, for `hard_negative`, supports the alternative L1 value).

If any of these three conditions cannot plausibly be met by an LLM given the prompt, mark `reviewer_decision = REJECT` or `DEFER` with notes.

### 6. Type-specific checks

#### Paraphrase
- The seed actor identity and the target value/direction must be **preserved** by the rewrite.
- The seed excerpt should be self-contained enough that the rewrite has a story to retell.
- Read the seed excerpt before approving. If it is truncated mid-context, mark `DEFER`.

#### Rare-positive
- The generated article must not read like a generic moral slogan.
- The named actor must be the **subject of the value-bearing action**, not a passive witness.
- Read the augmentation rationale and the actor archetype suggestion before approving.

#### Hard-negative
- Confirm the prompt distinguishes **topic relevance** (the surface domain) from **actor-specific value expression** (which must be absent for the target value).
- Confirm the `alternative_label_id` is set (or that the prompt forces a sensible alternative). The four hard-negatives in this preview are all DEFER'd because the first pilot does not include them — re-add them in a later pack with `alternative_label_id` manually filled.

#### Direction-contrastive
- Always review the **pair together**. APPROVE both members or DEFER both.
- The two articles should share topic but differ in actor + substance, not just in surface direction words.
- Confirm `paired_request_id` resolves to the partner request in the preview file.

### 7. Record your decision

In `01_request_review_table.csv`:

- `reviewer_decision` ∈ {`APPROVE`, `DEFER`, `REJECT`}.
- `reviewer_notes` should be brief; mention any prompt-adjustment requests if you choose `DEFER`.

After review, produce a manually-approved successor manifest (e.g. `02b_human_approved_manifest.jsonl`) listing only the IDs you marked `APPROVE`. **Do not** edit this pack's `02_low_risk_candidate_manifest_DRAFT.jsonl` in place — keep the DRAFT as a record of what the script proposed.

## What the next phase looks like (NOT to run yet)

Once a human-approved manifest exists, the assistant may be asked to author `research/fehu_augmentation_v1/run_generation.py` with:

- a dry-run-first default (refuses to send HTTP without `--execute`);
- a manifest-required guard (refuses any request whose `do_not_execute` is true unless an approved manifest is passed in);
- automatic invocation of `research/fehu_submission_safety/augmented_training_data_guard.py --strict` on the output.

Nothing in **this** session prepares for that step beyond clarifying which requests will eventually populate it.
