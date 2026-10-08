# EPISIGHT — Person 3 Work Plan
## Synthetic Data, Domain, Benchmark, Evaluation & QA Owner

> Mission: make the prototype testable and trustworthy by supplying reproducible synthetic data, realistic case logic, hidden ground truth, a validated policy/evidence corpus, automated evaluation, and end-to-end quality assurance.

---

## 0. Status Update — 2026-10-02 (read this first)

> Updated by Person 1. The backend is complete for P0 and merged to `main`: ingest/validation, screening, investigation engine (rule planner + AI planner), brief, and a **batch runner** that produces the evaluation input. This section lists what exists, what changed in your tasks, the rules your dataset must respect, and what to do next. The original plan below is kept and annotated (**Updated** markers).
> References: [data-contract.md](data-contract.md) (v1 frozen) · [decisions.md](decisions.md) · [architecture.md](architecture.md) §7 · [development-plan.md](development-plan.md)

### 0.1 Timeline and priorities (D-16)

- Submission is about **48 hours from 2026-10-02**.
- **P0:** official dataset with the **five golden cases** (A–E) + ground truth + curated policy corpus, validated and run through the batch runner.
- **P1:** 20+ benchmark cases and a scoring harness with aggregate metrics.
- **P2:** 50 cases, variance analysis, dashboards.

### 0.2 What already exists for you

| Item | Where | Notes |
|---|---|---|
| Data contract (frozen v1) | [data-contract.md](data-contract.md) §1–§4 | File layout, every field, enums, forbidden label fields, ground-truth schema (§3.7) |
| Reference dataset in the exact format | `apps/api/tests/fixtures/dataset/v0-interim/`, `.../policies/pc-0-interim/` | Written by Person 1 for development. Use it as a **format template**, not as your dataset. Scenario table: `apps/api/tests/fixtures/README.md`; generator: `build_interim_dataset.py` |
| Dataset validator | `episight seed` and `episight batch` | Validates the whole delivery and reports **all** problems at once (schema, foreign keys, forbidden fields, text vs availability, duplicate IDs). Refuses any `ground-truth` directory |
| Batch runner (your evaluation input) | `uv run episight batch` | All four ablation modes, Data Contract §6 JSON + CSV + `summary.md`; repeats; AI recordings and replay. No database or Docker needed |
| Backend golden tests + CI | `apps/api/tests`, `.github/workflows/backend.yml` | Run on the interim data on every push. Your official data needs its own run (§0.6) |

### 0.3 Changes vs. the original plan (task shifts)

| Area | Original plan | Now | What you do |
|---|---|---|---|
| Golden cases | Four (A–D) | **Five** (D-01): **E = Conflicting Evidence** | Author A–E; scenario classes are named (e.g. `LEGIT_STAGED_PROCEDURE`), letters only for golden cases |
| Data contract | You write it (Phase 0) | Written and frozen jointly (Person 1 drafted, decisions locked) | Follow it; request changes through [decisions.md](decisions.md), not ad hoc |
| Evaluation runner | You trigger the backend per case | **Split:** running = Person 1's `episight batch` (done); **scoring = your harness** | Your harness loads the batch JSON + your ground truth and computes metrics. No HTTP calls needed |
| Benchmark with AI planner | Not specified | You run `--mode FULL` with **your own key** | `apps/api/.env`: `OPENAI_API_KEY=…`, `EPISIGHT_LLM_PROVIDER=openai`, `EPISIGHT_LLM_MODEL=gpt-4o-mini` (or an Anthropic key). Costs are on that key |
| Case identity | `case_id` in ground truth | Cases are **episode groups** (D-03); `case_id` is derived by screening | Ground truth joins on **`anchor_episode_ids`** = the full sorted episode group |
| Evidence matching | By evidence ID | Evidence IDs include the run (D-22) | Match evidence by **`(source_type, source_id, requirement_key)`** |
| Case B expected behaviour | "continue / unresolved" | `HUMAN_REVIEW_REQUIRED` + `EVIDENCE_PATHS_EXHAUSTED` (D-05) | Use these values in ground truth |
| Status values | One status list | `outcome` + `stop_reason` (D-04) | Ground truth `expected_outcome` / `expected_stop_reason` use the enums in data-contract §4 |
| Regression | Your suite on 4 cases | Backend CI runs golden regression on interim data | You run the official regression after changes (§0.6, Phase 13) |
| Failure analysis | Joint | You report, Person 1 fixes engine/lexicon issues | Send the case JSON from the batch output with each report |

