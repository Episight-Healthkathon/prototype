from datetime import UTC, datetime
from functools import cache

from episight.agent.loading import contexts_from_dataset
from episight.agent.orchestrator import run_investigation
from episight.agent.planners.rule_planner import RulePlanner
from episight.contracts.enums import InvestigationMode
from episight.ingest.loader import load_dataset, load_policies
from tests.conftest import DATASET_DIR, POLICY_DIR

FIXED_NOW = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


@cache
def contexts():
    return {c.patient_id: c for c in contexts_from_dataset(load_dataset(DATASET_DIR), load_policies(POLICY_DIR))}


def ctx_for(patient_id):
    return contexts()[patient_id]


def run(patient_id, mode=InvestigationMode.FULL_RULE_PLANNER, planner=None, **kw):
    ctx = ctx_for(patient_id)
    return run_investigation(
        ctx, run_id=f"RUN-TEST-{patient_id}", planner=planner or RulePlanner(), mode=mode, now=lambda: FIXED_NOW, **kw
    )
