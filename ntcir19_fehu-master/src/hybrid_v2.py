#!/usr/bin/env python3
"""
Hybrid v2 pipeline: DeBERTa value-only candidates + LLM direction assignment.

Design rationale vs v1:
  v1: DeBERTa predicts (value, direction) candidates; LLM keeps or removes.
      DeBERTa direction errors are directly inherited when the LLM keeps a candidate.
  v2: DeBERTa predicts VALUE-ONLY candidates (max score over both directions).
      LLM verifies relevance for each actor and assigns direction itself.
      DeBERTa direction errors are no longer directly inherited because the LLM
      assigns direction from scratch for each kept value candidate.

Research hypothesis:
  DeBERTa-only: high recall, lower precision, high DRR.
  Prompt-only:  high precision, lower recall, low DRR.
  Hybrid v2:    targets DeBERTa recall + reduced DRR by delegating direction to LLM.
                May or may not exceed prompt-only; diagnostics are saved for analysis.

Run from project root:
    python src/hybrid_v2.py --mode dev --limit 5
    python src/hybrid_v2.py --mode dev
    python src/hybrid_v2.py --mode dev --provider openai --model gpt-4o
    python src/hybrid_v2.py --mode dev --provider deepseek
    python src/hybrid_v2.py --mode test --provider deepseek --model deepseek-v4-flash
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer
from peft import PeftModel
from openai import OpenAI
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from train_deberta import (
    ValueClassifier,
    MODEL_NAME,
    NUM_LABELS,
    MAX_LENGTH,
    CHECKPOINT_DIR,
)

from evaluation import (
    parse_task1a,
    parse_task1b,
    evaluate,
    l2_universe,
    l1_dir_universe,
    direction_reverse_rate_gold_excl,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
DEV_ARTICLES  = BASE_DIR / "dataset/dev/dev_event_base.json"
DEV_LABELS    = BASE_DIR / "dataset/gold_labels/dev/dev_human_values.json"
TEST_ARTICLES = BASE_DIR / "dataset/test/test_article_event_base.json"
L1_FILE       = BASE_DIR / "dataset/hv_categories/human_value_level1_values.json"
L2_FILE       = BASE_DIR / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_FILE = BASE_DIR / "dataset/hv_categories/level_1_to_level_2.json"
LOGS_DIR      = BASE_DIR / "logs"

COMPARE_DIRS = {
    "Prompt-only":  BASE_DIR / "output/task1_prompt",
    "DeBERTa-only": BASE_DIR / "output/task1_deberta",
    "Hybrid v1":    BASE_DIR / "output/task1_hybrid",
}

HYBRID_V2_DIRS = {
    "Hybrid v2 OAI":      BASE_DIR / "output/task1_hybrid_v2_openai_gpt_4o_mini",
    "Hybrid v2 DS Pro":   BASE_DIR / "output/task1_hybrid_v2_deepseek_deepseek_v4_pro",
    "Hybrid v2 DS Flash": BASE_DIR / "output/task1_hybrid_v2_deepseek_deepseek_v4_flash",
}

CONTENT_LIMIT = 10_000
N_L1 = NUM_LABELS // 2   # 54


# ── Taxonomy ──────────────────────────────────────────────────────────────────
def load_taxonomy():
    """Return (l1_id_to_name, l1_id_to_l2_id, l2_id_to_name)."""
    l1_name_to_id = json.loads(L1_FILE.read_text(encoding="utf-8"))
    l2_name_to_id = json.loads(L2_FILE.read_text(encoding="utf-8"))
    raw = json.loads(L1_TO_L2_FILE.read_text(encoding="utf-8"))["level_1_to_level_2"]
    l1_id_to_name  = {v: k for k, v in l1_name_to_id.items()}
    l1_id_to_l2_id = {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}
    l2_id_to_name  = {v: k for k, v in l2_name_to_id.items()}
    return l1_id_to_name, l1_id_to_l2_id, l2_id_to_name


# ── API key ───────────────────────────────────────────────────────────────────
def resolve_api_key(args):
    if args.api_key:
        return args.api_key
    env_var = "DEEPSEEK_API_KEY" if args.provider == "deepseek" else "OPENAI_API_KEY"
    key = os.environ.get(env_var, "")
    if key:
        return key
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{env_var}="):
                return line.split("=", 1)[1].strip()
    return ""


def model_slug(model_name):
    return model_name.replace("-", "_").replace(".", "_")


# ── Data preparation ──────────────────────────────────────────────────────────
def load_articles(mode, limit=None):
    path = DEV_ARTICLES if mode == "dev" else TEST_ARTICLES
    arts = json.loads(path.read_text(encoding="utf-8"))
    return arts[:limit] if limit else arts


def prepare_data(articles):
    """
    Returns:
      examples         – list of {guid, actor_id, actor_name, text} for DataLoader
      articles_by_guid – {guid: {guid, title, content, id2name}}
    """
    articles_by_guid = {}
    examples = []
    for art in articles:
        guid    = str(art["guid"])
        title   = art.get("title", "")
        content = art.get("content", "")
        text    = f"Title: {title}\n{content}"  # tokenizer handles truncation
        id2name = {
            str(aid): name
            for d in art.get("actors", [])
            for name, aid in d.items()
        }
        articles_by_guid[guid] = {
            "guid": guid, "title": title, "content": content, "id2name": id2name,
        }
        for actor_id, actor_name in id2name.items():
            examples.append({
                "guid": guid, "actor_id": actor_id,
                "actor_name": actor_name, "text": text,
            })
    return examples, articles_by_guid


class InferDataset(Dataset):
    def __init__(self, examples, tokenizer):
        self.examples = examples
        self.tok = tokenizer

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, i):
        ex  = self.examples[i]
        enc = self.tok(
            ex["text"], ex["actor_name"],
            truncation="only_first", max_length=MAX_LENGTH,
            padding="max_length", return_tensors="pt",
        )
        item = {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "guid":           ex["guid"],
            "actor_id":       ex["actor_id"],
            "actor_name":     ex["actor_name"],
        }
        if "token_type_ids" in enc:
            item["token_type_ids"] = enc["token_type_ids"].squeeze(0)
        return item


# ── DeBERTa loading ───────────────────────────────────────────────────────────
def load_deberta(device):
    print("Loading DeBERTa checkpoint...")
    base  = AutoModel.from_pretrained(MODEL_NAME)
    enc   = PeftModel.from_pretrained(base, str(CHECKPOINT_DIR))
    model = ValueClassifier(enc, base.config.hidden_size).to(device)
    model.classifier.load_state_dict(
        torch.load(CHECKPOINT_DIR / "classifier.pt", map_location=device, weights_only=True)
    )
    model.eval()
    return model


# ── Value-only candidate generation ──────────────────────────────────────────
@torch.no_grad()
def run_value_only_inference(model, loader, device, args, l1_id_to_name, articles, articles_by_guid):
    """
    For each (article, actor) pair:
      value_score[l1] = max(contradictory_score, aligned_score)
    Selects candidates by threshold | top_k union, sorted and capped.

    Returns article_candidates: list matching original article order.
    [{"guid", "title", "actors": [{"actor_id", "actor_name", "candidates"}]}]
    """
    per_actor = {}  # (guid, actor_id) -> candidates list

    for batch in tqdm(loader, desc="DeBERTa inference"):
        ids   = batch["input_ids"].to(device)
        mask  = batch["attention_mask"].to(device)
        ttids = batch.get("token_type_ids")
        if ttids is not None:
            ttids = ttids.to(device)
        probs = torch.sigmoid(model(ids, mask, ttids)).cpu().float()  # (B, 108)

        for i in range(probs.size(0)):
            p          = probs[i]
            guid       = batch["guid"][i]
            actor_id   = batch["actor_id"][i]
            actor_name = batch["actor_name"][i]

            contra_scores  = p[0::2]  # shape (54,): indices 0,2,…,106
            aligned_scores = p[1::2]  # shape (54,): indices 1,3,…,107
            value_scores   = torch.max(contra_scores, aligned_scores)  # (54,)

            thresh_idxs = set(
                value_scores.ge(args.deberta_threshold).nonzero(as_tuple=True)[0].tolist()
            )
            k = min(args.top_k, N_L1)
            topk_idxs = set(value_scores.topk(k).indices.tolist())

            union = thresh_idxs | topk_idxs
            union_sorted = sorted(union, key=lambda idx: value_scores[idx].item(), reverse=True)
            union_sorted = union_sorted[:args.max_candidates_per_actor]

            candidates = [
                {
                    "l1_value_id":         str(idx),
                    "l1_value_name":       l1_id_to_name.get(str(idx), f"value_{idx}"),
                    "confidence":          round(value_scores[idx].item(), 6),
                    "aligned_score":       round(aligned_scores[idx].item(), 6),
                    "contradictory_score": round(contra_scores[idx].item(), 6),
                }
                for idx in union_sorted
            ]
            per_actor[(guid, actor_id)] = candidates

    # Regroup by article in original order
    article_candidates = []
    for art in articles:
        guid     = str(art["guid"])
        art_info = articles_by_guid[guid]
        actors   = []
        for actor_id, actor_name in art_info["id2name"].items():
            if (guid, actor_id) in per_actor:
                actors.append({
                    "actor_id":   actor_id,
                    "actor_name": actor_name,
                    "candidates": per_actor[(guid, actor_id)],
                })
        article_candidates.append({
            "guid":   guid,
            "title":  art_info["title"],
            "actors": actors,
        })
    return article_candidates


# ── Cache utilities ───────────────────────────────────────────────────────────
def compute_candidate_hash(actor_entries):
    """
    Hash based on actor_id + sorted l1_value_ids so threshold/top_k changes
    invalidate the cache.
    """
    hashable = sorted(
        [
            {
                "actor_id":    e["actor_id"],
                "l1_value_ids": sorted(c["l1_value_id"] for c in e["candidates"]),
            }
            for e in actor_entries
        ],
        key=lambda x: x["actor_id"],
    )
    return hashlib.md5(json.dumps(hashable).encode("utf-8")).hexdigest()


def make_cache_key(guid, candidate_hash, provider, model):
    return f"{guid}||{candidate_hash}||{provider}||{model}"


def load_cache(cache_path):
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  Warning: cache file corrupted, starting fresh: {cache_path}")
    return {}


def save_cache(cache, cache_path):
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


# ── LLM prompts ───────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are an expert in human value analysis for news articles.

You will receive:
1. A news article.
2. A list of actors.
3. For each actor, a list of candidate human values produced by a classifier.

Your task:
For each candidate value, decide whether the article provides direct or strongly implied evidence that this value is relevant to the specific actor.

Important rules:
- Only keep a candidate if the evidence is connected to the specific actor.
- Do not keep a value merely because it is generally related to the article topic.
- Do not transfer evidence from one actor to another actor.
- If the evidence is weak, generic, or only vaguely plausible, remove the candidate.
- For each value you keep, assign exactly one direction:
  "aligned" means the actor's behavior supports, promotes, protects, or expresses this value.
  "contradictory" means the actor's behavior violates, undermines, harms, or conflicts with this value.
- You may keep multiple values for the same actor if each is supported by article evidence.
- You must only select from the provided candidate value IDs.
- Do not invent new actor IDs.
- Do not invent new value IDs.

Output format:
Return only a valid JSON array.
No markdown.
No explanation outside JSON.
Each item must be:
{
  "actor_id": "string",
  "l1_value_id": "string",
  "direction": "aligned" or "contradictory"
}\
"""


