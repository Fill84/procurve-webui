# procurve-webui — Design Spec

**Date:** 2026-04-23
**Author:** Phillippe Pelzer
**Target hardware:** HP ProCurve Switch 2810-24G (J9021A), firmware N.11.78, at `192.168.178.3`
**Status:** Approved for Phase 0 + Phase 1 implementation.

---

## 1. Problem statement

The HP ProCurve 2810-24G ships with a Java-applet-based web UI (`agent.jar`) that no longer runs in any modern browser. The switch is fully functional, but its UI is effectively dead. Goal: build a modern replacement UI that communicates with the switch over the same HTTP protocol the applet uses, so the user never has to touch the original UI (or install legacy Java) again.

Full feature parity with the original applet is the target (Identity, Status, Configuration, Security, Diagnostics, Support tabs).

---

## 2. High-level architecture

One Docker container, three logical layers inside:

```
┌─────────────────────────────────────────────────────────────┐
│ Docker container: procurve-webui                            │
│                                                             │
│  ┌────────────────────┐       ┌─────────────────────────┐   │
│  │ React SPA          │  ←→   │ FastAPI app             │   │
│  │ (pre-built,        │ HTTP  │ ┌─────────────────────┐ │   │
│  │  static served     │ /ws   │ │ REST + WS endpoints │ │   │
│  │  by FastAPI)       │       │ └──────────┬──────────┘ │   │
│  └────────────────────┘       │            │            │   │
│                               │ ┌──────────▼──────────┐ │   │
│                               │ │ procurve_client     │ │   │
│                               │ │ (typed Python,      │ │   │
│                               │ │  talks to switch)   │ │   │
│                               │ └──────────┬──────────┘ │   │
│                               └────────────┼────────────┘   │
└────────────────────────────────────────────┼────────────────┘
                                             │ HTTP
                                             ▼
                                  ┌──────────────────────┐
                                  │ ProCurve 2810-24G    │
                                  │ 192.168.178.3        │
                                  │ (eHTTP v2.0 server)  │
                                  └──────────────────────┘
```

### Characteristics

- **Single container, single process.** Uvicorn runs FastAPI; FastAPI also serves the static React build from `/dist`. No separate nginx, no separate Node server.
- **Configuration via `.env`:** `SWITCH_HOST`, optional `SWITCH_PORT`, `POLL_INTERVAL_SECONDS`, `READ_ONLY`, `HOST` (bind address), `METRICS_ENABLED`, `SESSION_SECRET` (random key for signing session cookies). **Switch credentials are NOT in `.env`** — they are entered by the user at the UI login and live only in browser session + backend RAM.
- **No database.** Source of truth is the switch itself. Polling cache is in-memory. Backups are plain files in a mounted volume (`/app/backups`).
- **Modules inside FastAPI** split per tab: `api/status.py`, `api/identity.py`, `api/configuration.py`, `api/security.py`, `api/diagnostics.py`, `api/support.py`, `api/backup.py`.
- **`procurve_client`** is a standalone Python package, fully typed with Pydantic v2 models, async where meaningful. Re-usable as a library.
- **WebSocket** only for live port counters/gauges; all other data via REST.

### Repository layout

```
procurve-webui/
├── backend/
│   ├── app/                  # FastAPI app + routes
│   ├── procurve_client/      # Protocol client library
│   └── tests/
├── frontend/                 # React + Vite + TS + Tailwind
├── research/                 # Phase 0 artifacts (decomp, protocol docs, fixtures, backups)
├── docker/                   # Dockerfile, entrypoint.sh
├── docs/                     # specs, plans, protocol reference
└── docker-compose.yml        # dev convenience
```

---

## 3. Tech stack (decided)

| Layer | Choice | Notes |
|---|---|---|
| Backend language | Python 3.12 | |
| Backend framework | FastAPI | OpenAPI auto-generated |
| HTTP client | httpx (async) | |
| Models / validation | Pydantic v2 | |
| Test framework | pytest | |
| Logging | structlog | JSON structured |
| Metrics (optional) | prometheus-client | opt-in via `METRICS_ENABLED` |
| Session signing | itsdangerous | for signed session cookies |
| Frontend language | TypeScript | |
| Frontend framework | React 18+ | |
| Build | Vite | |
| Styling | TailwindCSS + shadcn/ui | |
| Data fetching | TanStack Query | |
| Routing | TanStack Router | type-safe |
| Charts | Recharts | |
| Client-side validation | Zod | generated from OpenAPI |
| Deployment | Docker (single container) | |
| Java decompiler | CFR | for Phase 0 |

