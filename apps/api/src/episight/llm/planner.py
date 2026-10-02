"""AI planner (M6, D-07). Implemented in the next step; until then FULL mode uses the rule fallback."""

from episight.agent.planners.base import Planner


def llm_planner_or_none() -> Planner | None:
    """Return the configured AI planner, or None when no LLM is configured."""
    return None
