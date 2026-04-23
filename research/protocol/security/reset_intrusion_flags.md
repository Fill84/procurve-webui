# reset_intrusion_flags

**Tab:** security
**Kind:** write
**Source in applet:** none — plain HTML form.
**Source in HTML:** `research/mirror/2026-04-23/security/intrusion2.html` (live-fetched 2026-04-23), L7:

```
<form action="../cgi/intrusion_clear">
    <input type="submit" value=" Reset Alert Flags ">
</form>
```

## HTTP contract

- **Method:** GET (HTML default — no `method="POST"`).
- **URL template:** `/cgi/intrusion_clear`
- **Query params:** none. The submit button has no `name` attribute, so clicking it adds nothing to the URL (browser omits unnamed controls).
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):** `unknown — needs live capture under user supervision`.
- **Response body:** `unknown — needs live capture under user supervision`. Likely a redirect back to `/security/intrusionf.html` or a short `OK~` line.
- **Success indicator:** HTTP 200 or 302 redirect; body does not contain `error`.
- **Error indicators:** body starting with `error~`.

## Field reference

No fields (button-only form).

## Example request (prepared — NOT live-tested)

```
GET /cgi/intrusion_clear HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Not captured. Per `memory/feedback_switch_write_safety.md` we do not live-test writes in Phase 0 even though this write is low-risk (clearing cosmetic alert flags; doesn't reconfigure anything). Live capture deferred to Phase 1 Task 1.14.

## Pydantic sketch

```python
from pydantic import BaseModel


class ResetIntrusionFlagsRequest(BaseModel):
    pass  # no inputs


class ResetIntrusionFlagsResponse(BaseModel):
    applied: bool
    message: str | None = None
```

## Notes & caveats

- Very low-risk write — only clears cosmetic alert flags, does not change configured port-security policies or erase the log itself.
- Not in the "absolutely forbidden" write set (not a password change, not a reset, not a manager-list edit). Still deferred to Phase 1 for live capture.
- Related: `get_intrusion.md`.
