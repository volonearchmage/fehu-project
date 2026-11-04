"""Shared E4 infrastructure.

Design invariants (see reports/E4_IMPLEMENTATION_AND_HANDOFF_REPORT.md):
  * The frozen E1 pipeline (RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py)
    is imported READ-ONLY and never modified or copied. E4 reuses its taxonomy
    loading, few-shot construction, system/user prompt builders, JSON parser,
    submission-format conversion, and API client factory.
  * No silent failures:
      - structural problems (malformed JSON, wrong schema shape, missing
        actors, verdict/candidate mismatch) raise E4SchemaError; the call layer
        retries the API call and hard-fails the run after max_retries;
      - item-level semantic violations on the FINAL attempt (out-of-family
        value, invalid sentence/unit reference, invalid actor in a candidate)
        reject only the offending item, but every rejection is appended to the
        run's violations.jsonl, logged at WARNING, and counted in the run
        summary. Nothing is dropped without a written trace.
  * Cache identity: every stage cache carries a _meta header (model config +
    prompt hash + stage); resuming with a mismatched meta is a hard error.
"""

import hashlib
import json
import logging
import os
import sys
import threading
import time

E4_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RH_TEST_DIR = os.path.dirname(E4_DIR)
CONFIG_DIR = os.path.join(E4_DIR, "config")
PROMPTS_DIR = os.path.join(E4_DIR, "prompts")
RUNS_DIR = os.path.join(E4_DIR, "runs")
E1_SCRIPTS_DIR = os.path.join(RH_TEST_DIR, "E1_fewshot_repair", "scripts")

# E1's own truncation rule for long articles (frozen behavior, mirrored for
# the sentence-based stages so every stage sees the same text window).
E1_TRUNC_THRESHOLD = 12000
E1_TRUNC_HEAD = 6000
E1_TRUNC_TAIL = 3000

EVIDENCE_KINDS = (
    "action", "statement", "intention", "consequence",
    "evaluation_by_others", "background",
)
DIRECTIONS = ("aligned", "contradictory")
RELEVANCE_VERDICTS = ("KEEP", "DROP", "UNCERTAIN")
ATTRIBUTIONS = (
    "actor", "other_actor", "narrator", "quoted_speaker", "background",
    "uncertain",
)
DIRECTION_VERDICTS = ("aligned", "contradictory", "uncertain")


class E4Error(Exception):
    """Base class for all explicit E4 failures."""


class E4SchemaError(E4Error):
    """A model response (or config/cache file) violates the expected schema."""


class E4ModelError(E4Error):
    """All retries for one API call failed."""


class E4ValidationError(E4Error):
    """An internal invariant was violated (bug or bad input data)."""


# ---------------------------------------------------------------------------
# Frozen E1 import (read-only reuse)
# ---------------------------------------------------------------------------

_e1_module = None


def load_frozen_e1():
    """Import the frozen E1 pipeline module and initialize its taxonomy globals.

    Import has no side effects beyond path lookups (verified: E1 only creates
    directories inside main()). E1_RUN_TS is pinned so E1's run-dir string is
    deterministic and obviously unused.
    """
    global _e1_module
    if _e1_module is not None:
        return _e1_module
    if not os.path.isfile(os.path.join(E1_SCRIPTS_DIR, "run_pipeline_e1.py")):
        raise E4ValidationError(
            f"Frozen E1 pipeline not found at {E1_SCRIPTS_DIR}")
    os.environ.setdefault("E1_RUN_TS", "e4_frozen_import_noop")
    if E1_SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, E1_SCRIPTS_DIR)
    import run_pipeline_e1 as e1  # noqa: E402
    e1.l1_name_to_id, e1.l2_name_to_id, e1.l1_id_to_l2_id = e1.load_taxonomy()
    _e1_module = e1
    return e1


# ---------------------------------------------------------------------------
# Taxonomy helpers
# ---------------------------------------------------------------------------

