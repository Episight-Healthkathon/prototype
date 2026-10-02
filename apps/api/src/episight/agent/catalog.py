"""Requirement catalog and dependency graph (architecture §7.1). Versioned, deterministic configuration."""

from dataclasses import dataclass
from enum import StrEnum

from episight.contracts.enums import RequirementDirection, RequirementKey, SignalType, ToolName
from episight.retrieval.context import ContextType

CATALOG_VERSION = "catalog-1"


class Scope(StrEnum):
    NONE = "NONE"  # structural requirement, not resolved by reading notes
    GROUP = "GROUP"  # notes of every anchor episode
    LATER = "LATER"  # notes of anchor episodes after the index episode (the repeated care)
    RELATED = "RELATED"  # notes of anchors + related episodes


@dataclass(frozen=True)
class RequirementSpec:
    key: RequirementKey
    label: str
    direction: RequirementDirection
    material: bool
    tools: tuple[ToolName, ...]
    scope: Scope = Scope.NONE
    context_type: ContextType | None = None
    prerequisites: tuple[RequirementKey, ...] = ()
    signal_types: tuple[SignalType, ...] = (SignalType.READMISSION, SignalType.FRAGMENTATION)
    spawned: bool = False

    @property
    def is_explaining_context(self) -> bool:
        """Context requirements whose FOUND state can explain the signal (spawned checks excluded)."""
        return self.direction == RequirementDirection.CONTEXT and not self.spawned


K = RequirementKey
_NOTE_PREREQS = (K.EPISODE_RELATEDNESS, K.CLINICAL_DOCUMENT_AVAILABILITY)

SPECS: dict[RequirementKey, RequirementSpec] = {
    s.key: s
    for s in [
        RequirementSpec(
            K.EPISODE_RELATEDNESS,
            "Are the episodes actually related?",
            RequirementDirection.RISK,
            True,
            (ToolName.GET_EPISODE_HISTORY,),
        ),
        RequirementSpec(
            K.DIAGNOSIS_CONSISTENCY,
            "Are the diagnoses consistent across episodes?",
            RequirementDirection.RISK,
            True,
            (ToolName.COMPARE_DIAGNOSIS,),
        ),
        RequirementSpec(
            K.PROCEDURE_RELATIONSHIP,
            "Are procedures repeated or related across episodes?",
            RequirementDirection.RISK,
            True,
            (ToolName.COMPARE_PROCEDURES,),
        ),
        RequirementSpec(
            K.PROVIDER_CONTEXT,
            "Does provider context (class, referral) matter?",
            RequirementDirection.BACKGROUND,
            False,
            (ToolName.GET_PROVIDER_CONTEXT,),
        ),
        RequirementSpec(
            K.CLINICAL_DOCUMENT_AVAILABILITY,
            "Which clinical documents are available?",
            RequirementDirection.BACKGROUND,
            True,
            (ToolName.RETRIEVE_CLINICAL_EVIDENCE,),
            prerequisites=(K.EPISODE_RELATEDNESS,),
        ),
        RequirementSpec(
            K.EMERGENCY_CONTEXT,
            "Is there documented emergency context for the repeated care?",
            RequirementDirection.CONTEXT,
            True,
            (ToolName.FIND_EXCEPTION_EVIDENCE,),
            Scope.LATER,
            ContextType.EMERGENCY,
            _NOTE_PREREQS,
        ),
        RequirementSpec(
            K.CHRONIC_CONDITION_CONTEXT,
            "Is a relevant chronic condition documented?",
            RequirementDirection.CONTEXT,
            True,
            (ToolName.FIND_EXCEPTION_EVIDENCE,),
            Scope.RELATED,
            ContextType.CHRONIC,
            _NOTE_PREREQS,
        ),
        RequirementSpec(
            K.SCHEDULED_PROCEDURE_CONTEXT,
            "Is a scheduled or staged procedure documented?",
            RequirementDirection.CONTEXT,
            True,
            (ToolName.FIND_EXCEPTION_EVIDENCE,),
            Scope.GROUP,
            ContextType.SCHEDULED_PROCEDURE,
            _NOTE_PREREQS,
        ),
        RequirementSpec(
            K.SUPPORTING_EXAM_FOLLOWUP_CONTEXT,
            "Was the repeat visit a consultation of supporting-examination results?",
            RequirementDirection.CONTEXT,
            True,
            (ToolName.FIND_EXCEPTION_EVIDENCE,),
            Scope.LATER,
            ContextType.SUPPORTING_EXAM_FOLLOWUP,
            _NOTE_PREREQS,
            (SignalType.FRAGMENTATION,),
        ),
        RequirementSpec(
            K.CLINICAL_JUSTIFICATION,
            "Is there a documented clinical justification for the repeated care?",
            RequirementDirection.CONTEXT,
            True,
            (ToolName.FIND_EXCEPTION_EVIDENCE,),
            Scope.LATER,
            ContextType.CLINICAL_JUSTIFICATION,
            _NOTE_PREREQS,
        ),
        RequirementSpec(
            K.RISK_INDICATORS_IN_NOTES,
            "Do notes indicate premature discharge, unresolved complaints or repeats without indication?",
            RequirementDirection.RISK,
            True,
            (ToolName.FIND_SUPPORTING_EVIDENCE,),
            Scope.GROUP,
            ContextType.RISK_INDICATOR,
            _NOTE_PREREQS,
        ),
        RequirementSpec(
            K.APPLICABLE_POLICY,
            "Which policy rules apply?",
            RequirementDirection.POLICY,
            True,
            (ToolName.RETRIEVE_POLICY,),
        ),
        RequirementSpec(
            K.SCHEDULE_CONSISTENCY,
            "Does the performed procedure match the documented plan?",
            RequirementDirection.CONTEXT,
            True,
            (ToolName.COMPARE_PROCEDURES,),
            spawned=True,
        ),
    ]
}

