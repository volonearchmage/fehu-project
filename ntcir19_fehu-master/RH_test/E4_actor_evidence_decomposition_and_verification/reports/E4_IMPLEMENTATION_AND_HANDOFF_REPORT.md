# E4 Implementation and Handoff Report

**Experiment:** E4_actor_evidence_decomposition_and_verification
**Date built:** 2026-07-23
**Status:** implementation + offline validation complete. **No API inference,
no model training or fine-tuning, no dev-set evaluation, and no test-set
inference was performed.** All validation was offline (syntax, imports,
mocked-response unit tests, schema checks, dry runs).

---

## 1. Goal and constraints

E4 is a prompt-only Task-1 experiment intended to improve on E1 (best
replicated single-system dev result: 1b micro 0.5480) and eventually exceed
Liu's best reported Task-1b dev Micro-F1 of 0.5657, while remaining
directly usable on the official Task-1 test input.

Inputs used per article: `guid`, `title`, `content`, `actors` — verified to
be exactly the fields present in `dataset/test/test_article_event_base.json`
(the loader hard-fails if any is missing and touches nothing else).

Not used anywhere: official subevents, Task-2 labels/files, dev gold labels
during inference, DeBERTa, LoRA, any fine-tuning, dev-selected label lists
or per-label rules. The four taxonomy families and the sibling map are
built only from the official taxonomy structure (see §6/§7).

E1, E2, E3, E3a are preserved unchanged (hash-verified, see §11).

## 2. Final architecture

```
                       article (guid,title,content,actors)
                                      │
                     deterministic sentence split (S1..Sn)
                                      │
        ┌────────────── stage 1: evidence extraction (1 call) ─────────────┐
        │  DeepSeek Flash organizes exact sentence IDs into typed evidence │
        │  units per actor (action/statement/intention/consequence/        │
        │  evaluation_by_others/background); NO value labels allowed       │
        └───────────────────────────────┬──────────────────────────────────┘
                                        │ units (u1..uk, each → S# IDs)
            ┌───────────────────────────┼──────────────────────────────┐
            │ stage 2: GLOBAL VIEW      │      stage 3: FAMILY VIEW    │
            │ frozen E1 prediction      │      4 independent scans     │
            │ (byte-identical E1 system │      (openness / enhancement │
            │ prompt; E1 user prompt +  │      / conservation /        │
            │ evidence block; 1 call)   │      transcendence; 4 calls) │
            └───────────┬───────────────┴───────────────┬──────────────┘
     E4a output ◄───────┘ raw items → frozen            │ candidates with
     (frozen E1          process_results                │ evidence + reason
      conversion)                                       │
                        merge into candidate union (cid, sources, evidence)
                                        │
     E4b output ◄── union + fixed direction-conflict rule (no verifier)
                                        │
              stage 4: VERIFIER (1 call; judges ALL candidates)
              relevance / actor attribution / sibling contrast / direction
                                        │
     E4c output ◄── aggregation per config/aggregation_rules.json
```

All three variants emit official `pred_task1a.json` / `pred_task1b.json`
via the frozen E1 `process_results`, then re-validate the files against the
official schema (actor ids, l1 ∈ 0..53, direction ∈ {"0","1"}, l2 ∈ 0..19,
no 1b duplicates).

## 3. Differences between E4a, E4b, E4c

- **E4a** = E1 + evidence scaffold. The prediction call is the frozen E1
  logic: system prompt byte-identical to a real E1 run (same repaired
  few-shot demos `0-4349-1-t`/`0-4352-3-1`, same
  `targeted_more_shot_balanced` variant text — asserted by test), user
  prompt is E1's own with exactly one insertion (the evidence-unit block)
  before E1's closing instruction, spliced by an assert-exactly-once anchor
  replacement. Output parsing/conversion byte-reuses E1 functions. E4a
  reproduces E3a's structural benefit (walk the article unit by unit)
  without official subevents.
- **E4b** = E4a + dual-view candidates. The global view is E4a's own
  prediction (no numeric label cap, all 54 values jointly, E1's complete
  few-shot examples). The family view scans each of 4 fixed taxonomy
  families in its own call, listing only that family's values as assignable
  plus adjacent values from other families as explicit non-assignable
  contrast. Output = union of both views with a fixed direction-conflict
  rule (prefer the globally backed direction; unresolvable → drop pair).
- **E4c** = E4b + independent verifier + aggregation. The verifier judges
  every merged candidate (relevance KEEP/DROP/UNCERTAIN, actor attribution,
  sibling-label contrast, direction) and can never add candidates: its
  verdict set must equal the candidate ID set exactly or the response is
  rejected. Aggregation follows `config/aggregation_rules.json` (§8).

