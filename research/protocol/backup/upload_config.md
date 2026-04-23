# upload_config

**Tab:** backup
**Kind:** write
**Source in applet:** none — this is a pure HTML form. Grep across
`research/decompiled/` for `multipart|enctype|Content-Disposition|uploadConfile|uploadImgfile|boundary|configfile`
returned zero hits; no applet class constructs this URL.
**Source in HTML:**
  - `research/mirror/2026-04-23/configuration/configfileSingle.html` — parent page; provides the "Upload" button that navigates to the form (no slot info passed).
  - `research/mirror/2026-04-23/configuration/uploadConfile.html` — the actual multipart upload form.

## HTTP contract

- **Method:** POST
  (`uploadConfile.html:15` — `<form name="sti" action="../cgi/upload" enctype="multipart/form-data" method="post">`)
- **URL template:** `/cgi/upload`
  (resolved from the form's `action="../cgi/upload"` relative to the form's location `/configuration/uploadConfile.html`; the `..` strips the `/configuration/` prefix.)
- **Content-Type:** `multipart/form-data; boundary=<client-generated>`
  (`uploadConfile.html:15` — the `enctype="multipart/form-data"` attribute. The boundary itself is chosen by the HTTP client and must not collide with any byte sequence in the file part. Browsers use something like `----WebKitFormBoundary<16 hex chars>`; our Python client will pick a fixed literal for byte-match testability.)
- **Request headers:** standard for a form POST. No `X-*` headers; no CSRF token; the blank-credentials manager account means no `Authorization` header is required for the current switch state. When the user sets a manager password, `Authorization: Basic ...` must be sent exactly as for every other applet CGI (see `_conventions.md`).
- **Request body:** `multipart/form-data` with the four parts listed below, in the order the browser submits them (document-source order of the `<input>` elements).

### Multipart parts (order as the browser submits them)

The HTML form (`uploadConfile.html:15-22`) declares four controls. All four are submittable — the visible text input, the file input, the checkbox (when checked), and the submit button (the one that was clicked). A standards-compliant HTTP client will emit all four parts in source order.

#### Part 1: `configname`

- **Field name:** `configname`
- **HTML source:** `uploadConfile.html:17` — `Configuration Name: <input name="configname" value="Config" /><br/>`
- **Encoded as:** text field (no `type="..."` attribute means `type="text"` by default)
- **Content-Disposition:** `form-data; name="configname"`
- **Content-Type:** not set (text default)
- **Body:** UTF-8 bytes of the configuration filename on the switch. Default value is the literal string `Config` (from the HTML `value` attribute). This appears to name the configuration file as stored in flash; the switch lists it in the `Config File` column on `configfileSingle.html` (L52, L62) as `Config` for both Primary and Secondary rows.
- **Notes:** visible, user-editable. No `maxlength` or `size` attribute in the HTML. Whether the switch will accept non-ASCII, whitespace, or empty values is `unknown — needs live capture under user supervision`. For safety the Python client will default to exactly `Config` and restrict to ASCII letters/digits/underscore until we have live validation data.

#### Part 2: `configfile`

- **Field name:** `configfile`
- **HTML source:** `uploadConfile.html:18` — `File: <input type="file"   name="configfile"/><br/>`
- **Encoded as:** file upload (`type="file"`)
- **Content-Disposition:** `form-data; name="configfile"; filename="<filename>"`
- **Content-Type:** `application/octet-stream` (no `accept=` hint in the HTML; browsers fall back to `application/octet-stream` for files with unknown MIME). The switch is not known to validate the part's `Content-Type`.
- **Body:** the raw bytes of the configuration file to restore. These are the same bytes that `download_config` returns — ASCII with CRLF line endings, starting with `; J9021A Configuration Editor; Created on release #<firmware>`. See `download_config.md` for the format. Round-trip fidelity with the previously-downloaded `CONFIG.pcc` MUST be preserved byte-for-byte — do not re-encode, do not normalize line endings, do not strip trailing whitespace.
- **Notes:** The `filename` parameter in the Content-Disposition is sent by the browser based on the user's chosen file on disk. Whether the switch reads/validates `filename` or ignores it in favor of `configname` is `unknown — needs live capture under user supervision`. Our default filename will be `CONFIG.pcc` for consistency with the download endpoint's `Content-Disposition: attachment; filename="CONFIG.pcc"`.

#### Part 3: `reboot`

