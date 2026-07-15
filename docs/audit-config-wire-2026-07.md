# Configuration subsystem byte-faithfulness audit — findings & fix log

**Date:** 2026-07-14 (audit) / 2026-07-15 (fix batch)
**Scope:** all 29 ops in `backend/procurve_client/operations/configuration.py`, checked
against decompiled applet sources (`research/decompiled/`), the mirrored legacy HTML
(`research/mirror/2026-04-23/configuration/`), fixtures, and the actual bytes
httpx 0.28.1 puts on the wire. Safety wiring (`app/write_safety.py`,
`app/api/configuration.py`, `procurve_client/transport.py`) also reviewed.
**Method:** static analysis only — no requests were sent to the switch.

## Verified byte-faithful (no action needed)

- `set_bobports` — `?ifAdminStatus=1|2&indeces=<csv>` with literal commas matches
  SwitchBob.java:282-293 exactly.
- `set_fault_detection` — `/cgi/web_agent?ffs=` only; sensitivity values 0/32/128/224
  match web_agent.html.
- `set_system_info` / `set_support` / `set_ip_config` / `set_default_gateway` — field
  names, document order, hidden `indeces=0`, `apply= Apply Changes ` all match the
  mirror; httpx's `+`-for-space matches browser form encoding.
- `set_port_config` (single port) — matches `research/fixtures/get_port_form.response.txt`.
- `set_device_features` — all five endpoint paths confirmed in the mirror; 1=On/2=Off.
- Safety architecture — read-only gate → pre-write backup → write on every route;
  `/ip` additionally requires typed host confirmation; `ensure_write_ok` after every
  write; transport serializes one request per host, no retries.

## Findings & resolution status

| # | Severity | Finding | Status (2026-07-15) |
|---|---|---|---|
| F1 | HIGH | `set_monitor` sent `portCopySourceMask` as a decimal LSB-first integer; MonitorList.java:getPortMask is unambiguous: port 1 = MSB of a 32-bit word, rendered as space-separated lowercase hex byte pairs (ports 1+2 → `c0 00 00 00`). | **FIXED** — API now takes `source_ports: list[int]`; `monitor_source_mask()` emits the legacy format; frontend `portMask.ts` deleted; protocol doc corrected; unit tests pin the bytes (`c0+00+00+00` on the wire). Still not live-captured. |
| F2 | MEDIUM | All seven QoS write contracts cite mirror files (`cos_vlan1.html`, `cos_tos.html`, `cos_dscpt.html`, `cos_tosds.html`, `cos_app3.html`, `cos_user1.html`, `cos_proto.html`) that are absent from `research/mirror/` and never were in git history. | **MITIGATED** — all 11 QoS protocol docs now carry a "Ground-truth gap" banner marking the contracts experimental. Real fix needs a re-mirror or live capture of the QoS sub-pages. |
| F3 | MEDIUM | QoS/monitor/device-features write models lacked range validation — out-of-range bytes could reach the switch. | **FIXED** — `SetCosApptRequest` (port 1..65535, dscp 0..63, pr 0..7), `SetCosUserPriRequest`, `SetCosVlanPriRequest`/`SetDscpTableRequest`/`SetDiffservRequest` (domain-or-255 sentinel), `SetMonitorRequest` (ports 1..32), `SetDeviceFeaturesRequest.vlan_id` (1..4094). |
| F4 | MEDIUM | Multi-port `mod_ports` joined `indeces` with a literal comma; ListPane.java:572 URL-encodes it (`%2C`). Docstring wrongly cited the SwitchBob convention. | **FIXED** — `set_port_config` now uses httpx params (emits `%2C`); byte-level test added; `_conventions.md` documents the two different comma conventions. |
| F5 | LOW | `set_device_features` could emit field combinations the legacy pages never produce. | **FIXED** — per-endpoint required/forbidden validation: `feature_set`/`feature2_set` = IGMP+STP, `globalfeature_set` = STP only, `vlan(2)feature_set` = IGMP only. |
| F6 | LOW | `*` encodes as `%2A` (httpx) where Java URLEncoder/browsers leave it literal — free-text fields only; semantically identical to any RFC decoder. | **ACCEPTED** — documented in `_conventions.md`; revisit only if a live byte-match fails. |
| F7 | INFO | `set_cos_appt` param order diverged from doc (`ap` before `src`); `SetCosProtoRequest.apply` was caller-overridable free text; `PortConfigTable.tsx` silently trimmed port names on write. | **FIXED** — param order now `action,app,tcpudp,src,ap,dscp,pr` (byte-tested); `apply` pinned to `Literal["Apply Changes"]`; frontend sends the name verbatim. `get_devfeatures_page` hardcoding `features2.html` fails safe (ParseError) — left as-is. |

## Verification

- Backend: `pytest -m "not live"` → 648 passed, 1 skipped (43 live deselected).
  Ruff + mypy clean.
- Frontend: `tsc -b`, eslint, vitest (18 tests) — all clean; `schema.d.ts`
  regenerated from the updated OpenAPI schema.
- Live suite note: `tests/live/` still shows two pre-existing environmental
  failures (`get_stack_cfg`, `get_vlan_protocol` — the switch drops the
  connection on those CGIs; stacking is disabled on this unit) and the
  roundtrip test stops on a missing local reference file. Unrelated to this
  batch.

## Open follow-ups

1. Live-capture (or re-mirror) the QoS sub-pages to close F2.
2. Live-verify the F1 monitor mask format before first real use of
   monitor-enable (byte-faithful to the decompiled applet, but never
   observed on the wire).
