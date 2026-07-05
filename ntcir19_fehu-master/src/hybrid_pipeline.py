#!/usr/bin/env python3
"""
Hybrid Pipeline: DeBERTa candidate generation + LLM verification for FEHU Task-1.

Step 1 – DeBERTa produces high-recall candidates (low threshold + top-k union).
Step 2 – LLM verifies each candidate (keep or remove only, no direction changes).
Step 3 – Strict whitelist filters any LLM hallucination before output.

Run from project root:
    python src/hybrid_pipeline.py --mode dev --api_key sk-xxx
    python src/hybrid_pipeline.py --mode dev --limit 5 --api_key sk-xxx
    python src/hybrid_pipeline.py --mode dev --skip_deberta --api_key sk-xxx
"""

import argparse
import json
import os
import re
import shlex
import subprocess
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

# Import model architecture and constants from train_deberta — must match exactly.
from train_deberta import ValueClassifier, MODEL_NAME, NUM_LABELS, MAX_LENGTH, CHECKPOINT_DIR

# ── Paths ─────────────────────────────────────────────────────────────────────
DEV_ARTICLES  = BASE_DIR / "dataset/dev/dev_event_base.json"
DEV_LABELS    = BASE_DIR / "dataset/gold_labels/dev/dev_human_values.json"
TEST_ARTICLES = BASE_DIR / "dataset/test/test_article_event_base.json"
L1_FILE       = BASE_DIR / "dataset/hv_categories/human_value_level1_values.json"
L2_FILE       = BASE_DIR / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_FILE = BASE_DIR / "dataset/hv_categories/level_1_to_level_2.json"
HYBRID_OUT    = BASE_DIR / "output/task1_hybrid"
# NOTE: output/task1/ is legacy ambiguous (both run_pipeline.py and the older
# train_deberta.py used to write there). After the audit (2026-06-13) the
# canonical DeBERTa-only predictions live at output/task1_deberta/. Never use
# output/task1/ as a DeBERTa baseline — its contents may be prompt-only.
DEBERTA_OUT   = BASE_DIR / "output/task1_deberta"
LOGS_DIR      = BASE_DIR / "logs"


