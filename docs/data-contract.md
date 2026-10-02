# EPISIGHT — Data Contract (Proposal)

> **Status:** **v1 FROZEN** (2026-10-02). Owned by Person 1. Any change requires a contract-version bump, a note in the Progress Log of [development-plan.md](development-plan.md), and notifying Person 3 (data) / Person 2 (enums).
> **Scope:** (1) the files Person 3 delivers, (2) how the backend stores them, (3) the internal evidence and state objects the backend creates.
> Decisions referenced as D-xx live in [decisions.md](decisions.md).

---

## 1. Conventions

- **Format:** UTF-8 JSON Lines (`.jsonl`), one entity per line, with a `manifest.json` per dataset version.
- **IDs:** strings with a type prefix and zero padding, stable across regenerations with the same seed: `PAT-000123`, `PRV-0007`, `EPI-000456`, `CLM-000456`, `NOTE-001234`, `POL-PMK26-2021-S03`.
- **Timestamps:** ISO-8601 with an offset (`2026-03-07T10:30:00+07:00`). Date-only values (`YYYY-MM-DD`) are allowed where noted.
- **Codes:** diagnoses in ICD-10 (e.g., `I50.0`); procedures in ICD-9-CM (e.g., `36.06`), as used by INA-CBG. Synthetic but realistic.
- **Enums:** `UPPER_SNAKE_CASE`, in English. Free text (notes, policy) may be Indonesian (D-08).
- **Forbidden fields** in agent-accessible data: `scenario`, `label`, `case_class`, `ground_truth`, `expected_*`, `is_fraud`, `is_legitimate`. The ingest validator rejects them.

## 2. Dataset Layout (delivered by Person 3)

```text
data/
├── synthetic/<dataset_version>/          # e.g. v0.1.0
│   ├── manifest.json
│   ├── patients.jsonl
│   ├── providers.jsonl
│   ├── episodes.jsonl
│   ├── claims.jsonl
│   └── clinical_notes.jsonl
├── policies/<corpus_version>/            # e.g. pc-0.1.0
│   ├── manifest.json
│   └── policy_sections.jsonl
└── ground-truth/<dataset_version>/       # NEVER ingested by the backend
    └── cases.jsonl
```

### 2.1 `manifest.json` (synthetic)

```json
{
  "dataset_version": "v0.1.0",
  "generator_version": "gen-0.1.0",
  "seed": 20261001,
  "generated_at": "2026-10-05T09:00:00+07:00",
  "contract_version": "data-contract/1",
  "counts": { "patients": 40, "providers": 6, "episodes": 180, "claims": 180, "clinical_notes": 420 },
  "files": { "episodes.jsonl": "sha256:…" }
}
```

## 3. Source Entities

Legend: **R** = required, O = optional/nullable.

### 3.1 Patient — `patients.jsonl`

| Field | Type | R | Notes |
|---|---|---|---|
| `patient_id` | string | R | Pseudonymous only |
| `birth_year` | int | O | Only if needed for display; no names, NIK, or addresses |
| `sex` | `M` \| `F` | O | |
| `chronic_conditions` | string[] (ICD-10) | O | Registry-style background, which may be incomplete by design |

### 3.2 Provider — `providers.jsonl`

| Field | Type | R | Notes |
|---|---|---|---|
| `provider_id` | string | R | |
| `name` | string | R | Clearly synthetic ("RS Sintetis Nusantara 03") |
| `provider_type` | `FKRTL` \| `FKTP` | R | |
| `hospital_class` | `A`\|`B`\|`C`\|`D` | O | Used as provider context |
| `region` | string | O | Synthetic label |

### 3.3 Episode — `episodes.jsonl`

| Field | Type | R | Notes |
|---|---|---|---|
| `episode_id` | string | R | |
| `patient_id` | string | R | FK |
| `provider_id` | string | R | FK |
| `encounter_type` | `INPATIENT` \| `OUTPATIENT` | R | |
| `start_at` | timestamp | R* | Admission or visit time. *May be null only in data-quality test cases |
| `end_at` | timestamp | O | Discharge time (inpatient). Null for outpatient or when missing |
| `admission_type` | `EMERGENCY` \| `ELECTIVE` \| null | O | D-11: source metadata only, which on its own never resolves emergency context. Null in golden Case A; may deliberately contradict notes |
| `primary_diagnosis` | ICD-10 string | R | |
| `secondary_diagnoses` | ICD-10 string[] | O | |
| `procedures` | `{code, performed_at?}`[] | O | ICD-9-CM |
| `discharge_status` | `HOME` \| `REFERRED` \| `DIED` \| `AGAINST_ADVICE` \| null | O | |
| `class_of_care` | `1`\|`2`\|`3` | O | Room class |

### 3.4 Claim — `claims.jsonl`

