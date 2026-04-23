# set_ssl

> ⚠️ **FORBIDDEN:** Never invoked against the live switch.
> Rewriting or disabling SSL config can sever the management session
> and regenerate/revoke the server cert mid-connection, risking lockout.
> See `memory/feedback_switch_write_safety.md`. Only the user runs this
> operation manually when they choose.

**Tab:** security
**Kind:** write
**Source in applet:** none — plain HTML form with a client-side JS helper
that stitches together state from multiple frames before submitting.
**Source in HTML:** `research/mirror/2026-04-23/security/ssl_cert1.html`
(live-fetched 2026-04-23). Form declaration at L313:
`<Form Name=certcreate action="../cgi/setssl">`. The `submitApply()`
helper (L276-300) assembles the final URL.

## HTTP contract

- **Method:** GET (HTML default — no `method="POST"` attribute).
- **URL template:** `/cgi/setssl?action={action}&prt={port}&certific={certific}&certtype={certtype}&rsakey={rsakey}&startdatem={…}&enddatem={…}&…` (full field set below).
- **Query params (top-level, always present):**

  | name | type | required | description |
  |---|---|---|---|
  | `action` | int | yes | SSL enable state — mirrors the `sslstate` option value: `1`=Off, `2`=On. Written at `ssl_cert1.html:294` (`form.action.value = st`). |
  | `prt` | int | yes | SSL port (default 443). `ssl_cert1.html:295`. |
  | `certific` | int | yes | Certificate installation mode. `ssl_cert1.html:291-296`: `3` = self-signed / create, `2` = use installed. |

- **Query params (certificate-creation fields, required only when `certific=3` and `action=2`):**

  | name | type | description |
  |---|---|---|
  | `certtype` | int | `3` = Self Signed, `4` = Create CA Request (`<Option Value=3/4>` at `ssl_cert1.html:324-327`) |
  | `rsakey` | int | RSA key size — `1`=Current Key, `2`=512, `3`=768, `4`=1024 (`ssl_cert1.html:334-337`) |
  | `startdatem`, `startdated`, `startdatey` | int | Validity start month/day/year |
  | `enddatem`, `enddated`, `enddatey` | int | Validity end month/day/year |
  | `cn` | string | Common Name |
  | `orgname` | string | Organization Name |
  | `orgunit` | string | Organization Unit |
  | `city` | string | City |
  | `state` | string | State |
  | `country` | 2-letter code | Country (ISO-3166 alpha-2, picked from a baked-in list at `ssl_cert1.html:29-…`) |

  The exact field names beyond the top three (`action`, `prt`, `certific`)
  were not fully enumerated in the mirrored HTML (the file is 30 KB of
  per-country `<option>` entries and the lower form section). Live-capture
  of a form-submit is `unknown — needs live capture under user supervision`.

- **Request headers:** standard.
- **Request body:** none (GET).
- **Response headers (relevant):** `unknown — needs live capture under user supervision`.
- **Response body:** `unknown — needs live capture under user supervision`. Likely an HTML confirmation page or redirect.
- **Success indicator:** HTTP 200 with body NOT containing `error`. `unknown`.
- **Error indicators:** body starting with `error~`.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| ssl_enabled | `action` | querystring int | `bool` | `1`=Off, `2`=On |
| ssl_port | `prt` | querystring int | `int` | default 443 |
| cert_mode | `certific` | querystring int | `CertificMode` enum | `3`=self-signed/create, `2`=use installed |
| cert_type | `certtype` | querystring int | `CertType` enum (optional) | `3`=Self Signed, `4`=CA Request |
| rsa_key | `rsakey` | querystring int | `RSAKey` enum (optional) | 1=current, 2=512, 3=768, 4=1024 |
| validity_start | `startdate{m,d,y}` | 3×int | `date` (optional) | |
| validity_end | `enddate{m,d,y}` | 3×int | `date` (optional) | |
| common_name | `cn` | querystring | `str` (optional) | |
| organization_name | `orgname` | querystring | `str` (optional) | |
| organization_unit | `orgunit` | querystring | `str` (optional) | |
| city | `city` | querystring | `str` (optional) | |
| state | `state` | querystring | `str` (optional) | |
| country | `country` | querystring 2-char | `str` (optional) | |

## Example request (prepared — NOT live-tested)

Enable SSL on port 443, keep current certificate:
```
GET /cgi/setssl?action=2&prt=443&certific=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Generate a self-signed certificate (full form — field names tentative):
```
GET /cgi/setssl?action=2&prt=443&certific=3&certtype=3&rsakey=4&startdatem=1&startdated=1&startdatey=2026&enddatem=1&enddated=1&enddatey=2036&cn=HP2810_01&orgname=Example&orgunit=IT&city=Kamer&state=NH&country=NL HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Not captured. Per `memory/feedback_switch_write_safety.md` we do not
live-test writes in Phase 0. Enabling SSL or regenerating the cert while
the management connection is in flight could interrupt the session.

## Pydantic sketch

```python
from datetime import date
from enum import IntEnum
from pydantic import BaseModel


class SSLActionCode(IntEnum):
    OFF = 1
    ON = 2


class CertificMode(IntEnum):
    USE_INSTALLED = 2
    CREATE_OR_SELF_SIGNED = 3


class CertType(IntEnum):
    SELF_SIGNED = 3
    CA_REQUEST = 4


class RSAKey(IntEnum):
    CURRENT = 1
    BITS_512 = 2
    BITS_768 = 3
    BITS_1024 = 4


class SetSSLRequest(BaseModel):
    enabled: SSLActionCode = SSLActionCode.ON
    port: int = 443
    cert_mode: CertificMode = CertificMode.USE_INSTALLED
    cert_type: CertType | None = None
    rsa_key: RSAKey | None = None
    validity_start: date | None = None
    validity_end: date | None = None
    common_name: str | None = None
    organization_name: str | None = None
    organization_unit: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class SetSSLResponse(BaseModel):
    applied: bool
    message: str | None = None
```

## Notes & caveats

- Turning SSL on or regenerating the cert can interrupt the current HTTP session if the browser is connecting via HTTPS already. Defer to Phase 1 live capture under user supervision.
- The `action` field is double-duty: the `sslstate` option value on the form maps directly to the `action` wire key. The field name is misleading because most CGIs use `action` as an operation selector; here it is the power state of the SSL subsystem.
- The `certific` value is assembled in `submitApply()` from which radio button is selected on `ssl_cert.html`: `3` if "Create" is checked, `2` if "Use Installed" is checked. The value `1` (from `ssl_config.html`'s `sslStatus`) is not used for `certific`.
- Country list is 250+ entries, harvested from `ssl_cert1.html:29-…`. The new UI should reuse that list verbatim for consistency with the firmware's expectations.
- Full param list beyond `action`/`prt`/`certific` is `unknown — needs live capture under user supervision`. The HTML contains the input fields but the JS that appends them to the URL was truncated by the subset of the file I read — Phase 1 should scrape the complete HTML.
