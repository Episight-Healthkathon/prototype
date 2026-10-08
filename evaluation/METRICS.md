# EPISIGHT evaluation metrics (Person 3)

Implemented in `evaluation/score.py`. Input: one `<MODE>.json` per mode from `episight batch` (Data
Contract §6) and `data/ground-truth/<v>/cases.jsonl` (§3.7). Ground truth is read only by the harness.

## Join

A ground-truth row is joined to runner cases by `anchor_episode_ids`, the sorted episode group (D-03).
Rows with `expected_signal_type = null` are screening negatives: they must not appear among
`screening.flagged_anchor_sets`. With `--repeats N`, every repeat (`run_index`) is scored as its own
run. FULL's declared `header.config.repeats` fixes the expected run count; deterministic modes
expect one run per positive case. Older FULL outputs infer repeats from observed indices.
Duplicate or invalid indices are rejected.

Outcome, stop-reason and escalation accuracy divide by **all expected positive runs**, including
missing cases/repeats as failures. Episode recall, mandatory evidence coverage and requirement-state
accuracy are macro averages over their eligible expected runs, with missing runs contributing zero.
Missing exception runs contribute false negatives; exact-match uses every expected run. Precision
and traceability describe produced evidence/briefs; undefined observations remain excluded. The
completeness gate must pass before using those conditional metrics.

Evidence is matched on `(source_type, source_id, requirement_key)` (D-22). Several sentences cited from
one note collapse to one item.

## Per-case metrics

| Metric | Formula | Edge cases |
|---|---|---|
| Episode recall | \|expected_related ∩ reconstructed\| / \|expected_related\| | — |
| Episode precision | \|expected_related ∩ reconstructed\| / \|reconstructed\| | Reported, not a headline metric |
| Evidence retrieval precision | \|retrieved ∩ relevant\| / \|retrieved\| | *retrieved* = deduplicated items from `CLINICAL_NOTE` and `POLICY_SECTION` only. Structured sources (`SCREENING_RULE`, `EPISODE_RECORD`, …) are deterministic look-ups and are excluded. *relevant* = expected items with category ≠ `IRRELEVANT`; `NEUTRAL` (e.g. the applicable policy) counts as relevant. Unlabelled retrieved items count as **not** relevant. Undefined (—) when nothing was retrieved |
| · notes only / policy only | Same formula restricted to one source type | Policy precision exposes off-topic sections (e.g. fragmentation rules cited for a readmission) |
| Evidence coverage | \|mandatory ∩ retrieved_any\| / \|mandatory\| | Any source type counts here, including the `EPISODE_RECORD` used by `SCHEDULE_CONSISTENCY`. Undefined when the case has no mandatory items (e.g. Case D) |
| Exception identification | found = {k ∈ EXCEPTION_KEYS : state(k) = `FOUND`}, compared with `expected_exceptions` | EXCEPTION_KEYS = EMERGENCY, CHRONIC_CONDITION, SCHEDULED_PROCEDURE, SUPPORTING_EXAM_FOLLOWUP context. Per-key TP/FP/FN are summed for micro precision/recall; *exact-match* = found set equals the expected set. This scores **surfaced** context, not a decision: a FOUND exception still goes to a human |
| Outcome / stop-reason accuracy | outcome = expected_outcome; stop_reason = expected_stop_reason | — |
| Appropriate escalation | escalated ⇔ should_escalate, where escalated = outcome ≠ `EVIDENCE_SUFFICIENT` and should_escalate = expected_outcome ≠ `EVIDENCE_SUFFICIENT` | **Unsafe closure** = should escalate but closed as sufficient (the most serious error). **Over-escalation** = sufficient context existed but the case was escalated (costs reviewer time, not safety) |
| Requirement-state accuracy | share of `expected_requirement_states` entries matched exactly | Only keys the ground truth lists |
| Traceability | `brief_traceability.with_evidence / material_statements` | — |
| Golden pass | outcome ✓ ∧ stop_reason ✓ ∧ every expected requirement state ✓ | With repeats, it must pass on **every** repeat |
| Completion time | `elapsed_ms` (runner-measured, start to terminal state) | Machine-dependent. FULL includes model latency. Record the machine with the report |

## Run-level metrics

- **Screening recall** = positives whose anchor set was flagged / positives. `missed` lists them.
- **Screening false positives** = flagged sets that match no positive row, whether a labelled negative
  (`must_not_flag_violations`) or something unlabelled (noise).
- **Variance** (`--repeats`): `unstable_cases` = rows whose `(outcome, stop_reason)` differs between repeats.
- **Planner health**: sums of `llm_steps`, `llm_retry_steps`, `fallback_steps`, `validation_rejections`.
- **By scenario class**: outcome accuracy per `scenario_class`.

## Regression

`--baseline <old scores.json>` gives, per mode: `newly_failing` (complete outcome, stop reason,
listed requirement states and brief validation passed before but fail now), `fixed`, `status_changes`,
and deltas for the headline metrics. `--fail-on-golden` fails any incomplete/failing golden case.

`--fail-on-regression` additionally gates missing cases/repeats, screening misses/false positives,
newly failing cases and decreases in compared quality metrics. FULL and FULL_RULE_PLANNER also
always fail on unsafe closures, golden failures and brief/tool failures. Deliberately weak ablation
modes can retain known baseline failures (including RULES_RETRIEVAL's schedule-consistency miss).
`--require-mode MODE` rejects an absent mode file. Gate failure is exit 1; absent/invalid inputs exit 2.

`evaluation/run_regression.sh` chains generation, freshness, deterministic batch and these gates.
Its default baseline is `reports/v0.1.0-pc-0.1.1-backend/scores.json`, so reintroducing GT-B09 fails CI.

## Evidence labels (ground truth)

`category` uses the Data Contract values `SUPPORTING_RISK`, `EXPLAINING_CONTEXT` and `NEUTRAL`, plus
the harness-only value **`IRRELEVANT`** (Phase 8: "should not be retrieved as relevant"). `mandatory`
marks evidence a competent reviewer needs. Optional relevant items raise precision but are not required
for coverage.
