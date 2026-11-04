"""One full input for J/S; offset-derived body/event masks, no truncation."""
from dataclasses import dataclass
from pathlib import Path

from .data import load_json, sha256


def render(bag):
    text = f"Target actor ({bag.actor_id}): {bag.actor_name}\nArticle:\n"
    start = len(text)
    text += bag.content
    spans = [(start, len(text))]
    text += "\nSubevents:\n"
    for i, event in enumerate(bag.events, 1):
        text += f"{i}. [id={event.id}] "
        start = len(text)
        text += event.text
        spans.append((start, len(text)))
        text += "\n"
    return text, spans


@dataclass(frozen=True)
class EncodedBag:
    key: tuple[str, str]
    event_ids: tuple[str, ...]
    input_ids: tuple[int, ...]
    scope_indices: tuple[tuple[int, ...], ...]


class BagTokenizer:
    def __init__(self, directory: Path, lock: dict, max_length=8192):
        from tokenizers import Tokenizer
        for name, info in lock["files"].items():
            if sha256(directory / name) != info["sha256"]:
                raise ValueError(f"Tokenizer/config hash mismatch: {name}")
        config = load_json(directory / "config.json")
        if max_length > config["max_position_embeddings"]:
            raise ValueError("Token budget exceeds published model limit")
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.max_length = max_length
        self.pad_id = config["pad_token_id"]

    def encode(self, bag, *, audit_overlength=False):
        text, spans = render(bag)
        enc = self.tokenizer.encode(text, add_special_tokens=True)
        if len(enc.ids) > self.max_length and not audit_overlength:
            raise ValueError(f"{bag.key}: {len(enc.ids)} > {self.max_length}; no truncation permitted")
        scopes = []
        for lo, hi in spans:
            indices = []
            for i, ((start, end), special) in enumerate(zip(enc.offsets, enc.special_tokens_mask)):
                if special or start == end or start >= hi or end <= lo:
                    continue
                # Byte-level tokenizers can include leading whitespace. A crossing
                # token is allowed only when its portion outside the scope is whitespace.
                if text[start:min(end, lo)].strip() or text[max(start, hi):end].strip():
                    raise ValueError("Tokenizer token crosses a scope boundary")
                indices.append(i)
            if not indices:
                raise ValueError(f"{bag.key}: empty body/event token span")
            scopes.append(tuple(indices))
        if len(set(i for scope in scopes for i in scope)) != sum(map(len, scopes)):
            raise ValueError("Overlapping scope masks")
        return EncodedBag(bag.key, tuple(e.id for e in bag.events), tuple(enc.ids), tuple(scopes))


def collate(encoded, pad_id, supervision=None):
    """Labels travel in a separate dictionary; never passed to ScopeModel."""
    import torch
    if not encoded:
        raise ValueError("Empty batch")
    b, length, scopes = len(encoded), max(len(e.input_ids) for e in encoded), max(len(e.scope_indices) for e in encoded)
    ids = torch.full((b, length), pad_id, dtype=torch.long)
    attention = torch.zeros((b, length), dtype=torch.bool)
    masks = torch.zeros((b, scopes, length), dtype=torch.bool)
    children = torch.zeros((b, scopes - 1), dtype=torch.bool)
    for i, e in enumerate(encoded):
        ids[i, :len(e.input_ids)] = torch.tensor(e.input_ids)
        attention[i, :len(e.input_ids)] = True
        children[i, :len(e.event_ids)] = True
        for j, indices in enumerate(e.scope_indices):
            masks[i, j, list(indices)] = True
    batch = dict(input_ids=ids, attention_mask=attention, scope_masks=masks)
    targets = dict(child_mask=children)
    if supervision is not None:
        article = torch.zeros((b, 108))
        events = torch.zeros((b, scopes - 1, 108))
        for i, e in enumerate(encoded):
            gold = supervision[e.key]  # Missing is an error, never an empty prediction.
            if tuple(gold["event_ids"]) != e.event_ids:
                raise ValueError("Supervision event order mismatch")
            article[i, gold["article"]] = 1
            for j, indices in enumerate(gold["children"]):
                events[i, j, indices] = 1
        targets.update(article_targets=article, child_targets=events)
    return batch, targets
