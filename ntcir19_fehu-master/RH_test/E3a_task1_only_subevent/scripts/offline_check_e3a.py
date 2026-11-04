#!/usr/bin/env python3
"""Offline (no-API) checks of the generated E3a pipeline logic.

Verifies, on real taxonomy + train data (never calling any API):
  1. E3a uses NO Task-2 gold: the generated source never references
     `subevents_human_values`, and the few-shot demos' `output` is BYTE-
     IDENTICAL to E1's (same Task-1 article-level gold, 15 + 10 labels);
  2. E3a only ADDS subevent TEXTS to demos (input segmentation), same two
     frozen E1 demo guids;
  3. parse_model_json and process_results are unchanged from E1 — article-
     level {"items": [...]} handling, (actor, direction, l1) dedup, invalid
     actor/l1 drops — and process_results still returns exactly two values
     (no per-subevent union machinery, unlike E3).

Run: python3 offline_check_e3a.py   (stdlib only; never calls any API)
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
os.environ.setdefault("E3A_RUN_TS", "offline_check_tmp")

sys.path.insert(0, HERE)
import run_pipeline_e3a as p  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


# ---- 1a. no Task-2 gold anywhere in the generated source -------------------
# The only allowed mention of "subevents_human_values" is the descriptive
# run_config delta label; there must be NO code that actually reads it
# (subscript or .get access into the Task-2 gold structure).
src = open(os.path.join(HERE, "run_pipeline_e3a.py"), encoding="utf-8").read()
check("no code reads subevents_human_values (Task-2 gold)",
      '["subevents_human_values"]' not in src
      and '.get("subevents_human_values"' not in src
      and "['subevents_human_values']" not in src)
check("only mention of subevents_human_values is the descriptive label",
      src.count("subevents_human_values") == 1
      and "no subevents_human_values" in src)
check("source has no per-subevent output wrapper (unlike E3)",
      '"subevents": [' not in src and 'result["subevents"]' not in src)

p.l1_name_to_id, p.l2_name_to_id, p.l1_id_to_l2_id = p.load_taxonomy()

# ---- 1b. demo output byte-identical to E1 (Task-1 article-level gold) -------
e1_dir = os.path.join(BASE, "RH_test", "E1_fewshot_repair", "scripts")
sys.path.insert(0, e1_dir)
os.environ.setdefault("E1_RUN_TS", "offline_check_tmp_e1")
import run_pipeline_e1 as e1  # noqa: E402
e1.l1_name_to_id, e1.l2_name_to_id, e1.l1_id_to_l2_id = e1.load_taxonomy()

ex_a = p.load_few_shot_examples(n=2)
ex_1 = e1.load_few_shot_examples(n=2)
check("same two frozen E1 demo guids",
      [e["guid"] for e in ex_a] == [e["guid"] for e in ex_1] == ["0-4349-1-t", "0-4352-3-1"])
check("demo OUTPUT byte-identical to E1 (Task-1 gold, no Task-2)",
      [e["output"] for e in ex_a] == [e["output"] for e in ex_1])
check("demo output label counts are E1's 15 + 10 (not E3's 13 + 8)",
      [len(e["output"]) for e in ex_a] == [15, 10])
check("demo output items are 3-field article-level (no l2/explanation/subevent_id)",
      all(set(it) == {"actor_id", "l1_value_id", "direction"}
          for e in ex_a for it in e["output"]))

# ---- 2. E3a only ADDS subevent texts ---------------------------------------
check("demos carry subevent TEXTS (input segmentation)",
      all(e.get("subevents") and all({"id", "subevent"} <= set(s) for s in e["subevents"])
          for e in ex_a))
check("subevent counts 8 + 6", [len(e["subevents"]) for e in ex_a] == [8, 6])

# ---- 3. parser + process_results unchanged from E1 -------------------------
check("parser unwraps items object",
      p.parse_model_json('{"items": [{"a": 1}]}', "t") == [{"a": 1}])
check("parser has no subevents branch (E1 behavior)",
      p.parse_model_json('{"subevents": [{"x": 1}]}', "t") == [{"subevents": [{"x": 1}]}])

actors = [{"Actor A": "A-1"}, {"Actor B": "B-2"}]
flat = [
    {"actor_id": "A-1", "l1_value_id": "22", "direction": "contradictory"},
    {"actor_id": "A-1", "l1_value_id": "22", "direction": "contradictory"},  # dup
    {"actor_id": "A-1", "l1_value_id": "22", "direction": "aligned"},        # other dir kept
    {"actor_id": "B-2", "l1_value_id": "26", "direction": "aligned"},
    {"actor_id": "GHOST", "l1_value_id": "22", "direction": "aligned"},      # invalid actor
    {"actor_id": "B-2", "l1_value_id": "99", "direction": "aligned"},        # invalid l1
]
ret = p.process_results("g", actors, flat)
check("process_results returns exactly 2 values (article-level, not E3's 3)",
      isinstance(ret, tuple) and len(ret) == 2)
t1a, t1b = ret
check("1b dedup keeps both directions, drops invalids",
      {(v["actor"], v["direction"], v["l1_value"]) for v in t1b}
      == {("A-1", "0", "22"), ("A-1", "1", "22"), ("B-2", "1", "26")})
check("1a projected + deduped",
      {(v["actor"], v["l2_value"]) for v in t1a}
      == {("A-1", p.l1_id_to_l2_id["22"]), ("B-2", p.l1_id_to_l2_id["26"])})

print()
if failures:
    sys.exit(f"{len(failures)} check(s) FAILED: {failures}")
print("ALL CHECKS PASSED")
