"""Batch runner for evaluation (M8, Data Contract §6).

Runs every screened case of a dataset through the engine, in one or more ablation modes, and writes per mode:
  <out>/<MODE>.json   runner output (header, cases, screening) for Person 3's harness
  <out>/<MODE>.csv    one row per case, for quick inspection
  <out>/summary.md    side-by-side comparison of the modes

The runner never reads evaluation labels: scoring happens in the evaluation harness, outside the backend,
joined on `anchor_episode_ids`. Data comes from files, not the database, so it runs without Docker.
"""

import csv
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from episight.agent.catalog import CATALOG_VERSION
from episight.agent.context import CaseContext
from episight.agent.loading import contexts_from_dataset
from episight.agent.orchestrator import DEFAULT_MAX_STEPS, TOOL_TIMEOUT_S, InvestigationResult, run_investigation
from episight.agent.planners.base import Planner
from episight.agent.planners.rule_planner import RulePlanner
from episight.contracts.enums import EvidenceCategory, InvestigationMode, PlannerSource, RequirementState, ToolStatus
from episight.ingest.loader import load_dataset, load_policies
from episight.llm.config import LlmSettings, Provider, get_llm_settings
from episight.llm.prompt import PROMPT_VERSION
from episight.llm.recording import JsonDirStore
from episight.screening.rules import screen

RUNNER_VERSION = "1"
ALL_MODES = [
    InvestigationMode.RULES_ONLY,
    InvestigationMode.RULES_RETRIEVAL,
    InvestigationMode.FULL_RULE_PLANNER,
    InvestigationMode.FULL,
]

PlannerFactory = Callable[[InvestigationMode, int], Planner]


@dataclass
class PlannerInfo:
    provider: str
    model: str | None
    prompt_version: str | None


def default_planner_factory(
    recordings: Path | None, settings: LlmSettings | None = None
) -> tuple[PlannerFactory, PlannerInfo]:
    """FULL uses the configured AI planner (recordings per repeat), other modes the rule planner."""
    from episight.llm.planner import llm_planner_or_none

    settings = settings or get_llm_settings()
    provider = settings.resolved_provider()
    info = PlannerInfo(
        provider.value,
        settings.resolved_model(provider) if provider != Provider.NONE else None,
        PROMPT_VERSION if provider != Provider.NONE else None,
    )

    def factory(mode: InvestigationMode, repeat: int) -> Planner:
        if mode != InvestigationMode.FULL:
            return RulePlanner()
        store = JsonDirStore(recordings / f"rep-{repeat}") if recordings else None
        return llm_planner_or_none(store=store, settings=settings) or RulePlanner(source=PlannerSource.RULE_FALLBACK)

    return factory, info


def _code_version() -> str | None:
    from episight.services.investigations import code_version

    return code_version()


def case_output(ctx: CaseContext, result: InvestigationResult, repeat: int) -> dict[str, Any]:
    st = result.state
    sources = [a.planner.source for a in st.trail]
    material = [
        s
        for s in result.brief.case_summary
        + result.brief.supporting_risk_evidence
        + result.brief.explaining_context_evidence
        + result.brief.uncertainty
        + result.brief.suggested_next_review
        if s.material
    ]
    return {
        "case_id": ctx.case_id,
        "run_index": repeat,
        "signal_type": ctx.signal_type.value,
        "anchor_episode_ids": sorted(ctx.group_ids),
        "reconstructed_episode_ids": sorted(ctx.reconstruction.related_scope_ids),
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "source_type": e.source_type.value,
                "source_id": e.source_id,
                "requirement_key": e.requirement_key.value,
                "stance": e.stance.value,
                "relevance_category": e.relevance_category.value,
            }
            for e in sorted(st.evidence.values(), key=lambda e: (e.investigation_step, e.evidence_id))
        ],
        "requirement_states": {k.value: r.state.value for k, r in st.requirements.items()},
        "outcome": st.outcome.value if st.outcome else None,
        "stop_reason": st.stop_reason.value if st.stop_reason else None,
        "tool_call_count": len(st.trail),
        "step_count": st.step,
        "tool_failures": sum(a.tool_status in (ToolStatus.ERROR, ToolStatus.TIMEOUT) for a in st.trail),
        "elapsed_ms": result.elapsed_ms,
        "planner": {
            "llm_steps": sources.count(PlannerSource.LLM),
            "llm_retry_steps": sources.count(PlannerSource.LLM_RETRY),
            "fallback_steps": sources.count(PlannerSource.RULE_FALLBACK),
            "rule_steps": sources.count(PlannerSource.RULE),
            "validation_rejections": sum(1 for a in st.trail if a.planner.validation_errors),
            "skipped_requirements": [
                k.value for k, r in st.requirements.items() if r.state == RequirementState.SKIPPED
            ],
        },
        "brief": result.brief.model_dump(mode="json", by_alias=True),
        "brief_traceability": {
            "material_statements": len(material),
            "with_evidence": sum(1 for s in material if s.evidence_ids),
        },
        "brief_validation": {"passed": result.validation.passed, "violations": result.validation.violations},
    }


