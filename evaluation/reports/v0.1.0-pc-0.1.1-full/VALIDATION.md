# Fresh FULL benchmark — 2026-10-08

Backend `90e914f` (`main`), dataset `v0.1.0`, verified policy corpus `pc-0.1.1`.
Synthetic inputs and ground-truth labels were unchanged. OpenAI `gpt-4o-mini`,
prompt `planner-2`, max 12 steps, three independent repeats of all 20 cases.
The run loaded the existing backend and explicitly selected live OpenAI settings;
its small wrapper stops on three consecutive API errors. Backend source was unchanged.

Live run: **16:55:29–17:14:09 WIB**, 1,120.530 seconds (18 minutes 41 seconds)
including deterministic modes. FULL averages 18.605 seconds per investigation.
There were 625 model requests and zero API errors. An earlier attempt with an
invalid key is separate and contributes no result or recording to this benchmark.

## Results and limitations

- FULL: 60/60 correct outcomes and stop reasons, all 20 cases correct in all three
  repeats. Golden A–E passes 5/5 in every repeat. No missing runs or unstable outcomes.
- Screening and episode recall, mandatory evidence coverage, evidence precision,
  requirement-state accuracy and brief traceability: 100%. No unsafe closure,
  brief validation failure or tool failure.
- Planner: 607 executed steps; 589 decisions accepted immediately, 17 accepted
  after a validation retry, one rule fallback after both answers were rejected.
  Fallback: GT-B13 / `CASE-RA-5bfa9633`, repeat index 1. Its outcome remained correct.
  The generated report's AI-step row counts first-answer decisions (589);
  `summary.md` counts both first-answer and retry decisions (606).
- Exception precision remains 30/33 (90.91%), recall 100%, exact-match case accuracy
  95%. All three false positives are the existing GT-B06 scoring interpretation:
  scheduled context is FOUND while procedure consistency is CONFLICTING.
  Outcome and state labels remain correct; labels were not adjusted to improve metrics.
- FULL_RULE_PLANNER: 20/20 correct outcomes, 5/5 golden, zero unsafe closures.
  Its measured mean latency is 16 ms. FULL has no measured quality advantage over
  it on this small synthetic benchmark and is slower.
- RULES_RETRIEVAL retains its known GT-B06 ablation weakness: one unsafe closure,
  19/20 correct outcomes. RULES_ONLY remains an intentionally weak ablation.
  These results do not establish performance on real claims or broader paraphrases.

## Verification

The scoring command required all four mode files and passed `--fail-on-regression`
against `../v0.1.0-pc-0.1.1-backend/scores.json`. This baseline compares the three
deterministic modes; FULL additionally passed completeness, golden, safety and
brief/tool checks. Independently joining raw results to the 20 positive anchor
sets verified all 60 expected slots, outcomes, stop reasons and labelled states.
All eight must-not-flag fixtures stayed out of screening.

Replay used the backend's replay-only client: no API call or valid key was needed.
All 60 case objects matched the live run after excluding only `elapsed_ms` and
`brief.generated_at`. This comparison includes evidence, requirement states,
brief content, planner provenance, counts, validation results and outcomes.
See `verification.json` for the machine-readable verification result.

`replay_bundle.zip` contains all four raw mode outputs, the 625 recorded model
responses, the runner/verification scripts and run metadata. It includes no env
file or credentials. Every archive member was checked against its original SHA-256
and the archive passed its CRC check; `manifest.json` records source/member hashes.

## Reproduce without API calls

Use backend revision `90e914f` and run these commands from the repository root:

```powershell
uv run --project apps/api python -c "from zipfile import ZipFile; ZipFile('evaluation/reports/v0.1.0-pc-0.1.1-full/replay_bundle.zip').extractall('evaluation/runs/full-pc011-reproduce')"
uv run --project apps/api python evaluation/runs/full-pc011-reproduce/verify_replay.py
uv run --project apps/api python evaluation/score.py --run evaluation/runs/full-pc011-reproduce --ground-truth data/ground-truth/v0.1.0/cases.jsonl --baseline evaluation/reports/v0.1.0-pc-0.1.1-backend/scores.json --fail-on-regression --require-mode FULL --require-mode FULL_RULE_PLANNER --require-mode RULES_ONLY --require-mode RULES_RETRIEVAL
```

The verification script compares freshly replayed FULL output to the archived live
run. Scoring all four archived mode outputs reproduces the reported quality metrics;
wall time and replay time are deliberately separate.