class Taxonomy:
    def __init__(self, e1):
        self.l1_name_to_id = dict(e1.l1_name_to_id)
        self.l2_name_to_id = dict(e1.l2_name_to_id)
        self.l1_id_to_l2_id = dict(e1.l1_id_to_l2_id)
        self.l1_id_to_name = {v: k for k, v in self.l1_name_to_id.items()}
        self.l2_id_to_name = {v: k for k, v in self.l2_name_to_id.items()}
        if len(self.l1_id_to_name) != 54 or len(self.l2_id_to_name) != 20:
            raise E4ValidationError(
                f"Taxonomy size unexpected: {len(self.l1_id_to_name)} L1 / "
                f"{len(self.l2_id_to_name)} L2")
        self.l1_ids_by_l2 = {}
        for l1_id, l2_id in self.l1_id_to_l2_id.items():
            self.l1_ids_by_l2.setdefault(l2_id, []).append(l1_id)
        for l2_id in self.l1_ids_by_l2:
            self.l1_ids_by_l2[l2_id].sort(key=int)

    def valid_l1(self, l1_id):
        return l1_id in self.l1_id_to_name


# ---------------------------------------------------------------------------
# Config loading + validation
# ---------------------------------------------------------------------------

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_model_config():
    cfg = _load_json(os.path.join(CONFIG_DIR, "model_config.json"))
    for key in ("provider", "model", "temperature", "max_output_tokens",
                "request_timeout", "max_retries", "e1_prompt_variant"):
        if key not in cfg:
            raise E4ValidationError(f"model_config.json missing key: {key}")
    if cfg["provider"] != "deepseek":
        raise E4ValidationError(
            "E4 is specified for the DeepSeek Flash configuration; provider "
            f"{cfg['provider']!r} is not supported")
    return cfg


def load_families(taxonomy):
    raw = _load_json(os.path.join(CONFIG_DIR, "taxonomy_families.json"))
    families = raw["families"]
    seen_l2 = []
    for fam in families:
        for key in ("family_id", "family_name", "l2_ids", "contrast_l2_ids"):
            if key not in fam:
                raise E4ValidationError(
                    f"family {fam.get('family_id')!r} missing key {key}")
        for l2_id in fam["l2_ids"] + fam["contrast_l2_ids"]:
            if l2_id not in taxonomy.l2_id_to_name:
                raise E4ValidationError(
                    f"family {fam['family_id']}: unknown L2 id {l2_id!r}")
        overlap = set(fam["l2_ids"]) & set(fam["contrast_l2_ids"])
        if overlap:
            raise E4ValidationError(
                f"family {fam['family_id']}: contrast overlaps own L2s "
                f"{sorted(overlap)}")
        seen_l2.extend(fam["l2_ids"])
    if sorted(seen_l2, key=int) != sorted(taxonomy.l2_id_to_name, key=int):
        raise E4ValidationError(
            "taxonomy_families.json l2_ids do not partition the 20 official "
            f"L2 ids exactly (got {sorted(seen_l2, key=int)})")
    if len(seen_l2) != len(set(seen_l2)):
        raise E4ValidationError("taxonomy_families.json: an L2 id appears in "
                                "more than one family")
    for fam in families:
        fam["l1_ids"] = sorted(
            (l1 for l2 in fam["l2_ids"] for l1 in taxonomy.l1_ids_by_l2[l2]),
            key=int)
    covered = sorted((l1 for f in families for l1 in f["l1_ids"]), key=int)
    if covered != sorted(taxonomy.l1_id_to_name, key=int):
        raise E4ValidationError("families do not cover all 54 L1 values "
                                "exactly once")
    return families


def load_sibling_map(taxonomy):
    """Merge structural same-L2 siblings with the curated cross-L2 pairs."""
    raw = _load_json(os.path.join(CONFIG_DIR, "sibling_map.json"))
    siblings = {l1: set() for l1 in taxonomy.l1_id_to_name}
    for l2_id, l1_ids in taxonomy.l1_ids_by_l2.items():
        for a in l1_ids:
            for b in l1_ids:
                if a != b:
                    siblings[a].add(b)
    for pair in raw["extra_pairs"]:
        if len(pair) != 2 or pair[0] == pair[1]:
            raise E4ValidationError(f"sibling_map.json bad pair: {pair}")
        a, b = pair
        if not (taxonomy.valid_l1(a) and taxonomy.valid_l1(b)):
            raise E4ValidationError(f"sibling_map.json unknown L1 in pair {pair}")
        siblings[a].add(b)
        siblings[b].add(a)
    return {l1: sorted(s, key=int) for l1, s in siblings.items()}


