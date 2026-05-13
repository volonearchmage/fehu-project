"""
FEHU Task-1: Article-level Human Value Classification
Prompt-based Pipeline - Supports OpenAI GPT and Google Gemini

Usage:
    # Run on dev set (to evaluate)
    python src/run_pipeline.py --mode dev

    # Use Gemini for full dev set
    python src/run_pipeline.py --mode dev --provider gemini

    # Use OpenAI for final test submission
    python src/run_pipeline.py --mode test --provider openai --model gpt-4o

    # Use OpenAI gpt-4o-mini (default)
    python src/run_pipeline.py --mode dev --provider openai

API Key Setup - Create '.env' file in project root:
    OPENAI_API_KEY=sk-your-key-here
    GEMINI_API_KEY=your-gemini-key-here
"""

import json
import os
import sys
import time
import argparse
from openai import OpenAI
from tqdm import tqdm

# ============================================================
# CONFIG - Change these paths if your folder structure differs
# ============================================================

# Base directory: the root of ntcir19_fehu-master
# This script assumes it's run from the project root:
#   python src/run_pipeline.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data paths
TEST_ARTICLES = os.path.join(BASE_DIR, "dataset", "test", "test_article_event_base.json")
DEV_ARTICLES = os.path.join(BASE_DIR, "dataset", "dev", "dev_event_base.json")
TRAIN_ARTICLES = os.path.join(BASE_DIR, "dataset", "train", "train_event_base.json")
TRAIN_LABELS = os.path.join(BASE_DIR, "dataset", "gold_labels", "train", "train_human_values.json")
DEV_LABELS = os.path.join(BASE_DIR, "dataset", "gold_labels", "dev", "dev_human_values.json")

# Taxonomy paths
HV_DIR = os.path.join(BASE_DIR, "dataset", "hv_categories")
L1_VALUES_PATH = os.path.join(HV_DIR, "human_value_level1_values.json")
L2_VALUES_PATH = os.path.join(HV_DIR, "human_value_level2_values.json")
L1_TO_L2_PATH = os.path.join(HV_DIR, "level_1_to_level_2.json")

# Output paths
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "task1")

# Model config
MODEL = "gpt-4o-mini"  # Use gpt-4o-mini for dev; switch to gpt-4o for final
TEMPERATURE = 0.1
MAX_RETRIES = 3

# ============================================================
# LOAD TAXONOMY
# ============================================================

def load_taxonomy():
    """Load all value category definitions."""
    with open(L1_VALUES_PATH, "r", encoding="utf-8") as f:
        l1_name_to_id = json.load(f)  # {"Be creative": "0", ...}

    with open(L2_VALUES_PATH, "r", encoding="utf-8") as f:
        l2_name_to_id = json.load(f)  # {"Self-direction: thought": "0", ...}

    with open(L1_TO_L2_PATH, "r", encoding="utf-8") as f:
        l1_to_l2_raw = json.load(f)["level_1_to_level_2"]
        # {"Be creative": "Self-direction: thought", ...}

    # Build L1 id -> L2 id mapping
    l1_id_to_l2_id = {}
    for l1_name, l2_name in l1_to_l2_raw.items():
        l1_id = l1_name_to_id[l1_name]
        l2_id = l2_name_to_id[l2_name]
        l1_id_to_l2_id[l1_id] = l2_id

    return l1_name_to_id, l2_name_to_id, l1_id_to_l2_id


# ============================================================
# BUILD FEW-SHOT EXAMPLES FROM TRAINING DATA
# ============================================================

