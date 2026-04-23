# getGVRPPort

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANgvrpPanel.java:143` (called through
`VLANmain.callURL("getGVRPPort")`); parsed at
`VLANgvrpPanel.java:144-162`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/getGVRPPort`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, one line, tilde-delimited. The
  first token is a sentinel-ish GVRP-enable flag; the remainder
  is a stream of three-field port records.

  Layout:
  ```
  <gvrp_enable>~<port_name>~<port_id>~<mode>~<port_name>~<port_id>~<mode>~...
  ```
  - `gvrp_enable` is `ON` or `OFF`. The applet ignores every port
    record unless this token equals `ON` (case-insensitive) —
    `VLANgvrpPanel.java:152-153`.
  - Trailing `~` terminator after the last record.

- **Success indicator:** HTTP 200 with body starting with `ON` or
  `OFF`. This CGI does **not** emit the `OK~`/`error~` sentinel;
  the leading token is instead a GVRP mode flag.
- **Error indicators:** Non-200; empty body; malformed tokens.

## Field reference

Leading sentinel:

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| gvrp_enable | 0 | `ON` / `OFF` | `bool` | If OFF the body's port records are stale / noise. |

Per port record (positions offset from 1, in groups of 3):

| field | wire type | python type | notes |
|---|---|---|---|
| port_name | string | `str` | Display name: `1`..`24`, `Dyn1`..`Dyn3` on our 2810. |
| port_id | decimal integer | `int` | Internal port index (matches port for fixed ports; `73`..`75` for trunks). |
| mode | decimal integer | `int` | `0`=Disable, `1`=Learn, `2`=Block. See "Notes". |

## Example request

```
GET /cgi/getGVRPPort HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__getGVRPPort.response.txt` (live-captured
2026-04-23, 269 bytes).

Raw body:
```
OFF~1~1~-2141579148~2~2~-2141579148~...~7~7~1~8~8~1~9~9~2~10~10~0~...~Dyn1~73~1~Dyn2~74~1~Dyn3~75~1~
```

(The `-2141579148` values in ports 1-6 appear when the switch has
GVRP globally OFF and the firmware leaves those slots uninitialised
— classic 32-bit-int garbage. The applet never renders these
because the leading sentinel is `OFF`. When GVRP is ON the values
are the valid `0`/`1`/`2` mode codes.)

## Pydantic sketch

```python
from pydantic import BaseModel


class GvrpPort(BaseModel):
    port_name: str
    port_id: int
    mode: int  # 0=Disable, 1=Learn, 2=Block


class GetGvrpPortResponse(BaseModel):
    gvrp_enable: bool
    ports: list[GvrpPort]
```

## Notes & caveats

- **Mode encoding.** The applet uses a choice `{" ", "Disable",
  "Learn", "Block"}` at `VLANgvrpPanel.java:57-59`; the wire value
  is the selected index minus one (the `--n` in
  `MultiList.setModeForSelected`, MultiList.java:299). So
  `Disable=0`, `Learn=1`, `Block=2`.
- **Sentinel-gated body.** The applet's
  `fillList()` at `VLANgvrpPanel.java:152` drops every port record
  when `gvrp_enable != "ON"`. Our Python client should surface the
  raw records but mark them stale in the same condition.
- **Uninitialised port records.** When GVRP is globally OFF (our
  fixture), the mode column for non-trunk ports contains a random
  32-bit integer (observed `-2141579148`). Phase 1 tests must treat
  these as "undefined" rather than valid modes.
- **Paired with `setGVRPPort`.** See `set_gvrp_port.md`.
</content>
</invoke>