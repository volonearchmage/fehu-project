"""E6 Stage-0: taxonomy-blind self-segmentation of articles into subevents.

Produces the segments.json that run_pipeline_e6.py consumes in place of
dataset subevents. The segmentation prompt must never see the value taxonomy
or the actor list (it must not be able to smuggle label hints into the
segmentation), and this is enforced by offline_check_e6.py.

Usage:
  python run_segmentation_e6.py --mode dev \
      --out RH_test/E6_e3a_self_segmentation/runs/<ts>/segments.json

Fail-fast policy: any article whose segmentation cannot be parsed/validated
after MAX_RETRIES aborts the whole run (partial output is written to the
cache so a re-run resumes, but segments.json is only written when every
article has a valid segmentation). No fallback to dataset subevents, ever.
"""

import argparse
import json
import os
import sys
import time

from tqdm import tqdm

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEV_ARTICLES = os.path.join(BASE_DIR, "dataset", "dev", "dev_event_base.json")
TEST_ARTICLES = os.path.join(BASE_DIR, "dataset", "test",
                             "test_article_event_base.json")

DEFAULT_MODEL = "deepseek-v4-flash"
TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 4000
REQUEST_TIMEOUT = 120
MAX_RETRIES = 5
MIN_UNITS = 2      # official dev range is 2..20 (median 9)
MAX_UNITS = 30     # hard ceiling; pathological outputs abort

SEGMENTATION_SYSTEM_PROMPT = """You are an expert news editor. Your task is to segment a news article into its component subevents (event units).

RULES:
1. Read the whole article and break it into numbered subevents, in the order they appear in the article.
2. Each subevent is ONE distinct event, action, statement, or development described in the article, written as a single self-contained sentence (a close paraphrase of the article's wording is fine).
3. Aim for 6-12 subevents for a typical article; use fewer for very short articles and more for very long ones. Never fewer than 2 and never more than 30.
4. Together the subevents should cover every part of the article that describes something happening; do not skip sections.
5. Only describe what happened. Do not interpret, evaluate, or judge anyone or anything.

OUTPUT FORMAT: Return ONLY a valid JSON object:
{"subevents": [{"id": "0", "subevent": "..."}, {"id": "1", "subevent": "..."}]}
IDs are consecutive integers as strings starting at "0". Do NOT include any text before or after the JSON object. No markdown.
Double quotes and other special characters inside subevent text MUST be validly JSON-escaped."""


def build_segmentation_user_prompt(article):
    # Same truncation rule as the main pipeline, for consistency.
    content = article["content"]
    if len(content) > 12000:
        content = content[:6000] + "\n...[truncated]...\n" + content[-3000:]
    return f"""Title: {article["title"]}

Article:
{content}

Segment this article into numbered subevents. Return ONLY the JSON object.
The output MUST contain at most 30 subevents. If you identify more than 30,
merge closely related developments until no more than 30 remain."""


def parse_and_validate(content, guid):
    """Parse the model's JSON and normalize into [{id, subevent}, ...].

    Raises ValueError on anything invalid — the caller retries / aborts.
    """
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    data = json.loads(content)
    if not isinstance(data, dict) or "subevents" not in data:
        raise ValueError(f"{guid}: no 'subevents' key")
    ses = data["subevents"]
    if not isinstance(ses, list):
        raise ValueError(f"{guid}: 'subevents' is not a list")
    if not (MIN_UNITS <= len(ses) <= MAX_UNITS):
        raise ValueError(f"{guid}: {len(ses)} units outside "
                         f"[{MIN_UNITS}, {MAX_UNITS}]")
    out = []
    for i, se in enumerate(ses):
        if not isinstance(se, dict):
            raise ValueError(f"{guid}: unit {i} not an object")
        text = se.get("subevent")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{guid}: unit {i} has empty text")
        # normalize ids to consecutive strings, official style
        out.append({"id": str(i), "subevent": text.strip()})
    return out


def segment_article(client, model_name, article):
    guid = article["guid"]
    user_prompt = build_segmentation_user_prompt(article)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SEGMENTATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
                timeout=REQUEST_TIMEOUT,
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content.strip()
            if not content:
                raise ValueError("empty content")
            return parse_and_validate(content, guid), content
        except Exception as e:  # noqa: BLE001 — retried, then fatal
            last_err = e
            print(f"  [WARN] {guid}: segmentation attempt {attempt + 1} "
                  f"failed: {e}")
            if attempt < MAX_RETRIES - 1:
                if "units outside" in str(e):
                    user_prompt += (
                        "\nThe previous segmentation was too fine-grained. "
                        "Merge related developments and return 6-20 subevents."
                    )
                if isinstance(e, json.JSONDecodeError):
                    user_prompt += (
                        "\nThe previous response was malformed JSON. Use short "
                        "plain sentences and JSON-escape every internal quote."
                    )
                time.sleep(3)
    raise RuntimeError(f"ABORT: segmentation failed for {guid} after "
                       f"{MAX_RETRIES} attempts: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dev", "test"], default="dev")
    ap.add_argument("--model", type=str, default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=str, required=True,
                    help="output segments.json path")
    args = ap.parse_args()

    if os.path.exists(args.out):
        sys.exit(f"ABORT: {args.out} already exists — refusing to overwrite")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("ERROR: DEEPSEEK_API_KEY not set")
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    path = DEV_ARTICLES if args.mode == "dev" else TEST_ARTICLES
    with open(path, "r", encoding="utf-8") as f:
        articles = json.load(f)
    if args.limit:
        articles = articles[:args.limit]
    print(f"Segmenting {len(articles)} {args.mode} articles "
          f"with {args.model}")

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    cache_path = os.path.join(out_dir, f"segmentation_cache_{args.mode}.json")
    raw_path = os.path.join(out_dir, f"segmentation_raw_{args.mode}.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Loaded segmentation cache with {len(cache)} articles")

    segments = {}
    raw_f = open(raw_path, "a", encoding="utf-8")
    for article in tqdm(articles, desc="Segmenting"):
        guid = article["guid"]
        if guid in cache:
            segments[guid] = cache[guid]
            continue
        parsed, raw = segment_article(client, args.model, article)
        segments[guid] = parsed
        cache[guid] = parsed
        raw_f.write(json.dumps({"guid": guid, "raw": raw},
                               ensure_ascii=False) + "\n")
        raw_f.flush()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    raw_f.close()

    counts = sorted(len(v) for v in segments.values())
    dist = {
        "n_articles": len(segments),
        "units_min": counts[0],
        "units_median": counts[len(counts) // 2],
        "units_max": counts[-1],
        "units_mean": round(sum(counts) / len(counts), 2),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "E6_e3a_self_segmentation",
            "stage": "0_self_segmentation",
            "mode": args.mode,
            "segmenter_model": args.model,
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "taxonomy_blind": True,
            "unit_distribution": dist,
            "segments": segments,
        }, f, ensure_ascii=False, indent=2)
    print(f"[done] {len(segments)} segmentations -> {args.out}")
    print(f"unit distribution: {dist}")


if __name__ == "__main__":
    main()