- **Field name:** `reboot`
- **HTML source:** `uploadConfile.html:19` — `<input name="reboot" type="checkbox" checked>Reboot`
- **Encoded as:** text field containing the checkbox's submitted value
- **Content-Disposition:** `form-data; name="reboot"`
- **Content-Type:** not set
- **Body:** literal string `on` — HTML checkboxes with no explicit `value="..."` attribute submit the string `on` when checked. When unchecked, the part is OMITTED ENTIRELY from the multipart body (standard HTML form behavior).
- **Notes:** The HTML has `checked` as an attribute, so the browser default is "reboot after upload" → part IS present with body `on`. Interpretation: when this part is present, the switch reboots after applying the uploaded config; when absent, the config is stored but the switch continues running the current config until a manual reboot. Confirming this semantic is `unknown — needs live capture under user supervision`. The Python client will expose this as a boolean and omit the part entirely when false (matching browser behavior exactly).

#### Part 4: `Uplo`

- **Field name:** `Uplo`
- **HTML source:** `uploadConfile.html:21` — `<input type="submit" name="Uplo" value="Upload"/>`
- **Encoded as:** text field carrying the submit button's `value`
- **Content-Disposition:** `form-data; name="Uplo"`
- **Content-Type:** not set
- **Body:** literal string `Upload` (from the `value` attribute)
- **Notes:** HTML forms submit the `name=value` pair of the submit button that was clicked. There is only one submit button in this form, so this part is always present when the form is submitted via the UI. The field name `Uplo` looks like a truncation of "Upload" (possibly a Procurve quirk or deliberate 4-char identifier); **preserve byte-exact** per `_conventions.md`'s byte-exact rule for writes.

### Response

- **Response headers (relevant):** `unknown — needs live capture under user supervision`. Based on the general Procurve CGI pattern (all other applet CGIs return `text/plain` or an HTML confirmation page), the most likely shape is either:
  - HTML confirmation page announcing success + auto-reboot timer, OR
  - HTTP 302 redirect back to `configfileSingle.html`, OR
  - Plain-text sentinel (`OK~` / `error~`) following the broader applet convention.
- **Response body:** `unknown — needs live capture under user supervision`.
- **Success indicator:** `unknown — needs live capture under user supervision`. Expected to be HTTP 200 with a body that does NOT contain the substring `error`. If `reboot=on`, the TCP connection will be reset shortly after the response as the switch restarts.
- **Error indicators:** `unknown — needs live capture under user supervision`. Possible failure modes the switch likely rejects on:
  - Malformed config file content (syntax error in the uploaded ASCII)
  - File too large for flash
  - Missing required parts
  - Authorization failure once manager credentials are set
  The specific status code / body pattern for each case can only be determined by live testing.

## Field reference

| wire key | wire type | python type | validation rule | notes |
|---|---|---|---|---|
| `configname` | multipart text part | `str` | default `"Config"`; ASCII, no whitespace until live-validated | visible field; user-editable on the HTML form |
| `configfile` | multipart file part | `bytes` | non-empty; same format as `download_config` response | filename in Content-Disposition likely ignored by switch (to confirm live) |
| `reboot` | multipart text part, OPTIONAL | `bool` | HTML default `True` (checkbox `checked`) | when False, omit the part entirely; when True, body is literal `on` |
| `Uplo` | multipart text part | literal `"Upload"` | always present, always `"Upload"` | submit-button name; note 4-char spelling `Uplo`, preserve byte-exact |

## Example request (prepared — NOT live-tested)

Below is a byte-accurate sketch using the reference backup
`research/backups/2026-04-23/CONFIG.pcc` (2904 bytes, SHA256
`f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11`) as
the file-part body. The boundary uses a fixed literal so the Phase 1
byte-match test is deterministic; in production the client may pick any
boundary that doesn't collide with the config text.

All line terminators in the multipart envelope are CRLF (`\r\n`), per
RFC 7578. The file-part body contains the raw config bytes verbatim
(which themselves use CRLF internally — do not re-normalize).

Content-Length is the sum of all bytes after the blank line separating
headers from body, including boundary markers and the trailing `--`. For
the exact fixture above it is 3246 bytes (precise count verifiable from
the template below: four part headers + boundaries + 2904 file bytes +
the five part bodies `Config`, raw file, `on`, `Upload`, plus terminator).

```
POST /cgi/upload HTTP/1.1
Host: 192.168.178.3
Content-Type: multipart/form-data; boundary=---PROCURVEBOUNDARY
Content-Length: <computed>
Accept: */*

-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="configname"

Config
-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="configfile"; filename="CONFIG.pcc"
Content-Type: application/octet-stream

... (2904 bytes of `research/backups/2026-04-23/CONFIG.pcc` verbatim, CRLF line endings preserved) ...
-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="reboot"

on
-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="Uplo"

Upload
-----PROCURVEBOUNDARY--
```

