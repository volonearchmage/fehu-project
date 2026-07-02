# Go / No-Go Decision

| Action | Decision | Reason |
|---|---|---|
| **Human review of v2 preview** | ✅ **GO** | All 15 safety gates pass. v2 preview is well-formed (18 requests, 0 fails, 6 design-justified warns). The review sheet (`output/research_generation_preview/20260614_171644/human_review_sheet.csv`) is prepared. |
| **Creation of `run_generation.py`** | 🛑 **NO-GO** until human review + budget approval | The generation runner is not implemented yet. Authoring it now would mean writing API-calling code before the requests it would dispatch are approved. |
| **Tiny-pilot API generation** | 🛑 **NO-GO** until step above | Requires explicit per-request approval AND `run_generation.py` authored with dry-run-first semantics. |
| **Model training (DeBERTa + augmented)** | 🛑 **NO-GO** | Requires actual augmented data first; none has been produced. |
| **Final FEHU submission (`pred_task1*.json` for test set)** | 🛑 **NO-GO** | Not authorised. `fehu_prediction_format_guard.py` must pass first on any candidate submission, and no candidate exists yet. |

## Why this split

- **GO** items are local, read-only, reversible — they do not change project state.
- **NO-GO** items are external (API cost, GPU time) and/or write into protected paths (final predictions). Each requires explicit user approval.

## Single-sentence recommendation

> **Proceed to human review of the v2 preview; do not author `run_generation.py` or call any API yet.**
