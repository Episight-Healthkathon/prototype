# EPISIGHT evaluation (Person 3)

| File | Purpose |
|---|---|
| `score.py` | Scoring harness: runner output + ground truth → `scores.json`, `per_case_<MODE>.csv`, `report.md` |
| `METRICS.md` | Metric formulas and edge cases |
| `run_regression.sh` | Regenerate (freshness check) → batch (3 deterministic modes) → score → fail if a golden case fails |
| `reports/v0.1.0-pc-0.1.1-backend/` | Current deterministic regression baseline: verified corpus + emergency-care matcher |
| `reports/v0.1.0-baseline/` | Historical deterministic baseline, before Person 1's fixes |
| `reports/v0.1.0-full/` | All four modes incl. FULL (OpenAI `gpt-4o-mini`, 3 repeats) |
| `FINDINGS.md` | Benchmark findings reported to Person 1 |
| `runs/` | Scratch run output (git-ignored) |

## Deterministic benchmark (no key needed)

```bash
bash evaluation/run_regression.sh my-run       # writes evaluation/runs/my-run/report.md
```

## AI planner (FULL) benchmark: needs a key

Use `pc-0.1.1` for a new benchmark. The committed `v0.1.0-full` report and recordings describe the
older backend/corpus and are retained as historical evidence, not a benchmark of the new matcher.

Create `apps/api/.env` (git-ignored) from `.env.example` with one key, for example:

```
OPENAI_API_KEY=sk-...
EPISIGHT_LLM_PROVIDER=openai
EPISIGHT_LLM_MODEL=gpt-4o-mini
```

Then:

```bash
cd apps/api
uv run episight batch --out ../../evaluation/runs/full --dataset ../../data/synthetic/v0.1.0 \
  --policies ../../data/policies/pc-0.1.1 --mode all --repeats 3 --recordings ../../evaluation/runs/full/recordings
cd ../..
python evaluation/score.py --run evaluation/runs/full --ground-truth data/ground-truth/v0.1.0/cases.jsonl \
  --baseline evaluation/reports/v0.1.0-pc-0.1.1-backend/scores.json --fail-on-regression
```

Without a key, FULL falls back to the rule planner every step (`fallback_steps` > 0 in the report), so
it is not an AI-planner result. To re-score later without calling the model, set
`EPISIGHT_LLM_REPLAY=replay`.

### Reproduce the committed FULL report without a key

`reports/v0.1.0-full/recordings/` holds the model responses from that run (one folder per repeat).
Replay answers only from them. Reproduce them on the **historical backend revision `240039e`** with
the old corpus; the new matcher changes subsequent planner inputs, so the old recordings cannot
prove a new FULL result. Never disable replay to silently fall back to paid calls.

```bash
cd apps/api
EPISIGHT_LLM_PROVIDER=openai EPISIGHT_LLM_MODEL=gpt-4o-mini OPENAI_API_KEY=replay EPISIGHT_LLM_REPLAY=replay \
  uv run episight batch --out ../../evaluation/runs/full-replay --dataset ../../data/synthetic/v0.1.0 \
  --policies ../../data/policies/pc-0.1.0 --mode FULL --repeats 3 \
  --recordings ../../evaluation/reports/v0.1.0-full/recordings
```

Baseline machine: AMD64 Family 25 (Windows 11), Python 3.12 via uv. `elapsed_ms` depends on the machine.

## Regression gate

The script requires all three deterministic mode files and compares against the current baseline.
Missing cases/repeats, screening errors, new case/state failures and falling quality metrics fail.
Unsafe closures or invalid briefs/tools always fail in full modes. Weak ablation modes may retain
their documented baseline failures. `--baseline` alone reports differences; add
`--fail-on-regression` to enforce them. Use a fresh run name when switching modes/corpora.
