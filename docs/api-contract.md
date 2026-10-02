# EPISIGHT — API Contract (Proposal)

> **Status:** **v1 FROZEN** (2026-10-02), `X-Contract-Version: 1`. Owned by Person 1. Any change requires a contract-version bump, regenerated TS types and fixtures, and notifying Person 2.
> **Canonical implementation:** Pydantic models in `apps/api/src/episight/contracts/`. The OpenAPI document at `/api/v1/openapi.json` is generated from them, and TypeScript types in `packages/shared-types` are generated from that. This document is the human-readable summary. If they disagree, raise it; don't guess.
> Enum values are defined in [data-contract.md §4](data-contract.md). Decisions (D-xx) are in [decisions.md](decisions.md).

---

## 1. Conventions

- Base path: `/api/v1`. JSON only. Field names in `snake_case`.
- Timestamps: ISO-8601 with offset. Durations are integer `*_ms` / `*_days` fields.
- Every response carries an `X-Request-ID` header and `X-Contract-Version: 1`.
- Lists use `{ "items": [...], "total": n, "limit": n, "offset": n }`.
- Unknown enum values: the frontend must render a neutral fallback. The backend only adds enum values with a contract-version bump.
- **Safety invariant:** no response contains a field, enum value, or action that expresses fraud, approval, rejection, or payment.

## 2. Error Envelope

```ts
interface ApiError {
  error: {
    code: ErrorCode;
    message: string;           // human-readable, safe to display
    details?: Record<string, unknown>;
    request_id: string;
  };
}

type ErrorCode =
  | "VALIDATION_ERROR"          // 422
  | "CASE_NOT_FOUND"            // 404
  | "EVIDENCE_NOT_FOUND"        // 404
  | "RUN_NOT_FOUND"             // 404
  | "BRIEF_NOT_READY"           // 409 — investigation not finished or never started
  | "INVESTIGATION_IN_PROGRESS" // 409 — start requested while a run is active
  | "INVESTIGATION_ALREADY_COMPLETED" // 409 — start without rerun=true
  | "SERVICE_UNAVAILABLE"       // 503 — DB/index not ready
  | "INTERNAL_ERROR";           // 500
```

## 3. Endpoints

| # | Method & path | Purpose | Priority | Screen |
|---|---|---|---|---|
| E1 | `GET /health` | Liveness + DB/index readiness | P0 | — |
| E2 | `GET /cases` | Case queue | P0 | Case Queue |
| E3 | `GET /cases/{case_id}` | Case detail / overview | P0 | Case Overview |
| E4 | `GET /cases/{case_id}/episodes` | Episode timeline | P0 | Episode Timeline |
| E5 | `POST /cases/{case_id}/investigate` | Start (or re-run) investigation | P0 | Investigation Workspace |
| E6 | `GET /cases/{case_id}/investigation` | Current state + trail of latest (or given) run | P0 | Investigation Workspace |
| E7 | `GET /cases/{case_id}/evidence` | Evidence ledger for a case | P0 | Workspace / Brief |
| E8 | `GET /evidence/{evidence_id}` | Evidence detail + provenance | P0 | Evidence drawer |
| E9 | `GET /cases/{case_id}/brief` | Reviewer brief | P0 | Reviewer Brief |
| E10 | `GET /meta/enums` | Enum values + reviewer-friendly labels | P1 | all |
| E11 | `POST /cases/{case_id}/reviews` | Record a human review action | P1 | Reviewer Brief |
| E12 | `GET /cases/{case_id}/reviews` | Review history | P1 | Reviewer Brief |
| E13 | `GET /cases/{case_id}/runs` | Run history | P1 | Workspace |
| E14 | `POST /admin/screening/run` | Re-run screening (dev only, disabled unless `EPISIGHT_ENV=dev`) | P1 | — |

### E1 `GET /health`

`200 { "status": "ok", "db": "ok", "policy_index": "ok", "dataset_version": "v0.1.0", "corpus_version": "pc-0.1.0" }`. Returns `503` with the same shape when a dependency is down.

