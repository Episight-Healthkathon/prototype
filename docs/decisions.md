# EPISIGHT — Decision Log

> One entry per decision. Architecture and contract docs **link here** instead of restating decisions, so they don't drift.
> **Status values:** `OPEN` (not decided) → `LOCKED` (decided by Person 1 as technical owner; no Person 2/3 sign-off required) · `SUPERSEDED` (replaced by a later entry; never delete).
> **Owners** listed per entry are the people to *inform* of the decision, not approvers.
> **Changing a LOCKED decision:** add a new entry that supersedes it. Do not edit the old one.

## Summary

| ID | Title | Status |
|---|---|---|
| D-01 | Five golden cases | LOCKED |
| D-02 | Screening thresholds | LOCKED |
| D-03 | Cases are episode groups | LOCKED |
| D-04 | Separate progress, outcome, stop reason | LOCKED |
| D-05 | Case B expected behavior | LOCKED |
| D-06 | Review-priority labels | LOCKED (deferred) |
| D-07 | Role of the LLM: AI planner inside a deterministic envelope | LOCKED |
| D-08 | Language of clinical notes and policy corpus | LOCKED |
| D-09 | Retrieval: in-process BM25 | LOCKED |
| D-10 | Monorepo deviation | LOCKED |
| D-11 | Structured admission type is not a shortcut | LOCKED |
| D-12 | Unavailable vs not found | LOCKED |
| D-13 | Limits and timeouts | LOCKED |
| D-14 | Human review actions | LOCKED |
| D-15 | Auth | LOCKED |
| D-16 | Deadline / timebox: ~48 h, vertical slice first | LOCKED |
| D-17 | Python version | LOCKED |
| D-18 | LLM provider and model | **OPEN** |
| D-19 | No model training / fine-tuning | LOCKED |
| D-20 | Async runtime is a prototype constraint | LOCKED |
| D-21 | Regression determinism via record/replay | LOCKED |

Locked 2026-10-02 unless noted.

---

### D-01 — Five golden cases
- **Status:** LOCKED · **Owners:** P3 (primary), P1 · **Date:** 2026-10-01
- **Decision:** Golden set = **A** Legitimate Readmission, **B** Potential Fragmentation, **C** Scheduled Procedure, **D** Missing Evidence, **E** Conflicting Evidence. Benchmark scenarios are identified by named classes (e.g., `LEGIT_STAGED_PROCEDURE`), never by letters.
- **Reason:** Resolves the context doc vs proposal conflict over Case D without dropping either scenario. The Definition of Done needs a fixed conflicting-evidence regression case.
- **Consequences:** Expected behaviors in [architecture.md §7.7](architecture.md). Mock fixtures cover A–E.

### D-02 — Screening thresholds
- **Status:** LOCKED · **Owners:** P1, P3 · **Date:** 2026-10-01
- **Decision:** Readmission = inpatient → inpatient, same `provider_id`, same primary ICD-10 code, `admission(ep2) − discharge(ep1) ≤ 30` calendar days. Fragmentation = outpatient → outpatient, same provider, same primary ICD-10 code, `visit(ep2) − visit(ep1) ≤ 7` days. Boundaries are inclusive. "Related diagnosis" (same ICD-10 3-character category) exists as a config flag, off by default.
- **Reason:** Follows Permenkes 26/2021 definitions (proposal §3). Exact-code matching is a deterministic **prototype baseline on synthetic data**. We do not claim it is correct production behavior.
- **Consequences:** Rule IDs and versions are recorded in `signal_details`.

### D-03 — Cases are episode groups
- **Status:** LOCKED · **Owners:** P1, P3 · **Date:** 2026-10-01
- **Decision:** A case is a **connected episode group** (chain) with an anchor signal, not a single pair. The case stores `episode_group_ids`, the list of qualifying `pairs`, and a `primary_pair` (the qualifying pair with the shortest interval; ties broken by earliest date). The UI may focus on the primary pair, while the graph and reconstruction keep every related episode.
- **Reason:** Three or more episodes within the thresholds are one clinical story. Splitting them into pairs would duplicate cases and fragment evidence.
- **Consequences:** `case_id` hashes the sorted `episode_group_ids`; ground truth joins on `anchor_episode_ids` (= group).

