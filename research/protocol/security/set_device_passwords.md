# set_device_passwords

> ⚠️ **FORBIDDEN** — this operation is documented for protocol-parity only. It
> MUST NOT be invoked (not even with user approval) during the Phase-0
> research stage. Setting or clearing the Manager password on the switch
> can lock the tools or the user out of the device with no
> viable recovery short of a physical factory-reset button press.
> See `memory/feedback_switch_write_safety.md` for the safety rule.

**Tab:** security
**Kind:** write
**Source in applet:** none — this is a pure HTML form, no applet class wires it up.
**Source in HTML:** `research/mirror/2026-04-23/security/web_access.html`
  - Frame wrapper: `research/mirror/2026-04-23/security/web_accessf.html`
  - Sub-tab label: `passwords~Device Passwords~../security/web_accessf.html~selected` in `research/mirror/2026-04-23/security/menu.html:11`

## HTTP contract

- **Method:** GET
  The form has no `method=` attribute, so the HTML default (`GET`) applies — even though the fields contain passwords. `web_access.html:32` (`<form name=websec action="web_access.html">`).
- **URL template:** `/security/web_access.html`
  The form's `action="web_access.html"` is a relative URL that resolves against the form's own location (`/security/web_access.html`), so the submission target is the same path. The web server's CGI layer treats a GET of this URL WITH the password fields populated as a write operation, and a GET without the fields as a read of the HTML form page.
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | `_UserName` | string | yes (may be empty) | Operator username. Empty string clears the operator username. |
  | `_UserPasswd` | string | yes (may be empty) | Operator password. Empty string clears the operator password. |
  | `_UserPasswd2` | string | yes | Confirmation of `_UserPasswd`. The HTML does not enforce equality client-side — the server is the only gate; but we mirror the HTML behavior and send both. |
  | `_RootName` | string | yes (may be empty) | Manager (read-write admin) username. |
  | `_RootPasswd` | string | yes (may be empty) | Manager password. |
  | `_RootPasswd2` | string | yes | Confirmation of `_RootPasswd`. |
  | `apply` | literal ` Apply Changes ` | yes | Submit-button name+value pair. Spaces around `Apply Changes` are present in the HTML `value=" Apply Changes "` attribute and must be preserved byte-exact. |

- **Request headers:** standard. Currently the switch has blank creds so no `Authorization: Basic …` is sent; after a manager password is set the browser supplies Basic auth.
- **Request body:** none (GET).
- **Response headers (relevant):** `unknown — needs live capture under user supervision` (forbidden to test).
- **Response body:** `unknown — needs live capture under user supervision`. Based on other HTML-form write paths on this switch, the most likely shape is a confirmation HTML page at the same URL or a 302 redirect back to the security menu.
- **Success indicator:** HTTP 200 with a body that does NOT contain the string `error`. `unknown — needs live capture under user supervision`.
- **Error indicators:** `unknown — needs live capture under user supervision`.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| operator_username | `_UserName` | querystring | `str` | ASCII, `size=16` in HTML | empty string clears |
| operator_password | `_UserPasswd` | querystring | `SecretStr` | `size=16` in HTML; HTML `type=password` | empty clears |
| operator_password_confirm | `_UserPasswd2` | querystring | `SecretStr` | must equal `_UserPasswd` | enforced only by server |
| manager_username | `_RootName` | querystring | `str` | `size=16` | empty clears |
| manager_password | `_RootPasswd` | querystring | `SecretStr` | `size=16`; `type=password` | empty clears |
| manager_password_confirm | `_RootPasswd2` | querystring | `SecretStr` | must equal `_RootPasswd` | server-validated |
| apply | `apply` | querystring | literal | constant | preserve leading/trailing space: `" Apply Changes "` |

## Example request (prepared — NOT live-tested)

```
GET /security/web_access.html?_UserName=operator&_UserPasswd=opsecret&_UserPasswd2=opsecret&_RootName=admin&_RootPasswd=supersecret&_RootPasswd2=supersecret&apply=+Apply+Changes+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Note: the spaces around `Apply Changes` in the submit-button value are URL-encoded to `+` per `application/x-www-form-urlencoded` rules. The leading and trailing `+` are intentional — they come from the HTML `value=" Apply Changes "` attribute.

## Example response

Not captured. The FORBIDDEN banner at the top of this doc prohibits live invocation of this operation during Phase 0.

## Pydantic sketch

```python
from pydantic import BaseModel, SecretStr, field_validator


class SetDevicePasswordsRequest(BaseModel):
    operator_username: str = ""
    operator_password: SecretStr = SecretStr("")
    manager_username: str = ""
    manager_password: SecretStr = SecretStr("")

    @field_validator("operator_username", "manager_username")
    @classmethod
    def _ascii(cls, v: str) -> str:
        if len(v) > 16:
            raise ValueError("username too long (HTML size=16)")
        return v


class SetDevicePasswordsResponse(BaseModel):
    applied: bool
    message: str | None = None
```

## Notes & caveats

- **Blank-credentials sensitivity.** The current switch accepts any request without `Authorization`. Setting a manager password here will immediately require Basic auth on the very next request — including the one that reads back the confirmation page. The Python client must stash the new credentials BEFORE issuing this GET and retry with them if the first request closes the connection.
- **GET for password change.** Yes, passwords travel in the query string — shocking by modern standards but it's what the 2810 firmware implements. URL logs on any intermediate proxy (there shouldn't be any on a management LAN, but worth noting) will contain the passwords in cleartext. Do NOT enable request logging for this operation.
- **Same-URL GET/POST duality.** `/security/web_access.html` serves the HTML form on a bare GET and acts as a password-setting CGI when the form fields are supplied. Our Python client must distinguish by context (caller intent), not by URL shape.
- **Confirmation enforcement is server-side.** The HTML has no `onSubmit` handler — it submits even when `_UserPasswd != _UserPasswd2`. The switch is responsible for rejecting a mismatch.
- **Stack sync warning.** `web_access.html:5-14` JS warns that on a stack-member switch, password changes are overridden by the commander at next sync. The warning is display-only and does not affect the wire contract.
- **Safety:** see `memory/feedback_switch_write_safety.md`. Also see `security/get_web_access_page.md` for the matching safe read of the HTML form (used for UI prefill of the current username values, which the server appears to leave blank on render).
