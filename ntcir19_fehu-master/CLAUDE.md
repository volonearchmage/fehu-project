# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **NTCIR-19 FEHU** (Fact-based Event-centric Human Value Understanding) benchmark repository. The project provides:
- A benchmark dataset for identifying human values expressed by actors in factual news articles
- Evaluation code for scoring model predictions
- A baseline pipeline using GPT-4o/GPT-4o-mini for value classification

**Note (March 20, 2026):** Versions before commit `af52dcb` contained a data bug in actor alignment. The current version is corrected.

## Build & Environment Setup

### Prerequisites
- Python 3.7+
- OpenAI API key (for baseline pipeline)
- Gemini API key (optional, for alternative baseline)

### Installation
```bash
# No installation needed - pure Python
# For API access, create .env in project root:
echo "OPENAI_API_KEY=sk-your-key-here" > .env
echo "GEMINI_API_KEY=your-gemini-key-here" >> .env
```

### Running the Baseline Pipeline
```bash
# Evaluate on dev set with GPT-4o-mini (default)
python src/run_pipeline.py --mode dev

# Use GPT-4o for final test submission
python src/run_pipeline.py --mode test --model gpt-4o

# Process only first N articles (quick testing)
python src/run_pipeline.py --mode dev --limit 5

# Pass API key directly
python src/run_pipeline.py --mode dev --api_key sk-your-key
```

### Running Evaluation
```bash
# Evaluate predictions against gold labels
python evaluation.py \
  --gold_task1 dataset/gold_labels/dev/dev_human_values.json \
  --pred_task1a output/task1/pred_task1a.json \
  --pred_task1b output/task1/pred_task1b.json \
  --gold_task2 dataset/gold_labels/dev/dev_human_values.json \
  --pred_task2a output/task2/pred_task2a.json \
  --pred_task2b output/task2/pred_task2b.json
```

## Architecture & Key Components

### Task Structure
The benchmark has **two main tasks** with **two variants each**:

**Task-1: Article-level Human Value Recognition**
- **Task-1a:** Identify Level-2 human values for each actor (20 possible values)
- **Task-1b:** Identify Level-1 human values + direction for each actor (54 values + aligned/contradictory)
- Evaluation unit: `(article_guid, actor_id)`

**Task-2: Subevent-level Human Value Recognition**
- **Task-2a:** Identify Level-2 values for each actor in each subevent
- **Task-2b:** Identify Level-1 values + direction for each actor in each subevent
- Evaluation unit: `(article_guid, subevent_id, actor_id)`

