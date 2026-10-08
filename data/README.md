# EPISIGHT data (Person 3)

Official synthetic dataset, policy corpus and hidden ground truth (Data Contract v1 §2).

```text
data/
├── generator/generate_dataset.py   # deterministic generator (stdlib only) + tests
├── synthetic/v0.1.0/               # agent-readable dataset: manifest + 5 JSONL files
├── policies/pc-0.1.1/              # verified source transcription (Permenkes 26/2021, p. 55)
└── ground-truth/v0.1.0/            # evaluation only: cases.jsonl + README (scenario table)
```

## Regenerate

```bash
python data/generator/generate_dataset.py            # seed 20261004 -> v0.1.0 (byte-identical every time)
python data/generator/generate_dataset.py --seed 7 --noise-patients 30 --version v0.1.0-s7
python data/generator/generate_dataset.py --reset    # wipe the version's dataset + ground truth first
```

Golden cases A–E use no randomness and are identical for every seed. Benchmark cases take small date
shifts and wording variants from the seed; noise patients are random but can never be flagged.

## Validate and run

```bash
cd apps/api
uv run episight batch --out ../../evaluation/runs/validate --dataset ../../data/synthetic/v0.1.0 \
  --policies ../../data/policies/pc-0.1.1 --mode RULES_ONLY
```

## Tests

```bash
uv run --project apps/api pytest data/generator/tests evaluation/tests
```

## Content

- 5 golden cases (A–E), 15 benchmark cases and 8 screening fixtures that must not be flagged, plus
  12 noise patients. See `ground-truth/v0.1.0/README.md` for the scenario table. Do not read it into
  anything the agent can see.
- Policy corpus `pc-0.1.1`: four sections transcribed from the official JDIH Kemenkes PDF, page 55,
  verified on 2026-10-08; only whitespace/line wrapping is normalized. Includes the complete
  supporting-exam exception and its one-episode qualification. Effective date: 2021-08-30.
  See `policies/pc-0.1.1/VERIFICATION.md` for sources and the comparison with the old summaries.
- `pc-0.1.0` remains a historical, unverified summary for the committed old benchmark/recordings.
  The synthetic dataset and ground-truth labels are unchanged.
