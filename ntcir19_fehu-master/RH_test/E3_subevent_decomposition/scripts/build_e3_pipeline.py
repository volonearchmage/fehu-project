#!/usr/bin/env python3
"""Build the E3 pipeline from the completed E1 pipeline (read-only).

Source:  RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py  (frozen — the
         E1 baseline, itself generated from liu_method/run_pipeline.py)
Output:  RH_test/E3_subevent_decomposition/scripts/run_pipeline_e3.py

Method: every E3 delta is a string replacement asserted to match EXACTLY ONCE
in the E1 source; any mismatch aborts without writing. The complete E1→E3
diff is therefore auditable from this file alone. Neither the Liu original
nor any E1/E2 file is modified.

E3 changes the UNIT OF PREDICTION, nothing else (design doc:
docs/FEHU_E3_DESIGN_ANALYSIS_20260723.md). One API call per article, but the
model judges each listed subevent separately and returns per-subevent label
blocks; the article-level prediction is the deterministic direction-specific
union computed in code (the existing (actor, direction, l1_value) dedup).
None of E2's rejected bias-control/evidence-gate instructions are included.

E3 deltas:
  S1  Prompt: TASK line reframed to per-subevent judgment; structural
      guideline 7 added (judge each subevent on its own events; values may
      recur across subevents; uninvolved actors get nothing); OUTPUT FORMAT
      becomes one element per subevent, each with "subevent_id" and an
      "items" array (empty allowed); DeepSeek JSON-object rewrite updated to
      a top-level {"subevents": [...]} with a matching example; user prompt
      lists the article's subevents and asks for per-subevent output.
  S2  Few-shot demos: same two deterministically selected E1 demo articles
      (selection rule untouched), but demo outputs re-rendered from the
      OFFICIAL per-subevent train gold (`subevents_human_values`), one block
      per subevent in article order, deduplicated within each block, in the
      exact compact 3-field item format; subevents without gold labels show
      an empty "items" array. Demo subevent lists rendered in the examples.
  S3  Parser accepts the {"subevents": [...]} object; process_results
      flattens the per-subevent blocks and the existing (actor, direction,
      l1_value) dedup performs the deterministic direction-specific union.
  S4  Metadata: per-label supporting-subevent lists exported to
      unit_support.json (analysis/verifier input ONLY — never a filter).
  S5  Bookkeeping: env var E1_RUN_TS -> E3_RUN_TS; run_config experiment
      name, base_pipeline, and delta list updated; fewshot_meta records
      subevent counts.

Everything else — model, temperature, max tokens, JSON mode, retries, cache
handling, the targeted_more_shot_balanced variant text as modified by E1,
E1's demo-selection rule and full-content rendering, the L1->L2 mapping and
per-task dedup, and the official evaluation path — is byte-identical to E1.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SRC = BASE / "RH_test" / "E1_fewshot_repair" / "scripts" / "run_pipeline_e1.py"
DST = HERE / "run_pipeline_e3.py"

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


# ---- S5: run-timestamp env var ---------------------------------------------
rep(
    'os.environ.get("E1_RUN_TS")',
    'os.environ.get("E3_RUN_TS")',
    "S5-envvar",
)

# ---- S2: demo outputs from official per-subevent gold ----------------------
# Selection rule (2-3 actors, every actor labeled, both directions, >=1 actor
# with >=5 labels, 8-16 total, <=2600 chars) is untouched, so the same two
# demos are chosen. Only the rendering of their outputs changes.
rep(
    '''        # E1: complete, deduplicated gold label set per actor, in the exact
        # compact output format the model is asked to produce
        # (actor_id, l1_value_id, direction) -- no cap, no reasoning field.
        seen = set()
        output_values = []
        for hv in labels["article_human_values"]:
            key = (str(hv["actor"]), str(hv["l1_value"]), str(hv["direction"]))
            if key in seen:
                continue
            seen.add(key)
            output_values.append({
                "actor_id": hv["actor"],
                "l1_value_id": hv["l1_value"],
                "direction": "aligned" if hv["direction"] == "1" else "contradictory",
            })

        examples.append({
            "guid": guid,
            "title": article["title"],
            "content": article["content"],  # E1: full content (<=2600 chars by selection)
            "actors": actor_list,
            "output": output_values
        })''',
    '''        # E3: demo output = OFFICIAL per-subevent train gold
        # (subevents_human_values), one block per subevent in article order,
        # deduplicated within each block, items in the exact compact 3-field
        # format (actor_id, l1_value_id, direction). Subevents without gold
        # labels show an empty "items" array (empty output is legitimate).
        se_gold = {str(blk["subevent_id"]): blk.get("subevent_human_values", [])
                   for blk in labels.get("subevents_human_values", [])}
        unit_outputs = []
        n_labels = 0
        for se in article.get("subevents", []) or []:
            sid = str(se["id"])
            seen = set()
            items = []
            for hv in se_gold.get(sid, []):
                key = (str(hv["actor"]), str(hv["l1_value"]), str(hv["direction"]))
                if key in seen:
                    continue
                seen.add(key)
                items.append({
                    "actor_id": hv["actor"],
                    "l1_value_id": hv["l1_value"],
                    "direction": "aligned" if hv["direction"] == "1" else "contradictory",
                })
            n_labels += len(items)
            unit_outputs.append({"subevent_id": sid, "items": items})

        examples.append({
            "guid": guid,
            "title": article["title"],
            "content": article["content"],  # E1: full content (<=2600 chars by selection)
            "actors": actor_list,
            "subevents": article.get("subevents", []) or [],
            "output": unit_outputs,
            "n_labels": n_labels,
        })''',
    "S2-demo-gold",
)

# ---- S1: TASK line ----------------------------------------------------------
rep(
    "TASK: Given a factual news article and a list of actors (people, "
    "organizations, or groups mentioned in the article), identify which "
    "human values each actor's behavior expresses or violates.",
    "TASK: Given a factual news article, its list of subevents (numbered "
    "event units extracted from the article), and a list of actors (people, "
    "organizations, or groups mentioned in the article), identify FOR EACH "
    "SUBEVENT which human values each actor's behavior in that subevent "
    "expresses or violates. Judge every subevent on its own described "
    "events, using the full article as background context.",
    "S1-task",
)

# ---- S1: guideline 7 + per-subevent OUTPUT FORMAT (template only) ----------
# Anchored through the unique "Rule-breakers" guideline tail so the separate
# single-line copies of these strings inside build_deepseek_system_prompt's
# .replace() arguments stay untouched (same anchoring gotcha as E2's B2).
rep(
    '''   - Rule-breakers/criminals: often contradictory to "Be compliant"(30), "Be responsible"(42)

OUTPUT FORMAT: Return ONLY a valid JSON array. Each element must have:
- "actor_id": the actor's ID string (e.g., "0-4405-1-3-0")
- "l1_value_id": the Level-1 value ID as a string (e.g., "42")
- "direction": either "aligned" or "contradictory"
- "reasoning": one sentence explaining why (keep it brief)

Do NOT include any text before or after the JSON array. No markdown, no explanation."""''',
    '''   - Rule-breakers/criminals: often contradictory to "Be compliant"(30), "Be responsible"(42)