### E2 `GET /cases`

Query: `signal_type?`, `progress_status?` (repeatable), `outcome?` (repeatable), `q?` (matches `case_id` or `patient_id`), `sort?` = `index_date|-index_date|min_interval_days|case_id` (default `-index_date`), `limit?` (default 50, max 200), `offset?`.

```ts
interface CaseSummary {
  case_id: string;
  signal_type: SignalType;
  patient_id: string;                 // pseudonymous
  provider: { provider_id: string; name: string };
  index_date: string;                 // date
  min_interval_days: number;
  episode_count: number;
  progress_status: ProgressStatus;    // FLAGGED | INVESTIGATING | BRIEF_READY | INVESTIGATION_FAILED
  outcome: Outcome | null;            // set once the stopping policy fires (D-04)
  updated_at: string;
}
// 200: { items: CaseSummary[], total, limit, offset }
```

### E3 `GET /cases/{case_id}`

```ts
interface CaseDetail extends CaseSummary {
  episode_group_ids: string[];        // connected episode chain (D-03)
  primary_pair: { from_episode_id: string; to_episode_id: string }; // UI focus
  signal: RiskSignal;
  stop_reason: StopReason | null;
  latest_run: RunSummary | null;
  brief_available: boolean;
  data_quality_issues: string[];
}

interface RiskSignal {
  rule_id: string;                    // e.g. "READMISSION_30D_SAME_PROVIDER_SAME_DX"
  rule_version: string;
  description: string;                // reviewer-facing: "Repeated inpatient stay at the same FKRTL with the same primary diagnosis within 30 days"
  params: { threshold_days: number; diagnosis_match: "EXACT" | "CATEGORY" };
  pairs: Array<{
    from_episode_id: string;
    to_episode_id: string;
    interval_days: number;
    matched: { same_patient: boolean; same_provider: boolean; same_primary_diagnosis: boolean; encounter_type: EncounterType };
  }>;
  disclaimer: "A risk signal starts an investigation. It is not a finding.";
}

interface RunSummary {
  run_id: string;
  mode: InvestigationMode;
  run_status: RunStatus;
  step: number;
  max_steps: number;
  started_at: string;
  finished_at: string | null;
  outcome: Outcome | null;
  stop_reason: StopReason | null;
}
```

### E4 `GET /cases/{case_id}/episodes`

```ts
interface EpisodeTimeline {
  case_id: string;
  patient_id: string;
  episodes: TimelineEpisode[];        // chronological
}

interface TimelineEpisode {
  episode_id: string;
  role: "ANCHOR" | "RELATED" | "CONTEXT"; // ANCHOR = satisfied the rule; RELATED = linked by reconstruction; CONTEXT = nearby history
  encounter_type: EncounterType;
  admission_type: "EMERGENCY" | "ELECTIVE" | null;
  provider: { provider_id: string; name: string; hospital_class: string | null };
  start_at: string | null;
  end_at: string | null;
  length_of_stay_days: number | null;
  interval_from_previous_days: number | null;
  primary_diagnosis: { code: string; label: string | null };
  secondary_diagnoses: Array<{ code: string; label: string | null }>;
  procedures: Array<{ code: string; label: string | null; performed_at: string | null }>;
  claim: { claim_id: string; inacbg_code: string | null; claim_status: string | null } | null;
  documents: Array<{ note_id: string; note_type: string; title: string | null; availability: "AVAILABLE" | "UNAVAILABLE" | "RESTRICTED" }>;
  relation_reasons: string[];         // e.g. ["SAME_PATIENT", "SAME_PROVIDER", "SAME_PRIMARY_DIAGNOSIS", "WITHIN_30_DAYS"]
  evidence_ids: string[];             // evidence already linked to this episode
}
```

### E5 `POST /cases/{case_id}/investigate`

Request (all optional): `{ "mode": "FULL", "rerun": false, "max_steps": 12 }`. `mode` ∈ `RULES_ONLY | RULES_RETRIEVAL | FULL_RULE_PLANNER | FULL`, default `FULL` (AI planner). If the LLM is unavailable, `FULL` degrades step by step to the rule planner, which is visible via `planner_source`.