### D-04 — Separate progress, outcome, stop reason
- **Status:** LOCKED · **Owners:** P1, P2 · **Date:** 2026-10-01
- **Decision:** Three fields instead of one enum.
  - `progress_status`: `FLAGGED`, `INVESTIGATING`, `BRIEF_READY`, `INVESTIGATION_FAILED`
  - `outcome`: `EVIDENCE_SUFFICIENT`, `EVIDENCE_CONFLICTING`, `EVIDENCE_UNAVAILABLE`, `HUMAN_REVIEW_REQUIRED`
  - `stop_reason`: see [data-contract.md §4](data-contract.md)
  - Plus technical `run_status` on each run.
- **Reason:** A single enum loses the outcome once the brief is ready. All seven statuses from context doc §9 are preserved across `progress_status` and `outcome`. `INVESTIGATION_FAILED` is added so a system failure never looks like a conclusion (Person 2 plan, Phase 7).
- **Consequences:** Documented deviation from context doc §9's single list. The UI badge is derived from both fields.

### D-05 — Case B expected behavior
- **Status:** LOCKED · **Owners:** P3 (primary), P1 · **Date:** 2026-10-01
- **Decision:** The agent keeps searching for justification until every context requirement has full coverage. If justification is still absent, the result is `progress_status = BRIEF_READY`, `outcome = HUMAN_REVIEW_REQUIRED`, `stop_reason = EVIDENCE_PATHS_EXHAUSTED`, and a brief that states the **unresolved risk** and "no explaining context found in available sources". Never "risk confirmed".
- **Reason:** No evidence ≠ legitimate, and no evidence ≠ fraud.

### D-06 — Review-priority labels
- **Status:** LOCKED (deferred beyond P0) · **Owners:** P2, P3
- **Decision:** Not in P0. If adopted, a deterministic function of requirement states, labelled "review priority", never a numeric risk or fraud score.

### D-07 — Role of the LLM: AI planner inside a deterministic envelope
- **Status:** LOCKED · **Owners:** Team · **Date:** 2026-10-01 · **Supersedes:** v0.1 wording "rules make all the decisions"
- **Decision:** *Rules control the safety envelope; AI controls adaptive investigation within it.* Deterministic code governs screening, state integrity, allowed actions, state transitions, and safety-critical stopping. An AI planner performs evidence-gap prioritization, next-tool selection, and search scoping inside that envelope. Every proposal is validated (V1–V9, [architecture.md §7.4](architecture.md)), and a deterministic rule planner is the fallback.
- **Reason:** The evidence-gap-driven agent is the core differentiator in the proposal, and the ablation must be able to show value beyond a deterministic workflow. An optional, advisory LLM would make "Full EPISIGHT" indistinguishable from rules.
- **Consequences:** The AI planner is P0 (M6). The `FULL_RULE_PLANNER` ablation variant is added. The LLM passage classifier remains P1.

### D-08 — Language
- **Status:** LOCKED · **Owners:** P3, P2 · **Date:** 2026-10-01
- **Decision:** Synthetic clinical notes and the policy corpus are primarily in **Bahasa Indonesia**. Medical terms, drug names and codes may appear in English/Latin as they realistically do. Code, enums and API field names are in English. UI language is Person 2's call.

### D-09 — Retrieval: in-process BM25
- **Status:** LOCKED · **Owners:** P1, P3 · **Date:** 2026-10-01
- **Decision:** `rank-bm25` in-process for notes and policy. No vector DB. Revisit pgvector only if Person 3's retrieval-quality labels show BM25 is the bottleneck.

### D-10 — Monorepo deviation
- **Status:** LOCKED · **Owners:** Team · **Date:** 2026-10-02
- **Decision:** A single Python package in `apps/api` whose module boundaries mirror `packages/agent`, `packages/episode-graph`, and `packages/retrieval`. Backend tests are colocated in `apps/api/tests`. `packages/shared-types` holds TS types generated from OpenAPI.

### D-11 — Structured admission type is not a shortcut
- **Status:** LOCKED · **Owners:** P3 · **Date:** 2026-10-01
- **Decision:** `episodes.admission_type` may exist as source metadata, but on its own it can **never** move `EMERGENCY_CONTEXT` to `FOUND`. It is recorded as `INFORMS` evidence, and resolution requires clinical-note evidence. In golden Case A, `admission_type` is null, so emergency context must be found through note retrieval. Where it is present, it may contradict notes (a natural source of conflict cases).
- **Reason:** Otherwise the investigation feature is not actually exercised.

