"""Offline Person 3 acceptance: challenge cases, label audit, governance and CLI pipeline QA.

Run: uv run --project apps/api python evaluation/run_person3_qa.py --out evaluation/runs/person3-qa
No model calls, database or frontend. The baseline and its labels are read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/api/src"))

from episight.agent.loading import contexts_from_dataset  # noqa: E402
from episight.agent.orchestrator import run_investigation  # noqa: E402
from episight.agent.planners.rule_planner import RulePlanner  # noqa: E402
from episight.batch import case_output  # noqa: E402
from episight.contracts.data import (  # noqa: E402
    FORBIDDEN_FIELD_PREFIXES,
    FORBIDDEN_FIELDS,
)
from episight.contracts.enums import InvestigationMode, SourceType  # noqa: E402
from episight.episodes.timeline import build_timeline  # noqa: E402
from episight.ingest.loader import (  # noqa: E402
    IngestError,
    load_dataset,
    load_policies,
)
from episight.llm.prompt import build_user_payload  # noqa: E402

from data.generator.generate_dataset import PROVIDERS, Builder, ts  # noqa: E402
from evaluation.paraphrase_cases import KNOWN_GAP_STATES, VARIANTS, Variant  # noqa: E402
from evaluation.score import load_jsonl, score_run  # noqa: E402

BASE = ROOT / "data/synthetic/v0.1.0"
POLICY = ROOT / "data/policies/pc-0.1.1"
TRUTH = ROOT / "data/ground-truth/v0.1.0/cases.jsonl"
AMENDED_TRUTH = ROOT / "data/ground-truth/v0.1.0-labels-1/cases.jsonl"
NOW = datetime(2026, 10, 8, tzinfo=UTC)
EXCEPTIONS = {
    "EMERGENCY_CONTEXT",
    "CHRONIC_CONDITION_CONTEXT",
    "SCHEDULED_PROCEDURE_CONTEXT",
    "SUPPORTING_EXAM_FOLLOWUP_CONTEXT",
}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def source_hashes() -> dict[str, str]:
    paths = [
        *BASE.glob("*"),
        *POLICY.glob("*"),
        TRUTH,
        AMENDED_TRUTH,
        *(ROOT / "apps/api/src/episight").rglob("*.py"),
    ]
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()
    }


def forbidden_keys(value) -> list[str]:
    if isinstance(value, dict):
        return [k for k in value if k in FORBIDDEN_FIELDS or k.startswith(FORBIDDEN_FIELD_PREFIXES)] + [
            k for v in value.values() for k in forbidden_keys(v)
        ]
    if isinstance(value, list):
        return [k for v in value for k in forbidden_keys(v)]
    return []


def expected(v: Variant) -> tuple[str, str]:
    if v.state == "UNAVAILABLE":
        return "EVIDENCE_UNAVAILABLE", "REQUIRED_EVIDENCE_UNAVAILABLE"
    if v.state == "CONFLICTING" or (v.key == "SCHEDULED_PROCEDURE_CONTEXT" and v.performed != "36.06"):
        return "EVIDENCE_CONFLICTING", "CONFLICTING_EVIDENCE"
    if v.key == "SCHEDULED_PROCEDURE_CONTEXT" and v.known_gap:
        # Intended correct plan/code reconstruction, rather than the observed limitation.
        return "EVIDENCE_SUFFICIENT", "SUFFICIENT_EVIDENCE"
    if v.state == "FOUND":
        return "EVIDENCE_SUFFICIENT", "SUFFICIENT_EVIDENCE"
    return "HUMAN_REVIEW_REQUIRED", "EVIDENCE_PATHS_EXHAUSTED"


def build_challenge(directory: Path) -> list[dict]:
    b = Builder(20261008)
    truth = []
    for v in VARIANTS:
        pid = b.patient(1970, "F")
        prv = "PRV-0001"
        if v.encounter == "INPATIENT":
            e1 = b.inpatient(pid, prv, date(2026, 1, 1), "08:00", 2, "I25.1")
            procs = (
                [{"code": v.performed, "performed_at": ts(date(2026, 1, 10))}] if v.key.startswith("SCHEDULED") else []
            )
            e2 = b.inpatient(pid, prv, date(2026, 1, 10), "08:00", 2, "I25.1", procs=procs)
            b.discharge(e1, "Kondisi stabil saat pulang.")
            b.discharge(
                e2,
                None if v.availability != "AVAILABLE" else "Kondisi stabil saat pulang.",
                v.availability,
            )
        else:
            e1 = b.outpatient(pid, prv, date(2026, 1, 1), "08:00", "K30")
            e2 = b.outpatient(pid, prv, date(2026, 1, 4), "08:00", "K30")
        ntype = (
            "PROCEDURE_PLAN"
            if v.key.startswith("SCHEDULED")
            else ("OUTPATIENT_VISIT" if v.encounter == "OUTPATIENT" else "PROGRESS")
        )
        note_day = 1 if v.first_only else (4 if v.encounter == "OUTPATIENT" else 10)
        nid = b.note(
            e1 if v.first_only else e2,
            ntype,
            ts(date(2026, 1, note_day)),
            v.text if v.availability == "AVAILABLE" else None,
            "Catatan klinis sintetis",
            v.availability,
        )
        if v.encounter == "OUTPATIENT" and v.first_only:
            b.note(
                e2,
                "OUTPATIENT_VISIT",
                ts(date(2026, 1, 4)),
                "Kondisi stabil saat kunjungan ulang.",
                "Catatan kunjungan ulang sintetis",
            )
        if v.other_text:
            b.note(
                e2,
                ntype,
                ts(date(2026, 1, 10), "09:00"),
                v.other_text,
                "Catatan pemeriksaan sintetis",
            )
        outcome, stop = expected(v)
        states = {v.key: v.state}
        if v.key.startswith("SCHEDULED") and v.state == "FOUND":
            states["SCHEDULE_CONSISTENCY"] = "FOUND" if v.performed == "36.06" else "CONFLICTING"
        truth.append(
            {
                "gt_id": v.id,
                "golden_case": None,
                "scenario_class": v.key,
                "expected_signal_type": "READMISSION" if v.encounter == "INPATIENT" else "FRAGMENTATION",
                "anchor_episode_ids": [e1, e2],
                "expected_related_episode_ids": [e1, e2],
                "expected_evidence": [],
                "expected_exceptions": [v.key] if v.state == "FOUND" and v.key in EXCEPTIONS else [],
                "expected_requirement_states": states,
                "expected_outcome": outcome,
                "expected_stop_reason": stop,
                "notes_for_reviewers": v.known_gap or "Independent context expectation.",
                "challenge_note_id": nid,
            }
        )
    tables = {
        "patients": b.patients,
        "providers": PROVIDERS,
        "episodes": b.episodes,
        "clinical_notes": b.notes,
        "claims": b.claims,
    }
    hashes = {}
    for name, rows in tables.items():
        path = directory / f"{name}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8",
            newline="\n",
        )
        hashes[path.name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(
        directory / "manifest.json",
        {
            "dataset_version": "qa-paraphrase-1",
            "generator_version": "person3-qa-1",
            "contract_version": "data-contract/1",
            "seed": 20261008,
            "synthetic": True,
            "counts": {k: len(v) for k, v in tables.items()},
            "files": hashes,
        },
    )
    return truth


def run_dataset(dataset_dir: Path, truth: list[dict]) -> tuple[dict, list[dict]]:
    dataset, policies = load_dataset(dataset_dir), load_policies(POLICY)
    contexts = contexts_from_dataset(dataset, policies)
    labels = {tuple(sorted(t["anchor_episode_ids"])): t for t in truth if t["expected_signal_type"]}
    cases, audits = [], []
    for ctx in contexts:
        before = json.dumps(
            {
                "episodes": [e.model_dump(mode="json") for e in ctx.episodes.values()],
                "notes": [n.model_dump(mode="json") for n in ctx.notes.values()],
            },
            sort_keys=True,
        )
        result = run_investigation(
            ctx,
            run_id=f"RUN-QA-{ctx.case_id}",
            planner=RulePlanner(),
            mode=InvestigationMode.FULL_RULE_PLANNER,
            now=lambda: NOW,
        )
        output = case_output(ctx, result, 0)
        cases.append(output)
        label = labels[tuple(sorted(ctx.group_ids))]
        timeline = build_timeline(
            case_id=ctx.case_id,
            patient_id=ctx.patient_id,
            episode_group_ids=ctx.group_ids,
            threshold_days=ctx.threshold_days,
            patient_episodes=ctx.episodes.values(),
            providers=ctx.providers,
            claims_by_episode=ctx.claims,
            notes_by_episode=ctx.notes_by_episode,
        )
        literal, policy_metadata = True, True
        for ev in result.state.evidence.values():
            if ev.source_type == SourceType.CLINICAL_NOTE:
                note = ctx.notes[ev.source_id]
                literal &= note.text is not None and note.text[ev.char_start : ev.char_end] == ev.source_excerpt
            if ev.source_type == SourceType.POLICY_SECTION:
                section = ctx.policy.get(ev.source_id)
                literal &= section.text[ev.char_start : ev.char_end] == ev.source_excerpt
                policy_metadata &= ev.policy_version == section.version and bool(
                    section.source_url and section.effective_date
                )
        after = json.dumps(
            {
                "episodes": [e.model_dump(mode="json") for e in ctx.episodes.values()],
                "notes": [n.model_dump(mode="json") for n in ctx.notes.values()],
            },
            sort_keys=True,
        )
        payload = build_user_payload(result.state, ctx, [])
        checks = {
            "brief_valid": result.validation.passed,
            "literal_provenance": bool(literal),
            "policy_metadata": bool(policy_metadata),
            "source_records_unchanged": before == after,
            "prompt_has_no_label_fields": not forbidden_keys(payload),
            "human_review_notice": result.brief.review_status.value == "PENDING_HUMAN_REVIEW"
            and bool(result.brief.human_decision_notice),
            "timeline_covers_expected_episodes": set(label["expected_related_episode_ids"])
            <= {e.episode_id for e in timeline.episodes},
            "signal_matches_label": ctx.signal_type.value == label["expected_signal_type"],
            "material_statements_traceable": output["brief_traceability"]["material_statements"]
            == output["brief_traceability"]["with_evidence"],
            "tool_calls_succeeded": output["tool_failures"] == 0,
            "no_model_calls": output["planner"]["llm_steps"] == output["planner"]["llm_retry_steps"] == 0,
        }
        audits.append(
            {
                "gt_id": label["gt_id"],
                "golden_case": label["golden_case"],
                "case_id": ctx.case_id,
                "checks": checks,
                "outcome": output["outcome"],
                "stop_reason": output["stop_reason"],
                "timeline": timeline.model_dump(mode="json"),
                "evidence": [e.model_dump(mode="json") for e in result.state.evidence.values()],
            }
        )
    return {
        "header": {
            "mode": "FULL_RULE_PLANNER",
            "dataset_version": dataset.manifest.dataset_version,
            "corpus_version": policies.manifest.corpus_version,
            "config": {"repeats": 1},
        },
        "cases": cases,
        "screening": {"flagged_anchor_sets": [c["anchor_episode_ids"] for c in cases]},
    }, audits


def label_audit(truth: list[dict]) -> dict:
    contradictions = []
    for t in truth:
        surfaced = {k for k, s in t["expected_requirement_states"].items() if k in EXCEPTIONS and s == "FOUND"}
        if not surfaced <= set(t["expected_exceptions"]):
            contradictions.append(
                {
                    "gt_id": t["gt_id"],
                    "found_but_not_labelled": sorted(surfaced - set(t["expected_exceptions"])),
                }
            )
    return {
        "definition": "METRICS.md scores surfaced FOUND context, not adjudicated exceptions.",
        "contradictions": contradictions,
        "historical_labels_changed": False,
        "resolution": "v0.1.0-labels-1 adds the surfaced scheduled context to GT-B06. Historical labels and scores are retained.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "evaluation/runs/person3-qa")
    args = ap.parse_args(argv)
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / "evaluation/runs"):
        ap.error("--out must stay inside evaluation/runs; acceptance never overwrites baseline inputs or reports")
    before = source_hashes()
    challenge_truth = build_challenge(out / "dataset")
    write_json(out / "evaluation-only/challenge_expectations.json", challenge_truth)
    baseline_truth = load_jsonl(TRUTH)
    baseline, baseline_audits = run_dataset(BASE, baseline_truth)
    challenge, challenge_audits = run_dataset(out / "dataset", challenge_truth)
    baseline_scores, challenge_scores = (
        score_run(baseline, baseline_truth),
        score_run(challenge, challenge_truth),
    )
    amended_truth = load_jsonl(AMENDED_TRUTH)
    amended_scores = score_run(baseline, amended_truth)
    write_json(out / "baseline.json", baseline)
    write_json(out / "challenge.json", challenge)
    write_json(out / "pipeline_audit.json", baseline_audits + challenge_audits)
    write_json(out / "label_audit.json", label_audit(baseline_truth))
    checks = {
        "source_inputs_unchanged": before == source_hashes(),
        "all_runtime_governance_checks": all(all(a["checks"].values()) for a in baseline_audits + challenge_audits),
        "baseline_golden": all(baseline_scores["aggregate"]["golden"].values()),
        "baseline_outcomes": baseline_scores["aggregate"]["outcome_accuracy"] == 1,
        "baseline_screening": baseline_scores["aggregate"]["screening"]["recall"] == 1,
        "baseline_complete": not baseline_scores["aggregate"]["missing_runs"],
        "baseline_no_false_positives": not baseline_scores["aggregate"]["screening"]["false_positive_sets"],
        "challenge_complete": not challenge_scores["aggregate"]["missing_runs"]
        and len(challenge["cases"]) == len(VARIANTS),
        "no_unsafe_challenge_closures": not challenge_scores["aggregate"]["escalation"]["unsafe_closures"],
        "amended_labels_consistent": not label_audit(amended_truth)["contradictions"],
    }
    corrections = []
    for old, new in zip(baseline_truth, amended_truth, strict=True):
        corrections.extend((old["gt_id"], k) for k in old if old[k] != new.get(k))
    checks["label_amendment_scoped"] = corrections == [("GT-B06", "expected_exceptions")]
    checks["synthetic_patient_ids"] = all(
        p["patient_id"].startswith("PAT-") for p in load_jsonl(BASE / "patients.jsonl")
    )
    checks["no_label_fields_in_source_tables"] = all(
        not forbidden_keys(row) for path in BASE.glob("*.jsonl") for row in load_jsonl(path)
    )
    try:
        load_dataset(TRUTH.parent)
        checks["ingest_refuses_ground_truth"] = False
    except IngestError as exc:
        checks["ingest_refuses_ground_truth"] = "refusing to ingest" in str(exc)
    mismatches = []
    by_label = {tuple(t["anchor_episode_ids"]): t for t in challenge_truth}
    by_id = {v.id: v for v in VARIANTS}
    for c in challenge["cases"]:
        t = by_label[tuple(c["anchor_episode_ids"])]
        bad_states = {
            k: {"expected": v, "actual": c["requirement_states"].get(k)}
            for k, v in t["expected_requirement_states"].items()
            if c["requirement_states"].get(k) != v
        }
        if bad_states or (c["outcome"], c["stop_reason"]) != (
            t["expected_outcome"],
            t["expected_stop_reason"],
        ):
            mismatches.append(
                {
                    "id": t["gt_id"],
                    "actual_outcome": c["outcome"],
                    "actual_stop_reason": c["stop_reason"],
                    "expected_outcome": t["expected_outcome"],
                    "states": bad_states,
                    "known_gap": by_id[t["gt_id"]].known_gap,
                }
            )
    checks["only_documented_challenge_gaps"] = all(
        m["id"] in KNOWN_GAP_STATES
        and m["actual_outcome"] == "HUMAN_REVIEW_REQUIRED"
        and m["actual_stop_reason"] == "EVIDENCE_PATHS_EXHAUSTED"
        and m["states"] == KNOWN_GAP_STATES[m["id"]]
        for m in mismatches
    )
    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "runtime_source_hashes": before,
        "qa_source_hashes": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                ROOT / "evaluation/paraphrase_cases.py",
                ROOT / "evaluation/score.py",
            )
        },
        "runtime_worktree_modified": subprocess.run(
            ["git", "diff", "--quiet", "--", "apps/api/src"], cwd=ROOT, check=False
        ).returncode
        != 0,
        "model_calls": 0,
        "scope": "CLI/domain pipeline, not HTTP/PostgreSQL or frontend E2E",
        "variants": [asdict(v) for v in VARIANTS],
    }
    result = {
        "checks": checks,
        "passed": all(checks.values()),
        "baseline": baseline_scores["aggregate"],
        "challenge": challenge_scores["aggregate"],
        "mismatches": mismatches,
        "amended_label_metrics": amended_scores["aggregate"],
        "label_audit": label_audit(baseline_truth),
        "metadata": metadata,
    }
    # This is a context/outcome challenge, not an evidence-relevance benchmark. Its evidence
    # annotations are intentionally empty; do not publish the scorer's precision as a quality claim.
    for key in (
        "evidence_precision",
        "note_evidence_precision",
        "policy_precision",
        "evidence_coverage",
    ):
        result["challenge"].pop(key, None)
    result["challenge"]["evidence_metric_scope"] = (
        "Not annotated; assessed separately by literal provenance and brief checks."
    )
    write_json(out / "acceptance.json", result)
    print(
        json.dumps(
            {"passed": result["passed"], "checks": checks, "mismatches": mismatches},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
