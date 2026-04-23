# get_ssl_state

**Tab:** security
**Kind:** read
**Source in applet:** none — the SSL page is rendered server-side by the
firmware and the current state is baked into JS variables inside the HTML.
**Source in HTML:**
  - `research/mirror/2026-04-23/security/ssl_config.html` (live-fetched 2026-04-23) — SSL Enable + port.
  - `research/mirror/2026-04-23/security/ssl_cert.html` (live-fetched) — certificate mode radio (create vs. use installed).

The SSL sub-tab landing page `ssl_menu.html` (L3-L12) chooses between
`sslf.html` (self-signed / create-cert view) and `ssl_ca_signedf.html`
(CA-signed view) based on the firmware-injected JS variable `crtStat`:
```
if (crtStat != 2) parent.ssf.document.location = "sslf.html" ;
else              parent.ssf.document.location = "ssl_ca_signedf.html" ;
```

## HTTP contract

- **Method:** GET
- **URL template(s):** there is no single "get SSL state" CGI. The state is
  read by scraping JavaScript initializers out of the rendered HTML pages:

  | URL | fields scraped |
  |---|---|
  | `/security/ssl_config.html` | `sslStatus` (1=Off, 2=On), `Value="443"` (default port, editable) |
  | `/security/ssl_cert.html` | `certificateStatus` (1=create-mode selected, 2=use-installed-mode selected) |
  | `/security/ssl_menu.html` | `crtStat` (1=no CA-signed cert installed, 2=CA-signed cert installed) |

- **Query params:** none.
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):** `Content-Type: text/html`.
- **Response body:** HTML page. Scrape the inline `<script>` for the
  initializer variables listed above.
- **Success indicator:** HTTP 200 with `text/html`.
- **Error indicators:** HTTP 401/403/404.

## Field reference

Projected (scraped) fields, consolidated across the three pages:

| field | source | python type | notes |
|---|---|---|---|
| ssl_enabled | `ssl_config.html` JS `var sslStatus = <int>` | `bool` | 1=Off → False, 2=On → True |
| ssl_port | `ssl_config.html` `<Input Name="sslport" value="443">` | `int` | default 443 |
| cert_mode | `ssl_cert.html` JS `var certificateStatus = <int>` | `CertMode` enum | 1=create / self-signed, 2=use installed |
| ca_signed_installed | `ssl_menu.html` JS `var crtStat = <int>` | `bool` | 1=not installed → False, 2=installed → True |

## Example request

```
GET /security/ssl_config.html HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See fixtures:
- `research/fixtures/security__get_ssl_config_page.response.txt` (942 bytes, SHA256 `60328377a2744fb756ebbf381a96fd3351439b00fd9a24b8082895009fb85aa0`)
- `research/fixtures/security__get_ssl_cert_mode_page.response.txt` (916 bytes, SHA256 `7ca61f82eb4bdc465a1eb6e9a4f3b58a5a4fff0ec8501470df8aa2270f68531f`)

Excerpt from `ssl_config.html`:
```
<script>
      function initForm()
      {
        var sslStatus = 1 ;
        document.sslsetting.sslstate.options[sslStatus - 1].selected = true;
      }
</script>
...
<Input Type="TEXT" Name="sslport" Size=5 maxlength=5 Value="443">
```

Excerpt from `ssl_cert.html`:
```
<script>
   function initForm()
   {
        var certificateStatus = 1 ;
```

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel


class CertMode(IntEnum):
    CREATE_OR_SELF_SIGNED = 1
    USE_INSTALLED = 2


class SSLState(BaseModel):
    ssl_enabled: bool
    ssl_port: int = 443
    cert_mode: CertMode
    ca_signed_installed: bool
```

## Notes & caveats

- The switch does not expose a tilde-delimited SSL read CGI — we scrape HTML. Regex against the specific JS lines (`var sslStatus = <int>`, `var certificateStatus = <int>`, `var crtStat = <int>`, and `Value="<port>"` on the `sslport` input) is stable as long as the firmware does not change.
- Installed certificate details (Common Name, fingerprints, validity dates, etc.) render in `ssl_cert2.html`'s table cells — but on this switch, the firmware left every cell blank because no certificate is installed (see captured `/tmp/ssl_cert2.html`: `if (certType == 1) alert("No certificate is installed.")`). When a certificate IS installed, scraping the `<td>` values between `<B>...:</B>` markers is the expected approach; fixture capture for that branch is deferred.
- Writing the SSL state (enable/disable, cert generation) goes through `/cgi/setssl` — see `set_ssl.md`.
