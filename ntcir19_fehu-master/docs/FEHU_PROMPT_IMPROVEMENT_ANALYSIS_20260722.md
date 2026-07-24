# FEHU Prompt-Focused Improvement Analysis

**Date:** 2026-07-22
**Inputs:** Prof. Yu's NEVU paper (`2603.17838v1.pdf` — Wang et al., *Event-Centric Human Value Understanding in News-Domain Texts*, read in full), the handoff summary (`FEHU_Master_Research_Handoff_Phase0_to_Phase3_20260722.md`, cross-checked against the Phase-0–3 artifacts and found consistent), the repository, and prior validation results.
**Status:** analysis only. No code modified, no experiments run, no detailed multi-stage plan — a ranked catalog of optimization ideas for discussion. Nothing below is implemented until explicitly approved.

---

## 1. Why the current prompt method has likely reached its limit

Our strongest single prompt system is Liu's frozen `targeted_more_shot_balanced` on DeepSeek Flash (1b micro 0.5347, macro 0.3385, DRR 0.023, 88 classes). Five concrete, evidence-backed ceilings:

1. **The prompt teaches under-prediction.** The few-shot demonstrations truncate gold outputs to the **first 4 labels** (`liu_method/run_pipeline.py:253`) and demo articles to 500 chars (line 257), while real actors average ~5.2 directed labels and articles ~13. Micro-recall 0.505 with 397 Liu-only-missed gold labels vs. 701 missed by everything (`…hybrid…/19_complementarity_analysis.csv`) is consistent with a learned output-length prior, not a knowledge limit.
2. **Evidence is discarded for long articles.** Inputs >9,000 chars are cut to the first 6,000 + last 3,000 (`run_pipeline.py:306`); mid-article evidence is invisible. NEVU's controlled grouping test shows exactly this kind of context structuring is worth **+13–19 pp recall** when done right (Fig. 8).
3. **One call must label all actors at once.** All our pipelines (V1–V3, Liu) prompt per *article*; NEVU's protocol conditions each judgment on a **(unit, actor)** pair with dedicated `evidence` and `context` fields (Eq. 5). Our single-completion format dilutes attention across ~2.6 actors and 100+ candidate labels, which plausibly caps both tail recall and precision.
4. **Single-pass, single-model decoding.** Everything runs one pass at temperature 0.1. NEVU's annotation pipeline needed **3-way multi-LLM voting plus a QA verification stage** to reach acceptable label quality — strong evidence that one greedy pass sits well below the recall/precision frontier reachable from the same base model.
5. **Verification is coarse.** V3's verifier and the hybrid's review are *bulk* calls (all uncertain items in one completion) that trade F1 for precision (V3: verified 0.4455 < variant-B 0.4628). NEVU verifies **each candidate individually** with the value definition and grounded evidence (QA style, App. E.2) — a finer instrument than ours.

Independent context: on NEVU's own benchmark, *no* prompting configuration of any proprietary model beats lightweight LoRA fine-tuning of an 8B open model (best prompting 47.05 micro vs. LoRA 55.26; macro 39.87 vs. 44.29; DRR 1.09 vs. 0.01–0.03 on composite units, Table 4). Numbers are not directly comparable to FEHU dev, but the *pattern* — prompting plateaus where supervised adaptation keeps going, especially on macro and direction — matches what we observe locally.

## 2. What NEVU offers as inspiration (not to copy)