| Field | Type | R | Notes |
|---|---|---|---|
| `claim_id` | string | R | |
| `episode_id` | string | R | FK, 1:1 with episode in P0 |
| `submitted_at` | timestamp | R | |
| `inacbg_code` | string | O | Synthetic group code |
| `claimed_amount_idr` | int | O | Display only; never used for signals |
| `claim_status` | `SUBMITTED` \| `PENDING` \| `VERIFIED` | O | **No** approved/rejected values, to avoid implying decisions |

### 3.5 Clinical note — `clinical_notes.jsonl`

| Field | Type | R | Notes |
|---|---|---|---|
| `note_id` | string | R | |
| `episode_id` | string | R | FK |
| `note_type` | `TRIAGE` \| `ADMISSION` \| `PROGRESS` \| `DISCHARGE_SUMMARY` \| `PROCEDURE_PLAN` \| `PROCEDURE_REPORT` \| `OUTPATIENT_VISIT` \| `SUPPORTING_EXAM_RESULT` \| `REFERRAL` | R | |
| `title` | string | O | |
| `authored_at` | timestamp | R | |
| `language` | `id` \| `en` | R | D-08: primarily `id`; English/Latin medical terms inside `id` notes are normal |
| `availability` | `AVAILABLE` \| `UNAVAILABLE` \| `RESTRICTED` | R | D-12 |
| `text` | string \| null | R | Must be `null` iff availability ≠ `AVAILABLE` |

**Document registry semantics (D-12).** This table is the registry of documents that exist for an episode.

- A registered but `UNAVAILABLE`/`RESTRICTED` note makes the affected requirements `UNAVAILABLE`.
- A search over available notes that finds nothing yields `NOT_FOUND`, and only once coverage is complete.
- Expected documents: every `INPATIENT` episode is expected to have a `DISCHARGE_SUMMARY`. If none is registered, it is treated as an unavailable expected document.

### 3.6 Policy section — `data/policies/<v>/policy_sections.jsonl`

| Field | Type | R | Notes |
|---|---|---|---|
| `policy_id` | string | R | Section-level ID, e.g. `POL-PMK26-2021-READMISI-01` |
| `document_title` | string | R | e.g. "Permenkes No. 26 Tahun 2021 tentang Pedoman INA-CBG" |
| `section` | string | R | Section/chapter label |
| `text` | string | R | Curated excerpt, verified by Person 3 |
| `source_ref` | string | R | Human-readable citation |
| `source_url` | string | O | e.g. JDIH link |
| `version` | string | R | Document version / issuance |
| `effective_date` | date | O | |
| `topics` | string[] | O | e.g. `READMISSION`, `FRAGMENTATION`, `EXCEPTION_EMERGENCY` |

### 3.7 Ground truth — `data/ground-truth/<v>/cases.jsonl` (evaluation only)

| Field | Type | Notes |
|---|---|---|
| `gt_id` | string | |
| `golden_case` | `A`\|`B`\|`C`\|`D`\|`E` \| null | D-01 |
| `scenario_class` | enum, e.g. `LEGIT_READMISSION_EMERGENCY`, `POTENTIAL_FRAGMENTATION`, `LEGIT_STAGED_PROCEDURE`, `LEGIT_CHRONIC`, `MISSING_EVIDENCE`, `CONFLICTING_EVIDENCE`, `UNRELATED_LOOKALIKE`, `NOT_FLAGGABLE` | |
| `expected_signal_type` | `READMISSION` \| `FRAGMENTATION` \| null | null = should **not** be flagged (screening FP test) |
| `anchor_episode_ids` | string[] | **Join key** with runner output: the sorted episode group that should be flagged (D-03) |
| `expected_related_episode_ids` | string[] | Episode Recall |
| `expected_evidence` | `{source_type, source_id, requirement_key, category, mandatory}`[] | Precision / Coverage |
| `expected_exceptions` | requirement_key[] | Exception Identification Accuracy |
| `expected_requirement_states` | `{requirement_key: state}` | Optional, finer-grained |
| `expected_outcome` | Outcome enum | Appropriate Escalation |
| `expected_stop_reason` | StopReason enum \| null | |
| `notes_for_reviewers` | string | Author rationale |

## 4. Shared Enums (canonical list; mirrored in [api-contract.md](api-contract.md))

