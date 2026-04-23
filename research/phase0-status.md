# Phase 0 completion status

Phase 0 is DONE when every section below has a concrete answer.

## Checklist

- [x] All 50 top-level decompiled applet classes (80 in the JAR before
      anonymous-inner-class inlining) classified in `analysis/class-groups.md`.
- [x] `analysis/callback-layer.md` describes the HTTP plumbing: URL
      construction (getCodeBase / basecgiurl), GET-only convention,
      tilde-delimited response with OK~/error~ sentinels, no applet-side
      auth (browser-session piggyback).
- [x] Every HTML file in `mirror/2026-04-23/` that embeds an applet has
      a section in `analysis/applet-params.md` (13 files).
- [x] `analysis/url-literals.md` enumerates 19 unique /cgi/ endpoints plus
      5 widget-driven URLs.
- [x] Every user-facing operation has a protocol doc under
      `research/protocol/<tab>/` following the template in `_conventions.md`.
- [x] Every read operation has a fixture in `research/fixtures/`.
- [x] `protocol/backup/download_config.md` + `protocol/backup/upload_config.md`
      both complete. Upload-config flags 9 unknowns for live capture.
- [x] Reference backup `research/backups/2026-04-23/CONFIG.pcc` SHA256
      re-verified against live switch — matches, no drift.

## Deliverable counts

- Mirror files (HTML + assets): 82
- Analysis artifacts: class-groups, url-sites, url-literals, url-literals.md,
  applet-params.raw, applet-params.md, callback-layer.md, class-sizes.
- Protocol docs (excluding _conventions.md): 72
- Read-response fixtures: 36
- Reference backup: `CONFIG.pcc` (2904 B, SHA256 f9234…98e11)

## Operations documented, by tab

| Tab | Ops | Fixtures |
|---|---|---|
| identity | 1 | 1 |
| status | 5 | 5 |
| configuration (non-VLAN/non-stacking) | 24 | 8 |
| configuration/vlan | 15 | 7 |
| configuration/stacking | 10 | 6 |
| security | 10 | 6 |
| diagnostics | 4 | 2 |
| support | 1 | 0 |
| backup | 2 | 1 |
| **total** | **72** | **36** |

## Operations flagged as ⚠️ FORBIDDEN (never invoked by me against live switch)

Detected by `grep -lr "FORBIDDEN" research/protocol/` (6 files):

- `research/protocol/diagnostics/device_reset.md`
- `research/protocol/security/get_perports.md`
- `research/protocol/security/get_web_access_page.md`
- `research/protocol/security/get_web_managers.md`
- `research/protocol/security/set_device_passwords.md`
- `research/protocol/security/set_web_manager.md`

Note: `security/set_ssl.md` is treated as write-forbidden in practice (it
rewrites the TLS/SSL config and would sever the management session), but
does not currently carry the `FORBIDDEN` banner string. Phase 1 should
add the banner for consistency before any live experimentation.

## Unknowns / open items for Phase 1+ live capture

Detected by `grep -rln "needs live capture" research/protocol/` — 19 docs
carry at least one unresolved marker. Grouped by tab:

- **backup (1 doc):**
  - `upload_config.md` — 9 markers: `configname` character set/validation,
    `filename` part handling, `reboot=on` semantics, response headers,
    response body shape, success indicator, error indicators, slot/idx
    behaviour, and whether a non-reboot upload actually takes effect on
    running-config vs. stored-config only.
- **configuration non-VLAN/non-stacking (3 docs):**
  - `set_bobports.md` — per-port param shape unverified.
  - `set_cosproto.md` — whole operation TBD; this switch does not expose
    the Protocol-priority table, so the exact param list and response
    shape remain unknown.
  - `set_cos_appt.md` — `dir` parameter purpose, reset semantics, and
    success-response shape unverified.
- **configuration/vlan (6 docs):**
  - `add_vlan.md`, `del_vlan.md`, `get_vlan_port.md`, `set_gvrp_mode.md`,
    `set_gvrp_port.md`, `set_primary.md` — error/response shapes and
    boundary behaviour (invalid VLAN IDs, already-deleted, etc.) are
    unknown because we do not live-test writes.
- **configuration/stacking (2 docs):**
  - `delete_members.md`, `set_members.md` — response shape and failure
    modes unknown; requires a live stacked fabric to capture.
- **security (6 docs):**
  - `reset_intrusion_flags.md` — response headers/body.
  - `set_device_passwords.md` — response headers/body/success/error (FORBIDDEN).
  - `set_perport.md` — secondary-frame param shape (`perport_form2.html` /
    `perport_form4.html`), response headers/body/success indicator, and
    the `SEND_ALARM=2` action-code mapping.
  - `set_ssl.md` — full param list (HTML JS truncation), body-of-submit
    shape, response headers/body.
  - `set_web_manager.md` — response headers/body shape (FORBIDDEN).
  - (Note: `get_perports.md`, `get_web_access_page.md`, `get_web_managers.md`
    are FORBIDDEN but already have concrete fixtures captured under user
    supervision, so they are NOT in the unknowns list.)
- **diagnostics (1 doc):**
  - `device_reset.md` — response headers/body and recovery timing; all
    unknowns marked FORBIDDEN, won't be resolved until a user-supervised
    reboot window.
- **status (1 doc):**
  - `get_port_counters.md` — one widget-driven URL not yet mapped in
    `url-literals.md`; needs further mirror decomposition or live capture.

Total: 19 docs × multiple markers each. All live-capture work is staged
for Phase 1 (writes under user supervision) or, for the 6 FORBIDDEN docs,
requires an explicit user-approved change window with a verified backup
in hand.

## Gate decision

- [x] All checklist boxes are `[x]` above.
- [x] Unknowns are documented, not hidden.
- [x] Live config SHA matches reference (`f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11`).

**All three satisfied: Phase 0 is CLOSED. Proceed to Phase 1.**

**Signed off:** 2026-04-23 reviewed by (Phillippe Pelzer).
