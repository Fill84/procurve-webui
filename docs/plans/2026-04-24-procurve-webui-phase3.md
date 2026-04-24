# procurve-webui — Phase 3 Implementation Plan

>
> **Prerequisite:** Phase 2 complete (tag `phase2-complete`).
>
> **User directive (2026-04-24):** "Implement every write action the best you can. I'll test writes myself — don't test live writes." Memory rule `feedback_switch_write_safety.md` still applies: agent does NOT invoke live-switch writes, passwords are ABSOLUTE BLOCKED.

**Goal:** Replace the 4 placeholder tabs (Configuration, Security, Diagnostics, Support) with real read + write functionality, using a universal "auto-backup before every write" pattern and hard gates for dangerous operations.

**Convention:** each task declares files to create/modify + test plan + commit message. Code specifics are minimal — implementers should follow existing patterns from `app/api/backups.py`, `app/api/identity.py`, and `frontend/src/features/backups/` for style.

---

## Task 3.1: Cross-cutting — write safety helper + DangerConfirmDialog

**Files to create:**
- `backend/app/write_safety.py`
- `backend/tests/app/test_write_safety.py`
- `frontend/src/components/ui/DangerConfirmDialog.tsx` (extracted from `RestoreDialog.tsx`)

**Files to modify:**
- `frontend/src/features/backups/RestoreDialog.tsx` — refactor to use `DangerConfirmDialog`.

### Backend helper

```python
# backend/app/write_safety.py
"""Universal safety wrapper for write endpoints.

Every write route in Phase 3 goes through `write_with_autobackup` so that:
1. `settings.read_only = True` returns 403 *before* any switch I/O.
2. `download_config` is called first and saved as a `trigger="pre-write"` backup.
3. The write itself runs only after the backup is persisted on disk.
4. On backup failure the write is aborted; the user never loses a rollback point.
"""
```

Exports:
- `async def write_with_autobackup(*, settings, store, transport, write: Callable[[], Awaitable[T]]) -> T`
- `def require_writable(settings: Settings) -> None` — raises `HTTPException(403, {error: "read_only", detail: ...})`.
- `def require_host_confirmation(confirmation: str | None, settings: Settings) -> None` — raises `HTTPException(400, {error: "host_mismatch", detail: ...})` when caller didn't type the current switch IP.

### Tests

Using mocked transport + in-memory `BackupStore` (tmp_path):
- `test_write_blocked_when_read_only_true`
- `test_write_proceeds_when_read_only_false_and_backup_saved`
- `test_backup_stored_before_write_function_called` (ordering check via mock side effects)
- `test_write_aborted_when_backup_fails`
- `test_require_host_confirmation_mismatch_raises_400`
- `test_require_host_confirmation_matches_passes`

### Frontend refactor

Extract the restore dialog's "type switch IP to confirm" pattern into `DangerConfirmDialog`. Props:

```ts
{
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmationValue: string;    // e.g. switch IP the user must type
  confirmationLabel: string;    // "Type the switch IP address to confirm"
  confirmButtonText: string;
  onConfirm: () => Promise<void> | void;
  onCancel: () => void;
  busy?: boolean;
  error?: string | null;
}
```

Rework `RestoreDialog.tsx` to wrap `DangerConfirmDialog`. Snapshot of behaviour preserved (diff still shown, 403 read_only message still shown on failure).

**Verify:** backend pytest + frontend `npm run build` + `npx tsc --noEmit` clean.

**Commit:** `phase3: write safety helper + DangerConfirmDialog`

---

## Task 3.2: Support tab

**Files to create:**
- `backend/app/api/support.py` (replaces placeholder import)
- `backend/tests/app/test_api_support.py`
- `frontend/src/features/support/SupportPage.tsx`
- `frontend/src/api/hooks/useSupport.ts`

**Files to modify:**
- `backend/app/api/placeholders.py` — remove `support_router`.
- `backend/app/main.py` — replace `support_router` import with the new router.
- `frontend/src/routes/_authenticated.support.tsx` — point at `SupportPage`.

