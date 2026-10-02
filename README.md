# EPISIGHT prototype

Evidence-first investigation copilot for **Episode Integrity** (readmission and episode fragmentation),
built for BPJS Kesehatan Healthkathon 2026. **Synthetic data only.** A risk signal starts an investigation;
it is never a verdict. EPISIGHT does not determine fraud, approve or reject claims, or make payment decisions.

Design docs: [architecture](docs/architecture.md) · [decisions](docs/decisions.md) ·
[data contract](docs/data-contract.md) · [API contract](docs/api-contract.md) · [plan](docs/development-plan.md)

## Repository layout

| Path | Owner | What |
|---|---|---|
| `apps/api/` | Person 1 | FastAPI backend: screening, episodes, investigation engine, brief |
| `apps/web/` | Person 2 | Next.js reviewer UI |
| `packages/shared-types/` | generated | OpenAPI, TypeScript types, mock fixtures (API Contract v1) |
| `data/` | Person 3 | Official synthetic dataset, policy corpus, ground truth (never ingested) |
| `evaluation/` | Person 3 | Benchmark harness and metrics |

## Backend quick start

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), and Node + pnpm (only for regenerating TS types).

```bash
docker compose up -d --wait            # PostgreSQL 16 on localhost:5433 (dev + test databases)

cd apps/api
uv sync                                # Python 3.12 environment
uv run episight db upgrade             # apply migrations
uv run episight seed                   # load the interim dataset + policy corpus, run screening
uv run uvicorn episight.main:app --reload --port 8000
```

- Health: <http://localhost:8000/api/v1/health>
- Case queue: <http://localhost:8000/api/v1/cases>
- Interactive API docs: <http://localhost:8000/api/v1/docs>

`episight seed` defaults to the interim fixtures in `apps/api/tests/fixtures/`. Point it at Person 3's
dataset once delivered:

```bash
uv run episight seed --dataset ../../data/synthetic/<version> --policies ../../data/policies/<version>
```

Seeding validates the whole delivery against Data Contract v1 and reports every problem at once. It refuses
anything under a `ground-truth` directory.

## Tests and checks

```bash
cd apps/api
uv run pytest            # unit + API tests (API tests use the episight_test database; skipped if Docker is down)
uv run ruff check src tests alembic
```

## Contract artifacts for the frontend

```bash
cd apps/api && uv run episight export-contract   # openapi.json, src/index.ts, fixtures/
cd packages/shared-types && pnpm install && pnpm generate   # src/api.d.ts
```

A test fails if the committed artifacts drift from the backend models.

## AI planner (optional key)

`FULL` mode (the default for `POST /cases/{id}/investigate`) uses an AI planner to choose the next
investigation step. The deterministic safety envelope still controls everything else (D-07). Put one key in
`apps/api/.env` (see `.env.example`) and restart the API:

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic, model `claude-opus-5-5` at low effort (with server-side refusal fallback) |
| `OPENAI_API_KEY` | OpenAI (ChatGPT), model `gpt-4o` |
| `EPISIGHT_LLM_PROVIDER` | `auto` (default: Anthropic first, then OpenAI), `anthropic`, `openai`, or `none` |
| `EPISIGHT_LLM_MODEL` | Override the model name for the chosen provider |

Without a key, or when the model errors, refuses, times out, or proposes an invalid action twice, that step
falls back to the rule planner (`planner.source = RULE_FALLBACK` in the trail). Every live call is recorded in
`planner_recordings`. `EPISIGHT_LLM_REPLAY=replay` reproduces runs from recordings without calling a model.
The test suite always runs with `EPISIGHT_LLM_PROVIDER=none`, so it never calls a paid API.

## Configuration

Environment variables (or `apps/api/.env`, see `.env.example`): `EPISIGHT_DATABASE_URL`,
`EPISIGHT_CORS_ORIGINS`, `EPISIGHT_LOG_LEVEL`, plus the AI planner variables above. Keys must never be committed.
