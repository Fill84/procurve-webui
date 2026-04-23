# Research artifacts

This directory holds everything needed to understand the ProCurve 2810-24G
protocol without re-examining the switch or applet from scratch. It is the
Phase 0 output.

## Contents

- `applet/agent.jar` — the original Java applet, byte-for-byte.
- `backups/<date>/CONFIG.pcc` — switch config snapshots. The
  `2026-04-23/CONFIG.pcc` file is the user-verified reference baseline
  used for write-testing roll-back during development. **Do not modify.**
- `mirror/<date>/` — full HTTP asset mirror of the switch.
- `tools/` — decompiler binaries (not committed to git — see `.gitignore`).
- `decompiled/` — `.java` files from CFR (not committed; regenerate with
  the decompile task).
- `analysis/` — intermediate cross-reference notes (class groups, URL
  literal extraction, applet parameter maps).
- `protocol/` — one markdown file per applet operation, documenting the
  HTTP contract.
- `fixtures/` — live response samples captured from read-only operations.
  These become unit-test inputs in Phase 1.
