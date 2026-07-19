#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V3 — two-generator prompt ensemble + precision verifier
+ optional frozen label-aware policy. Default provider/model:
deepseek / deepseek-v4-flash (switchable via CLI, e.g. --model deepseek-v4-pro).

Architecture per article:
  1. Variant A (concise balanced prompt)   → strict-validated predictions
  2. Variant B (targeted recall prompt,
     TRAIN-only demonstrations)            → strict-validated predictions
  3. Uncertain (actor, l1) pairs (single support or direction disagreement)
     → compact verifier call (accept/reject + direction), strict-validated
  4. Deterministic ensemble stages: variant_a, variant_b, union,
     intersection, verified; final = frozen label-aware policy if supplied,
     else the documented generic rule (verified; intersection when the
     verifier is disabled).
  5. Task-1a derived deterministically from final (and per-stage) Task-1b.

Guarantees inherited from Pipeline 2 (modules reused, not copied):
  * all-or-nothing schema validation, no silent repair or direction
    normalization, failures never become empty predictions;
  * identity-bound cache (provider, model, variant, prompt hash, taxonomy
    hash, rarity hash, demo-set hash, article hash, schema versions,
    temperature, token limit, verifier candidate hash); only successful
    schema-valid entries are reused;
  * failed articles → run status INCOMPLETE/FAILED, structured failure log.

New in V3:
  * deterministic HTTP 4xx provider errors are configuration errors: the
    article fails immediately (no retry) and the run aborts after
    CONFIG_ERROR_ABORT of them;
  * modes: dev / test / calibrate. Calibrate runs on a deterministic TRAIN
    split (demonstration articles excluded) so label-aware policies are
    learned without touching dev/test gold. Test mode never loads gold.

Usage (from project root):
    python src/run_pipeline_prompt_v3.py --dry_run --mode dev
    python src/run_pipeline_prompt_v3.py --mode dev --limit 3
    python src/run_pipeline_prompt_v3.py --mode dev --model deepseek-v4-pro
    python src/run_pipeline_prompt_v3.py --mode calibrate --calib_size 120
    python src/run_pipeline_prompt_v3.py --mode dev --policy <policy.json>

API keys come only from the environment (DEEPSEEK_API_KEY / OPENAI_API_KEY)
or the project .env file; never from the command line.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import shlex
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))

from task1_v2_taxonomy import (
    Taxonomy, TaxonomyValidationError, load_taxonomy, build_rarity_metadata,
    compute_article_hash, canonical_json, sha256_text, N_L1, N_L2,
    TRAIN_LABELS_PATH,
)
from task1_v2_schema import (
    SCHEMA_VERSION, ERR_API, ERR_EMPTY, ERR_SCHEMA, ERR_SEMANTIC,
    ValidationIssue, parse_response_json, validate_response_object,
    sorted_task1b_values, derive_task1a_values, build_response_json_schema,
    article_actor_ids,
)
from run_pipeline_prompt_v2 import (
    PROVIDERS, ProviderSpec, ProviderTransientError, resolve_api_key,
    CacheStore, cache_key, model_slug, current_git_commit, append_jsonl,
    filter_by_guids,
)
from prompts_task1_v3 import (
    PROMPT_VERSION_V3, VARIANT_A, VARIANT_B, VARIANT_VERIFIER,
    build_system_prompt_a, build_system_prompt_b, build_verifier_system_prompt,
    build_verifier_user_prompt, select_demonstrations,
    compute_prompt_hash_a, compute_prompt_hash_b, compute_prompt_hash_verifier,
    TRAIN_ARTICLES_PATH,
)
from prompts_task1_v2 import build_user_prompt
from task1_v3_ensemble import (
    VERIFIER_SCHEMA_VERSION, STAGE_NAMES, preds_to_tuples, analyze_pairs,
    verifier_candidates, classify_pair, candidates_hash,
    validate_verifier_response, verdicts_from_response,
    build_verifier_json_schema, build_stage_sets, apply_policy,
    tuples_to_prediction_items, load_policy, policy_label_strategies,
    check_policy_compatibility, PolicyValidationError,
    compute_pair_diagnostics, final_contribution_by_stage,
)

# ── Dataset paths ─────────────────────────────────────────────────────────────
DEV_ARTICLES = BASE_DIR / "dataset" / "dev" / "dev_event_base.json"
TEST_ARTICLES = BASE_DIR / "dataset" / "test" / "test_article_event_base.json"
DEV_LABELS = BASE_DIR / "dataset" / "gold_labels" / "dev" / "dev_human_values.json"

LOGS_DIR = BASE_DIR / "logs"
OUTPUT_ROOT = BASE_DIR / "output" / "task1_prompt_v3"

METHOD_NAME = "prompt_ensemble_v3"
TEMPERATURE = 0.0
MAX_COMPLETION_TOKENS = 4000
REQUEST_TIMEOUT_S = 120   # a hung request becomes a visible transient failure
DEFAULT_MAX_RETRIES = 3
TRANSIENT_SLEEP_S = 5
CORRECTION_SLEEP_S = 2
CONFIG_ERROR_ABORT = 3        # abort the run after this many deterministic 4xx
CALIB_SPLIT_SALT = "fehu_task1_v3_calibration_split"

ERR_API_CONFIG = "api_config_failure"

RUN_COMPLETE = "COMPLETE"
RUN_INCOMPLETE = "INCOMPLETE"
RUN_FAILED = "FAILED"

COUNTER_KEYS = (
    "api_calls", "cache_hits", "retries_api", "retries_empty", "retries_json",
    "retries_schema", "retries_semantic", "config_errors",
    "prompt_tokens", "completion_tokens",
)


