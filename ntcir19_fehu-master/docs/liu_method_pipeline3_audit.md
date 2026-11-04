# Liu reference method — audit against Pipeline 3

Date: 2026-07-13.
Reference files (read-only, never imported at runtime):
`liu_method/run_pipeline.py` (1065 lines), `liu_method/label_aware_ensemble.py` (225 lines).
Audited implementation: `src/prompts_task1_v3.py`, `src/task1_v3_ensemble.py`,
`src/run_pipeline_prompt_v3.py`, `src/calibrate_task1_v3.py`.

## 1. What Liu's method actually is

### 1.1 Prompt variants (all string-patches of one baseline)

| Variant | Construction |
|---|---|
| `baseline` | Label-**name** list only (no official definitions), 2 TRAIN few-shot examples, "3-7 values per actor", four actor-role "Common patterns" (police → Be just 45, victims → contradicted 22/25, crisis orgs → 37/38, criminals → 30/42), `reasoning` field per item. |
| DeepSeek adaptation | Rewrites output to a JSON **object** with an `"items"` array (JSON-object mode requirement), makes `reasoning` optional (≤ 8 words), adds one literal example JSON block. |
| `balanced` | Adds "ERROR-ANALYSIS-INFORMED CALIBRATION": evidence gates for 5 over-predicted generic labels (37, 45, 52, 38, 42), an always-check list of 4 "commonly missed" labels (27, 21, 19, 28), a generic direction heuristic, "prefer 4-8 high-evidence values". |
| `compact` | Removes `reasoning` entirely, "at most 6 values per actor", actor-specific-evidence gates, "omit if topic-level". |
| `compact_strict` | "At most 5", "prefer precision over recall", 3 concrete sibling-confusion gates (37 vs 42; 26 vs 27; 45 for authorities), "if direction uncertain, omit", victim/organization anti-shortcuts. |
| `targeted_more_shot` | compact + 5 abstract "situation → label + direction" calibration examples (22 aligned, 22 contradictory, 27 aligned, 27 contradictory, 19/20) + a **TARGETED RECOVERY CHECK** re-scan list of 6 labels: 22, 27, 26, 19, 20, 13. |
| `targeted_more_shot_strict` | targeted + per-label strictness gates for the same labels. |
| `targeted_more_shot_balanced` | **Liu's strongest variant.** targeted + per-label two-directional cue rules for 22 / 27 / 19-20 ("actor mitigates/protects/restores → aligned; actor causes harm/disruption/risk → contradictory"), sibling preference (26 over 27 for physical safety), "keep a weak target label only if in the actor's top 6". |

### 1.2 Few-shot selection
First 2 TRAIN articles (file order) with 2–3 actors and 4–8 gold labels. TRAIN-only ✅,
but: demo content truncated to 1500 chars, **only the first 4 gold outputs shown**, gold
explanations truncated to 150 chars. Showing a truncated gold output teaches
under-prediction and mid-list stopping — a defect, not a feature.

### 1.3 DeepSeek call configuration
`deepseek-v4-flash`, temperature 0.1, `max_tokens=8000` (other providers 4000),
`response_format={"type":"json_object"}`, per-request `timeout=120`,
**no** `thinking: disabled` extra-body.

### 1.4 Parsing / normalization (permissive — defects, do not copy)
Markdown fence stripping; typographic-quote replacement; unwrapping `{"items": …}` /
`{"article_human_values": …}`; wrapping non-lists; silently discarding invalid actors/IDs;
**any direction other than `"contradictory"` (including absent) is silently coerced to
aligned**; all-retries-failed → **empty list, cached as if valid**.

### 1.5 Cache
Keyed only by filename (`mode_provider_model_variant_tempX_maxY`) + guid. No prompt hash,
no article hash, no success flag; stale after any prompt edit unless `--refresh_cache`;
failures cached as empty predictions.

### 1.6 Majority vote
**Not present in the supplied files.** `label_aware_ensemble.py` only reads the *output
directory* of a run tagged `dev_deepseek_ensemble_majority_vote_full`; the script that
produced it was not supplied. The voting rule is unauditable.

