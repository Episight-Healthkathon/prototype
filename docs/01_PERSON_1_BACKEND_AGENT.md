# EPISIGHT — Person 1 Work Plan
## Backend, Agent & Core Intelligence Owner

> Mission: build the core investigation engine that turns a deterministic risk signal into a structured, traceable, evidence-grounded investigation brief.

---

## 1. Ownership Boundary

- Own:
  - FastAPI backend.
  - PostgreSQL integration.
  - temporal screening.
  - episode reconstruction / graph.
  - evidence-gap investigation state.
  - agent orchestration.
  - agent tools.
  - retrieval integration.
  - stopping rules.
  - investigation brief generation.
  - evidence ledger / provenance backend.
  - backend tests and robustness.
- Co-own with Person 3:
  - data contracts.
  - screening-rule validation.
  - evaluation runner integration.
  - benchmark failure analysis.
- Provide stable contracts to Person 2.
- Do **not** own:
  - frontend visual implementation;
  - synthetic benchmark ground truth;
  - domain-label validity;
  - final evaluation metric definitions.

---

## 2. Success Condition

Person 1 is complete when the following works through API calls without relying on manual intervention:

- [ ] Load/select a synthetic flagged case.
- [ ] Reconstruct related episodes.
- [ ] Build case state.
- [ ] Identify missing evidence.
- [ ] Select a relevant tool.
- [ ] Retrieve structured evidence.
- [ ] Update state.
- [ ] Repeat if needed.
- [ ] Stop according to documented rules.
- [ ] Produce a structured reviewer brief.
- [ ] Preserve provenance for all material evidence.

---

# PHASE 0 — Technical Contract Lock

## Tasks

- [ ] Review the project context file and refined EPISIGHT scope.
- [ ] Agree with Person 3 on data entities:
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
- [ ] Agree with Person 2 on frontend-facing response schemas.
- [ ] Define enums for:
  - signal type;
  - case status;
  - investigation status;
  - evidence category;
  - source type;
  - stop reason.
- [ ] Define `CaseState` schema.
- [ ] Define `Evidence` schema.
- [ ] Define `InvestigationBrief` schema.
- [ ] Define API error structure.
- [ ] Define maximum investigation steps.
- [ ] Decide what logic is deterministic and what logic may use an LLM.
- [ ] Document all contracts in `docs/api-contract.md` and/or typed shared schemas.

## Exit checklist

- [ ] Person 2 can build against stable mock response shapes.
- [ ] Person 3 can generate data that backend can ingest without custom one-off parsing.
- [ ] No major entity field is still ambiguous.

---

# PHASE 1 — Backend Foundation

## FastAPI setup

- [ ] Initialize FastAPI project.
- [ ] Configure environment settings.
- [ ] Create `/health` endpoint.
- [ ] Configure structured logging.
- [ ] Configure exception handlers.
- [ ] Configure request/response validation.
- [ ] Configure CORS for frontend development.
- [ ] Create application service/repository boundaries.

## Database

- [ ] Configure PostgreSQL connection.
- [ ] Create migration system.
- [ ] Create tables/models for:
  - patients;
  - providers;
  - episodes;
  - claims;
  - diagnoses/procedures as appropriate;
  - clinical notes;
  - cases;
  - evidence;
  - investigation state/sessions;
  - policies or policy metadata if stored in DB;
  - audit/investigation actions.
- [ ] Create deterministic seed command from Person 3 dataset.
- [ ] Ensure benchmark ground truth is **not** exposed through normal investigation repositories.

## API skeleton

- [ ] `GET /cases`
- [ ] `GET /cases/{case_id}`
- [ ] `GET /cases/{case_id}/episodes`
- [ ] `GET /cases/{case_id}/evidence`
- [ ] `POST /cases/{case_id}/investigate`
- [ ] `GET /cases/{case_id}/investigation`
- [ ] `GET /cases/{case_id}/brief`
- [ ] `GET /evidence/{evidence_id}`
- [ ] OpenAPI schema works.

## Exit checklist

- [ ] Database can be recreated from scratch.
- [ ] Synthetic seed imports successfully.
- [ ] All baseline endpoints respond with typed data.
- [ ] Frontend can begin real API integration.

---

# PHASE 2 — Temporal Screening Engine

