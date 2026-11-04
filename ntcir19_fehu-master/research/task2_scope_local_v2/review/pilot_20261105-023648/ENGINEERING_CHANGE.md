# Pre-training engineering correction

The first v2 acceptance failed bitwise next-update equality. Saved model, AdamW, scheduler and all RNG states restored exactly, but repeated default GPU backward/update calls differed (loss identical; parameter differences up to roughly1e-6). Detailed per-tensor evidence: ../resume_failure_diagnosis.json.

A targeted repeat with torch.use_deterministic_algorithms(True) and process-local CUBLAS_WORKSPACE_CONFIG=:4096:8 produced exactly equal model, optimizer, scheduler and RNG hashes (../resume_deterministic_diagnosis.json). This is consistent with documented CUDA/SDPA non-determinism; it does not identify a unique responsible kernel. Official reference: https://docs.pytorch.org/docs/main/generated/torch.nn.functional.scaled_dot_product_attention.html .

All T/J/S now share this numerical setting. No driver/kernel/environment package changes. Original acceptance failure, cache, frozen protocol/source and checkpoint remain unchanged. This execution directory freezes the new implementation, revalidates spans and re-executes necessary real GPU acceptance. No diagnostic checkpoint enters training.

Explicit complete-epoch recovery also retains each epoch output directory, so a selected checkpoint from before recovery remains locatable. No additional epochs or automatic retries.
