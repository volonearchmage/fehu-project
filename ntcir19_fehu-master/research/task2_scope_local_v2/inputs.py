"""V2 input-only serialization; IDs remain metadata, never interpolated in text."""
import argparse
import gzip
from pathlib import Path

from research.task2_scope_local_v1.data import bags, load_articles, load_json, sha256, validate_split
from research.task2_scope_local_v1.tokenization import BagTokenizer as V1Tokenizer, EncodedBag
from research.task2_scope_local_v1.chunking import canonical, digest, make_windows, validate_windows
from research.task2_scope_local_v1.prepare import PROJECT, SOURCE, write_json

PACKAGE = Path(__file__).resolve().parent
V1 = PACKAGE.with_name("task2_scope_local_v1")


def render(bag):
    text = f"Target actor: {bag.actor_name}\nArticle:\n"
    start = len(text)
    text += bag.content
    spans = [(start, len(text))]
    text += "\nSubevents:\n"
    for i, event in enumerate(bag.events, 1):
        text += f"{i}. "
        start = len(text)
        text += event.text
        spans.append((start, len(text)))
        text += "\n"
    return text, spans


class BagTokenizer(V1Tokenizer):
    def encode(self, bag, *, audit_overlength=False):
        text, spans = render(bag)
        enc = self.tokenizer.encode(text, add_special_tokens=True)
        if len(enc.ids) > self.max_length and not audit_overlength:
            raise ValueError("Overlength input: no silent truncation")
        scopes = []
        for lo, hi in spans:
            indices = []
            for i, ((start, end), special) in enumerate(zip(enc.offsets, enc.special_tokens_mask)):
                if special or start == end or start >= hi or end <= lo:
                    continue
                if text[start:min(end, lo)].strip() or text[max(start, hi):end].strip():
                    raise ValueError("Token crosses semantic scope boundary")
                indices.append(i)
            if not indices:
                raise ValueError("Empty body/event token span")
            scopes.append(tuple(indices))
        if len(set(i for s in scopes for i in s)) != sum(map(len, scopes)):
            raise ValueError("Overlapping masks")
        return EncodedBag(bag.key, tuple(e.id for e in bag.events), tuple(enc.ids), tuple(scopes))


def build(out, tokenizer_dir):
    out.mkdir(parents=True, exist_ok=False)
    cfg = load_json(PACKAGE / "config.json")
    protocol = load_json(V1 / "protocol.json")
    source_paths = [PROJECT / "dataset/train/train_event_base.json", SOURCE / "grouped_train_split.json"]
    sources = {str(p.relative_to(PROJECT)): sha256(p) for p in source_paths}
    if any(protocol["source_sha256"][n] != h for n, h in sources.items()):
        raise ValueError("Frozen inputs/split changed")
    parts = validate_split(load_articles(source_paths[0]), load_json(source_paths[1]))
    tok = BagTokenizer(tokenizer_dir, load_json(V1 / "tokenizer_lock.json"))
    report = dict(source_sha256=sources, tokenizer_lock_sha256=sha256(V1 / "tokenizer_lock.json"),
        config_sha256=sha256(PACKAGE / "config.json"), input_implementation_sha256=sha256(Path(__file__)),
        labels_read=False, model_executed=False, partitions={}, overlength=[],
        excluded_partitions=["holdout", "dev", "test2"])
    for part in ("fit", "tune"):
        path = out / f"{part}.chunks.jsonl.gz"
        audit = []
        with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as z:
            for b in bags(parts[part]):
                text, spans = render(b)
                enc = tok.encode(b, audit_overlength=True)
                plan = make_windows(enc, max_length=cfg["max_length"], overlap=cfg["body_overlap_tokens"])
                checks = validate_windows(plan)
                row = dict(input_sha256=digest(b.as_input()), rendered_sha256=digest(text), plan=plan.as_cache())
                z.write((canonical(row) + "\n").encode())
                audit.append(dict(guid=b.guid, actor_id=b.actor_id, input_sha256=row["input_sha256"],
                    rendered_sha256=row["rendered_sha256"], plan_sha256=digest(row["plan"]), **checks))
                if len(plan.windows) > 1:
                    raw_enc = tok.tokenizer.encode(text, add_special_tokens=True)
                    body = len(enc.scope_indices[0]); events = sum(len(s) for s in enc.scope_indices[1:])
                    special = sum(raw_enc.special_tokens_mask)
                    header = sum(not s and hi <= spans[0][0] for (_, hi), s in zip(raw_enc.offsets, raw_enc.special_tokens_mask))
                    report["overlength"].append(dict(partition=part, guid=b.guid, actor_id=b.actor_id,
                        actor_name=b.actor_name, event_ids=plan.event_ids, **checks,
                        token_accounting=dict(body=body, event_text=events, model_special=special,
                            actor_article_header=header, event_list_markers=len(enc.input_ids)-body-events-special-header),
                        aggregate_weights=[w.owned_count/body for w in plan.windows]))
        write_json(out / f"{part}.coverage.json", audit)
        report["partitions"][part] = dict(articles=len(parts[part]), bags=len(audit),
            events=sum(len(a.events) for a in parts[part]), candidates=sum(a["event_supervision_instances"] for a in audit),
            windows=sum(a["windows"] for a in audit), max_window_tokens=max(max(a["window_tokens"]) for a in audit),
            max_original_tokens=max(a["original_tokens"] for a in audit), cache=path.name, sha256=sha256(path),
            coverage_sha256=sha256(out / f"{part}.coverage.json"))
    write_json(out / "manifest.json", report)
    print(canonical(report), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tokenizer-dir", type=Path, required=True)
    a = p.parse_args()
    build(a.out, a.tokenizer_dir)
