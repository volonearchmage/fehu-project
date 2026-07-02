"""
FEHU Task-1: Article-level Human Value Classification — Prompt-only OpenAI pipeline.

Usage (from project root):
    # dev evaluation
    python src/run_pipeline.py --mode dev
    python src/run_pipeline.py --mode dev --model gpt-4o
    python src/run_pipeline.py --mode dev --limit 5

    # test submission (no eval)
    python src/run_pipeline.py --mode test --model gpt-4o

API Key Setup — Create '.env' in project root or `export OPENAI_API_KEY=sk-...`:
    OPENAI_API_KEY=sk-your-key-here

This script is the post-audit version. Changes vs. the original:
  • --model now actually flows into the API call (was silently ignored).
  • Cache path includes provider + model slug → no cross-model contamination.
  • Default output directory is `output/task1_prompt_openai_{model_slug}/`
    (no longer writes to ambiguous `output/task1/`).
  • Overwrite-safe: existing predictions are never overwritten unless
    --force_overwrite is given; otherwise a timestamped sibling is created.
  • run_config.json + metrics.json (dev mode) are emitted next to predictions.
  • --limit N correctly filters the dev gold to the same N guids before
    scoring (recall is no longer deflated).
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from tqdm import tqdm

# ============================================================
# CONFIG — paths derived from project root
# ============================================================

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_ARTICLES  = BASE_DIR / "dataset" / "test" / "test_article_event_base.json"
DEV_ARTICLES   = BASE_DIR / "dataset" / "dev"  / "dev_event_base.json"
TRAIN_ARTICLES = BASE_DIR / "dataset" / "train" / "train_event_base.json"
TRAIN_LABELS   = BASE_DIR / "dataset" / "gold_labels" / "train" / "train_human_values.json"
DEV_LABELS     = BASE_DIR / "dataset" / "gold_labels" / "dev"   / "dev_human_values.json"

HV_DIR         = BASE_DIR / "dataset" / "hv_categories"
L1_VALUES_PATH = HV_DIR / "human_value_level1_values.json"
L2_VALUES_PATH = HV_DIR / "human_value_level2_values.json"
L1_TO_L2_PATH  = HV_DIR / "level_1_to_level_2.json"

LOGS_DIR = BASE_DIR / "logs"

# Default model used when --model is not provided.
DEFAULT_MODEL = "gpt-4o-mini"
PROVIDER      = "openai"
METHOD_NAME   = "prompt_only"

TEMPERATURE = 0.1
MAX_RETRIES = 3


# ============================================================
# HELPERS
# ============================================================

def model_slug(name: str) -> str:
    """Lower-case, alphanumeric+underscore slug for filenames."""
    s = name.lower()
    s = re.sub(r"[/.:\-]", "_", s)
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def stable_text_hash(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def safe_output_dir(base: Path, force_overwrite: bool) -> tuple[Path, bool]:
    """
    Return an output directory that does not clobber existing predictions.

    Returns (dir, used_timestamped_fallback).
    """
    p1a = base / "pred_task1a.json"
    p1b = base / "pred_task1b.json"
    if base.exists() and (p1a.exists() or p1b.exists()) and not force_overwrite:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = base.parent / f"{base.name}_{ts}"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback, True
    base.mkdir(parents=True, exist_ok=True)
    return base, False


def current_git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(BASE_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out
    except Exception:
        return "unknown"


# ============================================================
# LOAD TAXONOMY
# ============================================================

def load_taxonomy():
    """Load all value category definitions."""
    with open(L1_VALUES_PATH, "r", encoding="utf-8") as f:
        l1_name_to_id = json.load(f)
    with open(L2_VALUES_PATH, "r", encoding="utf-8") as f:
        l2_name_to_id = json.load(f)
    with open(L1_TO_L2_PATH, "r", encoding="utf-8") as f:
        l1_to_l2_raw = json.load(f)["level_1_to_level_2"]

    l1_id_to_l2_id = {}
    for l1_name, l2_name in l1_to_l2_raw.items():
        l1_id = l1_name_to_id[l1_name]
        l2_id = l2_name_to_id[l2_name]
        l1_id_to_l2_id[l1_id] = l2_id

    return l1_name_to_id, l2_name_to_id, l1_id_to_l2_id


# ============================================================
# FEW-SHOT EXAMPLES
# ============================================================

def load_few_shot_examples(n=2):
    """Load n training articles with their gold labels as few-shot examples."""
    with open(TRAIN_ARTICLES, "r", encoding="utf-8") as f:
        train_articles = json.load(f)
    with open(TRAIN_LABELS, "r", encoding="utf-8") as f:
        train_labels = json.load(f)

    guid_to_labels  = {item["guid"]: item for item in train_labels}
    guid_to_article = {item["guid"]: item for item in train_articles}

    candidates = []
    for item in train_labels:
        guid = item["guid"]
        hvs  = item.get("article_human_values", [])
        if guid in guid_to_article:
            actors = guid_to_article[guid].get("actors", [])
            if 2 <= len(actors) <= 3 and 4 <= len(hvs) <= 8:
                candidates.append(guid)

    selected = candidates[:n]

    examples = []
    for guid in selected:
        article = guid_to_article[guid]
        labels  = guid_to_labels[guid]

        actor_list = []
        for actor_dict in article["actors"]:
            for name, aid in actor_dict.items():
                actor_list.append({"name": name, "id": aid})

        output_values = []
        for hv in labels["article_human_values"]:
            l1_id   = hv["l1_value"]
            l1_name = [k for k, v in l1_name_to_id.items() if v == l1_id][0]
            output_values.append({
                "actor_id":      hv["actor"],
                "l1_value_name": l1_name,
                "l1_value_id":   hv["l1_value"],
                "direction":     "aligned" if hv["direction"] == "1" else "contradictory",
                "reasoning":     hv.get("explanation", "")[:150],
            })

        examples.append({
            "title":   article["title"],
            "content": article["content"][:1500],
            "actors":  actor_list,
            "output":  output_values,
        })

    return examples


# ============================================================
# PROMPT TEMPLATES — preserved verbatim from the pre-patch version
# ============================================================

def build_system_prompt(few_shot_examples):
    """Build the system prompt with task description and few-shot examples."""

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

    if few_shot_examples:
        system_prompt += "\n\nEXAMPLES:\n"
        for i, ex in enumerate(few_shot_examples):
            actor_str  = ", ".join([f'{a["name"]} (ID: {a["id"]})' for a in ex["actors"]])
            output_str = json.dumps(ex["output"][:4], indent=2, ensure_ascii=False)
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
    actor_lines = []
    for actor_dict in article["actors"]:
        for name, aid in actor_dict.items():
            actor_lines.append(f"- {name} (ID: {aid})")
    actor_str = "\n".join(actor_lines)

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
# API CALL — model_name now flows through correctly (audit C1)
# ============================================================

def call_gpt(client, system_prompt, user_prompt, article_guid, model_name):
    """Call OpenAI API with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_completion_tokens=4000,
            )

            content = response.choices[0].message.content.strip()

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
# RESULT PROCESSING — preserved verbatim from pre-patch
# ============================================================

