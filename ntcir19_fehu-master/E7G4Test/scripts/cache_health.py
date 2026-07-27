#!/usr/bin/env python3
"""Post-stage cache health for a member pipeline run on test.

pass 1: any empty-list cache entries are PURGED from the cache (so a rerun
        re-fetches exactly those); exit 2 => caller must rerun the stage.
pass 2: if a purged article is STILL empty AND the pass-2 log shows a
        [FAIL] line for it => unrecovered API failure => exit 1 (abort).
        If still empty with no [FAIL] => the model genuinely returned an
        empty prediction twice; print CONFIRMED_EMPTY <name>:<guid> and
        exit 0 (recorded, never silent).
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--articles", type=Path, required=True)
    ap.add_argument("--passno", type=int, required=True, choices=[1, 2])
    args = ap.parse_args()

    guids = [str(a["guid"]) for a in json.loads(args.articles.read_text())]
    cache = json.loads(args.cache.read_text())
    missing = [g for g in guids if g not in cache]
    if missing:
        print(f"[{args.name}] {len(missing)} articles missing from cache "
              f"(first: {missing[:3]}) — stage incomplete")
        sys.exit(1)
    empty = [g for g in guids if not cache[g]]
    if not empty:
        print(f"[{args.name}] cache healthy: {len(guids)} articles, 0 empty")
        sys.exit(0)

    if args.passno == 1:
        for g in empty:
            del cache[g]
        args.cache.write_text(json.dumps(cache, ensure_ascii=False))
        print(f"[{args.name}] purged {len(empty)} empty entries "
              f"({empty[:5]}) — rerun stage to re-fetch")
        sys.exit(2)

    log_text = args.log.read_text(errors="replace")
    failed = [g for g in empty if f"[FAIL] {g}:" in log_text]
    if failed:
        print(f"[{args.name}] ABORT: unrecovered API failures for {failed}")
        sys.exit(1)
    for g in empty:
        print(f"CONFIRMED_EMPTY {args.name}:{g}")
    print(f"[{args.name}] {len(empty)} article(s) confirmed empty by "
          f"model judgment (re-fetched once, no API failure)")
    sys.exit(0)


if __name__ == "__main__":
    main()