- `202 { "run_id": "RUN-…", "run_status": "QUEUED", "poll_url": "/api/v1/cases/{case_id}/investigation?run_id=RUN-…" }`
- `409 INVESTIGATION_IN_PROGRESS` if a run is `QUEUED`/`RUNNING`.
- `409 INVESTIGATION_ALREADY_COMPLETED` if the case has a finished run and `rerun` is not `true`.

### E6 `GET /cases/{case_id}/investigation?run_id=`

Defaults to the latest run. Returns `404 RUN_NOT_FOUND` if never started. Suggested polling: every 1 s while `run_status ∈ {QUEUED, RUNNING}`.

```ts
interface InvestigationView {
  run: RunSummary;
  state: CaseState;
  trail: InvestigationAction[];       // ordered by step
}
```

### E7 `GET /cases/{case_id}/evidence?category=&requirement_key=&run_id=`

`200 { items: Evidence[], total, limit, offset }`

### E8 `GET /evidence/{evidence_id}`

`200 Evidence` plus `source`, the provenance payload for the drawer:

```ts
interface EvidenceDetail extends Evidence {
  source: {
    source_type: SourceType;
    source_id: string;
    title: string;
    // CLINICAL_NOTE: full note text with highlight offsets
    text?: string | null;
    highlight?: { char_start: number; char_end: number } | null;
    availability?: "AVAILABLE" | "UNAVAILABLE" | "RESTRICTED";
    // POLICY_SECTION
    document_title?: string; section?: string; version?: string; effective_date?: string | null; source_ref?: string; source_url?: string | null;
    // structured records
    field_path?: string; value?: unknown;
  };
}
```

### E9 `GET /cases/{case_id}/brief?run_id=`

`200 InvestigationBrief` (§4.6), or `409 BRIEF_NOT_READY`.

### E13 `GET /cases/{case_id}/runs`

`200 { items: RunSummary[], total, limit, offset }`, newest first. Every run of the case stays readable through E6 with `?run_id=`.

### Runtime notes (E5/E6)

- E5 returns `202` immediately, and the run executes in the background (D-20). Poll E6 about every 1 s.
- While a run is `QUEUED`, E6 already returns a valid view: the initial state with all questions `OPEN` at step 0.
- `progress_status` and `outcome` on the case update when the run completes. A failed or interrupted run shows `progress_status = INVESTIGATION_FAILED` and `run.run_status = FAILED`.
- In `FULL` mode, `planner.source` shows `RULE_FALLBACK` for every step until an AI planner is configured (D-18).

### E11 `POST /cases/{case_id}/reviews` (P1)

Request `{ "action": "MARK_REVIEWED" | "ADD_NOTE" | "REQUEST_MORE_EVIDENCE", "note": "…", "reviewer_label": "Reviewer 1" }` → `201 ReviewAction`. No other actions exist; approve, reject, and fraud actions are not representable.

## 4. Core Object Shapes

### 4.1 Evidence

```ts
interface Evidence {
  evidence_id: string;
  case_id: string;
  run_id: string;
  episode_id: string | null;
  source_type: SourceType;
  source_id: string;
  source_title: string;
  source_excerpt: string;
  field_path: string | null;
  char_start: number | null;
  char_end: number | null;
  requirement_key: RequirementKey;
  stance: "AFFIRMS" | "NEGATES" | "INFORMS";
  relevance_category: EvidenceCategory;
  exception_type: string | null;
  retrieved_by_tool: ToolName;
  retrieval_reason: string;
  extraction_method: ExtractionMethod;
  retrieved_at: string;
  investigation_step: number;
  policy_version: string | null;
}
```

### 4.2 Requirement (an evidence gap)