def process_results(article_guid, actors, gpt_results):
    """Convert GPT output to the official submission format."""
    valid_actor_ids = set()
    for actor_dict in actors:
        for _, aid in actor_dict.items():
            valid_actor_ids.add(aid)

    task1a_values = []
    task1b_values = []
    seen_task1a   = set()
    seen_task1b   = set()

    for item in gpt_results:
        actor_id      = str(item.get("actor_id", ""))
        l1_id         = str(item.get("l1_value_id", ""))
        direction_str = item.get("direction", "aligned")

        if actor_id not in valid_actor_ids:
            continue
        if not l1_id.isdigit() or int(l1_id) < 0 or int(l1_id) > 53:
            continue

        # direction_mapping.json: aligned="1", contradictory="0"
        direction = "0" if direction_str == "contradictory" else "1"

        l2_id = l1_id_to_l2_id.get(l1_id, None)
        if l2_id is None:
            continue

        key_1a = (actor_id, l2_id)
        if key_1a not in seen_task1a:
            seen_task1a.add(key_1a)
            task1a_values.append({"actor": actor_id, "l2_value": l2_id})

        key_1b = (actor_id, direction, l1_id)
        if key_1b not in seen_task1b:
            seen_task1b.add(key_1b)
            task1b_values.append({
                "actor": actor_id, "l1_value": l1_id, "direction": direction
            })

    return task1a_values, task1b_values


# ============================================================
# EVALUATION — filters gold to processed guids when --limit is set
# ============================================================

def _filter(d, guids):
    return {k: v for k, v in d.items() if k[0] in guids} if guids else d


