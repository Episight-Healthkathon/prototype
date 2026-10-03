# Benchmark findings for Person 1 — dataset v0.1.0, code 001ee96

Source: `evaluation/reports/v0.1.0-baseline/` (deterministic modes; FULL with the AI planner not run
yet). Case JSON: rerun `uv run episight batch --case <CASE_ID> ...` or read `scores.json`.

## F-1 · RULES_RETRIEVAL never opens SCHEDULE_CONSISTENCY → unsafe closure (GT-B06)

- **Case:** `CASE-RA-79ad8dec` (GT-B06). The plan in episode 1 names ICD-9-CM 36.06; episode 2 records
  36.07.
- **FULL_RULE_PLANNER:** `SCHEDULE_CONSISTENCY = CONFLICTING` → `EVIDENCE_CONFLICTING`. Correct.
- **RULES_RETRIEVAL:** `SCHEDULE_CONSISTENCY` is absent from `requirement_states`, so the case closes as
  `EVIDENCE_SUFFICIENT`. This is the only unsafe closure in the benchmark. GT-C and GT-B05 also lose the
  consistency check in this mode (their outcome is still right).
- **Question:** is it intended that the non-adaptive baseline never runs the spawned
  `SCHEDULE_CONSISTENCY` requirement? If yes, this is a strong ablation result for the proposal (§13):
  adaptive planning prevents a wrong closure. If no, it's a bug in how the baseline enumerates
  actions.

## F-2 · Emergency described without keywords is missed (GT-B09, by design)

- **Case:** `CASE-RA-6b3ce4c9` (GT-B09). The repeat triage note says the patient arrived by ambulance
  after vomiting blood, was hypotensive (80/50) and tachycardic (128) and was treated in the
  resuscitation room ("ruang resusitasi"). None of IGD, gawat darurat, triase, syok or cito appears.
- **All modes:** `EMERGENCY_CONTEXT = NOT_FOUND` → `HUMAN_REVIEW_REQUIRED`. The ground truth expects
  `EVIDENCE_SUFFICIENT`.
- **Note:** this is not an unsafe outcome (the case escalates instead of closing). It is a lexical
  robustness gap and the case where the M10 LLM passage classifier, or extra phrases such as
  "ruang resusitasi", "ambulans" or "datang dengan ambulans", would show value. Please don't
  overfit the lexicon to this exact sentence; more paraphrase cases will follow.

## Data-side notes (for awareness, no action)

- The SCHEDULE_CONSISTENCY code is extracted only when the code is in the **same sentence** as the
  scheduled phrase. My first Case C draft split them and failed; the dataset now complies (§0.4).
- `RULES_ONLY` reaches `NO_ACTIONABLE_GAP` for every case (0/5 golden). That's expected for the
  baseline.
- Policy retrieval is now 100% on-topic with the split corpus (definition + exceptions per signal
  type). The interim corpus cited the fragmentation section on readmission cases.
