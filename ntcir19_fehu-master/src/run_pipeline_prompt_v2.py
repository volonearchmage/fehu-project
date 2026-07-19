#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V2 — prompt-only, actor-conditioned, taxonomy-grounded.

Independent of src/run_pipeline.py and src/run_pipeline_deepseek_flash.py
(which are preserved unmodified as historical baselines).

Core guarantees vs. the old pipeline:
  * No failure is ever converted into an empty prediction. API, empty-response,
    JSON-parse, schema, and semantic-validation failures are recorded per
    article; the run is marked INCOMPLETE/FAILED accordingly.
  * Strict all-or-nothing validation (src/task1_v2_schema.py). No silent
    repair, wrapping, direction normalization, or item deletion.
  * Cache entries are bound to provider, model, prompt version, prompt hash,
    taxonomy hash, rarity hash, article hash, guid, schema version, and
    success status. Any mismatch is a cache miss. Failed entries are never
    reused.
  * The model returns Level-1 + direction only; Task-1a is derived
    deterministically from accepted Task-1b predictions.
  * Zero-shot taxonomy-grounded prompt (src/prompts_task1_v2.py); rare labels
    get extra retrieval attention with the SAME evidence standard.

Usage (from project root):
    python src/run_pipeline_prompt_v2.py --dry_run --mode dev
    python src/run_pipeline_prompt_v2.py --mode dev --provider deepseek \\
        --model deepseek-v4-flash --limit 5

API keys come only from the environment (OPENAI_API_KEY / DEEPSEEK_API_KEY)
or the project .env file. They are never accepted on the command line and
never printed or written to any artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))

from task1_v2_taxonomy import (
    Taxonomy, TaxonomyValidationError, load_taxonomy, build_rarity_metadata,
    compute_article_hash, canonical_json, sha256_text, N_L1, N_L2,
    TRAIN_LABELS_PATH,
)
from prompts_task1_v2 import (
    PROMPT_VERSION, build_system_prompt, build_user_prompt, compute_prompt_hash,
)
from task1_v2_schema import (
    SCHEMA_VERSION, ERR_API, ERR_EMPTY, ERR_JSON, ERR_SCHEMA, ERR_SEMANTIC,
    ValidationIssue, parse_response_json, validate_response_object,
    sorted_task1b_values, derive_task1a_values, build_response_json_schema,
)

# ── Dataset paths ─────────────────────────────────────────────────────────────
DEV_ARTICLES = BASE_DIR / "dataset" / "dev" / "dev_event_base.json"
TEST_ARTICLES = BASE_DIR / "dataset" / "test" / "test_article_event_base.json"
DEV_LABELS = BASE_DIR / "dataset" / "gold_labels" / "dev" / "dev_human_values.json"

LOGS_DIR = BASE_DIR / "logs"
OUTPUT_ROOT = BASE_DIR / "output" / "task1_prompt_v2"

METHOD_NAME = "prompt_only_v2"
TEMPERATURE = 0.0
DEFAULT_MAX_RETRIES = 3
TRANSIENT_SLEEP_S = 5
CORRECTION_SLEEP_S = 2
MAX_COMPLETION_TOKENS = 4000

RUN_COMPLETE = "COMPLETE"
RUN_INCOMPLETE = "INCOMPLETE"
RUN_FAILED = "FAILED"


# ============================================================
# Provider abstraction
# ============================================================

class ProviderTransientError(RuntimeError):
    """API/network failure — retry the same request."""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: Optional[str]
    api_key_env: str
    token_param: str                 # "max_completion_tokens" | "max_tokens"
    supports_json_schema: bool       # strict structured output
    supports_json_object: bool       # plain JSON mode
    extra_body: Optional[dict] = None


PROVIDERS: Dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        name="openai", base_url=None, api_key_env="OPENAI_API_KEY",
        token_param="max_completion_tokens",
        supports_json_schema=True, supports_json_object=True,
    ),
    "deepseek": ProviderSpec(
        name="deepseek", base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY", token_param="max_tokens",
        supports_json_schema=False, supports_json_object=True,
        extra_body={"thinking": {"type": "disabled"}},
    ),
}