def run_dev_evaluation(pred_1a_path, pred_1b_path, processed_guids=None):
    """
    Run official evaluation on dev predictions.

    When `processed_guids` is provided (e.g. --limit run), the dev gold
    is filtered to the same guid set before scoring, so recall is not
    deflated.
    """
    sys.path.insert(0, str(BASE_DIR))
    from evaluation import (
        parse_task1a, parse_task1b, evaluate,
        l2_universe, l1_dir_universe,
        direction_reverse_rate_gold_excl,
    )

    gold_1a = _filter(parse_task1a(str(DEV_LABELS)),    processed_guids)
    pred_1a = _filter(parse_task1a(str(pred_1a_path)),  processed_guids)
    gold_1b = _filter(parse_task1b(str(DEV_LABELS)),    processed_guids)
    pred_1b = _filter(parse_task1b(str(pred_1b_path)),  processed_guids)

    r1a = evaluate(gold_1a, pred_1a, l2_universe())
    r1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    drr, rev_cnt, denom, amb = direction_reverse_rate_gold_excl(gold_1b, pred_1b)

    print("\nTask-1a (Level-2, no direction):")
    print(f"  Micro F1:  {r1a['micro_f1']:.4f}")
    print(f"  Macro F1:  {r1a['macro_f1']:.4f}")
    print(f"  Precision: {r1a['micro_precision']:.4f}")
    print(f"  Recall:    {r1a['micro_recall']:.4f}")

    print("\nTask-1b (Level-1 + direction):")
    print(f"  Micro F1:  {r1b['micro_f1']:.4f}")
    print(f"  Macro F1:  {r1b['macro_f1']:.4f}")
    print(f"  Precision: {r1b['micro_precision']:.4f}")
    print(f"  Recall:    {r1b['micro_recall']:.4f}")
    print(f"  DRR:       {drr:.4f}  ({rev_cnt}/{denom},  ambiguous={amb})")

    return {
        "task1a": {
            "micro_f1":         r1a["micro_f1"],
            "macro_f1":         r1a["macro_f1"],
            "micro_precision":  r1a["micro_precision"],
            "micro_recall":     r1a["micro_recall"],
        },
        "task1b": {
            "micro_f1":               r1b["micro_f1"],
            "macro_f1":               r1b["macro_f1"],
            "micro_precision":        r1b["micro_precision"],
            "micro_recall":           r1b["micro_recall"],
            "direction_reverse_rate": drr,
            "reversed_count":         rev_cnt,
            "denominator_count":      denom,
            "ambiguous_count":        amb,
        },
    }


# ============================================================
# MAIN
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser(description="FEHU Task-1 Prompt-only OAI Pipeline (post-audit).")
    ap.add_argument("--mode", choices=["dev", "test"], default="dev")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only first N articles (debug). "
                         "Dev gold is filtered to those guids for fair scoring.")
    ap.add_argument("--model", type=str, default=DEFAULT_MODEL,
                    help=f"OpenAI model to use (default: {DEFAULT_MODEL})")
    ap.add_argument("--api_key", type=str, default=None,
                    help="OpenAI API key (or set OPENAI_API_KEY env var).")
    ap.add_argument("--output_dir", type=str, default=None,
                    help="Override output directory. "
                         "Default: output/task1_prompt_openai_{model_slug}/")
    ap.add_argument("--version", type=str, default=None,
                    help="Optional version tag appended to the output dir.")
    ap.add_argument("--force_overwrite", action="store_true",
                    help="Overwrite existing predictions instead of writing "
                         "to a timestamped sibling folder.")
    return ap.parse_args()


