# setGVRPPort

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANgvrpPanel.java:111-137`. Body assembled
at lines 112-118 (same pattern as `setVLANPort` — repeated
`PORT=<id>&MODE=<mode>` pairs); prefixed with `"setGVRPPort?"` at
line 119. Dispatched via `VLANmain.callURL(query)` at line 123. The
response body is drained but not inspected.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:**
  `/cgi/setGVRPPort?PORT={port_id_1}&MODE={mode_1}&PORT={port_id_2}&MODE={mode_2}...`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `PORT` | decimal integer, **repeating** | yes, one per changed port | Internal port ID. |
| `MODE` | decimal integer, **repeating** | yes, one per changed port | GVRP mode — `0`=Disable, `1`=Learn, `2`=Block. |

Note: unlike `setVLANPort`, there is **no** leading `VLAN_ID` (GVRP
mode is per-port, not per-VLAN).

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. Expected `OK` on success; the
  applet reads the body but only logs it — no success/error branch.
  Error format is **unknown — needs live capture**.
- **Success indicator:** HTTP 200. Body format is unverified —
  Phase 1 should capture one on the first real-world call.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| port_ids | `PORT` (repeating) | decimal integer | `list[int]` | `len >= 1` | |
| modes | `MODE` (repeating) | decimal integer | `list[int]` | `0..2`, same length as `port_ids` | `0`=Disable, `1`=Learn, `2`=Block. |

## Example request

Set port 5 to Learn (1) and port 6 to Block (2). Byte-exact:

```
GET /cgi/setGVRPPort?PORT=5&MODE=1&PORT=6&MODE=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Matches the Java assembly — no trailing `&` after the last pair
(`VLANgvrpPanel.java:115-117`).

## Example response

Prepared example only — no live test.

Expected success:
```
OK
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field


class GvrpPortModeChange(BaseModel):
    port_id: int
    mode: int = Field(ge=0, le=2)  # 0=Disable, 1=Learn, 2=Block


class SetGvrpPortRequest(BaseModel):
    changes: list[GvrpPortModeChange] = Field(min_length=1)


class SetGvrpPortResponse(BaseModel):
    ok: bool
```

`httpx` call pattern:

```python
params: list[tuple[str, str]] = []
for c in req.changes:
    params.append(("PORT", str(c.port_id)))
    params.append(("MODE", str(c.mode)))
r = client.get("/cgi/setGVRPPort", params=params)
```

## Notes & caveats

- **Only changed ports.** `VLANgvrpPanel.java:113` uses
  `getChangedPortsID()` — same pattern as `setVLANPort`.
- **Key-order is load-bearing.** `PORT` immediately followed by its
  matching `MODE`; no grouping.
- **GVRP must be globally ON.** If `getGVRPMode` returns `OFF` the
  applet doesn't expose this panel. Server-side behaviour when GVRP
  is off but this CGI is called directly is **unknown — needs live
  capture**.
- **Mode encoding.** Choice is `{" ", "Disable", "Learn", "Block"}`
  (`VLANgvrpPanel.java:57-59`); wire = `selected_index - 1` =
  `0/1/2`.
</content>
</invoke>