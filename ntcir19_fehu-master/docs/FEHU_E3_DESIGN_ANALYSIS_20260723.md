# E3 Design Analysis — After E1 (retained) and E2 (rejected)

**Date:** 2026-07-23
**Inputs:** `RH_test/E1_fewshot_repair/reports/E1_REPORT.md` (run `20260722_152456`), `RH_test/E2_prompt_bias_control/reports/E2_REPORT.md` (run `20260723_000019`), `docs/FEHU_PROMPT_IMPROVEMENT_ANALYSIS_20260722.md` (ideas P2/P3/P6).
**Status:** design analysis only — no code, no runs.

## 1. The question

Should E3 return to E1 as the base, add subevent decomposition to improve recall, and avoid adding stricter generation constraints? **Yes.** The E1+E2 pair is close to a controlled experiment on exactly this question, and both halves point the same way.

## 2. Why E2 lost too much recall

E2 changed nothing except adding precision-leaning *instructions* on top of E1 (evidence test, exact-definition discrimination, no semantic expansion, direction-from-behavior, victim rule). The result (1b): FP −124 but TP −103, micro-F1 −0.018, macro-F1 −0.045, and E2 even fell below the original Liu baseline.

Three mechanisms explain the loss:

1. **Instruction gates are indiscriminate.** A prompt-level rule like "only output values with explicit evidence" is applied by the model at generation time, where it cannot reliably distinguish *weakly-evidenced-but-correct* labels from spurious ones. It trades TPs for FPs at roughly a 1:1.2 ratio (103:124) — far too expensive when the system is recall-limited (E1 macro-recall 0.392 vs. macro-precision 0.416; the tail classes are the binding constraint on macro-F1).
2. **The suppression concentrated exactly where E1's gain lived.** E1's headline win was macro (+0.033), from freeing less-frequent labels the old 4-label demos had capped. E2's rules removed disproportionately those same tail labels: macro-recall −0.062, 3 fewer distinct classes, non-target-90 macro −0.05. Stricter evidence requirements hit rare values hardest because their evidence is inherently thinner.
3. **The direction instructions were inert.** DRR 0.0347 → 0.0351, reversals 77 → 78. Telling the model to "judge direction from behavior, not role" produced no measurable effect — direction errors are apparently not correctable by generic in-prompt exhortation. (This also means E3 should not spend prompt budget on direction wording; the direction patch belongs in a targeted post-hoc stage, idea P6.)

The general lesson, now confirmed empirically in this project: **generation should be recall-oriented; precision should be recovered by a separate stage that sees one candidate at a time.**

## 3. Should E3 preserve E1's higher-recall prompt?