7. Judge each subevent independently on its own described events. The same value may legitimately recur in several subevents — output it in every subevent where that actor's behavior supports it. If an actor plays no role in a subevent, output nothing for that actor in that subevent.

OUTPUT FORMAT: Return ONLY a valid JSON array with one element per subevent, in the order the subevents are listed. Each element must have:
- "subevent_id": the subevent's id string (e.g., "0")
- "items": the value judgments for that subevent (an empty array if none); each item must have:
  - "actor_id": the actor's ID string (e.g., "0-4405-1-3-0")
  - "l1_value_id": the Level-1 value ID as a string (e.g., "42")
  - "direction": either "aligned" or "contradictory"
  - "reasoning": one sentence explaining why (keep it brief)

Do NOT include any text before or after the JSON array. No markdown, no explanation."""''',
    "S1-outputformat",
)

# ---- S1: demo rendering shows the subevent list ----------------------------
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
                f'{se["id"]}: {se["subevent"]}' for se in ex["subevents"])
            output_str = json.dumps(ex["output"], indent=2, ensure_ascii=False)  # E3: official per-subevent gold
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
    "S1-demo-render",
)

# ---- S1: DeepSeek JSON-object rewrite --------------------------------------
rep(
    '''    prompt = prompt.replace(
        "OUTPUT FORMAT: Return ONLY a valid JSON array. Each element must have:",
        'OUTPUT FORMAT: Return ONLY a valid JSON object with an "items" array. '
        'Each element in "items" must have:'
    ).replace(''',
    '''    prompt = prompt.replace(
        "OUTPUT FORMAT: Return ONLY a valid JSON array with one element per "
        "subevent, in the order the subevents are listed. Each element must have:",
        'OUTPUT FORMAT: Return ONLY a valid JSON object with a "subevents" '
        'array holding one element per subevent, in the order the subevents '
        'are listed. Each element must have:'
    ).replace(''',
    "S1-deepseek-header",
)
rep(
    '''        "Do NOT include any text before or after the JSON array. No markdown, no explanation.",
        'Do NOT include any text before or after the JSON object. No markdown, no explanation.\\n\\n'
        'Example JSON output:\\n'
        '{\\n'
        '  "items": [\\n'
        '    {\\n'
        '      "actor_id": "0-4405-1-3-0",\\n'
        '      "l1_value_id": "42",\\n'
        '      "direction": "aligned",\\n'
        '      "reasoning": "The actor takes responsibility for public safety."\\n'
        '    }\\n'
        '  ]\\n'
        '}'
    )''',
    '''        "Do NOT include any text before or after the JSON array. No markdown, no explanation.",
        'Do NOT include any text before or after the JSON object. No markdown, no explanation.\\n\\n'
        'Example JSON output:\\n'
        '{\\n'
        '  "subevents": [\\n'
        '    {\\n'
        '      "subevent_id": "0",\\n'
        '      "items": [\\n'
        '        {\\n'
        '          "actor_id": "0-4405-1-3-0",\\n'
        '          "l1_value_id": "42",\\n'
        '          "direction": "aligned",\\n'
        '          "reasoning": "The actor takes responsibility for public safety."\\n'
        '        }\\n'
        '      ]\\n'
        '    }\\n'
        '  ]\\n'
        '}'
    )''',
    "S1-deepseek-example",
)

# ---- S1: user prompt lists subevents ---------------------------------------
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

For each subevent, identify the human values each actor's behavior in that subevent expresses or violates. Return ONLY a JSON array with one element per subevent."""''',
    "S1-userprompt",
)
rep(
    '''    return prompt.replace(
        "Identify the human values for each actor. Return ONLY a JSON array.",
        'Identify the human values for each actor. Return ONLY a JSON object with an "items" array.'
    )''',
    '''    return prompt.replace(
        "For each subevent, identify the human values each actor's behavior "
        "in that subevent expresses or violates. Return ONLY a JSON array "
        "with one element per subevent.",
        "For each subevent, identify the human values each actor's behavior "
        "in that subevent expresses or violates. Return ONLY a JSON object "
        'with a "subevents" array, one element per subevent.'
    )''',
    "S1-deepseek-userprompt",
)

# ---- S3: parser accepts the per-subevent object ----------------------------
rep(
    '''    result = json.loads(content)
    if isinstance(result, dict) and "items" in result:
        result = result["items"]''',
    '''    result = json.loads(content)
    if isinstance(result, dict) and "subevents" in result:
        result = result["subevents"]
    elif isinstance(result, dict) and "items" in result:
        result = result["items"]''',
    "S3-parser",
)

# ---- S3: flatten per-subevent blocks; dedup below IS the union -------------
rep(
    '''    task1a_values = []  # For pred_task1a.json
    task1b_values = []  # For pred_task1b.json

    seen_task1a = set()  # Deduplicate (actor, l2_value)
    seen_task1b = set()  # Deduplicate (actor, direction, l1_value)

    for item in gpt_results:''',
    '''    # E3: the model output is per-subevent ([{"subevent_id", "items"}]).
    # Flatten the blocks here; the (actor, direction, l1_value) dedup below
    # IS the deterministic direction-specific union across subevents.
    flat = []
    for elem in gpt_results:
        if isinstance(elem, dict) and isinstance(elem.get("items"), list):
            unit_id = str(elem.get("subevent_id", ""))
            for item in elem["items"]:
                flat.append((unit_id, item))
        elif isinstance(elem, dict):
            flat.append(("", elem))  # tolerate flat article-level items

    task1a_values = []  # For pred_task1a.json
    task1b_values = []  # For pred_task1b.json

    seen_task1a = set()  # Deduplicate (actor, l2_value)
    seen_task1b = set()  # Deduplicate (actor, direction, l1_value)
    unit_support = {}    # "direction:l1@actor" -> supporting subevent ids

    for unit_id, item in flat:
        if not isinstance(item, dict):
            continue''',
    "S3-flatten",
)

# ---- S4: record supporting subevents (metadata only, never a filter) -------
rep(
    '''        # Map L1 -> L2
        l2_id = l1_id_to_l2_id.get(l1_id, None)
        if l2_id is None:
            continue

        # Task 1a: (actor, l2_value) - deduplicate''',
    '''        # Map L1 -> L2
        l2_id = l1_id_to_l2_id.get(l1_id, None)
        if l2_id is None:
            continue

        # E3 metadata only (never a filter): which subevents support this label
        skey = f"{direction}:{l1_id}@{actor_id}"
        units = unit_support.setdefault(skey, [])
        if unit_id not in units:
            units.append(unit_id)

        # Task 1a: (actor, l2_value) - deduplicate''',
    "S4-support",
)
rep(
    "    return task1a_values, task1b_values",
    "    return task1a_values, task1b_values, unit_support",
    "S4-return",
)
rep(
    '''    # Process each article
    all_task1a = []
    all_task1b = []''',
    '''    # Process each article
    all_task1a = []
    all_task1b = []
    all_unit_support = {}''',
    "S4-accumulator",
)
rep(
    '''        # Process results
        task1a_values, task1b_values = process_results(guid, article["actors"], gpt_results)''',
    '''        # Process results
        task1a_values, task1b_values, unit_support = process_results(guid, article["actors"], gpt_results)
        all_unit_support[guid] = unit_support''',
    "S4-callsite",
)
rep(
    '''    with open(task1b_path, "w", encoding="utf-8") as f:
        json.dump(all_task1b, f, indent=2, ensure_ascii=False)
    print(f"Saved Task-1b predictions to: {task1b_path}")''',
    '''    with open(task1b_path, "w", encoding="utf-8") as f:
        json.dump(all_task1b, f, indent=2, ensure_ascii=False)
    print(f"Saved Task-1b predictions to: {task1b_path}")

    support_path = os.path.join(output_dir, "unit_support.json")
    with open(support_path, "w", encoding="utf-8") as f:
        json.dump(all_unit_support, f, indent=2, ensure_ascii=False)
    print(f"Saved subevent-support metadata to: {support_path}")''',
    "S4-save",
)