### 0.4 Rules your dataset must respect (these decide whether results are right)

**Screening (D-02, inclusive thresholds, exact primary ICD-10 code, same `provider_id`):**
- Readmission: INPATIENT → INPATIENT, `admission(ep2).date − discharge(ep1).date ≤ 30` days.
- Fragmentation: OUTPATIENT → OUTPATIENT, `visit(ep2).date − visit(ep1).date ≤ 7` days.
- Consecutive qualifying episodes chain into **one case** (D-03). Episodes with no `start_at` are skipped and reported as `MISSING_TIMESTAMP`; content duplicates as `DUPLICATE_EPISODE_ROW`.

**Which notes answer which question.** The engine only looks in these episodes:

| Question (requirement key) | Notes searched | Design implication |
|---|---|---|
| `EMERGENCY_CONTEXT` | Repeat episodes only (every anchor after the first) | Emergency evidence must be in the **repeat** episode's notes |
| `CLINICAL_JUSTIFICATION` | Repeat episodes only | Same |
| `SUPPORTING_EXAM_FOLLOWUP_CONTEXT` (fragmentation only) | Repeat episodes only | The repeat visit should mention reviewing exam results |
| `SCHEDULED_PROCEDURE_CONTEXT` | All anchor episodes | A plan in episode 1 counts. Include the **ICD-9-CM code** in the plan sentence so the plan-vs-performed check can run |
| `SCHEDULE_CONSISTENCY` (opened automatically) | Plan code vs procedures recorded in later episodes | Matching code → FOUND; different code → CONFLICTING; no code → NOT_FOUND (C would then end as `HUMAN_REVIEW_REQUIRED`) |
| `CHRONIC_CONDITION_CONTEXT` | Anchors + RELATED episodes (same diagnosis or ICD-10 category within 90 days) | A prior related outpatient visit can carry chronic context |
| `RISK_INDICATORS_IN_NOTES` | All anchor episodes | e.g. "keluhan serupa", "belum membaik", "pulang atas permintaan sendiri" |

**Availability (D-12):**
- `availability` ∈ `AVAILABLE` / `UNAVAILABLE` / `RESTRICTED`; `text` must be `null` exactly when not available.
- ⚠️ **Every INPATIENT episode is expected to have a `DISCHARGE_SUMMARY` note registered.** If none is registered, it is treated as an unavailable document, and the case can end as `EVIDENCE_UNAVAILABLE` even if you did not intend that. Register one, available or not, on purpose.
- A question becomes `NOT_FOUND` only after every readable note in its scope was read. If any in-scope note is unreadable and nothing affirming was found, it is `UNAVAILABLE`.

**`admission_type` (D-11):** may be set as metadata, but it never resolves emergency context on its own. In golden Case A leave it `null`; the emergency must be documented in the notes.

**Language (D-08):** notes in Bahasa Indonesia; English/Latin medical terms and codes are fine.

**Context matcher (important).** Note reading in P0 is deterministic: a phrase list per context type with negation handling ("tidak ada …", "tanpa …", "bukan …"). Current phrases (`apps/api/src/episight/retrieval/context.py`):

| Context | Affirming phrases (examples) | Negating |
|---|---|---|
| Emergency | igd, ugd, gawat darurat, kegawatdaruratan, triase merah, "triase: merah", kuning-merah, emergency, cito, penurunan kesadaran, syok | negation cue before the phrase; "masuk secara elektif", "admisi elektif" |
| Chronic | kronik, kronis, chronic, menahun, ppok, copd, ckd, penyakit kronis | negation cue |
| Scheduled / staged | dijadwalkan, terjadwal, rencana tindakan, bertahap, tahap kedua, staged, scheduled, sesuai rencana, sesuai jadwal, planned | negation cue ("tidak ada … yang dijadwalkan") |
| Supporting-exam follow-up | hasil pemeriksaan penunjang, pemeriksaan penunjang, membawa hasil, hasil laboratorium / lab / endoskopi / rontgen / radiologi / ekg / usg, konsultasi hasil | negation cue |
| Clinical justification | pemicu, atas indikasi, indikasi medis, dicurigai, memberat, perburukan, edema paru akut, komplikasi, decompensated, (uro)sepsis, tidak dapat dilakukan, karena | — |
| Risk indicators | keluhan serupa / sama / masih ada / berulang, belum membaik, tidak membaik, pulang atas permintaan sendiri, pulang paksa, tanpa indikasi | — |