def run_batch(
    dataset_dir: Path,
    policy_dir: Path | None,
    out_dir: Path,
    modes: list[InvestigationMode],
    *,
    case_ids: list[str] | None = None,
    repeats: int = 1,
    max_steps: int = DEFAULT_MAX_STEPS,
    recordings: Path | None = None,
    planner_factory: PlannerFactory | None = None,
    planner_info: PlannerInfo | None = None,
    progress: Callable[[str], None] = lambda _: None,
) -> dict[str, Path]:
    dataset = load_dataset(dataset_dir)
    policies = load_policies(policy_dir) if policy_dir else None
    contexts = contexts_from_dataset(dataset, policies)
    if case_ids:
        unknown = set(case_ids) - {c.case_id for c in contexts}
        if unknown:
            raise ValueError(f"unknown case id(s): {', '.join(sorted(unknown))}")
        contexts = [c for c in contexts if c.case_id in set(case_ids)]
    if planner_factory is None:
        planner_factory, planner_info = default_planner_factory(recordings)
    planner_info = planner_info or PlannerInfo("custom", None, None)
    screening = {"flagged_anchor_sets": [sorted(c.episode_group_ids) for c in screen(dataset.episodes).cases]}

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    summaries: dict[InvestigationMode, list[dict[str, Any]]] = {}
    for mode in modes:
        started = datetime.now(UTC)
        config = {
            "mode": mode.value,
            "max_steps": max_steps,
            "catalog_version": CATALOG_VERSION,
            "tool_timeout_s": TOOL_TIMEOUT_S,
            "repeats": repeats,
            "planner": planner_info.__dict__ if mode == InvestigationMode.FULL else {"provider": "rule"},
        }
        cases = []
        for repeat in range(repeats if mode == InvestigationMode.FULL else 1):
            for ctx in contexts:
                progress(f"{mode.value} rep {repeat} {ctx.case_id}")
                result = run_investigation(
                    ctx,
                    run_id=f"RUN-BATCH-{mode.value}-{ctx.case_id}-{repeat}",
                    planner=planner_factory(mode, repeat),
                    mode=mode,
                    max_steps=max_steps,
                )
                cases.append(case_output(ctx, result, repeat))
        header = {
            "runner_version": RUNNER_VERSION,
            "mode": mode.value,
            "dataset_version": dataset.manifest.dataset_version,
            "corpus_version": policies.manifest.corpus_version if policies else None,
            "code_version": _code_version(),
            "config": config,
            "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16],
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        path = out_dir / f"{mode.value}.json"
        path.write_text(
            json.dumps({"header": header, "cases": cases, "screening": screening}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written[f"{mode.value}.json"] = path
        written[f"{mode.value}.csv"] = _write_csv(out_dir / f"{mode.value}.csv", cases)
        summaries[mode] = cases
    written["summary.md"] = _write_summary(
        out_dir / "summary.md", summaries, dataset.manifest.dataset_version, planner_info
    )
    return written


_CSV_FIELDS = [
    "case_id",
    "run_index",
    "signal_type",
    "anchor_episode_ids",
    "outcome",
    "stop_reason",
    "step_count",
    "tool_failures",
    "elapsed_ms",
    "evidence_count",
    "supporting_risk",
    "explaining_context",
    "llm_steps",
    "llm_retry_steps",
    "fallback_steps",
    "traceability",
]


def _write_csv(path: Path, cases: list[dict[str, Any]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for c in cases:
            cats = [e["relevance_category"] for e in c["evidence"]]
            t = c["brief_traceability"]
            writer.writerow(
                {
                    "case_id": c["case_id"],
                    "run_index": c["run_index"],
                    "signal_type": c["signal_type"],
                    "anchor_episode_ids": ";".join(c["anchor_episode_ids"]),
                    "outcome": c["outcome"],
                    "stop_reason": c["stop_reason"],
                    "step_count": c["step_count"],
                    "tool_failures": c["tool_failures"],
                    "elapsed_ms": c["elapsed_ms"],
                    "evidence_count": len(cats),
                    "supporting_risk": cats.count(EvidenceCategory.SUPPORTING_RISK.value),
                    "explaining_context": cats.count(EvidenceCategory.EXPLAINING_CONTEXT.value),
                    "llm_steps": c["planner"]["llm_steps"],
                    "llm_retry_steps": c["planner"]["llm_retry_steps"],
                    "fallback_steps": c["planner"]["fallback_steps"],
                    "traceability": f"{t['with_evidence']}/{t['material_statements']}",
                }
            )
    return path


def _write_summary(
    path: Path, summaries: dict[InvestigationMode, list[dict[str, Any]]], dataset_version: str, planner: PlannerInfo
) -> Path:
    modes = list(summaries)
    lines = [
        "# EPISIGHT batch summary",
        "",
        f"Dataset `{dataset_version}` · AI planner: `{planner.provider}` `{planner.model or '-'}` "
        f"(prompt `{planner.prompt_version or '-'}`) · generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        "",
        "Outcomes are evidence situations, not verdicts. Scoring against evaluation labels happens in the evaluation "
        "harness, not here.",
        "",
        "| Case | " + " | ".join(m.value for m in modes) + " |",
        "|---|" + "---|" * len(modes),
    ]
    case_ids = list(dict.fromkeys(c["case_id"] for cases in summaries.values() for c in cases))
    for cid in case_ids:
        cells = []
        for m in modes:
            runs = [c for c in summaries[m] if c["case_id"] == cid]
            outcomes = sorted({c["outcome"] for c in runs})
            steps = "/".join(str(c["step_count"]) for c in runs)
            cells.append(f"{' | '.join(outcomes) if len(outcomes) > 1 else outcomes[0]} ({steps} steps)")
        lines.append(f"| `{cid}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "| Mode | Runs | Avg steps | Avg elapsed (ms) | AI steps | Fallback steps | Brief failures |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in modes:
        cases = summaries[m]
        n = len(cases) or 1
        lines.append(
            f"| {m.value} | {len(cases)} | {sum(c['step_count'] for c in cases) / n:.1f} | "
            f"{sum(c['elapsed_ms'] for c in cases) / n:.0f} | "
            f"{sum(c['planner']['llm_steps'] + c['planner']['llm_retry_steps'] for c in cases)} | "
            f"{sum(c['planner']['fallback_steps'] for c in cases)} | "
            f"{sum(not c['brief_validation']['passed'] for c in cases)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
