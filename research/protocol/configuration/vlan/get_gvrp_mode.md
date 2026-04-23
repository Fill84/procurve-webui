# getGVRPMode

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANfirstPanel.java:148` (called through
`VLANmain.callURL("getGVRPMode")`); parsed at
`VLANfirstPanel.java:152-172`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/getGVRPMode`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, a single token on one line:
  ```
  ON
  ```
  or
  ```
  OFF
  ```

- **Success indicator:** HTTP 200 with body exactly `ON` or `OFF`
  (case-insensitive; applet uses `equalsIgnoreCase("ON")` at
  `VLANfirstPanel.java:160`).
- **Error indicators:** Non-200; any other body value (treated as
  OFF).

## Field reference

| field | wire | python type | notes |
|---|---|---|---|
| mode | `ON` / `OFF` | `bool` | `True` when wire is `ON`. |

## Example request

```
GET /cgi/getGVRPMode HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__getGVRPMode.response.txt` (live-captured
2026-04-23, 4 bytes — `OFF\n`).

## Pydantic sketch

```python
from pydantic import BaseModel


class GetGvrpModeResponse(BaseModel):
    enabled: bool  # True when wire was "ON"
```

## Notes & caveats

- **Only called when `family=1` (Infinity) or higher.**
  `VLANfirstPanel.java:147` guards the call behind `m_family == 1`.
  Our 2810 is `family=1`, so this CGI is actively used.
- **Paired with `setGVRPMode`.** See `set_gvrp_mode.md`.
- **GVRP is globally OFF on this switch** (fixture = `OFF`), which
  is why `getGVRPPort`'s sentinel token is also `OFF` and the
  applet leaves the GVRP panel inactive by default.
</content>
</invoke>