---

## 4. Phased delivery (Option B — vertical slices)

Each phase is its own spec + plan + implementation cycle. This spec only covers Phase 0 and Phase 1 in detail. Later phases get their own specs when the time comes.

| Phase | Contents | Session |
|---|---|---|
| **0** | Reverse-engineering; protocol docs; read-only fixtures; backup feasibility (already done, see §7) | **This session** |
| **1** | Python `procurve_client` library — typed, tested, all operations (read + write) | **This session** |
| 2 | Docker scaffold + read-only UI (Identity + Status tabs, live port gauges) | Later |
| 3+ | Configurable tabs one at a time (Configuration → Security → Diagnostics → Support) with write ops + safety UX | Later |

---

## 5. Phase 0 — Reverse engineering

### 5.1 Asset mirror

Mirror all GET-accessible assets of the switch to `research/mirror/<date>/`:

- All `.html` pages under `/`, `/status/`, `/identity/`, `/configuration/`, `/security/`, `/diagnostics/`, `/support/`
- `agent.jar` (already downloaded — 183 KB, 80 class files) + any other JARs under `/classes/`
- All referenced images, GIFs, CSS files

Rationale: HTML pages carry `<param>` tags on `<applet>` elements that act as a directory of which operation lives at which URL.

### 5.2 JAR decompilation

Decompile `agent.jar` using **CFR** (best readability for pre-Java-5 bytecode, preserves original string literals where URLs live). Fallback: `jd-cli` or `procyon`.

Output: 80 `.java` files at `research/decompiled/`. Classes will be cross-referenced manually (for the important ones: `PageSelector`, `CallbackClient`, `ResultProcessor`, `DeviceStatus`, `VLANmain`, `StackConfig`, etc.) and scanned with `grep` for URL patterns (`URL`, `openConnection`, `getInputStream`, `?` query delimiters, etc.).

### 5.3 Protocol documentation

For each identified operation, document in `research/protocol/<operation>.md`:

- URL (base + path + querystring template)
- HTTP method
- Headers (Content-Type, Cookie, session markers)
- Request body (format, fields, types, encoding)
- Response format (sketch or regex)
- Error conditions (HTTP status, magic strings in body)
- Authentication behavior (currently blank user/password; later Basic Auth support needed)

Each doc pairs getters and setters side-by-side where applicable.

### 5.4 Live verification (reads only)

For every read operation we believe we understand: issue a live GET/POST and compare the response to our parser's expectations. Save responses as fixtures at `research/fixtures/<operation>.response.txt`. These become the unit-test inputs for Phase 1.

For write operations: **no live issue.** Instead:

- Full bytecode-level analysis of the setter in decompiled Java
- All edge cases / validation rules extracted from Java code, written into the protocol md
- "Prepared example request" alongside the Java source in the protocol md, ready for human verification before ever firing
- A Python unit test that byte-for-byte compares the generated request against a known-good template inferred from decompilation

### 5.5 Backup feasibility (already verified)

Done during brainstorm on 2026-04-23:

- **Endpoint:** `GET /cgi/configfile?idx=1&fg=1&D1=Download`
- **Response:** `Content-Type: application/octet-stream; file="CONFIG.pcc"`, ASCII text with CRLF line terminators, 2904 bytes for the current config
- **Format:** standard ProCurve `show running-config` text (hostname, interfaces, VLANs, fault-finder, etc.)
- **Restore mechanism:** `configuration/configfileSingle.html` has an Upload form; the exact HTTP contract is still to be reverse-engineered in Phase 0
- **Reference backup saved:** `research/backups/2026-04-23/CONFIG.pcc`, SHA256 `f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11` — user-verified as a full valid backup

### 5.6 Phase 0 deliverables

