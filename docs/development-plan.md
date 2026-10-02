# EPISIGHT — Person 1 Development Plan (Tracked)

> **Owner:** Person 1 (Backend, Agent & Core Intelligence)
> **Created:** 2026-10-01 · **Last updated:** 2026-10-02
> **Derived from:** [01_PERSON_1_BACKEND_AGENT.md](01_PERSON_1_BACKEND_AGENT.md) phases 0–12 and the context doc's phases 0–5, re-sequenced into milestones that each end in something demonstrable.
> **Design references:** [architecture.md](architecture.md) · [decisions.md](decisions.md) · [data-contract.md](data-contract.md) · [api-contract.md](api-contract.md)

---

## How to Track Progress

- **Status markers:** `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked (add a reason) · `[-]` dropped (add a reason).
- **Task IDs** (`BE-<milestone>.<n>`) are stable. Reference them in branch names (`be/6.5-rule-planner`), commit messages, and PR titles.
- When a task is done, tick it, add the PR/commit reference after it (`— #12` or `— abc1234`), and add a line to the [Progress Log](#progress-log).
- A milestone is done only when every item in its **Exit criteria** is ticked.
- New work discovered mid-milestone gets a new ID at the end of that milestone. Never renumber.
- Blocked tasks point at a decision (D-xx, [decisions.md](decisions.md)) or a handoff (HO-xx, below). Decision changes go to `decisions.md`, not into this plan or the architecture doc.
- Decisions are made by Person 1 as technical owner; Person 2/3 are informed, not asked to approve.
- Work happens on branches (Phase 0 branch: `phase0/contracts`). Commits are GPG-signed, so commit from your own terminal.

## Milestone Overview

| Milestone | Scope | Maps to (context doc phase) | Priority | Status |
|---|---|---|---|---|
| **M0** | Contract lock | Phase 0 | P0 | `[~]` (D-16, D-18 open) |
| **M1** | Backend foundation + read API on fixtures | Phase 1 | P0 | `[x]` |
| **M2** | Temporal screening | Phase 1 | P0 | `[~]` (core done in M1; P3 fixtures pending) |
| **M3** | Episode reconstruction | Phase 1 | P0 | `[x]` |
| **M4** | Evidence ledger + retrieval | Phase 2 | P0 | `[x]` |
| **M5** | Agent tools | Phase 2 | P0 | `[x]` |
| **M6** | Case state, safety envelope, AI planner, orchestrator, stopping (core) | Phase 2 | P0 | `[x]` (live-model check pending a key) |
| **M7** | Reviewer brief + provenance API | Phase 3 | P0 | `[~]` (done except P1 review actions / meta enums) |
| **M8** | Evaluation integration + ablation | Phase 3–4 | P1 (runner is P0 for golden checks) | `[~]` (runner done; needs Person 3 harness + dataset) |
| **M9** | Robustness, regression, stabilization | Phase 4–5 | P0/P1 | `[ ]` |
| **M10** | LLM passage classifier + optional brief paraphrase | — | P1/P2 | `[ ]` |

**Critical path:** M0 → M1 → M2 → M3 → M4/M5 (partly parallel) → M6 → M7 → M8 → M9. M1–M5 build the deterministic backbone first. The AI planner (M6) is built on top of the safety envelope, and the rule planner lands before it so every later milestone has a working fallback. M10 comes only after M9's golden baseline is green.

**Integration checkpoints (for Person 2):**

- **CP-1** (early M1, after BE-1.4 + BE-1.11): mock fixtures + generated TS types published. The frontend builds all four screens against them.
- **CP-2** (end of M1): real `GET /cases`, `/cases/{id}`, `/episodes` served from the fixture dataset.
- **CP-3** (end of M6): `POST /investigate` + polling `GET /investigation` work for golden cases A–E.
- **CP-4** (end of M7): brief + evidence detail live. Full four-screen flow runs end-to-end.

---

## M0 — Contract Lock

