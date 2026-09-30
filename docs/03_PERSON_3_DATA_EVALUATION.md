# EPISIGHT — Person 3 Work Plan
## Synthetic Data, Domain, Benchmark, Evaluation & QA Owner

> Mission: make the prototype testable and trustworthy by supplying reproducible synthetic data, realistic case logic, hidden ground truth, a validated policy/evidence corpus, automated evaluation, and end-to-end quality assurance.

---

## 1. Ownership Boundary

- Own:
  - synthetic data design and generation;
  - golden cases;
  - benchmark case taxonomy;
  - hidden ground truth;
  - synthetic clinical notes;
  - policy corpus preparation;
  - evidence relevance labels;
  - metric definitions;
  - evaluation harness;
  - regression benchmark;
  - domain QA;
  - governance QA;
  - end-to-end prototype QA.
- Co-own with Person 1:
  - data schema;
  - screening-rule fixtures;
  - benchmark runner interface;
  - failure analysis.
- Co-own with Person 2:
  - terminology;
  - case wording;
  - uncertainty labels;
  - domain-correct UI representation.
- Do **not** own:
  - backend orchestration implementation;
  - frontend implementation;
  - live agent tool logic.

---

## 2. Success Condition

Person 3 is complete when:

- [ ] Synthetic dataset can be regenerated deterministically.
- [ ] Four golden cases are stable and representative.
- [ ] Ground truth is separate and inaccessible to the agent.
- [ ] Clinical/policy evidence is realistic enough to test retrieval and reasoning.
- [ ] 20+ benchmark cases exist, with 20–50 as the target range if time permits.
- [ ] Evaluation can run automatically.
- [ ] Metrics can be reproduced.
- [ ] Regressions can be detected.
- [ ] Prototype behavior respects domain and governance constraints.

---

# PHASE 0 — Data & Evaluation Contract Lock

## Data contract

- [ ] Agree entities with Person 1:
  - patient;
  - provider;
  - episode;
  - claim;
  - diagnosis;
  - procedure;
  - clinical note;
  - policy document;
  - case;
  - evidence;
  - ground truth.
- [ ] Define required vs optional fields.
- [ ] Define ID format.
- [ ] Define timestamps/time zone assumptions.
- [ ] Define relation keys.
- [ ] Define missing-data representation.
- [ ] Write a concise `data-contract.md` or equivalent.

## Evaluation contract

- [ ] Define expected case outcomes.
- [ ] Define metric formulas.
- [ ] Define benchmark result format.
- [ ] Define pass/fail criteria for golden cases.
- [ ] Confirm no ground truth is exposed to agent-readable repositories.

---

# PHASE 1 — Synthetic Data Schema

## Patient

- [ ] `patient_id`
- [ ] pseudonymous only.
- [ ] minimal synthetic metadata only if required.

## Provider

- [ ] `provider_id`
- [ ] synthetic FKRTL/provider name or label.
- [ ] type/location only if needed for prototype logic.

## Episode

- [ ] `episode_id`
- [ ] `patient_id`
- [ ] `provider_id`
- [ ] encounter type.
- [ ] start/end timestamps.
- [ ] diagnosis.
- [ ] procedure IDs.
- [ ] note IDs.

## Claim

- [ ] `claim_id`
- [ ] `episode_id`
- [ ] synthetic claim metadata required for screening/display.

## Clinical note

- [ ] `note_id`
- [ ] `episode_id`
- [ ] note type.
- [ ] text.
- [ ] created timestamp.

## Policy document

- [ ] `policy_id`
- [ ] title.
- [ ] section.
- [ ] content.
- [ ] source metadata.
- [ ] version/effective date where available.

## Ground truth

- [ ] `case_id`
- [ ] case class.
- [ ] expected related episodes.
- [ ] expected relevant evidence IDs/types.
- [ ] expected exception/context.
- [ ] expected stop behavior.
- [ ] expected final investigation state.

---

# PHASE 2 — Synthetic Generator

## Generator requirements

- [ ] Reproducible with seed.
- [ ] Deterministic golden cases.
- [ ] Configurable number of background/noise episodes.
- [ ] Configurable benchmark case counts.
- [ ] No real participant information.
- [ ] No copied real patient notes.

## Generation output

- [ ] patients file/table.
- [ ] providers file/table.
- [ ] episodes file/table.
- [ ] claims file/table.
- [ ] diagnoses/procedures.
- [ ] clinical notes.
- [ ] policy corpus separately.
- [ ] ground truth separately.

