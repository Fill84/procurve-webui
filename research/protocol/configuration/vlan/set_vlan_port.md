# setVLANPort

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANmodifyPanel.java:119-148`. Query assembled
at lines 120-127:
```
"setVLANPort?VLAN_ID=" + vlanId + "&" + <port-state-body>
```
where the body is `PORT=<id>&MODE=<mode>` pairs joined with `&`
(first pair has no leading `&`, lines 122-126). Dispatched via
`VLANmain.callURL(query)` at line 131.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:**
  `/cgi/setVLANPort?VLAN_ID={vlan_id}&PORT={port_id_1}&MODE={mode_1}&PORT={port_id_2}&MODE={mode_2}...`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer | yes | Target VLAN. |
| `PORT` | decimal integer, **repeating** | yes, one per changed port | Internal port ID (the `port_id`, not `port_name`). |
| `MODE` | decimal integer, **repeating** | yes, one per changed port | New mode — `0`=Auto/No, `1`=Tagged, `2`=Untagged, `3`=Forbid. |

The `PORT`/`MODE` pairs are emitted in change order — only
ports whose mode was actually modified are sent
(`MultiList.getChangedPortsID()`).

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, one line. On success starts with
  `OK` (substring check at `VLANmodifyPanel.java:137`
  `string2.substring(0, 2).equals("OK")`). On failure the body is
  a human-readable error message shown directly in a `VLANDialog`
  (no `error~` prefix is required; any non-`OK` prefix triggers the
  dialog).
- **Success indicator:** Body begins with `OK`.
- **Error indicators:** Body doesn't begin with `OK`.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| vlan_id | `VLAN_ID` | decimal integer | `int` | `1..4094` | |
| port_ids | `PORT` (repeating) | decimal integer | `list[int]` | >=1 entry | Internal port index — e.g. `1`..`24`, `73`..`75` for trunks on our 2810. |
| modes | `MODE` (repeating) | decimal integer | `list[int]` | `0..3`, same length as `port_ids` | See encoding note. |

## Example request

Set VLAN 20 so ports 5 and 6 become Tagged (MODE=1) and port 7
becomes Untagged (MODE=2). Byte-exact:

```
GET /cgi/setVLANPort?VLAN_ID=20&PORT=5&MODE=1&PORT=6&MODE=1&PORT=7&MODE=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Note the pairing: `PORT` and `MODE` alternate. The applet never sends
a `PORT=` without an immediately-following `MODE=`.

## Example response

Prepared example only — no live test.

Success:
```
OK
```

Error:
```
Cannot tag primary VLAN on trunk ports
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field, field_validator


class PortModeChange(BaseModel):
    port_id: int
    mode: int = Field(ge=0, le=3)  # 0=Auto/No, 1=Tagged, 2=Untagged, 3=Forbid


class SetVlanPortRequest(BaseModel):
    vlan_id: int = Field(ge=1, le=4094)
    changes: list[PortModeChange] = Field(min_length=1)


class SetVlanPortResponse(BaseModel):
    ok: bool
    error_message: str | None = None
```

For `httpx` — interleave the keys in order:

```python
params: list[tuple[str, str]] = [("VLAN_ID", str(req.vlan_id))]
for c in req.changes:
    params.append(("PORT", str(c.port_id)))
    params.append(("MODE", str(c.mode)))
r = client.get("/cgi/setVLANPort", params=params)
```

## Notes & caveats

- **Key-order is load-bearing.** The switch may be order-sensitive
  (`PORT` immediately followed by its `MODE`). Python clients must
  preserve interleaving and **not** use a dict that would group
  all `PORT`s first and all `MODE`s second.
- **Only changed ports are sent.** The applet calls
  `getChangedPortsID()`, which returns only rows whose user-edited
  mode differs from the server-reported mode. Python clients should
  follow the same pattern — sending `PORT=x&MODE=<current>` for
  unchanged ports wastes work and may trigger unnecessary
  validation errors.
- **Mode encoding.** Derived from `VLANmodifyPanel.java:79-83`
  (`{" ", "Auto/No", "Tagged", "Untagged", "Forbid"}`) and
  `MultiList.setModeForSelected` (MultiList.java:295-310) which
  subtracts 1 from the selected index. So:
  - `0` = Auto (GVRP ON) / No (GVRP OFF)
  - `1` = Tagged
  - `2` = Untagged
  - `3` = Forbid
- **No response parsing in the happy path.** The applet only checks
  the first two bytes for `OK` and skips to the next line; it treats
  blank lines as "read one more" (line 134-136). Python parser should
  do the same.
</content>
</invoke>