- [x] **BE-0.1** Read sources, inspect repo, reconcile discrepancies → [architecture.md §2](architecture.md)
- [x] **BE-0.2** Draft architecture, data contract, API contract, and this plan
- [x] **BE-0.3** Lock data decisions and freeze [data-contract.md](data-contract.md) at v1
- [x] **BE-0.4** Lock API decisions and freeze [api-contract.md](api-contract.md) at v1
- [x] **BE-0.5** Freeze enums (data-contract §4), including progress transition rules
- [x] **BE-0.6** Revise the boundary to "rules control the safety envelope, AI controls adaptive investigation" ([architecture.md §3, §6, §7.4](architecture.md)); D-07 locked
- [-] **BE-0.7** ~~Hand-author mock fixtures~~: moved to BE-1.11 (generated from the Pydantic models instead of hand-written, to avoid doing the work twice)
- [ ] **BE-0.8** Team agrees on the timebox (D-16) and cuts P1/P2 scope accordingly
- [x] **BE-0.9** Create [decisions.md](decisions.md) as the single decision log
- [~] **BE-0.10** Commit Phase 0 docs on branch `phase0/contracts` — ca231d8; push + PR still pending
- [~] **BE-0.11** Resolve D-18: providers implemented (Anthropic default + OpenAI adapter); API key owner and budget still open

**Exit criteria**
- [x] Contracts frozen at v1 (shape questions are answered by [api-contract.md](api-contract.md); fixtures follow in BE-1.11).
- [x] Person 3 has a frozen data contract to generate against ([data-contract.md](data-contract.md)).
- [ ] No entity field or enum is still ambiguous. Every blocking D-xx is closed. *(remaining: D-16 deadline, D-18 LLM provider/key; neither blocks M1–M5)*

---

## M1 — Backend Foundation

- [x] **BE-1.1** Scaffold repo layout (architecture §5): `.gitignore`, `.editorconfig`, root `README.md` skeleton, `docker-compose.yml` (Postgres dev + test DBs)
- [x] **BE-1.2** `apps/api` uv project (Python 3.12 pinned via `.python-version`), ruff, pytest. No Makefile (Windows); the `episight` CLI + README commands cover dev/test/lint/seed/reset
- [x] **BE-1.3** FastAPI app factory, `pydantic-settings` config, `GET /health`, JSON logging with `request_id`, error envelope + exception handlers, CORS for `localhost:3000`
- [x] **BE-1.4** `contracts/` Pydantic enums + DTOs; `episight export-contract` writes `openapi.json` + `src/index.ts`; `pnpm generate` writes `src/api.d.ts`; drift caught by `test_contract.py` (no CI yet)
- [x] **BE-1.5** SQLAlchemy models + Alembic initial migration for all tables in data-contract §5
- [x] **BE-1.6** Ingest CLI: `episight seed --dataset <dir> --policies <dir>` validates the manifest, schema, FKs, and forbidden fields; idempotent; refuses `data/ground-truth/**`; `episight db reset`
- [x] **BE-1.7** Interim dev fixture dataset (golden A–E, hand-authored) in `apps/api/tests/fixtures/dataset/`, so work is not blocked on HO-P3-1
- [x] **BE-1.8** Read endpoints E2, E3, E4 (ANCHOR + CONTEXT roles; RELATED arrives in M3), E7/E8 real queries (empty until M6). E5/E6/E9 return contract errors (503 / `RUN_NOT_FOUND` / `BRIEF_NOT_READY`) until M6/M7
- [x] **BE-1.9** Isolation tests: no `ground[-_]truth` reference in `src/`; no `evaluation` import; forbidden-field rejection
- [x] **BE-1.10** Module import-boundary test (domain modules do not import `api`/`db`; `agent/envelope` does not import `llm`)
- [x] **BE-1.11** Mock fixtures in `packages/shared-types/fixtures/`: real list/detail/timeline for all 6 interim cases + one scripted Golden-A investigation (running, completed, evidence, evidence detail, brief), all validated against the models, with a drift test. B–E investigation fixtures will be regenerated from real engine runs after the vertical slice

**Exit criteria**
- [x] Clean-room run (fresh DB volume + fresh venv) following README: `docker compose up -d --wait` → `uv sync` → `episight db upgrade` → `episight seed` → `/health` ok, 6 cases. *(Repeat from a true `git clone` once committed.)*
- [x] All baseline endpoints respond with typed data; OpenAPI renders at `/api/v1/docs`.
- [x] CP-1 + CP-2 ready for Person 2 (fixtures/types + real `/cases`, `/cases/{id}`, `/episodes`).

---

## M2 — Temporal Screening

