# Deployment (split hosting)

Prototype deploy for demos. **Synthetic data only.**

| Part | Host | Config |
|---|---|---|
| Web (`apps/web`) | Vercel | Project settings (below) |
| API (`apps/api`) | Render, Docker, free plan | `render.yaml`, `apps/api/Dockerfile` |
| Database | Neon Postgres, free plan | Connection string only |

The browser only talks to Vercel. Next rewrites `/api/v1/*` to the API (`apps/web/next.config.ts`),
so the API needs no CORS setup and no credential ever reaches the browser.

The API must be a long-lived process: investigations run as FastAPI background tasks after
`POST /investigate` returns. Serverless functions would kill them.

## 1. Database (Neon)

1. Create a project at <https://neon.tech> (region close to the Render region, e.g. Singapore).
2. Copy the connection string (`postgresql://...?sslmode=require`). Paste it as-is:
   the API rewrites `postgres://` / `postgresql://` to the psycopg 3 driver.

## 2. Schema and data (once, from your machine)

From `apps/api`, with the database URL for this shell only:

```powershell
$env:EPISIGHT_DATABASE_URL = "<neon connection string>"
uv run episight db upgrade
uv run episight seed --dataset ../../data/synthetic/v0.1.0 --policies ../../data/policies/pc-0.1.1
Remove-Item Env:EPISIGHT_DATABASE_URL
```

`seed` **replaces** all data, including investigation history. Re-run it only to reset the demo.
The container applies migrations on every start, so later schema changes need no manual step.

## 3. API (Render)

1. Render dashboard → **New → Blueprint** → pick this repository. It reads `render.yaml`.
2. Enter `EPISIGHT_DATABASE_URL` (the Neon string) when prompted.
3. Wait for the deploy, then open `https://<service>.onrender.com/api/v1/health`.

Free services sleep after ~15 minutes idle; the first request after that takes up to a minute.
Open the health URL a minute before a demo.

## 4. Web (Vercel)

1. Vercel → **Add New → Project** → import this repository.
2. **Root Directory:** `apps/web`. Framework preset: Next.js (pnpm is detected from the lockfile).
3. **Node.js version:** 24 (matches CI).
4. **Environment variable:** `EPISIGHT_API_URL = https://<service>.onrender.com` (no trailing slash).
   Rewrites are fixed at build time: after changing it, **redeploy**.
5. In the app, choose **API lokal** to use the hosted backend, or share `?mode=demo` for the offline demo.

## AI planner and API keys

The blueprint sets `EPISIGHT_LLM_PROVIDER=none`: every step uses the rule fallback and nothing is billed.
The investigate endpoint has no login or rate limit, so a key on a public URL lets anyone spend it.
Before enabling the AI planner:

1. Restrict who can reach the site (Vercel → Settings → Deployment Protection; password protection
   needs a paid plan). Anyone with the Render URL can still call the API directly, so keep it private.
2. Create a **dedicated** key with a low monthly spend limit; revoke it after the event.
3. On Render, set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) and change `EPISIGHT_LLM_PROVIDER` to `auto`.

Never put a key in a `NEXT_PUBLIC_*` variable or in a committed file.

## Test the image locally

```bash
docker compose up -d --wait
docker build -t episight-api apps/api
docker run --rm -p 8000:8000 \
  -e EPISIGHT_DATABASE_URL=postgresql://episight:episight@host.docker.internal:5433/episight \
  episight-api
```
