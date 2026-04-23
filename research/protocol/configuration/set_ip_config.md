# set_ip_config

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/ip2.html:54-55`
(`<form name=ipi action="../cgi/ip" onReset="doReset();" onSubmit="return doSubmit();">`),
with the hidden `rt` field (line 56) filled in from
`parent.ipvf.document.iprt.rt.value` by `doSubmit()` (line 37),
hidden `VLAN` (line 62) and `mode` (line 63) fields,
and the inline frame
`ip_mode.html` (lines 22-27) that drives the mode selector. The
frameset entry is
`research/mirror/2026-04-23/configuration/ipf.html:3-8`.
Sub-tab key in menu: `ip` (menu.html:40).

## HTTP contract

- **Method:** GET.
- **URL template:** `/cgi/ip?rt={gateway}&VLAN={vlan_id}&mode={mode}&apply=+Apply+Changes+`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | rt | IPv4 dotted-quad | yes | Default gateway. Value is copied from the sibling frame's `/cgi/gateway` form by `doSubmit()` (ip2.html:37). Defaults to `0.0.0.0` if blank (ip1.html:44-47). |
  | VLAN | integer | yes | VLAN ID the IP config applies to. Hidden; on this switch it's `97` (ip2.html:62) — the primary VLAN. On a multi-VLAN switch the ip1 frame redirects to `ip1a.html` with a per-VLAN selector (ip1.html:37-41). |
  | mode | `1`, `2`, or `3` | yes | IP assignment mode: `1` = Disabled (no IP), `2` = Manual, `3` = DHCP/Bootp. See `ip_mode.html:22-27`. |
  | apply | literal `" Apply Changes "` | submit button name | Preserve for byte-exact replay. |

- **Request headers:** none beyond standard.
- **Request body:** none (GET).
- **Response body:** **not live-tested** (per Phase-0 safety rules —
  this call can break connectivity). The page warns "Changing IP
  configuration could result in loss of browser connectivity to the
  current URL" (ip2.html:95-96) and additionally `doSubmit()` asks
  for explicit confirmation when `mode=1` (Disabled) — line 39-47.
  Expected body: a short `OK~...` acknowledgement.
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP; loss of connectivity after
  applying `mode=1`.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| gateway | `rt` | dotted-quad IPv4 | `IPv4Address \| Literal["0.0.0.0"]` | strict IPv4 | May be `0.0.0.0` meaning "no default gateway". |
| vlan_id | `VLAN` | integer | `int` | `1..4094` | VLAN the IP config is bound to. On single-VLAN switches always the primary VLAN. |
| mode | `mode` | `1`/`2`/`3` | `Literal[1, 2, 3]` | exact values | 1=Disabled, 2=Manual, 3=DHCP/Bootp. |
| apply | `apply` | literal `" Apply Changes "` | `str` | exact literal | Submit-button value; preserve. |

## Reading the current value

No dedicated CGI. The live VLAN, mode, gateway, IP address, and
subnet mask are injected server-side into `ip2.html`:
- `<input type=hidden name=VLAN value=97>` (ip2.html:62)
- `<input type=hidden name=mode value=3>` (ip2.html:63)
- IP Address text: `192.168.178.3` (ip2.html:77)
- Subnet Mask text: `255.255.255.0` (ip2.html:87)

The gateway is held in the sibling frame `ip1.html`:
- `defaultGateway = "192.168.178.1";` (ip1.html:31, a JS literal
  set by the page-generation template)
- `<input name=rt value="192.168.178.1" size=16>` (ip1.html:64)

A Python client must GET both
`/configuration/ip2.html` and `/configuration/ip1.html` and scrape.
Same injected-JS pattern as `set_fault_detection.md`.

## Example request

Switch to Manual with explicit IP / mask (note: the page never
exposes `ip` or `mask` inputs — those aren't editable via web UI
on this firmware; only gateway, VLAN, and mode are) — so the most
common request is changing just the gateway + mode:

Set gateway to 192.168.178.1, VLAN 97, DHCP mode:
```
GET /cgi/ip?rt=192.168.178.1&VLAN=97&mode=3&apply=+Apply+Changes+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Switch to manual mode, keep gateway:
```
GET /cgi/ip?rt=192.168.178.1&VLAN=97&mode=2&apply=+Apply+Changes+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from enum import IntEnum
from ipaddress import IPv4Address
from pydantic import BaseModel, Field


class IpMode(IntEnum):
    DISABLED = 1
    MANUAL = 2
    DHCP = 3


class SetIpConfigRequest(BaseModel):
    gateway: IPv4Address  # wire: rt; 0.0.0.0 allowed
    vlan_id: int = Field(ge=1, le=4094)  # wire: VLAN
    mode: IpMode  # wire: mode


class SetIpConfigResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **Can break connectivity.** `mode=1` disables IP entirely; the
  page asks for user confirmation. A Python client that exposes
  this should require explicit opt-in.
- **IP address and subnet mask are read-only on this firmware.**
  The form does not submit them, and scraped values suggest they
  are either set via CLI or derived from the VLAN config. The wire
  keys `ip` / `mask` exist in older 2810 firmware but are omitted
  here.
- **The gateway lives in a sibling frame.** ip1.html and ip2.html
  are two different forms in two different frames. The apply
  button on ip2.html's form reaches into ip1.html via
  `parent.ipvf.document.iprt.rt.value`. Python callers consolidate
  both into one request; this is a UI quirk, not a wire-protocol
  one.
- **Related:** `set_default_gateway` (see that file) — the
  sibling `/cgi/gateway` endpoint, which the `Apply` button on the
  gateway frame (ip1.html) submits independently when clicked
  directly. In practice the two CGIs are usually called together.
