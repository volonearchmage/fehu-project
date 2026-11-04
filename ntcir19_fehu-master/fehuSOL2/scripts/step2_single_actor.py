#!/usr/bin/env python3
"""FEHU SOL2 Step 2: one DeepSeek V4 Pro non-thinking call per actor.

Scientific isolation:
  * same E1 baseline system prompt and two full-label demonstrations;
  * same article text/truncation, taxonomy, parser, output conversion;
  * model=deepseek-v4-pro, thinking=disabled, temperature=0;
  * the sole prompt intervention is asking for exactly one target actor.

All caches and artifacts live under fehuSOL2/. Failed calls are never cached
as valid empty predictions; legitimate {"items": []} responses are cached.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[2]
BASE_RUNNER_PATH = PROJECT / "Mathematical_optimization/base/run_pipeline_e1_base.py"
DEV_ARTICLES = PROJECT / "dataset/dev/dev_event_base.json"
DEFAULT_RUN_DIR = PROJECT / "fehuSOL2/runs/step2_single_actor_pro_t0"
MODEL = "deepseek-v4-pro"
TEMPERATURE = 0.0
THINKING_MODE = "disabled"
MAX_TOKENS = 8000
REQUEST_TIMEOUT = 180.0
MAX_RETRIES = 5
USER_TEMPLATE_VERSION = "sol2_step2_single_actor_v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_base_runner():
    spec = importlib.util.spec_from_file_location("sol2_e1_base", BASE_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import base runner: {BASE_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.l1_name_to_id, module.l2_name_to_id, module.l1_id_to_l2_id = module.load_taxonomy()
    return module


def iter_actors(article: dict[str, Any]):
    for actor_dict in article.get("actors", []):
        for name, actor_id in actor_dict.items():
            yield str(name), str(actor_id)


def build_single_actor_user_prompt(base, article: dict[str, Any], actor_name: str, actor_id: str) -> str:
    prompt = base.build_deepseek_user_prompt(article)
    old = 'Identify the human values for each actor. Return ONLY a JSON object with an "items" array.'
    if old not in prompt:
        raise AssertionError("base user prompt closing instruction changed")
    new = f"""TARGET ACTOR FOR THIS CALL:
- {actor_name} (ID: {actor_id})

Identify human values for this TARGET ACTOR only. The other listed actors are context for attribution and must not appear in the output.
Every returned item must use actor_id \"{actor_id}\" exactly.
Return ONLY a JSON object with an \"items\" array. An empty items array is valid when this target actor has no supported value."""
    return prompt.replace(old, new, 1)


def filter_target_items(items: list[Any], actor_id: str) -> tuple[list[dict[str, Any]], int, int]:
    kept: list[dict[str, Any]] = []
    extraneous = 0
    malformed = 0
    for item in items:
        if not isinstance(item, dict):
            malformed += 1
            continue
        if str(item.get("actor_id", "")) != actor_id:
            extraneous += 1
            continue
        kept.append(item)
    return kept, extraneous, malformed


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_dotenv_without_logging() -> None:
    for path in (PROJECT / ".env", PROJECT.parent / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


_thread_state = threading.local()


def thread_client(api_key: str):
    client = getattr(_thread_state, "client", None)
    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        _thread_state.client = client
    return client


def call_one(
    base,
    api_key: str,
    system_prompt: str,
    article: dict[str, Any],
    actor_name: str,
    actor_id: str,
    request_timeout: float,
) -> dict[str, Any]:
    guid = str(article["guid"])
    call_id = f"{guid}::{actor_id}"
    user_prompt = build_single_actor_user_prompt(base, article, actor_name, actor_id)
    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        content = ""
        try:
            response = thread_client(api_key).chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
                timeout=request_timeout,
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty response content")
            parsed = base.parse_model_json(content, call_id)
            if not isinstance(parsed, list):
                raise ValueError("parsed response is not a list")
            kept, extraneous, malformed = filter_target_items(parsed, actor_id)
            usage = getattr(response, "usage", None)
            return {
                "status": "success",
                "guid": guid,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "items": kept,
                "raw_parsed_item_count": len(parsed),
                "extraneous_item_count": extraneous,
                "malformed_item_count": malformed,
                "attempts": attempt,
                "finish_reason": getattr(response.choices[0], "finish_reason", None),
                "system_fingerprint": getattr(response, "system_fingerprint", None),
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                } if usage is not None else None,
                "raw_content": content,
            }
        except Exception as exc:  # retries must cover transport and schema failures
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 12))

    return {
        "status": "failure",
        "guid": guid,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "attempts": MAX_RETRIES,
        "error": last_error,
    }


