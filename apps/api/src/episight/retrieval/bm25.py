"""Okapi BM25 in pure Python (D-09: in-process retrieval). Deterministic: ties break by document order."""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    index: int
    score: float


class BM25:
    def __init__(self, documents: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = [Counter(d) for d in documents]
        self.lengths = [len(d) for d in documents]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(doc.keys())
        n = len(self.docs)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def score(self, query: Sequence[str], index: int) -> float:
        doc = self.docs[index]
        length_norm = 1 - self.b + self.b * (self.lengths[index] / self.avg_len if self.avg_len else 0)
        total = 0.0
        for term in query:
            tf = doc.get(term, 0)
            if tf:
                total += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * length_norm)
        return total

    def search(self, query: Sequence[str], top_k: int = 5, min_score: float = 0.0) -> list[Hit]:
        hits = [Hit(i, self.score(query, i)) for i in range(len(self.docs))]
        hits = [h for h in hits if h.score > min_score]
        hits.sort(key=lambda h: (-h.score, h.index))
        return hits[:top_k]
