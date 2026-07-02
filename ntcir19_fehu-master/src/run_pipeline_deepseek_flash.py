#!/usr/bin/env python3
"""
Prompt-only DeepSeek V4 Flash pipeline — based on run_pipeline.py.

Identical to run_pipeline.py except:
  - Provider: deepseek (OpenAI-compatible API, base_url="https://api.deepseek.com")
  - Model: deepseek-v4-flash
  - API key: DEEPSEEK_API_KEY (never OPENAI_API_KEY)
  - Output: output/task1_prompt_deepseek_v4_flash/
  - Cache: logs/cache_dev_deepseek_v4_flash.json

Prompt structure, taxonomy, post-processing, and evaluation are unchanged.
Run from project root:
    python src/run_pipeline_deepseek_flash.py --mode dev --limit 5
    python src/run_pipeline_deepseek_flash.py --mode dev --limit 20
    python src/run_pipeline_deepseek_flash.py --mode dev
    python src/run_pipeline_deepseek_flash.py --mode test
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from evaluation import (
    parse_task1a, parse_task1b, evaluate,
    l2_universe, l1_dir_universe,
    direction_reverse_rate_gold_excl,
)

# ── Config ────────────────────────────────────────────────────────────────────
PROVIDER       = "deepseek"
MODEL          = "deepseek-v4-flash"
TEMPERATURE    = 0.1
MAX_RETRIES    = 3
METHOD_VERSION = "prompt_deepseek_v4_flash"

# ── Paths ─────────────────────────────────────────────────────────────────────
TEST_ARTICLES  = BASE_DIR / "dataset/test/test_article_event_base.json"
DEV_ARTICLES   = BASE_DIR / "dataset/dev/dev_event_base.json"
TRAIN_ARTICLES = BASE_DIR / "dataset/train/train_event_base.json"
TRAIN_LABELS   = BASE_DIR / "dataset/gold_labels/train/train_human_values.json"
DEV_LABELS     = BASE_DIR / "dataset/gold_labels/dev/dev_human_values.json"

HV_DIR         = BASE_DIR / "dataset/hv_categories"
L1_VALUES_PATH = HV_DIR / "human_value_level1_values.json"
L2_VALUES_PATH = HV_DIR / "human_value_level2_values.json"
L1_TO_L2_PATH  = HV_DIR / "level_1_to_level_2.json"

OUTPUT_DIR = BASE_DIR / "output/task1_prompt_deepseek_v4_flash"
LOGS_DIR   = BASE_DIR / "logs"

# Comparison method directories (for the evaluation table)
COMPARE_DIRS = {
    "Prompt OAI":       BASE_DIR / "output/task1_prompt",
    "DeBERTa-only":     BASE_DIR / "output/task1_deberta",
    "Hybrid v1":        BASE_DIR / "output/task1_hybrid",
    "Hybrid v2 DS Pro": BASE_DIR / "output/task1_hybrid_v2_deepseek_deepseek_v4_pro",
    "Hybrid v2 DS Fl":  BASE_DIR / "output/task1_hybrid_v2_deepseek_deepseek_v4_flash",
}


# ── Taxonomy ──────────────────────────────────────────────────────────────────
def load_taxonomy():
    """Copied verbatim from run_pipeline.py."""
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


# ── Few-shot examples ─────────────────────────────────────────────────────────
def load_few_shot_examples(n=2):
    """Copied verbatim from run_pipeline.py (uses l1_name_to_id global)."""
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


# ── Prompts (copied verbatim from run_pipeline.py) ────────────────────────────
def build_system_prompt(few_shot_examples):
    """Copied verbatim from run_pipeline.py (uses l1_name_to_id global)."""
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
    """Copied verbatim from run_pipeline.py."""
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


# ── API key ───────────────────────────────────────────────────────────────────
def resolve_api_key(args):
    if args.api_key:
        return args.api_key
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


# ── LLM call (adapted from run_pipeline.py call_gpt) ─────────────────────────
def call_llm(client, system_prompt, user_prompt, article_guid):
    """
    Returns (result_list, success, error).
    Adapted from run_pipeline.py call_gpt() for DeepSeek:
      - extra_body disables chain-of-thought to avoid JSON parse failures
      - max_tokens instead of max_completion_tokens for cross-provider compatibility
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=4000,
                extra_body={"thinking": {"type": "disabled"}},
            )

            content = response.choices[0].message.content.strip()

            # Strip markdown fences (copied from run_pipeline.py)
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            if not isinstance(result, list):
                print(f"  [WARN] {article_guid}: Response is not a list, wrapping it")
                result = [result]
            return result, True, None

        except json.JSONDecodeError as e:
            print(f"  [WARN] {article_guid}: JSON parse error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)

        except Exception as e:
            print(f"  [ERROR] {article_guid}: API error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(5)

    print(f"  [FAIL] {article_guid}: All retries failed, returning empty")
    return [], False, "all retries failed"


# ── Post-processing (copied verbatim from run_pipeline.py process_results) ────
def process_results(article_guid, actors, gpt_results):
    """Copied verbatim from run_pipeline.py (uses l1_id_to_l2_id global)."""
    valid_actor_ids = set()
    for actor_dict in actors:
        for name, aid in actor_dict.items():
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
            task1b_values.append({"actor": actor_id, "l1_value": l1_id, "direction": direction})

    return task1a_values, task1b_values


# ── Evaluation ────────────────────────────────────────────────────────────────
def _filter(d, guids):
    return {k: v for k, v in d.items() if k[0] in guids} if guids else d


def eval_result(pred_1a_path, pred_1b_path, processed_guids=None):
    """Evaluate a result set. Returns metrics dict, or None if files missing."""
    pred_1a_path = Path(pred_1a_path)
    pred_1b_path = Path(pred_1b_path)
    if not pred_1a_path.exists() or not pred_1b_path.exists():
        return None

    g1a = _filter(parse_task1a(str(DEV_LABELS)), processed_guids)
    p1a = _filter(parse_task1a(str(pred_1a_path)), processed_guids)
    g1b = _filter(parse_task1b(str(DEV_LABELS)), processed_guids)
    p1b = _filter(parse_task1b(str(pred_1b_path)), processed_guids)

    r1a = evaluate(g1a, p1a, l2_universe())
    r1b = evaluate(g1b, p1b, l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b, p1b)

    total_1a = sum(len(v) for v in p1a.values())
    total_1b = sum(len(v) for v in p1b.values())
    n_arts   = max(len({k[0] for k in g1a}), 1)

    return {
        "task1a": {
            "micro_f1":        r1a["micro_f1"],
            "macro_f1":        r1a["macro_f1"],
            "micro_precision": r1a["micro_precision"],
            "micro_recall":    r1a["micro_recall"],
        },
        "task1b": {
            "micro_f1":               r1b["micro_f1"],
            "macro_f1":               r1b["macro_f1"],
            "micro_precision":        r1b["micro_precision"],
            "micro_recall":           r1b["micro_recall"],
            "direction_reverse_rate": drr,
            "reversed_count":         rev,
            "denominator_count":      den,
            "ambiguous_count":        amb,
        },
        "total_task1a_predictions":      total_1a,
        "total_task1b_predictions":      total_1b,
        "avg_task1a_per_article":        round(total_1a / n_arts, 2),
        "avg_task1b_per_article":        round(total_1b / n_arts, 2),
    }


# ── Comparison table ──────────────────────────────────────────────────────────
def format_comparison_table(all_metrics):
    col_w  = [18, 9, 9, 9, 9, 11, 8, 8]
    header = ["Method", "1a MiF1", "1a MaF1", "1b MiF1", "1b MaF1",
              "Precision", "Recall", "DRR"]

    def row(cells):
        return "| " + " | ".join(str(c).ljust(w - 2) for c, w in zip(cells, col_w)) + " |"

    sep   = "+" + "+".join("-" * w for w in col_w) + "+"
    lines = [sep, row(header), sep]

    order = [
        ("Prompt OAI",       "Prompt OAI"),
        ("Prompt DS Flash",  "Prompt DS Flash"),
        ("DeBERTa-only",     "DeBERTa-only"),
        ("Hybrid v1",        "Hybrid v1"),
        ("Hybrid v2 DS Pro", "Hybrid v2 DS Pro"),
        ("Hybrid v2 DS Fl",  "Hybrid v2 DS Fl"),
    ]
    for label, key in order:
        m = all_metrics.get(key)
        if m is None:
            lines.append(row([label] + ["N/A"] * 7))
        else:
            a, b = m["task1a"], m["task1b"]
            lines.append(row([
                label,
                f"{a['micro_f1']:.4f}",
                f"{a['macro_f1']:.4f}",
                f"{b['micro_f1']:.4f}",
                f"{b['macro_f1']:.4f}",
                f"{b['micro_precision']:.4f}",
                f"{b['micro_recall']:.4f}",
                f"{b['direction_reverse_rate']:.4f}",
            ]))
    lines.append(sep)
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    ap = argparse.ArgumentParser(description="Prompt-only DeepSeek V4 Flash pipeline")
    ap.add_argument("--mode",    choices=["dev", "test"], default="dev")
    ap.add_argument("--limit",   type=int,  default=None,
                    help="Process only N articles (debug mode)")
    ap.add_argument("--api_key", default=None,
                    help="DeepSeek API key (or set DEEPSEEK_API_KEY env var / .env file)")
    return ap.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # Taxonomy globals — must be set before load_few_shot_examples / build_system_prompt
    global l1_name_to_id, l2_name_to_id, l1_id_to_l2_id
    l1_name_to_id, l2_name_to_id, l1_id_to_l2_id = load_taxonomy()

    print(f"mode={args.mode}  provider={PROVIDER}  model={MODEL}  limit={args.limit}")
    print(f"  output_dir={OUTPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Articles
    articles_path = DEV_ARTICLES if args.mode == "dev" else TEST_ARTICLES
    articles = json.loads(articles_path.read_text(encoding="utf-8"))
    if args.limit:
        articles = articles[:args.limit]
    processed_guids = {str(a["guid"]) for a in articles}
    print(f"Loaded {len(articles)} articles")

    # Few-shot + system prompt (identical to run_pipeline.py)
    print("Loading few-shot examples from training data...")
    few_shot = load_few_shot_examples(n=2)
    print(f"Loaded {len(few_shot)} few-shot examples")
    system_prompt = build_system_prompt(few_shot)

    # API key + client
    api_key = resolve_api_key(args)
    if not api_key:
        print("\nERROR: No DeepSeek API key found.")
        print("  Options:")
        print("    export DEEPSEEK_API_KEY=your_key_here")
        print("    python src/run_pipeline_deepseek_flash.py --api_key your_key_here")
        print("    Add DEEPSEEK_API_KEY=... to .env in project root")
        sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    # Cache
    cache_path = LOGS_DIR / f"cache_{args.mode}_deepseek_v4_flash.json"
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            print(f"Loaded cache ({len(cache)} entries): {cache_path.name}")
        except json.JSONDecodeError:
            print(f"  Warning: cache corrupted, starting fresh: {cache_path}")

    # Process articles
    all_task1a, all_task1b = [], []

    for article in tqdm(articles, desc="Processing articles"):
        guid = str(article["guid"])

        # Cache reuse requires matching provider + model + success
        cached   = cache.get(guid)
        use_cache = (
            cached is not None
            and cached.get("success")
            and cached.get("provider") == PROVIDER
            and cached.get("model") == MODEL
        )

        if use_cache:
            gpt_results = cached["result"]
        else:
            user_prompt = build_user_prompt(article)
            gpt_results, success, error = call_llm(
                client, system_prompt, user_prompt, guid
            )
            cache[guid] = {
                "guid":     guid,
                "provider": PROVIDER,
                "model":    MODEL,
                "result":   gpt_results,
                "success":  success,
                "error":    error,
            }
            cache_path.write_text(
                json.dumps(cache, ensure_ascii=False), encoding="utf-8"
            )

        task1a_values, task1b_values = process_results(guid, article["actors"], gpt_results)
        all_task1a.append({"guid": guid, "article_human_values": task1a_values})
        all_task1b.append({"guid": guid, "article_human_values": task1b_values})

    # Save predictions
    pred_1a_path = OUTPUT_DIR / "pred_task1a.json"
    pred_1b_path = OUTPUT_DIR / "pred_task1b.json"
    pred_1a_path.write_text(
        json.dumps(all_task1a, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pred_1b_path.write_text(
        json.dumps(all_task1b, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nPredictions saved → {OUTPUT_DIR}/")

    # Stats
    total_1a = sum(len(x["article_human_values"]) for x in all_task1a)
    total_1b = sum(len(x["article_human_values"]) for x in all_task1b)
    n = len(articles)
    print(f"Stats: 1a={total_1a} ({total_1a/n:.1f}/art)"
          f"  1b={total_1b} ({total_1b/n:.1f}/art)")

    # run_config.json
    run_config = {
        "method":     "prompt_only",
        "provider":   PROVIDER,
        "model":      MODEL,
        "version":    METHOD_VERSION,
        "output_dir": str(OUTPUT_DIR),
        "cache_path": str(cache_path),
        "mode":       args.mode,
        "limit":      args.limit,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "notes":      (
            "Prompt-only pipeline based on run_pipeline.py, "
            "with only LLM provider/model changed to DeepSeek V4 Flash."
        ),
    }
    (OUTPUT_DIR / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Evaluation (dev only)
    if args.mode != "dev":
        print("Test mode: skipping evaluation.")
        return

    filter_guids = processed_guids if args.limit else None
    print("\n[Evaluation]")
    all_metrics = {}

    # Current run
    m = eval_result(pred_1a_path, pred_1b_path, filter_guids)
    if m:
        all_metrics["Prompt DS Flash"] = m
        print(f"  Prompt DS Flash: 1a micro={m['task1a']['micro_f1']:.4f}"
              f"  1b micro={m['task1b']['micro_f1']:.4f}"
              f"  DRR={m['task1b']['direction_reverse_rate']:.4f}")

    # Comparison methods
    for label, comp_dir in COMPARE_DIRS.items():
        m = eval_result(
            comp_dir / "pred_task1a.json",
            comp_dir / "pred_task1b.json",
            filter_guids,
        )
        if m is None:
            print(f"  {label}: prediction files not found, skipping.")
        else:
            all_metrics[label] = m
            print(f"  {label}: 1a micro={m['task1a']['micro_f1']:.4f}"
                  f"  1b micro={m['task1b']['micro_f1']:.4f}"
                  f"  DRR={m['task1b']['direction_reverse_rate']:.4f}")

    # Save metrics
    (OUTPUT_DIR / "metrics.json").write_text(
        json.dumps(all_metrics.get("Prompt DS Flash", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Comparison table
    table = format_comparison_table(all_metrics)
    print("\n" + table)
    (OUTPUT_DIR / "comparison_table.txt").write_text(table + "\n", encoding="utf-8")
    print(f"\nAll results saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
