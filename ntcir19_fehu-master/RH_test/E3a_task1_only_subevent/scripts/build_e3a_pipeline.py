#!/usr/bin/env python3
"""Build the E3a pipeline from the completed E1 pipeline (read-only).

Source:  RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py  (frozen — the
         E1 baseline, itself generated from liu_method/run_pipeline.py)
Output:  RH_test/E3a_task1_only_subevent/scripts/run_pipeline_e3a.py

Method: every E3a delta is a string replacement asserted to match EXACTLY
ONCE in the E1 source; any mismatch aborts without writing. The complete
E1→E3a diff is therefore auditable from this file alone. Neither the Liu
original, nor any E1 file, nor the Task-2-based E3 files
(RH_test/E3_subevent_decomposition/) are modified.

WHAT E3a IS (design doc: docs/FEHU_E3_DESIGN_ANALYSIS_20260723.md, "soft"
decomposition variant). E3a keeps E1 almost entirely intact — the same
repaired few-shot demos with their **Task-1 article-level gold** label sets,
the same output format, the same model settings, the same high-recall
behavior — and adds ONE thing: the article's existing **subevent texts**
(the `subevents` field of event_base.json — plain input segmentation
available for train/dev/test, NOT Task-2 gold) are shown to the model as a
reasoning scaffold, with an instruction to walk the article subevent by
subevent so no value expressed in a single part of the story is missed. The
model still emits ONE consolidated **article-level** Task-1 prediction per
actor, parsed exactly as in E1 (no per-subevent output, no code-side union).

E3a vs the Task-2-based E3:
  - E3  uses `subevents_human_values` (Task-2 gold) to re-render demos and
        asks for per-subevent output blocks, unioned in code.
  - E3a uses NO Task-2 gold at all: demos keep E1's Task-1 article-level
        gold; subevents appear only as input context; output is article-level
        directly. process_results and the parser are byte-identical to E1.

E3a deltas:
  A1  Bookkeeping: env var E1_RUN_TS -> E3A_RUN_TS.
  A2  Few-shot example dict carries the article's subevent TEXTS (input
      only); the Task-1 article-level `output` is unchanged from E1.
  A3  Demo rendering shows a "Subevents:" block from those texts.
  A4  TASK line: subevents provided to examine the article unit by unit;
      final answer stays a single article-level list per actor.
  A5  Guideline 7 (recall-oriented, not a strictness rule): walk the
      subevents, then merge into one article-level list per actor — a value
      counts if expressed in ANY subevent.
  A6  User prompt: add the "Subevents:" block and a subevent-by-subevent
      closing instruction; output stays a JSON array.
  A7  DeepSeek user-prompt rewrite anchor updated to the new closing line.
  A8  fewshot_meta records subevent counts.
  A9  run_config experiment name / base / delta list updated.

Explicitly UNCHANGED from E1: OUTPUT FORMAT (article-level), the DeepSeek
system-prompt object rewrite, parse_model_json, process_results (article-
level (actor,direction,l1) dedup), the demo-selection rule and full-content
rendering, the targeted_more_shot_balanced variant text, the L1->L2 mapping,
and the official evaluation path. No E2 evidence/bias-control rules added.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SRC = BASE / "RH_test" / "E1_fewshot_repair" / "scripts" / "run_pipeline_e1.py"
DST = HERE / "run_pipeline_e3a.py"

text = SRC.read_text(encoding="utf-8")
n_deltas = 0


def rep(old: str, new: str, tag: str):
    global text, n_deltas
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ABORT [{tag}]: pattern found {count} times "
                         f"(expected 1):\n{old[:120]}...")
    text = text.replace(old, new)
    n_deltas += 1


# ---- A1: run-timestamp env var ---------------------------------------------
rep(
    'os.environ.get("E1_RUN_TS")',
    'os.environ.get("E3A_RUN_TS")',
    "A1-envvar",
)

# ---- A2: demo dict carries subevent TEXTS (Task-1 output unchanged) ---------
rep(
    '''        examples.append({
            "guid": guid,
            "title": article["title"],
            "content": article["content"],  # E1: full content (<=2600 chars by selection)
            "actors": actor_list,
            "output": output_values
        })''',
    '''        examples.append({
            "guid": guid,
            "title": article["title"],
            "content": article["content"],  # E1: full content (<=2600 chars by selection)
            # E3a: subevent TEXTS only (input segmentation from event_base.json,
            # NOT Task-2 gold). The Task-1 article-level output is unchanged.
            "subevents": article.get("subevents", []) or [],
            "actors": actor_list,
            "output": output_values
        })''',
    "A2-demo-subevents",
)

# ---- A3: demo rendering shows the subevent list ----------------------------
rep(
    '''            output_str = json.dumps(ex["output"], indent=2, ensure_ascii=False)  # E1: complete label set
            system_prompt += f"""
--- Example {i+1} ---
Title: {ex["title"]}
Article: {ex["content"]}
Actors: {actor_str}
Output:
{output_str}
"""''',
    '''            subevent_str = "\\n".join(
                f'{se["id"]}: {se["subevent"]}' for se in ex.get("subevents", []))
            output_str = json.dumps(ex["output"], indent=2, ensure_ascii=False)  # E1: complete label set (Task-1 gold)
            system_prompt += f"""