### 1.7 `label_aware_ensemble.py`
Offline set arithmetic on prediction files: Task-1b = base run ∪ {target-run predictions
whose `direction:l1` key is in an add-list}; Task-1a = target run wholesale.
`DEFAULT_ADD_LABELS` = {0:0, 0:22, 0:27, 0:44, 0:48, 1:13, 1:22, 1:27, 1:35, 1:46} — the
docstring says these are labels where the target run "showed complementary recall",
i.e. **selected by scoring on the same 177 dev articles used for reporting**. TRAIN
frequencies of these labels: mostly frequent/medium (22 = 883, 26 = 1018, 27 = 1590,
44 = 460, 46 = 364, 13 = 389) with two very-rare (35 = 25, 48 = 28) — the list is not
derivable from train statistics; it is a dev-fit artifact.

### 1.8 What most plausibly explains Liu's reported gains
1. **Targeted recovery of broad, high-support labels (22/26/27)** — recall gained on the
   highest-frequency labels moves micro-F1 far more than rare-label work. The *mechanism*
   (behavioral cues + re-scan pass + two-directional cue rules) is sound; the *label list*
   is dev-derived.
2. **Dev-fitted add-list ensembling** (§1.7) — direct dev leakage; the reported number is
   partially fit to the reporting set.
3. **Compact output** (no reasoning field) — fewer JSON failures and less drift for Flash.
4. Everything else (fence stripping, quote fixing, provider plumbing) is engineering
   detail, partly harmful (silent aligned-coercion inflates DRR risk invisibly).

## 2. Liu `targeted_more_shot_balanced` vs Pipeline 3 Variant B

| Dimension | Liu targeted_balanced | Pipeline 3 Variant B (v3.0.0) | Verdict |
|---|---|---|---|
| Length | ~11.6k chars system prompt | ~22.1k chars | Liu shorter, but only because taxonomy definitions are absent |
| Taxonomy coverage | 54 label **names**, no definitions | 54 labels with full official descriptions | B stronger (classification against definitions, not name intuition) |
| Behavioral cues | Concrete two-directional cues for 5 dev-chosen labels | Taxonomy-derived cues for all 18 train-rare labels, single-directional | Liu's *two-directional cue pattern* is portable; his label list is not |
| Rare-label treatment | None (his targets are train-frequent) | Rare checklist from TRAIN counts | Different target sets; both legitimate hypotheses |
| Actor grounding | "actor-specific evidence" gates | Equivalent + no-evidence-transfer rule | Present in both |
| Label-count guidance | "at most 6", "top 6 most relevant" | No min/max (deliberate) | Liu's cap is a dev-calibrated precision knob; not ported (hides recall failures) |
| Few-shot | 2 TRAIN demos, truncated gold output (defect) | 2 TRAIN demos, full deduplicated gold, rare-label-prioritized, hygiene-checked, hashed provenance | B stronger |
| Direction guidance | Generic mitigate→aligned / harm→contradictory heuristic + per-label cue rules | Relevance-first-then-direction rule only | **Gap in B**: no generic direction cue block → ported |
| Sibling disambiguation | 3 concrete dev-chosen pairs | None in B (V2 had 11 sets) | **Gap in B**: generic same-L2-group specificity rule ported |
| Evidence threshold | "explicit or strongly implied", omit-if-uncertain | Same standard, stated once | Equivalent |
| Flash suitability | Compact, concrete, JSON-object examples | Compact contract, structured demos | Comparable |

## 3. Feature disposition

