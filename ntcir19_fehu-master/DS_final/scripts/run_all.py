#!/usr/bin/env python3
"""
DS_final Master Orchestrator: Run all 4 pipelines + ensemble on test set.

Order (fastest to slowest):
  1. Flash T=0.0 test          (~11 min)
  2. Pro compact_strict test   (~14 min)
  3. Pro baseline test          (~24 min)
  4. Pro targeted_more_shot_balanced test (~76 min)
  5. Ensemble (majority vote + Flash dir fix)  (<1s)

Total: ~125 min, 700 API calls.

Usage:
    python DS_final/scripts/run_all.py
    python DS_final/scripts/run_all.py --skip_completed  # resume from cache
"""

from __future__ import annotations
import subprocess, sys, os, json, time, shutil
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parents[2]  # ntcir19_fehu-master/
PIPELINE = PROJECT / "Mathematical_optimization" / "base" / "run_pipeline_e1_base.py"
ENSEMBLE = PROJECT / "DS_final" / "scripts" / "ensemble.py"
VENV_PYTHON = PROJECT / "venv" / "bin" / "python"
OUTPUT_DIR = PROJECT / "DS_final" / "outputs"
RUNS_DIR = PROJECT / "DS_final" / "runs"
MATH_RUNS_DIR = PROJECT / "Mathematical_optimization" / "runs"
TEST_EVENT_BASE = PROJECT / "dataset" / "test" / "test_article_event_base.json"

STEPS = [
    {
        "name": "flash",
        "model": "deepseek-v4-flash",
        "variant": "baseline",
        "temp": "0.0",
        "est_min": 11,
    },
    {
        "name": "pro_compact",
        "model": "deepseek-v4-pro",
        "variant": "compact_strict",
        "temp": "0.0",
        "est_min": 14,
    },
    {
        "name": "pro_baseline",
        "model": "deepseek-v4-pro",
        "variant": "baseline",
        "temp": "0.0",
        "est_min": 24,
    },
    {
        "name": "pro_targeted",
        "model": "deepseek-v4-pro",
        "variant": "targeted_more_shot_balanced",
        "temp": "0.0",
        "est_min": 76,
    },
]


def find_pred_files(run_dir: Path) -> tuple[str | None, str | None]:
    """Find pred_task1a.json and pred_task1b.json in a run directory tree."""
    pred_1a = run_dir / "pred_task1a.json"
    pred_1b = run_dir / "pred_task1b.json"
    if pred_1a.exists() and pred_1b.exists():
        return str(pred_1a), str(pred_1b)
    return None, None


def validate_prediction_pair(pred_1a: Path, pred_1b: Path) -> None:
    """Fail unless both files cover the complete official test guid set."""
    expected = {
        str(item["guid"])
        for item in json.loads(TEST_EVENT_BASE.read_text(encoding="utf-8"))
    }
    for path in (pred_1a, pred_1b):
        data = json.loads(path.read_text(encoding="utf-8"))
        actual = {str(item["guid"]) for item in data}
        if len(data) != len(actual):
            raise RuntimeError(f"Duplicate article guid in {path}")
        if actual != expected:
            raise RuntimeError(
                f"Incomplete or wrong split in {path}: "
                f"expected {len(expected)} test guids, got {len(actual)}"
            )