def _model_slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[/.:\-]", "_", s)
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _current_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(BASE_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"

CONTENT_MAX = 10_000


# ── Taxonomy ──────────────────────────────────────────────────────────────────
def load_taxonomy():
    """Return (l1_id_to_name, l1_id_to_l2_id)."""
    l1_name_to_id = json.loads(L1_FILE.read_text())       # {name: id_str}
    l2_name_to_id = json.loads(L2_FILE.read_text())       # {name: id_str}
    raw = json.loads(L1_TO_L2_FILE.read_text())["level_1_to_level_2"]  # {l1_name: l2_name}
    l1_id_to_name  = {v: k for k, v in l1_name_to_id.items()}
    l1_id_to_l2_id = {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}
    return l1_id_to_name, l1_id_to_l2_id


# ── API key ───────────────────────────────────────────────────────────────────
def resolve_api_key(arg_key):
    if arg_key:
        return arg_key
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


# ── Data loading ──────────────────────────────────────────────────────────────
def load_articles(path, limit=None):
    arts = json.loads(Path(path).read_text())
    return arts[:limit] if limit else arts


def build_examples(articles):
    """
    Returns (examples_list, articles_by_guid).
    examples_list: [{guid, actor_id, actor_name, text}]
    articles_by_guid: {guid: {title, content, id2name}}
    """
    articles_by_guid = {}
    examples = []
    for art in articles:
        guid    = str(art["guid"])
        title   = art.get("title", "")
        content = art.get("content", "")
        if len(content) > CONTENT_MAX:
            content = content[:CONTENT_MAX]
        text    = f"Title: {title}\n{content}"
        id2name = {
            str(aid): name
            for d in art.get("actors", [])
            for name, aid in d.items()
        }
        articles_by_guid[guid] = {"title": title, "content": content, "id2name": id2name}
        for actor_id, actor_name in id2name.items():
            examples.append({"guid": guid, "actor_id": actor_id,
                              "actor_name": actor_name, "text": text})
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


# ── DeBERTa candidate generation ─────────────────────────────────────────────
@torch.no_grad()
def run_deberta_candidates(model, loader, device, args, l1_id_to_name):
    """
    Returns list of candidate entries (one per actor):
    [{"guid", "actor_id", "actor_name", "candidates": [{l1_value_id, direction,
      confidence, l1_value_name}]}]
    """
    results = []
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

            # Threshold-based candidates
            thresh_idxs = set(p.ge(args.deberta_threshold).nonzero(as_tuple=True)[0].tolist())

            # Top-k candidates (guaranteed floor)
            k = min(args.top_k, NUM_LABELS)
            topk_idxs = set(p.topk(k).indices.tolist())

            # Union, sorted by confidence descending, capped
            union = thresh_idxs | topk_idxs
            union_sorted = sorted(union, key=lambda idx: p[idx].item(), reverse=True)
            union_sorted = union_sorted[:args.max_candidates_per_actor]

            candidates = [
                {
                    "l1_value_id":   str(idx // 2),
                    "direction":     str(idx % 2),
                    "confidence":    round(p[idx].item(), 6),
                    "l1_value_name": l1_id_to_name.get(str(idx // 2), f"value_{idx // 2}"),
                }
                for idx in union_sorted
            ]
            results.append({
                "guid":       guid,
                "actor_id":   actor_id,
                "actor_name": actor_name,
                "candidates": candidates,
            })
    return results


# ── LLM verification ──────────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are a strict verifier for human value classification in news articles. "
    "You will receive a news article, actors, and for each actor a list of CANDIDATE human values "
    "with directions predicted by a classifier. "
    "Your ONLY job is to decide which candidates to KEEP and which to REMOVE. "
    "KEEP a candidate if the article provides clear evidence that this actor expresses or violates "
    "this value in the stated direction. "
    "REMOVE a candidate if there is no evidence, or if the value assignment seems incorrect. "
    "IMPORTANT: You must NOT change any direction. You must NOT add any new values. "
    "You can only keep or remove from the given list. "
    "OUTPUT: Return ONLY a valid JSON array of the candidates you want to KEEP. "
    'Each element: {"actor_id": string, "l1_value_id": string, "direction": "0" or "1"}. '
    'Use "0" for contradictory and "1" for aligned, exactly as given in the input. '
    "No markdown, no extra text."
)


def build_user_prompt(article_info, actor_entries):
    """
    article_info: {title, content}
    actor_entries: [{actor_id, actor_name, candidates: [{l1_value_id, direction,
                     confidence, l1_value_name}]}]
    """
    content = article_info["content"]
    if len(content) > CONTENT_MAX:
        content = content[:CONTENT_MAX]

    lines = [
        f"Title: {article_info['title']}",
        f"Article: {content}",
        "",
        "Candidates to verify:",
    ]
    for entry in actor_entries:
        lines.append(f"\nActor: {entry['actor_name']} (ID: {entry['actor_id']})")
        for c in entry["candidates"]:
            dir_str = "aligned" if c["direction"] == "1" else "contradictory"
            lines.append(
                f"  - [KEEP/REMOVE?] Value {c['l1_value_id']} ({c['l1_value_name']}), "
                f"direction: {dir_str}, confidence: {c['confidence']:.3f}"
            )
    lines.append(
        "\nReturn ONLY a JSON array of candidates to keep. "
        'Each element: {"actor_id": "...", "l1_value_id": "...", "direction": "0" or "1"}.'
    )
    return "\n".join(lines)


def _strip_markdown(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def call_llm(client, model, user_prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.0,
            )
            raw = resp.choices[0].message.content
            return json.loads(_strip_markdown(raw))
        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt + 1}): {e}")
        except Exception as e:
            print(f"  API error (attempt {attempt + 1}): {e}")
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    return []


# ── Whitelist validation ──────────────────────────────────────────────────────
def validate_against_whitelist(llm_items, candidate_set):
    """
    Drop any LLM output item not present in the DeBERTa candidate set.
    candidate_set: set of (actor_id, l1_value_id, direction) strings
    Returns (valid_items, n_invalid)
    """
    valid, n_invalid = [], 0
    for item in llm_items:
        try:
            key = (str(item["actor_id"]), str(item["l1_value_id"]), str(item["direction"]))
            if key in candidate_set:
                valid.append({"actor_id":    key[0],
                              "l1_value_id": key[1],
                              "direction":   key[2]})
            else:
                n_invalid += 1
        except (KeyError, TypeError):
            n_invalid += 1
    return valid, n_invalid


# ── Output generation ─────────────────────────────────────────────────────────
def build_submission(verified_by_guid, l1_id_to_l2_id):
    """
    verified_by_guid: {guid: [{actor_id, l1_value_id, direction}]}
    Returns (task1a_list, task1b_list) in submission format.
    """
    t1a, t1b = [], []
    for guid, items in verified_by_guid.items():
        va, vb, seen_l2 = [], [], set()
        for item in items:
            actor = item["actor_id"]
            l1    = item["l1_value_id"]
            dr    = item["direction"]
            l2    = l1_id_to_l2_id.get(l1, "0")
            vb.append({"actor": actor, "l1_value": l1, "direction": dr})
            if (actor, l2) not in seen_l2:
                seen_l2.add((actor, l2))
                va.append({"actor": actor, "l2_value": l2})
        t1a.append({"guid": guid, "article_human_values": va})
        t1b.append({"guid": guid, "article_human_values": vb})
    return t1a, t1b


# ── Evaluation ────────────────────────────────────────────────────────────────
def _filter_to_guids(d, guids):
    """Filter a {(guid, actor): labels} dict to only the specified guids."""
    if guids is None:
        return d
    return {k: v for k, v in d.items() if k[0] in guids}


def run_evaluation(pred_1a_path, pred_1b_path, processed_guids=None, label="Hybrid"):
    from evaluation import (
        parse_task1a, parse_task1b, evaluate,
        l2_universe, l1_dir_universe, direction_reverse_rate_gold_excl,
    )
    g1a = _filter_to_guids(parse_task1a(str(DEV_LABELS)), processed_guids)
    p1a = _filter_to_guids(parse_task1a(str(pred_1a_path)), processed_guids)
    r1a = evaluate(g1a, p1a, l2_universe())

    g1b = _filter_to_guids(parse_task1b(str(DEV_LABELS)), processed_guids)
    p1b = _filter_to_guids(parse_task1b(str(pred_1b_path)), processed_guids)
    r1b = evaluate(g1b, p1b, l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b, p1b)

    print(f"\n[{label}]")
    print(f"  Task-1a  micro={r1a['micro_f1']:.4f}  macro={r1a['macro_f1']:.4f}")
    print(f"  Task-1b  micro={r1b['micro_f1']:.4f}  macro={r1b['macro_f1']:.4f}"
          f"  P={r1b['micro_precision']:.4f}  R={r1b['micro_recall']:.4f}")
    print(f"  DRR={drr:.4f}  (rev={rev}/{den}  amb={amb})")
    return r1a, r1b, drr, rev, den, amb


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    ap = argparse.ArgumentParser(description="Hybrid DeBERTa+LLM pipeline for FEHU Task-1")
    ap.add_argument("--mode", choices=["dev", "test"], default="dev")
    ap.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name")
    ap.add_argument("--api_key", default=None, help="OpenAI API key")
    ap.add_argument("--deberta_threshold", type=float, default=0.20)
    ap.add_argument("--top_k", type=int, default=12,
                    help="Always include top-k candidates regardless of threshold")
    ap.add_argument("--max_candidates_per_actor", type=int, default=15)
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only first N articles (for debugging)")
    ap.add_argument("--skip_deberta", action="store_true",
                    help="Load candidates from cached file instead of running DeBERTa")
    return ap.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args   = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  mode={args.mode}  llm={args.model}"
          f"  threshold={args.deberta_threshold}  top_k={args.top_k}"
          f"  max_cands={args.max_candidates_per_actor}  limit={args.limit}")

    HYBRID_OUT.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    api_key = resolve_api_key(args.api_key)
    if not api_key:
        print("WARNING: No OpenAI API key found. LLM calls will fail.")
    client = OpenAI(api_key=api_key)

    l1_id_to_name, l1_id_to_l2_id = load_taxonomy()

    articles_path = DEV_ARTICLES if args.mode == "dev" else TEST_ARTICLES
    articles = load_articles(articles_path, args.limit)
    processed_guids = {str(a["guid"]) for a in articles}
    print(f"Articles to process: {len(articles)}")

    # Always build examples/articles_by_guid — needed for LLM prompts even when skipping DeBERTa
    examples, articles_by_guid = build_examples(articles)

    # ── Part 2: DeBERTa candidate generation ─────────────────────────────────
    candidates_file = HYBRID_OUT / f"candidates_{args.mode}.json"

    if args.skip_deberta and candidates_file.exists():
        print(f"Loading cached candidates from {candidates_file}")
        raw_candidates = json.loads(candidates_file.read_text())
        raw_candidates = [e for e in raw_candidates if e["guid"] in processed_guids]
    else:
        tok    = AutoTokenizer.from_pretrained(MODEL_NAME)
        model  = load_deberta(device)
        loader = DataLoader(
            InferDataset(examples, tok),
            batch_size=16, shuffle=False, num_workers=4, pin_memory=True,
        )
        raw_candidates = run_deberta_candidates(model, loader, device, args, l1_id_to_name)
        candidates_file.write_text(json.dumps(raw_candidates, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Candidates saved to {candidates_file}")
        del model, tok
        if device.type == "cuda":
            torch.cuda.empty_cache()

    # Group candidates by article
    by_article = defaultdict(list)
    for entry in raw_candidates:
        by_article[entry["guid"]].append(entry)

    # Build whitelist: guid → set of (actor_id, l1_value_id, direction)
    whitelist = defaultdict(set)
    for entry in raw_candidates:
        for c in entry["candidates"]:
            whitelist[entry["guid"]].add(
                (entry["actor_id"], c["l1_value_id"], c["direction"])
            )

    # ── Part 3 & 4: LLM verification with caching ────────────────────────────
    # Cache is now keyed by mode + LLM model. This prevents reusing
    # gpt-4o-mini results for a gpt-4o run (and vice versa).
    llm_slug   = _model_slug(args.model)
    cache_path = LOGS_DIR / f"cache_hybrid_v1_{args.mode}_openai_{llm_slug}.json"
    cache: dict = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    verified_by_guid: dict = {}
    invalid_llm_total = 0
    total_candidates  = 0
    total_kept        = 0

    for article in tqdm(articles, desc="LLM verification"):
        guid          = str(article["guid"])
        actor_entries = by_article.get(guid, [])
        total_candidates += sum(len(e["candidates"]) for e in actor_entries)

        if guid in cache:
            verified = cache[guid]
        else:
            if not actor_entries:
                verified = []
            else:
                prompt   = build_user_prompt(articles_by_guid[guid], actor_entries)
                llm_out  = call_llm(client, args.model, prompt)
                verified, n_inv = validate_against_whitelist(llm_out, whitelist[guid])
                invalid_llm_total += n_inv
            cache[guid] = verified
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

        verified_by_guid[guid] = verified
        total_kept += len(verified)

    # ── Part 5: Output generation ─────────────────────────────────────────────
    t1a, t1b = build_submission(verified_by_guid, l1_id_to_l2_id)
    pred_1a_path = HYBRID_OUT / "pred_task1a.json"
    pred_1b_path = HYBRID_OUT / "pred_task1b.json"
    pred_1a_path.write_text(json.dumps(t1a, ensure_ascii=False, indent=2), encoding="utf-8")
    pred_1b_path.write_text(json.dumps(t1b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPredictions written to {HYBRID_OUT}/")

    n_actors     = len(raw_candidates)
    avg_cands    = total_candidates / max(n_actors, 1)
    avg_kept     = total_kept / max(n_actors, 1)
    print(f"Stats: total_predictions={total_kept}  avg_candidates/actor={avg_cands:.1f}"
          f"  avg_kept/actor={avg_kept:.1f}  invalid_llm_items={invalid_llm_total}")

    # ── Part 6: Evaluation ────────────────────────────────────────────────────
    metrics: dict = {}
    if args.mode == "dev":
        r1a, r1b, drr, rev, den, amb = run_evaluation(
            pred_1a_path, pred_1b_path, processed_guids, label="Hybrid"
        )
        metrics["hybrid"] = {
            "task1a": r1a, "task1b": r1b,
            "drr": drr, "rev": rev, "den": den, "amb": amb,
        }

        db_1a = DEBERTA_OUT / "pred_task1a.json"
        db_1b = DEBERTA_OUT / "pred_task1b.json"
        if db_1a.exists() and db_1b.exists():
            r1a_db, r1b_db, drr_db, rev_db, den_db, amb_db = run_evaluation(
                db_1a, db_1b,
                processed_guids if args.limit else None,
                label="DeBERTa-only",
            )
            metrics["deberta_only"] = {
                "task1a": r1a_db, "task1b": r1b_db,
                "drr": drr_db, "rev": rev_db, "den": den_db, "amb": amb_db,
            }

    metrics["stats"] = {
        "n_articles":                len(articles),
        "n_actors":                  n_actors,
        "total_predictions":         total_kept,
        "avg_candidates_per_actor":  round(avg_cands, 2),
        "avg_kept_per_actor":        round(avg_kept, 2),
        "invalid_llm_items":         invalid_llm_total,
    }
    (HYBRID_OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    config = {
        "script":                   "src/hybrid_pipeline.py",
        "method":                   "hybrid_v1",
        "mode":                     args.mode,
        "provider":                 "openai",
        "llm_model":                args.model,
        "llm_model_slug":           llm_slug,
        "deberta_threshold":        args.deberta_threshold,
        "top_k":                    args.top_k,
        "max_candidates_per_actor": args.max_candidates_per_actor,
        "limit":                    args.limit,
        "is_limit_run":             bool(args.limit),
        "skip_deberta":             args.skip_deberta,
        "output_dir":               str(HYBRID_OUT),
        "cache_path":               str(cache_path),
        "deberta_baseline_dir":     str(DEBERTA_OUT),
        "command_line":             " ".join(shlex.quote(a) for a in sys.argv),
        "git_commit":               _current_git_commit(),
        "timestamp":                datetime.now(timezone.utc).isoformat(),
        "notes": (
            "Hybrid v1 (post-audit). DeBERTa baseline now read from "
            "output/task1_deberta/. Cache file is provider+LLM-model-keyed."
        ),
    }
    (HYBRID_OUT / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Metrics and config saved to {HYBRID_OUT}/")


if __name__ == "__main__":
    main()
