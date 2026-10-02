"""Read-only data a single investigation may access (its permission scope).

Built by the service layer from the database, or by the batch runner from dataset files. Tools receive
only this object, so the agent cannot reach data outside the case, and it never contains evaluation labels.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from episight.agent.catalog import Scope
from episight.contracts.data import Claim, ClinicalNote, Episode, PolicySection, Provider
from episight.contracts.enums import Availability, EncounterType, NoteType, SignalType
from episight.episodes.reconstruction import Reconstruction, reconstruct
from episight.retrieval.policy import PolicyIndex

EXPECTED_DOCUMENT_PREFIX = "EXPECTED:"


@dataclass(frozen=True)
class SignalPairData:
    from_episode_id: str
    to_episode_id: str
    interval_days: int


@dataclass
class CaseContext:
    case_id: str
    signal_type: SignalType
    patient_id: str
    provider_id: str
    group_ids: list[str]
    pairs: list[SignalPairData]
    rule_id: str
    rule_version: str
    rule_description: str
    threshold_days: int
    diagnosis_match: str
    episodes: dict[str, Episode]
    providers: dict[str, Provider]
    claims: dict[str, Claim]
    notes: dict[str, ClinicalNote]
    policy: PolicyIndex
    dataset_version: str | None = None
    reconstruction: Reconstruction = field(init=False)
    notes_by_episode: dict[str, list[ClinicalNote]] = field(init=False)

    def __post_init__(self) -> None:
        self.signal_type = SignalType(self.signal_type)  # rows from the DB carry plain strings
        self.reconstruction = reconstruct(self.group_ids, self.episodes.values(), self.threshold_days)
        self.group_ids = self.reconstruction.anchor_ids  # chronological
        by_episode: dict[str, list[ClinicalNote]] = defaultdict(list)
        for note in sorted(self.notes.values(), key=lambda n: (n.authored_at, n.note_id)):
            by_episode[note.episode_id].append(note)
        self.notes_by_episode = dict(by_episode)

    # --- scope helpers -----------------------------------------------------------------------

    @property
    def index_episode(self) -> Episode:
        return self.episodes[self.group_ids[0]]

    @property
    def later_ids(self) -> list[str]:
        return self.group_ids[1:]

    def scope_episode_ids(self, scope: Scope, related_known: bool = True) -> list[str]:
        if scope == Scope.GROUP:
            return list(self.group_ids)
        if scope == Scope.LATER:
            return list(self.later_ids)
        if scope == Scope.RELATED:
            return self.reconstruction.related_scope_ids if related_known else list(self.group_ids)
        return []

    def notes_for(self, episode_ids: Iterable[str], note_types: Sequence[NoteType] | None = None) -> list[ClinicalNote]:
        wanted = set(note_types) if note_types else None
        out = []
        for eid in episode_ids:
            for note in self.notes_by_episode.get(eid, []):
                if wanted is None or note.note_type in wanted:
                    out.append(note)
        return out

    def expected_missing_documents(self, episode_ids: Iterable[str]) -> list[str]:
        """D-12: an inpatient episode without a registered discharge summary counts as an unavailable document."""
        missing = []
        for eid in episode_ids:
            ep = self.episodes[eid]
            if ep.encounter_type != EncounterType.INPATIENT:
                continue
            if not any(n.note_type == NoteType.DISCHARGE_SUMMARY for n in self.notes_by_episode.get(eid, [])):
                missing.append(f"{EXPECTED_DOCUMENT_PREFIX}{eid}:DISCHARGE_SUMMARY")
        return missing

    def coverage_sources(self, episode_ids: Iterable[str]) -> tuple[list[str], list[str]]:
        """(available note ids, unavailable source ids) for a set of episodes."""
        episode_ids = list(episode_ids)
        available, unavailable = [], []
        for note in self.notes_for(episode_ids):
            (available if note.availability == Availability.AVAILABLE else unavailable).append(note.note_id)
        unavailable.extend(self.expected_missing_documents(episode_ids))
        return available, unavailable


def policy_index(sections: Sequence[PolicySection], corpus_version: str | None) -> PolicyIndex:
    return PolicyIndex(sections, corpus_version)