--- Example {i+1} ---
Title: {ex["title"]}
Article: {ex["content"]}
Subevents:
{subevent_str}
Actors: {actor_str}
Output:
{output_str}
"""''',
    "A3-demo-render",
)

# ---- A4: TASK line ---------------------------------------------------------
rep(
    "TASK: Given a factual news article and a list of actors (people, "
    "organizations, or groups mentioned in the article), identify which "
    "human values each actor's behavior expresses or violates.",
    "TASK: Given a factual news article, a breakdown of the article into "
    "numbered subevents (event units extracted from the article), and a list "
    "of actors (people, organizations, or groups mentioned in the article), "
    "identify which human values each actor's behavior across the article "
    "expresses or violates. The subevents are provided so you can examine the "
    "article one event unit at a time and not overlook a value expressed in a "
    "single part of the story; your FINAL answer is one consolidated "
    "article-level list of values per actor.",
    "A4-task",
)

# ---- A5: guideline 7 (recall scan) -----------------------------------------
# Anchored on the unique "Rule-breakers" bullet (the last line of the
# "Common patterns" block, present once; OUTPUT FORMAT is left untouched so
# its two copies stay ambiguous but irrelevant here).
rep(
    '''   - Rule-breakers/criminals: often contradictory to "Be compliant"(30), "Be responsible"(42)''',
    '''   - Rule-breakers/criminals: often contradictory to "Be compliant"(30), "Be responsible"(42)
7. The article is split into numbered subevents. Work through them one at a time and note every value each actor's behavior in that subevent expresses or violates; then merge these observations into a single article-level list per actor, where a value counts if it is expressed in ANY subevent. Use this pass to recover values that appear in only one part of the story.''',
    "A5-guideline7",
)

# ---- A6: user prompt adds the subevent block + closing instruction ---------
rep(
    '''    return f"""Title: {article["title"]}

Article:
{content}

Actors:
{actor_str}

Identify the human values for each actor. Return ONLY a JSON array."""''',
    '''    subevent_lines = []
    for se in article.get("subevents", []) or []:
        subevent_lines.append(f'{se["id"]}: {se["subevent"]}')
    subevent_str = "\\n".join(subevent_lines)

    return f"""Title: {article["title"]}

Article:
{content}

Subevents:
{subevent_str}

Actors:
{actor_str}

Go through the subevents one at a time to catch every value each actor expresses, then consolidate into ONE article-level list of values per actor. Return ONLY a JSON array."""''',
    "A6-userprompt",
)

# ---- A7: DeepSeek user-prompt rewrite anchor -------------------------------
rep(
    '''    return prompt.replace(
        "Identify the human values for each actor. Return ONLY a JSON array.",
        'Identify the human values for each actor. Return ONLY a JSON object with an "items" array.'
    )''',
    '''    return prompt.replace(
        "Go through the subevents one at a time to catch every value each "
        "actor expresses, then consolidate into ONE article-level list of "
        "values per actor. Return ONLY a JSON array.",
        "Go through the subevents one at a time to catch every value each "
        "actor expresses, then consolidate into ONE article-level list of "
        'values per actor. Return ONLY a JSON object with an "items" array.'
    )''',
    "A7-deepseek-userprompt",
)

# ---- A8: fewshot_meta records subevent counts ------------------------------
rep(
    '''        json.dump([{"guid": ex["guid"], "title": ex["title"],
                    "n_output_labels": len(ex["output"]),
                    "content_chars": len(ex["content"])}
                   for ex in few_shot_examples], f, indent=2, ensure_ascii=False)''',
    '''        json.dump([{"guid": ex["guid"], "title": ex["title"],
                    "n_subevents": len(ex.get("subevents", [])),
                    "n_output_labels": len(ex["output"]),
                    "content_chars": len(ex["content"])}
                   for ex in few_shot_examples], f, indent=2, ensure_ascii=False)''',
    "A8-fewshotmeta",
)

# ---- A9: run_config bookkeeping --------------------------------------------
rep(
    '''        json.dump({"experiment": "E1_fewshot_repair",
                   "base_pipeline": "liu_method/run_pipeline.py (frozen, copied)",''',
    '''        json.dump({"experiment": "E3a_task1_only_subevent",
                   "base_pipeline": "RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py (frozen, copied)",''',
    "A9-experiment",
)
rep(
    '''                   "deltas": ["D1 deterministic multi-label demos",
                              "D2 full demo content, no 4-label cap",
                              "D3 numeric label caps removed",
                              "D4 outputs isolated under RH_test/E1_fewshot_repair",
                              "D5 base-dir discovery from new location"]},''',
    '''                   "deltas": ["E1: D1 deterministic multi-label demos",
                              "E1: D2 full demo content, no 4-label cap",
                              "E1: D3 numeric label caps removed",
                              "E3a: A subevent TEXTS added as reasoning scaffold (task, guideline 7, user prompt, demos)",
                              "E3a: demos keep E1 Task-1 article-level gold ONLY (no subevents_human_values / Task-2 gold)",
                              "E3a: output stays E1 article-level; parser + process_results unchanged",
                              "isolation: outputs under RH_test/E3a_task1_only_subevent"]},''',
    "A9-deltas",
)

DST.write_text(text, encoding="utf-8")
print(f"wrote {DST} with {n_deltas} asserted deltas")
