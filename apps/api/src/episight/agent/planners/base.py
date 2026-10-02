from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from episight.agent.context import CaseContext
from episight.agent.envelope.allowed import AllowedAction
from episight.agent.state import InvestigationState
from episight.contracts.enums import PlannerSource, RequirementKey


@dataclass
class Decision:
    """A validated planner choice. `action is None` means: no further useful action (after skips)."""

    action: AllowedAction | None
    tool_input: BaseModel | None
    source: PlannerSource
    skips: list[tuple[RequirementKey, str]] = field(default_factory=list)
    priority_ranking: list[RequirementKey] = field(default_factory=list)
    note: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    model: str | None = None
    prompt_version: str | None = None
    request_hash: str | None = None
    latency_ms: int | None = None


class Planner(Protocol):
    def decide(self, st: InvestigationState, ctx: CaseContext, allowed: list[AllowedAction]) -> Decision: ...
