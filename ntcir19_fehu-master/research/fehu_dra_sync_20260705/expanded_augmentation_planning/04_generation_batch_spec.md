# Generation Batch Spec — Future DeepSeek V4 Pro Batches (DO NOT GENERATE IN THIS TASK)

**Created at:** 2026-07-04T21:42:51
**Generation model (future):** DeepSeek V4 Pro
**Design:** every batch is a direction-contrastive pair set; raw = 3× accepted target per label/direction;
all candidates go through: local structural validation → AI-assisted semantic verification → human
ACCEPT/REJECT → verified-pool update. `training_ready` stays false throughout.

**Global constraints for every batch (from the L1=12 replacement lessons):**
- Factual-news style, ≥6 sentences, one clearly named actor.
- `actor_mention` appears verbatim in content; `evidence_sentence` names the actor explicitly
  (never only "the company/团体/the group").
- The target value/direction must be the **dominant** narrative; no counter-signals
  (no awards/praise/recovery in contradictory samples; no failures/scandals in aligned samples).
- Direction codes follow `direction_mapping.json`: 1=aligned, 0=contradictory. Never inverted.
- One label per candidate; no Task-2 subevent labels.

---

## batch_01 — L1=22 "Have good health" (L2=8)
- **Raw:** 9 aligned + 9 contradictory → **accept 3 + 3**
- **Rationale:** largest zero-recall label (dev support 122, 50 aligned / 72 contradictory); both
  directions independently measurable.
- **Clean evidence patterns:** aligned — actor completes a rehabilitation program, adopts a verified
  health regimen, recovers fitness after treatment; contradictory — actor's documented substance abuse
  damages their health, actor ignores medical advice and is hospitalized, actor's overwork causes a
  diagnosed illness.
- **Ambiguity traps:** helping OTHERS' health (that is Be helpful, 37); public-safety framing (26);
  risk of illness without realized harm; policy debates about healthcare.
- **Validation focus:** evidence must concern the actor's OWN realized health state.

## batch_02 — L1=30 "Be compliant" (L2=11)
- **Raw:** 6 + 6 → **accept 2 + 2**
- **Rationale:** zero recall, balanced support (81; 44/37); clean rule-following semantics.
- **Clean evidence patterns:** aligned — actor implements a regulator's order fully and on schedule,
  actor follows court-mandated procedures; contradictory — actor operates without the required license,
  actor defies a direct regulatory order (realized violation, sanction issued).
- **Ambiguity traps:** politeness/propriety (32/33); irresponsibility (42); mere criticism of rules;
  planned-but-not-realized violations.
- **Validation focus:** an explicit rule/order/regulation must be named and followed/violated.

## batch_03 — L1=38 "Be honest" (L2=14)
- **Raw:** 6 + 6 → **accept 2 + 2** (pool density 2 → 6)
- **Rationale:** existing complete pair; direction-consistency continuity; balanced support (72; 44/28).
- **Clean evidence patterns:** aligned — proactive disclosure, voluntary correction of the record,
  transparent reporting beyond obligation; contradictory — admitted fabrication of data, documented
  lying to investigators.
- **Ambiguity traps:** failure (12), irresponsibility (42), rule-breaking (30) mislabeled as dishonesty;
  accusations without established falsehood.
- **Validation focus:** truthfulness/deception must be the core act, not a side effect.

## batch_04 — L1=12 "Have success" (L2=4)
- **Raw:** 6 + 6 → **accept 2 + 2** (pool density 2 → 6)
- **Rationale:** existing complete pair; thesis continuity. **Caveat:** contradictory dev support is
  only 7 → low evaluation power for that direction; keep aligned-side expectations primary.
- **Clean evidence patterns:** aligned — actor wins a named competition/contract, hits a stated target
  ahead of schedule, certified record; contradictory — actor cancels a flagship program after missing
  promised targets, loses a decisive bid, delivers a small fraction of a promised rollout.
- **Ambiguity traps:** success-dominant articles with one setback (the rejected-Oakridge pattern);
  dishonesty/capability/reputation framings; risk or delay without realized failure.
- **Validation focus:** dominant realized success/failure against a stated goal.

## batch_05 — L1=5 "Have freedom of action" (L2=1)
- **Raw:** 6 + 6 → **accept 2 + 2**
- **Rationale:** zero recall, balanced support (72; 30/42).
- **Clean evidence patterns:** aligned — court restores an actor's right to operate/travel/assemble;
  authority lifts restrictions on the actor's activities; contradictory — actor is banned from its
  core activity, movement/operations legally blocked, forced shutdown of the actor's operations.
- **Ambiguity traps:** freedom of thought/speech (2); privacy (6); compliance framing (30) when a ban
  is obeyed; abstract liberty rhetoric without a concrete action restriction.
- **Validation focus:** a concrete ability to ACT must be granted/restored vs removed/blocked.

## batch_06 — L1=46 "Have a world at peace" (L2=16)
- **Raw:** 3 + 3 → **accept 1 + 1**
- **Rationale:** zero recall, balanced (48; 22/26); very clean news semantics.
- **Clean evidence patterns:** aligned — actor signs/brokers a ceasefire, demobilizes forces,
  funds verified de-escalation; contradictory — actor launches an offensive, breaks a ceasefire,
  escalates armed conflict.
- **Ambiguity traps:** national security (26) and social stability (27) head labels; peace RHETORIC
  without action; humanitarian aid (37).
- **Validation focus:** the actor's own act must create or destroy peace, not merely comment on it.

---

## Totals
| | aligned | contradictory | total |
|---|---|---|---|
| **Raw to generate** | 36 | 36 | **72** |
| **Accepted target** | 12 | 12 | **24** |
| **Resulting pool** | | | **30 verified** (6 existing + 24 new) |

If acceptance falls short in a batch, regenerate that batch with tightened constraints — do not lower
the acceptance bar and do not backfill from off-target labels.
