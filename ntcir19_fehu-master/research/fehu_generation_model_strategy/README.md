# FEHU Generation Model Strategy

Documentation-only module describing **which model to use for which phase of
the augmentation pipeline, and why**. No code; no execution.

## Files

- `MODEL_SELECTION_AND_COST_STRATEGY.md` — full strategy

## Why a separate module

`research/fehu_augmentation_v1/METHOD_DESIGN.md` describes the four
augmentation types and the priority logic. This module focuses on a different
axis: **which LLM to use for each phase**, the cost / quality trade-off, and
the verification cadence. Keeping the two concerns separate makes both
documents easier to update as the pipeline scales from tiny pilot to full
augmentation.

## Status

Strategy only. No model has been called. No bill has been incurred.
