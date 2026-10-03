"""EPISIGHT scoring harness (Person 3): runner output (Data Contract §6) + hidden ground truth -> metrics.

Usage (repo root):
  python evaluation/score.py --run evaluation/runs/<name> --ground-truth data/ground-truth/v0.1.0/cases.jsonl
  python evaluation/score.py ... --baseline evaluation/reports/<old>/scores.json   # regression diff
  python evaluation/score.py ... --fail-on-golden                                   # exit 1 if a golden case fails

Reads every <MODE>.json in the run directory, writes scores.json, per_case_<MODE>.csv and report.md
next to them (or into --out). Ground truth is read only here; nothing is sent back to the backend.
Metric definitions: evaluation/METRICS.md. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

MODES = ("RULES_ONLY", "RULES_RETRIEVAL", "FULL_RULE_PLANNER", "FULL")
RETRIEVAL_SOURCES = {"CLINICAL_NOTE", "POLICY_SECTION"}
EXCEPTION_KEYS = ("EMERGENCY_CONTEXT", "CHRONIC_CONDITION_CONTEXT", "SCHEDULED_PROCEDURE_CONTEXT",
                  "SUPPORTING_EXAM_FOLLOWUP_CONTEXT")
SUFFICIENT = "EVIDENCE_SUFFICIENT"


def triple(item: dict) -> tuple[str, str, str]:
    return item["source_type"], item["source_id"], item["requirement_key"]


def fmt_triple(t: tuple[str, str, str]) -> str:
    return ":".join(t)


def ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def mean(values) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


# ---- per case --------------------------------------------------------------------------------------------

def score_case(c: dict, gt: dict) -> dict:
    expected_eps, got_eps = set(gt["expected_related_episode_ids"]), set(c["reconstructed_episode_ids"])
    retrieved_all = {triple(e) for e in c["evidence"]}
    retrieved = {t for t in retrieved_all if t[0] in RETRIEVAL_SOURCES}
    relevant = {triple(e) for e in gt["expected_evidence"] if e["category"] != "IRRELEVANT"}
    mandatory = {triple(e) for e in gt["expected_evidence"] if e["mandatory"]}
    notes = {t for t in retrieved if t[0] == "CLINICAL_NOTE"}
    policies = {t for t in retrieved if t[0] == "POLICY_SECTION"}

    states = c["requirement_states"]
    found_exc = sorted(k for k in EXCEPTION_KEYS if states.get(k) == "FOUND")
    exp_exc = set(gt["expected_exceptions"])
    exp_states = gt.get("expected_requirement_states") or {}
    state_hits = [states.get(k) == v for k, v in exp_states.items()]

    outcome_ok = c["outcome"] == gt["expected_outcome"]
    stop_ok = c["stop_reason"] == gt["expected_stop_reason"]
    should_escalate = gt["expected_outcome"] != SUFFICIENT
    trace = c.get("brief_traceability") or {}
    return {
        "gt_id": gt["gt_id"],
        "case_id": c["case_id"],
        "run_index": c.get("run_index", 0),
        "scenario_class": gt["scenario_class"],
        "golden_case": gt.get("golden_case"),
        "episode_recall": ratio(len(expected_eps & got_eps), len(expected_eps)),
        "episode_precision": ratio(len(expected_eps & got_eps), len(got_eps)),
        "evidence_retrieved": len(retrieved),
        "evidence_precision": ratio(len(retrieved & relevant), len(retrieved)),
        "note_evidence_precision": ratio(len(notes & relevant), len(notes)),
        "policy_precision": ratio(len(policies & relevant), len(policies)),
        "evidence_coverage": ratio(len(mandatory & retrieved_all), len(mandatory)),
        "missed_mandatory": sorted(fmt_triple(t) for t in mandatory - retrieved_all),
        "unlabelled_retrieved": sorted(fmt_triple(t) for t in retrieved - relevant),
        "exceptions_expected": sorted(exp_exc),
        "exceptions_found": found_exc,
        "exception_tp": len(exp_exc & set(found_exc)),
        "exception_fp": len(set(found_exc) - exp_exc),
        "exception_fn": len(exp_exc - set(found_exc)),
        "exception_exact": set(found_exc) == exp_exc,
        "outcome": c["outcome"],
        "expected_outcome": gt["expected_outcome"],
        "stop_reason": c["stop_reason"],
        "expected_stop_reason": gt["expected_stop_reason"],
        "outcome_correct": outcome_ok,
        "stop_reason_correct": stop_ok,
        "should_escalate": should_escalate,
        "escalated": c["outcome"] != SUFFICIENT,
        "unsafe_closure": should_escalate and c["outcome"] == SUFFICIENT,
        "state_accuracy": ratio(sum(state_hits), len(state_hits)),
        "state_mismatches": {k: [states.get(k), v] for k, v in exp_states.items() if states.get(k) != v},
        "golden_pass": outcome_ok and stop_ok and all(state_hits),
        "traceability": ratio(trace.get("with_evidence", 0), trace.get("material_statements", 0)),
        "brief_valid": (c.get("brief_validation") or {}).get("passed"),
        "elapsed_ms": c.get("elapsed_ms"),
        "step_count": c.get("step_count"),
        "tool_failures": c.get("tool_failures", 0),
        "planner": c.get("planner") or {},
    }


# ---- per run ---------------------------------------------------------------------------------------------

def score_run(run: dict, ground_truth: list[dict]) -> dict:
    flagged = {tuple(sorted(s)) for s in run["screening"]["flagged_anchor_sets"]}
    by_anchor: dict[tuple, list[dict]] = defaultdict(list)
    for c in run["cases"]:
        by_anchor[tuple(sorted(c["anchor_episode_ids"]))].append(c)

    positives = [g for g in ground_truth if g["expected_signal_type"]]
    negatives = [g for g in ground_truth if not g["expected_signal_type"]]
    pos_keys = {tuple(sorted(g["anchor_episode_ids"])) for g in positives}

    cases: dict[str, list[dict]] = {}
    for g in positives:
        runs = sorted(by_anchor.get(tuple(sorted(g["anchor_episode_ids"])), []), key=lambda c: c.get("run_index", 0))
        cases[g["gt_id"]] = [score_case(c, g) for c in runs]

    rows = [r for rs in cases.values() for r in rs]
    exc = {k: sum(r[f"exception_{k}"] for r in rows) for k in ("tp", "fp", "fn")}
    unstable = sorted(gid for gid, rs in cases.items()
                      if len({(r["outcome"], r["stop_reason"]) for r in rs}) > 1)
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_class[r["scenario_class"]].append(r)

    aggregate = {
        "screening": {
            "recall": ratio(sum(tuple(sorted(g["anchor_episode_ids"])) in flagged for g in positives), len(positives)),
            "missed": sorted(g["gt_id"] for g in positives if tuple(sorted(g["anchor_episode_ids"])) not in flagged),
            "must_not_flag_violations": sorted(
                g["gt_id"] for g in negatives if tuple(sorted(g["anchor_episode_ids"])) in flagged),
            "false_positive_sets": len(flagged - pos_keys),
            "flagged_sets": len(flagged),
        },
        "cases_scored": len(rows),
        "episode_recall": mean(r["episode_recall"] for r in rows),
        "episode_precision": mean(r["episode_precision"] for r in rows),
        "evidence_precision": mean(r["evidence_precision"] for r in rows),
        "note_evidence_precision": mean(r["note_evidence_precision"] for r in rows),
        "policy_precision": mean(r["policy_precision"] for r in rows),
        "evidence_coverage": mean(r["evidence_coverage"] for r in rows),
        "exceptions": {**exc, "precision": ratio(exc["tp"], exc["tp"] + exc["fp"]),
                       "recall": ratio(exc["tp"], exc["tp"] + exc["fn"]),
                       "exact_case_accuracy": mean(float(r["exception_exact"]) for r in rows)},
        "outcome_accuracy": mean(float(r["outcome_correct"]) for r in rows),
        "stop_reason_accuracy": mean(float(r["stop_reason_correct"]) for r in rows),
        "escalation": {
            "accuracy": mean(float(r["escalated"] == r["should_escalate"]) for r in rows),
            "unsafe_closures": sorted({r["gt_id"] for r in rows if r["unsafe_closure"]}),
            "over_escalations": sorted({r["gt_id"] for r in rows if r["escalated"] and not r["should_escalate"]}),
        },
        "state_accuracy": mean(r["state_accuracy"] for r in rows),
        "traceability": mean(r["traceability"] for r in rows),
        "brief_failures": sum(1 for r in rows if r["brief_valid"] is False),
        "tool_failures": sum(r["tool_failures"] for r in rows),
        "avg_steps": mean(r["step_count"] for r in rows),
        "avg_elapsed_ms": mean(r["elapsed_ms"] for r in rows),
        "planner": {k: sum(r["planner"].get(k, 0) for r in rows)
                    for k in ("llm_steps", "llm_retry_steps", "fallback_steps", "rule_steps",
                              "validation_rejections")},
        "golden": {g["golden_case"]: bool(cases[g["gt_id"]]) and all(r["golden_pass"] for r in cases[g["gt_id"]])
                   for g in positives if g.get("golden_case")},
        "variance": {"repeats": max((r["run_index"] for r in rows), default=0) + 1, "unstable_cases": unstable},
        "by_scenario_class": {k: {"runs": len(v), "outcome_accuracy": mean(float(r["outcome_correct"]) for r in v)}
                              for k, v in sorted(by_class.items())},
        "failing_cases": sorted({r["gt_id"] for r in rows if not (r["outcome_correct"] and r["stop_reason_correct"])}
                                | {gid for gid, rs in cases.items() if not rs}),
    }
    return {"header": run.get("header", {}), "aggregate": aggregate, "cases": cases}


# ---- regression ------------------------------------------------------------------------------------------

COMPARED_METRICS = ("episode_recall", "evidence_precision", "evidence_coverage", "outcome_accuracy",
                    "stop_reason_accuracy", "state_accuracy", "traceability", "avg_steps")


def _passing(scored: dict) -> dict[str, bool]:
    return {gid: bool(rs) and all(r["outcome_correct"] and r["stop_reason_correct"] for r in rs)
            for gid, rs in scored["cases"].items()}


def compare(base: dict, new: dict) -> dict:
    b, n = _passing(base), _passing(new)
    delta = {}
    for m in COMPARED_METRICS:
        x, y = base["aggregate"].get(m), new["aggregate"].get(m)
        delta[m] = None if x is None or y is None else y - x
    status = {gid: {"previous": [r["outcome"] for r in base["cases"].get(gid, [])],
                    "new": [r["outcome"] for r in new["cases"].get(gid, [])]}
              for gid in sorted(set(b) | set(n)) if b.get(gid) != n.get(gid)}
    return {
        "newly_failing": sorted(g for g in n if b.get(g, False) and not n[g]),
        "fixed": sorted(g for g in n if not b.get(g, True) and n[g]),
        "status_changes": status,
        "metric_delta": delta,
    }


# ---- output ----------------------------------------------------------------------------------------------

def pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def num(v: float | None, digits: int = 1) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


CSV_FIELDS = ["gt_id", "run_index", "case_id", "golden_case", "scenario_class", "expected_outcome", "outcome",
              "outcome_correct", "expected_stop_reason", "stop_reason", "stop_reason_correct", "unsafe_closure",
              "episode_recall", "evidence_precision", "evidence_coverage", "exceptions_expected", "exceptions_found",
              "exception_exact", "state_accuracy", "traceability", "step_count", "elapsed_ms", "missed_mandatory",
              "unlabelled_retrieved", "state_mismatches"]


def write_csv(path: Path, scored: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for rows in scored["cases"].values():
            for r in rows:
                w.writerow({k: (json.dumps(r[k]) if isinstance(r[k], (list, dict)) else r[k]) for k in CSV_FIELDS})


def render_report(results: dict[str, dict], comparisons: dict[str, dict] | None = None) -> str:
    modes = [m for m in MODES if m in results] + [m for m in results if m not in MODES]
    first = results[modes[0]]["header"]
    out = [
        "# EPISIGHT evaluation report",
        "",
        (f"Dataset `{first.get('dataset_version')}` · corpus `{first.get('corpus_version')}` · code "
        f"`{first.get('code_version')}`. Outcomes are evidence situations, not verdicts. Metric definitions: "
        "`evaluation/METRICS.md`."),
        "",
        "## Metrics by mode",
        "",
        "| Metric | " + " | ".join(modes) + " |",
        "|---|" + "---|" * len(modes),
    ]
    agg = {m: results[m]["aggregate"] for m in modes}
    lines = [
        ("Screening recall", lambda a: pct(a["screening"]["recall"])),
        ("Screening false-positive sets", lambda a: str(a["screening"]["false_positive_sets"])),
        ("Episode recall", lambda a: pct(a["episode_recall"])),
        ("Evidence retrieval precision", lambda a: pct(a["evidence_precision"])),
        ("· notes only", lambda a: pct(a["note_evidence_precision"])),
        ("· policy only", lambda a: pct(a["policy_precision"])),
        ("Evidence coverage (mandatory)", lambda a: pct(a["evidence_coverage"])),
        ("Exception precision", lambda a: pct(a["exceptions"]["precision"])),
        ("Exception recall", lambda a: pct(a["exceptions"]["recall"])),
        ("Exception exact-match (cases)", lambda a: pct(a["exceptions"]["exact_case_accuracy"])),
        ("Outcome accuracy", lambda a: pct(a["outcome_accuracy"])),
        ("Stop-reason accuracy", lambda a: pct(a["stop_reason_accuracy"])),
        ("Appropriate escalation", lambda a: pct(a["escalation"]["accuracy"])),
        ("Unsafe closures (should escalate, closed)", lambda a: str(len(a["escalation"]["unsafe_closures"]))),
        ("Requirement-state accuracy", lambda a: pct(a["state_accuracy"])),
        ("Brief traceability", lambda a: pct(a["traceability"])),
        ("Avg steps", lambda a: num(a["avg_steps"])),
        ("Avg elapsed (ms)", lambda a: num(a["avg_elapsed_ms"], 0)),
        ("AI planner steps / fallbacks", lambda a: f"{a['planner']['llm_steps']} / {a['planner']['fallback_steps']}"),
        ("Golden A–E passing", lambda a: f"{sum(a['golden'].values())}/{len(a['golden'])}"),
    ]
    out += [f"| {label} | " + " | ".join(fn(agg[m]) for m in modes) + " |" for label, fn in lines]

    out += ["", "## Golden cases", "", "| Case | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    for g in sorted(agg[modes[0]]["golden"]):
        out.append(f"| {g} | " + " | ".join("pass" if agg[m]["golden"].get(g) else "**FAIL**" for m in modes) + " |")

    out += ["", "## Outcome accuracy by scenario class", "",
            "| Scenario class | " + " | ".join(modes) + " |", "|---|" + "---|" * len(modes)]
    classes = sorted({k for m in modes for k in agg[m]["by_scenario_class"]})
    for k in classes:
        out.append(f"| {k} | " + " | ".join(pct(agg[m]["by_scenario_class"].get(k, {}).get("outcome_accuracy"))
                                           for m in modes) + " |")

    out += ["", "## Mismatches", ""]
    any_fail = False
    for m in modes:
        for gid, rows in results[m]["cases"].items():
            if not rows:
                any_fail = True
                out.append(f"- `{m}` **{gid}**: case not produced (screening miss)")
                continue
            for r in rows:
                if r["outcome_correct"] and r["stop_reason_correct"] and not r["state_mismatches"]:
                    continue
                any_fail = True
                rep = f" (repeat {r['run_index']})" if agg[m]["variance"]["repeats"] > 1 else ""
                out.append(f"- `{m}` **{gid}**{rep} `{r['case_id']}`: got {r['outcome']} / {r['stop_reason']}, "
                           f"expected {r['expected_outcome']} / {r['expected_stop_reason']}"
                           + (f"; states got/expected {r['state_mismatches']}" if r["state_mismatches"] else ""))
    if not any_fail:
        out.append("None.")
    for m in modes:
        s = agg[m]["screening"]
        if s["missed"] or s["must_not_flag_violations"]:
            out.append(f"- `{m}` screening: missed {s['missed']}, flagged must-not-flag {s['must_not_flag_violations']}")
        if agg[m]["variance"]["unstable_cases"]:
            out.append(f"- `{m}` unstable across repeats: {agg[m]['variance']['unstable_cases']}")

    if comparisons:
        out += ["", "## Regression vs baseline", ""]
        for m, d in comparisons.items():
            deltas = ", ".join(f"{k} {v:+.3f}" for k, v in d["metric_delta"].items() if v)
            out.append(f"- `{m}`: newly failing {d['newly_failing'] or 'none'}; fixed {d['fixed'] or 'none'}; "
                       f"deltas: {deltas or 'none'}")
    out.append("")
    return "\n".join(out)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score EPISIGHT batch runner output against ground truth.")
    ap.add_argument("--run", type=Path, required=True, help="Directory with <MODE>.json from `episight batch`.")
    ap.add_argument("--ground-truth", type=Path, required=True, help="data/ground-truth/<v>/cases.jsonl")
    ap.add_argument("--out", type=Path, help="Output directory (default: the run directory).")
    ap.add_argument("--baseline", type=Path, help="A previous scores.json to diff against (regression).")
    ap.add_argument("--fail-on-golden", action="store_true", help="Exit 1 if any golden case fails in any mode.")
    args = ap.parse_args(argv)

    gt = load_jsonl(args.ground_truth)
    files = [p for p in sorted(args.run.glob("*.json")) if p.stem in MODES]
    if not files:
        print(f"no <MODE>.json files in {args.run}", file=sys.stderr)
        return 2
    out_dir = args.out or args.run
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {p.stem: score_run(json.loads(p.read_text(encoding="utf-8")), gt) for p in files}
    for mode, scored in results.items():
        write_csv(out_dir / f"per_case_{mode}.csv", scored)

    comparisons = None
    if args.baseline:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
        comparisons = {m: compare(base["modes"][m], results[m]) for m in results if m in base.get("modes", {})}

    payload = {"ground_truth": str(args.ground_truth), "modes": results, "regression": comparisons}
    (out_dir / "scores.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(render_report(results, comparisons), encoding="utf-8")
    for mode, scored in results.items():
        a = scored["aggregate"]
        pct = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"
        print(f"{mode:18} outcome {pct(a['outcome_accuracy']):>4}  golden {sum(a['golden'].values())}/"
              f"{len(a['golden'])}  coverage {pct(a['evidence_coverage']):>4}  precision "
              f"{pct(a['evidence_precision']):>4}  unsafe {len(a['escalation']['unsafe_closures'])}")
    print(f"wrote {out_dir / 'report.md'}")

    if args.fail_on_golden and any(not ok for s in results.values() for ok in s["aggregate"]["golden"].values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