```ts
interface Requirement {
  key: RequirementKey;
  label: string;                      // reviewer-facing question, e.g. "Is there documented emergency context?"
  direction: "RISK" | "CONTEXT" | "POLICY" | "BACKGROUND";
  material: boolean;
  state: RequirementState;            // OPEN | FOUND | NOT_FOUND | CONFLICTING | UNAVAILABLE | FAILED | SKIPPED (non-material only)
  state_explanation: string;          // e.g. "Searched 3 available notes across 2 episodes; no emergency context found."
  coverage: { in_scope_sources: number; searched_sources: number; unavailable_sources: number }; // NOT_FOUND only when searched = in_scope
  evidence_ids: string[];
  attempted_tools: ToolName[];
  spawned_by: RequirementKey | null;  // adaptive follow-up requirements
}
```

### 4.3 Next action

```ts
interface NextAction {
  tool_name: ToolName;
  tool_label: string;                 // "Checking clinical notes for emergency context"
  requirement_key: RequirementKey;
  reason: string;
}
```

### 4.4 Investigation action (trail item)

```ts
interface InvestigationAction {
  step: number;
  tool_name: ToolName;
  tool_label: string;
  requirement_key: RequirementKey | null;
  reason: string;                           // code-generated from requirement + scope
  input_summary: Record<string, unknown>;   // typed tool input, safe to display
  tool_status: ToolStatus;                  // OK | EMPTY | UNAVAILABLE | ERROR | TIMEOUT | REJECTED
  evidence_ids: string[];
  requirement_updates: Array<{ key: RequirementKey; from: RequirementState; to: RequirementState }>;
  planner: {
    source: PlannerSource;                  // LLM | LLM_RETRY | RULE_FALLBACK | RULE
    note: string | null;                    // short declared planner note; label it "Planner note"; never evidence
    priority_ranking: RequirementKey[];
    skipped_requirements: Array<{ key: RequirementKey; reason: string }>; // non-material only
    validation_errors: string[];            // why an LLM proposal was rejected, if it was
  };
  error: { code: string; message: string } | null;
  started_at: string;
  duration_ms: number;
}

type ToolName =
  | "get_episode_history" | "compare_diagnosis" | "compare_procedures" | "get_provider_context"
  | "retrieve_clinical_evidence" | "retrieve_policy" | "find_supporting_evidence" | "find_exception_evidence";
```

The trail shows actions, state, and evidence. The only model-authored text is `planner.note`, a short declared output that is labeled as such. Hidden model reasoning (thinking content) is never stored or returned.

### 4.5 CaseState (context doc §9 contract, extended)

```ts
interface CaseState {
  case_id: string;
  run_id: string;
  signal_type: SignalType;
  related_episode_ids: string[];
  known_facts: Array<{ fact_id: string; text: string; evidence_ids: string[] }>;   // every fact is evidence-backed
  supporting_risk_evidence: string[];        // evidence_ids
  explaining_context_evidence: string[];     // evidence_ids
  neutral_evidence: string[];                // evidence_ids
  requirements: Requirement[];               // the explicit evidence-gap model
  missing_evidence: RequirementKey[];        // requirements in UNAVAILABLE | FAILED
  unresolved_questions: Array<{ key: RequirementKey; question: string; state: RequirementState }>; // OPEN | CONFLICTING | UNAVAILABLE
  tools_called: Array<{ step: number; tool_name: ToolName; tool_status: ToolStatus }>;
  next_action: NextAction | null;            // null once stopped
  investigation_step: number;
  max_steps: number;
  progress_status: ProgressStatus;
  outcome: Outcome | null;
  stop_reason: StopReason | null;
  priority_ranking: RequirementKey[];        // latest ranking of OPEN requirements (from AI planner, or rule order)
  updated_at: string;
}
```

### 4.6 InvestigationBrief