### Human Value Taxonomy
- **Level-1 values:** 54 core human value categories (e.g., "Be creative", "Be just", "Have a safe country")
- **Level-2 values:** 20 higher-level categories (e.g., "Self-direction", "Security", "Benevolence")
- **Direction:** Binary classifier for each value
  - `"1"` = aligned (actor's behavior expresses/supports the value)
  - `"0"` = contradictory (actor's behavior violates/undermines the value)
- Mappings in `dataset/hv_categories/` (JSON files with name↔ID lookups and L1↔L2 relationships)

### Dataset Structure
```
dataset/
├── train/
│   └── train_event_base.json          # Training articles + actors + subevents
├── dev/
│   └── dev_event_base.json            # Dev articles
├── test/
│   ├── test_article_event_base.json   # Test articles only (Task-1)
│   └── test_subevent_event_base.json  # Test articles + subevents (Task-2)
├── gold_labels/
│   ├── train/train_human_values.json  # Gold labels for training
│   └── dev/dev_human_values.json      # Gold labels for dev (used for both Task-1 and Task-2)
├── hv_categories/
│   ├── human_value_level1_values.json
│   ├── human_value_level2_values.json
│   ├── level_1_to_level_2.json        # Mapping for Task-1a/2a (L1→L2)
│   ├── level_2_to_level_1.json        # Reverse mapping
│   └── direction_mapping.json         # Direction enum
└── evaluation_test_data_examples/
    └── pred/                          # Example prediction file formats
```

### Article & Label Schema
**Article (event_base.json):**
```json
{
  "guid": "unique_article_id",
  "title": "News headline",
  "content": "Full article text",
  "actors": [{"Actor Name": "actor_id_string"}, ...],
  "subevents": [{"id": "se_0", "subevent": "Subevent description"}, ...]
}
```

**Gold Labels (Task-1):**
```json
{
  "guid": "article_id",
  "article_human_values": [
    {
      "actor": "actor_id",
      "l1_value": "42",        # Level-1 value ID (0-53)
      "l2_value": "16",        # Level-2 value ID (0-19)
      "direction": "1",        # "1"=aligned, "0"=contradictory
      "explanation": "Reasoning text"
    },
    ...
  ]
}
```

**Predictions (Task-1a):**
```json
{
  "guid": "article_id",
  "article_human_values": [
    {
      "actor": "actor_id",
      "l2_value": "16"
    },
    ...
  ]
}
```

**Predictions (Task-1b):**
```json
{
  "guid": "article_id",
  "article_human_values": [
    {
      "actor": "actor_id",
      "l1_value": "42",
      "direction": "1"
    },
    ...
  ]
}
```

### Baseline Pipeline (src/run_pipeline.py)
The GPT-based baseline pipeline flow:
1. **Load Taxonomy:** Parse 54 Level-1 and 20 Level-2 value definitions and their mappings
2. **Load Few-Shot Examples:** Select 2 well-balanced training articles as demonstrations
3. **Build System Prompt:** Construct a detailed prompt with:
   - Task description
   - Full Level-1 value list with IDs
   - Domain-specific patterns (what values different actor types typically align/contradict)
   - Output format specification (JSON array with actor_id, l1_value_id, direction, reasoning)
   - Few-shot examples from training data
4. **For Each Article:**
   - Build user prompt with article content + actor list
   - Call GPT API with few-shot prompt
   - Parse JSON response (with retry logic and markdown stripping)
   - Deduplicate results by (actor, l2_value) for Task-1a and (actor, direction, l1_value) for Task-1b
   - Cache results for resumable runs
5. **Output:** Generate `pred_task1a.json` and `pred_task1b.json`
6. **Dev Mode:** Automatically run evaluation against gold labels after pipeline completes

**Key Parameters:**
- `MODEL = "gpt-4o-mini"` (configurable; use gpt-4o for final submission)
- `TEMPERATURE = 0.1` (low randomness for reproducibility)
- `MAX_RETRIES = 3` (robust error handling)
- Cache stored in `logs/cache_{mode}.json` for resumable processing

### Prompt Templates (src/prompts.py)
Reusable prompt building functions:
- `build_system_prompt(few_shot_examples)` - Creates detailed system prompt with L1 value list, guidelines, patterns, and examples
- `build_user_prompt(article)` - Formats single article for evaluation

### Evaluation Script (evaluation.py)
Metrics and scoring logic:
- **Micro-F1:** Precision/recall computed across all label instances
- **Macro-F1 (gold-supported):** Averaged only over labels that appear ≥1 time in gold
- **Direction Reverse Rate (DRR):** For Task-1b/2b only; measures how often a gold Level-1 value is predicted with opposite direction. Excludes ambiguous cases where the same L1 value has both directions in gold for the same instance.

**Key Functions:**
- `parse_task1a()` / `parse_task1b()` - Parse gold/prediction files into instance→labels sets
- `evaluate()` - Compute micro/macro F1 metrics
- `direction_reverse_rate_gold_excl()` - Compute DRR metric for direction variants

## Important Notes

### Data Bug History
- **Before commit af52dcb (March 20, 2026):** `dataset/gold_labels/train/train_human_values.json` and `dev/dev_human_values.json` contained incorrect actor alignments due to a code bug in data processing
- **Current version:** Bug has been corrected
- Always verify which commit version is in use when working with gold labels

### Output Structure
- Pipeline output is written to `output/task1/` (only Task-1 implemented in baseline)
- Cache is stored in `logs/cache_{mode}.json` (allows resuming interrupted runs)
- Example prediction formats are in `dataset/evaluation_test_data_examples/` for reference

### Direction Mapping for Task-1b/2b
When submitting Task-1b/2b predictions, the evaluator internally encodes labels as `"{direction}:{l1_value}"` (e.g., `"1:42"`). Your JSON output should use separate `l1_value` and `direction` fields, which are combined by the scoring script.

## Common Development Tasks

### Add a new baseline model
1. Create a new script in `src/` that loads articles from `DEV_ARTICLES` or `TEST_ARTICLES`
2. Load taxonomy from `dataset/hv_categories/` (reuse functions from `run_pipeline.py`)
3. Output predictions in format matching `dataset/evaluation_test_data_examples/pred/`
4. Invoke evaluation by parsing gold labels and calling `evaluation.py` functions

### Evaluate custom predictions
```bash
python evaluation.py \
  --gold_task1 dataset/gold_labels/dev/dev_human_values.json \
  --pred_task1a <your_pred_task1a.json> \
  --pred_task1b <your_pred_task1b.json>
```

### Test pipeline on small dataset
```bash
python src/run_pipeline.py --mode dev --limit 5
```

### Resume interrupted pipeline run
The cache in `logs/cache_{mode}.json` is automatically loaded, so simply re-run the same command.
