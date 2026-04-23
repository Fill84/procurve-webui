# get_web_managers

**Tab:** security
**Kind:** read
**Source in applet:** `GenericList.class` — page-level read driven by `dataURL` param.
**Source in HTML:** `research/mirror/2026-04-23/security/web_mgr.html` (live-fetched 2026-04-23 into `/tmp/web_mgr.html`; not in the initial mirror snapshot). Applet element at L101:

```
<applet code=GenericList.class archive=agent.jar name=addrlist codebase=../classes ...>
    <param name=dataURL value="../cgi/webMgr">
    <param name=titles value="Authorized Manager IP~IP Mask~Access Level">
    <param name=columns value="150~300~400">
    <param name=params  value="ipad~ipma~accs">
    <param name=onlyOneSelection value="1">
</applet>
```

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/webMgr`
- **Query params:** none (plain list read). The same CGI is also used for writes — see `security/set_web_manager.md` (⚠️ FORBIDDEN).
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | (plain text / unset) | typical for this applet-era CGI |

- **Response body:** zero or more tilde-delimited records, one per authorized-manager entry. No `OK~` or `error~` sentinel — the GenericList applet treats an empty body as an empty list and a non-empty body as row data.

  Schema per record (from the applet's `params` mapping) plus an implicit leading index:

  ```
  <index>~<ipad>~<ipma>~<accs>
  ```

  | position | applet field | wire meaning |
  |---|---|---|
  | 1 | (implicit index) | 1-based row number |
  | 2 | `ipad` | Authorized Manager IP (dotted-quad) |
  | 3 | `ipma` | IP mask (dotted-quad) |
  | 4 | `accs` | Access Level — rendered string `Manager` or `Operator` |

- **Success indicator:** HTTP 200; body is either empty or tilde-delimited rows (no `error~` prefix).
- **Error indicators:** body starting with `error~`.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| index | position 1 | int as ASCII | `int` | >=1 | 1-based |
| ip | `ipad` (position 2) | dotted-quad | `IPv4Address` | | |
| mask | `ipma` (position 3) | dotted-quad | `IPv4Address` | | typical default `255.255.255.255` |
| access_level | `accs` (position 4) | string | `AccessLevel` (enum) | `"Manager"` \| `"Operator"` | on the write side the applet sends `lvl=2` (Manager) / `lvl=1` (Operator) — see write doc |

## Example request

```
GET /cgi/webMgr HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/security__get_web_managers.response.txt`
(live-captured 2026-04-23, 84 bytes, SHA256
`5bf3125facf3f69856bf1bcbef74792234874fa11b5a5374b47dccdc6fad2d2f`).

Body:
```
1~192.168.178.22~255.255.255.255~Manager
2~192.168.178.100~255.255.255.255~Manager
```

## Pydantic sketch

```python
from enum import Enum
from ipaddress import IPv4Address
from pydantic import BaseModel


class AccessLevel(str, Enum):
    MANAGER = "Manager"
    OPERATOR = "Operator"


class AuthorizedManager(BaseModel):
    index: int
    ip: IPv4Address
    mask: IPv4Address
    access_level: AccessLevel


class WebManagersResponse(BaseModel):
    entries: list[AuthorizedManager]
```

## Notes & caveats

- The HTML enforces a maximum of 10 entries (`web_mgr.html:103`: `if(document.addrlist.itemCount() >= 10)`); the switch firmware may or may not enforce this server-side.
- When the list contains our own client IP, an accidental `set_web_manager` delete of that row will lock the client out. See `set_web_manager.md` ⚠️ FORBIDDEN banner.
- Related:
  - `set_web_manager.md` (⚠️ FORBIDDEN write — add/modify/delete)