Vary your wording on purpose (the plan says "not trivial keyword-only cases"). When the engine misses a phrasing a reviewer would recognise, that is a **valid benchmark finding**: report it to Person 1, who extends the phrase list (or, if time allows, adds the LLM passage classifier, M10). **Send 1–2 sample notes per context type to Person 1 early**, before writing all cases.

**Policy corpus:** the interim sections are **placeholders** (their `source_ref` says so) and must be replaced with curated, sourceable text from Permenkes 26/2021. Set `topics` per section, because retrieval filters on them: `READMISSION`, `FRAGMENTATION`, `EXCEPTION_EMERGENCY`, `EXCEPTION_CHRONIC`, `EXCEPTION_SCHEDULED`, `EXCEPTION_SUPPORTING_EXAM`.

### 0.5 Expected golden behaviour (put this in ground truth)

| Case | `expected_signal_type` | `expected_outcome` | `expected_stop_reason` | Key requirement states |
|---|---|---|---|---|
| A — Legitimate readmission | READMISSION | `EVIDENCE_SUFFICIENT` | `SUFFICIENT_EVIDENCE` | EMERGENCY_CONTEXT = FOUND (from notes) |
| B — Potential fragmentation | FRAGMENTATION | `HUMAN_REVIEW_REQUIRED` | `EVIDENCE_PATHS_EXHAUSTED` | all context questions NOT_FOUND |
| C — Scheduled procedure | READMISSION or FRAGMENTATION | `EVIDENCE_SUFFICIENT` | `SUFFICIENT_EVIDENCE` | SCHEDULED_PROCEDURE_CONTEXT = FOUND, SCHEDULE_CONSISTENCY = FOUND |
| D — Missing evidence | READMISSION | `EVIDENCE_UNAVAILABLE` | `REQUIRED_EVIDENCE_UNAVAILABLE` | context questions UNAVAILABLE |
| E — Conflicting evidence | READMISSION | `EVIDENCE_CONFLICTING` | `CONFLICTING_EVIDENCE` | EMERGENCY_CONTEXT = CONFLICTING |
| Not-flaggable lookalike | `null` | — | — | screening must not flag it |

### 0.6 Your next actions (in order)

1. Pull `main`; `cd apps/api && uv sync` (no Docker needed for batch runs).
2. Send 1–2 sample notes per context type to Person 1 (phrase check).
3. Build the official dataset: `data/synthetic/<version>/` (manifest + 5 JSONL files), `data/policies/<version>/`, and ground truth `data/ground-truth/<version>/cases.jsonl` (data-contract §3.7).
4. **Validate** (fails loudly with every problem):
   ```bash
   uv run episight batch --out ../../evaluation/runs/validate --dataset ../../data/synthetic/<v> --policies ../../data/policies/<v> --mode RULES_ONLY
   ```
5. **Run the benchmark** with your key:
   ```bash
   uv run episight batch --out ../../evaluation/runs/<name> --dataset ../../data/synthetic/<v> --policies ../../data/policies/<v> \
     --mode all --recordings ../../evaluation/runs/<name>/recordings
   ```
   `--repeats 3` for AI-planner variance; `EPISIGHT_LLM_REPLAY=replay` re-scores later without calling the model.
6. **Build the scoring harness** (`evaluation/`), using the field mapping in §0.7.
7. Report every golden mismatch to Person 1 with the case JSON.
8. Expand to 20+ cases; then governance and end-to-end QA.

### 0.7 Metric → batch output field mapping

