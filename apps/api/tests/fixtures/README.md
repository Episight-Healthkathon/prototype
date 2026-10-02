# Interim fixtures (BE-1.7)

A synthetic dataset and policy corpus, written by hand, used until Person 3's official dataset arrives
(HO-P3-1, HO-P3-3). Regenerate it with `uv run python tests/fixtures/build_interim_dataset.py`.

The data files contain no labels (Data Contract v1 §1). The scenario each patient represents is
documented **only here**, for test authors:

| Patient | Scenario | Screening expectation |
|---|---|---|
| PAT-000001 | Golden A: heart-failure readmission via the ED (emergency context in notes, `admission_type` null) | READMISSION, EPI-000101 → EPI-000102, 5 days |
| PAT-000002 | Golden B: three gastritis outpatient visits, no justification | FRAGMENTATION chain of 3 (4 d, 3 d) |
| PAT-000003 | Golden C: staged PCI, plan documented in episode 1 | READMISSION, 14 days |
| PAT-000004 | Golden D: episode-2 documents UNAVAILABLE / RESTRICTED | READMISSION, 10 days |
| PAT-000005 | Golden E: triage says ED, discharge summary says elective | READMISSION, 6 days |
| PAT-000006 | Same dx/provider 40 days apart, plus an exact duplicate row | not flagged; DUPLICATE_EPISODE_ROW |
| PAT-000007 | Second admission at a different provider | not flagged |
| PAT-000008 | Outpatient visits exactly 7 days apart; 2nd visit reviews supporting-exam results | FRAGMENTATION (boundary inclusive) |
| PAT-000009 | Different diagnoses 3 days apart, plus a record without a timestamp | not flagged; MISSING_TIMESTAMP |
| PAT-000010 | Inpatient followed by outpatient, same dx | not flagged |

The policy sections are **placeholders** that paraphrase the proposal's §3 definitions. Their
`source_ref` says so explicitly. They must be replaced by Person 3's curated corpus.
