# get_perports

**Tab:** security
**Kind:** read
**Source in applet:** `GenericList.class` — `dataURL=../cgi/perports?GR=`.
**Source in HTML:** `research/mirror/2026-04-23/security/perports1.html` (live-fetched 2026-04-23; not in the initial snapshot). Applet at L30:

```
<applet code=GenericList.class ... name=list ...>
    <param name=dataURL value="../cgi/perports?GR=">
    <param name=formURL value="../security/perport_formf.html?GR=">
    <param name=titles value="%Port~Port Name~Address%Selection~Authorized%Address~Violation%Action">
    <param name=columns value="70~160:x~250~380~590~1:h~1:h~1:h~1:h">
    <param name=params  value="pt~.~.~.~.~mode~sa~adl~tr">
    <param name=delay   value=15>
</applet>
```

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/perports?GR={group}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | `GR` | string | yes (may be empty) | Stack group / port-group filter. In the unstacked 2810 case the applet sends it as an empty string (`GR=`). |

- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | (plain text / unset) | applet-era CGI |

- **Response body:** zero or more tilde-delimited records, one per port. No `OK~`/`error~` sentinel. Columns correspond to the applet's `params` list (`pt~.~.~.~.~mode~sa~adl~tr`), with the `.` columns filled in by the CGI at the positions where the UI wants plain-text pass-through fields.

  Per-port schema, derived from the captured fixture (`7~7~ ~Continuous~ ~None~1~1~1~0`):

  | position | field (from `params`) | wire meaning |
  |---|---|---|
  | 1 | `pt` | port number |
  | 2 | (pass-through) | port label / display name (often same as `pt`) |
  | 3 | (pass-through) | Port Name (free-text; blank = single space ` `) |
  | 4 | (pass-through) | Address Selection (display text, e.g. `Continuous`, `Static`, `Port Access`, `Limited`) |
  | 5 | (pass-through) | Authorized Address (MAC or blank space) |
  | 6 | `mode` | mode code (see perport form) — `None`, integer, etc. The captured fixture shows the rendered token `None` here; on other rows it may be an integer mode code |
  | 7 | `sa` | security-action code (integer — `1`=None per `perport_form1.html:67`) |
  | 8 | `adl` | authorized-device-limit code (integer) |
  | 9 | `tr` | trunk flag (`0` = not in a trunk, `1` = trunked — see `perport_form1.html:108` `if( == 1){ alert("Trunk and meshed ports cannot have security features configured.")`) |

  Only ports present in the list appear in the response. On the captured 24-port switch, 10 ports are missing (1-6, 9-10, 15-16) — those ports are trunked/meshed or otherwise hidden from the per-port-security view.

- **Success indicator:** HTTP 200; non-empty body is a tilde-delimited list; empty body means no eligible ports.
- **Error indicators:** body starting with `error~`.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| port | `pt` | int as ASCII | `int` | 1-based port index |
| port_label | position 2 | string | `str` | usually equals `pt` stringified |
| port_name | position 3 | string | `str` | free-text label; blank is ` ` (single space) in the wire |
| address_selection | position 4 | string | `AddressSelection` enum | `Continuous`/`Static`/`Port Access`/`Limited` |
| authorized_address | position 5 | string | `str` | MAC in XX-XX-XX-XX-XX-XX form, or blank ` ` |
| mode | `mode` | string | `str` (`None` \| int) | display token for the mode column |
| security_action | `sa` | int | `int` | 1=None, other codes = configured trap/drop actions |
| address_limit | `adl` | int | `int` | numeric cap for Limited mode |
| trunk | `tr` | int (0/1) | `bool` | `1` means the port is trunked → security cannot be configured |

## Example request

```
GET /cgi/perports?GR= HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/security__get_perports.response.txt`
(live-captured 2026-04-23, 475 bytes, SHA256
`2b3d1ae1673afdb91315d4a28396a52eed5d4f4510a481d92aadb46f62f0d075`).

Excerpt (first 4 rows):
```
7~7~ ~Continuous~ ~None~1~1~1~0
8~8~ ~Continuous~ ~None~1~1~1~0
11~11~ ~Continuous~ ~None~1~1~1~0
12~12~ ~Continuous~ ~None~1~1~1~0
```

## Pydantic sketch

```python
from enum import Enum
from pydantic import BaseModel


class AddressSelection(str, Enum):
    CONTINUOUS = "Continuous"
    STATIC = "Static"
    PORT_ACCESS = "Port Access"
    LIMITED = "Limited"


class PortSecurityRow(BaseModel):
    port: int
    port_label: str
    port_name: str
    address_selection: AddressSelection
    authorized_address: str
    mode: str
    security_action: int
    address_limit: int
    trunk: bool


class PerportsResponse(BaseModel):
    rows: list[PortSecurityRow]
```

## Notes & caveats

- The GR=<group> parameter is always empty on a standalone 2810. On a stacked configuration it would carry the stack member index; we preserve the empty key (`GR=`) verbatim on the wire.
- Blank-string columns are serialized as a literal single space, not the empty string. Do not trim — the applet relies on the space to keep column positions aligned in its renderer.
- Related:
  - `set_perport.md` (write — configure one port's security policy) — ⚠️ FORBIDDEN for Phase 0 live testing per the general write-safety rule (but not in the "absolutely forbidden" set, so it's documented as a normal write).