- [x] **BE-2.1** Normalization: dedupe duplicate episode rows; record `MISSING_TIMESTAMP` / `DUPLICATE_EPISODE_ROW` as data-quality issues (never silently dropped)
- [x] **BE-2.2** Readmission rule (D-02), versioned `rule_id`
- [x] **BE-2.3** Fragmentation rule (D-02), versioned `rule_id`
- [x] **BE-2.4** Chain grouping (D-03) + deterministic `case_id`
- [x] **BE-2.5** Structured `signal_details` (per-pair matched fields, interval, params)
- [~] **BE-2.6** Idempotent case persistence (via `episight seed`, which re-screens); separate `episight screen` and E14 dropped unless needed (D-16)
- [x] **BE-2.7** Unit tests: inside, at, and outside the threshold; same patient/different provider; same provider/different diagnosis; inpatient/outpatient mismatch; duplicate rows; missing timestamps
- [ ] **BE-2.8** Run Person 3's screening fixtures (HO-P3-2)

**Exit criteria**
- [ ] Person 3's golden screening fixtures pass.
- [x] Screening is deterministic (two runs give identical case sets and IDs).
- [x] No verdict wording appears anywhere in signal output.

---

## M3 — Episode Reconstruction

- [x] **BE-3.1** `EpisodeGraph` domain abstraction (patient → episodes → provider/dx/px/claim/notes/evidence), with no NetworkX types leaking out
- [x] **BE-3.2** Reconstruction service: candidate window around anchors, chronological sort, intervals, `role`, `relation_reasons`, preserved source IDs
- [x] **BE-3.3** Full `EpisodeTimeline` DTO for E4
- [x] **BE-3.4** Tests: 2 related; 3+ related; similar-but-unrelated; same dx/wrong provider; missing procedure; out-of-order timestamps
- [x] **BE-3.5** Expose `reconstructed_episode_ids` for the Episode Recall metric

**Exit criteria**
- [ ] Golden cases reconstruct the expected episode sets.
- [ ] The timeline response is stable (contract test).

---

## M4 — Evidence Ledger & Retrieval

- [x] **BE-4.1** Evidence repository: deterministic `evidence_id`, dedupe + `surfaced_in_steps`, provenance validation (dangling `source_id` is rejected), immutability
- [x] **BE-4.2** Text utilities: Indonesian-aware normalizer/tokenizer, sentence segmentation with char offsets (D-08)
- [x] **BE-4.3** Clinical note retriever: availability inventory + BM25 over case-scoped sentences (D-09)
- [x] **BE-4.4** Context matcher: lexicon/patterns per context type (emergency, chronic, scheduled, supporting-exam follow-up, clinical justification, risk indicators) with a negation window and stance output (HO-P3-4)
- [x] **BE-4.5** Policy ingest + BM25 index, version/effective-date metadata, section-level citations (HO-P3-3)
- [x] **BE-4.6** E7 `GET /cases/{id}/evidence` and E8 `GET /evidence/{id}` with full `source` payload
- [x] **BE-4.7** Tests: empty retrieval, unavailable note, negated phrase, duplicate hit, excerpt equals literal source substring

**Exit criteria**
- [ ] Clinical retrieval surfaces the expected passages on golden cases.
- [ ] Policy retrieval returns sourceable, versioned sections.
- [ ] 100% of ledger items resolve to a stored source.

---

## M5 — Agent Tools

- [x] **BE-5.1** Tool framework: `ToolSpec` (name, reviewer label, input/output models, resolvable requirements, permission scope), `ToolResult` envelope, timeout wrapper, allowlisted registry
- [x] **BE-5.2** `get_episode_history`
- [x] **BE-5.3** `compare_diagnosis`
- [x] **BE-5.4** `compare_procedures` (including planned-vs-performed)
- [x] **BE-5.5** `get_provider_context`
- [x] **BE-5.6** `retrieve_clinical_evidence`
- [x] **BE-5.7** `retrieve_policy`
- [x] **BE-5.8** `find_supporting_evidence`
- [x] **BE-5.9** `find_exception_evidence`
- [x] **BE-5.10** Tests per tool: valid input, missing source, empty retrieval, malformed case, unsupported case type, duplicate evidence; outputs JSON-serializable

**Exit criteria**
- [ ] Every tool is typed in and out, reports failure explicitly, and never invents records.

---

## M6 — Case State, Orchestrator & Stopping (core)

