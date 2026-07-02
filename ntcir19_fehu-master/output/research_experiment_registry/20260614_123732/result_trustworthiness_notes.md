# Result Trustworthiness Notes

Each method folder is categorised into one of the canonical tags.

## `canonical_prompt_oai`

- **`output/task1_prompt`**  arts=177  pred_1a=929  pred_1b=1027  full_dev=True
    - run_config: no   metrics: no
    - model: unknown   provider: unknown   limit: unknown
    - notes: Prompt-only OpenAI (legacy; no run_config). Likely gpt-4o-mini.

## `canonical_prompt_ds_flash`

- **`output/task1_prompt_deepseek_v4_flash`**  arts=177  pred_1a=1500  pred_1b=1736  full_dev=True
    - run_config: yes   metrics: yes
    - model: deepseek-v4-flash   provider: deepseek   limit: None
    - notes: Prompt-only DeepSeek V4 Flash. Full run_config + metrics.

## `canonical_deberta`

- **`output/task1_deberta`**  arts=177  pred_1a=1786  pred_1b=3378  full_dev=True
    - run_config: no   metrics: no
    - model: unknown   provider: unknown   limit: unknown
    - notes: DeBERTa-only predictions. Regenerated from checkpoint.

## `canonical_hybrid_v1`

- **`output/task1_hybrid`**  arts=177  pred_1a=2417  pred_1b=3117  full_dev=True
    - run_config: yes   metrics: yes
    - model: gpt-4o-mini   provider: unknown   limit: None
    - notes: Hybrid v1 (DeBERTa cand + LLM keep/remove).

## `canonical_hybrid_v2_ds_pro`

- **`output/task1_hybrid_v2_deepseek_deepseek_v4_pro`**  arts=177  pred_1a=1069  pred_1b=1202  full_dev=True
    - run_config: yes   metrics: yes
    - model: deepseek-v4-pro   provider: deepseek   limit: None
    - notes: Hybrid v2 DeepSeek V4 Pro. Full provenance.

## `canonical_hybrid_v2_ds_flash`

- **`output/task1_hybrid_v2_deepseek_deepseek_v4_flash`**  arts=177  pred_1a=1078  pred_1b=1270  full_dev=True
    - run_config: yes   metrics: yes
    - model: deepseek-v4-flash   provider: deepseek   limit: None
    - notes: Hybrid v2 DeepSeek V4 Flash. Full provenance.

## `canonical_hybrid_v2_oai_mini`

- **`output/task1_hybrid_v2_openai_gpt_4o_mini`**  arts=0  pred_1a=None  pred_1b=None  full_dev=False
    - run_config: no   metrics: no
    - model: unknown   provider: unknown   limit: unknown
    - notes: Directory does not exist. Expected canonical Hybrid v2 OAI folder. Currently missing.

## `legacy_duplicate_ambiguous`

- **`output/task1`**  arts=177  pred_1a=929  pred_1b=1027  full_dev=True
    - run_config: no   metrics: no
    - model: unknown   provider: unknown   limit: unknown
    - notes: Legacy ambiguous: was written by both run_pipeline.py and train_deberta.py. Current bytes match output/task1_prompt/. Do not use as a method source.

## `orphan_legacy_hybrid_v2`

- **`output/task1_hybrid_v2`**  arts=177  pred_1a=1040  pred_1b=1098  full_dev=True
    - run_config: yes   metrics: yes
    - model: gpt-4o-mini   provider: unknown   limit: None
    - notes: Orphan: predates provider-aware naming in hybrid_v2.py. Canonical OAI v2 path output/task1_hybrid_v2_openai_gpt_4o_mini/ does not exist.

## `limit_debug_run`

- **`output/task1_prompt_deepseek_v4_flash_limit5`**  arts=5  pred_1a=46  pred_1b=52  full_dev=False
    - run_config: yes   metrics: yes
    - model: deepseek-v4-flash   provider: deepseek   limit: 5
    - notes: Limit (debug) run of Prompt DS Flash with N=5. Exclude from full-dev comparisons.

- **`output/task1_hybrid_v2_limit20`**  arts=20  pred_1a=136  pred_1b=151  full_dev=False
    - run_config: yes   metrics: yes
    - model: gpt-4o-mini   provider: unknown   limit: 20
    - notes: Limit (debug) run of Hybrid v2 with N=20.
