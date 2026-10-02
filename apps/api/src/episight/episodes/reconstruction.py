"""Episode reconstruction (M3): which of the patient's episodes belong to the case's clinical story.

- ANCHOR: the screening group (episodes that satisfied the rule).
- RELATED: other episodes of the same patient within the window that share the primary diagnosis or its
  ICD-10 category (any provider or encounter type). They widen the evidence scope.
- CONTEXT: remaining episodes of the patient inside the window, shown for orientation only.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from episight.contracts.data import Episode
from episight.contracts.enums import EpisodeRole

WINDOW = timedelta(days=90)

# ICD-10 categories treated as chronic-class diagnoses (informs, never resolves, chronic context).
CHRONIC_ICD10_CATEGORIES = frozenset(
    {"I10", "I11", "I25", "I50", "E10", "E11", "J44", "J45", "N18", "B20", "F20", "G40", "K74"}
)


def icd10_category(code: str) -> str:
    return code.split(".", 1)[0].upper()


def is_chronic_class(code: str) -> bool:
    return icd10_category(code) in CHRONIC_ICD10_CATEGORIES


def _end_or_start(ep: Episode):
    return ep.end_at or ep.start_at


@dataclass
class Reconstruction:
    anchor_ids: list[str]
    related_ids: list[str]
    context_ids: list[str]
    roles: dict[str, EpisodeRole]
    reasons: dict[str, list[str]] = field(default_factory=dict)

    @property
    def related_scope_ids(self) -> list[str]:
        """Anchors plus related episodes, chronological."""
        return self.ordered([*self.anchor_ids, *self.related_ids])

    ordered_ids: list[str] = field(default_factory=list)

    def ordered(self, ids: Iterable[str]) -> list[str]:
        wanted = set(ids)
        return [i for i in self.ordered_ids if i in wanted]


def reconstruct(group_ids: Sequence[str], patient_episodes: Iterable[Episode], threshold_days: int) -> Reconstruction:
    episodes = [e for e in patient_episodes if e.start_at is not None]
    by_id = {e.episode_id: e for e in episodes}
    group = sorted((by_id[i] for i in group_ids if i in by_id), key=lambda e: (e.start_at, e.episode_id))
    group_set = {e.episode_id for e in group}
    index = group[0]
    window_start = index.start_at - WINDOW
    window_end = max(_end_or_start(e) for e in group) + WINDOW

    roles: dict[str, EpisodeRole] = {}
    reasons: dict[str, list[str]] = {}
    previous_anchor: Episode | None = None
    for ep in group:
        roles[ep.episode_id] = EpisodeRole.ANCHOR
        if previous_anchor is None:
            reasons[ep.episode_id] = ["INDEX_EPISODE"]
        else:
            reasons[ep.episode_id] = [
                "SAME_PATIENT",
                "SAME_PROVIDER",
                "SAME_PRIMARY_DIAGNOSIS",
                f"WITHIN_{threshold_days}_DAYS",
            ]
        previous_anchor = ep

    for ep in episodes:
        if ep.episode_id in group_set or not (window_start <= ep.start_at <= window_end):
            continue
        why = ["SAME_PATIENT"]
        if ep.primary_diagnosis == index.primary_diagnosis:
            why.append("SAME_PRIMARY_DIAGNOSIS")
        elif icd10_category(ep.primary_diagnosis) == icd10_category(index.primary_diagnosis):
            why.append("SAME_DIAGNOSIS_CATEGORY")
        if ep.provider_id == index.provider_id:
            why.append("SAME_PROVIDER")
        related = "SAME_PRIMARY_DIAGNOSIS" in why or "SAME_DIAGNOSIS_CATEGORY" in why
        roles[ep.episode_id] = EpisodeRole.RELATED if related else EpisodeRole.CONTEXT
        reasons[ep.episode_id] = [*why, "WITHIN_90_DAYS"]

    ordered = sorted(roles, key=lambda i: (by_id[i].start_at, i))
    return Reconstruction(
        anchor_ids=[e.episode_id for e in group],
        related_ids=[i for i in ordered if roles[i] == EpisodeRole.RELATED],
        context_ids=[i for i in ordered if roles[i] == EpisodeRole.CONTEXT],
        roles=roles,
        reasons=reasons,
        ordered_ids=ordered,
    )