Yes, byte-for-byte where possible. E1 is the best single-system dev result (1b micro 0.5480 / macro 0.3719, beating hybrid H3's micro), its gain (+0.0133 micro) is ~3× the documented ±0.004 run variance, and E2 showed that every softening of its recall posture costs more than it returns. E3 should treat the E1 prompt (few-shot demos `0-4349-1-t` / `0-4352-3-1`, full gold label sets, no numeric caps, no truncation) as a frozen base and change **only the unit of prediction** — one variable, same discipline as E1→E2.

Do **not** carry over any E2 wording. E2's B1/B2 blocks are rejected wholesale; there is no salvageable subset worth the confound.

## 4. Adding subevent decomposition without excessive false positives

The recall logic (idea P2, NEVU-style): tail values often live in a single subevent and get diluted in whole-article judgment; per-unit prediction with a **direction-specific union** recovers them (+13–19 pp recall in NEVU's controlled comparison). All 177 dev articles already carry subevents (median 9), so no segmentation machinery is needed.

The FP risk is real (NEVU saw −3 to −7 pp precision on loose groupings; union across units can only add labels, never remove them). But the controls should be **structural, not instructional**:

- **Locality is itself an evidence gate.** Requiring that the actor's value be grounded in the specific subevent under consideration is a *context restriction*, not a "be conservative" instruction. The model sees less text per judgment, so free-associated labels have less surface to attach to. This is the acceptable kind of strictness — it constrains the input, not the output disposition.
- **Deterministic union in code, not in the model.** Parse per-unit outputs and take the union over `(actor, l1_value, direction)` in the aggregation script. Never ask the model to self-merge — that reintroduces the compression that caused under-prediction in the first place, and code-side union is auditable.
- **Log unit-support counts as free metadata.** A label predicted in 4 of 9 subevents vs. 1 of 9 is a confidence signal that costs nothing to record and gives the later verification stage (and error analysis) a ranked FP-pruning order. Do **not** turn it into a hard threshold inside E3 (e.g., "keep only if ≥2 units") — that is E2's mistake in structural clothing; measure first.
- **Keep both directions when units disagree.** The evaluator's Task-1b encoding (`direction:l1`) treats directions as distinct labels and gold can contain both; the direction-specific union matches this. No conflict resolution inside E3.

Accept up front that E3's raw output will have **lower precision than E1**. That is by design: E3 is the candidate *generator*; its success criterion is recall/macro gain at tolerable precision cost, exactly as E1's was.

## 5. Verification: separate stage, not a tighter prompt

Yes — this is now the clearest structural conclusion from E1+E2. The per-candidate QA verifier (idea P3: "does actor *a* demonstrate value *v* in direction *d* in unit *u*? Yes/No + justification, value definition supplied") differs from E2's approach in the ways that matter:

- It is **asymmetric**: it can only remove candidates, so the generator's recall ceiling is untouched; the recall floor is then set by the verifier's per-candidate accuracy on true labels — a measurable, tunable quantity, unlike a prompt gate's diffuse suppression.
- It judges **one candidate with the value definition in view**, a far easier discrimination task than generating under a global "be strict" field.
- It composes with E3's metadata: verify low-support candidates first/hardest, wave through high-support ones if cost matters.

But the verifier should be a **separate experiment (E4)**, not bundled into E3. Bundling would make E3's effect unattributable (the exact confound the critical review flagged for v1→v2) and would hide the number we most need: how much precision the union actually costs, which determines how much verification is even needed.

## 6. Recommended E3 design (simplest practical form)

**E3 = frozen E1 prompt + per-subevent prediction + deterministic direction-specific union. Nothing else.**

1. **Base:** generate the pipeline from E1's via a `build_e3_pipeline.py` with assert-once deltas (same auditable pattern as E1/E2). No wording changes to guidelines, demos, or calibration text; no bias-control content.
2. **Unit of prediction — one call per article, per-subevent structured output (chunked map):** the user prompt lists the article (full content, as E1) followed by its enumerated subevents; the model outputs a JSON object keyed by subevent id, each holding the E1-format compact records for that unit, judging each subevent's actors on that subevent's events. One call per article keeps cost at ~1× E1 (~177 Flash calls), avoids 9× context duplication, and stays inside the existing retry/cache/JSON-mode machinery. The compact 3-field format at median 9 units fits comfortably in max_tokens 8000.
   - *Fallback if the chunked form underperforms:* true multi-call map–reduce (one call per subevent, article as context) as E3b — closer to NEVU's setup, ~9× cost, only worth it if E3a's per-unit judgments look contaminated by whole-article context.
3. **Aggregation in code:** union over `(actor, l1_value, direction)` for Task-1b; project through `level_1_to_level_2.json` and dedup for Task-1a (same as the existing dedup path). Record per-label unit-support counts in the run artifacts.
4. **Few-shot demos:** render the two E1 demo articles in the same per-subevent output format (their subevents and gold labels exist in train). This is the one genuinely new prompt surface — keep it mechanical: same articles, same complete gold label sets, just grouped by the subevent each label's evidence sits in (or, if gold-to-subevent assignment is ambiguous, attach each label to every subevent that supports it — union makes duplicates harmless).
5. **Evaluation:** official evaluator, dev 177, compared against frozen Liu **and** E1 in one table (the E2 report's three-way format). Success criterion: micro/macro recall up vs. E1 with F1 at worst flat; precision drop is expected and is E4's job. Also report DRR and target-18/non-target-90 splits, and unit-support histograms for the FP analysis that will shape E4.
6. **Out of scope for E3:** verification (E4), direction-QA (P6), any replication-of-E1 runs — though the standing ×3 replication caveat applies to whichever configuration wins.

This is the minimal design that tests the one remaining high-upside prompt-side lever (P2) while preserving everything E1 proved and avoiding everything E2 disproved.