# ---- S5: snapshots and run_config bookkeeping ------------------------------
rep(
    '''        json.dump([{"guid": ex["guid"], "title": ex["title"],
                    "n_output_labels": len(ex["output"]),
                    "content_chars": len(ex["content"])}
                   for ex in few_shot_examples], f, indent=2, ensure_ascii=False)''',
    '''        json.dump([{"guid": ex["guid"], "title": ex["title"],
                    "n_subevents": len(ex["subevents"]),
                    "n_output_labels": ex["n_labels"],
                    "content_chars": len(ex["content"])}
                   for ex in few_shot_examples], f, indent=2, ensure_ascii=False)''',
    "S5-fewshotmeta",
)
rep(
    '''        json.dump({"experiment": "E1_fewshot_repair",
                   "base_pipeline": "liu_method/run_pipeline.py (frozen, copied)",''',
    '''        json.dump({"experiment": "E3_subevent_decomposition",
                   "base_pipeline": "RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py (frozen, copied)",''',
    "S5-experiment",
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
                              "E3: S1 per-subevent prediction unit (task, output format, user prompt, demos)",
                              "E3: S2 demos re-rendered from official subevents_human_values gold",
                              "E3: S3 deterministic direction-specific union across subevents",
                              "E3: S4 unit_support metadata exported (never a filter)",
                              "isolation: outputs under RH_test/E3_subevent_decomposition"]},''',
    "S5-deltas",
)

DST.write_text(text, encoding="utf-8")
print(f"wrote {DST} with {n_deltas} asserted deltas")
