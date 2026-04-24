# Phase 2 — Completion status

Status date: 2026-04-24
Branch: `phase2`
Baseline: `phase1-complete`
Plan: `docs/plans/2026-04-23-procurve-webui-phase2.md`

## Deliverables

| Task | Scope | Status |
|------|-------|--------|
| 2.1 | FastAPI app scaffold (settings, logging, errors) | ✅ complete |
| 2.2 | Session auth + transport cache | ✅ complete |
| 2.3 | Read-only API routes (identity, status, health, placeholders) | ✅ complete |
| 2.4 | Backups API (list/create/download/diff/restore/delete) | ✅ complete |
| 2.5 | WebSocket `/ws/port-traffic` | ✅ complete |
| 2.6 | Static SPA hosting from FastAPI | ✅ complete |
| 2.7 | Frontend scaffold (Vite, React 19, TS 6, Tailwind v4) | ✅ complete |
| 2.8 | OpenAPI codegen + typed API client | ✅ complete |
| 2.9 | App shell + TanStack Router + login flow | ✅ complete |
| 2.10 | Identity page | ✅ complete |
| 2.11 | Status overview + 28-port SwitchSvg | ✅ complete |
| 2.12 | Port detail + live packet-rate chart (Recharts + WS) | ✅ complete |
| 2.13 | Backups page (list, take, diff, restore, delete) | ✅ complete |
| 2.14 | ComingLater stub page (Configuration / Security / Diagnostics / Support) | ✅ complete |
| 2.15 | Docker multi-stage build + compose | ✅ complete |
| 2.16 | Playwright e2e smoke | ⏭️ deferred (see below) |
| 2.17 | Phase 2 closure | ✅ this doc |

## Verification

### Backend

- **Test count:** 393 passing (up from 324 at Phase 1 close), `tests/live/*` excluded.
- **Coverage:** 93.7% across `procurve_client` + `app` — above the plan's ≥ 85 % target.
- **Strict mypy + ruff:** clean for `app/` and `tests/app/`.
- **Command used:**
  ```bash
  cd backend && source .venv/Scripts/activate
  pytest --cov=procurve_client --cov=app --cov-report=term --cov-report=html:htmlcov -q --ignore=tests/live
  ```
- **Coverage report:** `backend/htmlcov/index.html` (regenerated on every coverage run).

### Frontend

- **`npm run build`:** clean; total bundle ~700 kB raw, main chunk 297 kB / 93 kB gzip, code-split by route.
- **`npx tsc --noEmit`:** clean (TypeScript 6.0 strict).
- **Route tree generation:** `npm run gen:routes` runs automatically as the first step of `npm run build`.

### Docker

- **Image size:** 251 MB (`procurve-webui:latest` built from `docker/Dockerfile`).
- **`docker compose build`:** clean.
- **`docker compose up -d`:** container starts, reaches `(healthy)` within ~25 s.
- Non-root (`appuser`), healthcheck via Python stdlib `urllib.request` (no curl in the image).

## Safety posture

Phase 2 kept the project's write-safety rule intact: **no writes to the live switch without a verified backup first, read-only until backup confirmed**.

- `READ_ONLY=true` is the default in `.env.example` — restore is disabled out of the box.
- `POST /api/v1/backups/{filename}/restore` enforces the gate in the API layer BEFORE any call to `upload_config`. Returns `403 {error: "read_only", detail: …}` when blocked.
- The procurve_client `@WRITE` decorator remains a second line of defence.
- Path-traversal audit done and fixed for the backup store (commit `0ccdf0d`).
- No new live-switch write tests were added. Phase 1 roundtrip test remains opt-in.

## Known follow-ups

1. **Playwright e2e smoke (Task 2.16) deferred.** The plan lists Task 2.16 as "optional but recommended" and states the tests run "against a locally-running backend + dev frontend (no switch required if we add a mock transport layer; or against the live switch via the docker image)." We did NOT build a mock transport layer — it would have been additional scope — and running against the live switch from CI is not stable. Options for Phase 3:
   - Add a `ProcurveTransport` in-memory mock fixture plus a test-only `READ_ONLY` toggle so Playwright can exercise the UI end-to-end without the real switch.
   - Alternatively, run Playwright against the Docker image in a CI job where the switch is reachable and treat it as a pre-merge smoke gate rather than unit-level CI.
2. **shadcn CLI never invoked.** Tasks 2.9–2.14 hand-rolled the visual primitives (Buttons, Cards, Dialog) with Tailwind utility classes matching shadcn's appearance. Running `npx shadcn@latest add <component> --yes` in a future polish pass would swap them for the real library — visuals should stay ~identical.
3. **Tailwind v4 CSS variables.** The palette only has light mode defined in `src/styles/globals.css`; dark mode placeholders are stubbed. Phase 3 UI polish should fill in the real dark palette.
4. **Identity schema gap.** The plan's Identity page listed `system_description` and `system_clock`. The backend model exposes `product` (used as the subtitle) but no wall-clock field. Either extend the `DeviceIdentity` model in Phase 3 or drop the field.
5. **Restore redirect UX.** The auth guard passes a `redirect` query-string back to `/login`, but `LoginScreen` currently always navigates to `/` on success. Wire the round-trip in Phase 3.
6. **Byte-rate counters.** The WS chart only shows packet rates because the switch firmware does not expose byte counters. If a later firmware exposes them the WS frame can be extended without breaking the existing UI.

## Commit range

Phase 2 on `phase2` branch, from `bc243da` (FastAPI scaffold) through `4a13f5f` (Docker) — 21 commits, all prefixed `phase2:`.

## Tag

Tag: `phase2-complete` — placed on the tip of the `phase2` branch after this document is committed.
