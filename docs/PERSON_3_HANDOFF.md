# Person 3 handoff — 2026-10-08

The requested stages **1, 2, 3, 4 and 6 are complete for backend/CLI delivery**. Stage 5
(a new consolidated analytical evaluation report) was skipped at the user's request.
The original synthetic dataset, original ground truth and historical reports remain unchanged.

## Completed work and acceptance evidence

| Stage | Delivery | Evidence |
|---|---|---|
| 1 — Wording robustness | 40 reproducible, independently labelled scenarios covering Indonesian/English wording, negation, historical/conditional mentions, source scope, availability and conflict | `evaluation/paraphrase_cases.py`, `evaluation/person3-qa/2026-10-08/acceptance.json` |
| 2 — Label/metric audit | GT-B06's surfaced scheduled context corrected in a separate label version; no outcome/state/evidence changes | `data/ground-truth/v0.1.0-labels-1/README.md`, `label_audit.json` |
| 3 — Governance | Complete inputs, label isolation, synthetic IDs, read-only sources, literal provenance, policy metadata, human review, valid briefs and no model calls verified | Acceptance checks; backend isolation/envelope/robustness tests |
| 4 — Complete backend flow | Real ingest → screening → reconstruction → investigation → timeline/brief exercised on 20 official cases and all 40 challenges | `raw_qa_bundle.zip`, `golden/*.json` |
| 6 — Handoff | Reproduction instructions, scoped checklist, durable evidence, CI gate and remaining owners | This document and `evaluation/README.md` |

Three newly discovered unsafe challenge closures were fixed in the matcher: historical shock,
conditional shock instructions, and multiword negation such as "tidak ada komplikasi". Ordinary
emergency phrases now use the same conservative non-current guard as active resuscitation;
negation distance is measured after the complete cue. No ML classifier or additional paid run was added.

Verified locally: **501 tests passed** (backend unit + generator + evaluation), backend lint passed,
all three deterministic modes passed the existing regression gate, and **60/60 FULL recordings
replayed identically** after the matcher fix (excluding elapsed time and brief generation time).
The replay is verification of recorded decisions on the existing dataset, not a fresh live benchmark
or proof that the AI planner handles the new wording challenges.

Official full rule pipeline: 20/20 outcomes, golden A–E 5/5, no unsafe closure. Wording challenge:
**36/40 correct outcomes and labelled states, no unsafe closure**, four conservative over-escalations.
Acceptance passes with these explicit limitations; it does not mean 40/40 clinical expectations passed.
Challenge evidence is not comprehensively relevance-labelled, so no retrieval precision/coverage
claim is made from it. Literal provenance and brief validity are checked separately.

## Label interpretation

The old labels produced 10/11 exception precision (90.91%) because GT-B06 expects a FOUND scheduled
plan but lists no expected exception. `METRICS.md` scores **surfaced context**, not an adjudicated
exception. The versioned amendment lists that context while keeping procedure consistency CONFLICTING
and outcome EVIDENCE_CONFLICTING. Under amended labels the same outputs yield 11/11 (100%) precision;
this is a label consistency correction, not improved engine performance. Historical reports retain
their original labels and scores. Evaluation labels must never be sent to the API or ingested.

## Remaining work for Person 1

| Case | Documented limitation | Current safe behaviour |
|---|---|---|
| P11 | Active resuscitation expressed as "Resusitasi dilakukan ... henti napas" lacks the recognised wording pattern | Emergency NOT_FOUND → human review |
| P17 | Chronicity expressed as a disease lasting five years lacks a chronic phrase | Chronic context NOT_FOUND → human review |
| P23 | Planned procedure code is in a different sentence from the plan | Schedule consistency NOT_FOUND → human review |
| P28 | Exam-result follow-up described as reviewing imaging findings lacks the recognised wording pattern | Exam follow-up NOT_FOUND → human review |

These expectations remain failing and are retained for a future semantic passage classifier or
source-validated relation extraction. Do not relabel them as negatives or add broad keyword matches
solely to increase accuracy. CI permits only their specific documented safe states, fails new gaps
or any unsafe closure, and permits genuine improvements. Review the conservative sentence-wide
historical/conditional emergency guard when extending language coverage.

## Handoff to Person 2

Use the official dataset `data/synthetic/v0.1.0`, corpus `pc-0.1.1` and API contract in
`packages/shared-types/openapi.json`. `evaluation/person3-qa/2026-10-08/golden/` contains backend
timeline, brief, evidence and check results for official golden A–E. These are reference artifacts,
not replacement HTTP fixtures or application seed input.

- [ ] Verify A–E in the Case Queue and correct readmission/fragmentation labels.
- [ ] Verify timeline and source links against the delivered golden reference artifacts.
- [ ] Show NOT_FOUND and UNAVAILABLE distinctly; keep conflicting evidence on both sides visible.
- [ ] Show human review clearly and avoid claim/fraud/payment verdicts.
- [ ] Run actual HTTP/PostgreSQL integration and browser E2E when the stack is available.

This delivery exercised the CLI/domain pipeline and API DTO generation, not HTTP persistence or
browser UI. Docker's local daemon was unavailable; no database integration test is claimed here.
UI/domain wording review and browser E2E remain open until Person 2's frontend is ready.

## Reproduce without a frontend or API key

From the repository root:

```bash
uv run --project apps/api python evaluation/run_person3_qa.py --out evaluation/runs/person3-qa
uv run --project apps/api pytest -q -p no:cacheprovider apps/api/tests/unit data/generator/tests evaluation/tests
uv run --project apps/api ruff check apps/api/src apps/api/tests apps/api/alembic
```

The runner never requests a model client. CI sets `EPISIGHT_LLM_PROVIDER=none` and executes it after
the original deterministic regression. For historical FULL replay use its report's `VALIDATION.md`.
`acceptance.json` records the base Git commit, whether runtime source is modified, source hashes,
both label interpretations and exact misses; the committed QA bundle contains the raw outputs.

## Delivery checklist

- [x] Synthetic generator and independent challenge are reproducible.
- [x] Official golden cases, screening fixtures and original labels preserved.
- [x] GT-B06 interpretation audited and amended with separate version/provenance.
- [x] New unsafe wording closures fixed and regression-tested.
- [x] Ground truth isolation and governance checks pass.
- [x] CLI end-to-end golden QA and durable evidence delivered.
- [x] Existing benchmark/replay reproduced; no new paid model calls.
- [x] Known semantic limitations explicitly documented with owners and cases.
- [x] Ready for code review and commit; stage 5 intentionally skipped.
- [ ] HTTP/PostgreSQL integration and frontend E2E acceptance (Person 1/2).