def load_aggregation_rules():
    rules = _load_json(os.path.join(CONFIG_DIR, "aggregation_rules.json"))
    surv = rules["survival"]
    for key in ("both_views", "single_view"):
        for verdict in surv[key]:
            if verdict not in RELEVANCE_VERDICTS:
                raise E4ValidationError(
                    f"aggregation_rules survival.{key}: bad verdict {verdict!r}")
    for att in rules["attribution_reject"]:
        if att not in ATTRIBUTIONS or att == "actor":
            raise E4ValidationError(
                f"aggregation_rules attribution_reject: bad value {att!r}")
    if rules["attribution_uncertain_policy"] not in ("keep", "reject"):
        raise E4ValidationError("bad attribution_uncertain_policy")
    if rules["direction_resolution"]["tie_policy"] != "drop_pair":
        raise E4ValidationError("only tie_policy 'drop_pair' is implemented")
    if rules["direction_resolution"]["method"] != "strict_majority":
        raise E4ValidationError("only method 'strict_majority' is implemented")
    if rules["e4b_direction_conflict"] != "prefer_global":
        raise E4ValidationError("only e4b_direction_conflict 'prefer_global' "
                                "is implemented")
    if rules["verifier_can_add"] is not False:
        raise E4ValidationError("verifier_can_add must be false")
    return rules


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

