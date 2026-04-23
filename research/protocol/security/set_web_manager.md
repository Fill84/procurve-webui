# set_web_manager

> ⚠️ **FORBIDDEN** — this operation is documented for protocol-parity only. It
> MUST NOT be invoked (not even with user approval) during Phase 0.
> Adding, replacing, or deleting an Authorized Manager entry can
> immediately lock the tools or the user out of the switch's
> web UI. A stale or misconfigured mask makes management unreachable.
> See `memory/feedback_switch_write_safety.md`.

**Tab:** security
**Kind:** write
**Source in applet:** `GenericList.class` — submits via the JS helpers
`addAddress()`, `modifyAddress()`, `deleteAddress()` in
`research/mirror/2026-04-23/security/web_mgr.html` (live-fetched; not in
the initial snapshot). All three call
`document.addrlist.submitMultipleItems('../cgi/webMgr', <param-string>, …)`.
**Source in HTML:** `web_mgr.html` lines 32-111.

## HTTP contract

- **Method:** GET (GenericList's `submitMultipleItems` builds a GET URL).
- **URL template:** `/cgi/webMgr?{param-string}&{indeces=...}`
  The JS passes the query string before `submitMultipleItems` runs; `GenericList` then appends the selected-row indices as `indeces=<comma-sep>`. (For the Add case, no row selection is required — only the `indeces=` suffix, empty or omitted.)
- **Query params (union across the three JS variants):**

  | name | type | required | description |
  |---|---|---|---|
  | `addr` | dotted-quad IPv4 | yes (add/replace) | New manager IP (`authAdd` input) |
  | `mask` | dotted-quad IPv4 | yes (add/replace) | New manager mask (`mask` input, default `255.255.255.255`) |
  | `lvl` | int | yes (add/replace) | `2` = Manager, `1` = Operator (from the `<select name=acs>` option values) |
  | `action` | int | yes | `1` = add, `2` = modify/replace, `3` = delete |
  | `indeces` | comma-separated ints | yes for modify/delete | 1-based row indices of the entry to mutate; preserve misspelling per `_conventions.md` |

- **Request headers:** standard.
- **Request body:** none (GET).
- **Response headers (relevant):** `unknown — needs live capture under user supervision` (forbidden).
- **Response body:** `unknown — needs live capture under user supervision`. Consistent with other GenericList CGIs, a likely shape is the updated row list (same format as `get_web_managers` read) with the change applied, or a short `OK~` / `error~` sentinel line.
- **Success indicator:** `unknown`. Strong candidate: HTTP 200 with body NOT starting with `error~`.
- **Error indicators:** body starting with `error~`.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| ip | `addr` | querystring | `IPv4Address` | required for add/replace | JS calls `checkForInvalidLength(document.mdfa.authAdd.value)` before submit |
| mask | `mask` | querystring | `IPv4Address` | required for add/replace | default `255.255.255.255` |
| level | `lvl` | querystring | `AccessLevel` | `1`=Operator, `2`=Manager | preserve integer on wire even though the read returns strings |
| action | `action` | querystring | `Action` enum | `1`/`2`/`3` | |
| indeces | `indeces` | querystring comma-sep ints | `list[int]` | required for modify (`action=2`) and delete (`action=3`) | preserve misspelling |

## Example request (prepared — NOT live-tested)

Add an authorized manager at `192.168.178.42/32` with Manager access:
```
GET /cgi/webMgr?addr=192.168.178.42&mask=255.255.255.255&lvl=2&action=1&indeces= HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Replace (modify in place) the entry currently at index 2 with a new IP:
```
GET /cgi/webMgr?addr=192.168.178.7&mask=255.255.255.255&lvl=2&action=2&indeces=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Delete the entry at index 2:
```
GET /cgi/webMgr?action=3&indeces=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Not captured. The FORBIDDEN banner prohibits live invocation in Phase 0.

## Pydantic sketch

```python
from enum import IntEnum
from ipaddress import IPv4Address
from pydantic import BaseModel


class WebMgrAction(IntEnum):
    ADD = 1
    REPLACE = 2
    DELETE = 3


class AccessLevelCode(IntEnum):
    OPERATOR = 1
    MANAGER = 2


class SetWebManagerRequest(BaseModel):
    action: WebMgrAction
    ip: IPv4Address | None = None
    mask: IPv4Address | None = None
    level: AccessLevelCode | None = None
    indeces: list[int] = []  # preserve misspelling on wire


class SetWebManagerResponse(BaseModel):
    applied: bool
    message: str | None = None
```

## Notes & caveats

- **Lockout risk.** The Authorized Manager list acts as a whitelist — once populated, only IPs in the list can reach the web UI. Adding an entry that does not include the client's own IP may not lock us out immediately (the list is usually additive / permissive-by-default until it's non-empty), but semantics vary by firmware. Do NOT test without a verified backup AND a serial-console recovery path.
- **Misspelling preservation.** The parameter is spelled `indeces` on the wire (see `_conventions.md` — same misspelling as the port-config CGI). Python-side field name is `indeces` verbatim even though it's grammatically wrong.
- **Same CGI as read.** `/cgi/webMgr` with no query string is the safe read (`get_web_managers.md`); with `action=...` it mutates. Distinguish purely by caller intent.
- See `memory/feedback_switch_write_safety.md`.
