# Contributing to procurve-webui

Issues and pull requests are welcome. This project drives **real, fragile
switch hardware** — a careless change can crash or misconfigure someone's
production network gear — so the ground rules below are non-negotiable.

## Safety rules (read these first)

1. **Never increase poll cadence below 1 second, and never let requests to
   the switch stack.** The 2810's management CPU has crashed under
   high-frequency and parallel probing. The transport serializes all switch
   requests process-wide (`procurve_client/transport.py`) and the WebSocket
   fan-out keeps switch load constant regardless of client count
   (`app/ws/port_traffic.py`) — do not weaken either. **Never add retries to
   the transport.**
2. **Every new `@WRITE` operation must ship with:**
   - a protocol doc under `research/protocol/<tab>/`,
   - a byte-match unit test (assert the exact wire encoding — this firmware
     is picky about literal commas, field ordering, and 4-char field names),
   - the full API-layer safety pattern: `READ_ONLY` gate,
     `write_with_autobackup`, and `require_host_confirmation` for anything
     lockout-risky,
   - a docs entry in the README's Feature tour.
3. **No live tests in CI.** Tests marked `live`/`roundtrip` are opt-in
   local-only; CI runs `pytest -m "not live and not roundtrip"`.
4. **Frontend polling must pause when the tab is hidden.** React Query
   interval polls do this by default; anything hand-rolled (WebSockets,
   timers) must handle `visibilitychange` explicitly.

## Workflow

```bash
# Backend — all of these must be clean before a PR:
cd backend
ruff check .
mypy app procurve_client
pytest -m "not live and not roundtrip"

# Frontend:
cd frontend
npm run lint        # zero errors is the gate
npm run typecheck
npm test
npm run build
```

CI (`.github/workflows/ci.yml`) enforces the same set on every push/PR.

- If you change anything in `procurve_client` models or the API surface,
  regenerate the frontend types: `cd frontend && npm run gen:api` (commits
  `openapi.json` + `src/api/schema.d.ts`).
- The mock demo server (`tools/mock_demo/`) is shape-checked against the
  real response models by `backend/tests/app/test_demo_server_drift.py` —
  if you add an endpoint, the demo needs it too or the guard will tell you.
- Dependency changes: regenerate the lockfiles
  (`cd backend && uv lock && uv export --no-dev --no-emit-project
  --format requirements-txt -o requirements.lock`).

For substantive features, please open a discussion or design issue first —
larger changes are easier to land when the design is agreed up front. The
design docs under `docs/specs/` are good models for the level of detail
expected.

## Style

- Python: ruff + mypy `--strict` are the arbiters; match the existing
  docstring style (module docstrings explain the *wire contract*, not the
  code).
- Frontend: monochrome black/white visual identity — color is functional
  only (port LEDs, alert severities, danger buttons). Match the semantic
  tokens (`bg-card`, `text-muted-foreground`, …) used across the app.
