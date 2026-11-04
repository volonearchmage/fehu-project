"""E6 offline checks — run BEFORE any API call. All checks must pass.

Invariants:
  1. The E6 system prompt is BYTE-IDENTICAL to the frozen E3a run's snapshot
     (demos keep official training subevents; the scaffold is unchanged).
  2. The E6 eval path never uses dataset subevents: --segments is required,
     eval articles' subevents are overwritten, and there is no fallback.
  3. The segmentation prompt is taxonomy-blind: contains no L1/L2 value
     name, no value IDs list, no 'aligned'/'contradictory', and the
     segmentation script never loads the taxonomy or the actor list.
  4. parse_model_json and process_results are byte-identical to E3a's.
  5. A synthetic user prompt renders the SELF segments, not dataset ones.
"""

import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
E3A_SNAPSHOT = os.path.join(
    BASE_DIR, "RH_test", "E3a_task1_only_subevent", "runs",
    "20260723_141123", "system_prompt_snapshot.txt")
E3A_SRC = os.path.join(BASE_DIR, "RH_test", "E3a_task1_only_subevent",
                       "scripts", "run_pipeline_e3a.py")
E6_SRC = os.path.join(HERE, "run_pipeline_e6.py")
SEG_SRC = os.path.join(HERE, "run_segmentation_e6.py")

failures = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_fn(src, fn_name):
    """Extract a top-level function's source block by name."""
    m = re.search(rf"^def {fn_name}\(.*?(?=^def |^# =|\Z)", src,
                  re.M | re.S)
    return m.group(0) if m else None


e3a_src = open(E3A_SRC, encoding="utf-8").read()
e6_src = open(E6_SRC, encoding="utf-8").read()
seg_src = open(SEG_SRC, encoding="utf-8").read()

# ---- 1. system prompt byte-identical to frozen E3a snapshot ---------------
e6 = load_module(E6_SRC, "e6_pipeline")
l1, l2, l1l2 = e6.load_taxonomy()
e6.l1_name_to_id, e6.l2_name_to_id, e6.l1_id_to_l2_id = l1, l2, l1l2
examples = e6.load_few_shot_examples(n=2)
sp = e6.build_deepseek_system_prompt(examples)
sp = e6.apply_prompt_variant(sp, "targeted_more_shot_balanced")
snapshot = open(E3A_SNAPSHOT, encoding="utf-8").read()
check("system prompt byte-identical to E3a frozen snapshot",
      sp == snapshot)
check("demos carry official subevent texts (8 + 6)",
      [len(e["subevents"]) for e in examples] == [8, 6])

# ---- 2. eval path never uses dataset subevents ----------------------------
check("--segments argument exists and is documented required",
      '"--segments"' in e6_src and "REQUIRED" in e6_src)
check("pipeline aborts without --segments",
      "E6 never uses dataset subevents" in e6_src
      and "sys.exit(1)" in e6_src)
check("eval articles' subevents are overwritten from segments",
      'article["subevents"] = se' in e6_src)
check("missing-guid segmentation aborts (no fallback)",
      "lack self-segmentation" in e6_src)
check("no code path keeps dataset subevents for eval articles "
      "(overwrite happens before dry_run and before the article loop)",
      e6_src.index('article["subevents"] = se')
      < e6_src.index("if args.dry_run:"))

# ---- 3. segmentation is taxonomy-blind ------------------------------------
seg = load_module(SEG_SRC, "e6_segmentation")
seg_prompt = seg.SEGMENTATION_SYSTEM_PROMPT
l1_names = list(l1.keys())
l2_path = os.path.join(BASE_DIR, "dataset", "hv_categories",
                       "human_value_level2_values.json")
l2_names = list(json.load(open(l2_path, encoding="utf-8")).keys())
leaked = [n for n in l1_names + l2_names if n.lower() in seg_prompt.lower()]
check(f"segmentation prompt contains no L1/L2 value names (leaked={leaked})",
      not leaked)
check("segmentation prompt has no direction vocabulary",
      "aligned" not in seg_prompt.lower()
      and "contradictor" not in seg_prompt.lower()
      and "human value" not in seg_prompt.lower())
check("segmentation script never loads the taxonomy",
      "hv_categories" not in seg_src and "load_taxonomy" not in seg_src)
check("segmentation user prompt has no actor list",
      "actors" not in seg_src.split("def build_segmentation_user_prompt")[1]
      .split("def ")[0])

# ---- 4. parser + process_results byte-identical to E3a --------------------
for fn in ("parse_model_json", "process_results", "build_user_prompt",
           "build_deepseek_user_prompt", "build_system_prompt",
           "build_deepseek_system_prompt", "apply_prompt_variant",
           "load_few_shot_examples", "call_deepseek"):
    check(f"function {fn} byte-identical to E3a",
          extract_fn(e3a_src, fn) is not None
          and extract_fn(e3a_src, fn) == extract_fn(e6_src, fn))

# ---- 5. synthetic user prompt renders SELF segments -----------------------
fake_article = {
    "guid": "FAKE-1",
    "title": "T",
    "content": "C",
    "actors": [{"A": "a-1"}],
    "subevents": [{"id": "0", "subevent": "SELF_SEGMENT_MARKER"}],
}
up = e6.build_deepseek_user_prompt(fake_article)
check("user prompt renders the (self) subevents placed on the article",
      "SELF_SEGMENT_MARKER" in up and "0: SELF_SEGMENT_MARKER" in up)

# ---- 6. segmentation validator behaves ------------------------------------
ok_units = json.dumps({"subevents": [
    {"id": "7", "subevent": " a "}, {"id": "x", "subevent": "b"}]})
norm = seg.parse_and_validate(ok_units, "g")
check("validator normalizes ids to consecutive strings and strips text",
      norm == [{"id": "0", "subevent": "a"}, {"id": "1", "subevent": "b"}])
for bad in (json.dumps({"subevents": []}),
            json.dumps({"subevents": [{"id": "0", "subevent": ""}] * 3}),
            json.dumps({"nope": 1}),
            json.dumps({"subevents": [{"id": str(i), "subevent": "s"}
                                      for i in range(40)]})):
    try:
        seg.parse_and_validate(bad, "g")
        check(f"validator rejects {bad[:40]}...", False)
    except (ValueError, json.JSONDecodeError):
        check(f"validator rejects {bad[:40]}...", True)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL E6 OFFLINE CHECKS PASSED")