def build_outputs(base, articles: list[dict[str, Any]], cache: dict[str, Any]):
    all_1a: list[dict[str, Any]] = []
    all_1b: list[dict[str, Any]] = []
    stats = {"extraneous_items": 0, "malformed_items": 0, "raw_items": 0, "kept_items": 0}

    for article in articles:
        guid = str(article["guid"])
        combined: list[dict[str, Any]] = []
        for _, actor_id in iter_actors(article):
            key = f"{guid}::{actor_id}"
            entry = cache.get(key)
            if not entry or entry.get("status") != "success":
                raise RuntimeError(f"missing successful cache entry: {key}")
            combined.extend(entry.get("items", []))
            stats["extraneous_items"] += int(entry.get("extraneous_item_count", 0))
            stats["malformed_items"] += int(entry.get("malformed_item_count", 0))
            stats["raw_items"] += int(entry.get("raw_parsed_item_count", 0))
            stats["kept_items"] += len(entry.get("items", []))

        values_1a, values_1b = base.process_results(guid, article["actors"], combined)
        all_1a.append({"guid": guid, "article_human_values": values_1a})
        all_1b.append({"guid": guid, "article_human_values": values_1b})
    return all_1a, all_1b, stats


def load_evaluator():
    path = PROJECT / "Mathematical_optimization/evaluation/eval_full.py"
    spec = importlib.util.spec_from_file_location("sol2_step2_eval", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--limit", type=int, default=None, help="first N articles; cache can later resume full run")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--request-timeout", type=float, default=REQUEST_TIMEOUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()

    if args.workers < 1 or args.workers > 16:
        raise ValueError("workers must be between 1 and 16")

    base = load_base_runner()
    articles_all = json.loads(DEV_ARTICLES.read_text(encoding="utf-8"))
    articles = articles_all[: args.limit] if args.limit else articles_all
    few_shot = base.load_few_shot_examples(n=2)
    system_prompt = base.apply_prompt_variant(base.build_deepseek_system_prompt(few_shot), "baseline")

    first_name, first_id = next(iter_actors(articles[0]))
    first_user_prompt = build_single_actor_user_prompt(base, articles[0], first_name, first_id)
    prompt_identity = sha256_bytes(
        (system_prompt + "\0" + USER_TEMPLATE_VERSION + "\0" + first_user_prompt).encode("utf-8")
    )

    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "system_prompt_snapshot.txt").write_text(system_prompt, encoding="utf-8")
    (args.run_dir / "user_prompt_preview.txt").write_text(first_user_prompt, encoding="utf-8")

    manifest_path = args.run_dir / "manifest.json"
    manifest = {
        "experiment": "SOL2 Step 2 single-actor prompt",
        "model": MODEL,
        "thinking": THINKING_MODE,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "user_template_version": USER_TEMPLATE_VERSION,
        "system_prompt_sha256": sha256_bytes(system_prompt.encode("utf-8")),
        "prompt_identity_sha256": prompt_identity,
        "base_runner": str(BASE_RUNNER_PATH.relative_to(PROJECT)),
        "base_runner_sha256": sha256_file(BASE_RUNNER_PATH),
        "dev_articles_sha256": sha256_file(DEV_ARTICLES),
        "n_dev_articles": len(articles_all),
        "n_dev_actor_calls": sum(1 for article in articles_all for _ in iter_actors(article)),
        "only_prompt_delta": "one target actor per call; full article and complete actor list retained",
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        identity_keys = (
            "model", "thinking", "temperature", "max_tokens", "user_template_version",
            "system_prompt_sha256", "prompt_identity_sha256", "base_runner_sha256", "dev_articles_sha256",
        )
        mismatches = [key for key in identity_keys if existing.get(key) != manifest.get(key)]
        if mismatches:
            raise RuntimeError(f"run identity changed for existing run dir: {mismatches}")
    else:
        atomic_write_json(manifest_path, manifest)

    if args.dry_run:
        print(first_user_prompt)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return

    load_dotenv_without_logging()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing")

    cache_path = args.run_dir / "cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    tasks = []
    for article in articles:
        guid = str(article["guid"])
        for actor_name, actor_id in iter_actors(article):
            key = f"{guid}::{actor_id}"
            if not args.refresh_cache and cache.get(key, {}).get("status") == "success":
                continue
            tasks.append((key, article, actor_name, actor_id))

    print(f"Step 2: {len(articles)} articles, {sum(1 for a in articles for _ in iter_actors(a))} actor calls")
    print(f"Cached successful calls: {sum(1 for v in cache.values() if v.get('status') == 'success')}")
    print(f"API calls pending: {len(tasks)}; workers={args.workers}")

    failures: list[dict[str, Any]] = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_key = {
            executor.submit(
                call_one, base, api_key, system_prompt, article, actor_name, actor_id, args.request_timeout
            ): key
            for key, article, actor_name, actor_id in tasks
        }
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            result = future.result()
            completed += 1
            if result.get("status") == "success":
                cache[key] = result
                atomic_write_json(cache_path, cache)
            else:
                failures.append(result)
            if completed % 10 == 0 or completed == len(tasks):
                print(f"Completed {completed}/{len(tasks)} new calls; failures={len(failures)}")

    atomic_write_json(args.run_dir / "failures.json", failures)
    if failures:
        raise RuntimeError(f"{len(failures)} calls failed; rerun to retry before producing predictions")

    missing = []
    for article in articles:
        guid = str(article["guid"])
        for _, actor_id in iter_actors(article):
            key = f"{guid}::{actor_id}"
            if cache.get(key, {}).get("status") != "success":
                missing.append(key)
    if missing:
        raise RuntimeError(f"missing {len(missing)} successful calls")

    all_1a, all_1b, output_stats = build_outputs(base, articles, cache)
    atomic_write_json(args.run_dir / "pred_task1a.json", all_1a)
    atomic_write_json(args.run_dir / "pred_task1b.json", all_1b)

    summary = {
        "n_articles": len(articles),
        "n_actor_calls": sum(1 for article in articles for _ in iter_actors(article)),
        "n_task1a_predictions": sum(len(x["article_human_values"]) for x in all_1a),
        "n_task1b_predictions": sum(len(x["article_human_values"]) for x in all_1b),
        "output_filtering": output_stats,
        "cached_success_total": sum(1 for v in cache.values() if v.get("status") == "success"),
        "retry_calls": sum(1 for v in cache.values() if int(v.get("attempts", 1)) > 1),
        "system_fingerprints": sorted({
            str(v.get("system_fingerprint")) for v in cache.values()
            if v.get("system_fingerprint") is not None
        }),
    }
    atomic_write_json(args.run_dir / "run_summary.json", summary)

    if len(articles) == len(articles_all):
        evaluator = load_evaluator()
        metrics = evaluator.compute_all_metrics(
            str(args.run_dir / "pred_task1a.json"), str(args.run_dir / "pred_task1b.json")
        )
        metrics["label"] = "SOL2 Step 2 single-actor Pro non-thinking T=0"
        atomic_write_json(args.run_dir / "metrics.json", metrics)
        print(json.dumps({"summary": summary, "task1a": metrics["task1a"], "task1b": metrics["task1b"]}, indent=2))
    else:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