```ts
interface BriefStatement {
  statement_id: string;
  text: string;
  evidence_ids: string[];          // required non-empty for material statements
  requirement_keys: RequirementKey[];
  material: boolean;
}

interface InvestigationBrief {
  brief_id: string;
  case_id: string;
  run_id: string;
  generated_at: string;
  generator_version: string;
  progress_status: ProgressStatus;          // BRIEF_READY
  outcome: Outcome;
  stop_reason: StopReason;
  case_summary: BriefStatement[];
  risk_signal: RiskSignal;
  episode_timeline: Array<{ episode_id: string; label: string; start_at: string | null; end_at: string | null; interval_from_previous_days: number | null }>;
  supporting_risk_evidence: BriefStatement[];
  explaining_context_evidence: BriefStatement[];
  policy_references: Array<{ evidence_id: string; policy_id: string; document_title: string; section: string; version: string; excerpt: string }>;
  remaining_gaps: Array<{ key: RequirementKey; question: string; state: RequirementState; explanation: string }>;
  conflicts: Array<{ key: RequirementKey; affirming_evidence_ids: string[]; negating_evidence_ids: string[] }>;
  uncertainty: BriefStatement[];            // e.g. "Emergency context could not be assessed: episode notes unavailable."
  suggested_next_review: BriefStatement[];  // verification steps for the human, never decisions
  review_status: "PENDING_HUMAN_REVIEW" | "REVIEWED";
  human_decision_notice: "EPISIGHT does not determine fraud, approve or reject claims, or make payment decisions. The reviewer decides.";
  traceability: { material_statements: number; with_evidence: number };
  provenance: { evidence_ids: string[] };   // every evidence item referenced anywhere in the brief
}
```

**Brief guardrails, enforced by a validator before persisting:**

1. Every `material: true` statement has ≥ 1 `evidence_id` that exists in the ledger.
2. The brief text contains none of the banned phrases (e.g., "fraud confirmed", "terbukti fraud", "reject claim", "tolak klaim", "approve payment", "setujui pembayaran").
3. Every `UNAVAILABLE` / `NOT_FOUND` requirement appears in `remaining_gaps` or `uncertainty`. None are silently dropped.
4. If `outcome = EVIDENCE_CONFLICTING`, `conflicts` is non-empty and both sides are referenced.

If validation fails, the case goes to `HUMAN_REVIEW_REQUIRED`, the violations are recorded, and a clearly marked fallback brief is produced. A failed brief is never shown as successful.

## 5. Tool Contracts (internal, but surfaced in the trail)

Each tool has a Pydantic input model and returns a common envelope:

```ts
interface ToolResult<TFindings> {
  tool_name: ToolName;
  status: ToolStatus;
  evidence: Evidence[];               // candidate evidence; the ledger assigns final IDs and dedupes
  findings: TFindings;                // typed, tool-specific structured result
  sources_consulted: Array<{ source_type: SourceType; source_id: string; availability: string }>;
  error: { code: string; message: string } | null;
}
```

| Tool | Input (typed) | Findings (typed) |
|---|---|---|
| `get_episode_history` | `patient_id`, `episode_group_ids`, `window_days` | `related_episode_ids`, `relation_reasons` per episode |
| `compare_diagnosis` | `episode_ids` | `match: EXACT \| CATEGORY \| DIFFERENT`, codes per episode, `chronic_class: boolean` |
| `compare_procedures` | `episode_ids` | shared codes, related codes, planned-vs-performed (when a plan is in scope) |
| `get_provider_context` | `provider_id`, `episode_ids` | provider type/class, class-of-care changes, referral flags |
| `retrieve_clinical_evidence` | `episode_ids`, `note_types?`, `query?` | inventory `{note_id, note_type, availability}`, top passages |
| `find_exception_evidence` | `episode_ids`, `context_type` | `present: true \| false \| null`, passages with stance |
| `find_supporting_evidence` | `episode_ids`, `signal_type` | risk-indicator passages with stance |
| `retrieve_policy` | `signal_type`, `topics[]`, `query` | ranked policy sections with version metadata |

## 6. Mock Fixtures for Person 2

During Phase 0, Person 1 publishes `packages/shared-types/fixtures/` with one JSON file per endpoint response for each golden case (A–E). This includes an in-progress `InvestigationView` snapshot, so Person 2 can build loading and polling states before the backend exists. Fixtures are regenerated from the real Pydantic models once they exist, and a contract test fails if they drift.