def resolve_api_key(spec: ProviderSpec) -> str:
    """Environment first, then project .env. Never printed, never logged."""
    key = os.environ.get(spec.api_key_env, "")
    if key:
        return key
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{spec.api_key_env}="):
                return line.split("=", 1)[1].strip()
    return ""


def make_caller(spec: ProviderSpec, model: str) -> Callable[[List[dict], Optional[dict]], str]:
    """
    Build call_fn(messages, json_schema) -> raw response text.
    Raises ProviderTransientError on any API/transport failure.
    Imported lazily so tests and --dry_run never need the openai package
    or an API key.
    """
    from openai import OpenAI

    api_key = resolve_api_key(spec)
    if not api_key:
        raise SystemExit(
            f"ERROR: no API key found. Set {spec.api_key_env} in the "
            f"environment or in the project .env file. Keys are not accepted "
            f"on the command line."
        )
    client = OpenAI(api_key=api_key, base_url=spec.base_url)

    def call(messages: List[dict], json_schema: Optional[dict]) -> str:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": TEMPERATURE,
            spec.token_param: MAX_COMPLETION_TOKENS,
        }
        if spec.extra_body:
            kwargs["extra_body"] = spec.extra_body
        if json_schema is not None and spec.supports_json_schema:
            kwargs["response_format"] = {"type": "json_schema",
                                         "json_schema": json_schema}
        elif spec.supports_json_object:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
        except Exception as e:  # SDK/transport/API errors → transient
            raise ProviderTransientError(f"{type(e).__name__}: {e}") from e
        return content if content is not None else ""

    return call


# ============================================================
# Cache — identity-bound; failed entries are never reused
# ============================================================

def cache_identity(spec_name: str, model: str, prompt_hash: str,
                   taxonomy_hash: str, rarity_hash: str,
                   article: dict) -> dict:
    return {
        "provider": spec_name,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "taxonomy_hash": taxonomy_hash,
        "rarity_hash": rarity_hash,
        "article_hash": compute_article_hash(article),
        "article_guid": str(article["guid"]),
        "schema_version": SCHEMA_VERSION,
    }


def cache_key(identity: dict) -> str:
    return sha256_text(canonical_json(identity))


class CacheStore:
    def __init__(self, path: Optional[Path]):
        self.path = path
        self.data: Dict[str, dict] = {}
        if path is not None and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"  [WARN] Cache file corrupted, ignoring: {path}")
                self.data = {}

    def lookup(self, identity: dict) -> Optional[dict]:
        """Return the cached entry only if every identity field matches AND
        the entry was a success. Failed entries are never reused."""
        if self.path is None:
            return None
        entry = self.data.get(cache_key(identity))
        if not isinstance(entry, dict):
            return None
        if entry.get("identity") != identity:
            return None
        if entry.get("success") is not True:
            return None
        return entry

    def store(self, identity: dict, success: bool, predictions: Optional[list],
              error_types: Optional[List[str]] = None) -> None:
        if self.path is None:
            return
        self.data[cache_key(identity)] = {
            "identity": identity,
            "success": success,
            "predictions": predictions,
            "error_types": error_types or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False),
                             encoding="utf-8")


# ============================================================
# Per-article processing with explicit retry/failure policy
# ============================================================

@dataclass
class ArticleOutcome:
    guid: str
    success: bool
    from_cache: bool
    predictions: Optional[List[dict]]   # accepted raw prediction items
    issues: List[dict]                  # structured validation errors
    attempts: int
    raw_attempts: List[dict]            # [{"attempt", "kind", "raw"}]


