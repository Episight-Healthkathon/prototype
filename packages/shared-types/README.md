# @episight/shared-types

Generated API Contract v1 artifacts for the frontend. **Do not edit by hand.**

| Path | What |
|---|---|
| `openapi.json` | OpenAPI document generated from the backend's Pydantic models |
| `src/api.d.ts` | TypeScript types generated from `openapi.json` (`openapi-typescript`) |
| `src/index.ts` | Named aliases, e.g. `import type { CaseSummary, InvestigationView } from "@episight/shared-types"` |
| `fixtures/` | Deterministic mock responses: real screening output for every interim case, plus one scripted Golden-A investigation (running/completed view, evidence, evidence detail, brief). See `fixtures/index.json` |

Regenerate after any contract change:

```bash
cd apps/api && uv run episight export-contract   # openapi.json, src/index.ts, fixtures
cd packages/shared-types && pnpm generate        # src/api.d.ts
```
