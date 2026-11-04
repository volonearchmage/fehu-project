#!/usr/bin/env python3
"""Freeze verification for the prior experiments E4 must not touch.

Hashes every source/report file (*.py, *.md, *.txt) of E1, E2, E3, E3a and
the Liu ancestor pipeline — excluding runs/ and logs/ (run artifacts) — and
compares against config/frozen_hashes.json (the snapshot taken when E4 was
built). tests/test_frozen_unchanged.py runs the comparison; this CLI
regenerates the snapshot (ONLY legitimate when a prior experiment changed
for an approved reason):

  python3 freeze_check.py --write
"""

import argparse
import hashlib
import json
import os

from e4_common import CONFIG_DIR, RH_TEST_DIR

_BASE = os.path.dirname(RH_TEST_DIR)

FROZEN_ROOTS = [
    os.path.join(RH_TEST_DIR, "E1_fewshot_repair"),
    os.path.join(RH_TEST_DIR, "E2_prompt_bias_control"),
    os.path.join(RH_TEST_DIR, "E3_subevent_decomposition"),
    os.path.join(RH_TEST_DIR, "E3a_task1_only_subevent"),
    os.path.join(_BASE, "liu_method", "run_pipeline.py"),
]
_EXCLUDE_DIRS = {"runs", "logs", "__pycache__"}
_EXTENSIONS = {".py", ".md", ".txt"}
HASHES_PATH = os.path.join(CONFIG_DIR, "frozen_hashes.json")


def _iter_files(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIRS)
        for name in sorted(filenames):
            if os.path.splitext(name)[1] in _EXTENSIONS:
                yield os.path.join(dirpath, name)


def compute_hashes():
    hashes = {}
    for root in FROZEN_ROOTS:
        for path in _iter_files(root):
            with open(path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            hashes[os.path.relpath(path, _BASE)] = digest
    return hashes


def compare():
    """Return (missing, changed, added) relative to the stored snapshot."""
    with open(HASHES_PATH, "r", encoding="utf-8") as f:
        stored = json.load(f)["hashes"]
    current = compute_hashes()
    missing = sorted(set(stored) - set(current))
    added = sorted(set(current) - set(stored))
    changed = sorted(p for p in stored if p in current
                     and stored[p] != current[p])
    return missing, changed, added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="regenerate config/frozen_hashes.json")
    args = parser.parse_args()
    if args.write:
        payload = {
            "_comment": ("SHA-256 snapshot of frozen E1/E2/E3/E3a/Liu source "
                         "files, taken when E4 was built. "
                         "tests/test_frozen_unchanged.py compares against "
                         "this."),
            "hashes": compute_hashes(),
        }
        with open(HASHES_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        print(f"wrote {HASHES_PATH} ({len(payload['hashes'])} files)")
        return
    missing, changed, added = compare()
    if missing or changed:
        raise SystemExit(f"FROZEN FILES MODIFIED\n  missing: {missing}\n"
                         f"  changed: {changed}")
    print(f"frozen check OK ({len(compute_hashes())} files; "
          f"{len(added)} new files ignored)")


if __name__ == "__main__":
    main()