### D-12 — Unavailable vs not found
- **Status:** LOCKED · **Owners:** P3, P2 · **Date:** 2026-10-01
- **Decision:** The `clinical_notes` table acts as the **document registry**. A registered document with `availability ∈ {UNAVAILABLE, RESTRICTED}` (and `text = null`) makes the affected requirements `UNAVAILABLE`. A normal search over available sources with no relevant hit gives `NOT_FOUND`, and only with full coverage. Expected-document rule: an inpatient episode with no registered `DISCHARGE_SUMMARY` is treated as an unavailable expected document, not as "nothing to find".
- **Consequences:** The UI shows unavailable and not-found differently, and neither is shown as a negative finding.

### D-13 — Limits and timeouts
- **Status:** LOCKED · **Owners:** P1, P2 · **Date:** 2026-10-02
- **Decision:** `max_steps = 12`; tool timeout 10 s; planner call timeout 30 s; one re-ask per step; run timeout 180 s (`FULL`) / 60 s (rule modes).

### D-14 — Human review actions
- **Status:** LOCKED · **Owners:** P2 · **Date:** 2026-10-02
- **Decision:** P1 priority: `MARK_REVIEWED`, `ADD_NOTE`, `REQUEST_MORE_EVIDENCE` only. Approve, reject and fraud actions are not representable.

### D-15 — Auth
- **Status:** LOCKED · **Owners:** Team · **Date:** 2026-10-02
- **Decision:** No auth in P0; the UI shows a prototype banner. Optional fixed reviewer-role header in P1.

### D-16 — Deadline / timebox
- **Status:** LOCKED · **Owners:** Team · **Date:** 2026-10-02
- **Decision:** Submission horizon is **about 48 hours** (from 2026-10-02).
- **Implications:**
  - Priorities: **P0** = one end-to-end flow works (Golden Case A: queue → timeline → run investigation → evidence → brief). **P1** = all five golden cases work. **P2** = larger benchmark + polish. Features that don't strengthen the core EPISIGHT mechanism are dropped if time runs out.
  - Build order: M1 foundation → Golden Case A vertical slice → Cases D/E (unavailable / conflicting) → Cases B/C → benchmark → polish. No serial "finish every milestone" execution.
  - The team works in parallel: Person 2 builds on the generated mocks and frozen API contract; Person 3 builds the golden cases, notes, policy corpus and ground truth. Integration swaps mocks for the real API and interim fixtures for the official dataset as each becomes available.
  - Deprioritized: review actions (D-14), `/meta/enums`, streaming, LLM passage classifier (M10), infrastructure beyond the prototype.

### D-17 — Python version
- **Status:** LOCKED · **Owners:** P1 · **Date:** 2026-10-02
- **Decision:** Python 3.12 via `uv`. 3.11 is also supported.

### D-18 — LLM provider and model
- **Status:** **OPEN** · **Owners:** Team (needs API access and budget)
- **Decision:** Claude via the official `anthropic` Python SDK, model `claude-opus-5-5` at `low` effort for the per-step planner. Structured outputs for the decision object (forced `tool_choice` and `temperature` are not supported on current models). Refusals go to rule fallback. The key comes only from the `ANTHROPIC_API_KEY` env var. Moving to a cheaper or faster model (e.g., `claude-sonnet-5-5`) is a team cost/latency decision, to be measured on the benchmark first.
- **Open questions:** Who provides the key? What is the budget per benchmark run?

### D-19 — No model training / fine-tuning
- **Status:** LOCKED · **Owners:** Team · **Date:** 2026-10-01
- **Decision:** No Kaggle-style training or fine-tuning in the prototype. Order of work: tool/LLM orchestration → retrieval → state representation and prompt design → benchmark → error analysis. Revisit only if error analysis shows a bottleneck that retrieval, state representation, tool interfaces, prompting, deterministic guardrails, or a more capable model cannot fix.

### D-20 — Async runtime is a prototype constraint
- **Status:** LOCKED · **Owners:** P1, P2 · **Date:** 2026-10-01
- **Decision:** In-process `asyncio` background task + frontend polling. No Celery or Redis. Explicitly documented as a prototype constraint: jobs are lost on restart (marked `INTERRUPTED`), duplicate starts are rejected with 409, and every run has a timeout. See [architecture.md §8](architecture.md).

### D-21 — Regression determinism via record/replay
- **Status:** LOCKED · **Owners:** P1, P3 · **Date:** 2026-10-02
- **Decision:** Planner requests/responses are recorded, keyed by `hash(model, prompt_version, payload)`. Regression and CI replay them, and a replay miss fails loudly. Golden assertions are behavioral. The live benchmark runs repeat `FULL` to report variance.
