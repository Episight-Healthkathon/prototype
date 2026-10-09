# Person 2 frontend handoff — 2026-10-08

Stages 1–8 implemented in `apps/web`:

| Stage | Delivered |
|---|---|
| 1 · Visual foundation | Supplied transparent logo, supplied workflow slide, native case-story slides, blue/navy/teal visual system, self-hosted Manrope |
| 2 · App foundation | Next.js, typed API client, same-origin proxy, navigation, health/readiness, explicit live/demo modes, errors/loading/empty states |
| 3 · Case queue | ID search, signal/progress/evidence filters, all contract sort options, 10-row pagination |
| 4 · Case context | Screening criteria, rule metadata, chronological anchor/related/context timeline, expandable diagnosis/procedure/claim/document details |
| 5 · Investigation | Start/rerun, 1-second active polling, evidence gap coverage, next action, categorized ledger, facts, action trail and planner/fallback transparency |
| 6 · Brief/provenance | Risk/context/policy/uncertainty sections, equal conflict sides, source drawer, literal highlights, all citations and print styling |
| 7 · Integration | Real FastAPI + PostgreSQL, official v0.1.0 dataset and pc-0.1.1 corpus, isolated episight_frontend database |
| 8 · QA/handoff | Build/type/lint, meaningful frontend tests, real API golden A–E verification and browser workflow/responsive checks |

The current preview is http://127.0.0.1:3001, API http://127.0.0.1:8000/api/v1.
Startup instructions are in `apps/web/README.md`.

## Verified API golden results

Mode: FULL_RULE_PLANNER. Five runs through the Next.js API proxy, including every
evidence-detail endpoint, persisted run history, missing case 404, completed-run 409,
queue filtering and pagination:

| Case | Outcome | Steps | Sources | Material statements with sources |
|---|---|---:|---:|---:|
| CASE-RA-0bbfc334 | EVIDENCE_SUFFICIENT | 10 | 13 | 9/9 |
| CASE-FR-83f41f66 | HUMAN_REVIEW_REQUIRED | 11 | 8 | 5/5 |
| CASE-RA-d7840713 | EVIDENCE_SUFFICIENT | 11 | 10 | 8/8 |
| CASE-RA-609280ef | EVIDENCE_UNAVAILABLE | 10 | 4 | 3/3 |
| CASE-RA-608764ca | EVIDENCE_CONFLICTING | 5 | 6 | 8/8 |

This validates frontend integration and deterministic backend behavior. It is not
another live LLM benchmark. The running QA backend explicitly disables paid planner calls.

## Product boundaries

Outcomes describe evidence, not fraud or payment decisions. NOT_FOUND, UNAVAILABLE,
CONFLICTING and FAILED remain distinct. Planner notes are never evidence. No reviewer
notes are falsely persisted. No real Mobile JKN/BPJS patient data is integrated.

Both the UI and fixture generator read runtime datasets, never `data/ground-truth`.
The existing shared types and interim fixtures are preserved.

## Local verification

- TypeScript and ESLint passed; production build passed.
- Six frontend tests cover official queue semantics, golden outcomes and citations,
  missing/conflicting evidence, Unicode offsets and offline playback transitions.
- Browser checks cover queue search, Case A brief, clinical-source highlight,
  investigation rerun with persisted history, demo playback and an unavailable API.
- Layouts inspected at real 1440px and 390px iframe viewports, plus the default app
  viewport. At 390px the case page has no body horizontal overflow. Conflict sources
  use equal-width columns. Clinical copy was enlarged after the batched visual scan.
- Temporary responsive QA page is removed after verification. Backend and frontend
  are left running for the user to try.
