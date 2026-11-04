"""E6c offline checks — the ONLY deltas vs E6b's pipeline are:
  (1) call_deepseek adds extra_body thinking:disabled (pro non-thinking mode)
  (2) run-dir env var + experiment provenance strings
The scaffold system prompt must remain byte-identical to the frozen E3a
snapshot. E6c consumes E6b's segments (model is the only variable vs E6b)."""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
E3A_SNAPSHOT = os.path.join(
    BASE_DIR, "RH_test", "E3a_task1_only_subevent", "runs",
    "20260723_141123", "system_prompt_snapshot.txt")
E6B_PIPE = os.path.join(BASE_DIR, "RH_test", "E6b_granularity_control",
                        "scripts", "run_pipeline_e6b.py")
E6C_PIPE = os.path.join(HERE, "run_pipeline_e6c.py")

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


b = open(E6B_PIPE, encoding="utf-8").read()
c = open(E6C_PIPE, encoding="utf-8").read()

thinking_block = (
    "                timeout=request_timeout,\n"
    "                # E6c delta: run deepseek-v4-pro in NON-thinking mode\n"
    "                # (probe 2026-07-24: reasoning_content None, no thinking"
    " tokens)\n"
    '                extra_body={"thinking": {"type": "disabled"}},\n')
check("E6c call_deepseek contains thinking:disabled",
      '"thinking": {"type": "disabled"}' in c)
norm_c = (c.replace(thinking_block, "                timeout=request_timeout,\n")
          .replace("E6C_RUN_TS", "E6B_RUN_TS")
          .replace('"experiment": "E6c_pro_nonthinking"',
                   '"experiment": "E6b_granularity_control"')
          .replace('"base_pipeline": "RH_test/E6b_granularity_control/scripts/'
                   'run_pipeline_e6b.py (frozen, copied; identical scaffold; '
                   'call_deepseek adds thinking:disabled)"',
                   '"base_pipeline": "RH_test/E6_e3a_self_segmentation/scripts/'
                   'run_pipeline_e6.py (frozen, copied; identical scaffold)"'))
check("E6c pipeline byte-identical to E6b modulo the three declared deltas",
      norm_c == b)
check("thinking:disabled applies ONLY to the deepseek call path "
      "(exactly one occurrence)",
      c.count('"thinking": {"type": "disabled"}') == 1
      and c.count("extra_body") == 1)

e6c = load_module(E6C_PIPE, "e6c_pipeline")
l1, l2, l1l2 = e6c.load_taxonomy()
e6c.l1_name_to_id, e6c.l2_name_to_id, e6c.l1_id_to_l2_id = l1, l2, l1l2
examples = e6c.load_few_shot_examples(n=2)
sp = e6c.apply_prompt_variant(
    e6c.build_deepseek_system_prompt(examples), "targeted_more_shot_balanced")
snapshot = open(E3A_SNAPSHOT, encoding="utf-8").read()
check("system prompt byte-identical to E3a frozen snapshot", sp == snapshot)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL E6C OFFLINE CHECKS PASSED")