## Readmission screening

- [ ] Identify repeated inpatient episodes for the same pseudonymous patient.
- [ ] Check same provider/FKRTL as defined by prototype rule.
- [ ] Check same/related diagnosis according to agreed benchmark rule.
- [ ] Compute interval between episodes.
- [ ] Apply agreed temporal threshold.
- [ ] Return signal reason as structured fields.

## Fragmentation screening

- [ ] Identify repeated outpatient encounters.
- [ ] Check same patient.
- [ ] Check same provider/FKRTL.
- [ ] Check same/related diagnosis.
- [ ] Compute encounter interval.
- [ ] Apply agreed fragmentation temporal threshold.
- [ ] Return structured signal reasons.

## Screening output

- [ ] Create/update `Case` object.
- [ ] Save related episode IDs.
- [ ] Save signal metadata.
- [ ] Do not emit fraud or legitimacy verdict.

## Tests

- [ ] Inside threshold.
- [ ] Exactly at threshold.
- [ ] Outside threshold.
- [ ] Same patient, different provider.
- [ ] Same provider, different diagnosis.
- [ ] Inpatient/outpatient mismatch.
- [ ] Duplicate data rows.
- [ ] Missing timestamps.

## Exit checklist

- [ ] Person 3 golden screening fixtures pass.
- [ ] Screening outputs are deterministic.
- [ ] Risk signals are explainable via structured reasons.

---

# PHASE 3 — Episode Reconstruction / Graph

## Domain relationships

- [ ] Build relationship model linking:
  - patient → episodes;
  - episode → provider;
  - episode → diagnosis;
  - episode → procedures;
  - episode → claim;
  - episode → clinical notes;
  - episode → evidence.
- [ ] Implement NetworkX or a simpler domain graph abstraction.
- [ ] Keep graph implementation replaceable; do not couple API to NetworkX objects.

## Reconstruction service

- [ ] Retrieve related candidate episodes.
- [ ] Sort chronologically.
- [ ] Calculate intervals.
- [ ] Mark relation reasons.
- [ ] Return frontend-friendly timeline object.
- [ ] Preserve source IDs.

## Tests

- [ ] Two related episodes.
- [ ] Three+ related episodes.
- [ ] Similar but unrelated episode.
- [ ] Same diagnosis but wrong provider.
- [ ] Missing procedure.
- [ ] Out-of-order timestamps.

## Exit checklist

- [ ] Golden cases reconstruct expected episode sets.
- [ ] Episode Recall can be computed by Person 3.
- [ ] Frontend receives a stable timeline response.

---

# PHASE 4 — Evidence & Retrieval Infrastructure

## Evidence object

- [ ] Implement evidence repository/model.
- [ ] Required fields include:
  - evidence ID;
  - case ID;
  - related episode;
  - source type;
  - source ID;
  - excerpt/value;
  - tool used;
  - retrieval reason;
  - timestamp;
  - relevance category;
  - policy version when relevant.

## Clinical retrieval

- [ ] Retrieve candidate clinical notes by episode/case.
- [ ] Support context search relevant to:
  - emergency;
  - chronic condition;
  - scheduled procedure;
  - follow-up;
  - clinical justification.
- [ ] Return structured source metadata.

## Policy retrieval

- [ ] Ingest Person 3 policy corpus.
- [ ] Chunk/index if required.
- [ ] Preserve title/section/version/source metadata.
- [ ] Return top relevant policy evidence with traceable IDs.
- [ ] Prevent uncited policy statements from being treated as source-backed policy evidence.

## Exit checklist

- [ ] Clinical evidence retrieval works on golden cases.
- [ ] Policy retrieval returns sourceable evidence.
- [ ] Every retrieved item has provenance.

---

# PHASE 5 — Agent Tools

## Tool implementations

- [ ] `get_episode_history()`
- [ ] `compare_diagnosis()`
- [ ] `compare_procedures()`
- [ ] `get_provider_context()`
- [ ] `retrieve_clinical_evidence()`
- [ ] `retrieve_policy()`
- [ ] `find_supporting_evidence()`
- [ ] `find_exception_evidence()`

## Tool quality rules