def _correction_message(issues: List[ValidationIssue]) -> str:
    listing = "\n".join(
        f"- [{i.error_type}] field {i.field}: {i.reason}" for i in issues
    )
    return (
        "Your previous response violated the required output contract. "
        "Violations:\n" + listing + "\n\n"
        "Re-emit your classification as ONE valid JSON object that follows "
        "the output contract exactly (only the keys guid and predictions; "
        "each prediction has exactly actor_id, l1_value_id, direction as "
        "strings; direction is '0' or '1'; actor IDs copied exactly from the "
        "input; no duplicates; no markdown; no prose). Do not change, add, or "
        "remove any classification decision except as required to fix the "
        "listed violations."
    )


def process_article(
    article: dict,
    system_prompt: str,
    tax: Taxonomy,
    call_fn: Callable[[List[dict], Optional[dict]], str],
    max_retries: int,
    counters: Dict[str, int],
    use_structured_schema: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ArticleOutcome:
    """
    Run the full call → parse → validate loop for one article.

    Never returns a fabricated empty prediction: on final failure,
    outcome.success is False and outcome.predictions is None. A schema-valid
    model response with "predictions": [] is the only path to an empty
    successful outcome.
    """
    guid = str(article["guid"])
    user_prompt = build_user_prompt(article)
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    json_schema = build_response_json_schema(article, tax) if use_structured_schema else None

    messages = list(base_messages)
    all_issues: List[dict] = []
    raw_attempts: List[dict] = []
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        try:
            counters["api_calls"] += 1
            raw = call_fn(messages, json_schema)
        except ProviderTransientError as e:
            issue = ValidationIssue(
                guid=guid, error_type=ERR_API, field="<api>",
                invalid_value=None, reason=str(e), retry=attempt,
            )
            all_issues.append(issue.to_dict())
            raw_attempts.append({"attempt": attempt, "kind": ERR_API, "raw": None})
            counters["retries_api"] += 1
            if attempt < max_retries:
                sleep_fn(TRANSIENT_SLEEP_S)
            continue  # retry the same request

        obj, parse_issues = parse_response_json(raw, guid, attempt)
        if parse_issues:
            kind = parse_issues[0].error_type  # ERR_EMPTY or ERR_JSON
            all_issues.extend(i.to_dict() for i in parse_issues)
            raw_attempts.append({"attempt": attempt, "kind": kind, "raw": raw})
            counters["retries_empty" if kind == ERR_EMPTY else "retries_json"] += 1
            if attempt < max_retries:
                if kind == ERR_EMPTY:
                    messages = list(base_messages)  # fresh call
                    sleep_fn(TRANSIENT_SLEEP_S)
                else:
                    messages = base_messages + [
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": _correction_message(parse_issues)},
                    ]
                    sleep_fn(CORRECTION_SLEEP_S)
            continue

        val_issues = validate_response_object(obj, article, tax, attempt)
        if val_issues:
            all_issues.extend(i.to_dict() for i in val_issues)
            raw_attempts.append({"attempt": attempt, "kind": ERR_SCHEMA
                                 if any(i.error_type == ERR_SCHEMA for i in val_issues)
                                 else ERR_SEMANTIC, "raw": raw})
            if any(i.error_type == ERR_SCHEMA for i in val_issues):
                counters["retries_schema"] += 1
            else:
                counters["retries_semantic"] += 1
            if attempt < max_retries:
                messages = base_messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": _correction_message(val_issues)},
                ]
                sleep_fn(CORRECTION_SLEEP_S)
            continue

        # Fully valid response (possibly with an empty predictions list —
        # that is a legitimate model decision, not a failure).
        raw_attempts.append({"attempt": attempt, "kind": "success", "raw": raw})
        return ArticleOutcome(
            guid=guid, success=True, from_cache=False,
            predictions=obj["predictions"], issues=all_issues,
            attempts=attempt, raw_attempts=raw_attempts,
        )

    return ArticleOutcome(
        guid=guid, success=False, from_cache=False, predictions=None,
        issues=all_issues, attempts=attempt, raw_attempts=raw_attempts,
    )