def load_few_shot_examples(n=2):
    """
    Load n training articles with their gold labels as few-shot examples.
    Pick articles with moderate number of actors and clear value assignments.
    """
    with open(TRAIN_ARTICLES, "r", encoding="utf-8") as f:
        train_articles = json.load(f)
    with open(TRAIN_LABELS, "r", encoding="utf-8") as f:
        train_labels = json.load(f)

    # Build guid -> labels mapping
    guid_to_labels = {item["guid"]: item for item in train_labels}

    # Build guid -> article mapping
    guid_to_article = {item["guid"]: item for item in train_articles}

    # Select good examples: articles with 2-3 actors and 4-8 total labels
    candidates = []
    for item in train_labels:
        guid = item["guid"]
        hvs = item.get("article_human_values", [])
        if guid in guid_to_article:
            actors = guid_to_article[guid].get("actors", [])
            if 2 <= len(actors) <= 3 and 4 <= len(hvs) <= 8:
                candidates.append(guid)

    # Take first n candidates
    selected = candidates[:n]

    examples = []
    for guid in selected:
        article = guid_to_article[guid]
        labels = guid_to_labels[guid]

        # Format actor list
        actor_list = []
        for actor_dict in article["actors"]:
            for name, aid in actor_dict.items():
                actor_list.append({"name": name, "id": aid})

        # Format gold labels for the example output
        output_values = []
        for hv in labels["article_human_values"]:
            # Reverse lookup l1 name from id
            l1_id = hv["l1_value"]
            l1_name = [k for k, v in l1_name_to_id.items() if v == l1_id][0]
            output_values.append({
                "actor_id": hv["actor"],
                "l1_value_name": l1_name,
                "l1_value_id": hv["l1_value"],
                "direction": "aligned" if hv["direction"] == "1" else "contradictory",
                "reasoning": hv.get("explanation", "")[:150]  # Truncate for prompt length
            })

        examples.append({
            "title": article["title"],
            "content": article["content"][:1500],  # Truncate long articles
            "actors": actor_list,
            "output": output_values
        })

    return examples


# ============================================================
# BUILD THE PROMPT
# ============================================================

def build_system_prompt(few_shot_examples):
    """Build the system prompt with task description and few-shot examples."""

    # Build the L1 value list string
    l1_list_str = ""
    for name, vid in sorted(l1_name_to_id.items(), key=lambda x: int(x[1])):
        l1_list_str += f"  {vid}: {name}\n"

    system_prompt = f"""You are an expert in human value analysis for news articles.

TASK: Given a factual news article and a list of actors (people, organizations, or groups mentioned in the article), identify which human values each actor's behavior expresses or violates.

HUMAN VALUE CATEGORIES (Level-1, 54 values):
{l1_list_str}
DIRECTION:
- "aligned": The actor's behavior supports, upholds, or expresses this value.
- "contradictory": The actor's behavior violates, undermines, or contradicts this value.

GUIDELINES:
1. For each actor, identify 3-7 relevant values. Don't over-predict.
2. Only assign values that have clear evidence in the article text.
3. Consider both what actors DO and what they SAY.
4. The same actor can have both aligned and contradictory values.
5. Different actors in the same event often have opposing value directions.
6. Common patterns:
   - Law enforcement/authorities: often aligned with "Be just"(45), "Be responsible"(42), "Have a safe country"(26)
   - Victims/affected people: often contradicted on "Have good health"(22), "Have a comfortable life"(25)
   - Organizations responding to crises: often aligned with "Be helpful"(37), "Be honest"(38)
   - Rule-breakers/criminals: often contradictory to "Be compliant"(30), "Be responsible"(42)

OUTPUT FORMAT: Return ONLY a valid JSON array. Each element must have:
- "actor_id": the actor's ID string (e.g., "0-4405-1-3-0")
- "l1_value_id": the Level-1 value ID as a string (e.g., "42")
- "direction": either "aligned" or "contradictory"
- "reasoning": one sentence explaining why (keep it brief)

Do NOT include any text before or after the JSON array. No markdown, no explanation."""

    # Add few-shot examples
    if few_shot_examples:
        system_prompt += "\n\nEXAMPLES:\n"
        for i, ex in enumerate(few_shot_examples):
            actor_str = ", ".join([f'{a["name"]} (ID: {a["id"]})' for a in ex["actors"]])
            output_str = json.dumps(ex["output"][:4], indent=2, ensure_ascii=False)  # Show first 4 for brevity
            system_prompt += f"""
--- Example {i+1} ---
Title: {ex["title"]}
Article (truncated): {ex["content"][:500]}...
Actors: {actor_str}
Output:
{output_str}
"""

    return system_prompt


def build_user_prompt(article):
    """Build the user prompt for a single article."""
    # Build actor list
    actor_lines = []
    for actor_dict in article["actors"]:
        for name, aid in actor_dict.items():
            actor_lines.append(f"- {name} (ID: {aid})")
    actor_str = "\n".join(actor_lines)

    # Truncate very long articles to fit context window
    content = article["content"]
    if len(content) > 12000:
        content = content[:6000] + "\n...[truncated]...\n" + content[-3000:]

    return f"""Title: {article["title"]}

Article:
{content}

Actors:
{actor_str}

Identify the human values for each actor. Return ONLY a JSON array."""


