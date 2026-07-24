#!/usr/bin/env python3
"""Offline (no-API) checks of the generated E3 pipeline logic.

Verifies, on synthetic data only:
  1. parse_model_json accepts the E3 {"subevents": [...]} object (and keeps
     the legacy {"items": [...]} fallback);
  2. process_results performs the deterministic direction-specific union
     across subevent blocks, keeps per-task dedup and validation (bad actor,
     bad l1 id) exactly as in E1, and reports unit_support correctly;
  3. the few-shot loader still selects the two frozen E1 demo articles and
     renders one output block per subevent from the official
     subevents_human_values gold.

Run: python3 offline_check_e3.py   (stdlib only; never calls any API)
"""

import json
import os
import sys

os.environ.setdefault("E3_RUN_TS", "offline_check_tmp")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_pipeline_e3 as p  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


# taxonomy globals (main() normally sets these)
p.l1_name_to_id, p.l2_name_to_id, p.l1_id_to_l2_id = p.load_taxonomy()

# ---- 1. parser -------------------------------------------------------------
obj = {"subevents": [{"subevent_id": "0", "items": []}]}
check("parser unwraps subevents object",
      p.parse_model_json(json.dumps(obj), "t") == obj["subevents"])
check("parser keeps items fallback",
      p.parse_model_json('{"items": [{"a": 1}]}', "t") == [{"a": 1}])

# ---- 2. union / dedup / validation / unit_support --------------------------
actors = [{"Actor A": "A-1"}, {"Actor B": "B-2"}]
fake = [
    {"subevent_id": "0", "items": [
        {"actor_id": "A-1", "l1_value_id": "22", "direction": "contradictory"},
    ]},
    {"subevent_id": "1", "items": [
        # same (actor, value, direction) again -> union keeps ONE, support 2
        {"actor_id": "A-1", "l1_value_id": "22", "direction": "contradictory"},
        # same value, OTHER direction -> direction-specific: kept separately
        {"actor_id": "A-1", "l1_value_id": "22", "direction": "aligned"},
        {"actor_id": "B-2", "l1_value_id": "26", "direction": "aligned"},
        {"actor_id": "GHOST", "l1_value_id": "22", "direction": "aligned"},  # invalid actor
        {"actor_id": "B-2", "l1_value_id": "99", "direction": "aligned"},    # invalid l1
    ]},
    {"subevent_id": "2", "items": []},
]
t1a, t1b, sup = p.process_results("g", actors, fake)
got_1b = {(v["actor"], v["direction"], v["l1_value"]) for v in t1b}
check("1b union = 3 directed labels", got_1b == {
    ("A-1", "0", "22"), ("A-1", "1", "22"), ("B-2", "1", "26")})
check("1a projected + deduped", {(v["actor"], v["l2_value"]) for v in t1a}
      == {("A-1", p.l1_id_to_l2_id["22"]), ("B-2", p.l1_id_to_l2_id["26"])})
check("unit_support counts units not items", sup.get("0:22@A-1") == ["0", "1"]
      and sup.get("1:22@A-1") == ["1"] and sup.get("1:26@B-2") == ["1"])
check("invalid items absent from support",
      not any("GHOST" in k or ":99@" in k for k in sup))

# legacy flat items (no subevent blocks) still processed
t1a_f, t1b_f, sup_f = p.process_results(
    "g", actors, [{"actor_id": "A-1", "l1_value_id": "22", "direction": "aligned"}])
check("flat fallback tolerated", len(t1b_f) == 1 and sup_f["1:22@A-1"] == [""])

# ---- 3. few-shot loader ----------------------------------------------------
ex = p.load_few_shot_examples(n=2)
check("frozen E1 demo guids", [e["guid"] for e in ex] == ["0-4349-1-t", "0-4352-3-1"])
check("one output block per subevent", all(
    [b["subevent_id"] for b in e["output"]] == [str(s["id"]) for s in e["subevents"]]
    for e in ex))
with open(p.TRAIN_LABELS, encoding="utf-8") as f:
    gold = {i["guid"]: i for i in json.load(f)}
for e in ex:
    se_gold = {str(b["subevent_id"]): b.get("subevent_human_values", [])
               for b in gold[e["guid"]].get("subevents_human_values", [])}
    ok = True
    for blk in e["output"]:
        want = {(str(h["actor"]), str(h["l1_value"]),
                 "aligned" if h["direction"] == "1" else "contradictory")
                for h in se_gold.get(blk["subevent_id"], [])}
        got = {(i["actor_id"], i["l1_value_id"], i["direction"])
               for i in blk["items"]}
        ok = ok and want == got and all(set(i) == {"actor_id", "l1_value_id",
                                                   "direction"}
                                        for i in blk["items"])
    check(f"demo {e['guid']} blocks == official subevent gold (deduped)", ok)

print()
if failures:
    sys.exit(f"{len(failures)} check(s) FAILED: {failures}")
print(f"ALL CHECKS PASSED")
