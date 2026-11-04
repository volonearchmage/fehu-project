#!/usr/bin/env python3
"""E4 command-line entry point.

Variants (each produces its own official pred_task1a/1b files):
  e4a  evidence extraction -> frozen E1 prediction with evidence units
       (final output = raw E1-format items through frozen process_results)
  e4b  e4a's stages + 4 family scans -> union of global and family
       candidates (fixed direction-conflict rule, no verifier)
  e4c  e4b's stages + verifier -> aggregation per config/aggregation_rules.json

API calls per article: e4a = 2, e4b = 6, e4c = 7. Stage caches under
runs/<E4_RUN_TS>/ make every stage resumable and shareable between variants
of the same run (e4c reuses e4a/e4b caches of the same run timestamp).

Usage (dev experiments are for a LATER session; nothing here runs without an
explicit invocation):
  export DEEPSEEK_API_KEY=...
  export E4_RUN_TS=20260801_000000          # optional: pin/resume a run
  python3 run_e4.py --variant e4a --mode dev
  python3 run_e4.py --variant e4b --mode dev
  python3 run_e4.py --variant e4c --mode dev --evaluate
  python3 run_e4.py --variant e4c --mode dev --dry_run   # no API, prompt preview
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aggregate
import evidence
import family_scan
import outputs
import predict_global
import verify
from e4_common import (RUNS_DIR, E4ModelError, E4ValidationError,
                       ModelCaller, StageCache,
                       Taxonomy, ViolationLog, load_aggregation_rules,
                       load_families, load_frozen_e1, load_model_config,
                       load_sibling_map, load_template,
                       make_deepseek_transport, setup_logger, sha256_text)
from sentence_split import split_sentences

VARIANT_STAGES = {
    "e4a": ("evidence", "global"),
    "e4b": ("evidence", "global", "family"),
    "e4c": ("evidence", "global", "family", "verify"),
}


class E4Runner:
    def __init__(self, args):
        self.args = args
        self.e1 = load_frozen_e1()
        self.taxonomy = Taxonomy(self.e1)
        self.config = load_model_config()
        self.families = load_families(self.taxonomy)
        self.sibling_map = load_sibling_map(self.taxonomy)
        self.rules = load_aggregation_rules()

        self.run_ts = os.environ.get("E4_RUN_TS") or time.strftime(
            "%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(RUNS_DIR, self.run_ts)
        os.makedirs(self.run_dir, exist_ok=True)
        self.log = setup_logger(os.path.join(self.run_dir, "e4.log"))
        self.violations = ViolationLog(
            os.path.join(self.run_dir, "violations.jsonl"), self.log)
        self.failures_path = os.path.join(self.run_dir, "failures.jsonl")
        self.article_failures = []
        self._caller_lock = threading.Lock()
        self._failure_lock = threading.Lock()

        self.e1_system_prompt = predict_global.build_e1_system_prompt(
            self.e1, self.config["e1_prompt_variant"])
        self._caller = None
        self._write_run_config()
        self._init_caches()

    # -- setup ---------------------------------------------------------------

    def _prompt_hashes(self):
        hashes = {
            "evidence_system": sha256_text(load_template("evidence_system.txt")),
            "evidence_user": sha256_text(load_template("evidence_user.txt")),
            "family_system": sha256_text(load_template("family_system.txt")),
            "family_user": sha256_text(load_template("family_user.txt")),
            "verifier_system": sha256_text(load_template("verifier_system.txt")),
            "verifier_user": sha256_text(load_template("verifier_user.txt")),
            "e1_system_prompt": sha256_text(self.e1_system_prompt),
        }
        return hashes

    def _write_run_config(self):
        cfg_path = os.path.join(self.run_dir, "run_config.json")
        payload = {
            "experiment": "E4_actor_evidence_decomposition_and_verification",
            "variant": self.args.variant,
            "mode": self.args.mode,
            "limit": self.args.limit,
            "base_pipeline": ("RH_test/E1_fewshot_repair/scripts/"
                              "run_pipeline_e1.py (frozen, imported read-only)"),
            "model_config": self.config,
            "prompt_hashes": self._prompt_hashes(),
            "aggregation_rules": self.rules,
            "families": [f["family_id"] for f in self.families],
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        with open(os.path.join(self.run_dir, "e1_system_prompt_snapshot.txt"),
                  "w", encoding="utf-8") as f:
            f.write(self.e1_system_prompt)

    def _cache(self, name, extra_meta=None):
        meta = {"stage": name, "mode": self.args.mode,
                "model": self.config["model"],
                "temperature": self.config["temperature"],
                "max_output_tokens": self.config["max_output_tokens"]}
        meta.update(extra_meta or {})
        return StageCache(
            os.path.join(self.run_dir, f"cache_{name}.json"), meta)

    def _init_caches(self):
        hashes = self._prompt_hashes()
        self.cache_evidence = self._cache("evidence", {
            "prompt": hashes["evidence_system"] + hashes["evidence_user"]})
        self.cache_global = self._cache("global", {
            "prompt": hashes["e1_system_prompt"],
            "e1_variant": self.config["e1_prompt_variant"]})
        self.cache_family = {
            fam["family_id"]: self._cache(f"family_{fam['family_id']}", {
                "prompt": hashes["family_system"] + hashes["family_user"],
                "family_l1_ids": fam["l1_ids"]})
            for fam in self.families}
        self.cache_verify = self._cache("verify", {
            "prompt": hashes["verifier_system"] + hashes["verifier_user"]})

    def caller(self):
        with self._caller_lock:
            if self._caller is None:
                api_key = (self.args.api_key
                           or os.environ.get("DEEPSEEK_API_KEY"))
                if not api_key:
                    raise E4ValidationError(
                        "DEEPSEEK_API_KEY not set (only needed for uncached "
                        "articles; this run has cache misses)")
                transport = make_deepseek_transport(
                    self.e1, self.config, api_key)
                self._caller = ModelCaller(self.config, transport, self.log)
            return self._caller

    # -- data ----------------------------------------------------------------

    def load_articles(self):
        path = (self.e1.DEV_ARTICLES if self.args.mode == "dev"
                else self.e1.TEST_ARTICLES)
        with open(path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        for article in articles:
            for key in ("guid", "title", "content", "actors"):
                if key not in article:
                    raise E4ValidationError(
                        f"article missing required field {key!r} — E4 uses "
                        "only guid/title/content/actors")
        if self.args.limit:
            articles = articles[:self.args.limit]
        return articles

    # -- stages --------------------------------------------------------------

    def stage_evidence(self, article, sentences):
        guid = article["guid"]
        cached = self.cache_evidence.get(guid)
        if cached is not None:
            return cached
        system, user = evidence.build_prompts(article, sentences)

        def validator(obj, final):
            return evidence.validate_evidence(obj, article, sentences)

        units = self.caller().call_json(system, user, guid, "evidence",
                                        validator)
        self.cache_evidence.put(guid, units)
        return units

    def stage_global(self, article, sentences, units_by_actor):
        guid = article["guid"]
        cached = self.cache_global.get(guid)
        if cached is not None:
            return cached
        user = predict_global.build_user_prompt(
            self.e1, article, units_by_actor, sentences)
        items = self.caller().call_json(
            self.e1_system_prompt, user, guid, "global",
            predict_global.validate_items)
        self.cache_global.put(guid, items)
        return items

    def stage_family(self, family, article, sentences, units_by_actor):
        guid = article["guid"]
        cache = self.cache_family[family["family_id"]]
        cached = cache.get(guid)
        if cached is not None:
            return cached
        system, user = family_scan.build_prompts(
            family, self.taxonomy, article, sentences, units_by_actor)

        def validator(obj, final):
            return family_scan.validate_candidates(
                obj, final, family, article, sentences, units_by_actor,
                self.taxonomy, self.violations, guid)

        cands = self.caller().call_json(
            system, user, guid, f"family:{family['family_id']}", validator)
        cache.put(guid, cands)
        return cands

    def stage_verify(self, article, sentences, units_by_actor, merged):
        guid = article["guid"]
        cand_hash = sha256_text(json.dumps(
            [{k: sorted(v) if isinstance(v, set) else v
              for k, v in c.items()} for c in merged],
            sort_keys=True, default=str))
        cached = self.cache_verify.get(guid)
        if cached is not None:
            if cached["candidates_hash"] == cand_hash:
                return cached["verdicts"]
            self.log.info("[%s] verify cache stale (candidates changed); "
                          "recomputing", guid)
        if not merged:
            self.cache_verify.put(
                guid, {"candidates_hash": cand_hash, "verdicts": {}})
            return {}
        system, user = verify.build_prompts(
            article, sentences, units_by_actor, merged, self.taxonomy,
            self.sibling_map)
        expected = {c["cid"] for c in merged}

        def validator(obj, final):
            return verify.validate_verdicts(obj, expected)

        verdicts = self.caller().call_json(system, user, guid, "verify",
                                           validator)
        self.cache_verify.put(
            guid, {"candidates_hash": cand_hash, "verdicts": verdicts})
        return verdicts

    # -- per-article assembly ------------------------------------------------

    def process_article(self, article):
        guid = article["guid"]
        sentences = split_sentences(article["content"])
        units = self.stage_evidence(article, sentences)
        raw_items = self.stage_global(article, sentences, units)

        if self.args.variant == "e4a":
            return raw_items, []  # frozen E1 path: raw items to process_results

        global_cands = predict_global.candidates_from_items(
            raw_items, article, units, self.taxonomy, self.violations, guid)
        family_cands = []
        for family in self.families:
            family_cands.extend(
                self.stage_family(family, article, sentences, units))
        merged = aggregate.merge_candidates(global_cands, family_cands)

        if self.args.variant == "e4b":
            items, decisions = aggregate.e4b_union(merged, self.rules)
        else:
            verdicts = self.stage_verify(article, sentences, units, merged)
            items, decisions = aggregate.e4c_aggregate(
                merged, verdicts, self.rules)
        for d in decisions:
            d["guid"] = guid
        return items, decisions

    # -- dry run -------------------------------------------------------------

    def dry_run(self, article):
        sentences = split_sentences(article["content"])
        mock_units = {}
        counter = 0
        for actor_dict in article["actors"]:
            for _name, aid in actor_dict.items():
                counter += 1
                mock_units[aid] = [{
                    "uid": f"u{counter}", "kind": "action",
                    "sentence_ids": [sentences[0]["sid"]],
                    "note": "dry-run mock unit"}]
        sections = []
        sys_ev, usr_ev = evidence.build_prompts(article, sentences)
        sections.append(("EVIDENCE STAGE", sys_ev, usr_ev))
        usr_gl = predict_global.build_user_prompt(
            self.e1, article, mock_units, sentences)
        sections.append(("GLOBAL STAGE (frozen E1 + evidence)",
                         self.e1_system_prompt, usr_gl))
        fam = self.families[0]
        sys_fa, usr_fa = family_scan.build_prompts(
            fam, self.taxonomy, article, sentences, mock_units)
        sections.append((f"FAMILY STAGE ({fam['family_id']})", sys_fa, usr_fa))
        mock_cands = aggregate.merge_candidates(
            [{"actor_id": aid, "l1_value_id": "42", "direction": "aligned",
              "evidence": [u[0]["uid"]], "reason": "mock", "source": "global"}
             for aid, u in mock_units.items()], [])
        sys_ve, usr_ve = verify.build_prompts(
            article, sentences, mock_units, mock_cands, self.taxonomy,
            self.sibling_map)
        sections.append(("VERIFY STAGE", sys_ve, usr_ve))
        for title, system, user in sections:
            print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)
            print(f"--- system ({len(system)} chars) ---")
            print(system[:2500] + ("\n...[truncated]" if len(system) > 2500
                                   else ""))
            print(f"--- user ({len(user)} chars) ---")
            print(user[:2500] + ("\n...[truncated]" if len(user) > 2500
                                 else ""))
        print("\nDry run complete: no API was called.")

    # -- main ----------------------------------------------------------------

    def _process_or_record(self, article):
        """Process one article; on a per-article stage failure, record it
        explicitly and return empty predictions. Returns (guid, items,
        decisions). Safe to call from worker threads."""
        guid = article["guid"]
        try:
            items, decisions = self.process_article(article)
            return guid, items, decisions
        except E4ModelError as err:
            # A stage exhausted its retries for THIS article. Empirically these
            # are transient endpoint failures (empty/truncated JSON on large
            # articles), so one bad article must not abort the others. Surface
            # it loudly (ERROR log + failures.jsonl + run_summary) and emit
            # EMPTY predictions — explicit surfacing, not a silent fallback:
            # nothing is guessed or hidden. If failures become systemic
            # (> --max_article_failures), abort the whole run.
            self.log.error("ARTICLE FAILED [%s] variant %s: %s",
                           guid, self.args.variant, err)
            with self._failure_lock:
                self.article_failures.append({"guid": guid,
                                              "variant": self.args.variant,
                                              "error": str(err)})
                with open(self.failures_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(self.article_failures[-1],
                                       ensure_ascii=False) + "\n")
                n_failed = len(self.article_failures)
            if n_failed > self.args.max_article_failures:
                raise E4ValidationError(
                    f"{n_failed} article failures exceed "
                    f"--max_article_failures={self.args.max_article_failures}; "
                    "aborting (this indicates a systemic problem, not "
                    "transient errors). Resume with the same E4_RUN_TS after "
                    "investigating.")
            return guid, [], []

    def run(self):
        articles = self.load_articles()
        self.log.info("E4 %s | mode=%s | %d articles | run dir %s",
                      self.args.variant, self.args.mode, len(articles),
                      self.run_dir)
        if self.args.dry_run:
            self.dry_run(articles[0])
            return

        items_by_guid = {}
        all_decisions = []
        workers = max(1, self.args.workers)
        if workers == 1:
            for article in tqdm(articles, desc=f"E4 {self.args.variant}"):
                guid, items, decisions = self._process_or_record(article)
                items_by_guid[guid] = items
                all_decisions.extend(decisions)
        else:
            # Articles are independent; process them concurrently. Results are
            # keyed by guid and written in article order below, so the output
            # is identical regardless of worker count or completion order.
            # Shared state (caches, violations, failures, call counter) is
            # lock-protected. A systemic-failure abort still propagates.
            self.log.info("running with %d worker threads", workers)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self._process_or_record, art): art
                           for art in articles}
                for fut in tqdm(as_completed(futures), total=len(futures),
                                desc=f"E4 {self.args.variant}"):
                    guid, items, decisions = fut.result()
                    items_by_guid[guid] = items
                    all_decisions.extend(decisions)

        out_dir = os.path.join(self.run_dir, f"{self.args.variant}_pred")
        path_1a, path_1b = outputs.write_pred_files(
            self.e1, articles, items_by_guid, out_dir)
        if all_decisions:
            with open(os.path.join(out_dir, "decisions.jsonl"), "w",
                      encoding="utf-8") as f:
                for d in all_decisions:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")

        n_calls = self._caller.n_calls if self._caller else 0
        summary = {
            "variant": self.args.variant, "mode": self.args.mode,
            "articles": len(articles), "api_calls_this_invocation": n_calls,
            "violations": self.violations.summary(),
            "article_failures": len(self.article_failures),
            "failed_guids": [f["guid"] for f in self.article_failures],
            "pred_task1a": path_1a, "pred_task1b": path_1b,
        }
        with open(os.path.join(out_dir, "run_summary.json"), "w",
                  encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        self.log.info("done: %s", json.dumps(summary))

        if self.args.evaluate:
            if self.args.mode != "dev":
                raise E4ValidationError("--evaluate requires --mode dev")
            eval_guids = ({a["guid"] for a in articles}
                          if self.args.limit else None)
            outputs.run_dev_evaluation(self.e1, path_1a, path_1b, eval_guids)


def main():
    parser = argparse.ArgumentParser(description="FEHU E4 pipeline")
    parser.add_argument("--variant", choices=sorted(VARIANT_STAGES),
                        required=True)
    parser.add_argument("--mode", choices=["dev", "test"], default="dev")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry_run", action="store_true",
                        help="print stage prompts for the first article; "
                             "never calls any API")
    parser.add_argument("--evaluate", action="store_true",
                        help="run the official dev evaluation after the "
                             "pipeline (dev mode only; explicit opt-in)")
    parser.add_argument("--api_key", default=None)
    parser.add_argument("--workers", type=int, default=1,
                        help="number of concurrent article workers (default "
                             "1 = sequential). Articles are independent; "
                             "output is identical regardless of this value.")
    parser.add_argument("--max_article_failures", type=int, default=15,
                        help="abort the run only if MORE than this many "
                             "articles exhaust their retries (transient "
                             "endpoint failures are expected on large "
                             "articles; each is recorded in failures.jsonl "
                             "and given empty predictions).")
    args = parser.parse_args()
    E4Runner(args).run()


if __name__ == "__main__":
    main()
