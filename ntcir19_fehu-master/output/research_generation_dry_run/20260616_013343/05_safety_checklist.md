# Safety Checklist

## Go / No-Go

| # | Item | Decision |
|---|---|---|
| 1 | Approved manifest exists | ✅ GO |
| 2 | Manifest has exactly 6 rows | ✅ GO |
| 3 | Dry-run completed | ✅ GO |
| 4 | API generation now | 🛑 NO-GO |
| 5 | API key required now | 🛑 NO-GO |
| 6 | Run real generation now | 🛑 NO-GO |
| 7 | Training now | 🛑 NO-GO |
| 8 | Final FEHU submission now | 🛑 NO-GO |
| 9 | Official dataset modification | 🛑 NO-GO |
| 10 | Old prediction modification | 🛑 NO-GO |

## Negative invariants (verified by `01_manifest_validation_report.md`)

- ✅ No row carries `manual_approval_status == "PENDING_HUMAN_APPROVAL"`.
- ✅ No row carries `api_generation_authorized_now == true`.
- ✅ No row contains the field `execute` or `should_execute_now`.
- ✅ No `hard_negative` request approved.
- ✅ No `paraphrase` request approved.
- ✅ No sensitive-label (L1 ∈ {29, 44, 51}) request approved.
- ✅ Both required direction-contrastive pairs are complete.
- ✅ No secret-shaped tokens in the manifest payload.

## What this dry-run is NOT

- Not API generation.
- Not a model training step.
- Not a prediction submission.
- Not a quality / performance claim — it does not measure F1, recall, or DRR.

## What this dry-run IS

- Proof that the human-approved manifest is structurally valid.
- A documented execution plan that a future runner could consume.
- A static set of prompt previews so the professor / reviewer can sanity-check.
- A reaffirmation that real API generation requires a separate explicit authorisation.