If `reboot=False` is desired (store config without rebooting), the `reboot` part is OMITTED ENTIRELY:

```
POST /cgi/upload HTTP/1.1
Host: 192.168.178.3
Content-Type: multipart/form-data; boundary=---PROCURVEBOUNDARY
Content-Length: <computed>
Accept: */*

-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="configname"

Config
-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="configfile"; filename="CONFIG.pcc"
Content-Type: application/octet-stream

... (2904 bytes) ...
-----PROCURVEBOUNDARY
Content-Disposition: form-data; name="Uplo"

Upload
-----PROCURVEBOUNDARY--
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field

# ConfigBackup reused from download_config.md — represents the raw
# bytes + metadata of a config snapshot.
from procurve_client.models.backup import ConfigBackup


class UploadConfigRequest(BaseModel):
    backup: ConfigBackup
    config_name: str = Field(default="Config", description="Stored filename on the switch (wire key: configname)")
    reboot: bool = Field(default=True, description="If True, switch reboots after applying; wire part is omitted when False")


class UploadConfigResponse(BaseModel):
    accepted: bool
    rebooting: bool
    message: str | None = None
    # Response shape is still unknown — Phase 1 will populate this
    # from the first user-approved live capture in Task 1.14.
```

## Notes & caveats

- **This operation is not live-tested.** First round-trip demonstration happens only under explicit user approval in Task 1.14 of Phase 1. Every "unknown" marker in this document is a task for that round-trip session.
- **No slot selector.** The parent page (`configfileSingle.html:81`) links to the upload form with a plain `window.location.href='uploadConfile.html'` — no query string, no slot index, no form state carried. The upload form itself has NO slot/idx field. This switch stores config by NAME (`configname=Config`), not by slot — Primary/Secondary on `configfileSingle.html` refer to the software image slots, and both rows display the same `Config` name (L52, L62). Conclusion: one logical config file per name; uploading with a different `configname` would presumably create a separate entry, but this is `unknown — needs live capture under user supervision`.
- **No JavaScript on submit.** `uploadConfile.html`'s only script is `getvalue()` (lines 4-9) which is called from `<body onLoad>` and does nothing but read `window.location.href` into a local variable — no effect on form submission. There is no `onsubmit` handler on the form. This is unlike `configfileSingle.html`'s `download()` function (line 25) which rewrites `idx` before download submit.
- **The `reboot` semantic.** The HTML has `checked` by default, meaning the browser-default behavior uploads AND reboots. A config change without reboot may not fully take effect until the next restart on this platform (typical Procurve behavior: config is saved to flash but running-config is not reloaded). This is `unknown — needs live capture under user supervision`; Phase 1 should default `reboot=True` to match the HTML and document behavior once observed.
- **The field name `Uplo`.** Spelled exactly four characters — looks like a truncation of "Upload" (the value is `Upload`, so the switch may check by value not by name). Per `_conventions.md` byte-exact rule for writes, preserve `Uplo` verbatim on the wire. Our Python symbol for this literal will be `_SUBMIT_BUTTON_NAME = "Uplo"`.
- **Multipart boundary collision risk.** Config text is ASCII with many newlines, quote marks, and hyphens. A boundary like `---PROCURVEBOUNDARY` is safe because config lines never start with multiple dashes followed by that literal. Python's `httpx`/`requests` pick a random boundary and handle collision-checking automatically; manual boundary selection is only needed when the byte-match test demands a fixed value.
- **No image-upload conflation.** `uploadImgfile.html` (linked from `configfileSingle.html:10` via the `buildurl()` JS function for software-image uploads) is a SEPARATE form that was not mirrored in `research/mirror/2026-04-23/`. It targets a different CGI (likely `/cgi/upload` with a different field set, or `/cgi/imgupload`) and is out of scope for this task. Do not confuse the image-upload workflow with config-upload.
- **Unknowns summary** — the following facts cannot be determined from static sources alone and must be captured live under user supervision in Task 1.14:
  1. Response status code on success.
  2. Response body shape on success (HTML page? redirect? plain-text sentinel?).
  3. Response body shape on each error mode (bad config syntax, oversized, missing parts, wrong `configname`).
  4. Whether the switch validates the `filename` parameter in the file part's Content-Disposition.
  5. Whether the switch respects `configname` as the stored name, ignores it, or requires `"Config"` literally.
  6. Whether non-ASCII or whitespace in `configname` is accepted.
  7. Exact behavior when `reboot` part is omitted (stored + delayed apply, vs stored + silent discard until reboot, vs rejected).
  8. Authentication: response when manager password is set and `Authorization` header is missing/wrong (expected 401 but unconfirmed).