- **Prompt side:** actor-conditioned `(unit_text, evidence, context, actor)` input decomposition; subevent/composite-unit prediction with **direction-specific union merging** (their map–reduce, Eq. 7); multi-model 3-way voting for precision; **per-candidate QA verification** ("does actor *a* demonstrate value *v* in direction *d* in unit *u*? Yes/No + 1–2 sentence justification", with the value definition supplied); explicit failure modes to counter in instructions — *role-prior bias* (direction flipped toward the actor's stereotypical role) and *value granularity confusion* (spillover into adjacent values, their case study §6.5).
- **LoRA side:** LoRA on 8B instruction models with the same JSON output schema lifts macro dramatically (e.g., Qwen3-8B 9.35 → 42.42) and crushes direction errors (DRR ≈ 0.01–0.03 on composite units). The transferable insight for us is *not* their implementation but the target: **a generative, schema-constrained student learns direction jointly with values far better than our 108-way sigmoid DeBERTa head** (our student's DRR is 0.22–0.29 — its single worst property).
- **Directly exploitable local fact:** all **177 dev articles already contain subevents (median 9)** in `dev_event_base.json` — NEVU-style unit decomposition needs no new segmentation machinery.

## 3. Idea catalog

### Prompt-based (primary focus)

**P1 — Repair the few-shot demonstrations ("full-label demos").**
*Core:* rebuild Liu-style few-shot examples without the `[:4]` output cap, with direction-balanced demos showing realistic label counts, and without the 500-char demo truncation. *Why:* removes a demonstrated under-prediction prior on our strongest system. *Differs from now:* pure prompt-content fix on the frozen winner; no pipeline change. *Expected benefit:* micro/macro **recall** (+ several points plausible), tail recall; small precision risk. *Difficulty:* very low (one new run). *Risk:* longer demos eat context; over-prediction if pushed too far. *Worth testing:* **yes, first.*

**P2 — Subevent-decomposed prompting with direction-specific union ("unit → union").**
*Core:* prompt per subevent-group (or per subevent block within one call), predict per-actor directed values per unit, take the direction-specific union as the article-level Task-1b prediction; optionally a light dedup/verify pass after the union. *Why:* NEVU's strongest structural finding — grouped local context beats whole-article judgment by +13–19 pp recall; also neutralizes our long-article truncation issue. *Differs from now:* all current pipelines are article-level single-shot; V3's "union" was across *prompt variants*, not *text units*. *Expected benefit:* micro/macro recall and **long-tail recall** (tail values often live in one subevent); macro-F1. *Difficulty:* medium (prompt + aggregation code; ~2–9× calls or chunked single calls). *Risk:* FP accumulation across units (NEVU saw −3 to −7 pp precision on loose groupings) — needs the union to feed a verifier; cost multiplier. *Worth testing:* **yes.**

**P3 — Per-candidate QA verification (CLAVE/NEVU-style) replacing bulk verification.**
*Core:* for each candidate `(actor, l1, direction)` from any recall source (P1/P2 union, DeBERTa/N3 candidates), one small binary judgment with the official value definition, our confusion notes, and quoted evidence; batched, cacheable. *Why:* our bulk verifier loses recall while filtering; NEVU found per-candidate QA reliable enough to *annotate a benchmark*; it also gives auditable per-label rationales. *Differs from now:* granularity (per-candidate vs. per-article bulk), and definitions+evidence are mandatory context. *Expected benefit:* **micro precision** at much lower recall cost; better macro-precision; direction check included → DRR. *Difficulty:* medium (new verifier prompt + caching; cost scales with candidate count — the hybrid produced 4,251 reviews, so batching ~10 candidates/call keeps it ~430 calls). *Risk:* per-candidate judgments lose cross-label context (inflation control may weaken); cost. *Worth testing:* **yes** (as the shared verification layer for P1/P2/H1).

**P4 — Self-consistency / heterogeneous-model voting.**
*Core:* k=3 samples (temp ≈0.7) or 2–3 models (Flash + Pro) on the same prompt; union → P3 verification for the recall arm, ≥2-way agreement for a precision arm. *Why:* NEVU needed 3-way voting for quality; our own V3 showed union > any single stage on recall (0.472 recall at union); single greedy decoding is leaving variance on the table. *Differs from now:* V3's two *prompt variants* on one model, one pass each; this samples the *decoder* and/or *model*. *Expected benefit:* macro/tail recall (union arm), micro precision (agreement arm). *Difficulty:* low-medium (rerun machinery exists; ×k cost). *Risk:* pure cost; union without verification degrades precision (proven by the hybrid's raw-union ablation, 0.3859). *Worth testing:* yes, after P1/P3.

**P5 — Anti-inflation and anti-role-prior instructions.**
*Core:* add NEVU's two documented failure modes as explicit negative instructions with 1–2 contrastive mini-examples: (a) "do not add adjacent/generic values not directly evidenced" (granularity control), (b) "judge direction from described behavior, not from the actor's typical role" + require a quoted evidence span per label. *Why:* matches Liu's error profile (precision 0.568; reversals concentrated in role-laden classes); our confusion notes exist but are used only in the hybrid review, never in the primary generation prompt. *Differs from now:* content-level addition, no structural change. *Expected benefit:* micro/macro **precision**, DRR. *Difficulty:* very low. *Risk:* over-suppression of tail labels if worded too strongly. *Worth testing:* yes — bundled into P1's run.

**P6 — Targeted direction-QA pass for high-reversal classes.**
*Core:* after any pipeline, re-ask direction only (binary, evidence-quoting) for predictions in the ~10 classes carrying most reversals (from `20_direction_error_analysis.csv` / Phase-0 per-target reversal counts). *Why:* DRR is already low for LLMs (0.023) but reversals are concentrated; a cheap targeted pass could halve them. *Expected benefit:* **DRR** specifically; small micro gain. *Difficulty:* low (few dozen calls). *Risk:* flip-flopping correct directions. *Worth testing:* optional add-on; only if DRR matters for ranking.

### Hybrid (secondary)

**H1 — Hybrid v2.1: new candidates + per-candidate verification + replication.**
*Core:* keep the H2/H3 architecture but (i) swap candidate source to N3 checkpoints (direction-aware target recall 0.59) or F′-seed-44, at threshold ~0.10–0.20; (ii) replace the bulk review with P3's QA verifier; (iii) run ×3 passes with bootstrap CIs. *Why:* verification is proven load-bearing (0.547 vs. 0.406); the old hybrid used the weaker v2 candidates and an unreplicated single pass; N3 exists precisely to feed this. *Expected benefit:* macro & tail recall at held precision — the most credible route to clearly beating Liu on *both* micro and macro; also converts the headline claim into a CI-backed one. *Difficulty:* medium (mostly reuse; ~3×177 calls + verification). *Risk:* N3's ~2–4% candidate precision loads the verifier (mitigate with a probability floor and per-class caps). *Worth testing:* **yes — highest-value hybrid move.**

**H2 — Targeted rescue injection.**
*Core:* inject DeBERTa/N3 candidates only for classes where Liu's recall is historically ≈0 (~30 classes incl. the 18 targets), leaving Liu untouched elsewhere. *Why:* H2/H3 showed additions help targets but add FPs broadly; restricting injection to Liu's blind spots concentrates benefit. *Expected benefit:* macro/tail with minimal micro risk. *Difficulty:* low on top of H1. *Risk:* class list is dev-derived (leakage flag — freeze from train-side diagnosis instead). *Worth testing:* yes, as an H1 ablation arm.

### LoRA-inspired (bounded scope, secondary)

**L1 — Generative 8B QLoRA student with schema-constrained JSON output.**
*Core:* fine-tune an open 8B instruction model (e.g., Qwen3-8B class) with QLoRA on FEHU train (actor-conditioned prompt → `{aligned_hvs:[], contra_hvs:[]}`), as a *replacement student/candidate source* — our own data, article/subevent level, our schema; inspired by NEVU's G2→G3 pattern, not a port of it. *Why:* our DeBERTa student's fatal weaknesses are direction (DRR 0.22–0.29) and macro; NEVU shows precisely these two collapse under generative LoRA (DRR → ~0.01–0.03, macro ×3–4 vs. prompting the same backbone). A student with near-LLM direction quality would let the hybrid drop direction-neutralization entirely. *Differs from now:* generative token-level supervision vs. 108-way sigmoid head; direction learned jointly; no threshold problem (set-valued decoding). *Expected benefit:* potentially the largest single jump — macro, tail recall, and DRR simultaneously; a much stronger hybrid candidate source. *Difficulty:* medium-high but realistic on the RTX 4090 with 4-bit QLoRA (days incl. debugging; masked/partial supervision of synthetic records needs a token-level analogue — e.g., train target-only records with target-restricted output). *Risk:* VRAM/throughput; inference slower than DeBERTa; NEVU trained on ~62k directed instances vs. our 16.9k — transfer of the gain magnitude is unverified; seed variance unknown. *Worth testing:* **yes, as the parallel high-upside bet** — but after P1/P3/H1, per the prompt-first instruction.

## 4. Metric-impact mapping

| Idea | micro-P | micro-R/F1 | macro-P | macro-R/F1 | tail recall | DRR | Days |
|---|---|---|---|---|---|---|---|
| P1 full-label demos (+P5 bundled) | ± | **++** | + | **++** | + | ± | 0.5–1 |
| P2 subevent union (→P3) | − alone / ± with P3 | **++** | ± | **++** | **++** | ± | 1–2 |
| P3 QA verification | **++** | − small | **++** | + | ± | + | 1–2 |
| P4 self-consistency/voting | + (agree) | + (union) | + | + | + | ± | 1 |
| P6 direction-QA | ± | ± | ± | ± | — | **++** | 0.5 |
| H1 hybrid v2.1 (N3 + P3 + ×3) | + | + | + | **++** | **++** | + | 2 |
| H2 targeted rescue | **+** | ± | + | + | + | ± | +0.5 |
| L1 8B QLoRA student | + | + | **++** | **++** | **++** | **++** | 3–5 |

All of P1–P6, H1–H2 are testable within a few days each on the dev set (API cost: one full dev pass ≈ 177–531 calls at Flash prices; ×3 replication where claims are made). L1 is a few days of local GPU work with no API cost.

## 5. Ranking and recommendation

By expected value = (evidence behind the mechanism) × (expected metric gain) × (feasibility) ÷ (risk):

1. **P1 + P5 — repair the few-shot demos and add anti-inflation/anti-role-prior instructions.** Trivial cost, acts directly on the strongest system's *documented* self-inflicted caps, touches recall (our binding constraint vs. Liu's precision-recall balance). The cheapest information about how much headroom prompting still has.
2. **H1 — hybrid v2.1** (N3/F′ candidates + per-candidate QA verification + ×3 replication). The only route with a *proven* load-bearing mechanism on our own data, upgraded on its two known weak points; also converts the thesis headline into a replicated, CI-backed claim.
3. **P2 — subevent-decomposed prompting with union.** The strongest literature-backed recall lever (+13–19 pp in NEVU's controlled test), free unit structure already in our dev data; needs P3 as its precision backstop.
4. **L1 — 8B QLoRA generative student.** Largest potential single jump (macro + DRR together), directly inspired by the paper's central empirical result; slightly out of the "prompt-first" lane, so run it as the parallel bet once 1–3 are underway.
5. **P4 / P6 / H2** — cheap add-ons; fold into the above rather than test standalone.

**Recommended for discussion/approval: ideas 1–3 (P1+P5, H1, P2), with L1 pre-approved in principle as the parallel experiment.** I suggest we *not* pursue standalone P4/P6/H2 until the top three have results, and defer everything else in §3 accordingly.

*No implementation has been started; awaiting your review and explicit go-ahead.*
