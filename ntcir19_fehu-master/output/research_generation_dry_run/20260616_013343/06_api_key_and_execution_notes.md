# API Key and Future Execution Notes

> **No API key is needed for this dry-run.** The script in this folder cannot make a network
> call: it imports only the Python standard library and writes only to the dry-run output folder.

## Hard rules going forward

1. **Do NOT paste API keys into prompts, reports, CSV, JSONL, or logs.**
   The dry-run scans the manifest for tokens of shape `sk-…`, `ds-…`, `anthropic-…` and
   fails fast if any are found. Future runners must keep that scan.

2. **Future real API generation must require a separate, explicit user authorisation.**
   This document does not constitute that authorisation. The approved manifest also
   does not constitute it — every row carries `api_generation_authorized_now: false`
   and `requires_separate_generation_runner_approval: true`.

3. **Future real API generation must use environment variables, not hard-coded keys.**
   Recommended variables:
   - OpenAI: `OPENAI_API_KEY`
   - DeepSeek: `DEEPSEEK_API_KEY`
   The future runner should refuse to start if the variable is empty.

4. **The future runner must mask any key that accidentally appears in any input.**
   - On read: redact patterns `\b(sk|ds|anthropic)[-_][A-Za-z0-9_-]+\b` before logging.
   - On write: never include the key in any output file.

5. **The future runner must write outputs to a new timestamped folder:**
   ```
   output/research_augmentation_data/YYYYMMDD_HHMMSS/
   ├── augmented_samples.jsonl               # validated samples
   ├── augmented_samples_rejected.jsonl      # samples that failed verification
   ├── raw_responses.jsonl                   # raw LLM responses (key-redacted)
   ├── failures.jsonl                        # API failures, parse errors
   ├── validation_report.md                  # final guard output
   ├── generation_run_config.json            # provider/model/budget/timestamp
   └── verification_summary.json
   ```
   The runner must NEVER write into `output/task1*/`, `dataset/`, or `logs/cache_*`.

6. **The future runner must run the augmented-data guard automatically after generation:**
   ```
   python research/fehu_submission_safety/augmented_training_data_guard.py \
       --input augmented_samples.jsonl --strict
   ```
   A non-zero exit must abort the pipeline before any downstream consumer reads the file.

## What this dry-run authorises

> **Nothing.** This dry-run authorises no API call, no spending, and no downstream action.
> It only demonstrates that the manifest is valid and the execution plan is well-formed.
