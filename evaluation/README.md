# EPISIGHT evaluation (Person 3)

| File | Purpose |
|---|---|
| `score.py` | Scoring harness: runner output + ground truth → `scores.json`, `per_case_<MODE>.csv`, `report.md` |
| `METRICS.md` | Metric formulas and edge cases |
| `run_regression.sh` | Regenerate (freshness check) → batch (3 deterministic modes) → score → fail if a golden case fails |
| `reports/v0.1.0-baseline/` | Committed baseline report (diff against it with `--baseline`) |
| `reports/v0.1.0-full/` | All four modes incl. FULL (OpenAI `gpt-4o-mini`, 3 repeats) |
| `FINDINGS.md` | Benchmark findings reported to Person 1 |
| `runs/` | Scratch run output (git-ignored) |

## Deterministic benchmark (no key needed)

```bash
bash evaluation/run_regression.sh my-run       # writes evaluation/runs/my-run/report.md
```

## AI planner (FULL) benchmark: needs a key

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
  --policies ../../data/policies/pc-0.1.0 --mode all --repeats 3 --recordings ../../evaluation/runs/full/recordings
cd ../..
python evaluation/score.py --run evaluation/runs/full --ground-truth data/ground-truth/v0.1.0/cases.jsonl \
  --baseline evaluation/reports/v0.1.0-baseline/scores.json
```

Without a key, FULL falls back to the rule planner every step (`fallback_steps` > 0 in the report), so
it is not an AI-planner result. To re-score later without calling the model, set
`EPISIGHT_LLM_REPLAY=replay`.

### Reproduce the committed FULL report without a key

`reports/v0.1.0-full/recordings/` holds the model responses from that run (one folder per repeat).
Replay answers only from them, so no valid key is needed and the 60 FULL runs come out identical:

```bash
cd apps/api
EPISIGHT_LLM_PROVIDER=openai EPISIGHT_LLM_MODEL=gpt-4o-mini OPENAI_API_KEY=replay EPISIGHT_LLM_REPLAY=replay \
  uv run episight batch --out ../../evaluation/runs/full-replay --dataset ../../data/synthetic/v0.1.0 \
  --policies ../../data/policies/pc-0.1.0 --mode FULL --repeats 3 \
  --recordings ../../evaluation/reports/v0.1.0-full/recordings
```

Baseline machine: AMD64 Family 25 (Windows 11), Python 3.12 via uv. `elapsed_ms` depends on the machine.