- `research/mirror/<date>/` — all static switch assets
- `research/applet/agent.jar` (already present)
- `research/decompiled/` — 80 Java files
- `research/protocol/*.md` — one doc per operation, including both getters and setters
- `research/fixtures/*.response.txt` — live read response samples
- `research/backup-feasibility.md` — mechanism documentation (download + upload/restore contract)

**Gate into Phase 1:** protocol docs are complete enough that Phase 1 code can be written without re-reading Java.

---

## 6. Phase 1 — Python protocol client library

### 6.1 Package layout

```
backend/procurve_client/
├── __init__.py          # public API re-exports
├── transport.py         # HTTP transport (httpx wrapper), host/auth/session
├── auth.py              # None / Basic auth strategies
├── parsing.py           # response parsers (pipe-delim, custom, etc.)
├── errors.py            # typed exception hierarchy
├── models/              # Pydantic models per domain
│   ├── device.py        # DeviceInfo, SystemInfo
│   ├── port.py          # PortStatus, PortConfig, PortCounters
│   ├── vlan.py          # Vlan, VlanMembership
│   ├── stp.py           # SpanningTreeConfig
│   ├── security.py      # UserConfig, AccessRules
│   ├── log.py           # LogEntry
│   └── backup.py        # ConfigBackup
└── operations/          # one function per applet operation
    ├── identity.py
    ├── status.py
    ├── configuration.py
    ├── security.py
    ├── diagnostics.py
    └── support.py
```

### 6.2 Design principles

- **Flat function API.** Each operation is an async function, not a method on a god-object:
  ```python
  async def get_port_status(t: ProcurveTransport, port: int) -> PortStatus: ...
  async def set_port_config(t: ProcurveTransport, port: int, cfg: PortConfig) -> None: ...
  ```
- **One transport, many operations.** `ProcurveTransport` is the only stateful class: host, per-instance credentials (username + password), session cookies, httpx client. Operations are pure functions that take it as first arg. The FastAPI layer creates a transport per authenticated user-session, using the credentials that user logged in with; transports are cached in a session-indexed dict and torn down on logout / session expiry.
- **Pydantic v2 models for everything.** Both request and response; validators fail loudly if the switch returns something unexpected.
- **Strict mode for setters.** Setters accept only fully validated models. Validation rules come from decompiled Java code (e.g. "VLAN ID 1-4094", "port name max 32 chars").

### 6.3 Read vs. write separation in code

```python
from .._safety import READ, WRITE

@READ
async def get_vlans(t: ProcurveTransport) -> list[Vlan]: ...

@WRITE
async def set_port_config(t: ProcurveTransport, port: int, cfg: PortConfig) -> None: ...
```

The decorators:

- Are runtime no-ops for behavior (code runs normally when the API layer calls it).
- Mark metadata that FastAPI uses to label write-endpoints in OpenAPI.
- Enable a **`READ_ONLY=true`** env flag: all `@WRITE` functions raise `WriteDisabledError` without touching the switch.

**Default in the Docker image: `READ_ONLY=true`.** The user must explicitly flip it to `false` in `.env` before write-endpoints will do anything. This is an extra safety net on top of all UI confirmations.

### 6.4 Testing strategy for Phase 1

- **Unit tests:** parsers, models, URL builders. No network. Input = fixture files from `research/fixtures/`.
- **Integration tests:** only read-operations against the live switch, marked `@pytest.mark.live`, not run by default.
- **Byte-for-byte request tests for writes:** build the write request, serialize it, compare byte sequence against a template derived from decompilation. No network traffic, but strong check that the request is well-formed.
- **Coverage target:** >90% for `procurve_client/`.

### 6.5 In- vs. out-of-scope for Phase 1

**In scope:**

- Transport, auth, parsers, errors
- All operations for Identity + Status + Configuration + Security + Diagnostics + Support (both read and write)
- Pydantic models for all entities
- `get_config_backup()` read operation (wraps `GET /cgi/configfile?…`)
- `restore_config_backup()` write operation (wraps the Upload endpoint once reverse-engineered)

**Out of scope for Phase 1:**

- FastAPI routes (Phase 2+)
- Frontend (Phase 2+)
- Docker scaffold (Phase 2)
- Backup management API endpoints / scheduling (Phase 2)

---

## 7. Safety rules (development-time)

