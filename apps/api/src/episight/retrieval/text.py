"""Indonesian-aware text utilities. Offsets always refer to the original text, so excerpts are literal."""

import re
from dataclasses import dataclass

# Small Indonesian + English stop-word list; medical terms and codes are never removed.
STOPWORDS = frozenset(
    """
    dan atau yang di ke dari pada untuk dengan dalam ini itu adalah sebagai juga tidak ada akan oleh
    karena bila jika maka telah sudah masih saat sejak serta agar para setelah sebelum hari jam
    pasien kondisi the a an of to in on for with and or is was be by at as from
    """.split()
)
# Expansions keep both forms so either spelling matches.
ABBREVIATIONS = {
    "igd": "instalasi gawat darurat",
    "ugd": "unit gawat darurat",
    "ri": "rawat inap",
    "rj": "rawat jalan",
    "pci": "percutaneous coronary intervention",
    "chf": "congestive heart failure",
    "isk": "infeksi saluran kemih",
}

_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"])")


@dataclass(frozen=True)
class Sentence:
    start: int
    end: int
    text: str


def tokenize(text: str, expand: bool = True) -> list[str]:
    tokens = _TOKEN.findall(text.lower())
    out: list[str] = []
    for tok in tokens:
        if tok in STOPWORDS:
            continue
        out.append(tok)
        if expand and tok in ABBREVIATIONS:
            out.extend(t for t in ABBREVIATIONS[tok].split() if t not in STOPWORDS)
    return out


def sentences(text: str) -> list[Sentence]:
    """Split into sentences with character offsets into the original text."""
    out: list[Sentence] = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.start()
        chunk = text[start:end].strip()
        if chunk:
            offset = text.index(chunk, start)
            out.append(Sentence(offset, offset + len(chunk), chunk))
        start = match.end()
    tail = text[start:].strip()
    if tail:
        offset = text.index(tail, start)
        out.append(Sentence(offset, offset + len(tail), tail))
    return out