def main():
    args = parse_args()

    # ── Validate model + API key ────────────────────────────────────────────
    model_name = args.model
    slug       = model_slug(model_name)

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OpenAI API key provided.")
        print("  Pass --api_key or set OPENAI_API_KEY in the environment.")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    # ── Resolve output dir (overwrite-safe) ─────────────────────────────────
    if args.output_dir:
        out_root = Path(args.output_dir)
        if not out_root.is_absolute():
            out_root = BASE_DIR / out_root
    else:
        suffix = f"_{args.version}" if args.version else ""
        out_root = BASE_DIR / "output" / f"task1_prompt_{PROVIDER}_{slug}{suffix}"

    OUTPUT_DIR, used_fallback = safe_output_dir(out_root, args.force_overwrite)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Resolve cache path (provider + model keyed) ─────────────────────────
    cache_filename = f"cache_{args.mode}_{PROVIDER}_{slug}.json"
    cache_path     = LOGS_DIR / cache_filename

    # ── Load taxonomy + globals for prompt builders ─────────────────────────
    global l1_name_to_id, l2_name_to_id, l1_id_to_l2_id
    l1_name_to_id, l2_name_to_id, l1_id_to_l2_id = load_taxonomy()

    # ── Load articles ───────────────────────────────────────────────────────
    if args.mode == "dev":
        articles_path = DEV_ARTICLES
        print("Mode: DEV (will evaluate against gold labels)")
    else:
        articles_path = TEST_ARTICLES
        print("Mode: TEST (will produce submission files; no evaluation)")

    with open(articles_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if args.limit:
        articles = articles[:args.limit]
    processed_guids = {str(a["guid"]) for a in articles}

    print(f"Provider:  {PROVIDER}")
    print(f"Model:     {model_name}  (slug: {slug})")
    print(f"Articles:  {len(articles)}")
    print(f"Output:    {OUTPUT_DIR}")
    if used_fallback:
        print(f"  [INFO] Target folder existed → wrote to timestamped sibling.")
    print(f"Cache:     {cache_path.name}")

    # ── Few-shot + system prompt ────────────────────────────────────────────
    print("Loading few-shot examples from training data...")
    few_shot_examples = load_few_shot_examples(n=2)
    print(f"Loaded {len(few_shot_examples)} few-shot examples")
    system_prompt = build_system_prompt(few_shot_examples)

    # ── Cache ───────────────────────────────────────────────────────────────
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            print(f"Loaded cache: {len(cache)} entries")
        except json.JSONDecodeError:
            print("  [WARN] Cache file corrupted; starting fresh.")
            cache = {}

    # ── Process articles ────────────────────────────────────────────────────
    all_task1a = []
    all_task1b = []

    for article in tqdm(articles, desc="Processing articles"):
        guid = str(article["guid"])

        cached = cache.get(guid)
        # Per-entry provider+model guard so future cache reuse is safe even
        # if filenames are ever consolidated.
        use_cache = (
            isinstance(cached, dict)
            and cached.get("provider") == PROVIDER
            and cached.get("model") == model_name
            and "result" in cached
        )
        if use_cache:
            gpt_results = cached["result"]
        else:
            user_prompt = build_user_prompt(article)
            gpt_results = call_gpt(client, system_prompt, user_prompt, guid, model_name)
            cache[guid] = {
                "guid":     guid,
                "provider": PROVIDER,
                "model":    model_name,
                "result":   gpt_results,
            }
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

        task1a_values, task1b_values = process_results(guid, article["actors"], gpt_results)
        all_task1a.append({"guid": guid, "article_human_values": task1a_values})
        all_task1b.append({"guid": guid, "article_human_values": task1b_values})

    # ── Write predictions ───────────────────────────────────────────────────
    task1a_path = OUTPUT_DIR / "pred_task1a.json"
    task1b_path = OUTPUT_DIR / "pred_task1b.json"
    task1a_path.write_text(json.dumps(all_task1a, ensure_ascii=False, indent=2), encoding="utf-8")
    task1b_path.write_text(json.dumps(all_task1b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved Task-1a → {task1a_path}")
    print(f"Saved Task-1b → {task1b_path}")

    total_1a = sum(len(x["article_human_values"]) for x in all_task1a)
    total_1b = sum(len(x["article_human_values"]) for x in all_task1b)
    n = max(len(articles), 1)
    print(f"Stats: 1a={total_1a} ({total_1a/n:.1f}/article)  "
          f"1b={total_1b} ({total_1b/n:.1f}/article)")

    # ── run_config.json ─────────────────────────────────────────────────────
    run_config = {
        "script":         "src/run_pipeline.py",
        "method":         METHOD_NAME,
        "provider":       PROVIDER,
        "model":          model_name,
        "model_slug":     slug,
        "version":        args.version,
        "mode":           args.mode,
        "limit":          args.limit,
        "is_limit_run":   bool(args.limit),
        "output_dir":     str(OUTPUT_DIR),
        "cache_path":     str(cache_path),
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "git_commit":     current_git_commit(),
        "command_line":   " ".join(shlex.quote(a) for a in sys.argv),
        "dataset_paths": {
            "train_articles": str(TRAIN_ARTICLES),
            "dev_articles":   str(DEV_ARTICLES),
            "test_articles":  str(TEST_ARTICLES),
            "train_labels":   str(TRAIN_LABELS),
            "dev_labels":     str(DEV_LABELS),
            "l1_values":      str(L1_VALUES_PATH),
            "l2_values":      str(L2_VALUES_PATH),
            "l1_to_l2":       str(L1_TO_L2_PATH),
        },
        "prompt_template_hash": stable_text_hash(system_prompt),
        "taxonomy_hash":        stable_text_hash(json.dumps(
            {"l1": l1_name_to_id, "l2": l2_name_to_id}, sort_keys=True
        )),
        "stats": {
            "n_articles":         n,
            "total_predictions_1a": total_1a,
            "total_predictions_1b": total_1b,
        },
        "notes": (
            "Prompt-only OAI pipeline (post-audit). "
            "--model now flows into the API call; cache and output dir are "
            "model-keyed; --limit filters the dev gold for fair scoring."
        ),
    }
    (OUTPUT_DIR / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Evaluation (dev only) ───────────────────────────────────────────────
    if args.mode == "dev":
        print("\n" + "=" * 60)
        print("DEV EVALUATION")
        print("=" * 60)
        filter_guids = processed_guids if args.limit else None
        metrics = run_dev_evaluation(task1a_path, task1b_path, filter_guids)
        (OUTPUT_DIR / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nMetrics saved → {OUTPUT_DIR / 'metrics.json'}")
    else:
        print("Test mode: skipped evaluation.")


if __name__ == "__main__":
    main()