def build_user_prompt(article_entry, articles_by_guid):
    art_info = articles_by_guid[article_entry["guid"]]
    content  = art_info["content"]
    if len(content) > CONTENT_LIMIT:
        content = content[:CONTENT_LIMIT]

    lines = [
        "Title:",
        article_entry["title"],
        "",
        "Article:",
        content,
        "",
        "Actors and candidate values:",
    ]
    for entry in article_entry["actors"]:
        lines.append(f"\nActor: {entry['actor_name']} (ID: {entry['actor_id']})")
        lines.append("Candidate values:")
        for c in entry["candidates"]:
            lines.append(
                f"- Value {c['l1_value_id']}: {c['l1_value_name']},"
                f" classifier confidence={c['confidence']:.3f}"
            )

    lines.append(
        "\nPlease return only the JSON array of kept values with assigned direction."
    )
    return "\n".join(lines)


# ── Robust JSON parsing ───────────────────────────────────────────────────────
def extract_json_array(text):
    """Strip fences, find first JSON array, validate it is a list."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("\n")
        end   = len(parts) - 1 if parts[-1].strip() == "```" else len(parts)
        text  = "\n".join(parts[1:end]).strip()
    # Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # Find first balanced JSON array
    start = text.find("[")
    if start >= 0:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(text[start : i + 1])
                        if isinstance(result, list):
                            return result
                    except json.JSONDecodeError:
                        pass
                    break
    return None


# ── LLM API call ──────────────────────────────────────────────────────────────
def call_llm(client, args, user_prompt):
    """
    Returns (response_text, parsed_items, success, error).
    On failure returns ("", [], False, error_message).
    """
    extra_kwargs = {}
    if args.provider == "deepseek":
        extra_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=args.temperature,
                **extra_kwargs,
            )
            raw = resp.choices[0].message.content
            items = extract_json_array(raw)
            if items is None:
                raise ValueError(f"Response is not a JSON array: {raw[:200]}")
            return raw, items, True, None
        except Exception as e:
            err = str(e)
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return "", [], False, err
    return "", [], False, "exhausted retries"


# ── Whitelist and validation ──────────────────────────────────────────────────
def build_whitelist(article_candidates):
    """Return {guid: {actor_id: set_of_l1_value_ids}}."""
    wl = {}
    for art in article_candidates:
        guid = art["guid"]
        wl[guid] = {
            e["actor_id"]: {c["l1_value_id"] for c in e["candidates"]}
            for e in art["actors"]
        }
    return wl


def validate_and_convert(llm_items, guid_whitelist):
    """
    Validate actor_id, l1_value_id, direction.
    Convert "aligned"→"1", "contradictory"→"0".
    Deduplicate by (actor_id, l1_value_id, direction).
    Returns (valid_items, n_invalid).
    """
    valid, n_invalid = [], 0
    seen = set()
    for item in llm_items:
        try:
            actor_id = str(item["actor_id"])
            l1_id    = str(item["l1_value_id"])
            dir_word = str(item["direction"])
        except (KeyError, TypeError):
            n_invalid += 1
            continue

        if actor_id not in guid_whitelist:
            n_invalid += 1
            continue
        if l1_id not in guid_whitelist[actor_id]:
            n_invalid += 1
            continue
        if dir_word not in ("aligned", "contradictory"):
            n_invalid += 1
            continue

        direction = "1" if dir_word == "aligned" else "0"
        key = (actor_id, l1_id, direction)
        if key not in seen:
            seen.add(key)
            valid.append({"actor_id": actor_id, "l1_value_id": l1_id, "direction": direction})

    return valid, n_invalid


# ── Submission format ─────────────────────────────────────────────────────────
def build_submission(verified_by_guid, l1_id_to_l2_id):
    """
    verified_by_guid: {guid: [{actor_id, l1_value_id, direction}]}
    Returns (task1a_list, task1b_list).
    """
    t1a, t1b = [], []
    for guid, items in verified_by_guid.items():
        va, vb, seen_l2 = [], [], set()
        for it in items:
            actor = it["actor_id"]
            l1    = it["l1_value_id"]
            dr    = it["direction"]
            l2    = l1_id_to_l2_id.get(l1, "0")
            vb.append({"actor": actor, "l1_value": l1, "direction": dr})
            if (actor, l2) not in seen_l2:
                seen_l2.add((actor, l2))
                va.append({"actor": actor, "l2_value": l2})
        t1a.append({"guid": guid, "article_human_values": va})
        t1b.append({"guid": guid, "article_human_values": vb})
    return t1a, t1b


# ── Filtered evaluation ───────────────────────────────────────────────────────
def _filter(d, guids):
    return {k: v for k, v in d.items() if k[0] in guids} if guids else d


def eval_result(pred_1a_path, pred_1b_path, processed_guids=None):
    """
    Evaluate a result set. Returns metrics dict, or None if files missing.
    Filters to processed_guids when --limit is active.
    """
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
            "micro_f1":      r1a["micro_f1"],
            "macro_f1":      r1a["macro_f1"],
            "micro_precision": r1a["micro_precision"],
            "micro_recall":  r1a["micro_recall"],
        },
        "task1b": {
            "micro_f1":            r1b["micro_f1"],
            "macro_f1":            r1b["macro_f1"],
            "micro_precision":     r1b["micro_precision"],
            "micro_recall":        r1b["micro_recall"],
            "direction_reverse_rate": drr,
            "reversed_count":      rev,
            "denominator_count":   den,
            "ambiguous_count":     amb,
        },
        "total_task1a_predictions": total_1a,
        "total_task1b_predictions": total_1b,
        "average_task1a_predictions_per_article": round(total_1a / n_arts, 2),
        "average_task1b_predictions_per_article": round(total_1b / n_arts, 2),
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
        ("Prompt-only",        "Prompt-only"),
        ("DeBERTa-only",       "DeBERTa-only"),
        ("Hybrid v1",          "Hybrid v1"),
        ("Hybrid v2 OAI",      "Hybrid v2 OAI"),
        ("Hybrid v2 DS Pro",   "Hybrid v2 DS Pro"),
        ("Hybrid v2 DS Flash", "Hybrid v2 DS Flash"),
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
    ap = argparse.ArgumentParser(description="Hybrid v2: value-only candidates + LLM direction")
    ap.add_argument("--mode",                    choices=["dev", "test"], default="dev")
    ap.add_argument("--provider",                choices=["openai", "deepseek"], default="openai")
    ap.add_argument("--model",                   default=None,
                    help="LLM model (default: gpt-4o-mini for openai, deepseek-v4-pro for deepseek)")
    ap.add_argument("--api_key",                 default=None)
    ap.add_argument("--deberta_threshold",       type=float, default=0.20)
    ap.add_argument("--top_k",                   type=int,   default=10)
    ap.add_argument("--max_candidates_per_actor",type=int,   default=12)
    ap.add_argument("--limit",                   type=int,   default=None)
    ap.add_argument("--temperature",             type=float, default=0.0)
    ap.add_argument("--output_dir",              default=None,
                    help="Output directory (default: auto-computed from provider+model)")
    ap.add_argument("--no_cache",                action="store_true",
                    help="Do not reuse cached LLM responses (still writes new cache)")
    args = ap.parse_args()
    if args.model is None:
        args.model = "gpt-4o-mini" if args.provider == "openai" else "deepseek-v4-pro"
    return args


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args   = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    slug = model_slug(args.model)
    if args.output_dir is None:
        OUT_DIR = BASE_DIR / f"output/task1_hybrid_v2_{args.provider}_{slug}"
    else:
        OUT_DIR = BASE_DIR / args.output_dir
    cache_path = LOGS_DIR / f"cache_hybrid_v2_{args.mode}_{args.provider}_{slug}.json"

    print(f"Device: {device}  mode={args.mode}  provider={args.provider}  model={args.model}")
    print(f"  threshold={args.deberta_threshold}  top_k={args.top_k}"
          f"  max_cands={args.max_candidates_per_actor}  limit={args.limit}")
    print(f"  output_dir={OUT_DIR}")
    print(f"  cache={cache_path}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Taxonomy ──────────────────────────────────────────────────────────────
    l1_id_to_name, l1_id_to_l2_id, l2_id_to_name = load_taxonomy()

    # ── Load articles ─────────────────────────────────────────────────────────
    articles = load_articles(args.mode, args.limit)
    processed_guids = {str(a["guid"]) for a in articles}
    print(f"Articles: {len(articles)}")

    examples, articles_by_guid = prepare_data(articles)

    # ── Part 4: DeBERTa value-only candidate generation ───────────────────────
    candidates_file = OUT_DIR / f"candidates_{args.mode}.json"

    tok    = AutoTokenizer.from_pretrained(str(CHECKPOINT_DIR))
    model  = load_deberta(device)
    loader = DataLoader(
        InferDataset(examples, tok),
        batch_size=16, shuffle=False, num_workers=4, pin_memory=True,
    )
    article_candidates = run_value_only_inference(
        model, loader, device, args, l1_id_to_name, articles, articles_by_guid
    )
    candidates_file.write_text(
        json.dumps(article_candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Candidates saved → {candidates_file}")
    del model, tok
    if device.type == "cuda":
        torch.cuda.empty_cache()

    # ── Candidate stats ───────────────────────────────────────────────────────
    all_actor_cand_counts = [
        len(entry["candidates"])
        for art in article_candidates
        for entry in art["actors"]
    ]
    total_actor_pairs  = len(all_actor_cand_counts)
    total_candidates   = sum(all_actor_cand_counts)
    max_cands_observed = max(all_actor_cand_counts, default=0)
    min_cands_observed = min(all_actor_cand_counts, default=0)

    # ── API key check ─────────────────────────────────────────────────────────
    api_key = resolve_api_key(args)
    if not api_key:
        env_var = "DEEPSEEK_API_KEY" if args.provider == "deepseek" else "OPENAI_API_KEY"
        print(f"\nERROR: No {args.provider} API key found.")
        print(f"  Candidates saved. Provide --api_key or set {env_var} to continue.")
        sys.exit(1)
    if args.provider == "deepseek":
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    else:
        client = OpenAI(api_key=api_key)

    # ── Part 5 & 6: LLM verification with smart cache ─────────────────────────
    cache = load_cache(cache_path)

    whitelist = build_whitelist(article_candidates)

    verified_by_guid: dict = {}
    stats = {
        "total_kept_labels":    0,
        "invalid_llm_items":    0,
        "empty_llm_articles":   0,
        "json_parse_failures":  0,
        "api_failures":         0,
        "cache_hits":           0,
        "cache_misses":         0,
    }

    for art in tqdm(article_candidates, desc="LLM verification"):
        guid          = art["guid"]
        actor_entries = art["actors"]

        candidate_hash = compute_candidate_hash(actor_entries)
        cache_key      = make_cache_key(guid, candidate_hash, args.provider, args.model)

        # Check cache
        cached = cache.get(cache_key)
        use_cache = (
            not args.no_cache
            and cached is not None
            and cached.get("success")
            and cached.get("provider") == args.provider
            and cached.get("model") == args.model
        )

        if use_cache:
            parsed_items = cached["parsed_items"]
            stats["cache_hits"] += 1
        else:
            stats["cache_misses"] += 1
            if not actor_entries:
                response_text, parsed_items, success, error = "", [], True, None
            else:
                user_prompt = build_user_prompt(art, articles_by_guid)
                response_text, parsed_items, success, error = call_llm(
                    client, args, user_prompt
                )
                if not success:
                    stats["api_failures"] += 1
                    print(f"  [WARN] API failure for guid={guid}: {error}")
                elif parsed_items is None:
                    stats["json_parse_failures"] += 1
                    parsed_items = []

            cache[cache_key] = {
                "guid":           guid,
                "candidate_hash": candidate_hash,
                "provider":       args.provider,
                "model":          args.model,
                "response_text":  response_text,
                "parsed_items":   parsed_items or [],
                "success":        success if not actor_entries else (parsed_items is not None and success),
                "error":          error,
            }
            save_cache(cache, cache_path)

        # Validate and convert
        valid_items, n_invalid = validate_and_convert(
            parsed_items or [], whitelist.get(guid, {})
        )
        stats["invalid_llm_items"] += n_invalid
        if not valid_items:
            stats["empty_llm_articles"] += 1

        verified_by_guid[guid] = valid_items
        stats["total_kept_labels"] += len(valid_items)

    # ── Part 7: Build and save predictions ────────────────────────────────────
    t1a, t1b = build_submission(verified_by_guid, l1_id_to_l2_id)
    pred_1a_path = OUT_DIR / "pred_task1a.json"
    pred_1b_path = OUT_DIR / "pred_task1b.json"
    pred_1a_path.write_text(
        json.dumps(t1a, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pred_1b_path.write_text(
        json.dumps(t1b, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nPredictions saved → {OUT_DIR}/")

    # ── Part 9: Filtering stats ───────────────────────────────────────────────
    avg_cands = total_candidates / max(total_actor_pairs, 1)
    avg_kept  = stats["total_kept_labels"] / max(total_actor_pairs, 1)
    kept_ratio = stats["total_kept_labels"] / max(total_candidates, 1)
    articles_no_pred = sum(
        1 for g, items in verified_by_guid.items() if not items
    )

    filtering_stats = {
        "mode":                          args.mode,
        "provider":                      args.provider,
        "model":                         args.model,
        "total_articles_processed":      len(articles),
        "total_actor_pairs":             total_actor_pairs,
        "total_candidates":              total_candidates,
        "total_kept_labels":             stats["total_kept_labels"],
        "avg_candidates_per_actor":      round(avg_cands, 2),
        "avg_kept_labels_per_actor":     round(avg_kept, 2),
        "kept_ratio":                    round(kept_ratio, 4),
        "invalid_llm_items":             stats["invalid_llm_items"],
        "empty_llm_articles":            stats["empty_llm_articles"],
        "json_parse_failures":           stats["json_parse_failures"],
        "api_failures":                  stats["api_failures"],
        "cache_hits":                    stats["cache_hits"],
        "cache_misses":                  stats["cache_misses"],
        "articles_with_no_predictions":  articles_no_pred,
        "max_candidates_per_actor_observed": max_cands_observed,
        "min_candidates_per_actor_observed": min_cands_observed,
    }
    (OUT_DIR / "filtering_stats.json").write_text(
        json.dumps(filtering_stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Stats: total_kept={stats['total_kept_labels']}"
          f"  avg_cands/actor={avg_cands:.1f}"
          f"  avg_kept/actor={avg_kept:.1f}"
          f"  invalid_llm={stats['invalid_llm_items']}"
          f"  cache_hits={stats['cache_hits']}")

    # ── Part 10: Run config ───────────────────────────────────────────────────
    run_config = {
        "mode":                     args.mode,
        "provider":                 args.provider,
        "model":                    args.model,
        "deberta_threshold":        args.deberta_threshold,
        "top_k":                    args.top_k,
        "max_candidates_per_actor": args.max_candidates_per_actor,
        "limit":                    args.limit,
        "temperature":              args.temperature,
        "output_dir":               str(OUT_DIR),
        "timestamp":                datetime.now(timezone.utc).isoformat(),
        "device":                   str(device),
        "checkpoint_path":          str(CHECKPOINT_DIR),
        "cache_path":               str(cache_path),
    }
    (OUT_DIR / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Part 8: Evaluation (dev only) ────────────────────────────────────────
    if args.mode != "dev":
        print("Test mode: skipping evaluation.")
        return

    filter_guids = processed_guids if args.limit else None

    print("\n[Evaluation]")
    all_metrics = {}

    for label, comp_dir in {**COMPARE_DIRS, **HYBRID_V2_DIRS}.items():
        m = eval_result(comp_dir / "pred_task1a.json", comp_dir / "pred_task1b.json", filter_guids)
        if m is None:
            print(f"  {label}: prediction files not found, skipping.")
        else:
            all_metrics[label] = m
            print(f"  {label}: 1a micro={m['task1a']['micro_f1']:.4f}"
                  f"  1b micro={m['task1b']['micro_f1']:.4f}"
                  f"  DRR={m['task1b']['direction_reverse_rate']:.4f}")

    # Save own metrics (current run)
    current_label = next(
        (lbl for lbl, d in HYBRID_V2_DIRS.items() if d == OUT_DIR), "Hybrid v2"
    )
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(all_metrics.get(current_label, {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "comparison_metrics.json").write_text(
        json.dumps(all_metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    table = format_comparison_table(all_metrics)
    print("\n" + table)
    (OUT_DIR / "comparison_table.txt").write_text(table + "\n", encoding="utf-8")
    print(f"\nAll results saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