### Endpoint

- `GET /api/v1/support` → `SupportInfo` (static text, no switch call in Phase 2 sense — `support_redirect` returns the same data every time; it's what HP's applet uses as a landing page).

### UI

Card layout with HP's canonical support info: link to hp.com/networking/support, phone numbers if the model is licensed in your region, model + serial number (pulled from `useIdentity`), "copy to clipboard" for the model string. Keep it simple.

**Tests:** `test_support_returns_info`, `test_support_requires_auth`.

**Regen schema:** `cd frontend && npm run gen:api` and commit the updated `schema.d.ts`.

**Verify:** pytest, `npm run build`, `npx tsc --noEmit`.

**Commit:** `phase3: Support tab (read-only info)`

---

## Task 3.3: Diagnostics tab

**Files to create:**
- `backend/app/api/diagnostics.py`
- `backend/tests/app/test_api_diagnostics.py`
- `frontend/src/features/diagnostics/DiagnosticsPage.tsx`
- `frontend/src/features/diagnostics/PingCard.tsx`
- `frontend/src/features/diagnostics/LinkTestCard.tsx`
- `frontend/src/features/diagnostics/ConfigReportCard.tsx`
- `frontend/src/features/diagnostics/DeviceResetCard.tsx`
- `frontend/src/api/hooks/useDiagnostics.ts`

**Files to modify:**
- `backend/app/api/placeholders.py` — remove `diagnostics_router`.
- `backend/app/main.py` — replace import.
- `frontend/src/routes/_authenticated.diagnostics.tsx` — point at `DiagnosticsPage`.

### Endpoints

- `POST /api/v1/diagnostics/ping` → run `ping(transport, target_ip, count)`. Body: `{target_ip: string, count: int=3}`.
- `POST /api/v1/diagnostics/link-test` → `link_test(transport, target_ip, count)`.
- `GET /api/v1/diagnostics/configuration-report` → `get_configuration_report(transport)` (large text).
- `POST /api/v1/diagnostics/device-reset` → `device_reset(transport)`. **Dangerous** — goes through `write_with_autobackup` AND `require_host_confirmation(body.confirm_switch_host, settings)` before the call.

All four go through `require_writable(settings)` at the top — ping/link-test mutate switch state (they queue packets) and device-reset is clearly a write.