# ============================================================
# CALL OPENAI API
# ============================================================

def call_gpt(client, system_prompt, user_prompt, article_guid):
    """Call OpenAI API with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=TEMPERATURE,
                max_completion_tokens=4000,
            )

            content = response.choices[0].message.content.strip()

            # Try to extract JSON from response
            # Sometimes GPT wraps it in ```json ... ```
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            if not isinstance(result, list):
                print(f"  [WARN] {article_guid}: Response is not a list, wrapping it")
                result = [result]

            return result

        except json.JSONDecodeError as e:
            print(f"  [WARN] {article_guid}: JSON parse error (attempt {attempt+1}): {e}")
            print(f"  Response was: {content[:200]}...")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
            continue

        except Exception as e:
            print(f"  [ERROR] {article_guid}: API error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(5)
            continue

    print(f"  [FAIL] {article_guid}: All retries failed, returning empty")
    return []


# ============================================================
# PROCESS RESULTS -> OUTPUT FORMAT
# ============================================================

def process_results(article_guid, actors, gpt_results):
    """
    Convert GPT output to the official submission format.
    Produces entries for both task1a and task1b.
    """
    # Get valid actor IDs for this article
    valid_actor_ids = set()
    for actor_dict in actors:
        for name, aid in actor_dict.items():
            valid_actor_ids.add(aid)

    task1a_values = []  # For pred_task1a.json
    task1b_values = []  # For pred_task1b.json

    seen_task1a = set()  # Deduplicate (actor, l2_value)
    seen_task1b = set()  # Deduplicate (actor, direction, l1_value)

    for item in gpt_results:
        actor_id = str(item.get("actor_id", ""))
        l1_id = str(item.get("l1_value_id", ""))
        direction_str = item.get("direction", "aligned")

        # Validate actor_id
        if actor_id not in valid_actor_ids:
            continue

        # Validate l1_value_id
        if not l1_id.isdigit() or int(l1_id) < 0 or int(l1_id) > 53:
            continue

        # Convert direction
        if direction_str == "contradictory":
            direction = "0"
        else:
            direction = "1"  # Default to aligned

        # Map L1 -> L2
        l2_id = l1_id_to_l2_id.get(l1_id, None)
        if l2_id is None:
            continue

        # Task 1a: (actor, l2_value) - deduplicate
        key_1a = (actor_id, l2_id)
        if key_1a not in seen_task1a:
            seen_task1a.add(key_1a)
            task1a_values.append({
                "actor": actor_id,
                "l2_value": l2_id
            })

        # Task 1b: (actor, direction, l1_value) - deduplicate
        key_1b = (actor_id, direction, l1_id)
        if key_1b not in seen_task1b:
            seen_task1b.add(key_1b)
            task1b_values.append({
                "actor": actor_id,
                "l1_value": l1_id,
                "direction": direction
            })

    return task1a_values, task1b_values


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="FEHU Task-1 Prompt Pipeline")
    parser.add_argument("--mode", choices=["dev", "test"], default="dev",
                        help="Run on dev set (for evaluation) or test set (for submission)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only N articles (for quick testing)")
    parser.add_argument("--model", type=str, default=MODEL,
                        help="OpenAI model to use (default: gpt-4o-mini)")
    parser.add_argument("--api_key", type=str, default=None,
                        help="OpenAI API key (or set OPENAI_API_KEY env var)")
    args = parser.parse_args()

   # Set model (passed to call_gpt via args)
    model_name = args.model

    # Initialize OpenAI client
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No API key provided!")
        print("Either pass --api_key YOUR_KEY or set environment variable:")
        print('  Windows CMD:   set OPENAI_API_KEY=your_key_here')
        print('  Windows PS:    $env:OPENAI_API_KEY="your_key_here"')
        print('  Linux/Mac:     export OPENAI_API_KEY=your_key_here')
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Load taxonomy (global for use in other functions)
    global l1_name_to_id, l2_name_to_id, l1_id_to_l2_id
    l1_name_to_id, l2_name_to_id, l1_id_to_l2_id = load_taxonomy()

    # Load articles
    if args.mode == "dev":
        articles_path = DEV_ARTICLES
        print(f"Mode: DEV (will evaluate against gold labels)")
    else:
        articles_path = TEST_ARTICLES
        print(f"Mode: TEST (will produce submission files)")

    with open(articles_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if args.limit:
        articles = articles[:args.limit]

    print(f"Loaded {len(articles)} articles")
    print(f"Model: {MODEL}")

    # Load few-shot examples from training data
    print("Loading few-shot examples from training data...")
    few_shot_examples = load_few_shot_examples(n=2)
    print(f"Loaded {len(few_shot_examples)} few-shot examples")

    # Build system prompt (same for all articles)
    system_prompt = build_system_prompt(few_shot_examples)

    # Process each article
    all_task1a = []
    all_task1b = []

    # Cache file for resuming interrupted runs
    cache_path = os.path.join(BASE_DIR, "logs", f"cache_{args.mode}.json")
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Loaded cache with {len(cache)} processed articles")

    for article in tqdm(articles, desc="Processing articles"):
        guid = article["guid"]

        # Check cache
        if guid in cache:
            gpt_results = cache[guid]
        else:
            # Build prompt and call API
            user_prompt = build_user_prompt(article)
            gpt_results = call_gpt(client, system_prompt, user_prompt, guid)

            # Save to cache
            cache[guid] = gpt_results
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)

        # Process results
        task1a_values, task1b_values = process_results(guid, article["actors"], gpt_results)

        all_task1a.append({
            "guid": guid,
            "article_human_values": task1a_values
        })

        all_task1b.append({
            "guid": guid,
            "article_human_values": task1b_values
        })

    # Save output files
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    task1a_path = os.path.join(OUTPUT_DIR, "pred_task1a.json")
    task1b_path = os.path.join(OUTPUT_DIR, "pred_task1b.json")

    with open(task1a_path, "w", encoding="utf-8") as f:
        json.dump(all_task1a, f, indent=2, ensure_ascii=False)
    print(f"\nSaved Task-1a predictions to: {task1a_path}")

    with open(task1b_path, "w", encoding="utf-8") as f:
        json.dump(all_task1b, f, indent=2, ensure_ascii=False)
    print(f"Saved Task-1b predictions to: {task1b_path}")

    # Print stats
    total_1a = sum(len(item["article_human_values"]) for item in all_task1a)
    total_1b = sum(len(item["article_human_values"]) for item in all_task1b)
    print(f"\nStats:")
    print(f"  Articles processed: {len(articles)}")
    print(f"  Task-1a predictions: {total_1a} (avg {total_1a/len(articles):.1f} per article)")
    print(f"  Task-1b predictions: {total_1b} (avg {total_1b/len(articles):.1f} per article)")

    # If dev mode, run evaluation
    if args.mode == "dev":
        print("\n" + "="*60)
        print("RUNNING EVALUATION ON DEV SET")
        print("="*60)
        run_dev_evaluation(task1a_path, task1b_path)


def run_dev_evaluation(pred_1a_path, pred_1b_path):
    """Run the official evaluation script on dev predictions."""
    # Import evaluation functions directly
    sys.path.insert(0, BASE_DIR)
    from evaluation import (
        parse_task1a, parse_task1b, evaluate,
        l2_universe, l1_dir_universe,
        direction_reverse_rate_gold_excl
    )

    # Parse gold and predictions
    gold_1a = parse_task1a(DEV_LABELS)
    pred_1a = parse_task1a(pred_1a_path)
    gold_1b = parse_task1b(DEV_LABELS)
    pred_1b = parse_task1b(pred_1b_path)

    # Evaluate Task 1a
    results_1a = evaluate(gold_1a, pred_1a, l2_universe())
    print(f"\nTask-1a (Level-2, no direction):")
    print(f"  Micro F1: {results_1a['micro_f1']:.4f}")
    print(f"  Macro F1: {results_1a['macro_f1']:.4f}")
    print(f"  Precision: {results_1a['micro_precision']:.4f}")
    print(f"  Recall: {results_1a['micro_recall']:.4f}")

    # Evaluate Task 1b
    results_1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    drr, rev_cnt, denom_cnt, amb_cnt = direction_reverse_rate_gold_excl(gold_1b, pred_1b)
    print(f"\nTask-1b (Level-1 + direction):")
    print(f"  Micro F1: {results_1b['micro_f1']:.4f}")
    print(f"  Macro F1: {results_1b['macro_f1']:.4f}")
    print(f"  Precision: {results_1b['micro_precision']:.4f}")
    print(f"  Recall: {results_1b['micro_recall']:.4f}")
    print(f"  Direction Reverse Rate: {drr:.4f} ({rev_cnt}/{denom_cnt})")

    return results_1a, results_1b


if __name__ == "__main__":
    main()
