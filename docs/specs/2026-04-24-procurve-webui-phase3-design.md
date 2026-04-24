# procurve-webui — Phase 3 Design (write-capable tabs)

**Date:** 2026-04-24
**Baseline:** tag `phase2-complete`
**Goal:** Fill in the 4 placeholder tabs from Phase 2 — Configuration, Security, Diagnostics, Support — with READ + WRITE functionality, wired through the existing safety gates.

**User directive (2026-04-24):** "Implement every write action the best you can. I'll test writes myself — don't test live writes." Agent does NOT exercise live-switch write paths; unit/integration tests mock the transport. The existing memory rule `feedback_switch_write_safety.md` continues to apply.

---

## 1. Scope

### In scope

**Configuration tab (~20 procurve_client ops):**
- System info: `get_system_page` / `set_system_info`
- IP config: `get_ip_page` / `set_ip_config` / `set_default_gateway`
- Port config: `get_portscfg` / `get_port_form` / `set_port_config`
- Fault detection: `get_faultdetect_page` / `set_fault_detection`
- Monitor (port mirroring): `get_monitor_page` / `set_monitor`
- Device features (STP/GVRP/IGMP): `get_devfeatures_page` / `set_device_features`
- Bob ports (stacking placeholder): `get_bobports` / `set_bobports`
- QoS: CoS (`get_cos_appt`, `get_cos_userpri`, `get_cos_vlanpri`), DSCP (`get_dscptable`), Diffserv (`get_diffserv`), modes (`set_costos_mode`, `set_cosproto`)
- Support page form: `get_support_page` / `set_support`

**Security tab (~10 procurve_client ops, 1 BLOCKED):**
- Web access: `get_web_access_page` / `set_ssl` (HTTP/HTTPS policy)
- Web managers: `get_web_managers` / `set_web_manager` (authorized IP list)
- Per-port security: `get_perports` / `set_perport`
- Intrusion log: `get_intrusion` / `reset_intrusion_flags`
- SSL state: `get_ssl_state`
- **BLOCKED:** `set_device_passwords` — per memory `feedback_switch_write_safety.md`, never exposed in API or UI. The procurve_client function exists for parity but is unreachable through the web UI.

**Diagnostics tab (4 ops):**
- Ping: `ping`
- Link test: `link_test`
- Configuration report: `get_configuration_report`
- Device reset: `device_reset` — gated behind an extra confirmation step AND `READ_ONLY=false` AND a typed-confirmation match (same pattern as restore).

**Support tab (1 op):**
- `support_redirect` — static info page, no writes.

### Out of scope (Phase 3)

- VLAN management (VLAN ops exist in procurve_client but no Phase 2 placeholder tab to fill; add in Phase 4 if needed).
- Stacking beyond bob-ports (which is inside Configuration).
- Phase 2 follow-ups (real shadcn primitives, dark mode palette, Playwright e2e). Deferred to later polish phase.
- Firmware/image uploads (memory rule: explicit-per-action approval).
- Password changes (memory rule: ABSOLUTE BLOCKED).

---

## 2. Cross-cutting safety pattern

Every write endpoint follows this pattern, centralised in a small helper:

1. **Gate on `settings.read_only`.** If true → HTTP 403 with `{error: "read_only", detail: …}`. Unchanged from Phase 2.
2. **Auto-backup before write.** Trigger `download_config`, save with `trigger="pre-write"`. If backup fails (network error, store error) → HTTP 503, do NOT proceed to the write. The user is guaranteed a rollback point for every successful write.
3. **Execute the write** by delegating to the procurve_client operation.
4. **On exception after step 2:** the pre-write backup is already saved; return the error so the UI can offer "Restore the backup taken just before this change" as a suggested action.
5. **On success:** return the updated state (re-read) OR the operation's response, and invalidate any cached queries for that resource.

**Implementation:** a helper function/decorator on the API layer wraps each write route:

```python
async def write_with_autobackup(
    *,
    settings: Settings,
    store: BackupStore,
    transport: ProcurveTransport,
    write: Callable[[], Awaitable[T]],
) -> T:
    _require_writable(settings)          # raises 403 if read_only
    backup = await download_config(transport)
    store.save(backup, trigger="pre-write")
    return await write()
```

Each write route builds the `write` callable as a closure over the already-validated Pydantic body.

### Device reset (extra layer)

`POST /api/v1/diagnostics/device-reset` requires:
- `settings.read_only = False` (standard).
- Backup fresh (same as above).
- Request body has a `confirm_switch_host: string` field that must equal `settings.switch_host` — the same "type the IP to confirm" UX as restore.

### Devices that can lock out

`set_ip_config`, `set_default_gateway`, `set_web_manager` can sever the user's management access. These go through an additional confirmation dialog in the UI (typed IP confirm), AND the backend accepts a `confirm_switch_host` field that must match the current switch IP before the write is attempted. This does NOT replace the auto-backup — it's additive.

### Passwords

`POST /api/v1/security/device-passwords` is **not implemented** in the backend router. The function in `procurve_client.operations.security.set_device_passwords` exists for API parity but has no HTTP surface. Any future request to add this route must first update memory `feedback_switch_write_safety.md` and be a separate, explicitly-user-approved change.

---

## 3. Architecture

### Backend layer