- [x] **BE-6.1** Versioned requirement catalog per signal type (architecture §7.1)
- [x] **BE-6.2** `CaseState` initializer from screening + reconstruction
- [x] **BE-6.3** Pure state reducer: `ToolResult` → requirement transitions, evidence partitions, known facts, unresolved questions, spawned requirements
- [x] **BE-6.4** Conflict detection (architecture §7.4)
- [x] **BE-6.5** Rule planner (deterministic fallback and CI mode): fixed priority order, full-coverage searches, repeat guard, reviewer-facing `reason`
- [x] **BE-6.6** Stopping policy S1–S7 (architecture §7.5), fully unit-tested per rule
- [x] **BE-6.7** Orchestrator loop: per-step persistence of action + state snapshot, max steps, run timeout, bounded retry, failure → explicit state (D-13)
- [x] **BE-6.8** Async runtime: E5 (202 + 409 guards), E6 polling view, stale-run recovery on startup
- [x] **BE-6.9** Golden behavior tests A–E assert the outcome, stop reason, key requirement states, and that the trails differ across cases (D-01, D-05)
- [x] **BE-6.10** Modes `RULES_ONLY`, `RULES_RETRIEVAL`, `FULL_RULE_PLANNER`, `FULL` (architecture §11)
- [x] **BE-6.11** Safety envelope: allowed-action generator with scope bounds + requirement dependency graph + coverage tracking (architecture §7.1, §7.3)
- [x] **BE-6.12** Action validator V1–V9, including the bounded re-ask and rule-planner fallback path (architecture §7.4)
- [x] **BE-6.13** `llm/` adapter: Anthropic SDK client, per-step structured-output schema (`action_id` enum = allowed set), refusal/timeout/error → fallback, key from env only (D-18)
- [x] **BE-6.14** AI planner: versioned system prompt + state serializer (no ground truth), output → proposal, `planner_note`/`priority_ranking`/`skip` handling
- [x] **BE-6.15** Record/replay of planner calls (`planner_recordings`), with a replay mode that fails on a miss (D-21)
- [x] **BE-6.16** Planner telemetry in the trail and runner output (`planner_source`, validation errors, latency)
- [x] **BE-6.17** Envelope adversarial tests: the planner returns a disallowed tool, a non-open requirement, out-of-scope episodes, a duplicate call, a material skip, or a premature "no further action", and each one is rejected and falls back

**Exit criteria**
- [ ] A: context surfaced via notes · B: `HUMAN_REVIEW_REQUIRED` / `EVIDENCE_PATHS_EXHAUSTED`, gaps `NOT_FOUND` · C: scheduled context + schedule consistency · D: `EVIDENCE_UNAVAILABLE` · E: `EVIDENCE_CONFLICTING`. These pass in `FULL_RULE_PLANNER` **and** in `FULL` (live and replay).
- [ ] The AI planner visibly adapts: across A–E, trails differ in order and scope, driven by state.
- [ ] With the LLM disabled or failing, every run still completes through the fallback.
- [ ] No infinite loops (a property test with random tool outcomes always terminates ≤ `max_steps`).
- [ ] `missing` is never converted to `false`/legitimate, and `conflicting` is never collapsed.
- [ ] CP-3 is delivered to Person 2.

---

## M7 — Reviewer Brief & Provenance

- [x] **BE-7.1** Deterministic brief builder from persisted state (api-contract §4.6)
- [x] **BE-7.2** Brief validator: evidence-backed material statements, banned phrases (EN + ID), gap completeness, conflict completeness; failure → `HUMAN_REVIEW_REQUIRED` + marked fallback
- [x] **BE-7.3** Persist brief; regenerate from state (the regenerated brief is identical); E9
- [x] **BE-7.4** Trail in E6 includes all actions; E13 run history
- [ ] **BE-7.5** (P1) Review actions E11/E12 (D-14)
- [ ] **BE-7.6** (P1) E10 `/meta/enums` with reviewer-facing labels
- [x] **BE-7.7** Contract tests: fixtures regenerated from real models; TS types in sync

**Exit criteria**
- [ ] Traceability = 100% of material statements on golden cases.
- [ ] No brief can contain verdict or payment language (tested).
- [ ] CP-4: the four-screen flow runs end-to-end with Person 2.

---

## M8 — Evaluation Integration & Ablation

- [x] **BE-8.1** `episight batch --mode --cases --out` producing runner output (data-contract §6), including the screening block and version header
- [ ] **BE-8.2** Agree on the output schema with Person 3's harness; run the harness on golden A–E
- [x] **BE-8.3** (P1) Ablation runs: `RULES_ONLY` / `RULES_RETRIEVAL` / `FULL_RULE_PLANNER` / `FULL` on the full benchmark; `FULL` repeated live to report variance
- [ ] **BE-8.4** Failure analysis with Person 3; log defects as new `BE-9.x` tasks
- [ ] **BE-8.5** (P1) 20+ case benchmark runs within an acceptable time (target < 60 s total in deterministic mode)
- [ ] **BE-8.6** Record the regression baseline in `evaluation/` (with dataset/corpus/code versions)