class ProviderConfigError(RuntimeError):
    """Deterministic provider error (HTTP 400/401/403/404/422). Retrying the
    identical request cannot succeed; treated as a configuration error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


_CONFIG_STATUS_CODES = {400, 401, 403, 404, 422}


def make_caller_v3(spec: ProviderSpec, model: str) -> Callable:
    """call_fn(messages, json_schema) -> (raw_text, usage_dict_or_None).

    Deterministic 4xx → ProviderConfigError (no retry); anything else →
    ProviderTransientError (bounded retry). Imported lazily so tests and
    --dry_run never need the openai package or an API key."""
    from openai import OpenAI

    api_key = resolve_api_key(spec)
    if not api_key:
        raise SystemExit(
            f"ERROR: no API key found. Set {spec.api_key_env} in the "
            f"environment or the project .env file.")
    client = OpenAI(api_key=api_key, base_url=spec.base_url)

    def call(messages: List[dict], json_schema: Optional[dict]):
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": TEMPERATURE,
            "timeout": REQUEST_TIMEOUT_S,
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
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status in _CONFIG_STATUS_CODES:
                raise ProviderConfigError(
                    f"{type(e).__name__} (HTTP {status}): {e}",
                    status_code=status) from e
            raise ProviderTransientError(f"{type(e).__name__}: {e}") from e
        content = response.choices[0].message.content
        usage = None
        if getattr(response, "usage", None) is not None:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
            }
        return (content if content is not None else ""), usage

    return call


# ============================================================
# Generic validated-call loop (shared by generators and verifier)
# ============================================================

@dataclass
class CallOutcome:
    stage: str
    success: bool
    obj: Optional[dict]
    issues: List[dict]
    attempts: int
    raw_attempts: List[dict]
    config_error: bool = False


def _correction_message(issues: List[ValidationIssue], contract_hint: str) -> str:
    listing = "\n".join(
        f"- [{i.error_type}] field {i.field}: {i.reason}" for i in issues)
    return ("Your previous response violated the required output contract. "
            "Violations:\n" + listing + "\n\n" + contract_hint)


GENERATOR_CONTRACT_HINT = (
    "Re-emit your classification as ONE valid JSON object with only the keys "
    "guid and predictions; each prediction has exactly actor_id, l1_value_id, "
    "direction as strings; direction is '0' or '1'; actor IDs copied exactly "
    "from the input; no duplicates; no markdown; no prose. Do not change any "
    "classification decision except as required to fix the listed violations."
)
VERIFIER_CONTRACT_HINT = (
    "Re-emit ONE valid JSON object with only the keys guid and verdicts; "
    "exactly one verdict per listed candidate; each verdict has exactly "
    "actor_id, l1_value_id, accept, direction as strings with accept and "
    "direction in {'0','1'}; no markdown; no prose. Do not change any "
    "accept/direction decision except as required to fix the listed violations."
)


def run_validated_call(
    stage: str,
    guid: str,
    system_prompt: str,
    user_prompt: str,
    validate_fn: Callable[[object, int], List[ValidationIssue]],
    json_schema: Optional[dict],
    call_fn: Callable,
    max_retries: int,
    counters: Dict[str, int],
    contract_hint: str,
    sleep_fn: Callable[[float], None] = time.sleep,
    failure_sink: Optional[Callable[[dict], None]] = None,
) -> CallOutcome:
    """call → parse → validate with bounded correction retries.

    Never fabricates a result: on final failure success=False, obj=None.
    ProviderConfigError fails immediately without retry."""
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    messages = list(base_messages)
    all_issues: List[dict] = []
    raw_attempts: List[dict] = []
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        try:
            counters["api_calls"] += 1
            raw, usage = call_fn(messages, json_schema)
            if usage:
                counters["prompt_tokens"] += usage.get("prompt_tokens", 0)
                counters["completion_tokens"] += usage.get("completion_tokens", 0)
        except ProviderConfigError as e:
            counters["config_errors"] += 1
            issue = ValidationIssue(guid=guid, error_type=ERR_API_CONFIG,
                                    field="<api>", invalid_value=None,
                                    reason=str(e), retry=attempt)
            all_issues.append(issue.to_dict())
            raw_attempts.append({"attempt": attempt, "kind": ERR_API_CONFIG,
                                 "raw": None})
            if failure_sink:
                failure_sink({"guid": guid, "stage": stage,
                              "error_class": "ProviderConfigError",
                              "status_code": e.status_code, "message": str(e),
                              "attempt": attempt,
                              "timestamp": datetime.now(timezone.utc).isoformat()})
            return CallOutcome(stage=stage, success=False, obj=None,
                               issues=all_issues, attempts=attempt,
                               raw_attempts=raw_attempts, config_error=True)
        except ProviderTransientError as e:
            issue = ValidationIssue(guid=guid, error_type=ERR_API,
                                    field="<api>", invalid_value=None,
                                    reason=str(e), retry=attempt)
            all_issues.append(issue.to_dict())
            raw_attempts.append({"attempt": attempt, "kind": ERR_API, "raw": None})
            counters["retries_api"] += 1
            if failure_sink:
                failure_sink({"guid": guid, "stage": stage,
                              "error_class": "ProviderTransientError",
                              "status_code": None, "message": str(e),
                              "attempt": attempt,
                              "timestamp": datetime.now(timezone.utc).isoformat()})
            if attempt < max_retries:
                sleep_fn(TRANSIENT_SLEEP_S)
            continue

        obj, parse_issues = parse_response_json(raw, guid, attempt)
        if parse_issues:
            kind = parse_issues[0].error_type
            all_issues.extend(i.to_dict() for i in parse_issues)
            raw_attempts.append({"attempt": attempt, "kind": kind, "raw": raw})
            counters["retries_empty" if kind == ERR_EMPTY else "retries_json"] += 1
            if attempt < max_retries:
                if kind == ERR_EMPTY:
                    messages = list(base_messages)
                    sleep_fn(TRANSIENT_SLEEP_S)
                else:
                    messages = base_messages + [
                        {"role": "assistant", "content": raw},
                        {"role": "user",
                         "content": _correction_message(parse_issues, contract_hint)},
                    ]
                    sleep_fn(CORRECTION_SLEEP_S)
            continue

        val_issues = validate_fn(obj, attempt)
        if val_issues:
            all_issues.extend(i.to_dict() for i in val_issues)
            has_schema = any(i.error_type == ERR_SCHEMA for i in val_issues)
            raw_attempts.append({"attempt": attempt,
                                 "kind": ERR_SCHEMA if has_schema else ERR_SEMANTIC,
                                 "raw": raw})
            counters["retries_schema" if has_schema else "retries_semantic"] += 1
            if attempt < max_retries:
                messages = base_messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user",
                     "content": _correction_message(val_issues, contract_hint)},
                ]
                sleep_fn(CORRECTION_SLEEP_S)
            continue

        raw_attempts.append({"attempt": attempt, "kind": "success", "raw": raw})
        return CallOutcome(stage=stage, success=True, obj=obj,
                           issues=all_issues, attempts=attempt,
                           raw_attempts=raw_attempts)

    return CallOutcome(stage=stage, success=False, obj=None, issues=all_issues,
                       attempts=attempt, raw_attempts=raw_attempts)


# ============================================================
# Cache identity (V3)
# ============================================================

def cache_identity_v3(provider: str, model: str, variant: str,
                      prompt_hash: str, taxonomy_hash: str, rarity_hash: str,
                      demo_set_hash: str, article: dict,
                      verifier_cfg: Optional[dict] = None) -> dict:
    return {
        "pipeline": METHOD_NAME,
        "provider": provider,
        "model": model,
        "variant": variant,
        "prompt_version": PROMPT_VERSION_V3,
        "prompt_hash": prompt_hash,
        "taxonomy_hash": taxonomy_hash,
        "rarity_hash": rarity_hash,
        "demo_set_hash": demo_set_hash,
        "article_hash": compute_article_hash(article),
        "article_guid": str(article["guid"]),
        "schema_version": SCHEMA_VERSION,
        "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_COMPLETION_TOKENS,
        "verifier_config": verifier_cfg or {},
    }


# ============================================================
# Per-article orchestration
# ============================================================

@dataclass
class RunContext:
    args: argparse.Namespace
    tax: Taxonomy
    rarity: dict
    system_prompts: Dict[str, str]
    prompt_hashes: Dict[str, str]
    demo_set_hash: str
    call_fn: Callable
    cache: CacheStore
    counters: Dict[str, int]
    lock: threading.Lock
    out_dir: Path
    max_retries: int
    use_verifier: bool
    abort_event: threading.Event = field(default_factory=threading.Event)

    def log(self, name: str, obj: dict) -> None:
        with self.lock:
            append_jsonl(self.out_dir / name, obj)

    def bump(self, deltas: Dict[str, int]) -> None:
        with self.lock:
            for k, v in deltas.items():
                self.counters[k] += v


@dataclass
class ArticleResult:
    guid: str
    article: dict
    success: bool
    stage_outcomes: Dict[str, dict]           # per stage: success/from_cache/attempts
    stages: Optional[Dict[str, Set[tuple]]]   # ensemble stage tuple sets
    pair_categories: Dict[str, int]
    verifier_stats: Dict[str, int]
    error_types: List[str]
    config_error: bool = False
    pair_diag: Optional[dict] = None          # compute_pair_diagnostics output


def _cached_call(ctx: RunContext, article: dict, variant: str,
                 system_prompt: str, user_prompt: str,
                 validate_fn, json_schema,
                 verifier_cfg: Optional[dict] = None,
                 result_key: str = "predictions"):
    """Cache-aware validated call. Returns (success, payload, meta)."""
    guid = str(article["guid"])
    ident = cache_identity_v3(
        ctx.args.provider, ctx.args.model, variant,
        ctx.prompt_hashes[variant], ctx.tax.taxonomy_hash,
        ctx.rarity["rarity_hash"],
        ctx.demo_set_hash if variant == VARIANT_B else "",
        article, verifier_cfg,
    )
    with ctx.lock:
        cached = ctx.cache.lookup(ident)
    if cached is not None:
        ctx.bump({"cache_hits": 1})
        return True, cached["predictions"], {
            "from_cache": True, "attempts": 0, "config_error": False}

    local_counters = {k: 0 for k in COUNTER_KEYS}
    outcome = run_validated_call(
        stage=variant, guid=guid, system_prompt=system_prompt,
        user_prompt=user_prompt, validate_fn=validate_fn,
        json_schema=json_schema, call_fn=ctx.call_fn,
        max_retries=ctx.max_retries, counters=local_counters,
        contract_hint=(VERIFIER_CONTRACT_HINT if variant == VARIANT_VERIFIER
                       else GENERATOR_CONTRACT_HINT),
        failure_sink=lambda rec: ctx.log("failure_log.jsonl", rec),
    )
    ctx.bump(local_counters)
    for att in outcome.raw_attempts:
        ctx.log("raw_responses.jsonl",
                {"guid": guid, "stage": variant, **att,
                 "timestamp": datetime.now(timezone.utc).isoformat()})
    for issue in outcome.issues:
        ctx.log("validation_errors.jsonl", {"stage": variant, **issue})

    payload = outcome.obj[result_key] if outcome.success else None
    with ctx.lock:
        ctx.cache.store(ident, outcome.success, payload,
                        [i["error_type"] for i in outcome.issues])
    return outcome.success, payload, {
        "from_cache": False, "attempts": outcome.attempts,
        "config_error": outcome.config_error,
        "error_types": sorted({i["error_type"] for i in outcome.issues})}


def process_article_v3(article: dict, ctx: RunContext) -> ArticleResult:
    guid = str(article["guid"])
    user_prompt = build_user_prompt(article)
    gen_schema = build_response_json_schema(article, ctx.tax)
    stage_outcomes: Dict[str, dict] = {}
    error_types: Set[str] = set()
    config_error = False

    def gen_validate(obj, attempt):
        return validate_response_object(obj, article, ctx.tax, attempt)

    results = {}
    for variant in (VARIANT_A, VARIANT_B):
        ok, preds, meta = _cached_call(
            ctx, article, variant, ctx.system_prompts[variant], user_prompt,
            gen_validate, gen_schema)
        stage_outcomes[variant] = {"success": ok, **meta}
        results[variant] = preds
        if not ok:
            error_types.update(meta.get("error_types", []))
            config_error = config_error or meta.get("config_error", False)

    if not (stage_outcomes[VARIANT_A]["success"]
            and stage_outcomes[VARIANT_B]["success"]):
        return ArticleResult(guid=guid, article=article, success=False,
                             stage_outcomes=stage_outcomes, stages=None,
                             pair_categories={}, verifier_stats={},
                             error_types=sorted(error_types),
                             config_error=config_error)

    a_tuples = preds_to_tuples(results[VARIANT_A])
    b_tuples = preds_to_tuples(results[VARIANT_B])
    pairs = analyze_pairs(a_tuples, b_tuples)
    pair_categories: Dict[str, int] = defaultdict(int)
    for da, db in pairs.values():
        pair_categories[classify_pair(da, db)] += 1

    verdicts = None
    verifier_stats: Dict[str, int] = {"candidates": 0, "accepted": 0,
                                      "rejected": 0}
    if ctx.use_verifier:
        candidates = verifier_candidates(pairs, article)
        verifier_stats["candidates"] = len(candidates)
        if candidates:
            v_cfg = {"enabled": True, "candidates_hash": candidates_hash(candidates)}
            v_user = build_verifier_user_prompt(article, candidates, ctx.tax)
            v_schema = build_verifier_json_schema(article, candidates)

            def v_validate(obj, attempt):
                return validate_verifier_response(obj, article, ctx.tax,
                                                  candidates, attempt)

            ok, v_payload, meta = _cached_call(
                ctx, article, VARIANT_VERIFIER,
                ctx.system_prompts[VARIANT_VERIFIER], v_user,
                v_validate, v_schema, verifier_cfg=v_cfg,
                result_key="verdicts")
            stage_outcomes[VARIANT_VERIFIER] = {"success": ok, **meta}
            if not ok:
                # A failed verifier is a failed article: silently dropping the
                # uncertain candidates would convert an API/schema failure
                # into a semantic decision.
                error_types.update(meta.get("error_types", []))
                return ArticleResult(
                    guid=guid, article=article, success=False,
                    stage_outcomes=stage_outcomes, stages=None,
                    pair_categories=dict(pair_categories),
                    verifier_stats=verifier_stats,
                    error_types=sorted(error_types),
                    config_error=meta.get("config_error", False))
            verdicts = verdicts_from_response({"verdicts": v_payload})
            verifier_stats["accepted"] = sum(
                1 for v in verdicts.values() if v["accept"] == "1")
            verifier_stats["rejected"] = sum(
                1 for v in verdicts.values() if v["accept"] == "0")
        else:
            verdicts = {}

    stages = build_stage_sets(a_tuples, b_tuples, pairs, verdicts)
    pair_diag = compute_pair_diagnostics(a_tuples, b_tuples, pairs, verdicts,
                                         ctx.rarity)
    return ArticleResult(guid=guid, article=article, success=True,
                         stage_outcomes=stage_outcomes, stages=stages,
                         pair_categories=dict(pair_categories),
                         verifier_stats=verifier_stats, error_types=[],
                         pair_diag=pair_diag)


def compute_run_status(n_requested: int, n_succeeded: int, n_failed: int) -> str:
    if n_failed == 0 and n_succeeded == n_requested:
        return RUN_COMPLETE
    return RUN_FAILED if n_succeeded == 0 else RUN_INCOMPLETE


# ============================================================
# Calibration split (TRAIN only, deterministic, demo GUIDs excluded)
# ============================================================

def calibration_split(train_articles: List[dict], demo_guids: Set[str],
                      size: int) -> List[dict]:
    ranked = sorted(
        (a for a in train_articles if str(a["guid"]) not in demo_guids),
        key=lambda a: sha256_text(f"{CALIB_SPLIT_SALT}:{a['guid']}"))
    return ranked[:size]


# ============================================================
# Evaluation + diagnostics
# ============================================================

def evaluate_predictions(pred_1a_path: Path, pred_1b_path: Path,
                         gold_path: Path, guids: Set[str]) -> dict:
    from evaluation import (
        parse_task1a, parse_task1b, evaluate, l2_universe, l1_dir_universe,
        direction_reverse_rate_gold_excl,
    )
    gold_1a = filter_by_guids(parse_task1a(str(gold_path)), guids)
    pred_1a = filter_by_guids(parse_task1a(str(pred_1a_path)), guids)
    gold_1b = filter_by_guids(parse_task1b(str(gold_path)), guids)
    pred_1b = filter_by_guids(parse_task1b(str(pred_1b_path)), guids)
    r1a = evaluate(gold_1a, pred_1a, l2_universe())
    r1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(gold_1b, pred_1b)
    return {
        "task1a": r1a,
        "task1b": {**r1b, "direction_reverse_rate": drr,
                   "direction_reverse_count": rev,
                   "direction_reverse_denom_gold_excl": den,
                   "ambiguous_gold_values_filtered": amb},
    }


def per_label_counts(gold: dict, pred: dict):
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


def write_final_diagnostics(out_dir: Path, gold_path: Path, guids: Set[str],
                            tax: Taxonomy, rarity: dict) -> dict:
    """Per-label CSV + frequency-group metrics for the FINAL predictions."""
    from evaluation import parse_task1a, parse_task1b, safe_div, f1_from_pr
    gold_1b = filter_by_guids(parse_task1b(str(gold_path)), guids)
    pred_1b = filter_by_guids(parse_task1b(str(out_dir / "pred_task1b.json")), guids)
    gold_1a = filter_by_guids(parse_task1a(str(gold_path)), guids)
    pred_1a = filter_by_guids(parse_task1a(str(out_dir / "pred_task1a.json")), guids)

    rows = []
    tp, fp, fn = per_label_counts(gold_1b, pred_1b)
    group_counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "labels": 0})
    for l1_id in tax.l1_ids:
        e = tax.l1_by_id[l1_id]
        meta = rarity["labels"][l1_id]
        for d in ("0", "1"):
            lab = f"{d}:{l1_id}"
            p = safe_div(tp[lab], tp[lab] + fp[lab])
            r = safe_div(tp[lab], tp[lab] + fn[lab])
            rows.append({
                "task": "task1b", "label": lab, "id": l1_id, "name": e.l1_name,
                "direction": d, "train_gold_count": meta["train_gold_count"],
                "frequency_group": meta["frequency_group"],
                "gold_count": tp[lab] + fn[lab],
                "pred_count": tp[lab] + fp[lab],
                "tp": tp[lab], "fp": fp[lab], "fn": fn[lab],
                "precision": round(p, 4), "recall": round(r, 4),
                "f1": round(f1_from_pr(p, r), 4),
            })
            g = group_counts[meta["frequency_group"]]
            g["tp"] += tp[lab]
            g["fp"] += fp[lab]
            g["fn"] += fn[lab]
            if tp[lab] + fn[lab] > 0:
                g["labels"] += 1
    tp, fp, fn = per_label_counts(gold_1a, pred_1a)
    for l2_id in tax.l2_ids:
        p = safe_div(tp[l2_id], tp[l2_id] + fp[l2_id])
        r = safe_div(tp[l2_id], tp[l2_id] + fn[l2_id])
        rows.append({
            "task": "task1a", "label": l2_id, "id": l2_id,
            "name": tax.l2_id_to_name[l2_id], "direction": "",
            "train_gold_count": "", "frequency_group": "",
            "gold_count": tp[l2_id] + fn[l2_id],
            "pred_count": tp[l2_id] + fp[l2_id],
            "tp": tp[l2_id], "fp": fp[l2_id], "fn": fn[l2_id],
            "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(f1_from_pr(p, r), 4),
        })
    with open(out_dir / "per_label_metrics.csv", "w", encoding="utf-8",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    groups = {}
    for group, g in sorted(group_counts.items()):
        p = safe_div(g["tp"], g["tp"] + g["fp"])
        r = safe_div(g["tp"], g["tp"] + g["fn"])
        groups[group] = {
            "gold_supported_label_slots": g["labels"],
            "tp": g["tp"], "fp": g["fp"], "fn": g["fn"],
            "micro_precision": round(p, 4), "micro_recall": round(r, 4),
            "micro_f1": round(f1_from_pr(p, r), 4),
        }
    return groups


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def load_price_config(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("input_usd_per_1m", "output_usd_per_1m"):
        if not isinstance(cfg.get(k), (int, float)):
            raise SystemExit(f"ERROR: price config must contain numeric {k!r}.")
    return cfg


# ============================================================
# CLI + main
# ============================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="FEHU Task-1 Pipeline V3 (two-generator ensemble + "
                    "verifier + frozen label-aware policy). API keys via "
                    "environment/.env only.")
    ap.add_argument("--mode", choices=["dev", "test", "calibrate"], default="dev")
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default="deepseek")
    ap.add_argument("--model", type=str, default="deepseek-v4-flash")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N articles of the mode's "
                         "article list.")
    ap.add_argument("--guid", action="append", default=None,
                    help="Process only this article GUID (repeatable).")
    ap.add_argument("--output_dir", type=str, default=None,
                    help="Override output directory (must be empty unless "
                         "--resume).")
    ap.add_argument("--resume", action="store_true",
                    help="Allow writing into an existing --output_dir; "
                         "previously successful calls are supplied by the "
                         "identity-bound cache, so only missing/failed calls "
                         "hit the API.")
    ap.add_argument("--max_retries", type=int, default=DEFAULT_MAX_RETRIES)
    ap.add_argument("--concurrency", type=int, default=1,
                    help="Parallel articles (default 1; max 8).")
    ap.add_argument("--use_verifier", dest="use_verifier", action="store_true",
                    default=True, help="Enable the verifier stage (default).")
    ap.add_argument("--no_verifier", dest="use_verifier", action="store_false",
                    help="Disable the verifier; the ensemble falls back to "
                         "the strict intersection for uncertain candidates.")
    ap.add_argument("--policy", type=str, default=None,
                    help="Frozen label-aware policy JSON produced by "
                         "src/calibrate_task1_v3.py. Without it the generic "
                         "deterministic rule is used and label-aware "
                         "calibration is marked unavailable.")
    ap.add_argument("--allow_policy_mismatch", action="store_true",
                    help="Apply a policy whose calibration provenance does "
                         "not match this run (recorded in the manifest; the "
                         "result is NOT a clean application of the policy).")
    ap.add_argument("--calib_size", type=int, default=120,
                    help="Calibration split size (calibrate mode only).")
    ap.add_argument("--demo_count", type=int, default=2,
                    help="Number of TRAIN demonstrations in Variant B.")
    ap.add_argument("--gold_labels", type=str, default=None,
                    help="Gold labels path. Optional in dev/calibrate "
                         "(defaults to the official dev/train gold); "
                         "forbidden in test mode.")
    ap.add_argument("--price_config", type=str, default=None,
                    help="JSON with input_usd_per_1m / output_usd_per_1m for "
                         "cost estimates.")
    ap.add_argument("--no_cache", action="store_true")
    ap.add_argument("--dry_run", action="store_true",
                    help="Validate everything and print call/token/cost "
                         "estimates without any API call.")
    return ap.parse_args(argv)


def resolve_output_dir_v3(args, slug: str) -> Path:
    if args.output_dir:
        out = Path(args.output_dir)
        if not out.is_absolute():
            out = BASE_DIR / out
        if out.exists() and any(out.iterdir()) and not args.resume:
            raise SystemExit(
                f"ERROR: --output_dir {out} exists and is not empty. "
                f"Pass --resume to continue a previous run there.")
        out.mkdir(parents=True, exist_ok=True)
        return out
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_ROOT / f"{ts}_{args.mode}_{args.provider}_{slug}"
    if out.exists():
        raise SystemExit(f"ERROR: output dir collision: {out}. Re-run.")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _sdk_version() -> str:
    try:
        from importlib.metadata import version
        return version("openai")
    except Exception:
        return "unavailable"


def stage_file_names(stage: str) -> Tuple[str, str]:
    return f"pred_task1a_{stage}.json", f"pred_task1b_{stage}.json"


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_retries < 1:
        raise SystemExit("ERROR: --max_retries must be >= 1")
    if not (1 <= args.concurrency <= 8):
        raise SystemExit("ERROR: --concurrency must be in 1..8")
    if args.mode == "test" and args.gold_labels:
        raise SystemExit("ERROR: test mode never reads gold labels; "
                         "remove --gold_labels.")
    price_cfg = load_price_config(args.price_config)
    slug = model_slug(args.model)
    started = datetime.now(timezone.utc).isoformat()

    # ── Taxonomy, rarity, demonstrations, prompts ───────────────────────────
    try:
        tax = load_taxonomy()
        rarity = build_rarity_metadata(tax)
    except TaxonomyValidationError as e:
        raise SystemExit(f"FATAL taxonomy validation error:\n{e}")

    demos, demo_provenance = select_demonstrations(tax, rarity, n=args.demo_count)
    if len(demos) < args.demo_count:
        raise SystemExit(
            f"ERROR: only {len(demos)} demonstration candidates found in "
            f"TRAIN for --demo_count {args.demo_count}.")
    demo_guids = {d["guid"] for d in demos}

    system_prompts = {
        VARIANT_A: build_system_prompt_a(tax),
        VARIANT_B: build_system_prompt_b(tax, rarity, demos),
        VARIANT_VERIFIER: build_verifier_system_prompt(tax),
    }
    prompt_hashes = {
        VARIANT_A: compute_prompt_hash_a(tax),
        VARIANT_B: compute_prompt_hash_b(tax, rarity, demos),
        VARIANT_VERIFIER: compute_prompt_hash_verifier(tax),
    }

    # ── Articles + gold path per mode ───────────────────────────────────────
    if args.mode == "dev":
        articles = json.loads(DEV_ARTICLES.read_text(encoding="utf-8"))
        gold_path = Path(args.gold_labels) if args.gold_labels else DEV_LABELS
    elif args.mode == "test":
        articles = json.loads(TEST_ARTICLES.read_text(encoding="utf-8"))
        gold_path = None
    else:  # calibrate
        train_articles = json.loads(TRAIN_ARTICLES_PATH.read_text(encoding="utf-8"))
        articles = calibration_split(train_articles, demo_guids, args.calib_size)
        gold_path = (Path(args.gold_labels) if args.gold_labels
                     else TRAIN_LABELS_PATH)

    if args.guid:
        wanted = set(args.guid)
        articles = [a for a in articles if str(a["guid"]) in wanted]
        missing = wanted - {str(a["guid"]) for a in articles}
        if missing:
            raise SystemExit(f"ERROR: GUIDs not found in {args.mode} "
                             f"article list: {sorted(missing)}")
    if args.limit:
        articles = articles[: args.limit]
    if not articles:
        raise SystemExit("ERROR: no articles selected.")
    requested_guids = [str(a["guid"]) for a in articles]
    overlap = demo_guids & set(requested_guids)
    if overlap:
        raise SystemExit(f"FATAL: demonstration articles overlap the "
                         f"evaluated articles: {sorted(overlap)}")

    # ── Frozen policy ───────────────────────────────────────────────────────
    default_strategy = "verified" if args.use_verifier else "intersection"
    policy = None
    policy_report = {"available": False,
                     "note": "No frozen policy supplied; the generic "
                             f"deterministic rule ({default_strategy}) is "
                             "the final output. Label-aware calibration "
                             "UNAVAILABLE for this run."}
    if args.policy:
        try:
            policy = load_policy(Path(args.policy))
        except PolicyValidationError as e:
            raise SystemExit(f"ERROR: invalid policy file: {e}")
        run_identity = {
            "provider": args.provider, "model": args.model,
            "temperature": TEMPERATURE, "prompt_hashes": prompt_hashes,
            "taxonomy_hash": tax.taxonomy_hash,
            "rarity_hash": rarity["rarity_hash"],
            "demo_set_hash": demo_provenance["demo_set_hash"],
            "schema_version": SCHEMA_VERSION,
            "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
            "verifier_enabled": args.use_verifier,
        }
        mismatches = check_policy_compatibility(policy, run_identity)
        if mismatches and not args.allow_policy_mismatch:
            raise SystemExit(
                "ERROR: the frozen policy was calibrated under a different "
                "configuration:\n  - " + "\n  - ".join(mismatches) +
                "\nRe-calibrate, or pass --allow_policy_mismatch to apply it "
                "anyway (recorded as a provenance violation).")
        policy_report = {
            "available": True,
            "path": str(Path(args.policy).resolve()),
            "policy_version": policy["policy_version"],
            "default_strategy": policy["default_strategy"],
            "n_label_overrides": sum(
                1 for v in policy["labels"].values()
                if v["strategy"] != "default"),
            "provenance": policy["calibration"],
            "mismatches": mismatches,
        }
        default_strategy = policy["default_strategy"]

    # ── Output dir + cache ──────────────────────────────────────────────────
    out_dir = resolve_output_dir_v3(args, slug)
    cache_path = None if args.no_cache else (
        LOGS_DIR / f"cache_task1_prompt_v3_{args.mode}_{args.provider}_{slug}.json")

    print(f"Pipeline V3  mode={args.mode} provider={args.provider} "
          f"model={args.model} articles={len(articles)} "
          f"verifier={'on' if args.use_verifier else 'off'} "
          f"policy={'frozen' if policy else 'generic'} dry_run={args.dry_run}")
    print(f"  prompt_version={PROMPT_VERSION_V3}")
    for v in (VARIANT_A, VARIANT_B, VARIANT_VERIFIER):
        print(f"  {v}: hash={prompt_hashes[v][:16]}…")
    print(f"  demos: {sorted(demo_guids)} (train), "
          f"demo_set_hash={demo_provenance['demo_set_hash'][:16]}…")
    print(f"  output: {out_dir}")

    # ── Snapshots ───────────────────────────────────────────────────────────
    snap = [f"PROMPT_VERSION: {PROMPT_VERSION_V3}"]
    for v in (VARIANT_A, VARIANT_B, VARIANT_VERIFIER):
        snap += [f"\n===== {v} (hash {prompt_hashes[v]}) =====",
                 system_prompts[v]]
    (out_dir / "prompt_snapshot.txt").write_text("\n".join(snap), encoding="utf-8")
    (out_dir / "demo_provenance.json").write_text(
        json.dumps(demo_provenance, ensure_ascii=False, indent=2),
        encoding="utf-8")
    if args.mode == "calibrate":
        (out_dir / "calibration_split.json").write_text(json.dumps({
            "salt": CALIB_SPLIT_SALT, "size": len(articles),
            "excluded_demo_guids": sorted(demo_guids),
            "guids": requested_guids,
            "calibration_guid_hash": sha256_text(canonical_json(requested_guids)),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    counters = {k: 0 for k in COUNTER_KEYS}
    manifest = {
        "script": "src/run_pipeline_prompt_v3.py",
        "method": METHOD_NAME,
        "prompt_version": PROMPT_VERSION_V3,
        "provider": args.provider,
        "model": args.model,
        "model_slug": slug,
        "mode": args.mode,
        "cli_args": vars(args),
        "command_line": " ".join(shlex.quote(a) for a in sys.argv),
        "git_commit": current_git_commit(),
        "python_version": platform.python_version(),
        "openai_sdk_version": _sdk_version(),
        "temperature": TEMPERATURE,
        "max_tokens": MAX_COMPLETION_TOKENS,
        "request_timeout_s": REQUEST_TIMEOUT_S,
        "max_retries": args.max_retries,
        "concurrency": args.concurrency,
        "use_verifier": args.use_verifier,
        "default_strategy": default_strategy,
        "prompt_hashes": prompt_hashes,
        "taxonomy_hash": tax.taxonomy_hash,
        "rarity_hash": rarity["rarity_hash"],
        "demo_set_hash": demo_provenance["demo_set_hash"],
        "demo_provenance": demo_provenance,
        "schema_version": SCHEMA_VERSION,
        "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
        "policy": policy_report,
        "gold_labels_path": str(gold_path) if gold_path else None,
        "dataset_paths": {
            "dev_articles": str(DEV_ARTICLES),
            "test_articles": str(TEST_ARTICLES),
            "train_articles": str(TRAIN_ARTICLES_PATH),
            "train_labels_for_rarity": str(TRAIN_LABELS_PATH),
        },
        "output_dir": str(out_dir),
        "cache_path": str(cache_path) if cache_path else None,
        "n_articles_requested": len(articles),
        "requested_guids": requested_guids,
        "started_utc": started,
    }

    # ── Dry run ─────────────────────────────────────────────────────────────
    if args.dry_run:
        checks = []
        for p in (DEV_ARTICLES, TEST_ARTICLES, TRAIN_ARTICLES_PATH,
                  TRAIN_LABELS_PATH):
            assert p.exists(), f"missing dataset path: {p}"
        checks.append("OK   dataset paths exist")
        assert tax.l1_ids == [str(i) for i in range(N_L1)]
        assert tax.l2_ids == [str(i) for i in range(N_L2)]
        checks.append(f"OK   taxonomy complete ({N_L1} L1 / {N_L2} L2)")
        assert all(str(d['guid']) not in set(requested_guids) for d in demos)
        checks.append(f"OK   {len(demos)} TRAIN demos, disjoint from "
                      f"evaluated articles")
        assert prompt_hashes[VARIANT_A] == compute_prompt_hash_a(tax)
        checks.append("OK   prompt hashes stable")
        est_input = est_output = 0
        n_ver = len(articles) if args.use_verifier else 0
        for a in articles[: min(3, len(articles))]:
            up = build_user_prompt(a)
            assert str(a["guid"]) in up
            build_response_json_schema(a, tax)
            cache_key(cache_identity_v3(
                args.provider, args.model, VARIANT_A,
                prompt_hashes[VARIANT_A], tax.taxonomy_hash,
                rarity["rarity_hash"], "", a))
        checks.append("OK   sample user prompts, schemas, cache identities")
        for a in articles:
            up_t = estimate_tokens(build_user_prompt(a))
            est_input += (estimate_tokens(system_prompts[VARIANT_A]) + up_t
                          + estimate_tokens(system_prompts[VARIANT_B]) + up_t)
            est_output += 2 * 400
            if args.use_verifier:
                est_input += (estimate_tokens(system_prompts[VARIANT_VERIFIER])
                              + up_t + 300)
                est_output += 300
        est_calls = len(articles) * 2 + n_ver
        checks.append(f"EST  API calls (no retries): {est_calls} "
                      f"({len(articles)} articles × 2 generators"
                      f"{' + ≤1 verifier' if args.use_verifier else ''})")
        checks.append(f"EST  tokens: ~{est_input:,} input / ~{est_output:,} "
                      f"output (chars/4 heuristic)")
        if price_cfg:
            cost = (est_input * price_cfg["input_usd_per_1m"]
                    + est_output * price_cfg["output_usd_per_1m"]) / 1e6
            checks.append(f"EST  cost: ~${cost:.2f} "
                          f"(price config {args.price_config})")
        print("\nDRY-RUN VALIDATION:")
        for c in checks:
            print(f"  {c}")
        manifest.update({"dry_run": True, "checks": checks,
                         "finished_utc": datetime.now(timezone.utc).isoformat()})
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "run_status.json").write_text(json.dumps({
            "status": RUN_COMPLETE, "dry_run": True,
            "note": "Dry run: static validations passed; no API calls made.",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nDry run complete. Artifacts in {out_dir}")
        return 0

    # ── Real run ────────────────────────────────────────────────────────────
    spec = PROVIDERS[args.provider]
    ctx = RunContext(
        args=args, tax=tax, rarity=rarity, system_prompts=system_prompts,
        prompt_hashes=prompt_hashes,
        demo_set_hash=demo_provenance["demo_set_hash"],
        call_fn=make_caller_v3(spec, args.model),
        cache=CacheStore(cache_path), counters=counters,
        lock=threading.Lock(), out_dir=out_dir,
        max_retries=args.max_retries, use_verifier=args.use_verifier,
    )

    results: Dict[str, ArticleResult] = {}
    aborted = False

    def worker(article):
        if ctx.abort_event.is_set():
            return None
        return process_article_v3(article, ctx)

    done = 0
    if args.concurrency == 1:
        for article in articles:
            res = worker(article)
            if res is None:
                break
            results[res.guid] = res
            done += 1
            print(f"  [{done}/{len(articles)}] {res.guid}: "
                  f"{'ok' if res.success else 'FAILED'}")
            ctx.log("article_status.jsonl", {
                "guid": res.guid, "success": res.success,
                "stage_outcomes": res.stage_outcomes,
                "error_types": res.error_types,
                "timestamp": datetime.now(timezone.utc).isoformat()})
            if counters["config_errors"] >= CONFIG_ERROR_ABORT:
                ctx.abort_event.set()
                aborted = True
                print(f"  [ABORT] {counters['config_errors']} deterministic "
                      f"provider configuration errors — aborting the run. "
                      f"Fix the configuration (see failure_log.jsonl).")
                break
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(worker, a): str(a["guid"]) for a in articles}
            for fut in as_completed(futs):
                res = fut.result()
                if res is None:
                    continue
                results[res.guid] = res
                done += 1
                print(f"  [{done}/{len(articles)}] {res.guid}: "
                      f"{'ok' if res.success else 'FAILED'}")
                ctx.log("article_status.jsonl", {
                    "guid": res.guid, "success": res.success,
                    "stage_outcomes": res.stage_outcomes,
                    "error_types": res.error_types,
                    "timestamp": datetime.now(timezone.utc).isoformat()})
                if counters["config_errors"] >= CONFIG_ERROR_ABORT:
                    if not ctx.abort_event.is_set():
                        ctx.abort_event.set()
                        aborted = True
                        print("  [ABORT] repeated provider configuration "
                              "errors — no new articles will be started.")

    succeeded = [g for g in requested_guids
                 if g in results and results[g].success]
    failed = [g for g in requested_guids
              if g in results and not results[g].success]
    not_processed = [g for g in requested_guids if g not in results]

    # ── Assemble stage outputs (successful articles only, input order) ──────
    policy_labels = policy_label_strategies(policy) if policy else {}
    stage_preds_1a: Dict[str, list] = {s: [] for s in STAGE_NAMES}
    stage_preds_1b: Dict[str, list] = {s: [] for s in STAGE_NAMES}
    final_1a, final_1b = [], []
    diag = {
        "pair_categories": defaultdict(int),
        "verifier": {"candidates": 0, "accepted": 0, "rejected": 0,
                     "articles_with_candidates": 0},
        "stage_totals": defaultdict(int),
        "stage_empty_articles": defaultdict(int),
        "final_direction_flips_by_verifier": 0,
        "n_actor_instances": 0,
        # A/B complementarity + verifier behavior (from compute_pair_diagnostics)
        "ab_exact_agreement_articles": 0,
        "tuple_jaccard_sum": 0.0,
        "pairs_proposed_by_both": 0,
        "pairs_direction_agreed": 0,
        "tuples_only_a": 0,
        "tuples_only_b": 0,
        "labels_only_a": defaultdict(int),
        "labels_only_b": defaultdict(int),
        "rare_labels_added_by_b": defaultdict(int),
        "verifier_by_category": defaultdict(lambda: {"candidates": 0,
                                                     "accepted": 0}),
        "conflict_direction_decisions": defaultdict(int),
        "final_contribution": defaultdict(int),
    }
    for guid in succeeded:
        res = results[guid]
        article = res.article
        diag["n_actor_instances"] += len(article_actor_ids(article))
        for cat, n in res.pair_categories.items():
            diag["pair_categories"][cat] += n
        diag["verifier"]["candidates"] += res.verifier_stats.get("candidates", 0)
        diag["verifier"]["accepted"] += res.verifier_stats.get("accepted", 0)
        diag["verifier"]["rejected"] += res.verifier_stats.get("rejected", 0)
        if res.verifier_stats.get("candidates", 0) > 0:
            diag["verifier"]["articles_with_candidates"] += 1

        pd = res.pair_diag
        diag["ab_exact_agreement_articles"] += int(pd["ab_exact_agreement"])
        diag["tuple_jaccard_sum"] += pd["tuple_jaccard"]
        diag["pairs_proposed_by_both"] += pd["pairs_proposed_by_both"]
        diag["pairs_direction_agreed"] += pd["pairs_direction_agreed"]
        diag["tuples_only_a"] += pd["tuples_only_a"]
        diag["tuples_only_b"] += pd["tuples_only_b"]
        for lab in pd["labels_only_a"]:
            diag["labels_only_a"][lab] += 1
        for lab in pd["labels_only_b"]:
            diag["labels_only_b"][lab] += 1
        for lab in pd["rare_labels_added_by_b"]:
            diag["rare_labels_added_by_b"][lab] += 1
        for cat, c in pd["verifier_by_category"].items():
            diag["verifier_by_category"][cat]["candidates"] += c["candidates"]
            diag["verifier_by_category"][cat]["accepted"] += c["accepted"]
        for k, v in pd["conflict_direction_decisions"].items():
            diag["conflict_direction_decisions"][k] += v

        final_tuples = apply_policy(res.stages, policy_labels, default_strategy)
        diag["final_direction_flips_by_verifier"] += len(
            final_tuples - res.stages["union"])
        for k, v in final_contribution_by_stage(final_tuples,
                                                res.stages).items():
            diag["final_contribution"][k] += v

        for stage in STAGE_NAMES:
            tuples = res.stages[stage]
            t1b = sorted_task1b_values(
                article, tuples_to_prediction_items(tuples))
            t1a = derive_task1a_values(article, t1b, tax)
            stage_preds_1b[stage].append(
                {"guid": guid, "article_human_values": t1b})
            stage_preds_1a[stage].append(
                {"guid": guid, "article_human_values": t1a})
            diag["stage_totals"][stage] += len(tuples)
            if not tuples:
                diag["stage_empty_articles"][stage] += 1
        t1b = sorted_task1b_values(article,
                                   tuples_to_prediction_items(final_tuples))
        t1a = derive_task1a_values(article, t1b, tax)
        final_1b.append({"guid": guid, "article_human_values": t1b})
        final_1a.append({"guid": guid, "article_human_values": t1a})
        diag["stage_totals"]["final"] += len(final_tuples)
        if not final_tuples:
            diag["stage_empty_articles"]["final"] += 1

    for stage in STAGE_NAMES:
        f1a, f1b = stage_file_names(stage)
        (out_dir / f1a).write_text(
            json.dumps(stage_preds_1a[stage], ensure_ascii=False, indent=2),
            encoding="utf-8")
        (out_dir / f1b).write_text(
            json.dumps(stage_preds_1b[stage], ensure_ascii=False, indent=2),
            encoding="utf-8")
    (out_dir / "pred_task1a.json").write_text(
        json.dumps(final_1a, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "pred_task1b.json").write_text(
        json.dumps(final_1b, ensure_ascii=False, indent=2), encoding="utf-8")

    status = compute_run_status(len(articles), len(succeeded),
                                len(failed) + len(not_processed))

    n_ok = max(len(succeeded), 1)

    def _rate(num, den):
        return round(num / den, 4) if den else None

    vb = diag["verifier_by_category"]
    diagnostics = {
        "pair_categories": dict(diag["pair_categories"]),
        "direction_conflict_pairs": diag["pair_categories"].get(
            "direction_conflict", 0) + diag["pair_categories"].get("partial", 0),
        "verifier": dict(diag["verifier"]),
        "final_direction_flips_by_verifier":
            diag["final_direction_flips_by_verifier"],
        "ab_agreement": {
            "exact_agreement_article_rate": _rate(
                diag["ab_exact_agreement_articles"], n_ok),
            "mean_tuple_jaccard": _rate(diag["tuple_jaccard_sum"], n_ok),
            "pair_direction_agreement_rate": _rate(
                diag["pairs_direction_agreed"],
                diag["pairs_proposed_by_both"]),
            "tuples_only_a": diag["tuples_only_a"],
            "tuples_only_b": diag["tuples_only_b"],
        },
        "labels_only_a": dict(sorted(diag["labels_only_a"].items())),
        "labels_only_b": dict(sorted(diag["labels_only_b"].items())),
        "rare_labels_added_by_b": dict(
            sorted(diag["rare_labels_added_by_b"].items())),
        "verifier_by_category": {
            cat: {**vb[cat],
                  "acceptance_rate": _rate(vb[cat]["accepted"],
                                           vb[cat]["candidates"])}
            for cat in sorted(vb)},
        "conflict_direction_decisions": dict(
            sorted(diag["conflict_direction_decisions"].items())),
        "final_contribution_by_stage": dict(diag["final_contribution"]),
        "per_stage": {
            s: {"total_tuples": diag["stage_totals"][s],
                "avg_per_article": round(diag["stage_totals"][s] / n_ok, 3),
                "avg_per_actor": round(
                    diag["stage_totals"][s]
                    / max(diag["n_actor_instances"], 1), 3),
                "empty_article_count": diag["stage_empty_articles"][s]}
            for s in list(STAGE_NAMES) + ["final"]},
        "n_actor_instances": diag["n_actor_instances"],
        "note": ("Diagnostics are computed offline from this run's outputs "
                 "and never influence inference decisions within the run."),
    }
    (out_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Evaluation + ablation (dev/calibrate only; successful guids only) ───
    ablation = None
    group_metrics = None
    if gold_path is not None and succeeded:
        eval_guids = set(succeeded)
        ablation = {}
        for stage in list(STAGE_NAMES) + ["final"]:
            if stage == "final":
                p1a, p1b = "pred_task1a.json", "pred_task1b.json"
            else:
                p1a, p1b = stage_file_names(stage)
            ablation[stage] = evaluate_predictions(
                out_dir / p1a, out_dir / p1b, gold_path, eval_guids)
        group_metrics = write_final_diagnostics(out_dir, gold_path,
                                                eval_guids, tax, rarity)
        (out_dir / "ablation_summary.json").write_text(
            json.dumps({"evaluated_guid_count": len(eval_guids),
                        "stages": ablation,
                        "final_frequency_group_metrics_task1b": group_metrics},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        header = ("| stage | 1a miF1 | 1a maF1 | 1b miF1 | 1b maF1 | 1b P | "
                  "1b R | DRR |\n|---|---|---|---|---|---|---|---|")
        rows = [header]
        for stage in list(STAGE_NAMES) + ["final"]:
            m = ablation[stage]
            rows.append(
                f"| {stage} | {m['task1a']['micro_f1']:.4f} | "
                f"{m['task1a']['macro_f1']:.4f} | "
                f"{m['task1b']['micro_f1']:.4f} | "
                f"{m['task1b']['macro_f1']:.4f} | "
                f"{m['task1b']['micro_precision']:.4f} | "
                f"{m['task1b']['micro_recall']:.4f} | "
                f"{m['task1b']['direction_reverse_rate']:.4f} |")
        (out_dir / "ablation_summary.md").write_text(
            "# Pipeline V3 ablation (successful guids only)\n\n"
            + "\n".join(rows) + "\n", encoding="utf-8")
        print("\nAblation (Task-1b micro-F1):")
        for stage in list(STAGE_NAMES) + ["final"]:
            print(f"  {stage:>13}: {ablation[stage]['task1b']['micro_f1']:.4f}")

    # ── Manifest + status ───────────────────────────────────────────────────
    actual_cost = None
    if price_cfg:
        actual_cost = round(
            (counters["prompt_tokens"] * price_cfg["input_usd_per_1m"]
             + counters["completion_tokens"] * price_cfg["output_usd_per_1m"])
            / 1e6, 4)
    manifest.update({
        "dry_run": False,
        "aborted_on_config_errors": aborted,
        "n_articles_succeeded": len(succeeded),
        "n_articles_failed": len(failed),
        "n_articles_not_processed": len(not_processed),
        "succeeded_guids": succeeded,
        "failed_guids": failed,
        "not_processed_guids": not_processed,
        "counters": counters,
        "token_usage": {"prompt_tokens": counters["prompt_tokens"],
                        "completion_tokens": counters["completion_tokens"]},
        "actual_cost_usd": actual_cost,
        "per_stage_prediction_cardinality": dict(diag["stage_totals"]),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    })
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "run_status.json").write_text(json.dumps({
        "status": status,
        "aborted_on_config_errors": aborted,
        "n_articles_requested": len(articles),
        "n_articles_succeeded": len(succeeded),
        "n_articles_failed": len(failed),
        "n_articles_not_processed": len(not_processed),
        "failed_guids": failed,
        "not_processed_guids": not_processed,
        "counters": counters,
        "finished": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nRun status: {status}"
          + (" (aborted on configuration errors)" if aborted else ""))
    if failed or not_processed:
        print(f"  failed={failed}  not_processed={len(not_processed)}")
        print("  NOTE: these articles are excluded from all prediction files; "
              "they were NOT converted into empty predictions. Re-run the "
              "same command (cache supplies previous successes).")
    if actual_cost is not None:
        print(f"  actual token cost: ${actual_cost}")
    print(f"Artifacts: {out_dir}")
    return 0 if status == RUN_COMPLETE else 1


if __name__ == "__main__":
    sys.exit(main())