- New API routers in `backend/app/api/`:
  - `configuration.py` (replaces placeholder) — one FastAPI router with ~15 read/write endpoints. Consider splitting into sub-routers (`configuration/system.py`, `configuration/ports.py`, `configuration/qos.py`, `configuration/features.py`) if the file grows past ~400 lines.
  - `security.py` (replaces placeholder) — ~8 endpoints.
  - `diagnostics.py` (replaces placeholder) — 4 endpoints.
  - `support.py` (replaces placeholder) — 1 endpoint.
- New helper `backend/app/write_safety.py` — houses `write_with_autobackup`, `_require_writable`, `_require_host_confirmation`. Reusable across the 4 routers.
- `main.py`: replace the 4 placeholder imports/routers with the real ones.
- `app/api/placeholders.py` is deleted.

### Frontend layer

- Feature directories:
  - `frontend/src/features/configuration/` with sub-pages for each logical group.
  - `frontend/src/features/security/`
  - `frontend/src/features/diagnostics/`
  - `frontend/src/features/support/`
- Route files updated to point at real pages instead of `ComingLaterPage`.
- Shared UI pattern: `ReadWritePanel<T>` component — takes `useQuery` + `useMutation` + render-props for view/edit forms. Implements the loading skeleton, error banner, edit/cancel/save/confirm flow. Reuse from Backups restore pattern.
- Each write mutation hook invalidates the relevant query and also the `["backups"]` query (pre-write backup becomes visible in the Backups tab).
- `DangerConfirmDialog` component — generic "type this value to confirm" dialog. Used for restore (existing), device reset (new), and management-IP changes (new). Factored out of `RestoreDialog.tsx`.

### Data flow

```
User clicks [Save] → DangerConfirmDialog (if danger-classed route) →
useMutation calls POST /api/v1/<tab>/<resource> →
backend validates body → _require_writable → _require_host_confirmation (if applicable) →
auto-backup → operation call → success response →
React Query invalidates resource queries + ["backups"] →
UI re-renders with fresh data + toast "Saved; pre-write backup taken at HH:MM:SS"
```

### Testing strategy

- **Per-endpoint unit tests (mocked):**
  - Read path: mock procurve_client operation, assert response shape + status.
  - Write path: mock operation, mock `download_config`, assert: (a) 403 when READ_ONLY, (b) backup saved before write, (c) operation called with expected args, (d) 502/422 mapping on failures.
- **No live-switch write tests.** Per user directive and existing memory rule. The live-switch test directory (`backend/tests/live/`) is not extended in Phase 3.
- **Frontend:** no dedicated test harness yet (same as Phase 2). Rely on type safety + `npm run build` + `npx tsc --noEmit`.

---

## 4. Per-tab decomposition

Each tab maps to a chunk of work. Order of implementation:

1. **Cross-cutting infrastructure** (`write_safety.py`, `DangerConfirmDialog`, `ReadWritePanel`). Unit tests for `write_with_autobackup`.
2. **Support tab** (smallest — 1 read endpoint, static info view). Shakes down the router/route/page pattern.
3. **Diagnostics tab** (4 ops, 1 dangerous). Tests the danger-gate pattern end-to-end.
4. **Security tab** (10 ops, one permanently blocked, two lockout-risky). Full write surface exercised.
5. **Configuration tab** (20 ops — the big one). Split into sub-sections: System, IP, Ports, Features, QoS, Monitor, Fault.
6. **Closure** — status doc + tag.

Each tab gets its own batch of implementer + reviewer implementer dispatches (per the implementer-driven-development skill pattern used in Phase 2).

---

## 5. Open questions / risks

- **Port-config form is a lot of fields.** `SetPortConfigRequest` in procurve_client has many knobs. UI should group them (enable/disable, mode, flow-control, trunk membership) rather than a flat form.
- **QoS has multiple tables** (CoS queue, user-pri, vlan-pri, DSCP, diffserv). Each is a separate table; user picks the mode (CoS vs DSCP) via `set_costos_mode`. Need a top-level mode selector that shows/hides relevant sub-tables.
- **`set_ssl`** doubles as HTTP/HTTPS policy AND SSL state. Naming in the procurve_client library may feel awkward; the UI should present it as "Web Access" not "SSL" to match HP's UI.
- **Configuration report** returns a potentially large text blob. UI shows it as `<pre>` with a download button (download as `.txt`).
- **Backup page cross-link.** Every write's toast should include a small "(pre-write backup just saved — see Backups)" link. Closes the feedback loop.
- **API schema regen.** Every new endpoint requires `npm run gen:api` and a `schema.d.ts` commit. Track this per task.

---

## 6. Success criteria

- All 4 tabs render real content (no more `ComingLaterPage`).
- Every write endpoint auto-backs-up first and is 403-gated when `READ_ONLY=true`.
- Dangerous operations (device reset, management-IP change, auth-managers change) require typed host confirmation.
- Password endpoints do NOT exist in the API.
- Backend tests all pass (mocked writes only); coverage stays ≥ 85%.
- `npm run build` + `npx tsc --noEmit` clean.
- Docker image still builds and runs healthy.
- Plan document and per-tab status notes are up to date.

Phase 3 is complete when all of the above hold and user has had a chance to live-test writes in his own environment.