**Reference backup:** `research/backups/2026-04-23/CONFIG.pcc`, SHA256 `f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11`. User-verified as complete and valid.

**Writes allowed but strictly rolled back.** Write-calls against the live switch during development are subject to the following invariant: after any write-test, the switch must be returned to the exact configuration captured in the reference backup.

**Workflow for every write-test:**

1. **Verify pre-state matches baseline.** `GET /cgi/configfile?idx=1&fg=1&D1=Download`; compare to `CONFIG.pcc`. If not identical → STOP. Notify the user; drift is treated as a bug (user won't touch the switch during dev).
2. **Execute write-call** under test.
3. **Verify the write worked.** Re-download; diff against baseline. Expected delta = the change under test.
4. **Restore by uploading `CONFIG.pcc`** (via the reverse-engineered Upload endpoint).
5. **Verify the restore succeeded.** Re-download; diff against baseline. Expected delta = empty.
6. **If post-restore config ≠ baseline:** STOP. Notify the user with the diff.

**Backup handling:** the reference backup is read-only during development. Never create a new backup, never overwrite, never move/rename. Only the user decides when a new baseline is taken.

**Still blocked without explicit per-action user approval (even with a valid backup):**

- Firmware/image uploads
- Factory reset / erase-config
- Reboot/reload if it risks long offline time
- Any write that could change the management IP or authorized-managers list (self-lockout risk)
- Any write-test before the Upload/restore mechanism has been reverse-engineered AND one trivial round-trip (write → restore → diff-empty) has been demonstrated

**Destructive-action guardrail (end-user UI, Phase 3+):** operations are tagged in the backend with a `safety` level (`normal` | `careful` | `dangerous`). `dangerous` is explicitly out-of-scope for Phase 3 — those need a separate spec.

---

## 8. End-user write-UI pattern (Phase 3+)

Every write-capable tab uses the same pattern.

### 8.1 Write-session lifecycle

1. Banner at top of any write-tab shows last backup info + `[Take fresh backup]` / `[View current config]`.
2. User modifies a form → `[Apply]` becomes active → preview of changes.
3. Click `[Apply]` → modal with syntax-highlighted diff, checklist (backup is < 15 min old, explicit "I understand" checkbox), `[Take fresh backup]` / `[Cancel]` / `[Apply write]`.
4. After apply → backend post-write verify-fetch → result panel with success indicator, new diff (baseline → live) for transparency, `[Rollback to last backup]` / `[Take new baseline backup]`.

### 8.2 Backups section in the UI (visible from Phase 2)

Separate "Backups" tab in navigation:

- Table of all backups on the mounted volume: timestamp, label, size, SHA256, trigger (manual / pre-write / scheduled)
- Actions per row: `[View diff vs live]` `[Download .pcc]` `[Restore…]` `[Delete]`
- Always-prominent `[Take backup now]`
- Auto-backup settings:
  - Before every write-session (forced, not disableable)
  - Optional scheduled (daily / weekly), configurable in UI → persisted to config file on volume
- Restore flow: double confirmation + "type the switch IP to confirm" + backend warns about potential lockout (changes to management IP / authorized-managers) + post-restore auto-verify

**Note:** this user-facing backup management is separate from the dev-time safety rule. End users can freely create, delete, and use multiple backups; the dev-time rule (one reference backup, never overwritten) applies only during development.

### 8.3 Safety levels on write endpoints

Each `@WRITE` is tagged with `safety=`:

- **`normal`** — port name / VLAN name / etc. Standard confirm + backup-check.
- **`careful`** — VLAN membership, STP, QoS. Additional "type the setting name to confirm" input.
- **`dangerous`** — authorized-managers, management IP, factory-reset, reboot, firmware upload. **Out of scope for Phase 3.** Requires a separate spec and UX.

### 8.4 Observability (write audit)

Every write event is logged to a rolling JSONL file + visible in an "Activity" panel in the UI:

```json
{
  "timestamp": "2026-04-23T15:12:47Z",
  "user": "local",
  "operation": "set_port_name",
  "target": "port 18",
  "before": "UPS",
  "after": "UPS-APC",
  "backup_hash_pre": "f9234e4f9e...",
  "backup_hash_post_write": "a1b2c3...",
  "status": "ok"
}
```

Retention: 52 weeks, weekly rotation.

---

## 9. Frontend architecture (Phase 2+)

### 9.1 What the end user sees in Phase 2

**Login screen** on first visit: username + password fields matching what the switch expects. Submit → backend validates against live switch → session cookie issued. Blank credentials work as long as the switch has blank auth (current state).

After login: Identity + Status tabs fully working, read-only. Configuration / Security / Diagnostics / Support visible in nav but stubbed with "coming in a later phase" placeholders. A Backups tab is also already present (read-only management of backups). Logout button in the header drops the session.

**Identity tab:** switch name / system description / serial / MAC / firmware version, uptime, system clock, contact / location.

**Status tab:** stylized switch render (24 ports), per-port live speed/duplex/name/VLAN membership, live traffic gauges via WebSocket (1-2s interval), alert/event indicator, overview dashboard with totals.

### 9.2 Switch rendering

The applet uses a `SwStrongbadBob` class to render the 2810-24G. We replace it with a hand-authored SVG:

- 24 copper ports in 2 rows × 12 (matching hardware layout)
- 4 mini-GBIC (SFP) slots on the right (J9021A has 4 combo ports)
- LEDs per port: link (green up / off down / amber error), activity blink
- Hover → tooltip with quick info; click → navigate to port-detail
- Responsive: stacks to 1 row on mobile

### 9.3 Backend ↔ frontend contract

- **OpenAPI as single source of truth.** FastAPI generates `/openapi.json`; frontend build runs `openapi-typescript` to generate TS types + a fetch client. No hand-written TS types for API.
- **WebSocket** endpoint `/ws/port-traffic` emits a JSON blob per second with per-port bytes/packets in/out. Frontend subscribes only while the Status tab is open.
- **API prefix:** `/api/v1/...`. Static React assets at `/` with client-side routing fallback.

### 9.4 Folder layout (frontend)

```
frontend/src/
├── main.tsx
├── App.tsx
├── api/                    # generated client + hooks
│   ├── client.ts
│   └── hooks/
├── components/
│   ├── ui/                 # shadcn primitives
│   ├── switch-panel/       # visual switch SVG
│   ├── port-gauge/         # live traffic gauges
│   └── ...
├── features/
│   ├── identity/
│   ├── status/
│   └── ...
├── lib/
└── styles/
```

---

## 10. Docker packaging (Phase 2)

### 10.1 Image build

Multi-stage:

```dockerfile
FROM node:22-alpine AS frontend-build
# npm ci + vite build → /app/frontend/dist

FROM python:3.12-slim AS backend
# pip install; COPY frontend/dist; run uvicorn
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Target: final image < 200 MB, non-root user, healthcheck against `/api/v1/health` which does a `GET /home.html` on the switch and checks HTTP 200. `.env` is mounted or passed via `-e`, never baked into the image.

### 10.2 docker-compose.yml (dev convenience)

```yaml
services:
  procurve-webui:
    build: .
    ports: ["8080:8080"]
    env_file: .env
    volumes:
      - ./backups:/app/backups
```

---

## 11. Cross-cutting concerns

### 11.1 Error hierarchy

```
ProcurveError
├── TransportError            # network, timeout, DNS
├── AuthError                 # 401/403 or auth-redirect
├── ProtocolError             # unexpected response format
│   ├── ParseError
│   └── SchemaError
├── OperationError            # switch rejected the operation
└── WriteDisabledError        # @WRITE called while READ_ONLY=true
```

HTTP mapping in FastAPI:

- `TransportError` → 502
- `AuthError` → 401
- `ProtocolError` → 500 with `{"error": "protocol", "detail": "..."}`
- `OperationError` → 422
- `WriteDisabledError` → 403

No stack traces in production responses; full traces in logs.

### 11.2 Logging + metrics

- Structured JSON logs via `structlog`. Entries carry `request_id`, `operation`, `switch_host`, `duration_ms`, status.
- Optional Prometheus metrics endpoint `/metrics`, opt-in via `METRICS_ENABLED`. Counters per operation, latency histograms, open WebSocket connections.
- Write audit log (separate JSONL file) roll-weekly, 52-week retention, visible in UI as "Activity".

### 11.3 Security of the webui itself

**Auth model: the switch is the identity provider.** No separate user database, no passwords on disk.

- **Login form in UI** asks for the same username + password the switch expects. On submit, the backend validates by issuing a known-good call against the switch with those credentials. On success, backend generates a signed session cookie (HttpOnly, Secure-when-HTTPS, SameSite=Strict) and holds the credentials in memory, keyed by session ID.
- **Session lifetime:** 8 hours idle timeout, configurable via `SESSION_TTL_HOURS`. Logout clears the server-side entry and invalidates the cookie.
- **All `/api/v1/*` endpoints require a valid session.** Unauthenticated requests get 401. The login endpoint `/api/v1/auth/login` is the only exception.
- **Credentials are never persisted** — not in `.env`, not in the database (there is no database), not in logs. They live only in browser-session + backend RAM. Restarting the container requires re-login.
- **Current switch state: blank user + blank password.** Submitting an empty form is accepted because the switch accepts anything. When the user later sets real switch credentials, the UI automatically starts requiring them — no code change needed.
- **Bind default on `127.0.0.1:8080`.** Remote access requires explicit `HOST=0.0.0.0`, documented with warning (switch creds would then travel the LAN in plaintext until HTTPS v2 ships).
- **CSRF token for write endpoints** on top of session auth: double-submit cookie pattern, same-origin.
- **Strict CORS:** same-origin only.
- **Secrets masked in logs** (`***` wherever password would appear, including tracebacks).
- **`SESSION_SECRET`** in `.env` — random key for signing session cookies. Required; user sets a random value at setup. A `.env.example` ships with a clearly-fake placeholder and instructions to generate one (`python -c "import secrets; print(secrets.token_urlsafe(32))"`). If missing at runtime, the container fails fast with a clear error — it does not self-generate to avoid silent weakening of security.
- **v2 (out of scope now):** HTTPS via Caddy sidecar or self-signed cert; optional "remember me" long-lived token; optional SSO if multi-user becomes a thing.

### 11.4 Testing strategy (cross-cutting)

- `procurve_client` (Phase 1): unit-tests + fixtures; integration read-only tests; byte-match write tests. Coverage >90%.
- `app` FastAPI (Phase 2+): route handler unit-tests with mocked client; contract-tests vs OpenAPI schema.
- `frontend` (Phase 2+): component tests via Vitest + Testing Library; Playwright E2E on a dev mock, never against the live switch.
- CI: GitHub Actions or local `make test`. No live-switch tests in CI ever.

---

## 12. Scope of this session

This session delivers:

1. This design document (committed to `docs/superpowers/specs/`).
2. Implementation plan for Phase 0 + Phase 1 (produced by writing-plans skill after this doc).
3. **Phase 0 implementation:** asset mirror, JAR decompilation, protocol docs, read-operation fixtures, Upload/restore mechanism documented.
4. **Phase 1 implementation:** Python `procurve_client` library — all read and write operations, with unit tests, byte-match write tests, live-integration read tests, and a demonstration round-trip (write → verify → restore → verify-empty) on one trivial change (e.g. port 18 name).

Phase 2 (Docker + UI) and Phase 3+ (config tabs with writes) are **out of scope** for this session; they get their own spec/plan cycles later.

### Definition of done for this session

- This design doc committed in a git-initialized repo.
- Directory structure present as in §2.
- `procurve_client` library operational with all documented operations (reads live-validated, writes byte-match tested, one full round-trip demonstrated under explicit go-ahead from the user).
- README with a quick overview (what's here, how to use it) for future sessions / collaborators.
- All protocol docs complete or explicitly marked `unknown / needs investigation` with rationale.

---

## 13. Open questions deferred to later specs

These are deliberately *not* decided here; they belong in Phase 2/3 specs:

- Exact choice of Backups retention defaults (e.g. keep last 50 manual + last 30 auto)
- Whether scheduled auto-backup is default on or off
- Multi-switch / multi-container UX
- UI-auth enhancements beyond v1 (remember-me token, SSO, multi-user) — v1 auth is decided: switch creds as defined in §11.3
- HTTPS / cert strategy (v2)
