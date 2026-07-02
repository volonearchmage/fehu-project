# FEHU Hybrid Pipeline — Improvement Roadmap

## Current Status (v1)

| Method | 1a MiF1 | 1b MiF1 | Precision | Recall | DRR |
|--------|---------|---------|-----------|--------|-----|
| Prompt-only | 0.481 | 0.342 | 0.570 | 0.245 | 0.021 |
| DeBERTa-only | 0.506 | 0.299 | 0.255 | 0.361 | 0.238 |
| Hybrid v1 | 0.465 | 0.239 | 0.211 | 0.275 | 0.074 |

## Problem

Hybrid v1 is worse than both baselines because:
1. DeBERTa generates candidates with ~24% wrong directions
2. LLM was set to "strict verify mode" (keep/remove only, no direction fix)
3. LLM keeps direction-wrong candidates → low precision
4. LLM also removes some correct candidates → lower recall than DeBERTa

## Fix: v2 — Value-only candidates + LLM assigns direction

### Core idea
- DeBERTa's strength: finding WHICH values are relevant (high recall)
- DeBERTa's weakness: determining direction (DRR=0.238)
- LLM's strength: direction judgment (DRR=0.021) + precision
- Solution: Let DeBERTa detect values only, let LLM decide direction

### Design
1. DeBERTa generates candidates as L1 VALUE only (merge aligned+contradictory)
   - For each actor, if either "Be just-aligned" OR "Be just-contradictory" passes threshold → "Be just" is a candidate
   - Use max confidence between the two directions as the candidate score
   - This gives higher recall because both direction signals contribute
2. LLM receives candidates WITHOUT direction, decides:
   - Is this value relevant? (keep/remove)
   - If relevant, what direction? (aligned/contradictory)
3. No candidate whitelist needed for direction (LLM assigns it fresh)

### Expected improvement
- Recall: should be >= DeBERTa (more candidates from merged directions)
- DRR: should be close to prompt-only (~0.02) since LLM handles direction
- Precision: should improve because LLM filters + correct direction

## Future improvements (v3+)

- Adjust DeBERTa threshold and top_k based on v2 results
- Try two-stage DeBERTa: stage 1 = 54-class value detection, stage 2 = direction (retrain needed)
- Use training data explanations in LLM prompt as few-shot examples
- LLM-augmented training data for rare categories
- Multi-model ensemble (GPT-4o-mini + DeepSeek + Gemini voting)