## CLI/script

- [ ] Generate.
- [ ] Reset.
- [ ] Validate schema.
- [ ] Optional seed DB helper with Person 1.

---

# PHASE 3 — Four Golden Cases

## Case A — Legitimate Readmission

- [ ] Same/similar diagnosis.
- [ ] Same provider as defined by screening.
- [ ] Short interval.
- [ ] Emergency context exists.
- [ ] Chronic condition or legitimate clinical context exists if appropriate.
- [ ] Supporting risk signal still exists.
- [ ] Expected behavior: surface explanatory context, not autonomous final judgement.

## Case B — Potential Fragmentation

- [ ] Repeated outpatient care.
- [ ] Short interval.
- [ ] Same/relevant diagnosis.
- [ ] Legitimate justification absent or incomplete.
- [ ] Expected behavior: continue investigation or preserve unresolved concern.

## Case C — Scheduled Procedure

- [ ] Related procedures.
- [ ] Planned/staged interval.
- [ ] Scheduled-care/supporting note exists.
- [ ] Risk signal should still be plausible at screening level.
- [ ] Expected behavior: recognize legitimate planned-care context.

## Case D — Missing Evidence

- [ ] Risk signal exists.
- [ ] Important contextual source is missing/unavailable.
- [ ] Agent should not infer missing context.
- [ ] Expected behavior: explicit uncertainty + human review.

## Golden-case quality checklist

- [ ] Not trivial keyword-only cases.
- [ ] Evidence is discoverable but not always in the same location.
- [ ] Ground truth is unambiguous to the benchmark author.
- [ ] Expected system behavior is documented.
- [ ] Cases remain fixed for regression testing.

---

# PHASE 4 — Benchmark Taxonomy & Expansion

## Required categories

- [ ] legitimate readmission;
- [ ] unresolved/potentially problematic readmission;
- [ ] legitimate fragmentation/follow-up;
- [ ] potential fragmentation;
- [ ] scheduled/staged procedure;
- [ ] chronic-condition revisit;
- [ ] emergency return;
- [ ] missing evidence;
- [ ] conflicting evidence;
- [ ] superficially similar but unrelated episode.

## Target volume

- [ ] First milestone: 4 golden cases.
- [ ] Second milestone: 20+ benchmark cases.
- [ ] Target if time permits: 20–50 total.

## Distribution principles

- [ ] Avoid class imbalance that makes metrics meaningless.
- [ ] Include hard positives.
- [ ] Include hard negatives.
- [ ] Include evidence noise.
- [ ] Include missingness.
- [ ] Include conflicting information.

---

# PHASE 5 — Synthetic Clinical Notes

## Note-writing rules

- [ ] Use synthetic fictional content only.
- [ ] Keep notes plausible but concise.
- [ ] Vary wording across cases.
- [ ] Do not always state the answer with exact benchmark keywords.
- [ ] Include useful context naturally.
- [ ] Include irrelevant information/noise in some cases.
- [ ] Include incomplete notes in missing-evidence cases.
- [ ] Include conflicting notes in conflict cases.

## Context types to encode

- [ ] emergency;
- [ ] chronic condition;
- [ ] scheduled procedure;
- [ ] planned follow-up;
- [ ] clinical justification;
- [ ] no documented justification;
- [ ] ambiguous statement.

## QA

- [ ] Every note links to correct episode.
- [ ] Expected evidence labels are documented in ground truth.
- [ ] Notes do not accidentally leak “ground_truth=…” style labels.

---

# PHASE 6 — Policy Knowledge Base

## Corpus fields

- [ ] policy ID.
- [ ] title.
- [ ] section.
- [ ] text/content.
- [ ] source metadata.
- [ ] version/effective date where supported.

## Preparation

- [ ] Include only verified relevant policy content from the refined project source material.
- [ ] Keep citation/source information.
- [ ] Prepare chunks suitable for retrieval.
- [ ] Label expected policy relevance for benchmark cases where applicable.

## QA

- [ ] No invented regulation.
- [ ] No unsupported exception rule.
- [ ] Policy metadata survives ingestion into Person 1 retrieval system.

---

# PHASE 7 — Screening Rule Fixtures

Work with Person 1 to build fixtures for:

- [ ] inside threshold.
- [ ] exactly at threshold.
- [ ] outside threshold.
- [ ] same patient + different provider.
- [ ] same provider + different diagnosis.
- [ ] inpatient vs outpatient mismatch.
- [ ] duplicate encounter.
- [ ] missing date.
- [ ] similar but unrelated episode.

For every fixture:

- [ ] expected signal type.
- [ ] expected related episodes.
- [ ] expected reason codes.
- [ ] expected no-signal where applicable.

---

# PHASE 8 — Evidence Relevance Labels

## Label each benchmark evidence item as

- [ ] supporting risk.
- [ ] explaining legitimate context.
- [ ] neutral/background.
- [ ] irrelevant/noise.

## Ground-truth evidence set

- [ ] Identify required/expected evidence.
- [ ] Identify optional supporting evidence.
- [ ] Identify evidence that should **not** be retrieved as relevant.

## Purpose

- Enables:
  - Evidence Retrieval Precision;
  - Evidence Coverage;
  - exception recognition evaluation.

---

# PHASE 9 — Evaluation Metric Definitions

## Episode Recall

- [ ] Define expected related-episode set.
- [ ] Compare against reconstructed set.
- [ ] Document formula and edge cases.

## Evidence Retrieval Precision

- [ ] Define relevant retrieved evidence.
- [ ] Define how duplicate evidence is handled.
- [ ] Document formula.

## Evidence Coverage

- [ ] Define expected evidence set.
- [ ] Define mandatory vs optional evidence if needed.
- [ ] Document formula.

## Exception Identification Accuracy

- [ ] Define what counts as correct exception recognition.
- [ ] Distinguish surfaced evidence from autonomous decision.
- [ ] Document formula.

## Appropriate Escalation

- [ ] Define which cases should escalate.
- [ ] Define correct stop states.
- [ ] Score missing/conflicting cases.

## Investigation Completion Time

- [ ] Measure from investigation start to terminal/brief-ready state.
- [ ] Keep environment/hardware caveat documented.

## Traceability

- [ ] Define material brief items.
- [ ] Count source-backed vs unsupported material items.
- [ ] Document formula.

---

# PHASE 10 — Evaluation Harness

## Runner behavior

- [ ] Load benchmark case list.
- [ ] Trigger Person 1 backend investigation.
- [ ] Wait for terminal state.
- [ ] Capture:
  - reconstructed episodes;
  - retrieved evidence IDs;
  - evidence categories;
  - stop reason;
  - final status;
  - runtime;
  - tool call count;
  - brief output.
- [ ] Load hidden ground truth only inside evaluation code.
- [ ] Compare actual vs expected.
- [ ] Compute metrics.
- [ ] Save per-case results.
- [ ] Save aggregate results.

## Output formats

- [ ] JSON.
- [ ] CSV where useful.
- [ ] Human-readable summary.

## Reproducibility

- [ ] Record dataset version/seed.
- [ ] Record backend/agent version or git commit if practical.
- [ ] Record policy corpus version.

---

# PHASE 11 — Hard Positives & Hard Negatives

## Hard negatives

Create cases that look suspicious but have legitimate context:

- [ ] short-interval same diagnosis + emergency return.
- [ ] repeated procedure + staged planned care.
- [ ] repeated outpatient + justified follow-up.
- [ ] chronic condition revisit.

Expected:

- [ ] system surfaces explanatory evidence;
- [ ] system does not convert screening signal into automatic judgement.

## Hard positives / unresolved risk

Create cases where risk signal remains concerning:

- [ ] repeated episode.
- [ ] no valid supporting exception evidence.
- [ ] partial/ambiguous notes.

Expected:

- [ ] investigation does not prematurely close as legitimate;
- [ ] evidence gap remains explicit.

---

# PHASE 12 — Missing & Conflicting Evidence Cases

## Missing evidence

- [ ] no clinical note.
- [ ] note inaccessible.
- [ ] missing procedure metadata.
- [ ] relevant policy not available in corpus where designed.

Expected:

- [ ] unavailable stays unavailable;
- [ ] uncertainty remains explicit;
- [ ] appropriate escalation occurs.

## Conflicting evidence

- [ ] one source supports risk.
- [ ] another source supports legitimate context.

Expected:

- [ ] both sides remain visible;
- [ ] no arbitrary forced conclusion;
- [ ] human review required.

---

# PHASE 13 — Regression Testing

## Golden regression suite

- [ ] Run Case A.
- [ ] Run Case B.
- [ ] Run Case C.
- [ ] Run Case D.

## Trigger regression run after