- [ ] Every tool has typed inputs.
- [ ] Every tool has typed outputs.
- [ ] Every tool returns source/reference metadata where applicable.
- [ ] Every tool exposes explicit error/failure state.
- [ ] No tool invents missing records.
- [ ] Tool outputs are serializable and persistable.

## Tests

- [ ] Valid input.
- [ ] Missing source.
- [ ] Empty retrieval.
- [ ] Malformed case.
- [ ] Unsupported case type.
- [ ] Duplicate evidence.

---

# PHASE 6 — Evidence-Gap Case State

## State structure

- [ ] `known_facts`
- [ ] `supporting_risk_evidence`
- [ ] `explaining_context_evidence`
- [ ] `missing_evidence`
- [ ] `unresolved_questions`
- [ ] `tools_called`
- [ ] `next_action`
- [ ] `investigation_step`
- [ ] `status`
- [ ] `stop_reason`

## State behavior

- [ ] Initialize state from screening + episode reconstruction.
- [ ] Derive initial evidence gaps.
- [ ] Update state after every tool call.
- [ ] Prevent repeated identical tool calls unless retry policy permits it.
- [ ] Persist state so frontend can inspect current progress.
- [ ] Preserve investigation history.

## Exit checklist

- [ ] For each golden case, known vs missing evidence is meaningfully different.
- [ ] State transitions are inspectable.
- [ ] Person 2 can render state without parsing free-form LLM prose.

---

# PHASE 7 — Evidence-Gap Agent Orchestrator

## Orchestration loop

- [ ] Read current case state.
- [ ] Determine highest-priority unresolved evidence gap.
- [ ] Choose one relevant tool.
- [ ] Execute tool.
- [ ] Validate tool response.
- [ ] Store evidence/action.
- [ ] Update case state.
- [ ] Evaluate stopping criteria.
- [ ] Repeat until stop.

## LLM constraints

- [ ] Use LLM only where it adds value.
- [ ] Do not allow raw LLM text to become source evidence.
- [ ] Tool results remain canonical evidence.
- [ ] Invalid tool choice falls back safely.
- [ ] Invalid structured output is rejected/retried within a bounded policy.
- [ ] No hidden access to ground truth.

## Dual-evidence behavior

- [ ] Search evidence supporting risk.
- [ ] Search evidence explaining legitimate context.
- [ ] Preserve both sides separately.
- [ ] Do not stop at the first supporting evidence if material exception context is still unresolved.

## Exit checklist

- [ ] Agent behavior differs appropriately across the 4 golden cases.
- [ ] Tool trace is visible.
- [ ] No infinite loops.
- [ ] No unsupported final claims.

---

# PHASE 8 — Stopping & Escalation Logic

## Required stopping states

- [ ] `EVIDENCE_SUFFICIENT`
- [ ] `EVIDENCE_CONFLICTING`
- [ ] `EVIDENCE_UNAVAILABLE`
- [ ] `HUMAN_REVIEW_REQUIRED`

## Rules

- [ ] Stop if required evidence has been sufficiently surfaced for a reviewer brief.
- [ ] Stop/escalate when material evidence conflicts.
- [ ] Stop/escalate when required evidence cannot be retrieved.
- [ ] Stop when max steps reached.
- [ ] Preserve unresolved questions in final output.
- [ ] Never convert `missing` into `false` or `legitimate` automatically.
- [ ] Never convert `conflicting` into one-sided certainty without human review.

## Tests

- [ ] Case A should surface legitimate context.
- [ ] Case B should remain under investigation or unresolved as designed.
- [ ] Case C should recognize scheduled-care context.
- [ ] Case D should stop with explicit uncertainty / human review.

---

# PHASE 9 — Investigation Brief Generator

## Output structure

- [ ] `case_summary`
- [ ] `risk_signal`
- [ ] `episode_timeline`
- [ ] `supporting_risk_evidence`
- [ ] `explaining_context_evidence`
- [ ] `policy_references`
- [ ] `remaining_gaps`
- [ ] `uncertainty`
- [ ] `suggested_next_review`
- [ ] `investigation_status`
- [ ] `source/provenance links`

## Quality constraints

- [ ] Every material evidence statement has evidence ID/source.
- [ ] Brief does not say “fraud confirmed.”
- [ ] Brief does not approve/reject a claim.
- [ ] Brief clearly indicates uncertainty.
- [ ] Brief can be regenerated from persisted structured state.

