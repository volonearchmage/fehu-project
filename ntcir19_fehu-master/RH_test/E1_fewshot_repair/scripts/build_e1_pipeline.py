#!/usr/bin/env python3
"""Build the E1 pipeline as a machine-checked modification of the frozen Liu
pipeline (liu_method/run_pipeline.py, read-only).

Every E1 delta is a string replacement asserted to match EXACTLY ONCE in the
source; any mismatch aborts without writing. The output script is
scripts/run_pipeline_e1.py. This makes the complete diff between Liu and E1
auditable from this file alone.

E1 deltas (and nothing else):
  D1  few-shot construction: deterministic selection (sorted by guid) of 2
      train articles with 2-3 actors, every actor labeled, both directions
      present, >=1 actor with >=5 labels, 8-16 total labels, content <=2600
      chars; demo outputs carry the COMPLETE gold label set per actor in the
      exact compact 3-field output format (actor_id, l1_value_id, direction).
  D2  demo rendering: full article content shown (no [:500] cut, no
      "(truncated)" wording); no [:4] output cap.
  D3  numeric label caps removed from instruction text (mandate item 4):
      "3-7 relevant values" guideline, "at most 6 values" compact rule, and
      the "top 6 most relevant values" clause become evidence-based wording
      with no fixed count.
  D4  outputs/cache/prompt snapshots redirected into
      RH_test/E1_fewshot_repair/runs/<timestamp>/ (never touching
      output/task1/ or liu_method/ artifacts); run_config and few-shot
      metadata dumped alongside.
  D5  find_base_dir extended with two more ancestor levels so the copied
      script locates the project root from RH_test/E1_fewshot_repair/scripts/.

Explicitly UNCHANGED: model (deepseek-v4-flash), temperature 0.1,
max_tokens 8000, JSON mode, retry logic, parser (including its
direction-coercion behavior), dedup/format conversion, the
targeted_more_shot_balanced variant text except the two capped lines, and
the official evaluation path.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SRC = BASE / "liu_method" / "run_pipeline.py"
DST = HERE / "run_pipeline_e1.py"

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


# ---- D5: base-dir discovery from the new location --------------------------
rep(
    """    candidates = [
        script_dir,
        os.path.dirname(script_dir),
        os.path.join(script_dir, "ntcir19_fehu-master", "ntcir19_fehu-master"),
        os.path.join(script_dir, "ntcir19_fehu-master"),
    ]""",
    """    candidates = [
        script_dir,
        os.path.dirname(script_dir),
        os.path.dirname(os.path.dirname(script_dir)),
        os.path.dirname(os.path.dirname(os.path.dirname(script_dir))),
        os.path.join(script_dir, "ntcir19_fehu-master", "ntcir19_fehu-master"),
        os.path.join(script_dir, "ntcir19_fehu-master"),
    ]""",
    "D5-basedir",
)

# ---- D4: E1 run directory constants ---------------------------------------
rep(
    'OUTPUT_DIR = os.path.join(BASE_DIR, "output", "task1")',
    'OUTPUT_DIR = os.path.join(BASE_DIR, "output", "task1")  # unused in E1\n'
    'E1_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
    'E1_RUN_DIR = os.path.join(E1_DIR, "runs",\n'
    '                          os.environ.get("E1_RUN_TS")\n'
    '                          or time.strftime("%Y%m%d_%H%M%S"))',
    "D4-rundir",
)

# ---- D1: few-shot selection ------------------------------------------------
rep(
    '''    # Select good examples: articles with 2-3 actors and 4-8 total labels
    candidates = []
    for item in train_labels:
        guid = item["guid"]
        hvs = item.get("article_human_values", [])
        if guid in guid_to_article:
            actors = guid_to_article[guid].get("actors", [])
            if 2 <= len(actors) <= 3 and 4 <= len(hvs) <= 8:
                candidates.append(guid)

    # Take first n candidates
    selected = candidates[:n]''',
    '''    # E1 selection (deterministic): 2-3 actors, EVERY listed actor labeled
    # (and no gold actor outside the list), both directions present, at least
    # one actor with >=5 distinct directed labels, 8-16 distinct labels in
    # total, and full content <= 2600 chars so the demo article is shown
    # WITHOUT truncation. Candidates sorted by guid; first n taken.
    candidates = []
    for item in train_labels:
        guid = item["guid"]
        hvs = item.get("article_human_values", [])
        if guid not in guid_to_article:
            continue
        art = guid_to_article[guid]
        actor_ids = {aid for d in art.get("actors", []) for aid in d.values()}
        if not (2 <= len(actor_ids) <= 3):
            continue
        per_actor = {}
        dirs = set()
        for hv in hvs:
            per_actor.setdefault(str(hv["actor"]), set()).add(
                (hv["l1_value"], hv["direction"]))
            dirs.add(hv["direction"])
        if set(per_actor) != actor_ids or dirs != {"0", "1"}:
            continue
        total = sum(len(v) for v in per_actor.values())
        if max(len(v) for v in per_actor.values()) < 5 or not (8 <= total <= 16):
            continue
        if len(art.get("content", "")) > 2600:
            continue
        candidates.append(guid)

    selected = sorted(candidates)[:n]''',
    "D1-selection",
)

# ---- D1: demo output = complete label set in compact 3-field format --------
rep(
    '''        # Format gold labels for the example output
        output_values = []
        for hv in labels["article_human_values"]:
            # Reverse lookup l1 name from id
            l1_id = hv["l1_value"]
            l1_name = [k for k, v in l1_name_to_id.items() if v == l1_id][0]
            output_values.append({
                "actor_id": hv["actor"],
                "l1_value_name": l1_name,
                "l1_value_id": hv["l1_value"],
                "direction": "aligned" if hv["direction"] == "1" else "contradictory",
                "reasoning": hv.get("explanation", "")[:150]  # Truncate for prompt length
            })

        examples.append({
            "title": article["title"],
            "content": article["content"][:1500],  # Truncate long articles
            "actors": actor_list,
            "output": output_values
        })''',
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
    "D1-output",
)

# ---- D2: demo rendering ----------------------------------------------------
rep(
    '            output_str = json.dumps(ex["output"][:4], indent=2, ensure_ascii=False)  # Show first 4 for brevity',
    '            output_str = json.dumps(ex["output"], indent=2, ensure_ascii=False)  # E1: complete label set',
    "D2-nocap",
)
rep(
    'Article (truncated): {ex["content"][:500]}...',
    'Article: {ex["content"]}',
    "D2-fullcontent",
)

# ---- D3: remove fixed numeric label caps ----------------------------------
rep(
    "1. For each actor, identify 3-7 relevant values. Don't over-predict.",
    "1. For each actor, identify every value that has clear actor-specific "
    "evidence in the article. Do not pad the list with weakly supported values.",
    "D3-guideline",
)
rep(
    "3. For each actor, output at most 6 values.",
    "3. For each actor, output every value supported by actor-specific "
    "evidence; do not add values without evidence.",
    "D3-compact",
)
rep(
    "6. If a target label has weak but plausible evidence, keep it only when "
    "it is one of the actor's top 6 most relevant values.",
    "6. If a target label has weak but plausible evidence, keep it only when "
    "the actor-specific clue is concrete.",
    "D3-balanced",
)

# ---- D4: cache into the run dir -------------------------------------------
rep(
    '''    cache_path = os.path.join(
        BASE_DIR,
        "logs",
        f"cache_{args.mode}_{args.provider}_{safe_model_name}_{variant_tag}_temp{temp_tag}_max{token_tag}.json",
    )
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)''',
    '''    cache_path = os.path.join(
        E1_RUN_DIR,
        f"cache_{args.mode}_{args.provider}_{safe_model_name}_{variant_tag}_temp{temp_tag}_max{token_tag}.json",
    )
    os.makedirs(E1_RUN_DIR, exist_ok=True)''',
    "D4-cache",
)

# ---- D4: predictions into the run dir + artifact snapshots -----------------
rep(
    '''    run_tag = f"{args.mode}_{args.provider}_{safe_model_name}_{variant_tag}_temp{temp_tag}_max{token_tag}"
    output_dir = os.path.join(OUTPUT_DIR, "runs", run_tag)
    os.makedirs(output_dir, exist_ok=True)''',
    '''    run_tag = f"{args.mode}_{args.provider}_{safe_model_name}_{variant_tag}_temp{temp_tag}_max{token_tag}"
    output_dir = E1_RUN_DIR
    os.makedirs(output_dir, exist_ok=True)''',
    "D4-output",
)
rep(
    "    system_prompt = apply_prompt_variant(system_prompt, args.prompt_variant)",
    '''    system_prompt = apply_prompt_variant(system_prompt, args.prompt_variant)

    # E1 provenance snapshots (written even for dry runs)
    os.makedirs(E1_RUN_DIR, exist_ok=True)
    with open(os.path.join(E1_RUN_DIR, "system_prompt_snapshot.txt"), "w",
              encoding="utf-8") as f:
        f.write(system_prompt)
    with open(os.path.join(E1_RUN_DIR, "fewshot_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump([{"guid": ex["guid"], "title": ex["title"],
                    "n_output_labels": len(ex["output"]),
                    "content_chars": len(ex["content"])}
                   for ex in few_shot_examples], f, indent=2, ensure_ascii=False)
    with open(os.path.join(E1_RUN_DIR, "run_config.json"), "w",
              encoding="utf-8") as f:
        json.dump({"experiment": "E1_fewshot_repair",
                   "base_pipeline": "liu_method/run_pipeline.py (frozen, copied)",
                   "provider": args.provider, "model": model_name,
                   "temperature": args.temperature,
                   "max_output_tokens": max_output_tokens,
                   "prompt_variant": args.prompt_variant,
                   "mode": args.mode, "limit": args.limit,
                   "deltas": ["D1 deterministic multi-label demos",
                              "D2 full demo content, no 4-label cap",
                              "D3 numeric label caps removed",
                              "D4 outputs isolated under RH_test/E1_fewshot_repair",
                              "D5 base-dir discovery from new location"]},
                  f, indent=2)''',
    "D4-snapshots",
)

DST.write_text(text, encoding="utf-8")
print(f"wrote {DST} with {n_deltas} asserted deltas")
