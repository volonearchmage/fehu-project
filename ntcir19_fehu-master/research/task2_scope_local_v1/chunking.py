"""Deterministic bag windows with one owner for each original body token."""
from dataclasses import asdict, dataclass
import hashlib
import json

from .tokenization import EncodedBag, render


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Window:
    input_ids: tuple[int, ...]
    source_indices: tuple[int, ...]
    scope_indices: tuple[tuple[int, ...], ...]  # owned body, then full events
    body_start: int
    body_end: int
    owned_start: int

    @property
    def owned_count(self):
        return self.body_end - self.owned_start


@dataclass(frozen=True)
class ChunkedBag:
    key: tuple[str, str]
    event_ids: tuple[str, ...]
    original: EncodedBag
    windows: tuple[Window, ...]

    def as_cache(self):
        return asdict(self)


def from_cache(row):
    original = row["original"]
    enc = EncodedBag(tuple(original["key"]), tuple(original["event_ids"]),
                     tuple(original["input_ids"]), tuple(tuple(s) for s in original["scope_indices"]))
    windows = tuple(Window(tuple(w["input_ids"]), tuple(w["source_indices"]),
                           tuple(tuple(s) for s in w["scope_indices"]),
                           w["body_start"], w["body_end"], w["owned_start"]) for w in row["windows"])
    return ChunkedBag(tuple(row["key"]), tuple(row["event_ids"]), enc, windows)


def make_windows(encoded, *, max_length=8192, overlap=256):
    if not isinstance(max_length, int) or not isinstance(overlap, int) or max_length <= 0 or overlap < 0:
        raise ValueError("Invalid window budget/overlap")
    body = encoded.scope_indices[0]
    if not body or body != tuple(range(body[0], body[-1] + 1)):
        raise ValueError("Body must be one contiguous original token span")
    n = len(body)
    prefix = tuple(range(body[0]))
    suffix = tuple(range(body[-1] + 1, len(encoded.input_ids)))
    capacity = max_length - len(prefix) - len(suffix)
    if capacity <= 0 or (n > capacity and overlap >= capacity):
        raise ValueError("Repeated complete context exceeds safe window budget; refusing truncation")
    if len(encoded.scope_indices) != len(encoded.event_ids) + 1:
        raise ValueError("Event/scope count mismatch")
    windows, start, previous_end = [], 0, 0
    while start < n:
        end = min(start + capacity, n)
        source = prefix + body[start:end] + suffix
        local = {global_idx: i for i, global_idx in enumerate(source)}
        scopes = (tuple(local[i] for i in body[previous_end:end]),) + tuple(
            tuple(local[i] for i in s) for s in encoded.scope_indices[1:])
        windows.append(Window(tuple(encoded.input_ids[i] for i in source), source, scopes, start, end, previous_end))
        previous_end = end
        if end == n:
            break
        start = end - overlap
    plan = ChunkedBag(encoded.key, encoded.event_ids, encoded, tuple(windows))
    validate_windows(plan, max_length=max_length)
    return plan


def validate_windows(plan, *, max_length=8192):
    original = plan.original
    if plan.key != original.key or plan.event_ids != original.event_ids or not plan.windows:
        raise ValueError("Window identity mismatch")
    body = original.scope_indices[0]
    covered, owners = set(), []
    for w in plan.windows:
        if not 0 < len(w.input_ids) <= max_length or len(w.source_indices) != len(w.input_ids):
            raise ValueError("Invalid window length")
        if (len(w.scope_indices) != len(plan.event_ids) + 1 or
                not 0 <= w.body_start <= w.owned_start < w.body_end <= len(body)):
            raise ValueError("Invalid ownership or scope count")
        expected_source = tuple(range(body[0])) + body[w.body_start:w.body_end] + tuple(range(body[-1] + 1, len(original.input_ids)))
        if w.source_indices != expected_source or w.input_ids != tuple(original.input_ids[i] for i in expected_source):
            raise ValueError("Source token order/content changed")
        mapped = tuple(tuple(w.source_indices[i] for i in scope) for scope in w.scope_indices)
        if mapped[0] != body[w.owned_start:w.body_end] or mapped[1:] != original.scope_indices[1:]:
            raise ValueError("Body/event span alignment changed")
        owners.extend(mapped[0])
        covered.update(w.source_indices)
    if tuple(owners) != body or covered != set(range(len(original.input_ids))):
        raise ValueError("Original tokens lost or body counted more than once")
    return dict(original_tokens=len(original.input_ids), body_tokens=len(body),
                windows=len(plan.windows), processed_tokens=sum(len(w.input_ids) for w in plan.windows),
                owned_body_counts=[w.owned_count for w in plan.windows],
                window_tokens=[len(w.input_ids) for w in plan.windows],
                article_supervision_instances=1, event_supervision_instances=len(plan.event_ids))


def token_breakdown(bag, tokenizer, encoded):
    text, spans = render(bag)
    raw = tokenizer.tokenizer.encode(text, add_special_tokens=True)
    if tuple(raw.ids) != encoded.input_ids:
        raise ValueError("Audit tokenization differs")
    body = set(encoded.scope_indices[0])
    events = {i for scope in encoded.scope_indices[1:] for i in scope}
    counts = dict(body=0, event_text=0, event_list_markers=0, actor_article_header=0, model_special=0)
    for i, ((lo, hi), special) in enumerate(zip(raw.offsets, raw.special_tokens_mask)):
        category = ("model_special" if special else "body" if i in body else
                    "event_text" if i in events else "actor_article_header" if hi <= spans[0][0] else "event_list_markers")
        counts[category] += 1
    if sum(counts.values()) != len(raw.ids):
        raise ValueError("Token accounting mismatch")
    return dict(total=len(raw.ids), categories=counts,
                event_text_tokens={e.id: len(s) for e, s in zip(bag.events, encoded.scope_indices[1:])},
                special_tokens=[raw.tokens[i] for i, mask in enumerate(raw.special_tokens_mask) if mask],
                body_characters=len(bag.content), event_characters=sum(len(e.text) for e in bag.events))
