"""Episode timeline for a case (API E4): anchors, related episodes and nearby context, chronological."""

from collections.abc import Iterable, Mapping, Sequence

from episight.contracts.api import (
    ClaimRef,
    CodeRef,
    DocumentRef,
    EpisodeTimeline,
    ProcedureRef,
    TimelineEpisode,
    TimelineProvider,
)
from episight.contracts.data import Claim, ClinicalNote, Episode, Provider
from episight.contracts.enums import EncounterType
from episight.episodes.codes import diagnosis_label, procedure_label
from episight.episodes.reconstruction import reconstruct


def _end_or_start(ep: Episode):
    return ep.end_at or ep.start_at


def build_timeline(
    *,
    case_id: str,
    patient_id: str,
    episode_group_ids: Sequence[str],
    threshold_days: int,
    patient_episodes: Iterable[Episode],
    providers: Mapping[str, Provider],
    claims_by_episode: Mapping[str, Claim],
    notes_by_episode: Mapping[str, Sequence[ClinicalNote]],
    evidence_ids_by_episode: Mapping[str, Sequence[str]] | None = None,
) -> EpisodeTimeline:
    episodes = [e for e in patient_episodes if e.start_at is not None]
    by_id = {e.episode_id: e for e in episodes}
    rec = reconstruct(episode_group_ids, episodes, threshold_days)
    evidence_ids_by_episode = evidence_ids_by_episode or {}

    items: list[TimelineEpisode] = []
    previous: Episode | None = None
    for episode_id in rec.ordered_ids:
        ep = by_id[episode_id]
        interval = None
        if previous is not None:
            interval = (ep.start_at.date() - _end_or_start(previous).date()).days
        los = None
        if ep.encounter_type == EncounterType.INPATIENT and ep.end_at is not None:
            los = (ep.end_at.date() - ep.start_at.date()).days

        provider = providers[ep.provider_id]
        claim = claims_by_episode.get(ep.episode_id)
        items.append(
            TimelineEpisode(
                episode_id=ep.episode_id,
                role=rec.roles[episode_id],
                encounter_type=ep.encounter_type,
                admission_type=ep.admission_type,
                provider=TimelineProvider(
                    provider_id=provider.provider_id, name=provider.name, hospital_class=provider.hospital_class
                ),
                start_at=ep.start_at,
                end_at=ep.end_at,
                length_of_stay_days=los,
                interval_from_previous_days=interval,
                primary_diagnosis=CodeRef(code=ep.primary_diagnosis, label=diagnosis_label(ep.primary_diagnosis)),
                secondary_diagnoses=[CodeRef(code=c, label=diagnosis_label(c)) for c in ep.secondary_diagnoses],
                procedures=[
                    ProcedureRef(code=p.code, label=procedure_label(p.code), performed_at=p.performed_at)
                    for p in ep.procedures
                ],
                claim=(
                    ClaimRef(
                        claim_id=claim.claim_id,
                        inacbg_code=claim.inacbg_code,
                        claim_status=claim.claim_status.value if claim.claim_status else None,
                    )
                    if claim
                    else None
                ),
                documents=[
                    DocumentRef(note_id=n.note_id, note_type=n.note_type, title=n.title, availability=n.availability)
                    for n in sorted(notes_by_episode.get(ep.episode_id, []), key=lambda n: (n.authored_at, n.note_id))
                ],
                relation_reasons=list(rec.reasons[episode_id]),
                evidence_ids=list(evidence_ids_by_episode.get(ep.episode_id, [])),
            )
        )
        previous = ep
    return EpisodeTimeline(case_id=case_id, patient_id=patient_id, episodes=items)
