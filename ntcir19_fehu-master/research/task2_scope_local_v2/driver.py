"""One finite sequential pilot process; no retries, watchdog or auto-resume."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main(run):
    stages = [(m, [sys.executable, "-m", "research.task2_scope_local_v2.train", "--run", str(run), "--method", m]) for m in ("T", "J", "S")]
    stages.append(("tune_scoring", [sys.executable, "-m", "research.task2_scope_local_v2.score", "--run", str(run)]))
    started = time.time(); records = []
    for name, argv in stages:
        record = dict(stage=name, argv=argv, started_unix=time.time())
        with (run / f"{name}.log").open("x") as log:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            record["pid"] = proc.pid
            with (run / "processes.jsonl").open("a") as f: f.write(json.dumps(record)+"\n")
            record["returncode"] = proc.wait()
        record["elapsed_seconds"] = time.time()-record["started_unix"]
        records.append(record)
        with (run / "stage_completions.jsonl").open("a") as f: f.write(json.dumps(record)+"\n")
        if record["returncode"]:
            (run / "driver_result.json").write_text(json.dumps(dict(completed=False, records=records, elapsed_seconds=time.time()-started),indent=2)+"\n")
            return record["returncode"]
    (run / "driver_result.json").write_text(json.dumps(dict(completed=True, records=records, elapsed_seconds=time.time()-started),indent=2)+"\n")
    return 0


if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--run",type=Path,required=True)
    sys.exit(main(p.parse_args().run.resolve()))
