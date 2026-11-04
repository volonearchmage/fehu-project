#!/usr/bin/env python3
"""Build the E2 pipeline from the completed E1 pipeline (read-only).

Source:  RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py  (frozen — the
         E1 baseline, itself generated from liu_method/run_pipeline.py)
Output:  RH_test/E2_prompt_bias_control/scripts/run_pipeline_e2.py

Method: every E2 delta is a string replacement asserted to match EXACTLY ONCE
in the E1 source; any mismatch aborts without writing. The complete E1→E2
diff is therefore auditable from this file alone. Neither the Liu original
nor any E1 file is modified.

E2 deltas (prompt-instruction changes only — few-shot repairs from E1 are
inherited unchanged):
  B1  Replace the "Common patterns" guideline — which explicitly teaches
      role-prior associations (e.g., "Law enforcement: often aligned with
      'Be just'") — with an anti-role-prior rule: role/identity is context,
      never evidence.
  B2  Insert an "EVIDENCE AND BIAS CONTROL" block (5 concise rules) before
      the OUTPUT FORMAT section: per-actor evidence test; exact-definition
      discrimination between closely related values; no semantic expansion
      to adjacent/generic values; direction judged from actual actions,
      statements, or outcomes (not sympathy, victimhood, or role); harm
      suffered is not evidence of the victim's own values.
  B3  Bookkeeping only: env var E1_RUN_TS -> E2_RUN_TS; run_config
      experiment name and delta list updated. No behavioral change.

Everything else — model, temperature, max tokens, JSON mode, retries,
parser, dedup/format conversion, the targeted_more_shot_balanced variant
text as modified by E1, E1's deterministic few-shot demos with complete
label sets, and the official evaluation path — is byte-identical to E1.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SRC = BASE / "RH_test" / "E1_fewshot_repair" / "scripts" / "run_pipeline_e1.py"
DST = HERE / "run_pipeline_e2.py"

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


# ---- B1: replace the role-prior "Common patterns" guideline ----------------
rep(
    """6. Common patterns:
   - Law enforcement/authorities: often aligned with "Be just"(45), "Be responsible"(42), "Have a safe country"(26)
   - Victims/affected people: often contradicted on "Have good health"(22), "Have a comfortable life"(25)
   - Organizations responding to crises: often aligned with "Be helpful"(37), "Be honest"(38)
   - Rule-breakers/criminals: often contradictory to "Be compliant"(30), "Be responsible"(42)""",
    """6. An actor's profession, office, institution, or group identity is context
   only — never evidence. Do NOT assign a value because actors of that type
   "usually" hold or violate it; every value must be grounded in what THIS
   actor concretely does, says, or causes in THIS article.""",
    "B1-role-prior",
)

# ---- B2: evidence-and-bias-control block before OUTPUT FORMAT --------------
# The bare OUTPUT FORMAT line appears twice in the source (the prompt
# template AND the search argument of build_deepseek_system_prompt's
# .replace()). Anchor on the B1 replacement tail, which is unique to the
# template, so the DeepSeek object-format rewrite keeps matching its own
# pattern untouched. rep() calls apply sequentially, so B1's text is
# already present when this runs.
rep(
    """   actor concretely does, says, or causes in THIS article.

OUTPUT FORMAT: Return ONLY a valid JSON array. Each element must have:""",
    """   actor concretely does, says, or causes in THIS article.

EVIDENCE AND BIAS CONTROL:
1. Evidence test: output a value for an actor only if you can point to a
   specific action, statement, or outcome of THAT actor in the article that
   supports it. If no such concrete evidence exists, omit the value.
2. Closely related values: when similar values both seem to apply (e.g.,
   "Have a safe country"(26) vs "Have a stable society"(27); "Be helpful"(37)
   vs "Be responsible"(42); "Have social recognition"(19) vs "Have a good
   reputation"(20); "Be just"(45) vs "Be responsible"(42)), re-read their
   exact names in the value list and keep only those each supported by its
   own evidence. Never add a value merely because it is semantically close
   to one you already selected.
3. No semantic expansion: do not add adjacent, broader, or generic values to
   "round out" an actor's profile. Each label stands on its own evidence.
4. Direction discipline: decide "aligned" vs "contradictory" from the
   actor's actual actions, statements, and their outcomes as described —
   never from whether the actor is an authority, a victim, sympathetic, or
   "usually good/bad". The same actor may carry both directions for one
   value only when each direction has its own distinct evidence.
5. Suffering harm is not, by itself, evidence about the victim's own values;
   label victims only for what they themselves do or say.

OUTPUT FORMAT: Return ONLY a valid JSON array. Each element must have:""",
    "B2-bias-control",
)

# ---- B3: bookkeeping -------------------------------------------------------
rep(
    'os.environ.get("E1_RUN_TS")',
    'os.environ.get("E2_RUN_TS")',
    "B3-envvar",
)
rep(
    '''        json.dump({"experiment": "E1_fewshot_repair",
                   "base_pipeline": "liu_method/run_pipeline.py (frozen, copied)",''',
    '''        json.dump({"experiment": "E2_prompt_bias_control",
                   "base_pipeline": "RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py (frozen, copied)",''',
    "B3-experiment",
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
                              "E2: B1 role-prior Common-patterns guideline replaced",
                              "E2: B2 EVIDENCE AND BIAS CONTROL block added",
                              "isolation: outputs under RH_test/E2_prompt_bias_control"]},''',
    "B3-deltas",
)

DST.write_text(text, encoding="utf-8")
print(f"wrote {DST} with {n_deltas} asserted deltas")