def load_template(name):
    with open(os.path.join(PROMPTS_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def render_template(template, mapping):
    """Substitute <<VAR>> placeholders; fail loudly on unused/leftover vars."""
    out = template
    for key, value in mapping.items():
        token = f"<<{key}>>"
        if token not in out:
            raise E4ValidationError(f"template does not contain {token}")
        out = out.replace(token, value)
    if "<<" in out and ">>" in out:
        start = out.index("<<")
        raise E4ValidationError(
            f"template has unreplaced placeholder near: {out[start:start+40]!r}")
    return out


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Article helpers
# ---------------------------------------------------------------------------

def actor_pairs(article):
    """[(name, actor_id), ...] in article order."""
    pairs = []
    for actor_dict in article["actors"]:
        for name, aid in actor_dict.items():
            pairs.append((name, aid))
    if not pairs:
        raise E4ValidationError(f"article {article['guid']}: no actors")
    return pairs


def render_actor_block(article):
    return "\n".join(f"- {name} (ID: {aid})" for name, aid in actor_pairs(article))


# ---------------------------------------------------------------------------
# Model call layer (strict; injectable transport for offline tests)
# ---------------------------------------------------------------------------

def _strip_json_wrappers(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return (content.replace("“", '"').replace("”", '"')
                   .replace("‘", "'").replace("’", "'"))


class ModelCaller:
    """Strict DeepSeek JSON-mode caller with retries and no silent fallback.

    `transport` is a callable (system_prompt, user_prompt) -> str (the raw
    model text). Offline tests inject a fake transport; the real one is built
    from the frozen E1 client factory via `make_deepseek_transport`.
    """

    def __init__(self, config, transport, logger=None):
        self.config = config
        self.transport = transport
        self.log = logger or logging.getLogger("e4")
        self.n_calls = 0
        self._count_lock = threading.Lock()

    def call_json(self, system_prompt, user_prompt, guid, stage, validator):
        """Call the model; parse JSON object; run `validator(obj)`.

        `validator` must raise E4SchemaError on structural problems (which are
        retried) and return the validated payload otherwise. After
        max_retries failed attempts the run fails with E4ModelError.

        max_tokens escalation: empty/truncated JSON is usually the response
        hitting the base token ceiling (finish_reason=length -> DeepSeek JSON
        mode returns truncated/empty content). Large-article stages (evidence
        organizing every sentence) legitimately need more than E1's inherited
        8000-token budget. On each parse/empty failure we DOUBLE the token
        budget (up to a cap) before retrying. This does not change the prompt
        or the requested output -- it only lets a valid response finish. The
        base budget still defines cache identity, so already-cached articles
        are untouched; only truncating articles escalate.
        """
        last_err = None
        base = self.config["max_output_tokens"]
        cap = self.config.get("max_output_tokens_cap", 32000)
        max_tokens = base
        for attempt in range(1, self.config["max_retries"] + 1):
            final = attempt == self.config["max_retries"]
            try:
                raw = self.transport(system_prompt, user_prompt, max_tokens)
                with self._count_lock:
                    self.n_calls += 1
                if not raw or not raw.strip():
                    raise E4SchemaError("empty model response")
                obj = json.loads(_strip_json_wrappers(raw))
                if not isinstance(obj, dict):
                    raise E4SchemaError(
                        f"response is {type(obj).__name__}, expected object")
                return validator(obj, final)
            except (json.JSONDecodeError, E4SchemaError) as err:
                last_err = err
                self.log.warning("[%s] %s attempt %d/%d (max_tokens=%d) "
                                 "schema/parse error: %s", guid, stage, attempt,
                                 self.config["max_retries"], max_tokens, err)
                if max_tokens < cap:
                    max_tokens = min(cap, max_tokens * 2)
                # Transient empty/truncated JSON responses from the endpoint
                # need recovery time; retrying with zero delay just re-hits
                # the same instability. Back off like the API-error path.
                if not final:
                    time.sleep(self.config.get("retry_backoff_seconds", 5))
            except E4Error:
                raise
            except Exception as err:  # network/API errors
                last_err = err
                self.log.warning("[%s] %s attempt %d/%d API error: %s",
                                 guid, stage, attempt,
                                 self.config["max_retries"], err)
                if not final:
                    time.sleep(5)
        raise E4ModelError(
            f"[{guid}] stage {stage}: all {self.config['max_retries']} "
            f"attempts failed; last error: {last_err}")


def make_deepseek_transport(e1, config, api_key):
    """Real transport using the frozen E1 client factory (JSON mode)."""
    client = e1.create_client("deepseek", api_key)

    def transport(system_prompt, user_prompt, max_tokens=None):
        max_tokens = max_tokens or config["max_output_tokens"]
        # A large token budget implies a long generation (empirically ~15-20
        # tokens/s worst case on big evidence extractions), so the per-request
        # timeout must scale with it or the call times out before finishing.
        timeout = min(600, max(config["request_timeout"], max_tokens // 25))
        response = client.chat.completions.create(
            model=config["model"],
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
            temperature=config["temperature"],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        return response.choices[0].message.content

    return transport


# ---------------------------------------------------------------------------
# Violations log (explicit surfacing of item-level rejections)
# ---------------------------------------------------------------------------

class ViolationLog:
    def __init__(self, path, logger=None):
        self.path = path
        self.count = 0
        self.by_kind = {}
        self.log = logger or logging.getLogger("e4")
        self._lock = threading.Lock()

    def record(self, guid, stage, kind, detail):
        entry = {"guid": guid, "stage": stage, "kind": kind, "detail": detail}
        with self._lock:
            self.count += 1
            self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
            self.log.warning("VIOLATION [%s] %s/%s: %s",
                             guid, stage, kind, detail)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def summary(self):
        return {"total": self.count, "by_kind": dict(self.by_kind)}


# ---------------------------------------------------------------------------
# Stage caches (resume support with identity checking)
# ---------------------------------------------------------------------------

class StageCache:
    """JSON cache {"_meta": {...}, "entries": {guid: payload}}.

    Resuming with a different meta (model config / prompt hash / stage) is a
    hard error: a cache must never silently mix prompt or model identities.
    """

    def __init__(self, path, meta):
        self.path = path
        self.meta = meta
        self._lock = threading.Lock()
        self.entries = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("_meta") != meta:
                raise E4ValidationError(
                    f"cache identity mismatch for {path}\n"
                    f"  on disk: {data.get('_meta')}\n  expected: {meta}\n"
                    "Delete the cache or use a fresh E4_RUN_TS.")
            self.entries = data["entries"]

    def get(self, guid):
        with self._lock:
            return self.entries.get(guid)

    def put(self, guid, payload):
        with self._lock:
            self.entries[guid] = payload
            self._flush()

    def _flush(self):
        # Caller holds self._lock. Unique tmp name so concurrent flushes of
        # this same cache never share a temp file before the atomic replace.
        tmp = f"{self.path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"_meta": self.meta, "entries": self.entries}, f,
                      ensure_ascii=False)
        os.replace(tmp, self.path)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger(log_path=None):
    logger = logging.getLogger("e4")
    logger.setLevel(logging.INFO)
    logger.handlers = []
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_path:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger
