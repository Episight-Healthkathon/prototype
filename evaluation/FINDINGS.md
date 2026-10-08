# Benchmark findings for Person 1 — dataset v0.1.0, code 001ee96

**Fresh FULL follow-up — 2026-10-08, backend `90e914f`:**
`reports/v0.1.0-pc-0.1.1-full/` runs the verified corpus with `gpt-4o-mini`, three
repeats: 60/60 outcomes and stop reasons correct, golden 5/5 per repeat, coverage
100%, zero unsafe closures and no unstable outcomes. GT-B09 passes 3/3. All 60
case objects replay identically except timing fields. The 625 calls had no API
errors; 17 steps needed a validation retry and one fell back after rejection
(GT-B13, repeat 1). Mean latency 18.6 s vs 16 ms for FULL_RULE_PLANNER; quality
metrics remain equal on this dataset, so F-3's lack of demonstrated AI-planner
advantage still holds. Exception precision is 90.91% under the unchanged GT-B06
label interpretation. Full details and the replay archive are in the new report.

**2026-10-08 follow-up:** F-2 is fixed by a conservative active-resuscitation-care matcher.
The new deterministic report is `reports/v0.1.0-pc-0.1.1-backend/`: 20/20 outcomes, A–E 5/5,
coverage 100%, no unsafe closures in FULL_RULE_PLANNER. Source policy transcription and the
regression gate were also corrected. The findings below describe the historical benchmark;
F-1 remains an ablation limitation. The detailed F-3 section describes the old AI
run; the fresh-run evidence is summarized above.

Source: `evaluation/reports/v0.1.0-baseline/` (deterministic modes) and `evaluation/reports/v0.1.0-full/`
(all four modes, FULL with OpenAI `gpt-4o-mini`, prompt `planner-2`, 3 repeats). Case JSON: rerun
`uv run episight batch --case <CASE_ID> ...` or read `scores.json`.

## F-1 · RULES_RETRIEVAL never opens SCHEDULE_CONSISTENCY → unsafe closure (GT-B06)

- **Case:** `CASE-RA-79ad8dec` (GT-B06). The plan in episode 1 names ICD-9-CM 36.06; episode 2 records
  36.07.
- **FULL_RULE_PLANNER:** `SCHEDULE_CONSISTENCY = CONFLICTING` → `EVIDENCE_CONFLICTING`. Correct.
- **FULL (AI planner):** same as FULL_RULE_PLANNER in all 3 repeats. Correct.
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
  `EVIDENCE_SUFFICIENT`. The AI planner doesn't help (3/3 repeats miss it): it chooses which tool to
  call next, but the tools still decide FOUND/NOT_FOUND by keyword, so a better plan can't find a
  passage the matcher doesn't recognise.
- **Note:** this is not an unsafe outcome (the case escalates instead of closing). It is a lexical
  robustness gap and the case where the M10 LLM passage classifier, or extra phrases such as
  "ruang resusitasi", "ambulans" or "datang dengan ambulans", would show value. Please don't
  overfit the lexicon to this exact sentence; more paraphrase cases will follow.

## F-3 · AI planner (FULL) equals the rule planner on v0.1.0

- **Result:** FULL scores the same as FULL_RULE_PLANNER on every metric (outcome 95%, golden 5/5,
  coverage 93%, 0 unsafe closures, brief traceability 100%). All 20 cases reached the same outcome in
  all 3 repeats (no unstable cases). Avg 10.2 steps vs 10.1.
- **Planner health:** 612 steps; 596 accepted on the first answer, 14 after one validation retry,
  2 fell back to the rule planner after the retry was also rejected (`CASE-RA-0bbfc334` GT-A and
  `CASE-RA-49e2e3ed` GT-B10, both repeat 0; outcomes still correct). No API errors.
- **Cost of the AI planner:** avg ~16.9 s per investigation vs ~6 ms for the rule planner.
- **Replay:** `EPISIGHT_LLM_REPLAY=replay` with the recordings reproduces all 60 FULL runs exactly with
  no valid key.
- **For the proposal (§13):** on this data the gain comes from the adaptive, requirement-driven loop
  (F-1, golden C), not from the model choosing actions. Where the model could add value is reading
  passages (F-2, M10), which the planner alone doesn't do.

## Data-side notes (for awareness, no action)

- The SCHEDULE_CONSISTENCY code is extracted only when the code is in the **same sentence** as the
  scheduled phrase. My first Case C draft split them and failed; the dataset now complies (§0.4).
- `RULES_ONLY` reaches `NO_ACTIONABLE_GAP` for every case (0/5 golden). That's expected for the
  baseline.
- Policy retrieval is now 100% on-topic with the split corpus (definition + exceptions per signal
  type). The interim corpus cited the fragmentation section on readmission cases.
