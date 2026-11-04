"""Audit and export clean bags/supervision, without model loading or training."""
import argparse
import datetime
import importlib.metadata
import json
import sys
from pathlib import Path

from .data import bags, load_articles, load_json, load_supervision, normalize, sha256, taxonomy, validate_split
from .tokenization import BagTokenizer

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "docs/2026-11-03_Task2_组会准备/evidence"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_jsonl(path, rows):
    with path.open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def prepare(out: Path, tokenizer_dir: Path):
    out.mkdir(parents=True, exist_ok=False)
    protocol_path = Path(__file__).with_name("protocol.json")
    protocol = load_json(protocol_path)
    for name, expected in protocol["source_sha256"].items():
        if sha256(PROJECT / name) != expected:
            raise ValueError(f"Pinned data/taxonomy/split hash mismatch: {name}")
    paths = {s: PROJECT / f"dataset/{s}/{s}_event_base.json" for s in ("train", "dev")}
    paths["test2"] = PROJECT / "dataset/test/test_subevent_event_base.json"
    gold_path = PROJECT / "dataset/gold_labels/train/train_human_values.json"
    historic = load_json(SOURCE / "scope_supervision_audit.json")
    checked = [*paths.values(), gold_path]
    hashes = {str(p.relative_to(PROJECT)): sha256(p) for p in checked}
    for name, actual in hashes.items():
        if actual != historic["file_sha256"][name]:
            raise ValueError(f"Official source bytes changed: {name}")
    inputs = {s: load_articles(p) for s, p in paths.items()}
    manifest_path = SOURCE / "grouped_train_split.json"
    partitions = validate_split(inputs["train"], load_json(manifest_path))
    mapping = taxonomy(PROJECT / "dataset/hv_categories")
    supervision, gold_stats = load_supervision(gold_path, inputs["train"], mapping)
    if gold_stats["containment_violations"]:
        raise ValueError("Child/article gold containment violated")
    lock = load_json(Path(__file__).with_name("tokenizer_lock.json"))
    tokenizer = BagTokenizer(tokenizer_dir, lock)
    summary = dict(status="CPU preparation only; no model weights loaded, training or evaluation",
                   time=datetime.datetime.now().astimezone().isoformat(), source_sha256=hashes,
                   split_sha256=sha256(manifest_path), tokenizer=lock,
                   protocol_sha256=sha256(protocol_path), pinned_source_sha256=protocol["source_sha256"],
                   python=sys.executable, python_version=sys.version,
                   versions={n: importlib.metadata.version(n) for n in ("torch", "tokenizers", "transformers", "numpy")},
                   train_gold_audit=gold_stats, partitions={}, overlength=[], gpu_experiment=False)
    all_parts = {**partitions, "dev": inputs["dev"], "test2": inputs["test2"]}
    # DEV/holdout/test exports are input-only. TRAIN gold is audited structurally
    # but only fit/tune supervision is exported, with no explanations anywhere.
    for part, articles in all_parts.items():
        part_bags = bags(articles)
        write_jsonl(out / f"{part}.inputs.jsonl", (b.as_input() for b in part_bags))
        if part in {"fit", "tune"}:
            write_jsonl(out / f"{part}.supervision.jsonl", (dict(guid=b.guid, actor_id=b.actor_id, **supervision[b.key]) for b in part_bags))
        lengths, rows = [], []
        for b in part_bags:
            encoded = tokenizer.encode(b, audit_overlength=True)
            length = len(encoded.input_ids)
            lengths.append(length)
            row = dict(guid=b.guid, actor_id=b.actor_id, tokens=length, event_ids=encoded.event_ids,
                       scope_tokens=list(map(len, encoded.scope_indices)), overlength=length > tokenizer.max_length)
            rows.append(row)
            if row["overlength"]:
                summary["overlength"].append(dict(partition=part, **row))
        write_jsonl(out / f"{part}.token_audit.jsonl", rows)
        ordered = sorted(lengths)
        summary["partitions"][part] = dict(articles=len(articles), bags=len(part_bags),
            events=sum(len(a.events) for a in articles), candidates=sum(len(b.events) for b in part_bags),
            tokens_max=max(lengths), tokens_p50=ordered[len(ordered)//2], tokens_p95=ordered[int(len(ordered)*.95)],
            overlength=sum(n > tokenizer.max_length for n in lengths))
    train_bodies = {normalize(a.content) for a in inputs["train"]}
    overlap = [dict(guid=a.guid, overlaps_train=normalize(a.content) in train_bodies) for a in inputs["dev"]]
    write_json(out / "dev_body_overlap.json", overlap)
    summary["dev_overlap"] = dict(overlap=sum(r["overlaps_train"] for r in overlap), nonoverlap=sum(not r["overlaps_train"] for r in overlap))
    summary["length_status"] = "BLOCKED: common chunk policy required before training" if summary["overlength"] else "All bags fit 8192 without truncation"
    summary["artifact_sha256"] = {p.name: sha256(p) for p in sorted(out.iterdir()) if p.is_file()}
    summary["source_unchanged"] = all(sha256(PROJECT / n) == h for n, h in protocol["source_sha256"].items())
    write_json(out / "audit.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "partitions", "dev_overlap", "length_status", "source_unchanged")}, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True, help="New directory; existing paths are refused")
    parser.add_argument("--tokenizer-dir", type=Path, required=True, help="Local pinned tokenizer; no network")
    args = parser.parse_args()
    prepare(args.out, args.tokenizer_dir)