**Exit criteria**
- [ ] Batch runs need no manual steps and are reproducible (same inputs → same output apart from timings).

---

## M9 — Robustness, Regression & Stabilization

- [ ] **BE-9.1** Failure tests: DB unavailable (503), empty retrieval, malformed note, policy corpus missing, tool exception, invalid structured output, timeout, max steps, repeated evidence, conflicting evidence
- [ ] **BE-9.2** Golden regression suite in CI (or `make regress`), which fails on any golden-case behavior change
- [ ] **BE-9.3** Determinism check: run the golden set twice and diff (excluding timings)
- [ ] **BE-9.4** README setup validated from a clean clone on a second machine or by a teammate
- [ ] **BE-9.5** Governance pass with Person 3 (no real data, no verdict endpoints, ground truth unreachable)

**Exit criteria (= Person 1 Definition of Done, 01 doc)**
- [ ] Backend starts from documented commands; DB recreate + seed works.
- [ ] Screening is deterministic and tested; reconstruction matches golden cases.
- [ ] State is explicit and inspectable; tools are chosen from gaps; dual evidence is surfaced.
- [ ] Missing and conflicting evidence are represented correctly; stopping is bounded.
- [ ] The brief is structured and source-backed; provenance is queryable.
- [ ] The batch evaluation runs unattended; all golden cases behave as expected.

---

## M10 — LLM Passage Classifier & Brief Paraphrase (P1/P2, after M9 baseline)

> The AI planner moved to M6 (D-07). M10 covers only the remaining optional LLM uses.

- [-] **BE-10.1** ~~`llm/` adapter~~: moved to BE-6.13 (D-07)
- [ ] **BE-10.2** LLM passage classifier: returns verbatim span + stance; span string-matched against the source; bounded retry; rule fallback
- [-] **BE-10.3** ~~LLM planner tie-break~~: superseded by the AI planner in M6 (D-07)
- [ ] **BE-10.4** Extend record/replay (BE-6.15) to classifier calls
- [ ] **BE-10.5** Classifier on/off ablation within `FULL`; keep only if metrics improve (proposal §13)
- [ ] **BE-10.6** (P2) Optional LLM paraphrase of brief statements, with evidence IDs preserved and validated; template fallback

---

## Cross-Team Handoffs

| ID | From → To | Deliverable | Needed by | Status |
|---|---|---|---|---|
| HO-P2-1 | P1 → P2 | Mock fixtures + generated TS types | BE-1.11 (CP-1) | `[x]` |
| HO-P2-2 | P1 → P2 | Real read endpoints | BE-1.8 (CP-2) | `[x]` |
| HO-P2-3 | P1 → P2 | Investigation start + polling | BE-6.8 (CP-3) | `[x]` |
| HO-P2-4 | P1 → P2 | Brief + evidence detail | BE-7.3 (CP-4) | `[x]` |
| HO-P3-1 | P3 → P1 | Dataset v0 with golden cases A–E (data-contract format) | BE-1.6 (fixture fallback: BE-1.7) | `[ ]` |
| HO-P3-2 | P3 → P1 | Screening rule fixtures (edge cases) | BE-2.8 | `[ ]` |
| HO-P3-3 | P3 → P1 | Policy corpus v0 (curated Permenkes 26/2021 sections) | BE-4.5 | `[ ]` |
| HO-P3-4 | P3 → P1 | Clinical notes with varied phrasing/negations + context lexicon review | BE-4.4 | `[ ]` |
| HO-P3-5 | P3 → P1 | Ground-truth schema + expected golden behavior | BE-6.9, BE-8.2 | `[ ]` |
| HO-P1-P3 | P1 → P3 | Runner output for harness | BE-8.1 | `[x]` |

## Open Decisions Snapshot

Full log in [decisions.md](decisions.md). All decisions are locked except **D-16** (deadline: sizes the P1/P2 scope) and **D-18** (LLM provider, key, budget: needed by BE-6.13, so it does not block M1–M5).

## Progress Log

