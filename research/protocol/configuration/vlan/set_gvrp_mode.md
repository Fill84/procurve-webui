# setGVRPMode

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANfirstPanel.java:190` — `callURL("setGVRPMode?MODE=" + n2)`
where `n2` is `1` (enable) or `2` (disable). Response drained and
compared to `"OK"` at line 198.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/setGVRPMode?MODE={mode}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `MODE` | decimal integer | yes | `1` = enable GVRP, `2` = disable GVRP. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. Expected `OK` on success.
- **Success indicator:** Body equals `OK` (case-insensitive).
- **Error indicators:** Non-200; non-OK body. Exact error format
  **unknown — needs live capture**.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| mode | `MODE` | decimal integer | `int` | `1` = enable, `2` = disable. |

## Example request

Enable GVRP:

```
GET /cgi/setGVRPMode?MODE=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Disable GVRP:

```
GET /cgi/setGVRPMode?MODE=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Prepared example only — no live test.

Success:
```
OK
```

## Pydantic sketch

```python
from pydantic import BaseModel


class SetGvrpModeRequest(BaseModel):
    enabled: bool

    def to_wire_mode(self) -> int:
        return 1 if self.enabled else 2


class SetGvrpModeResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **`family=1`-only.** Toggled through the GVRP checkbox which is
  only enabled for `family == 1` (`VLANfirstPanel.java:65-71`).
  This matches our 2810.
- **Reboot warning.** The applet shows a reboot-required
  `VLANDialog` when the user toggles the checkbox — see
  `VLANfirstPanel.java:106-120`. This is shared with `setVLANMode`.
  However, the `VLANfirstPanel.m_checkboxGVRP.addItemListener` at
  lines 123-136 does **not** re-open the reboot dialog for GVRP
  alone — only the VLAN-enable checkbox does. So GVRP toggles take
  effect immediately without reboot, based on the Java path.
- **Same 1/2 encoding as `setVLANMode`.**
</content>
</invoke>