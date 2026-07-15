# procurve-webui frontend

React 19 + TypeScript SPA for the ProCurve 2810-24G web UI. Served in
production by the FastAPI backend from `dist/`; talks to the API same-origin
(`/api/v1/*`, WebSocket at `/ws/port-traffic`).

## Prerequisites

- Node 22 LTS
- The backend (for `gen:api` and for the dev proxy target)

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Vite dev server on :5173, proxying `/api` + `/ws` to :8080 |
| `npm run build` | Route codegen → `tsc -b` → production bundle in `dist/` |
| `npm run lint` | ESLint (zero errors is the CI gate) |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm test` | vitest (jsdom + Testing Library) |
| `npm run gen:api` | Regenerate `openapi.json` + `src/api/schema.d.ts` from the backend |
| `npm run gen:routes` | Regenerate `src/routeTree.gen.ts` (also runs inside `build`) |

## Things that are not obvious

- **`src/api/schema.d.ts` is generated.** After any backend model/API
  change, run `npm run gen:api` (needs the backend venv importable, or a
  backend running on :8080 as fallback) and commit both generated files.
- **`.npmrc` pins `legacy-peer-deps=true`** so openapi-typescript@7
  (peer: typescript@^5) coexists with typescript@~6; `ignore-scripts=true`
  blocks install-time lifecycle scripts (supply-chain hardening — the
  May-2026 TanStack npm compromise executed via a lifecycle script).
- **Switch read-safety shapes this code.** Poll intervals are deliberate,
  interval polling pauses in hidden tabs (React Query default), and the
  live-traffic WebSocket closes on `visibilitychange`. Don't "optimize"
  cadences upward — see CONTRIBUTING.md at the repo root.
- **Visual identity is monochrome** — color is functional only (LEDs,
  alert severities, danger actions).