## 4. Files created (all new; nothing outside this directory was modified)

```
README.md
config/model_config.json            DeepSeek Flash settings (same as E1)
config/taxonomy_families.json       4 families over official L2 structure
config/sibling_map.json             curated cross-L2 confusable pairs
config/aggregation_rules.json       fixed aggregation rules (reviewable)
config/frozen_hashes.json           SHA-256 snapshot of E1/E2/E3/E3a/Liu
prompts/evidence_system.txt, evidence_user.txt
prompts/family_system.txt,  family_user.txt
prompts/verifier_system.txt, verifier_user.txt
implementation/e4_common.py         frozen-E1 import, config loaders, strict
                                    model caller, caches, violations log
implementation/sentence_split.py    deterministic split + traceability proofs
implementation/evidence.py          stage-1 prompts + all-or-nothing validation
implementation/predict_global.py    frozen-E1 global stage + anchor surgery
implementation/family_scan.py       family prompts + candidate validation
implementation/verify.py            verifier prompts + exact-coverage check
implementation/aggregate.py         merge + E4b union + E4c aggregation
implementation/outputs.py           official file writing + schema validation
implementation/run_e4.py            CLI orchestrator (variants, caches, dry run)
implementation/freeze_check.py      frozen-experiment hash verification CLI
tests/ (9 modules, 58 tests)        offline, mocked-model unit tests
runs/dryrun_preview_dev.log         real-article prompt preview (dev, no API)
runs/dryrun_preview_test.log        real-article prompt preview (test, no API)
reports/E4_IMPLEMENTATION_AND_HANDOFF_REPORT.md (this file)
```

Modified elsewhere: **nothing** (verified by `freeze_check.py`).

## 5. Prompt structure

- **Evidence stage** (`evidence_system/user.txt`): numbered original
  sentences + actor list → JSON `{"actors":[{"actor_id","units":[{"kind",
  "sentence_ids","note"}]}]}`. The prompt forbids value labels; the
  validator additionally rejects any unit carrying label-like keys
  (`l1_value_id`, `direction`, …) and any unit whose keys are not exactly
  `{kind, sentence_ids, note}`.
- **Global stage**: E1's frozen system prompt; E1's user prompt with the
  evidence block (each unit renders as `[u# | kind] — note` plus the quoted
  original sentences) inserted before the closing instruction.
- **Family stage** (`family_system/user.txt`): family values grouped under
  their official Level-2 names as the only assignable IDs; contrast block
  of adjacent families' values marked non-assignable; evidence units
  included; output candidates must cite sentence/unit IDs and a ≤20-word
  reason.
- **Verifier stage** (`verifier_system/user.txt`): article sentences +
  evidence units + one JSON line per candidate (cid, actor, value,
  claimed_direction, evidence, reason, found_by, closest_confusable_values
  from the sibling map) → one verdict per cid with the four judgments.
- Templates use `<<VAR>>` placeholders; rendering hard-fails on unused or
  leftover placeholders. Long articles (>12000 chars, 8 of 177 dev
  articles) mirror E1's own truncation: sentence-based stages show exactly
  the sentences overlapping E1's first-6000/last-3000-char window, with
  global sentence IDs preserved and omissions marked.

## 6. Taxonomy-family grouping

Fixed from the official `level_1_to_level_2.json` only: each family is a
set of official Level-2 categories grouped by the Schwartz higher-order
dimension encoded in the Level-2 names — openness_to_change (L2 0–3),
self_enhancement (L2 4–7), conservation (L2 8–13), self_transcendence
(L2 14–19). Validation (config loader + tests) proves the four families
partition all 20 L2 ids and cover all 54 L1 values exactly once. No dev
statistics were involved.

## 7. Sibling-label mapping strategy

Two layers, merged at runtime: (1) structural — every L1 value's siblings
include all other L1 values under the same official L2 category (computed
from the taxonomy, always present); (2) curated — 20 cross-L2 pairs whose
official names semantically overlap (e.g. 37 Be helpful ↔ 42 Be
responsible, 26 Have a safe country ↔ 46 Have a world at peace). The
curation is taxonomy-semantic, not dev-derived. Tests verify validity,
symmetry, no self-pairs, and same-L2 completeness.

## 8. Aggregation rules (config/aggregation_rules.json)

- Candidates found by BOTH views survive verifier relevance KEEP or
  UNCERTAIN; single-view candidates survive only KEEP; DROP always removes.