| Metric | Computed from (per case, in `<MODE>.json`) |
|---|---|
| Screening recall / false positives | `screening.flagged_anchor_sets` vs ground truth `anchor_episode_ids` / `expected_signal_type` (null = must not be flagged) |
| Episode Recall | `reconstructed_episode_ids` vs `expected_related_episode_ids` |
| Evidence Retrieval Precision | `evidence[]` matched on `(source_type, source_id, requirement_key)` against `expected_evidence` (decide whether NEUTRAL counts) |
| Evidence Coverage | mandatory `expected_evidence` items found in `evidence[]` |
| Exception Identification Accuracy | `requirement_states[<context key>] == "FOUND"` vs `expected_exceptions` |
| Appropriate Escalation | `outcome` + `stop_reason` vs `expected_outcome` / `expected_stop_reason` |
| Investigation Completion Time | `elapsed_ms` (FULL includes model latency; record the machine) |
| Traceability | `brief_traceability.with_evidence / material_statements` |
| Ablation (proposal §13) | Compare the four modes' files; `summary.md` gives a first view |
| AI-planner variance | `--repeats N` → `run_index`; compare outcomes and steps across runs |
| Planner health | `planner.llm_steps`, `llm_retry_steps`, `fallback_steps`, `validation_rejections` |

Reproducibility is in `header`: `dataset_version`, `corpus_version`, `code_version` (git SHA), `config` + `config_hash` (mode, max steps, catalog version, AI provider/model/prompt version).

### 0.8 First numbers on the interim data (for orientation only)

Average steps: RULES_ONLY 4.0 (cannot assess context → all `EVIDENCE_UNAVAILABLE`), RULES_RETRIEVAL 11.3, FULL_RULE_PLANNER 9.7, FULL (OpenAI `gpt-4o-mini`) 9.7 with 0 fallbacks. The last three modes reached the same outcomes. The AI planner is currently equal to the rule planner on this easy data; your more varied benchmark decides whether it adds value.

### 0.9 Progress — 2026-10-04 (Person 3)

Branch `feat/person3-data-eval`. Done:

- **Dataset v0.1.0** (`data/`): deterministic generator (`data/generator/generate_dataset.py`, seed 20261004) with golden A–E (seed-independent), 15 benchmark cases, 8 must-not-flag screening fixtures (31/7-day boundaries, other provider, other diagnosis, IP→OP, duplicate row, missing date, same ICD-10 category) and 12 noise patients. Generator tests: `data/generator/tests` (11).
- **Ground truth** `data/ground-truth/v0.1.0/cases.jsonl`: 28 rows with evidence labels (incl. `IRRELEVANT`), exceptions, requirement states, outcome and stop reason.
- **Policy corpus pc-0.1.0**: four sections (definition + exceptions × readmission/fragmentation) from the proposal's Permenkes 26/2021 definitions. ⚠️ Verbatim check against the JDIH PDF is still open.
- **Scoring harness** `evaluation/score.py` + `METRICS.md` + tests (12). Regression: `evaluation/run_regression.sh`, CI `.github/workflows/evaluation.yml`.
- **Baseline** (`evaluation/reports/v0.1.0-baseline/`): FULL_RULE_PLANNER golden 5/5, outcome accuracy 95%, coverage 93%, precision 100%, 0 unsafe closures; RULES_RETRIEVAL 4/5 golden, 1 unsafe closure. Findings for Person 1: `evaluation/FINDINGS.md`.

Open: FULL (AI planner) run with a key and `--repeats 3`; verbatim policy check; governance and E2E QA (Phases 14–16); more paraphrase cases.

### 0.10 Person 1 follow-up — 2026-10-08

- The historical FULL benchmark was completed after §0.9: `evaluation/reports/v0.1.0-full/`,
  3 repeats, 95% outcome accuracy, recorded model responses. Its corpus/backend remain historical.
- Policy `pc-0.1.1` is verified against JDIH Kemenkes, PDF page 55; complete source text,
  effective date and provenance are recorded in `data/policies/pc-0.1.1/VERIFICATION.md`.
- The backend recognises documented active resuscitation care without relying on transport alone;
  GT-B09 now passes. No synthetic case or ground-truth label was changed.
- Scoring keeps missing cases/repeats in the denominator. CI gates missing runs, screening errors,
  new case/state failures, quality regressions and full-mode unsafe closures/brief failures.
- New default deterministic baseline: `evaluation/reports/v0.1.0-pc-0.1.1-backend/`,
  FULL_RULE_PLANNER 20/20 outcomes, A–E 5/5, coverage 100%, no unsafe closure.
- Still open: fresh FULL recordings for this backend/corpus, broader paraphrase validation,
  governance and frontend E2E QA. The matcher remains a lexical prototype, not a clinical adjudicator.

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
  - evaluation harness (**Updated:** the scoring part; the batch runner is provided);
  - regression benchmark;
  - domain QA;
  - governance QA;
  - end-to-end prototype QA.
- Co-own with Person 1:
  - data schema (**Updated:** frozen v1; changes via decisions.md);
  - screening-rule fixtures;
  - benchmark runner interface (**Updated:** implemented as `episight batch`, Data Contract §6);
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
- [ ] ~~Four~~ **Five** golden cases are stable and representative.
- [ ] Ground truth is separate and inaccessible to the agent. *(Enforced on the backend side: ingest refuses `ground-truth` paths, no table stores it, a test scans runtime code. Keep files under `data/ground-truth/`.)*
- [ ] Clinical/policy evidence is realistic enough to test retrieval and reasoning.
- [ ] 20+ benchmark cases exist, with 20–50 as the target range if time permits.
- [ ] Evaluation can run automatically.
- [ ] Metrics can be reproduced.
- [ ] Regressions can be detected.
- [ ] Prototype behavior respects domain and governance constraints.

---

# PHASE 0 — Data & Evaluation Contract Lock

## Data contract

- [x] Agree entities with Person 1:
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
- [x] Define required vs optional fields.
- [x] Define ID format.
- [x] Define timestamps/time zone assumptions. *(ISO-8601 with offset.)*
- [x] Define relation keys.
- [x] Define missing-data representation. *(D-12 availability + expected discharge summary rule.)*
- [x] Write a concise `data-contract.md` or equivalent. *(All six above: [data-contract.md](data-contract.md) v1, frozen.)*

## Evaluation contract

- [ ] Define expected case outcomes. *(Golden values proposed in §0.5; confirm and put in ground truth.)*
- [ ] Define metric formulas. *(Field mapping in §0.7; formulas are yours.)*
- [x] Define benchmark result format. *(Runner output, Data Contract §6.)*
- [ ] Define pass/fail criteria for golden cases.
- [x] Confirm no ground truth is exposed to agent-readable repositories. *(Backend guards + tests; re-check in governance QA.)*

---

# PHASE 1 — Synthetic Data Schema

**Updated:** the schema is fixed by [data-contract.md](data-contract.md) §3. The reference files in `apps/api/tests/fixtures/dataset/v0-interim/` show every field in use.

## Patient

- [ ] `patient_id`
- [ ] pseudonymous only.
- [ ] minimal synthetic metadata only if required.

## Provider

- [ ] `provider_id`
- [ ] synthetic FKRTL/provider name or label.
- [ ] type/location only if needed for prototype logic. *(`provider_type`, optional `hospital_class`, `region`.)*

## Episode

- [ ] `episode_id`
- [ ] `patient_id`
- [ ] `provider_id`
- [ ] encounter type.
- [ ] start/end timestamps. *(Inpatient needs `end_at` for readmission intervals.)*
- [ ] diagnosis. *(`primary_diagnosis` + optional `secondary_diagnoses`.)*
- [ ] procedure IDs. *(`procedures: [{code, performed_at?}]`, ICD-9-CM.)*
- [ ] ~~note IDs~~ **Updated:** notes reference their episode (`clinical_notes.episode_id`), not the other way round.

## Claim

- [ ] `claim_id`
- [ ] `episode_id` (1:1 in v1)
- [ ] synthetic claim metadata required for screening/display. *(`claim_status` has no approved/rejected values.)*

## Clinical note

- [ ] `note_id`
- [ ] `episode_id`
- [ ] note type.
- [ ] text. *(`null` iff not available.)*
- [ ] created timestamp. *(`authored_at`.)*
- [ ] **New:** `language`, `availability`, optional `title`.

## Policy document

- [ ] `policy_id`
- [ ] title. *(`document_title`.)*
- [ ] section.
- [ ] content. *(`text`.)*
- [ ] source metadata. *(`source_ref`, optional `source_url`.)*
- [ ] version/effective date where available.
- [ ] **New:** `topics` (drives retrieval filtering, §0.4).

## Ground truth

**Updated:** follow [data-contract.md](data-contract.md) §3.7.

- [ ] ~~`case_id`~~ **Updated:** `gt_id` + `anchor_episode_ids` (join key; full sorted episode group).
- [ ] case class. *(`scenario_class`, plus `golden_case` A–E or null.)*
- [ ] expected related episodes. *(`expected_related_episode_ids`.)*
- [ ] expected relevant evidence IDs/types. *(`expected_evidence: [{source_type, source_id, requirement_key, category, mandatory}]`.)*
- [ ] expected exception/context. *(`expected_exceptions`: requirement keys.)*
- [ ] expected stop behavior. *(`expected_stop_reason`.)*
- [ ] expected final investigation state. *(`expected_outcome`; optional `expected_requirement_states`.)*

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
- [ ] diagnoses/procedures. *(Inside `episodes.jsonl`.)*
- [ ] clinical notes.
- [ ] policy corpus separately.
- [ ] ground truth separately.
- [ ] **New:** `manifest.json` per dataset and per policy corpus (data-contract §2.1).

## CLI/script

- [ ] Generate.
- [ ] Reset.
- [x] Validate schema. *(Provided: `episight batch … --mode RULES_ONLY` or `episight seed --dataset …`.)*
- [x] Optional seed DB helper with Person 1. *(Provided: `episight seed --dataset <dir> --policies <dir>`.)*

---

# PHASE 3 — ~~Four~~ Five Golden Cases

## Case A — Legitimate Readmission