---

# PHASE 10 — Evidence Ledger & Auditability

## Persist

- [ ] tool action;
- [ ] input reference;
- [ ] evidence returned;
- [ ] timestamp;
- [ ] retrieval reason;
- [ ] investigation step;
- [ ] policy version/source;
- [ ] error/failure state.

## API

- [ ] Evidence detail endpoint.
- [ ] Case evidence list endpoint.
- [ ] Investigation trace endpoint or embedded trace response.

## Exit checklist

- [ ] Person 2 can show evidence detail drawer.
- [ ] Person 3 can calculate traceability metric.

---

# PHASE 11 — Evaluation Integration

## Work with Person 3

- [ ] Create benchmark runner interface.
- [ ] Run investigation in batch mode.
- [ ] Return machine-readable output.
- [ ] Record runtime and step count.
- [ ] Ensure no ground-truth access.
- [ ] Export results in stable JSON/CSV-friendly format.

## Debug metrics

- [ ] episode reconstruction result;
- [ ] retrieved evidence IDs;
- [ ] stop reason;
- [ ] tool call count;
- [ ] elapsed time;
- [ ] brief output.

---

# PHASE 12 — Robustness & Regression

## Unit tests

- [ ] screening;
- [ ] graph reconstruction;
- [ ] evidence repository;
- [ ] tool outputs;
- [ ] state transitions;
- [ ] stopping rules;
- [ ] brief generation.

## Failure tests

- [ ] database unavailable;
- [ ] retrieval empty;
- [ ] malformed note;
- [ ] policy unavailable;
- [ ] tool exception;
- [ ] invalid LLM structured output;
- [ ] timeout;
- [ ] max-step reached;
- [ ] repeated evidence;
- [ ] conflicting evidence.

## Regression

- [ ] Run golden cases after every significant agent/tool change.
- [ ] Track previously passing cases that regress.
- [ ] Do not optimize only for the demo case.

---

# P0 / P1 / P2 Priorities

## P0 — Must finish

- [ ] FastAPI + DB.
- [ ] Screening.
- [ ] Episode reconstruction.
- [ ] Evidence schema and repository.
- [ ] Case state.
- [ ] Core tools.
- [ ] Clinical + policy retrieval.
- [ ] Evidence-gap loop.
- [ ] Dual-evidence behavior.
- [ ] Explicit stopping logic.
- [ ] Reviewer brief.
- [ ] Provenance API.
- [ ] Golden-case end-to-end support.

## P1 — Strongly recommended

- [ ] Batch benchmark runner.
- [ ] Investigation history endpoint.
- [ ] Better retrieval ranking.
- [ ] Policy version metadata.
- [ ] Structured action logs.
- [ ] 20+ benchmark-case support.

## P2 — Stretch

- [ ] streaming agent progress;
- [ ] richer graph model;
- [ ] advanced retry policies;
- [ ] richer role/access model;
- [ ] performance optimization beyond demo needs.

---

# Daily / PR Checklist

Before opening a PR:

- [ ] Tests pass.
- [ ] No ground-truth code path is reachable by investigation agent.
- [ ] No endpoint emits autonomous fraud/payment verdict.
- [ ] New output has typed schema.
- [ ] New evidence includes provenance.
- [ ] API change communicated to Person 2.
- [ ] Data requirement change communicated to Person 3.
- [ ] Golden cases still pass or regression is documented.

---

# Final Definition of Done — Person 1

- [ ] Backend starts from documented commands.
- [ ] Database can be recreated and seeded.
- [ ] Screening is deterministic and tested.
- [ ] Episode reconstruction matches expected golden-case episodes.
- [ ] Case state is explicit and persisted/inspectable.
- [ ] Agent chooses tools based on evidence gaps.
- [ ] Both risk-supporting and context-explaining evidence can be surfaced.
- [ ] Missing and conflicting evidence are represented correctly.
- [ ] Stopping logic is bounded and deterministic at the policy level.
- [ ] Reviewer brief is structured and source-backed.
- [ ] Evidence provenance is queryable.
- [ ] Batch evaluation can run without special manual steps.
- [ ] All four golden cases exhibit their expected behavior.