| Enum | Values |
|---|---|
| `SignalType` | `READMISSION`, `FRAGMENTATION` |
| `EncounterType` | `INPATIENT`, `OUTPATIENT` |
| `ProgressStatus` | `FLAGGED`, `INVESTIGATING`, `BRIEF_READY`, `INVESTIGATION_FAILED` (D-04) |
| `Outcome` | `EVIDENCE_SUFFICIENT`, `EVIDENCE_CONFLICTING`, `EVIDENCE_UNAVAILABLE`, `HUMAN_REVIEW_REQUIRED` (D-04) |
| `StopReason` | `SUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`, `REQUIRED_EVIDENCE_UNAVAILABLE`, `EVIDENCE_PATHS_EXHAUSTED`, `MAX_STEPS_REACHED`, `TOOL_FAILURE`, `TIMEOUT`, `NO_ACTIONABLE_GAP`, `INTERRUPTED` |
| `RunStatus` | `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED` |
| `InvestigationMode` | `RULES_ONLY`, `RULES_RETRIEVAL`, `FULL_RULE_PLANNER`, `FULL` (default) |
| `PlannerSource` | `LLM`, `LLM_RETRY`, `RULE_FALLBACK`, `RULE` |
| `EvidenceCategory` | `SUPPORTING_RISK`, `EXPLAINING_CONTEXT`, `NEUTRAL` |
| `SourceType` | `EPISODE_RECORD`, `CLAIM_RECORD`, `PROVIDER_RECORD`, `CLINICAL_NOTE`, `POLICY_SECTION`, `SCREENING_RULE` |
| `RequirementKey` | see [architecture.md §7.1](architecture.md) |
| `RequirementState` | `OPEN`, `FOUND`, `NOT_FOUND`, `CONFLICTING`, `UNAVAILABLE`, `FAILED`, `SKIPPED` (non-material only) |
| `RequirementDirection` | `RISK`, `CONTEXT`, `POLICY`, `BACKGROUND` |
| `ToolStatus` | `OK`, `EMPTY`, `UNAVAILABLE`, `ERROR`, `TIMEOUT`, `REJECTED` |
| `ExtractionMethod` | `STRUCTURED_FIELD`, `RULE_MATCH`, `BM25_RETRIEVAL`, `LLM_ASSISTED` |

**Progress transitions:** `FLAGGED → INVESTIGATING → BRIEF_READY`, or `INVESTIGATING → INVESTIGATION_FAILED` on a system failure (DB error, crash, interruption). A re-run sets the case back to `INVESTIGATING`. `outcome` and `stop_reason` are set when the stopping policy fires and stay attached to the case until the next run completes.

## 5. Backend-Created Objects

### 5.1 Case (created by screening)

| Field | Notes |
|---|---|
| `case_id` | Deterministic: `CASE-RA-` / `CASE-FR-` + first 8 hex chars of `sha256(signal_type + sorted episode_group_ids)` |
| `signal_type` | |
| `patient_id`, `provider_id` | |
| `episode_group_ids` | Connected chain of episodes satisfying the rule (≥ 2), sorted (D-03). Exported as `anchor_episode_ids` for the evaluation join |
| `primary_pair` | `{from_episode_id, to_episode_id}`: the qualifying pair with the shortest interval (ties broken by earliest date). This is the UI focus |
| `signal_details` | `{rule_id, rule_version, params:{threshold_days, diagnosis_match}, pairs:[{from_episode_id, to_episode_id, interval_days, matched:{same_patient, same_provider, same_primary_diagnosis, encounter_type}}]}` |
| `min_interval_days` | For queue display |
| `index_date` | Start of first episode in the group |
| `progress_status`, `outcome`, `stop_reason` | §4 (D-04) |
| `latest_run_id` | |
| `data_quality_issues` | e.g. `DUPLICATE_EPISODE_ROW`, `MISSING_TIMESTAMP` (recorded, not silently dropped) |

### 5.2 Evidence (ledger entry; immutable once written)

| Field | Notes |
|---|---|
| `evidence_id` | Deterministic: `EV-` + hash(`case_id`, `run_id`, `requirement_key`, `source_type`, `source_id`, `char_start`, `char_end`, `field_path`) (amended by D-22). Re-surfacing the same evidence dedupes and appends the step to `surfaced_in_steps`. Evaluation matches evidence by `(source_type, source_id, requirement_key)` |
| `case_id`, `run_id` | |
| `episode_id` | Nullable for policy evidence |
| `source_type`, `source_id` | Must resolve to a stored record; validation rejects dangling references |
| `source_title` | e.g. "Discharge summary — EPI-000456" / policy section title |
| `field_path` | For structured evidence, e.g. `episodes.primary_diagnosis` |
| `source_excerpt` | Literal substring of source text, or a rendered structured value |
| `char_start`, `char_end` | Offsets into note/policy text |
| `requirement_key` | Which gap this evidence speaks to |
| `stance` | `AFFIRMS` \| `NEGATES` \| `INFORMS` (relative to the requirement; drives conflict detection) |
| `relevance_category` | `SUPPORTING_RISK` \| `EXPLAINING_CONTEXT` \| `NEUTRAL` |
| `exception_type` | e.g. `EMERGENCY`, `CHRONIC`, `SCHEDULED_PROCEDURE`, `SUPPORTING_EXAM_FOLLOWUP` (context evidence only) |
| `retrieved_by_tool` | Tool name |
| `retrieval_reason` | From the planner action |
| `extraction_method` | `ExtractionMethod` |
| `retrieved_at` | |
| `investigation_step` | First step that surfaced it |
| `surfaced_in_steps` | int[] |
| `policy_version`, `policy_effective_date` | Policy evidence only |

