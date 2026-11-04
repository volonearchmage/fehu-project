"""Build and hash input-only window caches; no labels, model or network access."""
import argparse
import datetime
import gzip
import json
from pathlib import Path

from .chunking import canonical, digest, from_cache, make_windows, token_breakdown, validate_windows
from .data import bags, load_articles, load_json, sha256, validate_split
from .prepare import PROJECT, SOURCE, write_json
from .tokenization import BagTokenizer

PACKAGE = Path(__file__).resolve().parent


def read_cache(path, expected_sha256=None):
    if expected_sha256 and sha256(path) != expected_sha256:
        raise ValueError(f"Input cache hash mismatch: {path}")
    result = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            result.append(from_cache(row["plan"]))
    if len({p.key for p in result}) != len(result):
        raise ValueError("Duplicate cached bags")
    return result


def build(out, tokenizer_dir):
    out.mkdir(parents=True, exist_ok=False)
    config = load_json(PACKAGE / "chunking_v1.json")
    lock = load_json(PACKAGE / "tokenizer_lock.json")
    original_protocol = load_json(PACKAGE / "protocol.json")
    files = {s: PROJECT / f"dataset/{s}/{s}_event_base.json" for s in ("train", "dev")}
    files["test2"] = PROJECT / "dataset/test/test_subevent_event_base.json"
    manifest_path = SOURCE / "grouped_train_split.json"
    source_hashes = {}
    # Only input JSON and the split are touched. TRAIN/DEV/holdout labels are not
    # consulted, including their historical summary statistics.
    for path in [*files.values(), manifest_path]:
        name = str(path.relative_to(PROJECT))
        source_hashes[name] = sha256(path)
        if source_hashes[name] != original_protocol["source_sha256"][name]:
            raise ValueError(f"Frozen input/split changed: {name}")
    articles = {name: load_articles(path) for name, path in files.items()}
    parts = validate_split(articles.pop("train"), load_json(manifest_path)) | articles
    tokenizer = BagTokenizer(tokenizer_dir, lock)
    report = dict(schema=config["schema"], time=datetime.datetime.now().astimezone().isoformat(),
                  source_sha256=source_hashes, config_sha256=sha256(PACKAGE / "chunking_v1.json"),
                  tokenizer_lock_sha256=sha256(PACKAGE / "tokenizer_lock.json"),
                  labels_read=False, model_executed=False, partitions={}, overlength=[],
                  implementation_sha256={n: sha256(PACKAGE / n) for n in ("chunking.py", "tokenization.py", "data.py")})
    for part, records in parts.items():
        path = out / f"{part}.chunks.jsonl.gz"
        counts = dict(articles=len(records), bags=0, candidates=0, windows=0, max_window_tokens=0, original_tokens=0, processed_tokens=0)
        audit = []
        # mtime=0 and empty filename give reproducible compressed cache bytes.
        with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
            for bag in bags(records):
                encoded = tokenizer.encode(bag, audit_overlength=True)
                plan = make_windows(encoded, max_length=config["max_length"], overlap=config["body_overlap_tokens"])
                checks = validate_windows(plan, max_length=config["max_length"])
                row = dict(input_sha256=digest(bag.as_input()), plan=plan.as_cache())
                zipped.write((canonical(row) + "\n").encode())
                audit.append(dict(guid=bag.guid, actor_id=bag.actor_id, input_sha256=row["input_sha256"],
                                  plan_sha256=digest(row["plan"]), **checks))
                counts["bags"] += 1
                counts["candidates"] += len(bag.events)
                counts["windows"] += len(plan.windows)
                counts["max_window_tokens"] = max(counts["max_window_tokens"], *checks["window_tokens"])
                counts["original_tokens"] += checks["original_tokens"]
                counts["processed_tokens"] += checks["processed_tokens"]
                if len(plan.windows) > 1:
                    report["overlength"].append(dict(partition=part, guid=bag.guid, actor_id=bag.actor_id,
                        actor_name=bag.actor_name, token_accounting=token_breakdown(bag, tokenizer, encoded),
                        window_layout=[dict(body_start=w.body_start, body_end=w.body_end, owned_start=w.owned_start,
                                      tokens=len(w.input_ids), owned_tokens=w.owned_count,
                                      aggregate_weight=w.owned_count / len(encoded.scope_indices[0])) for w in plan.windows],
                        event_ids=plan.event_ids, **checks))
        write_json(out / f"{part}.coverage.json", audit)
        report["partitions"][part] = dict(**counts, cache=path.name, sha256=sha256(path),
                                            coverage_sha256=sha256(out / f"{part}.coverage.json"))
    write_json(out / "chunking_v1.json", config)
    report["source_unchanged"] = all(sha256(PROJECT / n) == h for n, h in source_hashes.items())
    report["status"] = "All input bags covered; window budget and unique body ownership verified; GPU untested"
    write_json(out / "manifest.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.out, args.tokenizer_dir)