**Actually:** ping/link-test do not mutate persistent config. The procurve_client `@WRITE` marker is used because these write ICMP/test packets to the wire. Per design: treat them as non-persistent writes — **no auto-backup** needed (nothing to back up), but DO keep `require_writable` so that `READ_ONLY=true` still disables them (matches HP UI behavior where read-only users can't run diagnostics). Add a module-level comment explaining this exception.

Configuration-report is a `@READ` — no gate, no backup.

Device-reset IS persistent (factory defaults) — MUST auto-backup + host-confirmation + `require_writable`.

### UI

Each card is self-contained:
- **PingCard:** input `target_ip`, count dropdown, [Run] button → shows streaming-ish result list.
- **LinkTestCard:** same, but targeted at another switch's MAC/IP.
- **ConfigReportCard:** [Generate] button → fetches the text → shows in a `<pre>` with [Download .txt] and [Copy to clipboard].
- **DeviceResetCard:** the danger zone. Yellow warning banner, [Reset to factory defaults…] button, `DangerConfirmDialog` requiring typed switch IP. Toast "Switch will reboot; management connection will drop." Explain in the dialog that settings.read_only=true blocks this and how to enable.

**Tests (mocked):**
- `test_ping_happy_path`
- `test_ping_blocked_when_read_only`
- `test_link_test_happy_path`
- `test_config_report_returns_text`
- `test_device_reset_blocked_when_read_only`
- `test_device_reset_requires_host_confirmation_match`
- `test_device_reset_creates_pre_write_backup_before_call`

**Regen schema.**

**Verify:** pytest, build, tsc.

**Commit:** `phase3: Diagnostics tab (ping, link test, config report, device reset)`

---

## Task 3.4: Security tab

**Files to create:**
- `backend/app/api/security.py`
- `backend/tests/app/test_api_security.py`
- `frontend/src/features/security/SecurityPage.tsx`
- `frontend/src/features/security/WebAccessCard.tsx`
- `frontend/src/features/security/WebManagersCard.tsx`
- `frontend/src/features/security/PerPortSecurityCard.tsx`
- `frontend/src/features/security/IntrusionLogCard.tsx`
- `frontend/src/features/security/SslStateCard.tsx`
- `frontend/src/api/hooks/useSecurity.ts`

**Files to modify:**
- `backend/app/api/placeholders.py` — remove `security_router`.
- `backend/app/main.py` — replace import.
- `frontend/src/routes/_authenticated.security.tsx` — point at `SecurityPage`.

### Endpoints

Read:
- `GET /api/v1/security/web-access` → `get_web_access_page`
- `GET /api/v1/security/web-managers` → `get_web_managers`
- `GET /api/v1/security/per-port` → `get_perports` (requires slot, e.g. `?slot=0` — confirm shape from the operation)
- `GET /api/v1/security/intrusion` → `get_intrusion`
- `GET /api/v1/security/ssl-state` → `get_ssl_state`

Write (all go through `write_with_autobackup`):
- `PUT /api/v1/security/web-access` (SSL / HTTP policy) → `set_ssl` — **lockout-risky if HTTPS-only enforced without cert loaded**; add UI warning.
- `POST /api/v1/security/web-managers` → `set_web_manager` (adds a manager entry). **Lockout-risky** — require host confirmation.
- `DELETE /api/v1/security/web-managers/{index}` → call `set_web_manager` with the manager removed. Same lockout guard.
- `PUT /api/v1/security/per-port/{port}` → `set_perport`
- `POST /api/v1/security/intrusion/reset` → `reset_intrusion_flags`

NOT implemented:
- `POST /api/v1/security/device-passwords` — DO NOT ADD. Per memory `feedback_switch_write_safety.md`, passwords are ABSOLUTE BLOCKED.

### UI

Vertical stack of cards on `SecurityPage`:
- **WebAccessCard:** toggle HTTP vs HTTPS; [Save] with warning "Enabling HTTPS-only without a valid cert will lock you out."
- **WebManagersCard:** table of authorized IPs/masks; [Add] inline form → host-confirm dialog; [Remove] row → host-confirm dialog.
- **PerPortSecurityCard:** table of ports + learn-mode + action-on-intrusion; edit per row → host-confirm not required (non-lockout).
- **IntrusionLogCard:** list of recent intrusions; [Reset flags] button.
- **SslStateCard:** read-only display of cert state.

**Tests (mocked):**
- Happy-path read for each endpoint.
- Write blocked when `READ_ONLY=true` (one test per write endpoint; parametrize if pytest allows).
- Write host-confirmation mismatch → 400 for each lockout-risky endpoint.
- Pre-write backup saved before each write.
- Intrusion-reset does NOT require host confirm.
- **Negative test: `POST /api/v1/security/device-passwords` returns 404** (route does not exist).

**Regen schema.**

**Verify.**

**Commit:** `phase3: Security tab (web access, web managers, per-port, intrusion, SSL)`

---

## Task 3.5: Configuration tab

Split into **5 sub-commits** for review-ability. All land on the same `configuration` router and page.

**Files to create (all):**
- `backend/app/api/configuration.py` (single file; if it exceeds ~450 lines, split into `backend/app/api/configuration/{__init__.py,system.py,ports.py,qos.py,features.py}`)
- `backend/tests/app/test_api_configuration.py` (or split to match)
- `frontend/src/features/configuration/ConfigurationPage.tsx`
- `frontend/src/features/configuration/SystemInfoCard.tsx`
- `frontend/src/features/configuration/IpConfigCard.tsx`
- `frontend/src/features/configuration/PortConfigTable.tsx`
- `frontend/src/features/configuration/FaultDetectionCard.tsx`
- `frontend/src/features/configuration/MonitorCard.tsx`
- `frontend/src/features/configuration/DeviceFeaturesCard.tsx`
- `frontend/src/features/configuration/qos/*` (CosTableCard, UserPriCard, VlanPriCard, DscpTableCard, DiffservCard, QosModeSelector)
- `frontend/src/features/configuration/BobPortsCard.tsx`
- `frontend/src/features/configuration/SupportPageCard.tsx` (the Support page form, distinct from Phase 3.2's Support tab)
- `frontend/src/api/hooks/useConfiguration.ts`

**Files to modify:**
- `backend/app/api/placeholders.py` — delete the file (last placeholder removed).
- `backend/app/main.py` — replace 4 placeholder imports; delete the old placeholders router registrations.
- `frontend/src/routes/_authenticated.configuration.tsx` — point at `ConfigurationPage`.

### 3.5a: System Info + IP Config

Endpoints:
- `GET /api/v1/configuration/system` → `get_system_page`
- `PUT /api/v1/configuration/system` → `set_system_info` (+ auto-backup)
- `GET /api/v1/configuration/ip` → `get_ip_page`
- `PUT /api/v1/configuration/ip` → `set_ip_config` (+ auto-backup + **host confirm required** — changing management IP is lockout-risky)
- `PUT /api/v1/configuration/gateway` → `set_default_gateway` (+ auto-backup)

UI: two cards. `SystemInfoCard` is simple editable form (name/location/contact). `IpConfigCard` has the Big Scary Switcher — DHCP vs static — with a warning banner and host-confirm.

Tests: read + write happy paths, read-only block, host-confirm for IP change.

**Commit:** `phase3: Configuration — system info + IP config`

### 3.5b: Port config

Endpoints:
- `GET /api/v1/configuration/ports` → `get_portscfg`
- `GET /api/v1/configuration/ports/{port}` → `get_port_form(transport, port)`
- `PUT /api/v1/configuration/ports/{port}` → `set_port_config` (+ auto-backup)

UI: `PortConfigTable` lists all 24 (or 28) ports with inline-edit per row. Reuses the port-detail page's navigation pattern.

**Commit:** `phase3: Configuration — port config`

### 3.5c: Device features + fault detection + monitor

Endpoints:
- `GET /api/v1/configuration/device-features` → `get_devfeatures_page` (STP/GVRP/IGMP flags)
- `PUT /api/v1/configuration/device-features` → `set_device_features`
- `GET /api/v1/configuration/fault-detection` → `get_faultdetect_page`
- `PUT /api/v1/configuration/fault-detection` → `set_fault_detection`
- `GET /api/v1/configuration/monitor` → `get_monitor_page`
- `PUT /api/v1/configuration/monitor` → `set_monitor` (port mirroring config)
- `GET /api/v1/configuration/bob-ports` → `get_bobports` (stacking candidate ports)
- `PUT /api/v1/configuration/bob-ports` → `set_bobports`

UI: cards.

**Commit:** `phase3: Configuration — device features, fault detection, monitor, bob-ports`

### 3.5d: QoS (all sub-tables)

Endpoints:
- `GET /api/v1/configuration/qos/cos` → `get_cos_appt`
- `PUT /api/v1/configuration/qos/cos` → `set_cos_appt`
- `GET /api/v1/configuration/qos/user-pri` → `get_cos_userpri`
- `PUT /api/v1/configuration/qos/user-pri` → `set_cos_userpri`
- `GET /api/v1/configuration/qos/vlan-pri` → `get_cos_vlanpri`
- `PUT /api/v1/configuration/qos/vlan-pri` → `set_cos_vlanpri`
- `PUT /api/v1/configuration/qos/mode` → `set_costos_mode` (CoS vs DSCP master mode)
- `GET /api/v1/configuration/qos/dscp` → `get_dscptable`
- `PUT /api/v1/configuration/qos/dscp` → `set_dscptable`
- `GET /api/v1/configuration/qos/diffserv` → `get_diffserv`
- `PUT /api/v1/configuration/qos/diffserv` → `set_diffserv`
- `PUT /api/v1/configuration/qos/cos-proto` → `set_cosproto`

UI: a master "QoS Mode" selector at the top (CoS vs DSCP), then sub-cards gated on mode. Each sub-card is a table with inline edit.

**Commit:** `phase3: Configuration — QoS (CoS, DSCP, diffserv)`

### 3.5e: Support page form

Endpoints:
- `GET /api/v1/configuration/support-page` → `get_support_page`
- `PUT /api/v1/configuration/support-page` → `set_support`

UI: `SupportPageCard` — fields for support contact / URL as a config item. Note: this is distinct from the Support *tab* (Task 3.2), which is a static info page. This is the editable form the admin can set to influence what the *applet* shows on its Support screen.

**Commit:** `phase3: Configuration — support page form`

---

## Task 3.6: Remove placeholders + regen schema + verify integration

**Files to modify:**
- `backend/app/api/placeholders.py` — delete (all 4 placeholders replaced).
- `backend/app/main.py` — clean up imports.
- `backend/tests/app/test_placeholders.py` — delete or repurpose.
- `frontend/src/features/coming-later/` — keep the component; it's still exported but now unused in production. Don't delete (may be handy for future phases).

**Regen schema:** `cd frontend && npm run gen:api`.

**Verify:**
- `pytest -q --ignore=tests/live` passes.
- `cd frontend && npm run build && npx tsc --noEmit` clean.
- `docker compose build && docker compose up -d` — container starts, `/api/v1/health` responds.
- Each tab loads without console errors.

**Commit:** `phase3: remove placeholders, regen OpenAPI schema`

---

## Task 3.7: Phase 3 closure

**Files to create:**
- `docs/plans/phase3-status.md`

Contents:
- Deliverables checklist (each of 3.1–3.6 ticked).
- Final backend test count + coverage %.
- Frontend bundle sizes.
- Docker image size.
- Safety attestation: "No live-switch writes were performed by the agent. Mocked tests exercise every write route."
- Known follow-ups (VLAN tab? Stacking tab? Password-change UI request? Cert-upload UI?).
- Link to the pre-write backup logs (once user has run some writes).

**Commit:** `phase3: completion status — Phase 3 closed`
**Tag:** `phase3-complete`

---

## Self-review — Phase 3 plan

**Safety coverage:**
- ✅ Password operations NEVER exposed in API.
- ✅ Every write auto-backs-up (`write_with_autobackup`).
- ✅ `READ_ONLY=true` default preserved — writes disabled out of the box.
- ✅ Lockout-risky writes (IP/gateway/web-managers/device-reset) gated by typed host confirmation.
- ✅ No live-switch write tests.
- ✅ Firmware uploads NOT added.

**Scope check:** Phase 3 is large (~40 new endpoints). Broken into 6 cross-cutting + per-tab tasks + 5 sub-tasks under Configuration (3.5a–e). Each sub-task is a single review/commit unit. If time pressure hits mid-Phase-3, the natural cut point is after 3.4 (Security done) — 3.5 (Configuration) can become a Phase 3b.

**Placeholder scan:** no TBDs, but some per-tab detail is deferred to the implementer to figure out based on existing procurve_client model shapes. That's intentional — the plan stays compact by trusting the established code patterns from Phase 2.

**Execution recommendation:** implementer-driven. One implementer + one spec reviewer + one code-quality reviewer per task unit (same as Phase 2). Configuration's 5 sub-tasks each get their own triple.

Expected commit count: roughly 20–25 commits total.