CONTEXT_TYPE_TO_KEY = {s.context_type: s.key for s in SPECS.values() if s.context_type}

# Dependency graph: a FOUND parent opens these follow-up checks.
SPAWNS: dict[RequirementKey, tuple[RequirementKey, ...]] = {
    K.SCHEDULED_PROCEDURE_CONTEXT: (K.SCHEDULE_CONSISTENCY,),
}
SPAWNED_BY = {child: parent for parent, children in SPAWNS.items() for child in children}

# Rule-planner priority: structure first, then documents, then context in a signal-specific order.
_CONTEXT_ORDER = {
    SignalType.READMISSION: [
        K.EMERGENCY_CONTEXT,
        K.SCHEDULED_PROCEDURE_CONTEXT,
        K.SCHEDULE_CONSISTENCY,
        K.CHRONIC_CONDITION_CONTEXT,
        K.CLINICAL_JUSTIFICATION,
    ],
    SignalType.FRAGMENTATION: [
        K.SCHEDULED_PROCEDURE_CONTEXT,
        K.SCHEDULE_CONSISTENCY,
        K.SUPPORTING_EXAM_FOLLOWUP_CONTEXT,
        K.CHRONIC_CONDITION_CONTEXT,
        K.EMERGENCY_CONTEXT,
        K.CLINICAL_JUSTIFICATION,
    ],
}


def priority_order(signal_type: SignalType) -> list[RequirementKey]:
    return [
        K.EPISODE_RELATEDNESS,
        K.DIAGNOSIS_CONSISTENCY,
        K.PROCEDURE_RELATIONSHIP,
        K.PROVIDER_CONTEXT,
        K.CLINICAL_DOCUMENT_AVAILABILITY,
        *_CONTEXT_ORDER[signal_type],
        K.RISK_INDICATORS_IN_NOTES,
        K.APPLICABLE_POLICY,
    ]


def initial_requirements(signal_type: SignalType) -> list[RequirementSpec]:
    return [s for s in SPECS.values() if signal_type in s.signal_types and not s.spawned]
