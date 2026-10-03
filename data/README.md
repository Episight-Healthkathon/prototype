# EPISIGHT data (Person 3)

Official synthetic dataset, policy corpus and hidden ground truth (Data Contract v1 §2).

```text
data/
├── generator/generate_dataset.py   # deterministic generator (stdlib only) + tests
├── synthetic/v0.1.0/               # agent-readable dataset: manifest + 5 JSONL files
├── policies/pc-0.1.0/              # curated policy corpus (Permenkes 26/2021, readmisi/fragmentasi)
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
  --policies ../../data/policies/pc-0.1.0 --mode RULES_ONLY
```

## Tests

```bash
uv run --project apps/api pytest data/generator/tests evaluation/tests
```

## Content

- 5 golden cases (A–E), 15 benchmark cases and 8 screening fixtures that must not be flagged, plus
  12 noise patients. See `ground-truth/v0.1.0/README.md` for the scenario table. Do not read it into
  anything the agent can see.
- Policy corpus `pc-0.1.0`: four sections (definition + exceptions for readmission and fragmentation)
  taken from the operational definitions in the final proposal (§3), which cites Permenkes 26/2021.
  **Still to do:** check the wording word for word against the JDIH PDF before calling it an official
  quote. `source_ref` and the corpus manifest (`status`) say so.