- [ ] Same/similar diagnosis. *(Screening needs the same primary ICD-10 code.)*
- [ ] Same provider as defined by screening.
- [ ] Short interval.
- [ ] Emergency context exists. *(In the **repeat** episode's notes; `admission_type` null.)*
- [ ] Chronic condition or legitimate clinical context exists if appropriate.
- [ ] Supporting risk signal still exists.
- [ ] Expected behavior: surface explanatory context, not autonomous final judgement. *(`EVIDENCE_SUFFICIENT` / `SUFFICIENT_EVIDENCE`.)*

## Case B — Potential Fragmentation

- [ ] Repeated outpatient care.
- [ ] Short interval.
- [ ] Same/relevant diagnosis.
- [ ] Legitimate justification absent or incomplete.
- [ ] Expected behavior: ~~continue investigation or preserve unresolved concern~~ **Updated (D-05):** `HUMAN_REVIEW_REQUIRED` / `EVIDENCE_PATHS_EXHAUSTED`; brief states the risk is unresolved.

## Case C — Scheduled Procedure

- [ ] Related procedures.
- [ ] Planned/staged interval.
- [ ] Scheduled-care/supporting note exists. *(Put the planned ICD-9-CM code in the plan sentence; record the same code as performed in the later episode.)*
- [ ] Risk signal should still be plausible at screening level.
- [ ] Expected behavior: recognize legitimate planned-care context. *(`EVIDENCE_SUFFICIENT`; SCHEDULE_CONSISTENCY = FOUND.)*

## Case D — Missing Evidence

- [ ] Risk signal exists.
- [ ] Important contextual source is missing/unavailable. *(Register the repeat episode's notes as `UNAVAILABLE`/`RESTRICTED` with `text: null`.)*
- [ ] Agent should not infer missing context.
- [ ] Expected behavior: explicit uncertainty + human review. *(`EVIDENCE_UNAVAILABLE` / `REQUIRED_EVIDENCE_UNAVAILABLE`.)*

## Case E — Conflicting Evidence — **New (D-01)**

- [ ] Risk signal exists.
- [ ] One available source affirms a context (e.g. triage documents an emergency presentation).
- [ ] Another available source negates it (e.g. discharge summary states an elective admission / no emergency).
- [ ] Expected behavior: both sides visible, human review. *(`EVIDENCE_CONFLICTING` / `CONFLICTING_EVIDENCE`.)*

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

- [ ] First milestone: ~~4~~ 5 golden cases.
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
- [ ] Vary wording across cases. *(See the phrase list in §0.4; misses are findings to report.)*
- [ ] Do not always state the answer with exact benchmark keywords.
- [ ] Include useful context naturally.
- [ ] Include irrelevant information/noise in some cases.
- [ ] Include incomplete notes in missing-evidence cases.
- [ ] Include conflicting notes in conflict cases.
- [ ] **New:** put context in the episodes the engine reads for that question (§0.4 scope table).

## Context types to encode

- [ ] emergency;
- [ ] chronic condition;
- [ ] scheduled procedure;
- [ ] planned follow-up / supporting-exam result consultation;
- [ ] clinical justification;
- [ ] no documented justification;
- [ ] ambiguous statement.

## QA

- [ ] Every note links to correct episode.
- [ ] Expected evidence labels are documented in ground truth.
- [ ] Notes do not accidentally leak “ground_truth=…” style labels. *(The validator also rejects label-like fields: `scenario`, `label`, `case_class`, `ground_truth`, `expected_*`, `is_fraud`, `is_legitimate`.)*

---

# PHASE 6 — Policy Knowledge Base

## Corpus fields

- [ ] policy ID.
- [ ] title.
- [ ] section.
- [ ] text/content.
- [ ] source metadata.
- [ ] version/effective date where supported.
- [ ] **New:** `topics` (§0.4).

## Preparation

- [ ] Include only verified relevant policy content from the refined project source material.
- [ ] Keep citation/source information.
- [ ] Prepare chunks suitable for retrieval. *(One JSONL row per section; the first sentence is shown as the excerpt.)*
- [ ] Label expected policy relevance for benchmark cases where applicable.
- [ ] **New:** replace the interim placeholder sections (`POL-INTERIM-*`).

## QA

- [ ] No invented regulation.
- [ ] No unsupported exception rule.
- [x] Policy metadata survives ingestion into Person 1 retrieval system. *(Version, source_ref, URL and effective date are carried into evidence and the brief.)*

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

*(Backend unit tests already cover every case above on synthetic fixtures, and the interim dataset includes each as a patient. Your fixtures should cover them in the official dataset. Interval definitions: §0.4.)*

For every fixture:

- [ ] expected signal type.
- [ ] expected related episodes.
- [ ] expected reason codes. *(Screening reports `rule_id` + per-pair `matched` flags; data-quality codes `MISSING_TIMESTAMP`, `DUPLICATE_EPISODE_ROW`.)*
- [ ] expected no-signal where applicable.

---

# PHASE 8 — Evidence Relevance Labels

## Label each benchmark evidence item as

- [ ] supporting risk.
- [ ] explaining legitimate context.
- [ ] neutral/background.
- [ ] irrelevant/noise.

*(**Updated:** label against the engine's identity `(source_type, source_id, requirement_key)`. For notes, `source_id` is the note ID; the engine cites individual sentences, so several evidence items can share one note.)*

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

*(Field mapping for every metric: §0.7.)*

## Episode Recall

- [ ] Define expected related-episode set.
- [ ] Compare against reconstructed set.
- [ ] Document formula and edge cases.

## Evidence Retrieval Precision

- [ ] Define relevant retrieved evidence.
- [ ] Define how duplicate evidence is handled. *(The engine dedupes per run; one sentence can be evidence for two requirements.)*
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

- [ ] Measure from investigation start to terminal/brief-ready state. *(`elapsed_ms`.)*
- [ ] Keep environment/hardware caveat documented.

## Traceability

- [ ] Define material brief items. *(The brief marks statements `material: true`.)*
- [ ] Count source-backed vs unsupported material items. *(`brief_traceability`.)*
- [ ] Document formula.

---

# PHASE 10 — Evaluation Harness

**Updated:** running is done by `episight batch` (Person 1). Your harness only scores.

## Runner behavior

- [x] Load benchmark case list. *(The batch runs every screened case; `--case` filters.)*
- [x] ~~Trigger Person 1 backend investigation~~ Run investigations. *(`episight batch`, no HTTP needed.)*
- [x] Wait for terminal state.
- [x] Capture: *(all in `<MODE>.json`)*
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

- [x] JSON. *(Runner output.)*
- [x] CSV where useful. *(Runner CSV per mode.)*
- [ ] Human-readable summary. *(The runner's `summary.md` compares modes; your metric report is still needed.)*

## Reproducibility

- [x] Record dataset version/seed. *(`header.dataset_version`; seed in your manifest.)*
- [x] Record backend/agent version or git commit if practical. *(`header.code_version`, `config_hash`, prompt version.)*
- [x] Record policy corpus version. *(`header.corpus_version`.)*

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
- [ ] human review required. *(`EVIDENCE_CONFLICTING`.)*

---

# PHASE 13 — Regression Testing

## Golden regression suite

- [ ] Run Case A.
- [ ] Run Case B.
- [ ] Run Case C.
- [ ] Run Case D.
- [ ] **New:** Run Case E.

*(Backend CI already runs A–E on the interim data on every push. You run them on the official dataset with `episight batch --mode FULL_RULE_PLANNER` (deterministic) and `--mode FULL` with replay.)*

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

Verify the actual prototype behavior (backend tests that already enforce an item are noted):

- [ ] Synthetic data only.
- [ ] Pseudonymous patient IDs.
- [ ] No real JKN participant data.
- [ ] No autonomous fraud verdict. *(Brief validator bans decision language; enum and API-surface tests.)*
- [ ] No autonomous claim rejection. *(Same.)*
- [ ] No payment decision. *(Same.)*
- [ ] No record modification by agent. *(Tools are read-only; source tables are written only by ingest.)*
- [ ] Missing evidence remains explicit. *(Golden D tests.)*
- [ ] Conflicting evidence remains visible. *(Golden E tests.)*
- [ ] Human review state exists. *(`review_status`, `human_decision_notice` in every brief.)*
- [ ] Evidence provenance exists. *(Literal-excerpt provenance check on every evidence item.)*
- [ ] Policy source/version metadata preserved where available.
- [ ] Tool failures are not replaced by fabricated answers. *(Failure tests: tool error, hung tool, timeout.)*

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
- [ ] correct representation of missing evidence. *(`NOT_FOUND` vs `UNAVAILABLE`; see Person 2 plan §0.5.)*
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

- [x] Data contract. *(Frozen v1.)*
- [ ] Synthetic generator.
- [ ] ~~4~~ 5 golden cases.
- [ ] Ground truth isolation. *(Keep it under `data/ground-truth/`; backend side enforced.)*
- [ ] Synthetic clinical notes.
- [ ] Policy corpus (replacing placeholders).
- [ ] Screening fixtures.
- [ ] evidence relevance labels.
- [ ] metric definitions.
- [ ] ~~basic evaluation runner~~ **scoring harness** (runner provided).
- [ ] governance QA.
- [ ] golden-case E2E QA.

## P1 — Strongly recommended

- [ ] 20+ benchmark cases.
- [ ] hard-positive/hard-negative balance.
- [ ] regression automation.
- [ ] aggregate metric report.
- [ ] policy retrieval quality labels.
- [ ] systematic failure categorization.
- [ ] **New:** ablation report (four modes) for the proposal's §13 claim.

## P2 — Stretch

- [ ] 50-case benchmark.
- [ ] richer case generator controls.
- [ ] benchmark dashboard data feed.
- [ ] deeper slice analysis by case class.
- [ ] repeated-run variance analysis if the agent has nondeterministic behavior. *(Supported: `--repeats N`.)*

---

# Daily / PR Checklist

Before merging data/evaluation changes:

- [ ] Dataset still validates against schema. *(`episight batch … --mode RULES_ONLY`.)*
- [ ] Golden cases remain deterministic.
- [ ] Ground truth is still isolated.
- [ ] No real patient data has been introduced.
- [ ] Policy content remains sourceable/verified.
- [ ] Metric formula changes are documented.
- [ ] Regression suite rerun if relevant.
- [ ] Person 1 informed of schema changes.
- [ ] Person 2 informed of terminology/status changes.
- [ ] No API key committed (`apps/api/.env` is git-ignored).

---

# Final Definition of Done — Person 3

- [ ] Synthetic dataset is reproducible.
- [ ] ~~Four~~ Five golden cases are stable and documented.
- [ ] 20+ benchmark cases exist, or the limitation is explicitly documented if time prevents it.
- [ ] Ground truth is hidden from the agent.
- [ ] Clinical notes are synthetic and useful for retrieval testing.
- [ ] Policy corpus is sourceable and version-aware where possible.
- [ ] Screening fixtures cover boundary conditions.
- [ ] Evidence relevance labels support precision/coverage metrics.
- [ ] Evaluation runner executes without manual case-by-case intervention. *(Runner provided; harness must chain on it.)*
- [ ] Aggregate metrics are reproducible.
- [ ] Missing/conflicting evidence cases behave correctly.
- [ ] Governance checklist passes.
- [ ] End-to-end golden-case QA passes.
