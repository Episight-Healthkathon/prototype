# Person 1 follow-up — 2026-10-08

Dataset `v0.1.0` and hidden ground-truth labels are unchanged. Corpus `pc-0.1.1` is a verified
source transcription; see `data/policies/pc-0.1.1/VERIFICATION.md`.

These are fresh deterministic runs of the working tree based on `240039e`, rather than that
commit alone. `scores.json` headers include SHA-256 hashes of the matcher and scoring source.
The runs use Python 3.12.13 on Windows and no database or paid model. Timings are machine-dependent.

- FULL_RULE_PLANNER: 20/20 correct outcomes and stop reasons, golden A–E 5/5, mandatory evidence
  coverage 100%, no unsafe closure, no new failing case vs the old baseline. GT-B09 is fixed.
- RULES_RETRIEVAL: 19/20 correct outcomes; the known schedule-consistency ablation weakness remains.
- RULES_ONLY intentionally does not investigate clinical context.
- Exception precision remains below 100% because the metric counts FOUND scheduled context in
  GT-B06 while its performed-procedure consistency is CONFLICTING. No label was adjusted to improve it.
- FULL with the AI planner was not rerun. Old model recordings do not establish results for the new
  matcher/corpus; a fresh model benchmark requires fresh recordings.

The scoring gate now rejects incomplete cases/repeats, duplicate run indices, screening errors,
new case/state failures and quality regressions. Full modes additionally reject unsafe closures,
golden failures and brief/tool failures. The current report becomes the default deterministic
baseline, so GT-B09 cannot regress silently back to the historical 95% accuracy.

Validation completed: 483 backend unit/generator/scoring tests passed, backend Ruff checks passed,
and the complete `run_regression.sh` script passed against this baseline. Controlled missing-case,
non-golden unsafe-closure and GT-B09 regression probes all failed the gate as intended. Independent
comparison of raw outcomes and stop reasons against the 20 positive anchor groups also passed.
Database/API integration tests were not rerun for this change.

Reproduce from the repository root in a uv environment with:

```bash
PYTHON="uv run --project apps/api python" bash evaluation/run_regression.sh person1-check
```

On PowerShell, run `episight batch` for RULES_ONLY, RULES_RETRIEVAL and FULL_RULE_PLANNER with
`--policies ../../data/policies/pc-0.1.1`, then score the output with the baseline and
`--fail-on-regression --require-mode RULES_ONLY --require-mode RULES_RETRIEVAL
--require-mode FULL_RULE_PLANNER`. Do not ingest the ground-truth directory.