def run_step(step: dict, skip_if_exists: bool) -> Path:
    """Run one pipeline step. Returns path to run directory."""
    run_dir = RUNS_DIR / step["name"]

    if skip_if_exists:
        pred_1a, pred_1b = find_pred_files(run_dir)
        if pred_1a and pred_1b:
            validate_prediction_pair(Path(pred_1a), Path(pred_1b))
            print(f"  [{step['name']}] Predictions exist, skipping...")
            return run_dir

    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(VENV_PYTHON), str(PIPELINE),
        "--provider", "deepseek",
        "--model", step["model"],
        "--mode", "test",
        "--temperature", step["temp"],
        "--prompt_variant", step["variant"],
    ]

    print(f"\n{'='*60}")
    print(f"  Step: {step['name']}")
    print(f"  Model: {step['model']} | Variant: {step['variant']} | T={step['temp']}")
    print(f"  Estimated: ~{step['est_min']} min")
    print(f"{'='*60}")

    t0 = time.time()
    # Stable per-step directories make interrupted API runs resumable.
    pipeline_run_dir = MATH_RUNS_DIR / f"ds_final_{step['name']}"
    env = os.environ.copy()
    env["E1_RUN_TS"] = pipeline_run_dir.name
    result = subprocess.run(cmd, cwd=str(PROJECT), capture_output=False, env=env)
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"  ERROR: Pipeline failed with code {result.returncode}")
        sys.exit(1)

    print(f"  Completed in {elapsed/60:.1f} min")

    # Copy from the exact directory assigned to this step.
    pred_1a, pred_1b = find_pred_files(pipeline_run_dir)

    if pred_1a and pred_1b:
        validate_prediction_pair(Path(pred_1a), Path(pred_1b))
        shutil.copy2(pred_1a, run_dir / "pred_task1a.json")
        shutil.copy2(pred_1b, run_dir / "pred_task1b.json")
        shutil.copy2(pipeline_run_dir / "run_config.json", run_dir / "run_config.json")
        print(f"  Predictions copied to {run_dir}")
    else:
        raise RuntimeError(f"Could not find prediction files in {pipeline_run_dir}")

    return run_dir


def main():
    import argparse
    ap = argparse.ArgumentParser(description="DS_final Master Orchestrator")
    ap.add_argument("--skip_completed", action="store_true",
                    help="Skip steps with existing predictions")
    ap.add_argument("--ensemble_only", action="store_true",
                    help="Only run ensemble (skip API calls)")
    args = ap.parse_args()

    print("=" * 60)
    print("DS_final: Full Pipeline Execution")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    run_dirs = {}

    if not args.ensemble_only:
        total_est = sum(s["est_min"] for s in STEPS)
        print(f"\nEstimated total time: ~{total_est} min ({total_est//60}h{total_est%60}m)")
        print(f"Steps: {len(STEPS)} pipeline runs → 1 ensemble")

        for i, step in enumerate(STEPS):
            print(f"\n--- Step {i+1}/{len(STEPS)} ---")
            run_dir = run_step(step, args.skip_completed)
            run_dirs[step["name"]] = run_dir
    else:
        # Load existing run dirs
        for step in STEPS:
            run_dir = RUNS_DIR / step["name"]
            pred_1a, pred_1b = find_pred_files(run_dir)
            if not pred_1b:
                print(f"ERROR: Missing predictions for {step['name']} in {run_dir}")
                sys.exit(1)
            validate_prediction_pair(Path(pred_1a), Path(pred_1b))
            run_dirs[step["name"]] = run_dir
            print(f"  Found {step['name']}: {pred_1b}")

    # ── Ensemble ──
    print(f"\n{'='*60}")
    print("  Step: Ensemble (Majority Vote + Flash Dir Fix)")
    print(f"{'='*60}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(VENV_PYTHON), str(ENSEMBLE),
        "--baseline", str(run_dirs["pro_baseline"] / "pred_task1b.json"),
        "--targeted", str(run_dirs["pro_targeted"] / "pred_task1b.json"),
        "--compact",   str(run_dirs["pro_compact"] / "pred_task1b.json"),
        "--flash",     str(run_dirs["flash"] / "pred_task1b.json"),
        "--event_base", str(TEST_EVENT_BASE),
        "--output_1b", str(OUTPUT_DIR / "pred_task1b.json"),
        "--output_1a", str(OUTPUT_DIR / "pred_task1a.json"),
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT))
    if result.returncode != 0:
        print("ERROR: Ensemble failed")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"DS_final Complete!")
    print(f"Submission files:")
    print(f"  {OUTPUT_DIR / 'pred_task1a.json'}")
    print(f"  {OUTPUT_DIR / 'pred_task1b.json'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
