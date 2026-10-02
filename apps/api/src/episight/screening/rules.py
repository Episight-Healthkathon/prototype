"""Deterministic temporal screening (D-02, D-03).

Produces risk *signals* grouped into connected episode chains. A signal starts an investigation;
nothing here expresses legitimacy or fraud.
"""

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from episight.contracts.data import Episode
from episight.contracts.enums import DiagnosisMatch, EncounterType, SignalType


@dataclass(frozen=True)
class ScreeningRule:
    signal_type: SignalType
    encounter_type: EncounterType
    threshold_days: int
    rule_id: str
    rule_version: str
    description: str
    diagnosis_match: DiagnosisMatch = DiagnosisMatch.EXACT


READMISSION_RULE = ScreeningRule(
    signal_type=SignalType.READMISSION,
    encounter_type=EncounterType.INPATIENT,
    threshold_days=30,
    rule_id="READMISSION_30D_SAME_PROVIDER_SAME_DX",
    rule_version="1",
    description=(
        "Repeated inpatient stay at the same FKRTL with the same primary diagnosis within 30 days of discharge"
    ),
)
FRAGMENTATION_RULE = ScreeningRule(
    signal_type=SignalType.FRAGMENTATION,
    encounter_type=EncounterType.OUTPATIENT,
    threshold_days=7,
    rule_id="FRAGMENTATION_7D_SAME_PROVIDER_SAME_DX",
    rule_version="1",
    description="Repeated outpatient visit at the same FKRTL with the same primary diagnosis within 7 days",
)
RULES = (READMISSION_RULE, FRAGMENTATION_RULE)
RULES_BY_SIGNAL = {r.signal_type: r for r in RULES}


@dataclass(frozen=True)
class QualifyingPair:
    from_episode_id: str
    to_episode_id: str
    interval_days: int


@dataclass
class ScreenedCase:
    case_id: str
    signal_type: SignalType
    patient_id: str
    provider_id: str
    episode_group_ids: list[str]
    primary_pair: QualifyingPair
    pairs: list[QualifyingPair]
    rule: ScreeningRule
    index_date: date
    data_quality_issues: list[str] = field(default_factory=list)

    @property
    def min_interval_days(self) -> int:
        return self.primary_pair.interval_days

    def signal_details(self) -> dict:
        return {
            "rule_id": self.rule.rule_id,
            "rule_version": self.rule.rule_version,
            "params": {
                "threshold_days": self.rule.threshold_days,
                "diagnosis_match": self.rule.diagnosis_match.value,
            },
            "pairs": [
                {
                    "from_episode_id": p.from_episode_id,
                    "to_episode_id": p.to_episode_id,
                    "interval_days": p.interval_days,
                    "matched": {
                        "same_patient": True,
                        "same_provider": True,
                        "same_primary_diagnosis": True,
                        "encounter_type": self.rule.encounter_type.value,
                    },
                }
                for p in self.pairs
            ],
        }


@dataclass
class ScreeningResult:
    cases: list[ScreenedCase]
    data_quality_issues: list[str]


def make_case_id(signal_type: SignalType, episode_ids: Iterable[str]) -> str:
    prefix = "CASE-RA-" if signal_type == SignalType.READMISSION else "CASE-FR-"
    digest = hashlib.sha256((signal_type.value + "|" + ",".join(sorted(episode_ids))).encode()).hexdigest()
    return prefix + digest[:8]


def interval_days(previous: Episode, current: Episode, rule: ScreeningRule) -> int | None:
    """Calendar days between episodes as the rule defines them; None if a timestamp is missing.

    Readmission: admission(current) − discharge(previous). Fragmentation: visit(current) − visit(previous).
    """
    if current.start_at is None:
        return None
    if rule.encounter_type == EncounterType.INPATIENT:
        if previous.end_at is None:
            return None
        anchor = previous.end_at.date()
    else:
        if previous.start_at is None:
            return None
        anchor = previous.start_at.date()
    return (current.start_at.date() - anchor).days


def _normalize(episodes: Iterable[Episode]) -> tuple[list[Episode], list[str], dict[str, str]]:
    """Drop rows that are content-duplicates of another episode and records without a start time.

    Returns the usable episodes, data-quality issues, and a map dropped_id -> kept_id.
    """
    issues: list[str] = []
    kept: list[Episode] = []
    seen: dict[tuple, str] = {}
    duplicate_of: dict[str, str] = {}
    for ep in sorted(episodes, key=lambda e: e.episode_id):
        if ep.start_at is None:
            issues.append(f"MISSING_TIMESTAMP:{ep.episode_id}")
            continue
        key = (ep.patient_id, ep.provider_id, ep.encounter_type, ep.primary_diagnosis, ep.start_at, ep.end_at)
        if key in seen:
            duplicate_of[ep.episode_id] = seen[key]
            issues.append(f"DUPLICATE_EPISODE_ROW:{ep.episode_id}")
            continue
        seen[key] = ep.episode_id
        kept.append(ep)
    return kept, issues, duplicate_of


def _screen_rule(episodes: list[Episode], rule: ScreeningRule, issues: list[str]) -> list[ScreenedCase]:
    groups: dict[tuple, list[Episode]] = defaultdict(list)
    for ep in episodes:
        if ep.encounter_type == rule.encounter_type:
            groups[(ep.patient_id, ep.provider_id, ep.primary_diagnosis)].append(ep)

    cases: list[ScreenedCase] = []
    for (patient_id, provider_id, _dx), group in sorted(groups.items()):
        group.sort(key=lambda e: (e.start_at, e.episode_id))
        chain: list[QualifyingPair] = []
        chains: list[list[QualifyingPair]] = []
        for prev, cur in zip(group, group[1:], strict=False):
            days = interval_days(prev, cur, rule)
            if days is None:
                issues.append(f"MISSING_TIMESTAMP:{prev.episode_id if cur.start_at else cur.episode_id}")
            if days is not None and 0 <= days <= rule.threshold_days:
                chain.append(QualifyingPair(prev.episode_id, cur.episode_id, days))
                continue
            if chain:
                chains.append(chain)
                chain = []
        if chain:
            chains.append(chain)

        by_id = {e.episode_id: e for e in group}
        for pairs in chains:
            ids = [pairs[0].from_episode_id] + [p.to_episode_id for p in pairs]
            primary = min(pairs, key=lambda p: (p.interval_days, by_id[p.from_episode_id].start_at))
            cases.append(
                ScreenedCase(
                    case_id=make_case_id(rule.signal_type, ids),
                    signal_type=rule.signal_type,
                    patient_id=patient_id,
                    provider_id=provider_id,
                    episode_group_ids=sorted(ids),
                    primary_pair=primary,
                    pairs=pairs,
                    rule=rule,
                    index_date=by_id[ids[0]].start_at.date(),
                )
            )
    return cases


def screen(episodes: Iterable[Episode]) -> ScreeningResult:
    usable, issues, duplicate_of = _normalize(episodes)
    cases: list[ScreenedCase] = []
    for rule in RULES:
        cases.extend(_screen_rule(usable, rule, issues))

    issues = sorted(set(issues))
    for case in cases:
        group = set(case.episode_group_ids)
        case.data_quality_issues = [
            i for i in issues if i.split(":", 1)[1] in group or duplicate_of.get(i.split(":", 1)[1]) in group
        ]
    cases.sort(key=lambda c: (c.index_date, c.case_id))
    return ScreeningResult(cases=cases, data_quality_issues=issues)
