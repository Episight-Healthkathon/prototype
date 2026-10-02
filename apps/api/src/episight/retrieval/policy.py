"""Policy retrieval over the curated corpus. Returns stored sections only, never generated policy text."""

from collections.abc import Sequence
from dataclasses import dataclass

from episight.contracts.data import PolicySection
from episight.retrieval.bm25 import BM25
from episight.retrieval.text import tokenize


@dataclass(frozen=True)
class PolicyHit:
    section: PolicySection
    score: float


class PolicyIndex:
    def __init__(self, sections: Sequence[PolicySection], corpus_version: str | None = None):
        self.sections = list(sections)
        self.corpus_version = corpus_version
        self._bm25 = BM25([tokenize(f"{s.document_title} {s.section} {s.text}") for s in self.sections])

    def __len__(self) -> int:
        return len(self.sections)

    def get(self, policy_id: str) -> PolicySection | None:
        return next((s for s in self.sections if s.policy_id == policy_id), None)

    def search(self, query: str, topics: Sequence[str] = (), top_k: int = 2) -> list[PolicyHit]:
        wanted = set(topics)
        hits = self._bm25.search(tokenize(query), top_k=len(self.sections))
        out = []
        for hit in hits:
            section = self.sections[hit.index]
            if wanted and not wanted & set(section.topics):
                continue
            out.append(PolicyHit(section, round(hit.score, 4)))
        return out[:top_k]