### 5.3 Investigation run, state, and actions

- `investigation_runs`: `run_id`, `case_id`, `mode`, `run_status`, `config` (max_steps, timeouts, catalog version, planner version), `dataset_version`, `corpus_version`, `code_version` (git SHA), `started_at`, `finished_at`, `outcome`, `stop_reason`, `error`.
- `investigation_states`: one JSONB snapshot per step (`run_id`, `step`, `state`), so the timeline of state changes is replayable. The state shape is `CaseState` in [api-contract.md §4.5](api-contract.md).
- `investigation_actions`: `action_id`, `run_id`, `step`, `tool_name`, `tool_input` (JSON), `reason` (code-generated), `requirement_key`, `tool_status`, `evidence_ids[]`, `requirement_updates[]`, `error`, `started_at`, `duration_ms`, plus planner fields: `planner_source`, `planner_model`, `prompt_version`, `planner_request_hash`, `planner_note` (LLM text, never evidence), `priority_ranking[]`, `skipped_requirements[]`, `validation_errors[]`, `planner_latency_ms`. **Append-only**, and this is the audit log.
- `planner_recordings`: `request_hash`, `model`, `prompt_version`, `request` (JSON), `response` (JSON), `created_at`. Used for record/replay (D-21).
- `briefs`: `brief_id`, `run_id`, `case_id`, `generator_version`, `content` (JSONB, `InvestigationBrief`), `validation` (`{passed, violations[]}`), `generated_at`.
- `review_actions` (P1): `review_id`, `case_id`, `brief_id`, `action` (`MARK_REVIEWED` \| `ADD_NOTE` \| `REQUEST_MORE_EVIDENCE`), `note`, `reviewer_label`, `created_at`.

### 5.4 Source tables

`patients`, `providers`, `episodes` (+ `episode_diagnoses`, `episode_procedures` or array columns), `claims`, `clinical_notes`, `policy_sections`. Each carries `dataset_version` / `corpus_version`. The backend never updates source rows after ingest ("agent must not alter source records").

## 6. Runner Output (Person 1 → Person 3 evaluation)

Produced by `episight batch --mode <MODE> --out <file>.json`: one object per case, plus a run header.

```json
{
  "header": {
    "runner_version": "1", "mode": "FULL", "dataset_version": "v0.1.0",
    "corpus_version": "pc-0.1.0", "code_version": "abc1234", "config_hash": "…",
    "started_at": "…", "finished_at": "…"
  },
  "cases": [
    {
      "case_id": "CASE-RA-1a2b3c4d",
      "signal_type": "READMISSION",
      "anchor_episode_ids": ["EPI-000455", "EPI-000456"],
      "reconstructed_episode_ids": ["EPI-000455", "EPI-000456"],
      "evidence": [
        { "evidence_id": "EV-…", "source_type": "CLINICAL_NOTE", "source_id": "NOTE-001234",
          "requirement_key": "EMERGENCY_CONTEXT", "stance": "AFFIRMS", "relevance_category": "EXPLAINING_CONTEXT" }
      ],
      "requirement_states": { "EMERGENCY_CONTEXT": "FOUND" },
      "outcome": "EVIDENCE_SUFFICIENT",
      "stop_reason": "SUFFICIENT_EVIDENCE",
      "tool_call_count": 9,
      "step_count": 9,
      "tool_failures": 0,
      "planner": { "llm_steps": 8, "llm_retry_steps": 1, "fallback_steps": 0, "validation_rejections": 1, "skipped_requirements": ["PROVIDER_CONTEXT"] },
      "elapsed_ms": 412,
      "brief": { "…": "InvestigationBrief" },
      "brief_traceability": { "material_statements": 11, "with_evidence": 11 }
    }
  ],
  "screening": { "flagged_anchor_sets": [["EPI-000455", "EPI-000456"]] }
}
```

The `screening` block lets Person 3 compute screening recall and false positives against ground-truth rows whose `expected_signal_type` is null.

**As implemented (runner v1, additive to the shape above):** `header.config` (mode, max_steps, catalog version, tool timeout, repeats, AI planner provider/model/prompt version) with `config_hash`; per case `run_index` (for `--repeats`), `planner.rule_steps`, and `brief_validation {passed, violations}`. Command: `uv run episight batch` (see README).
