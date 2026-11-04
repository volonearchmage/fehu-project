"""E6b offline checks — the ONLY delta vs E6 is the segmentation-granularity
instruction. Everything else must be byte-identical (scaffold identical to
the frozen E3a snapshot; segmentation still taxonomy-blind)."""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
E3A_SNAPSHOT = os.path.join(
    BASE_DIR, "RH_test", "E3a_task1_only_subevent", "runs",
    "20260723_141123", "system_prompt_snapshot.txt")
E6_SEG = os.path.join(BASE_DIR, "RH_test", "E6_e3a_self_segmentation",
                      "scripts", "run_segmentation_e6.py")
E6_PIPE = os.path.join(BASE_DIR, "RH_test", "E6_e3a_self_segmentation",
                       "scripts", "run_pipeline_e6.py")
E6B_SEG = os.path.join(HERE, "run_segmentation_e6b.py")
E6B_PIPE = os.path.join(HERE, "run_pipeline_e6b.py")

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


e6_seg = open(E6_SEG, encoding="utf-8").read()
e6b_seg = open(E6B_SEG, encoding="utf-8").read()
e6_pipe = open(E6_PIPE, encoding="utf-8").read()
e6b_pipe = open(E6B_PIPE, encoding="utf-8").read()

# ---- pipeline: identical except run-dir env var + experiment provenance ----
norm_a = e6_pipe.replace("E6_RUN_TS", "@TS@").replace(
    '"experiment": "E6_e3a_self_segmentation"', "@EXP@").replace(
    '"base_pipeline": "RH_test/E3a_task1_only_subevent/scripts/run_pipeline_e3a.py (frozen, copied)"', "@BP@")
norm_b = e6b_pipe.replace("E6B_RUN_TS", "@TS@").replace(
    '"experiment": "E6b_granularity_control"', "@EXP@").replace(
    '"base_pipeline": "RH_test/E6_e3a_self_segmentation/scripts/run_pipeline_e6.py (frozen, copied; identical scaffold)"', "@BP@")
check("pipeline byte-identical to E6 modulo run-dir env var + provenance",
      norm_a == norm_b)

# ---- segmentation: identical except the granularity rule ------------------
old_rule = ("3. Aim for 6-12 subevents for a typical article; use fewer for "
            "very short articles and more for very long ones. Never fewer than 2.")
new_rule = ("3. Aim for 6-9 subevents for a typical article; merge "
            "closely-related sentences that describe the same development "
            "into ONE subevent. Use fewer for very short articles and at "
            "most a few more for very long ones. Never fewer than 2.")
check("E6b seg prompt contains the new granularity rule",
      new_rule in e6b_seg and old_rule not in e6b_seg)
check("segmentation script otherwise byte-identical to E6",
      e6b_seg.replace(new_rule, old_rule) == e6_seg)

# ---- scaffold system prompt still byte-identical to frozen E3a ------------
e6b = load_module(E6B_PIPE, "e6b_pipeline")
l1, l2, l1l2 = e6b.load_taxonomy()
e6b.l1_name_to_id, e6b.l2_name_to_id, e6b.l1_id_to_l2_id = l1, l2, l1l2
examples = e6b.load_few_shot_examples(n=2)
sp = e6b.build_deepseek_system_prompt(examples)
sp = e6b.apply_prompt_variant(sp, "targeted_more_shot_balanced")
snapshot = open(E3A_SNAPSHOT, encoding="utf-8").read()
check("system prompt byte-identical to E3a frozen snapshot", sp == snapshot)

# ---- segmentation still taxonomy-blind ------------------------------------
seg_mod = load_module(E6B_SEG, "e6b_segmentation")
p = seg_mod.SEGMENTATION_SYSTEM_PROMPT.lower()
check("seg prompt has no value/direction vocabulary",
      "aligned" not in p and "contradictor" not in p and "human value" not in p)
check("seg script never loads taxonomy",
      "hv_categories" not in e6b_seg and "load_taxonomy" not in e6b_seg)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL E6B OFFLINE CHECKS PASSED")