| Reference feature | Disposition | Rationale |
|---|---|---|
| Two-directional cue pattern ("protects/restores → 1; causes/blocks → 0") | **Adopted** (generic DIRECTION CUES block in Variant B, v3.1.0) | Taxonomy-neutral heuristic addressing DRR; not label-specific, no dev dependence |
| Sibling-specificity gate | **Adopted** (generic same-L2-group rule in Variant B) | Justified by the taxonomy's L2 grouping; Liu's concrete pairs were dev-chosen, the generalization is not |
| Per-request API timeout (120 s) | **Adopted** (`REQUEST_TIMEOUT_S` in `make_caller_v3`) | A hung request stalls the whole run; timeout converts it to a visible transient failure |
| Re-scan pass for easily-missed labels | **Already present** (Variant B Pass 2) | B's checklist is TRAIN-rarity-derived instead of dev-error-derived |
| TRAIN-only few-shot demonstrations | **Already present, stronger** | B's demos are untruncated, validated, hashed |
| Label-aware base+target combination | **Already present, stronger** | The frozen-policy calibrator learns per-(direction,l1) strategies from TRAIN with support/gain safeguards; strictly more expressive than a hand add-list |
| Per-stage output files for offline ensembling | **Already present** | Six stage outputs per run |
| `DEFAULT_ADD_LABELS` and the recovery list {22,27,26,19,20,13} as hard-coded targets | **Rejected — leakage** | Selected by inspecting dev gold/errors of the same 177 reporting articles. Kept as a *future experiment*: test whether TRAIN-only calibration independently rediscovers these labels |
| "3-7 values per actor" / "at most 6" / "top 6" caps | **Rejected — unsafe** | Dev-calibrated output-cardinality knob; silently suppresses recall and masks miscalibration |
| Actor-role "Common patterns" (police → 45 …) | **Rejected — unsafe** | Stereotype priors; the V2/V3 anti-shortcut policy exists specifically to remove these |
| Direction defaulting to aligned; failure → empty cached prediction; fence/quote repair; dict unwrapping | **Rejected — technically unsafe** | Hides failures, corrupts DRR accounting, uncacheable audit trail; violates Pipeline 3's strict-validation contract |
| Identity-free cache | **Rejected** | Pipeline 3's identity-bound cache supersedes it |
| `max_tokens=8000` for DeepSeek | **Not adopted** | Liu needed headroom for per-item `reasoning` strings; V3 forbids reasoning output, so worst-case output is < 2k tokens. A truncated response would fail JSON validation *visibly* and retry — no silent risk |
| No `thinking: disabled` extra-body | **Not adopted** | V2's Flash experience: disabling thinking avoids JSON-mode parse failures; keep |
| Majority voting | **Not applicable** | Implementation absent from the reference; undefined for two generators; V3's agreement + verifier rule replaces it |
| Abstract "situation → label" calibration examples (Ex. A–E) | **Future experiment** | Mechanism is portable, but writing them for *specific* labels requires a target list; must come from TRAIN calibration output, not dev errors. Revisit after the first `--mode calibrate` run |

## 4. Verifier check (task §6)

The V3 verifier user prompt already carries, per candidate: exact `actor_id` + actor
name, `l1_value_id` + official Level-1 name, the **full official descriptions**, and the
full article + actor list. It receives no proposed direction, no proposer identity, no
confidence, no gold/metric information, and the strict validator rejects any verdict
outside the candidate list. No change required; tests now pin the definition requirement.

## 5. Changes made to Pipeline 3 (v3.1.0)

1. `PROMPT_VERSION_V3` → `fehu_task1_prompt_v3.1.0` (invalidates all prior cache
   identities; no paid caches existed).
2. Variant B: added generic **DIRECTION CUES** block and same-L2-group
   **sibling-specificity rule** (§3). Variant A unchanged (no defect found).
3. `make_caller_v3`: explicit per-request timeout (120 s), recorded in the manifest.
4. New offline diagnostics (deterministic, computed after inference, never fed back into
   the same run): A/B exact-agreement rate, mean tuple Jaccard, pair direction-agreement
   rate, tuples/labels only-A / only-B, train-rare labels added by B, verifier acceptance
   split by candidate category (single_a / single_b / direction_conflict / partial),
   conflict direction decisions, final-output contribution by stage.
5. Tests: Liu files are data-only (no `src/` module references `liu_method`); no
   hard-coded add-label set exists in the pipeline; Variant B contains the ported blocks;
   checklist labels are all TRAIN-rare; verifier prompt carries official definitions;
   version bump invalidates cache identities; diagnostics deterministic.

Nothing here is claimed to improve FEHU scores until an authorized paid experiment
measures it.
