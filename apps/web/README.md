# EPISIGHT reviewer frontend

Next.js App Router + React + TypeScript, using generated API Contract v1 types.

From the repository root:

```powershell
pnpm install
pnpm dev
```

Open http://127.0.0.1:3001. Port 3001 avoids the Grafana service on this machine.
The same-origin `/api/v1` proxy targets FastAPI on port 8000; set `EPISIGHT_API_URL`
in `apps/web/.env` when the backend runs elsewhere. No model keys belong in the browser.

## Data modes

- **API lokal:** the real API, database, background investigations and persisted run history.
- **Demo offline:** official synthetic v0.1.0 + pc-0.1.1 engine snapshots, served locally.
  The demo plays a recorded midpoint then the completed state; it does not execute a new
  investigation or AI request. Playback state lives in `sessionStorage`. Switching mode
  persists in `localStorage`. A URL with `?mode=demo` or `?mode=live` selects an explicit mode.

Default investigation mode is `FULL_RULE_PLANNER` (rules + retrieval). The API UI also
offers `FULL`, whose AI configuration and fallback remain server-controlled.

## Backend used for frontend QA

The local QA run uses **episight_frontend**, a separate PostgreSQL database, preserving
the existing `episight` database. To reproduce on a fresh machine:

```powershell
docker compose up -d --wait
docker compose exec db psql -U episight -d postgres -c "CREATE DATABASE episight_frontend OWNER episight;"
cd apps/api
$env:EPISIGHT_DATABASE_URL='postgresql+psycopg://episight:episight@localhost:5433/episight_frontend'
$env:EPISIGHT_LLM_PROVIDER='none'
uv run episight db upgrade
uv run episight seed --dataset ../../data/synthetic/v0.1.0 --policies ../../data/policies/pc-0.1.1
uv run uvicorn episight.main:app --host 127.0.0.1 --port 8000
```

Seeding replaces data in the configured database. Run it only when preparing that
isolated demo database, not on an existing working dataset. On later starts, just run
Docker and uvicorn with the same database URL; migration and seeding are not required again.

## Checks

```powershell
pnpm check
pnpm test
pnpm build
pnpm --filter @episight/web test:api
```

`test:api` requires the running API and frontend. It investigates/reruns five synthetic
cases, checks all evidence sources and saves `test-results/api-smoke.json` locally.
It does not read ground truth or invoke a paid model.

Regenerate demo snapshots from the official runtime dataset:

```powershell
cd apps/api
uv run python ../web/scripts/generate-demo.py
```

Generated API types and shared interim fixtures remain unchanged. Demo fixtures in
`public/demo` are generated outputs, not handwritten patient data.

## Routes and boundaries

- `/`: landing page with official logo, four interactive story slides and five case examples.
- `/cases`: search, signal/progress/outcome filters, sorting and pagination.
- `/cases/{case_id}`: overview, expandable episode timeline, investigation workspace,
  evidence gaps, categorized evidence, action trail, run history and reviewer brief.
- `/cases/{case_id}?view=workspace` or `?view=brief`: direct links to those screens.
- `/guide`: reviewer terminology, evidence states and prototype limits.
- Shared evidence drawer: literal excerpt, full source highlight, structured values,
  source availability, policy link/version, retrieval reason and provenance.

Source offsets use Unicode code points to match Python rather than UTF-16 indices.
The brief can be printed through the browser. Reviewer-note persistence and claim
decisions are not implemented or simulated; the backend has no corresponding supported action.

All patient/provider identities are synthetic. The supplied reference slide is explicitly
labelled illustrative; its dates and classifications do not override API data.
