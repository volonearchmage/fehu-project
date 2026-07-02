# Review and Reject Notes
**Audit Date:** 2026-06-26  
**Source:** 03_semantic_judgments.jsonl and 04_semantic_verification_table.csv

---

## Summary Counts

| Verdict | Count |
|---------|-------|
| ACCEPT_SUGGESTED | 3 |
| REVIEW_SUGGESTED | 3 |
| REJECT_SUGGESTED | 0 |

No candidates are currently suggested for rejection. All three REVIEW candidates have specific, resolvable concerns that a human reviewer can adjudicate.

---

## Candidates Requiring Human Review

### 1. prev_rare_positive_32_001_83df110175
**L1:** 32 "Be behaving properly" | **Direction:** 1 (aligned)  
**Original status:** WARN

**Why not ACCEPT_SUGGESTED:**  
The evidence sentence uses "The group" rather than naming the actor "Climate Change Activists and Supporters". This is the sole concern. Structurally, value alignment, direction, and content quality are all strong. The evidence sentence fully supports the label; only the actor naming convention falls short of ideal.

**Human review question:**  
> Is "The group submitted a detailed route plan in advance, designated marshals to ensure crowd compliance with traffic laws, and cleared the area by the agreed time." — with "The group" understood as the actor — sufficient for training quality?

**Expected outcome:** High likelihood of upgrading to ACCEPT after human confirmation. The semantic content is strong.

---

### 2. prev_dir_contrast_38_003_contradictory_e969e14138
**L1:** 38 "Be honest" | **Direction:** 0 (contradictory)  
**Original status:** WARN

**Why not ACCEPT_SUGGESTED:**  
Two concerns:
1. Evidence sentence uses "The company" rather than "BrightPath Analytics".
2. The article is only 4 sentences long. While the value-direction alignment is correct and unambiguous (fabricating data violates honesty), a 4-sentence article may not provide sufficient contextual signal for a model to learn rich actor-value associations.

**Human review question:**  
> (a) Is "The company admitted to fabricating client performance data during a regulatory review." — with "The company" understood as BrightPath Analytics — adequate for training?  
> (b) Is a 4-sentence article rich enough to produce a useful training example, or should we request a more detailed regeneration?

**Expected outcome:** If content length is acceptable, this is likely upgradable to ACCEPT. If the human reviewer judges the content too sparse, REJECT and add to a re-request list for a richer article.

---

### 3. prev_dir_contrast_12_002_contradictory_ce1da19f54
**L1:** 12 "Have success" | **Direction:** 0 (contradictory)  
**Original status:** WARN

**Why not ACCEPT_SUGGESTED:**  
This is the most complex REVIEW case. Three concurrent concerns:

1. Evidence sentence uses "The team" rather than "Oakridge High School".

2. **Mixed framing / direction ambiguity.** The article contains explicit success signals alongside the championship loss:  
   - "22–6 record, the best in a decade"  
   - "Senior point guard Jordan Lee scored 24 points, earning tournament MVP honors"  
   - "Several players received college scholarship offers after the game"  
   - "the season was widely viewed as a turning point for the program"  
   
   The direction label direction=0 is based on one fact (losing the championship game), while the bulk of the article narrates a successful season. This creates training risk: a model could learn to associate "best record in a decade" and "MVP" with direction=0.

3. **High training risk** (training_risk=0 in the score table). This is the only candidate with a non-trivial training risk score.

**Human review question:**  
> If a human annotator read this article about Oakridge High School without knowing the label, would they more naturally label the team as:  
> (a) direction=0: failing to have success (because they lost the championship)  
> (b) direction=1: having success (because of the outstanding season record and awards)  
> 
> If the answer is (b), this candidate should be REJECTED and replaced with an article where failure is the dominant, unambiguous narrative. A better contradictory example for "Have success" would be an article where the actor fails clearly and completely, without surrounding positive achievements.

**Expected outcome:** This is the candidate most likely to be REJECTED. The ambiguous direction framing is a meaningful training quality concern. If rejected, the direction_contrastive pair for L1=12 would have only the aligned member (candidate 2) and would need a cleaner contradictory replacement.

---

## Special Analysis: The 3 WARN Candidates — Evidence_mentions_actor

All three WARN candidates (1, 3, 5) triggered the `evidence_mentions_actor = WARN` rule, meaning the evidence sentence does not explicitly name the actor. The question is whether this matters semantically:

| Candidate | Evidence phrase | Actor in evidence? | Semantic adequacy |
|-----------|----------------|-------------------|------------------|
| prev_rare_positive_32_001 | "The group..." | No (uses "The group") | HIGH — "The group" has single referent in the article |
| prev_dir_contrast_38_003_contradictory | "The company..." | No (uses "The company") | HIGH — "The company" has single referent in the article |
| prev_dir_contrast_12_002_contradictory | "The team..." | No (uses "The team") | MODERATE — "The team" refers to Oakridge High School, but the positive framing concern is a separate and more serious issue |

**Conclusion on the evidence_mentions_actor WARN:**  
For candidates 1 and 3, the WARN is a surface-level naming issue, not a semantic problem. The human reviewer should confirm the generic reference is clear in context.  
For candidate 5, the WARN is the lesser of two concerns — the mixed framing issue is the primary reason for REVIEW_SUGGESTED.

---

## Systematic Issues Found Across Candidates

### Issue 1: Evidence sentence actor naming (3/6 candidates)
Three candidates use generic references ("The group", "The company", "The team") in the evidence sentence. This is consistent with natural news writing style, where pronouns and generic terms replace proper nouns after first introduction. However, for training data purposes, evidence sentences that explicitly name the actor are more reliable. Future generation requests should include an explicit constraint: *"The evidence_sentence must name the actor explicitly."*

### Issue 2: Direction contrastive pair completeness
The direction_contrastive pair for L1=12 (Have success) consists of:
- Aligned: prev_dir_contrast_12_002_aligned_ce1da19f54 → ACCEPT_SUGGESTED
- Contradictory: prev_dir_contrast_12_002_contradictory_ce1da19f54 → REVIEW_SUGGESTED (possible rejection)

If the contradictory member is rejected, the pair is broken. A replacement contradictory sample for L1=12 would be needed before both members can enter training. This should be noted for the next generation request round.

The L1=38 (Be honest) pair is stronger:
- Aligned: prev_dir_contrast_38_003_aligned_e969e14138 → ACCEPT_SUGGESTED
- Contradictory: prev_dir_contrast_38_003_contradictory_e969e14138 → REVIEW_SUGGESTED (likely upgradable)

### Issue 3: Article length variation
Content length ranges from 384 characters (prev_dir_contrast_38_003_contradictory, 4 sentences) to 874 characters (prev_rare_positive_24_004, 9 sentences). The shortest article is a concern for training data richness. Future generation requests should specify a minimum article length, e.g., "at least 6 sentences" or "150–200 words."

### Issue 4: No candidates suggested for rejection
The absence of REJECT_SUGGESTED verdicts is a positive signal about generation quality. However, given that candidate 5 (prev_dir_contrast_12_002_contradictory) has a high training risk score, the human reviewer should apply extra scrutiny to this candidate and not assume that REVIEW_SUGGESTED necessarily leads to ACCEPT.