- [ ] agent prompt change.
- [ ] tool logic change.
- [ ] retrieval change.
- [ ] screening change.
- [ ] policy corpus change.
- [ ] data schema change.

## Track

- [ ] previous status.
- [ ] new status.
- [ ] metric delta.
- [ ] newly failing cases.
- [ ] reason if known.

## Principle

- [ ] Do not optimize only until the demo case looks good.

---

# PHASE 14 — Governance QA

Verify the actual prototype behavior:

- [ ] Synthetic data only.
- [ ] Pseudonymous patient IDs.
- [ ] No real JKN participant data.
- [ ] No autonomous fraud verdict.
- [ ] No autonomous claim rejection.
- [ ] No payment decision.
- [ ] No record modification by agent.
- [ ] Missing evidence remains explicit.
- [ ] Conflicting evidence remains visible.
- [ ] Human review state exists.
- [ ] Evidence provenance exists.
- [ ] Policy source/version metadata preserved where available.
- [ ] Tool failures are not replaced by fabricated answers.

If any checkbox fails:

- [ ] Create issue.
- [ ] Assign owner.
- [ ] Block final “done” status until fixed or explicitly documented as a limitation.

---

# PHASE 15 — Domain / UX QA with Person 2

Review each screen for:

- [ ] correct terminology.
- [ ] no misleading “fraud” wording.
- [ ] no false certainty.
- [ ] correct representation of missing evidence.
- [ ] correct distinction between risk signal and investigation result.
- [ ] legitimate-context evidence is not visually hidden.
- [ ] human-review requirement is understandable.

---

# PHASE 16 — End-to-End QA

For every golden case:

- [ ] Appears correctly in Case Queue.
- [ ] Signal type/reasons are correct.
- [ ] Timeline contains expected episodes.
- [ ] Evidence gaps are sensible.
- [ ] Tool actions are sensible.
- [ ] Retrieved evidence matches expected labels.
- [ ] Stop reason matches expected behavior.
- [ ] Reviewer Brief preserves both evidence sides.
- [ ] Provenance opens correctly.
- [ ] No hidden ground-truth leakage.

---

# P0 / P1 / P2 Priorities

## P0 — Must finish

- [ ] Data contract.
- [ ] Synthetic generator.
- [ ] 4 golden cases.
- [ ] Ground truth isolation.
- [ ] Synthetic clinical notes.
- [ ] Policy corpus.
- [ ] Screening fixtures.
- [ ] evidence relevance labels.
- [ ] metric definitions.
- [ ] basic evaluation runner.
- [ ] governance QA.
- [ ] golden-case E2E QA.

## P1 — Strongly recommended

- [ ] 20+ benchmark cases.
- [ ] hard-positive/hard-negative balance.
- [ ] regression automation.
- [ ] aggregate metric report.
- [ ] policy retrieval quality labels.
- [ ] systematic failure categorization.

## P2 — Stretch

- [ ] 50-case benchmark.
- [ ] richer case generator controls.
- [ ] benchmark dashboard data feed.
- [ ] deeper slice analysis by case class.
- [ ] repeated-run variance analysis if the agent has nondeterministic behavior.

---

# Daily / PR Checklist

Before merging data/evaluation changes:

- [ ] Dataset still validates against schema.
- [ ] Golden cases remain deterministic.
- [ ] Ground truth is still isolated.
- [ ] No real patient data has been introduced.
- [ ] Policy content remains sourceable/verified.
- [ ] Metric formula changes are documented.
- [ ] Regression suite rerun if relevant.
- [ ] Person 1 informed of schema changes.
- [ ] Person 2 informed of terminology/status changes.

---

# Final Definition of Done — Person 3

- [ ] Synthetic dataset is reproducible.
- [ ] Four golden cases are stable and documented.
- [ ] 20+ benchmark cases exist, or the limitation is explicitly documented if time prevents it.
- [ ] Ground truth is hidden from the agent.
- [ ] Clinical notes are synthetic and useful for retrieval testing.
- [ ] Policy corpus is sourceable and version-aware where possible.
- [ ] Screening fixtures cover boundary conditions.
- [ ] Evidence relevance labels support precision/coverage metrics.
- [ ] Evaluation runner executes without manual case-by-case intervention.
- [ ] Aggregate metrics are reproducible.
- [ ] Missing/conflicting evidence cases behave correctly.
- [ ] Governance checklist passes.
- [ ] End-to-end golden-case QA passes.
