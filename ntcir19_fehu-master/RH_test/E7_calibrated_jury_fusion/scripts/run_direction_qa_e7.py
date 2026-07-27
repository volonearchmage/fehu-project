#!/usr/bin/env python3
"""E7 G4 — targeted direction-QA repair on a fused run's flagged cells.

Flag rule (pre-registered): a fused cell (actor, value, direction) is flagged
iff at least one juror predicts the SAME value with the OPPOSITE direction
(annotation field jury_opposite_direction >= 1) AND the fused set does not
already contain both directions of that value for that actor (gold can
legitimately contain both; those are skipped).

For each flagged cell one focused QA call (deepseek-v4-flash, temp 0.1, JSON
mode) decides aligned vs contradictory from the article text alone; the cell's
direction is flipped iff the QA answer differs from the current direction.
Decisions are cached per (guid, actor, value); an API failure after retries
KEEPS the original direction and is recorded as qa_failed (logged, never
silent). Everything else is copied through unchanged; Task-1a is re-projected.

Usage:
  python run_direction_qa_e7.py --in_run runs/<ts>_G3_veto_add \
      --out_dir runs/<ts>_G4_dirqa
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "RH_test/E5_deberta_auxiliary_fusion/scripts"))

from fusion_lib import (  # noqa: E402
    FusionError, load_articles, load_task1b, load_l1_to_l2, project_1a,
    write_pred_files, split_label, sha256_file,
)

ARTICLES = ROOT / "dataset/dev/dev_event_base.json"
HV_DIR = ROOT / "dataset/hv_categories"
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0.1
MAX_TOKENS = 300
TIMEOUT = 120
MAX_RETRIES = 3

QA_SYSTEM = """You are an expert in human value analysis for news articles.

You will be given a news article, one actor from that article, and ONE human value. Decide whether the actor's behavior in the article ALIGNS with the value (supports, upholds, or expresses it) or CONTRADICTS the value (violates, undermines, or works against it).

Judge only from the actor's described behavior and statements in the article, not from the actor's typical role.

Return ONLY a valid JSON object: {"direction": "aligned"} or {"direction": "contradictory"}. No other text."""


def qa_user_prompt(article, actor_name, value_name):
    content = article["content"]
    if len(content) > 12000:
        content = content[:6000] + "\n...[truncated]...\n" + content[-3000:]
    return (f"Title: {article['title']}\n\nArticle:\n{content}\n\n"
            f"Actor: {actor_name}\n"
            f"Human value: {value_name}\n\n"
            f'Does this actor\'s behavior align with or contradict this value? '
            f'Return ONLY the JSON object.')


def qa_call(client, article, actor_name, value_name, tag):
    for attempt in range(MAX_RETRIES):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": QA_SYSTEM},
                          {"role": "user",
                           "content": qa_user_prompt(article, actor_name,
                                                     value_name)}],
                temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"}, timeout=TIMEOUT)
            content = r.choices[0].message.content.strip()
            d = json.loads(content).get("direction")
            if d not in ("aligned", "contradictory"):
                raise ValueError(f"bad direction {d!r}")
            return "1" if d == "aligned" else "0", None
        except Exception as e:  # noqa: BLE001 — retried, then recorded
            print(f"  [WARN] {tag}: QA attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(3)
    return None, "qa_failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_run", type=Path, required=True)
    ap.add_argument("--out_dir", type=Path, required=True)
    ap.add_argument("--articles", type=Path, default=ARTICLES,
                    help="articles file matching the fused run "
                         "(default: dev; pass the test file for test runs)")
    args = ap.parse_args()

    out = args.out_dir
    if out.exists():
        # resume is allowed only from the QA cache; a completed run
        # (pred files present) is never overwritten
        extra = [p.name for p in out.iterdir()
                 if p.name != "dir_qa_cache.json"]
        if extra:
            raise FusionError(f"out_dir {out} already holds {extra} — "
                              f"refusing to overwrite a completed run")
    out.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("ERROR: DEEPSEEK_API_KEY not set")
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    guids, actors = load_articles(args.articles)
    art_by_guid = {a["guid"]: a
                   for a in json.loads(args.articles.read_text())}
    fused = load_task1b(args.in_run / "pred_task1b.json")
    ann = [json.loads(l)
           for l in open(args.in_run / "annotations.jsonl")]
    l1_names = json.loads(
        (HV_DIR / "human_value_level1_values.json").read_text())
    id_to_name = {v: k for k, v in l1_names.items()}

    # flag cells
    flagged = []
    for a in ann:
        if a["jury_opposite_direction"] < 1:
            continue
        key = (a["guid"], a["actor_id"])
        lab = a["label"]
        d, val = split_label(lab)
        opp = f"{'0' if d == '1' else '1'}:{val}"
        if lab not in fused.get(key, set()):
            continue  # annotation of a cell not in this run's output
        if opp in fused.get(key, set()):
            continue  # both directions present -> legitimate, skip
        flagged.append((key, lab))
    print(f"{len(flagged)} flagged cells "
          f"(of {sum(len(v) for v in fused.values())} fused labels)")

    cache_path = out / "dir_qa_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    decisions = []
    n_flip = n_keep = n_fail = 0
    for (key, lab) in flagged:
        guid, actor_id = key
        d, val = split_label(lab)
        ckey = f"{guid}|{actor_id}|{val}"
        if ckey in cache:
            qa_dir, err = cache[ckey], None
            if qa_dir == "FAILED":
                qa_dir, err = None, "qa_failed"
        else:
            actor_name = actors.get(key)
            if actor_name is None:
                raise FusionError(f"actor {key} not in articles")
            qa_dir, err = qa_call(client, art_by_guid[guid], actor_name,
                                  id_to_name[val], ckey)
            cache[ckey] = qa_dir if qa_dir else "FAILED"
            cache_path.write_text(json.dumps(cache))
        if err:
            n_fail += 1
            decisions.append({"guid": guid, "actor_id": actor_id,
                              "label": lab, "qa": None, "action": "keep",
                              "reason": "qa_failed"})
            continue
        if qa_dir != d:
            fused[key].discard(lab)
            fused[key].add(f"{qa_dir}:{val}")
            n_flip += 1
            decisions.append({"guid": guid, "actor_id": actor_id,
                              "label": lab, "qa": qa_dir, "action": "flip"})
        else:
            n_keep += 1
            decisions.append({"guid": guid, "actor_id": actor_id,
                              "label": lab, "qa": qa_dir, "action": "keep"})

    l1_to_l2 = load_l1_to_l2(HV_DIR)
    fused = {k: v for k, v in fused.items() if v}
    write_pred_files(out, guids, fused, project_1a(fused, l1_to_l2))
    with open(out / "dir_qa_decisions.jsonl", "w") as f:
        for dcn in decisions:
            f.write(json.dumps(dcn) + "\n")
    (out / "fusion_manifest.json").write_text(json.dumps({
        "experiment": "E7_calibrated_jury_fusion",
        "cell": "G4_dirqa",
        "based_on": str(args.in_run),
        "based_on_pred_sha256": sha256_file(args.in_run / "pred_task1b.json"),
        "qa_model": MODEL, "temperature": TEMPERATURE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counts": {"flagged": len(flagged), "flipped": n_flip,
                   "kept": n_keep, "qa_failed": n_fail},
    }, indent=2))
    print(f"[done] flagged {len(flagged)}  flipped {n_flip}  kept {n_keep}  "
          f"failed {n_fail} -> {out}")


if __name__ == "__main__":
    main()
