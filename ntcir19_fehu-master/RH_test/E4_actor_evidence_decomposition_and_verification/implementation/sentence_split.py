"""Deterministic sentence splitting with exact traceability.

Every sentence is an exact, untouched substring of the original article
content, addressed by (start, end) character offsets and a stable ID
("S1", "S2", ... in document order). No normalization, no rewriting: for
every sentence, content[start:end] == text (verified by verify_split and by
unit tests), so any downstream sentence reference is traceable to the
original article bytes.

Splitting rules (fixed, no configuration):
  1. Newlines are hard boundaries.
  2. Inside a line, a boundary is placed after sentence-final punctuation
     (. ! ? …) plus optional closing quotes/brackets, followed by
     whitespace, when the next character starts a new sentence (uppercase,
     digit, or opening quote/bracket) — unless the token before the period
     is a common abbreviation or a single-letter initial.
  3. Whitespace-only segments are skipped; sentences never overlap and
     appear in strictly increasing offset order.
Over-splitting is acceptable (evidence units may span several sentences);
determinism and traceability are the requirements.
"""

import re

from e4_common import (E1_TRUNC_HEAD, E1_TRUNC_TAIL, E1_TRUNC_THRESHOLD,
                       E4ValidationError)

_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "st", "gen", "gov", "sen", "rep", "prof",
    "jr", "sr", "no", "vs", "etc", "inc", "ltd", "co", "col", "lt",
    "sgt", "capt", "u.s", "u.n", "u.k", "a.m", "p.m",
}

_BOUNDARY = re.compile(
    r'[.!?…]["”\'’)\]]*\s+(?=["“\'‘(\[]?[A-Z0-9])')


def _is_abbreviation(text, punct_pos):
    """True if the '.' at punct_pos ends an abbreviation or initial."""
    if text[punct_pos] != ".":
        return False
    j = punct_pos - 1
    start = j
    while start >= 0 and (text[start].isalnum() or text[start] == "."):
        start -= 1
    token = text[start + 1:punct_pos].lower()
    if not token:
        return False
    if len(token) == 1 and token.isalpha():
        return True  # single-letter initial, e.g. "J."
    return token in _ABBREVIATIONS


def _split_line(text, offset):
    """Split one newline-free segment; yield (start, end) absolute spans."""
    spans = []
    pos = 0
    for match in _BOUNDARY.finditer(text):
        punct_pos = match.start()
        if _is_abbreviation(text, punct_pos):
            continue
        end = punct_pos + 1
        while end < len(text) and text[end] in '"”\'’)]':
            end += 1
        spans.append((pos, end))
        pos = match.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    out = []
    for start, end in spans:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            out.append((offset + start, offset + end))
    return out


def split_sentences(content):
    """Return [{"sid": "S1", "start": int, "end": int, "text": str}, ...]."""
    if not isinstance(content, str):
        raise E4ValidationError("content must be a string")
    spans = []
    line_start = 0
    for i, ch in enumerate(content + "\n"):
        if ch == "\n":
            if i > line_start:
                spans.extend(_split_line(content[line_start:i], line_start))
            line_start = i + 1
    sentences = [
        {"sid": f"S{k + 1}", "start": s, "end": e, "text": content[s:e]}
        for k, (s, e) in enumerate(spans)
    ]
    verify_split(content, sentences)
    return sentences


def verify_split(content, sentences):
    """Hard-verify traceability; raises E4ValidationError on any breach."""
    prev_end = -1
    for sent in sentences:
        s, e, text = sent["start"], sent["end"], sent["text"]
        if not (0 <= s < e <= len(content)):
            raise E4ValidationError(f"{sent['sid']}: bad span ({s},{e})")
        if content[s:e] != text:
            raise E4ValidationError(f"{sent['sid']}: text != content[start:end]")
        if s <= prev_end:
            raise E4ValidationError(f"{sent['sid']}: overlapping/unordered span")
        if text != text.strip():
            raise E4ValidationError(f"{sent['sid']}: not whitespace-trimmed")
        prev_end = e
    covered = bytearray(len(content))
    for sent in sentences:
        for i in range(sent["start"], sent["end"]):
            covered[i] = 1
    for i, ch in enumerate(content):
        if not ch.isspace() and not covered[i]:
            raise E4ValidationError(
                f"non-whitespace char at offset {i} ({ch!r}) not covered by "
                "any sentence")


def visible_sids(content, sentences):
    """Sentence IDs shown in prompts, mirroring E1's long-article truncation.

    E1 shows content[:6000] + content[-3000:] when len(content) > 12000. E4
    stages show exactly the sentences overlapping that same window (IDs stay
    global, so traceability to the full article is preserved); shorter
    articles show every sentence.
    """
    if len(content) <= E1_TRUNC_THRESHOLD:
        return [s["sid"] for s in sentences]
    tail_start = len(content) - E1_TRUNC_TAIL
    return [s["sid"] for s in sentences
            if s["start"] < E1_TRUNC_HEAD or s["end"] > tail_start]


def render_numbered(sentences, visible=None):
    """Render "S1: text" lines; omitted ranges are marked explicitly."""
    visible_set = set(visible) if visible is not None else None
    lines = []
    omitting = False
    for sent in sentences:
        if visible_set is not None and sent["sid"] not in visible_set:
            if not omitting:
                lines.append("...[sentences omitted]...")
                omitting = True
            continue
        omitting = False
        lines.append(f"{sent['sid']}: {sent['text']}")
    return "\n".join(lines)
