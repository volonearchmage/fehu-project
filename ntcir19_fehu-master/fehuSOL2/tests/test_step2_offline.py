#!/usr/bin/env python3
"""Offline invariants for the SOL2 Step 2 prompt and target filtering."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / "fehuSOL2/scripts/step2_single_actor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sol2_step2_tested", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    step2 = load_module()
    base = step2.load_base_runner()
    article = {
        "guid": "synthetic-guid",
        "title": "Synthetic title",
        "content": "Actor A helped residents. Actor B caused harm.",
        "actors": [{"Actor A": "a"}, {"Actor B": "b"}],
    }
    prompt = step2.build_single_actor_user_prompt(base, article, "Actor A", "a")
    assert "TARGET ACTOR FOR THIS CALL" in prompt
    assert "Actor A (ID: a)" in prompt
    assert 'actor_id "a" exactly' in prompt
    assert "Actor B (ID: b)" in prompt  # other actors remain for attribution context
    assert "for each actor" not in prompt.split("TARGET ACTOR FOR THIS CALL:", 1)[1]

    items = [
        {"actor_id": "a", "l1_value_id": "37", "direction": "aligned"},
        {"actor_id": "b", "l1_value_id": "42", "direction": "contradictory"},
        "malformed",
    ]
    kept, extraneous, malformed = step2.filter_target_items(items, "a")
    assert kept == [items[0]]
    assert extraneous == 1
    assert malformed == 1

    base.l1_name_to_id, base.l2_name_to_id, base.l1_id_to_l2_id = base.load_taxonomy()
    task1a, task1b = base.process_results(article["guid"], article["actors"], kept)
    assert task1b == [{"actor": "a", "l1_value": "37", "direction": "1"}]
    assert len(task1a) == 1 and task1a[0]["actor"] == "a"
    print("Step 2 offline invariants: PASS")


if __name__ == "__main__":
    main()
