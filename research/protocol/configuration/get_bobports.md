# get_bobports

**Tab:** configuration
**Kind:** read
**Source in applet:** `SwitchBob.java:64-85` (init reads the `getURL`
applet param, defaulting to `../cgi/get_bobports`, and builds
`m_psURL`); `SwitchBob.java:99-168` (`updateStatus()` opens the GET
and parses device / card / port records); `SwitchBob.java:170-201`
(`parseDeviceInfo()` + `parseCardInfo()`); `SwitchBob.java:203-278`
(`parsePortInfo()`). The `XFishBob` subclass (used by the 2810-24G
closeup) has the same contract with an absolute-path default —
`XFishBob.java:54-69`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/device_view.html:49-57`
(`<applet code=XFishBob.class>` with `<param name=getURL value="../cgi/get_bobports">`).
The frameset entry point is
`research/mirror/2026-04-23/configuration/device_viewf.html:5`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_bobports`
- **Query params:** none. The applet sends the bare endpoint; any
  parameters would be ignored.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, LF-separated. Multi-section stream:

  1. **Device line** (first line, always present) — 2 fields:
     `<codename>~<port_count>` e.g. `Pilsner~24`. Parsed by
     `SwitchBob.parseDeviceInfo` (line 170-176). `Pilsner` is the
     internal codename for the 2810-24G model family; `24` is the
     total port count.
  2. **Card/port blocks.** After the device header the body emits
     one or more repeat blocks. Each block is:
     - a **card line** (one tilde-delimited token: the card type,
       e.g. `GigT` — the port ID is implied), parsed by
       `parseCardInfo` (line 178-201), OR
     - a **port line** with 6-7 tilde-delimited fields (see below)
       — one per physical port.
     Blank lines separate blocks. On the 2810-24G capture there is
     one card and 24 port lines back-to-back with no trailing card
     break.

  Port line layout, per `parsePortInfo` (SwitchBob.java:211-223):
  ```
  <port>~<kind>~<label>~<link>~<enabled>~<mode>~<poe>
  ```
  - position 0 `<port>` — port number (`1`..N). The literal `none`
    signals an absent port and the applet skips it (line 226, 234).
  - position 1 `<kind>` — e.g. `GigT`, `Fiber`, `.` (the applet
    remaps `.` to `Fiber` internally — line 242).
  - position 2 `<label>` — human label rendered under the port.
  - position 3 `<link>` — `1` / `on` = carrier up;
    `0` / `off` = carrier down. Parsed as
    `string.equals("on") || string.equals("1")` (line 218).
  - position 4 `<enabled>` — `1` / `yes` = admin-enabled;
    otherwise disabled. Same equality test (line 220).
  - position 5 `<mode>` — human-readable link mode, e.g.
    `1000FDx`. Optional; empty if `stringTokenizer.hasMoreElements()`
    is false (line 221).
  - position 6 `<poe>` — PoE state code: `1` = no power (black LED),
    `3` = warning (yellow), else green. Optional (line 222).

- **Success indicator:** HTTP 200 with a first line whose second
  token parses as an integer (the port count).
- **Error indicators:** Non-200 HTTP. Java-side `IOException`
  (SwitchBob.java:157-160) leaves the applet's cached state
  unchanged; the Python client should surface the error.

## Field reference

| field | wire position | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| (device line) codename | 0 | string | `str` | | Model family codename (e.g. `Pilsner`). |
| (device line) port_count | 1 | decimal integer | `int` | `>= 1` | Total physical ports. |
| (port line) port | 0 | decimal integer OR `"none"` | `int \| Literal["none"]` | | `none` = slot empty. |
| (port line) kind | 1 | string | `str` | | `GigT`, `Fiber`, `.` (=Fiber). |
| (port line) label | 2 | string | `str` | may be `.` | Rendered label (not port_name; this is usually the port number). |
| (port line) link | 3 | `"0"`/`"1"`/`"on"`/`"off"` | `bool` | | Carrier state. |
| (port line) enabled | 4 | `"0"`/`"1"`/`"yes"`/`"no"` | `bool` | | Admin state. |
| (port line) mode | 5 | string | `str \| None` | optional | Link mode label. |
| (port line) poe | 6 | `"1"`/`"3"`/other | `int \| None` | optional | PoE state code. |

## Example request

```
GET /cgi/get_bobports HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_bobports.response.txt` (live-captured
2026-04-23, 387 bytes).

Excerpt:
```
Pilsner~24
1~GigT~1~1~1~
2~GigT~2~1~1~
...
24~GigT~24~1~1~
```

## Pydantic sketch

```python
from typing import Literal
from pydantic import BaseModel


class BobDevice(BaseModel):
    codename: str
    port_count: int


class BobPort(BaseModel):
    port: int | Literal["none"]
    kind: str
    label: str = ""
    link: bool
    enabled: bool
    mode: str | None = None
    poe: int | None = None


class BobPortsResponse(BaseModel):
    device: BobDevice
    ports: list[BobPort]
```

## Notes & caveats

- **No sentinel.** Same bare-stream pattern as `get_ports` and
  `listVLANS`.
- **Dual-row chassis.** The 2810-24G has 24 RJ-45 ports plus mini-
  GBIC transceiver slots; the `isdual=true` applet param
  (device_view.html:55) tells `XFishBob` to render two rows. The
  CGI body itself is flat — the applet derives the row layout from
  the port count alone.
- **PoE state absent on the 2810.** All observed rows end with a
  trailing `~` (empty `poe` cell). Parsing must tolerate missing
  trailing tokens.
- **Related:** `set_bobports` — the companion write endpoint for
  admin-enable/disable. `get_espData?SLOT_ID=N` — a separate CGI
  invoked only on alt-click of a transceiver slot (GenericBob.java:371);
  not part of the normal refresh loop and not documented as a
  Configuration-tab operation.
