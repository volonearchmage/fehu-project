"""Input-only bags, separately parsed supervision, and frozen split validation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

LABELS = 108
SPLIT_SEED = "fehu-task2-scope-20261103"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError(f"{path}: duplicate JSON key {k}")
            result[k] = v
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def nonempty(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty string")
    return value


def normalize(value):
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class Event:
    id: str
    text: str


@dataclass(frozen=True)
class Article:
    guid: str
    title: str
    content: str
    actors: tuple[tuple[str, str], ...]  # (id, name), input order
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Bag:
    guid: str
    actor_id: str
    actor_name: str
    content: str
    events: tuple[Event, ...]

    @property
    def key(self):
        return self.guid, self.actor_id

    def as_input(self):
        # This whitelist is the only model-input serialization. No labels/explanations.
        return asdict(self)


def load_articles(path: Path) -> tuple[Article, ...]:
    result = []
    for row in load_json(path):
        actors = []
        for actor in row["actors"]:
            if not isinstance(actor, dict) or len(actor) != 1:
                raise ValueError("Actor must contain exactly one name/id")
            name, aid = next(iter(actor.items()))
            actors.append((nonempty(aid), nonempty(name)))
        events = tuple(Event(nonempty(e["id"]), nonempty(e["subevent"])) for e in row["subevents"])
        if not actors or not events or len(set(a for a, _ in actors)) != len(actors) or len({e.id for e in events}) != len(events):
            raise ValueError("Missing/duplicate actor or event candidates")
        result.append(Article(nonempty(row["guid"]), nonempty(row["title"]),
                              nonempty(row["content"]), tuple(actors), events))
    if len({a.guid for a in result}) != len(result):
        raise ValueError("Duplicate input GUID")
    return tuple(result)


def bags(articles):
    return tuple(Bag(a.guid, aid, name, a.content, a.events) for a in articles for aid, name in a.actors)


def taxonomy(path: Path) -> dict[str, str]:
    fine = load_json(path / "human_value_level1_values.json")
    coarse = load_json(path / "human_value_level2_values.json")
    mapping = load_json(path / "level_1_to_level_2.json")["level_1_to_level_2"]
    if set(fine.values()) != {str(i) for i in range(54)} or set(coarse.values()) != {str(i) for i in range(20)}:
        raise ValueError("Unexpected taxonomy")
    if set(mapping) != set(fine):
        raise ValueError("Incomplete fine/coarse mapping")
    return {fine[name]: coarse[mapping[name]] for name in fine}


def label_index(fine: str, direction: str) -> int:
    if fine not in {str(i) for i in range(54)} or direction not in {"0", "1"}:
        raise ValueError("Invalid directed value")
    return 2 * int(fine) + int(direction)


def load_supervision(path: Path, articles, mapping):
    """Read TRAIN gold only. Missing addressed rows are empty published label sets.

    Unknown IDs and nonempty unidentified records are errors. Explanations are
    deliberately never retained. This function does not read prediction inputs.
    """
    inputs = {a.guid: a for a in articles}
    output, seen = {}, set()
    stats = dict(unidentified_empty_rows=0, missing_addressed_event_rows=0,
                 article_positives=0, child_positives=0, article_only=0,
                 containment_violations=0, both_direction_pairs=0, positive_candidates=0)
    for row in load_json(path):
        guid = row["guid"]
        if guid not in inputs or guid in seen:
            raise ValueError("Gold GUID missing/duplicated")
        seen.add(guid)
        a = inputs[guid]
        actor_ids = {aid for aid, _ in a.actors}

        def labels(values):
            found = set()
            for v in values:
                aid = v["actor"]
                idx = label_index(v["l1_value"], v["direction"])
                if aid not in actor_ids or v.get("l2_value") != mapping[v["l1_value"]]:
                    raise ValueError("Gold actor/taxonomy mismatch")
                if (aid, idx) in found:
                    raise ValueError("Duplicate directed label")
                found.add((aid, idx))
            return found

        article_values = labels(row["article_human_values"])
        event_values = {}
        for event in row["subevents_human_values"]:
            sid, values = event["subevent_id"], event["subevent_human_values"]
            if sid == "" and values == []:
                stats["unidentified_empty_rows"] += 1
                continue
            if sid in event_values or sid not in {e.id for e in a.events}:
                raise ValueError("Unknown/duplicate gold event")
            event_values[sid] = labels(values)
        stats["missing_addressed_event_rows"] += len(a.events) - len(event_values)
        union = set().union(*event_values.values()) if event_values else set()
        stats["article_positives"] += len(article_values)
        stats["article_only"] += len(article_values - union)
        stats["containment_violations"] += len(union - article_values)
        for aid, _ in a.actors:
            children = [sorted(idx for actor, idx in event_values.get(e.id, set()) if actor == aid) for e in a.events]
            output[(guid, aid)] = dict(article=sorted(idx for actor, idx in article_values if actor == aid),
                                       children=children, event_ids=[e.id for e in a.events])
            stats["child_positives"] += sum(map(len, children))
            stats["positive_candidates"] += sum(bool(v) for v in children)
            stats["both_direction_pairs"] += sum(sum(i % 2 == 0 and i + 1 in ids for i in ids) for ids in children)
    if seen != set(inputs):
        raise ValueError("Gold/input GUID coverage mismatch")
    return output, stats


def source_groups(articles):
    parent = {a.guid: a.guid for a in articles}

    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    owners = {}
    for a in articles:
        for key in (("body", normalize(a.content)), ("title", normalize(a.title))):
            if key in owners:
                parent[find(a.guid)] = find(owners[key])
            owners[key] = a.guid
    components = {}
    for a in articles:
        components.setdefault(find(a.guid), []).append(a.guid)
    return {hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest(): sorted(ids) for ids in components.values()}


def validate_split(articles, manifest):
    groups = source_groups(articles)
    if manifest["seed"] != SPLIT_SEED or groups != manifest["groups"]:
        raise ValueError("Frozen seed/source groups changed")
    ordered = sorted(groups, key=lambda g: hashlib.sha256((SPLIT_SEED + g).encode()).hexdigest())
    lo, hi = int(len(groups) * .8), int(len(groups) * .9)
    group_parts = dict(fit=ordered[:lo], tune=ordered[lo:hi], holdout=ordered[hi:])
    expected = {p: sorted(g for k in ids for g in groups[k]) for p, ids in group_parts.items()}
    if expected != manifest["guids"] or {p: len(v) for p, v in expected.items()} != manifest["record_counts"]:
        raise ValueError("Frozen split membership/coverage changed")
    if {p: len(v) for p, v in group_parts.items()} != manifest["component_counts"]:
        raise ValueError("Frozen group counts changed")
    lookup = {a.guid: a for a in articles}
    for field in ("content", "title"):
        owners = {}
        for part, ids in expected.items():
            for guid in ids:
                key = normalize(getattr(lookup[guid], field))
                if key in owners and owners[key] != part:
                    raise ValueError(f"Cross-split {field} overlap")
                owners[key] = part
    return {p: tuple(lookup[g] for g in ids) for p, ids in expected.items()}