# ============================================================
# Helpers
# ============================================================

def model_slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return re.sub(r"_+", "_", s).strip("_")


def current_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(BASE_DIR),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def append_jsonl(path: Path, obj: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def resolve_output_dir(args, slug: str) -> Path:
    if args.output_dir:
        out = Path(args.output_dir)
        if not out.is_absolute():
            out = BASE_DIR / out
        if out.exists() and any(out.iterdir()):
            raise SystemExit(
                f"ERROR: --output_dir {out} exists and is not empty. "
                f"Pipeline V2 never overwrites previous experiment folders."
            )
        out.mkdir(parents=True, exist_ok=True)
        return out
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_ROOT / f"{ts}_{args.provider}_{slug}"
    if out.exists():
        raise SystemExit(f"ERROR: output dir collision: {out}. Re-run.")
    out.mkdir(parents=True, exist_ok=True)
    return out


def filter_by_guids(parsed: dict, guids: Optional[set]) -> dict:
    """Filter an evaluation.py instance→labels dict to the given guid set."""
    if guids is None:
        return parsed
    return {k: v for k, v in parsed.items() if k[0] in guids}


# ============================================================
# Dev evaluation (official evaluation.py, gold filtered to evaluated guids)
# ============================================================

def run_dev_evaluation(pred_1a_path: Path, pred_1b_path: Path,
                       evaluated_guids: set, tax: Taxonomy, rarity: dict,
                       out_dir: Path) -> dict:
    from evaluation import (
        parse_task1a, parse_task1b, evaluate,
        l2_universe, l1_dir_universe, direction_reverse_rate_gold_excl,
        safe_div, f1_from_pr,
    )

    gold_1a = filter_by_guids(parse_task1a(str(DEV_LABELS)), evaluated_guids)
    pred_1a = filter_by_guids(parse_task1a(str(pred_1a_path)), evaluated_guids)
    gold_1b = filter_by_guids(parse_task1b(str(DEV_LABELS)), evaluated_guids)
    pred_1b = filter_by_guids(parse_task1b(str(pred_1b_path)), evaluated_guids)

    r1a = evaluate(gold_1a, pred_1a, l2_universe())
    r1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(gold_1b, pred_1b)

    metrics = {
        "evaluated_guid_count": len(evaluated_guids),
        "note": ("Gold is filtered to the guids with schema-valid predictions "
                 "in this run (successful articles only)."),
        "task1a": r1a,
        "task1b": {**r1b,
                   "direction_reverse_rate": drr,
                   "direction_reverse_count": rev,
                   "direction_reverse_denom_gold_excl": den,
                   "ambiguous_gold_values_filtered": amb},
    }

    # Per-label metrics CSV (Task-1b per direction:l1, Task-1a per l2).
    def per_label(gold, pred):
        from collections import defaultdict
        tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
        for iid in set(gold) | set(pred):
            g, p = gold.get(iid, set()), pred.get(iid, set())
            for lab in g & p:
                tp[lab] += 1
            for lab in p - g:
                fp[lab] += 1
            for lab in g - p:
                fn[lab] += 1
        return tp, fp, fn

    rows = []
    tp, fp, fn = per_label(gold_1b, pred_1b)
    for l1_id in tax.l1_ids:
        e = tax.l1_by_id[l1_id]
        meta = rarity["labels"][l1_id]
        for d in ("0", "1"):
            lab = f"{d}:{l1_id}"
            p = safe_div(tp[lab], tp[lab] + fp[lab])
            r = safe_div(tp[lab], tp[lab] + fn[lab])
            rows.append({
                "task": "task1b", "label": lab, "id": l1_id,
                "name": e.l1_name, "direction": d,
                "train_gold_count": meta["train_gold_count"],
                "frequency_group": meta["frequency_group"],
                "gold_count": tp[lab] + fn[lab], "pred_count": tp[lab] + fp[lab],
                "tp": tp[lab], "fp": fp[lab], "fn": fn[lab],
                "precision": round(p, 4), "recall": round(r, 4),
                "f1": round(f1_from_pr(p, r), 4),
            })
    tp, fp, fn = per_label(gold_1a, pred_1a)
    for l2_id in tax.l2_ids:
        p = safe_div(tp[l2_id], tp[l2_id] + fp[l2_id])
        r = safe_div(tp[l2_id], tp[l2_id] + fn[l2_id])
        rows.append({
            "task": "task1a", "label": l2_id, "id": l2_id,
            "name": tax.l2_id_to_name[l2_id], "direction": "",
            "train_gold_count": "", "frequency_group": "",
            "gold_count": tp[l2_id] + fn[l2_id], "pred_count": tp[l2_id] + fp[l2_id],
            "tp": tp[l2_id], "fp": fp[l2_id], "fn": fn[l2_id],
            "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(f1_from_pr(p, r), 4),
        })
    with open(out_dir / "per_label_metrics.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    return metrics


# ============================================================
# Dry run
# ============================================================

def run_dry_run(args, tax: Taxonomy, rarity: dict, articles: List[dict],
                system_prompt: str, prompt_hash: str, out_dir: Path,
                cache_path: Optional[Path]) -> List[str]:
    """Validate everything that can be validated without an API call."""
    checks: List[str] = []

    def ok(name):
        checks.append(f"OK   {name}")

    # Paths.
    for p in (DEV_ARTICLES, TEST_ARTICLES, DEV_LABELS, TRAIN_LABELS_PATH):
        if not p.exists():
            raise SystemExit(f"DRY-RUN FAIL: required path missing: {p}")
    ok("required dataset paths exist")

    # Taxonomy completeness (load_taxonomy already validated; re-assert).
    assert len(tax.l1_by_id) == N_L1 and tax.l1_ids == [str(i) for i in range(N_L1)]
    ok(f"exactly {N_L1} Level-1 labels with IDs '0'..'{N_L1-1}'")
    assert len(tax.l2_id_to_name) == N_L2 and tax.l2_ids == [str(i) for i in range(N_L2)]
    ok(f"exactly {N_L2} Level-2 labels with IDs '0'..'{N_L2-1}'")
    assert set(tax.l1_id_to_l2_id) == set(tax.l1_by_id)
    ok("complete Level-1 → Level-2 mapping")
    assert tax.direction_mapping == {"aligned": "1", "contradictory": "0"}
    ok("direction mapping: aligned='1', contradictory='0'")

    # Rarity metadata.
    assert set(rarity["labels"]) == set(tax.l1_by_id)
    assert all(m["frequency_group"] in
               ("frequent", "medium", "rare", "very_rare")
               for m in rarity["labels"].values())
    ok(f"rarity metadata covers all {N_L1} labels (hash {rarity['rarity_hash'][:12]}…)")

    # Prompt construction + hashing.
    assert "Rarity changes search attention, not the evidence standard." in system_prompt
    assert prompt_hash == compute_prompt_hash(tax, rarity)
    ok(f"system prompt built ({len(system_prompt)} chars), "
       f"prompt hash stable ({prompt_hash[:12]}…)")

    # Sample article prompt builds + schema + cache identity.
    n_samples = min(3, len(articles))
    for a in articles[:n_samples]:
        up = build_user_prompt(a)
        assert str(a["guid"]) in up and a["content"] in up
        schema = build_response_json_schema(a, tax)
        assert schema["schema"]["properties"]["guid"]["enum"] == [str(a["guid"])]
        ident = cache_identity(args.provider, args.model, prompt_hash,
                               tax.taxonomy_hash, rarity["rarity_hash"], a)
        assert len(cache_key(ident)) == 64
    ok(f"user prompt + response schema + cache identity built for "
       f"{n_samples} sample article(s)")

    ok(f"output directory resolved: {out_dir}")
    if cache_path is not None:
        ok(f"cache path resolved: {cache_path}")
    else:
        ok("cache disabled (--no_cache)")

    return checks


# ============================================================
# Main
# ============================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="FEHU Task-1 Pipeline V2 (prompt-only, auditable). "
                    "API keys via environment/.env only.")
    ap.add_argument("--mode", choices=["dev", "test"], default="dev")
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default="deepseek")
    ap.add_argument("--model", type=str, default="deepseek-v4-flash")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N articles. Dev gold is "
                         "filtered to the same guids for scoring.")
    ap.add_argument("--output_dir", type=str, default=None,
                    help="Override output directory (must not exist or be empty).")
    ap.add_argument("--max_retries", type=int, default=DEFAULT_MAX_RETRIES,
                    help="Maximum total attempts per article (default 3).")
    ap.add_argument("--no_cache", action="store_true",
                    help="Disable reading and writing the response cache.")
    ap.add_argument("--dry_run", action="store_true",
                    help="Validate everything without any API call.")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.max_retries < 1:
        raise SystemExit("ERROR: --max_retries must be >= 1")
    spec = PROVIDERS[args.provider]
    slug = model_slug(args.model)
    started = datetime.now(timezone.utc).isoformat()

    # ── Taxonomy + rarity (hard-fail on any inconsistency) ──────────────────
    try:
        tax = load_taxonomy()
        rarity = build_rarity_metadata(tax)
    except TaxonomyValidationError as e:
        raise SystemExit(f"FATAL taxonomy validation error:\n{e}")

    system_prompt = build_system_prompt(tax, rarity)
    prompt_hash = compute_prompt_hash(tax, rarity)

    # ── Articles ────────────────────────────────────────────────────────────
    articles_path = DEV_ARTICLES if args.mode == "dev" else TEST_ARTICLES
    articles = json.loads(articles_path.read_text(encoding="utf-8"))
    if args.limit:
        articles = articles[: args.limit]
    requested_guids = [str(a["guid"]) for a in articles]

    # ── Output dir + cache ──────────────────────────────────────────────────
    out_dir = resolve_output_dir(args, slug)
    cache_path = None if args.no_cache else (
        LOGS_DIR / f"cache_task1_prompt_v2_{args.mode}_{args.provider}_{slug}.json"
    )

    print(f"Pipeline V2  mode={args.mode} provider={args.provider} "
          f"model={args.model} articles={len(articles)} "
          f"dry_run={args.dry_run}")
    print(f"  prompt_version={PROMPT_VERSION}")
    print(f"  prompt_hash={prompt_hash[:16]}…  taxonomy_hash={tax.taxonomy_hash[:16]}…  "
          f"rarity_hash={rarity['rarity_hash'][:16]}…")
    print(f"  output: {out_dir}")

    # ── Snapshots (both real runs and dry runs) ─────────────────────────────
    (out_dir / "prompt_snapshot.txt").write_text(
        f"PROMPT_VERSION: {PROMPT_VERSION}\n"
        f"PROMPT_HASH: {prompt_hash}\n\n"
        f"===== SYSTEM PROMPT =====\n{system_prompt}\n\n"
        f"===== USER PROMPT TEMPLATE (sentinel article) =====\n"
        + build_user_prompt({
            "guid": "<GUID>", "title": "<TITLE>", "content": "<ARTICLE CONTENT>",
            "actors": [{"<ACTOR NAME>": "<ACTOR ID>"}],
        }),
        encoding="utf-8",
    )
    (out_dir / "taxonomy_snapshot.json").write_text(json.dumps({
        "taxonomy_hash": tax.taxonomy_hash,
        "direction_mapping": tax.direction_mapping,
        "l2": tax.l2_id_to_name,
        "l1": {lid: {"name": e.l1_name, "alternative_name": e.alternative_name,
                     "descriptions": list(e.descriptions), "l2_id": e.l2_id,
                     "l2_name": e.l2_name, "code": e.taxonomy_code}
               for lid, e in tax.l1_by_id.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "rarity_metadata_snapshot.json").write_text(
        json.dumps(rarity, ensure_ascii=False, indent=2), encoding="utf-8")

    counters = {k: 0 for k in (
        "api_calls", "cache_hits", "retries_api", "retries_empty",
        "retries_json", "retries_schema", "retries_semantic")}

    run_config = {
        "script": "src/run_pipeline_prompt_v2.py",
        "method": METHOD_NAME,
        "method_version": PROMPT_VERSION,
        "provider": args.provider,
        "model": args.model,
        "model_slug": slug,
        "mode": args.mode,
        "limit": args.limit,
        "dry_run": args.dry_run,
        "temperature": TEMPERATURE,
        "max_retries": args.max_retries,
        "timestamp": started,
        "git_commit": current_git_commit(),
        "command_line": " ".join(shlex.quote(a) for a in sys.argv),
        "dataset_paths": {
            "articles": str(articles_path),
            "dev_labels": str(DEV_LABELS),
            "train_labels_for_rarity": str(TRAIN_LABELS_PATH),
            "hv_categories": str(BASE_DIR / "dataset" / "hv_categories"),
        },
        "output_dir": str(out_dir),
        "cache_path": str(cache_path) if cache_path else None,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "taxonomy_hash": tax.taxonomy_hash,
        "rarity_metadata_hash": rarity["rarity_hash"],
        "schema_version": SCHEMA_VERSION,
        "n_articles_requested": len(articles),
    }

    # ── Dry run ─────────────────────────────────────────────────────────────
    if args.dry_run:
        checks = run_dry_run(args, tax, rarity, articles, system_prompt,
                             prompt_hash, out_dir, cache_path)
        print("\nDRY-RUN VALIDATION:")
        for c in checks:
            print(f"  {c}")
        run_config.update({"n_articles_succeeded": 0, "n_articles_failed": 0,
                           "counters": counters})
        (out_dir / "run_config.json").write_text(
            json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "run_status.json").write_text(json.dumps({
            "status": RUN_COMPLETE, "dry_run": True,
            "note": "Dry run: all static validations passed; no API calls "
                    "were made and no classifications were requested.",
            "checks": checks,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nDry run complete. Artifacts in {out_dir}")
        return 0

    # ── Real run ────────────────────────────────────────────────────────────
    call_fn = make_caller(spec, args.model)
    cache = CacheStore(cache_path)

    raw_responses_path = out_dir / "raw_responses.jsonl"
    parsed_predictions_path = out_dir / "parsed_predictions.jsonl"
    validation_errors_path = out_dir / "validation_errors.jsonl"
    failed_articles_path = out_dir / "failed_articles.jsonl"

    all_task1a, all_task1b = [], []
    succeeded, failed = [], []

    for idx, article in enumerate(articles, 1):
        guid = str(article["guid"])
        ident = cache_identity(args.provider, args.model, prompt_hash,
                               tax.taxonomy_hash, rarity["rarity_hash"], article)

        cached = cache.lookup(ident)
        if cached is not None:
            counters["cache_hits"] += 1
            predictions = cached["predictions"]
            outcome = ArticleOutcome(guid=guid, success=True, from_cache=True,
                                     predictions=predictions, issues=[],
                                     attempts=0, raw_attempts=[])
        else:
            outcome = process_article(article, system_prompt, tax, call_fn,
                                      args.max_retries, counters)
            for att in outcome.raw_attempts:
                append_jsonl(raw_responses_path,
                             {"guid": guid, **att,
                              "timestamp": datetime.now(timezone.utc).isoformat()})
            for issue in outcome.issues:
                append_jsonl(validation_errors_path, issue)
            cache.store(ident, outcome.success, outcome.predictions,
                        [i["error_type"] for i in outcome.issues])

        if outcome.success:
            t1b = sorted_task1b_values(article, outcome.predictions)
            t1a = derive_task1a_values(article, t1b, tax)
            all_task1b.append({"guid": guid, "article_human_values": t1b})
            all_task1a.append({"guid": guid, "article_human_values": t1a})
            append_jsonl(parsed_predictions_path, {
                "guid": guid, "from_cache": outcome.from_cache,
                "task1b": t1b, "task1a": t1a,
            })
            succeeded.append(guid)
        else:
            append_jsonl(failed_articles_path, {
                "guid": guid, "attempts": outcome.attempts,
                "error_types": sorted({i["error_type"] for i in outcome.issues}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            failed.append(guid)
            print(f"  [FAILED] {guid}: no schema-valid response after "
                  f"{outcome.attempts} attempts (recorded, NOT converted to "
                  f"an empty prediction)")

        print(f"  [{idx}/{len(articles)}] {guid}: "
              f"{'cache' if outcome.from_cache else 'api'} "
              f"{'ok' if outcome.success else 'FAILED'}")

    # ── Predictions (successful articles only — failures are never faked) ───
    pred_1a_path = out_dir / "pred_task1a.json"
    pred_1b_path = out_dir / "pred_task1b.json"
    pred_1a_path.write_text(json.dumps(all_task1a, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    pred_1b_path.write_text(json.dumps(all_task1b, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    if failed:
        status = RUN_FAILED if not succeeded else RUN_INCOMPLETE
    else:
        status = RUN_COMPLETE

    run_config.update({
        "n_articles_succeeded": len(succeeded),
        "n_articles_failed": len(failed),
        "counters": counters,
    })
    (out_dir / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "run_status.json").write_text(json.dumps({
        "status": status,
        "n_articles_requested": len(articles),
        "n_articles_succeeded": len(succeeded),
        "n_articles_failed": len(failed),
        "failed_guids": failed,
        "counters": counters,
        "finished": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Evaluation (dev mode, successful guids only) ────────────────────────
    metrics = None
    if args.mode == "dev" and succeeded:
        metrics = run_dev_evaluation(pred_1a_path, pred_1b_path,
                                     set(succeeded), tax, rarity, out_dir)
        (out_dir / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nTask-1a micro-F1 {metrics['task1a']['micro_f1']:.4f}  "
              f"macro-F1 {metrics['task1a']['macro_f1']:.4f}")
        print(f"Task-1b micro-F1 {metrics['task1b']['micro_f1']:.4f}  "
              f"macro-F1 {metrics['task1b']['macro_f1']:.4f}  "
              f"DRR {metrics['task1b']['direction_reverse_rate']:.4f}")

    # ── summary.md ──────────────────────────────────────────────────────────
    lines = [
        "# FEHU Task-1 Pipeline V2 run summary", "",
        f"- status: **{status}**",
        f"- mode: {args.mode}, provider: {args.provider}, model: {args.model}",
        f"- prompt version: {PROMPT_VERSION}, prompt hash: `{prompt_hash[:16]}…`",
        f"- articles requested/succeeded/failed: "
        f"{len(articles)}/{len(succeeded)}/{len(failed)}",
        f"- counters: {json.dumps(counters)}",
    ]
    if failed:
        lines.append(f"- failed guids (see failed_articles.jsonl): {failed}")
        lines.append("- NOTE: failed articles are excluded from prediction "
                     "files; they were NOT converted into empty predictions.")
    if metrics:
        lines += [
            "", "## Dev metrics (successful guids only)",
            f"- Task-1a: micro-F1 {metrics['task1a']['micro_f1']:.4f}, "
            f"macro-F1 {metrics['task1a']['macro_f1']:.4f}",
            f"- Task-1b: micro-F1 {metrics['task1b']['micro_f1']:.4f}, "
            f"macro-F1 {metrics['task1b']['macro_f1']:.4f}, "
            f"DRR {metrics['task1b']['direction_reverse_rate']:.4f}",
        ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nRun status: {status}")
    print(f"Artifacts: {out_dir}")
    return 0 if status == RUN_COMPLETE else 1


if __name__ == "__main__":
    sys.exit(main())
