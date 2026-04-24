# procurve-webui

Modern replacement web UI for the HP ProCurve 2810-24G (J9021A) switch.
Built because the original Java-applet UI no longer runs in modern browsers.

**Target switch:** set `SWITCH_HOST` in `.env` (model J9021A, firmware N.11.78)

## Status

- **Phase 0 — Reverse engineering:** in progress
- Phase 1 — Python `procurve_client` library: pending
- Phase 2 — Docker + read-only UI: later session
- Phase 3+ — Write-capable UI: later sessions

## Documents

- Design spec: [`docs/specs/2026-04-23-procurve-webui-design.md`](docs/specs/2026-04-23-procurve-webui-design.md)
- Phase 0 plan: [`docs/plans/2026-04-23-procurve-webui-phase0.md`](docs/plans/2026-04-23-procurve-webui-phase0.md)
- Phase 1 plan: [`docs/plans/2026-04-23-procurve-webui-phase1.md`](docs/plans/2026-04-23-procurve-webui-phase1.md)

## Research artifacts

See [`research/README.md`](research/README.md).
