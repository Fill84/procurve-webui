# get_web_access_page

**Tab:** security
**Kind:** read
**Source in applet:** none — static HTML form page.
**Source in HTML:** `research/mirror/2026-04-23/security/web_access.html`

## HTTP contract

- **Method:** GET
- **URL template:** `/security/web_access.html`
- **Query params:** none. The URL returns the HTML form on a bare GET. Adding the password fields turns this same URL into the `set_device_passwords` write (⚠️ FORBIDDEN — see that doc).
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | `text/html` | |

- **Response body:** the HTML password-change form. Fields of interest for the new UI are the `<input name=...>` defaults — but the firmware renders username fields with empty `value=""` attributes regardless of what is configured in `show running-config`. Reading the *current* usernames requires parsing `running-config` from `/cgi/configfile` (see `backup/download_config.md`) rather than this page.
- **Success indicator:** HTTP 200 with `text/html`.
- **Error indicators:** HTTP 401 once a manager password is set and no `Authorization: Basic …` is sent.

## Field reference

The response is HTML, not tilde-delimited; Pydantic modelling is done on a scraped projection.

| scraped field | source in HTML | python type | notes |
|---|---|---|---|
| operator_username | `<input name=_UserName value="...">` (L52) | `str` | firmware renders empty even when set |
| manager_username | `<input name=_RootName value="...">` (L98) | `str` | firmware renders empty even when set |

## Example request

```
GET /security/web_access.html HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/security__get_web_access_page.response.txt`
(live-captured 2026-04-23, 3421 bytes, SHA256
`0285786ac37993e4b2cb4e039b9204e41dec4e945a911a994aadabe7efebbfc5`).

Excerpt:
```
<form name=websec action="web_access.html">
<input name=_UserName value="" size=16>
...
<input name=_RootName value="" size=16>
```

## Pydantic sketch

```python
from pydantic import BaseModel


class WebAccessPage(BaseModel):
    operator_username: str = ""
    manager_username: str = ""
```

## Notes & caveats

- The HTML returns empty `value=""` even when credentials are configured — this is standard password-form security hygiene (never echo the current password/username back in rendered HTML). The new UI should not rely on this page to display the current usernames; it should scrape `download_config` for that.
- Presence of the page itself still conveys a signal: the switch is reachable and the web UI is enabled. A 401 here means auth is required; a 403/404 means web access has been disabled entirely.
- Related: `set_device_passwords.md` (⚠️ FORBIDDEN write).