- Attribution in {other_actor, narrator, quoted_speaker, background}
  removes the candidate regardless of relevance; "uncertain" keeps (policy
  field, reviewable).
- The verifier cannot add candidates (enforced structurally: exact cid
  coverage required).
- Direction per (actor, l1): strict majority of the non-uncertain opinions
  of {global view, family view, verifier}; tie or no opinion → the pair is
  dropped. One direction per pair; aligned + contradictory are never both
  output (asserted in code; note the evaluator would accept both — this is
  a deliberate E4 design constraint).
- E4b (no verifier): union; direction conflicts keep the globally backed
  direction; unresolvable conflicts drop the pair.
- Every kept/dropped pair is written to `decisions.jsonl` (full audit
  trail), and rules changes are visible in `run_config.json`.

## 9. Expected API call flow and cost

Per article: evidence 1 + global 1 + family 4 + verifier 1.

| Variant | calls/article | dev (177) | test (175) |
|---|---|---|---|
| E4a | 2 | 354 | 350 |
| E4b | 6 | 1,062 | 1,050 |
| E4c | 7 | 1,239 | 1,225 |

Variants share stage caches within one `E4_RUN_TS`: running e4a → e4b →
e4c on the same run timestamp costs 7 calls/article total, not 15.
Retries (max 3/call) add only on failures. All calls are DeepSeek Flash
JSON-mode, temperature 0.1, max 8000 output tokens (E1's exact settings).

## 10. Cache, resume, and failure design

- Every stage has a JSON cache in `runs/<E4_RUN_TS>/cache_<stage>.json`
  keyed by guid, with a `_meta` identity header (stage, mode, model,
  temperature, max tokens, prompt hash). Resuming against a cache with a
  different identity is a **hard error** — caches never silently mix prompt
  or model versions. Writes are atomic (tmp + rename).
- The verifier cache stores a hash of the exact candidate set per guid; if
  upstream candidates change, the entry is recomputed, not reused.
- Fully cached reruns need no API key (the client is built lazily on the
  first cache miss).
- Failure policy (no silent fallbacks):
  - structural problems — malformed JSON, wrong shape, missing actors,
    invalid sentence IDs in evidence, verdict/candidate mismatch — raise
    `E4SchemaError`; the call is retried up to 3 times, then the run stops
    with `E4ModelError`. The evidence stage is all-or-nothing.
  - item-level violations on the final attempt (out-of-family value,
    invalid actor/direction/evidence reference in a candidate) reject only
    that item but are appended to `runs/<ts>/violations.jsonl`, logged at
    WARNING, and counted in `run_summary.json`. Nothing disappears without
    a written trace.
  - the frozen E1 conversion path for E4a keeps E1's own tolerance
    (invalid items dropped by `process_results`) — that IS the frozen
    behavior; the strict E4 candidate extraction runs beside it and records
    what E1 would drop.

## 11. Offline validation results (all performed; no API)

- `python3 -m py_compile` over all implementation and test files: clean.
- `tests/` — **58 tests, all passing**, covering:
  - sentence splitting: determinism, exact-substring traceability, span
    ordering/coverage proofs, abbreviation/initial handling, and a
    round-trip over **all 177 real dev articles**;
  - evidence validation: completeness (missing actor rejected), unknown
    actor/sid/kind rejected, value-label leakage rejected, empty unit
    lists allowed only explicitly;
  - families/siblings: 4-family partition of 20 L2 / 54 L1, contrast
    disjointness, prompt-block completeness, sibling symmetry/validity,
    and validity of all 54 L1 ids and 108 directed classes;
  - aggregation: deterministic merge and cid assignment, all survival
    branches (both-view UNCERTAIN survives, single-view UNCERTAIN
    rejected, DROP removed, attribution override), direction repair by
    majority, tie → drop, never-both-directions invariant, verifier
    cannot add (extra/missing verdicts rejected);
  - outputs: official-format writing via frozen `process_results`,
    L1→L2 projection, schema validation catching corrupt files;
  - mocked end-to-end: e4a/e4b/e4c produce expected predictions on a
    synthetic article; call counts exactly 2/4/1 with cache sharing; full
    resume needs **zero** calls; persistent model failure is a hard error;
    dry run touches no API;
  - frozen check: E1, E2, E3, E3a and `liu_method/run_pipeline.py` match
    the SHA-256 snapshot (23 files) taken before E4 was built.
- Frozen-E1 identity: E4's global system prompt is asserted byte-identical
  to the prompt a real E1 run builds; the user prompt is E1's own with one
  audited insertion.
- Dry runs on the **real** first dev article and first test article
  (`runs/dryrun_preview_dev.log`, `runs/dryrun_preview_test.log`): all four
  stage prompts render; global system prompt is E1's full 15,265-char
  few-shot prompt; exit 0; "no API was called".
- JSON parsing of all config files is exercised by the config loaders in
  every test run.

## 12. Known risks

1. **Evidence-stage strictness**: the all-or-nothing evidence validator
   hard-fails an article after 3 bad responses. If DeepSeek Flash proves
   unreliable at exact sentence-ID citation, dev runs may stop mid-way
   (resume is cheap: caches keep everything already done). This is by
   design (no silent degradation), but expect possibly a few manual
   restarts on the first dev run.
2. **Precision pressure from the family view**: 4 independent scans plus a
   no-cap global view will raise candidate volume; E4b union is expected to
   be recall-heavy/precision-poor. E4b is a diagnostic variant — E4c's
   verifier is the intended operating point (E3-report evidence: a
   verification layer is load-bearing).
3. **Single-direction constraint**: gold occasionally contains both
   directions for one (actor, l1). E4 outputs at most one by spec, so a few
   gold pairs are unreachable — the cost is bounded and symmetric across
   variants.
4. **Verifier prompt length**: articles with many actors × many candidates
   plus quoted evidence could produce long verifier prompts; median dev
   article is ~3.2k chars so headroom is large, but the 8 longest articles
   (>12k chars) should be watched in logs.
5. **Sibling/family curation is judgment-based** (though taxonomy-only):
   if a value is systematically skipped as "confusable", family recall for
   it drops; `decisions.jsonl` + `violations.jsonl` make this auditable.
6. **DRR**: E3a showed structural scaffolds can raise direction reversals;
   E4c's direction-repair majority vote is the mitigation, but DRR must be
   checked in the dev evaluation.

## 13. Commands

```bash
cd RH_test/E4_actor_evidence_decomposition_and_verification

# offline (safe anytime, no API):
(cd tests && python3 -m unittest discover)          # 58 tests
python3 implementation/freeze_check.py              # frozen-experiment check
python3 implementation/run_e4.py --variant e4c --mode dev --dry_run

# real dev experiments (LATER; needs DEEPSEEK_API_KEY):
export DEEPSEEK_API_KEY=...
export E4_RUN_TS=$(date +%Y%m%d_%H%M%S)   # one shared run dir → shared caches
python3 implementation/run_e4.py --variant e4a --mode dev            # 354 calls
python3 implementation/run_e4.py --variant e4b --mode dev            # +708
python3 implementation/run_e4.py --variant e4c --mode dev --evaluate # +177
# test submission (only after dev results justify it):
python3 implementation/run_e4.py --variant e4c --mode test
```

Interrupted runs: re-run the same command with the same `E4_RUN_TS`;
caches resume everything already completed.

## 14. Instructions for the next model (dev experiments)

1. Read this report and `config/aggregation_rules.json`; do not change any
   config before the first run (the rules are the registered experiment).
2. Re-run the offline suite + `freeze_check.py` first; all 58 tests must
   pass before spending API budget.
3. Optionally smoke-test with `--limit 5` (35 calls) and inspect
   `runs/<ts>/violations.jsonl`, `e4.log`, and one cached response of each
   stage before the full run.
4. Run e4a → e4b → e4c on ONE shared `E4_RUN_TS` (caches chain; total 7
   calls/article). Use `--evaluate` only when a run is complete.
5. Compare against: E1 1b micro 0.5480 / macro 0.3719; E3a 0.5666 / 0.4173
   (single passes); target: Liu's reported 0.5657 on 1b micro, with DRR and
   macro tracked. Evaluate all three variants — E4a isolates the evidence
   scaffold's effect, E4b isolates dual-view recall, E4c is the full
   system.
6. Any change to prompts/configs after seeing dev numbers is a NEW
   experiment: new run timestamp, and record the change; never edit E4
   configs in place to "fix" a result.

## 15. Compliance confirmation

- No DeepSeek or any paid API was called (all transports in tests are
  mocks; dry runs print prompts and exit before client creation).
- No dev-set or test-set experiment was run; no metrics were computed.
- No model was trained or fine-tuned.
- No prompt was modified based on dev performance.
- E1, E2, E3, E3a and the Liu pipeline are byte-identical to before this
  work (SHA-256 verified, `config/frozen_hashes.json`).
