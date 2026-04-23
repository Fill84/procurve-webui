# setVLANMode

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANfirstPanel.java:188` — `callURL("setVLANMode?MODE=" + n2)`
where `n2` is `1` (enable) or `2` (disable). Response drained but
not parsed beyond checking `equalsIgnoreCase("OK")` at line 198.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/setVLANMode?MODE={mode}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `MODE` | decimal integer | yes | `1` = enable VLANs, `2` = disable VLANs. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. Expected `OK` on success; any other
  body is treated as a no-op by the applet (which doesn't display an
  error — it just skips the `equalsIgnoreCase("OK")` branch).
- **Success indicator:** Body equals `OK` (case-insensitive).
- **Error indicators:** Non-200 HTTP; any non-OK body (applet silently
  ignores; server-side error format is **unknown — needs live
  capture**).

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| mode | `MODE` | decimal integer | `int` | `1` = enable, `2` = disable. Note: **NOT** `0`/`1`. |

## Example request

Enable VLAN support:

```
GET /cgi/setVLANMode?MODE=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Disable VLAN support:

```
GET /cgi/setVLANMode?MODE=2 HTTP/1.1
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


class SetVlanModeRequest(BaseModel):
    enabled: bool  # True -> MODE=1, False -> MODE=2

    def to_wire_mode(self) -> int:
        return 1 if self.enabled else 2


class SetVlanModeResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **Requires device reboot.** `VLANfirstPanel.java:106-120` opens a
  `VLANDialog` warning "This operation needs device reboot. Do you
  want to reboot device?" with OK/Cancel buttons. Clicking OK calls
  `device_reset` (the shared diagnostics reset endpoint —
  `VLANDialog.java:46`). The switch will apply the mode change but
  it does not take effect until the reboot completes. Python clients
  should surface the reboot-required state to callers.
- **Voyager-only UI path.** The enable-checkbox is only added to the
  button panel on `family == 0` (`VLANfirstPanel.java:62`). Our 2810
  is `family=1`, so the applet never invokes this endpoint in
  production. We still document it because the CGI itself is present
  on the switch.
- **Mode encoding quirk.** `1`/`2` rather than `0`/`1`. Mirrors the
  `ifAdminStatus=1/2` pattern in `set_bobports` — the applet-era
  HP CGIs uniformly use `1` = enable / `2` = disable for boolean
  admin-state toggles.
</content>
</invoke>