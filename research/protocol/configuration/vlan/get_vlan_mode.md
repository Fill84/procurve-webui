# getVLANMode

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANfirstPanel.java:145` (called through
`VLANmain.callURL("getVLANMode")`); parsed at
`VLANfirstPanel.java:152-172`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/getVLANMode`
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
  (case-insensitive; the applet compares with `equalsIgnoreCase("ON")`
  at `VLANfirstPanel.java:160`).
- **Error indicators:** Non-200; any other body value (treated as
  OFF by the applet).

## Field reference

| field | wire | python type | notes |
|---|---|---|---|
| mode | `ON` / `OFF` | `bool` | `True` when wire is `ON`. |

## Example request

```
GET /cgi/getVLANMode HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__getVLANMode.response.txt` (live-captured
2026-04-23, 3 bytes — `ON\n`).

## Pydantic sketch

```python
from pydantic import BaseModel


class GetVlanModeResponse(BaseModel):
    enabled: bool  # True when wire was "ON"
```

## Notes & caveats

- **Only called when `family=0` (Voyager).** `VLANfirstPanel.java:78-80`
  guards `setButtonPanel(0)` behind `family == 0`. Our 2810 is
  `family=1`, so the real applet never issues this request.
  We still document it because the CGI exists on the switch and
  is part of the VLAN protocol surface — a later Python client may
  expose the enable/disable toggle for completeness.
- **Paired with `setVLANMode`.** See `set_vlan_mode.md` for the
  write side.
</content>
</invoke>