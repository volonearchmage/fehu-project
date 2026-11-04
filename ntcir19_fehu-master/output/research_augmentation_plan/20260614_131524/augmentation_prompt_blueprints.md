# FEHU Augmentation Prompt Blueprints (planning stage)

These are **templates only**. No prompt below has been executed.
Direction encoding follows `direction_mapping.json`: `"1"` = aligned, `"0"` = contradictory.

---

## 1. Label-preserving paraphrase

### System
You are a careful news-style rewriter. You will be given a news article, a single actor mentioned in it, and a human value with a direction. Your job is to rewrite the article so the actor and the same value/direction relationship remain clearly expressed, but the surface wording, sentence order, and incidental details change. Do NOT change the actor identity. Do NOT change the value or direction. Do NOT introduce a new value relationship.

### User
```
Original title: {title}
Original article: {content}
Actor of interest: {actor_name} (ID: {actor_id})
L1 value to preserve: {l1_value_id} ({l1_value_name})
Direction to preserve: {direction_name}  ({direction})
Evidence sentence from the original: {explanation}

Rewrite the article (≤ 1500 chars) while preserving the actor and the value/direction relationship. Output JSON only.
```

### Expected JSON
```json
{
  "title":          "...",
  "content":        "...",
  "actor_name":     "...",
  "evidence_sentence": "...",
  "explanation":    "<one sentence why the new content expresses the same value+direction>"
}
```

### Rejection rules (verifier)
- actor_name missing from new content
- evidence_sentence absent from content
- value clearly drifted to a different L1
- direction inverted
- length < 50 chars or > 8000 chars

### Quality checklist
1. The actor's behaviour is the *subject* of the evidence sentence.
2. The new content avoids verbatim copying of the original (no >50 % token overlap).
3. The new content is plausibly news-like (not first-person narrative).

---

## 2. Rare-positive generation

### System
You are a synthetic news writer for a research benchmark. Given an L1 human value, a direction, and an actor archetype, write a short, news-style article in which the named actor's behaviour clearly expresses (or contradicts, depending on direction) the value. Keep the article ≤ 1500 chars. Use a concrete factual style; avoid first-person narration; avoid editorial commentary.

### User
```
L1 value: {l1_value_id} ({l1_value_name})
L2 category: {l2_value_id} ({l2_value_name})
Direction: {direction_name} ({direction})
Actor archetype: {actor_archetype}   (e.g. "city council member", "humanitarian NGO", "tech CEO")
Suggested actor name: {suggested_actor_name}
Definition / what this value means: {value_definition}
Optional related training seed (for style only, do not copy): {optional_seed_excerpt}
Generate a short news-style article. Output JSON only.
```

### Expected JSON
```json
{
  "title":          "...",
  "content":        "...",
  "actor_name":     "...",
  "evidence_sentence": "<verbatim sentence from content that demonstrates the value>",
  "explanation":    "..."
}
```

### Rejection rules (verifier)
- actor_name not in content
- value not actually expressed
- direction inverted
- content references real, identifiable individuals or organisations in defamatory contexts
- content too short or too long

### Quality checklist
1. The article reports an *action* by the actor, not just an opinion.
2. The direction is unambiguous (no reader would flip it).
3. The value is the *primary* one expressed by the action.

---

## 3. Hard-negative generation

### System
You are creating a near-miss training example. The actor's behaviour will be related to the target topic but should NOT be labelled with the target L1 value. A different, related value is the real label.

### User
```
Target L1 value (do NOT predict for this actor): {target_l1_id} ({target_l1_name})
Actually-correct L1 value (this IS expressed): {alternative_l1_id} ({alternative_l1_name})
Direction (for the alternative value): {direction_name} ({direction})
Suggested actor name: {suggested_actor_name}
Suggested topic: {topic_hint}
Write a short news-style article where the actor expresses the alternative value, but a careless reader might assume the target value applies. Output JSON only.
```

### Expected JSON
```json
{
  "title":          "...",
  "content":        "...",
  "actor_name":     "...",
  "evidence_sentence": "<sentence supporting the alternative L1 value>",
  "explanation":    "<why the target L1 value does NOT apply here>"
}
```

### Rejection rules (verifier)
- Article actually expresses the target value too (would be a positive)
- Article expresses neither the target nor the alternative value
- Direction inverted

### Quality checklist
1. The "near miss" is plausible — a naive model would over-predict the target.
2. The alternative value's evidence is concrete.
3. The article does NOT contain any statement that clearly expresses the target value.

---

## 4. Direction-contrastive pair

### System
You will write a PAIR of short news-style articles for the same L1 human value. The two articles must share topic and rough length, but one must clearly express the value in the **aligned** direction and the other in the **contradictory** direction. Use different actors for the two articles so the direction is the discriminating signal, not the actor name.

### User
```
L1 value: {l1_value_id} ({l1_value_name})
Topic hint: {topic_hint}   (e.g. "court ruling on freedom of assembly")
Actor A name: {actor_a_name}     (aligned)
Actor B name: {actor_b_name}     (contradictory)
Output a JSON object with two fields: "aligned" and "contradictory", each containing {title, content, actor_name, evidence_sentence, explanation}.
```

### Expected JSON
```json
{
  "aligned":       { "title":"...", "content":"...", "actor_name":"...", "evidence_sentence":"...", "explanation":"..." },
  "contradictory": { "title":"...", "content":"...", "actor_name":"...", "evidence_sentence":"...", "explanation":"..." }
}
```

### Rejection rules (verifier)
- Pair differs only in surface direction words (e.g. swapping "supports" ↔ "violates")
- Actor names identical
- Topics differ entirely (defeats the contrastive design)

### Quality checklist
1. The aligned article shows the actor *acting in support* of the value.
2. The contradictory article shows the actor *acting against* the value.
3. Both articles are plausible news; neither is a thought-experiment.

---

## 5. Teacher verification prompt

### System
You are an expert annotator for the FEHU benchmark. Decide whether the given synthetic sample is well-formed enough to enter the training pool. Be strict.

### User
```
Sample (JSON):
{sample}

Target label: {l1_value_id} ({l1_value_name}), direction = {direction_name}
Augmentation type: {augmentation_type}

Reject if:
- The actor named in sample.actor_name does not appear in sample.content.
- The evidence_sentence does not support the labelled L1 value with the labelled direction.
- The direction is ambiguous (could be flipped without changing the text much).
- The content also expresses a different value for the same actor with equal weight.
- The content contains real-world defamation, slurs, or PII.

Return JSON:
{
  "verdict": "accept" | "reject" | "needs_human_review",
  "reason":  "<one-sentence justification>"
}
```

### Quality checklist
1. Reject if the actor is unnamed or generic ("a man", "officials").
2. Reject if the article reads like an opinion piece rather than news.
3. Accept only when the value-direction relationship is unambiguous.
