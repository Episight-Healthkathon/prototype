"""Build CaseContexts directly from dataset files (tests, batch runner). No database involved."""

from episight.agent.context import CaseContext, SignalPairData
from episight.ingest.loader import Dataset, PolicyCorpus
from episight.retrieval.policy import PolicyIndex
from episight.screening.rules import ScreenedCase, screen


def context_for(case: ScreenedCase, dataset: Dataset, policy: PolicyIndex) -> CaseContext:
    episodes = {e.episode_id: e for e in dataset.episodes if e.patient_id == case.patient_id}
    notes = {n.note_id: n for n in dataset.notes if n.episode_id in episodes}
    return CaseContext(
        case_id=case.case_id,
        signal_type=case.signal_type,
        patient_id=case.patient_id,
        provider_id=case.provider_id,
        group_ids=list(case.episode_group_ids),
        pairs=[SignalPairData(p.from_episode_id, p.to_episode_id, p.interval_days) for p in case.pairs],
        rule_id=case.rule.rule_id,
        rule_version=case.rule.rule_version,
        rule_description=case.rule.description,
        threshold_days=case.rule.threshold_days,
        diagnosis_match=case.rule.diagnosis_match.value,
        episodes=episodes,
        providers={p.provider_id: p for p in dataset.providers},
        claims={c.episode_id: c for c in dataset.claims if c.episode_id in episodes},
        notes=notes,
        policy=policy,
        dataset_version=dataset.manifest.dataset_version,
    )


def contexts_from_dataset(dataset: Dataset, policies: PolicyCorpus | None) -> list[CaseContext]:
    index = PolicyIndex(policies.sections if policies else [], policies.manifest.corpus_version if policies else None)
    return [context_for(c, dataset, index) for c in screen(dataset.episodes).cases]