| Date | Task(s) | Note |
|---|---|---|
| 2026-10-01 | BE-0.1, BE-0.2 | Sources reviewed; architecture, data contract, API contract, and plan drafted. No implementation started. |
| 2026-10-01 | BE-0.6, BE-0.9 | Review feedback applied: the AI planner is core inside a deterministic safety envelope (D-07); status split into three fields (D-04); cases are episode groups (D-03); Case B → `EVIDENCE_PATHS_EXHAUSTED`; `decisions.md` created; docs moved to v0.2. |
| 2026-10-02 | BE-0.3–BE-0.6, BE-0.10 | Person 2/3 sign-off not required. Decisions locked except D-16/D-18; data and API contracts frozen at v1; architecture v1.0; mock fixtures moved to BE-1.11 (generated from models). |
| 2026-10-02 | D-16 | Deadline locked at ~48 h; build order: M1 → Golden A vertical slice → D/E → B/C → benchmark → polish. |
| 2026-10-02 | M1 (BE-1.1–1.11), BE-2.1–2.5, BE-2.7 | Backend foundation done on `m1/foundation`: compose Postgres (:5433), uv project (Python 3.12), FastAPI + error envelope + JSON logging, contract models, migration 0001, ingest/seed with validation, interim dataset (A–E + hard negatives), screening pulled forward from M2, read endpoints, contract export + TS types + fixtures. 124 tests pass; clean-room run verified. Python pinned to 3.12 after the clean-room run exposed a 3.13 OpenAPI drift. |
| 2026-10-02 | BE-3.1–3.4, BE-4.2, 4.4–4.6 | Reconstruction (ANCHOR/RELATED/CONTEXT, ICD-10 category relatedness, chronic-class codes) wired into the timeline; retrieval: sentence offsets, pure-Python BM25, context matcher with per-lexicon negation scope, policy index. Ledger/tools/state drafted, not yet wired or tested. 178 tests pass. |
| 2026-10-02 | M4, M5, BE-6.1–6.7, 6.9–6.12, 7.1–7.2 | Engine runs end-to-end in-process: 8 tools, provenance-checked ledger, reducer with coverage rule + dependency graph, envelope (allowed actions, V1–V9, S1–S8), rule planner, orchestrator, template brief + guardrail validator. All five golden cases produce their expected outcome on the interim data; 300 tests pass (incl. adversarial validator cases and random-planner termination). Rule planner shares a tool sequence for A and D (by design); sequence adaptivity is the AI planner's job. |
| 2026-10-02 | BE-6.8, BE-7.3, 7.4, 7.7 | Engine wired to DB and API: background runs with per-step persistence (state snapshots, append-only actions, evidence ledger rows, brief), start guards (409 in progress / already completed, rerun), run history (E13), startup recovery of interrupted runs, queued-run view. Mock fixtures now come from real engine runs for all 6 cases. Found and fixed: DB rows carried `signal_type` as a string. 394 tests pass; live server smoke test passed. |
| 2026-10-02 | BE-6.13–6.17, BE-0.11 (partial) | AI planner: vendor-neutral prompt + per-step strict JSON schema, envelope validation with one re-ask, rule fallback on any failure, record/replay (DB store for the API, JSON-dir store for batch). Adapters: Anthropic (`claude-opus-5-5`, effort low, structured outputs, server-side refusal fallback) and OpenAI (`gpt-4o`, strict json_schema). Added V5 guard: a narrowed note search must select an unread readable document. Tests never call a paid API. 433 tests pass. Live-model check waits for a key. |
| 2026-10-02 | BE-6.14 (tuning) | First live runs with OpenAI `gpt-4o-mini`: all five golden outcomes correct, 100% AI decisions, but 1–2 more steps than the rule planner (never skipped provider context; B and C hit 12/12). Fixes: envelope budget guard (optional questions not offered when remaining steps only cover open material ones; leftover optional questions marked SKIPPED at stop) and prompt `planner-2` (step cost, optional questions, order by most decisive source). Re-run: all five correct, steps equal to the rule planner (10/11/11/10/5), ~1.5 s per step, 2 single retries accepted. 435 tests pass. |
| 2026-10-02 | BE-8.1, BE-8.3, BE-3.5 | Batch runner `episight batch`: all four ablation modes from dataset files (no DB), Data Contract §6 JSON + CSV + summary.md, repeats for AI-planner variance, per-repeat recordings with replay. First live ablation on interim data (FULL = OpenAI gpt-4o-mini): avg steps RULES_ONLY 4.0 (all EVIDENCE_UNAVAILABLE / NO_ACTIONABLE_GAP), RULES_RETRIEVAL 11.3, FULL_RULE_PLANNER 9.7, FULL 9.7 (58 AI steps, 0 fallbacks); same outcomes for the last three modes; ~15 s per FULL case. 448 tests pass. |
