# get_alert_detail

**Tab:** status
**Kind:** read
**Source in applet:** `research/mirror/2026-04-23/status/overview2.html:13-20`
clicks "Open Event" → `openEvent()` in `research/mirror/2026-04-23/status/overview3.html` (fetched live 2026-04-24 via sandbox-permitted read — ovewrite3.html was not in the original mirror). `openEvent()` calls `submitMultipleItems('../status/overview2.html', '', 'fft', true, false)` which navigates the `fft` frame to `overview2.html?indeces=<id>&dt=<ts>`; the template-substituted JS in `overview2.html` then opens a popup to `ffviewf.html?index=<id>&dt=<ts>`, whose inner frame (server-template-substituted) loads `cgi/ffdetail?index=<id>&dt=<ts>`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/ffdetail?index=<row_id>&dt=<ts_centiseconds>`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | index | decimal int | yes | The `row_id` (position 0) of the event row from `GET /cgi/fflog?action=list`. |
  | dt | decimal int | yes | `ts_centiseconds` of the same event (position 3). Acts as an integrity/cursor check — if `dt` does not match the server's current record for `index` the switch may return an empty body. |

- **Request body:** none.
- **Response status:** HTTP 200.
- **Response Content-Type:** `text/html`.
- **Response body:** an HTML detail page. Layout observed (captured 2026-04-24 for a `Loss of Link` event):

  - `<title>` — human-readable event category (e.g. `Loss of Link`).
  - Inline `<script>` defines `hdr(title, dt, port, severity)` and `portMsg(act)`:
    - `hdr("Loss of Link", "11094915", "10", "3")` — title, raw ts-centiseconds, affected port ("0" if not port-specific), severity code (1..5).
    - A `window.setTimeout(...)` assigns `parent.ffbf.location = "../status/ffbuttons.html?index=1&type=11&pt=10&act=2&sfp=000000&se=3&dt=11094915"` — this seeds the buttons-frame with several discriminator fields:
      - `type` — alert type code (11 in the observed fixture)
      - `pt` — port
      - `act` — action context (2 = normal; 3 = port-disabled → adds Re-Enable Port button in `ffbuttons.html`)
      - `sfp` — a 6-digit hex bitmap (unclear meaning; likely SFP/port flags)
      - `se` — severity (same as the `hdr` arg)
  - `<body>` — a `<dl>` with `<dt>` sections:
    - `<dt><b>Description:</b>` `<dd>` — the free-form event description.
    - `<dt><b>Solution:</b>` `<ul><li>…</li></ul>` — troubleshooting steps.
    - `<dt><b>Other Possibilities:</b>` `<dd>` — secondary causes.
  - A final `<script>portMsg("<act>")</script>` call that only renders extra text when act=="3" (port disabled).

- **Success indicator:** HTTP 200 with HTML body containing a `<title>` and a `hdr(...)` call. An index/dt mismatch returns an empty body with HTTP 200 (observed: `Content-Length: 1` for bad `indeces=` query shape).

## Field reference (structured view for downstream parser)

| field | source in HTML | type | notes |
|---|---|---|---|
| title | `<title>…</title>` | str | e.g. `Loss of Link`. Also repeated as the first arg to `hdr(...)`. |
| severity | `hdr(…, …, …, "<N>")` 4th arg | `Literal[1..5]` | maps to one of `11~10~2~3~4` icon codes. |
| affected_port | `hdr(…, …, "<port>", …)` 3rd arg | `int` (0 = none) | Port number if port-specific, else 0. |
| ts_centiseconds | `hdr(…, "<dt>", …, …)` 2nd arg | int | Echo of the `dt` query param. |
| type_code | ffbuttons `type=` param from the `setTimeout` line | int | Alert type discriminator. |
| act_code | ffbuttons `act=` param | int | 2=normal, 3=port-disabled. |
| description | `<dd>` under the `<dt><b>Description:</b>` anchor | str | Free-form text. |
| solution | `<ul><li>…</li></ul>` under `<dt><b>Solution:</b>` | list\[str\] | One entry per `<li>`. |
| other_possibilities | `<dd>` under `<dt><b>Other Possibilities:</b>` | str | Free-form text. |

## Example request

```
GET /cgi/ffdetail?index=1&dt=11094915 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_alert_detail.response.html` (live-captured 2026-04-24, 2562 bytes). Also `research/fixtures/get_alert_detail_ffbuttons.response.html` for the companion buttons-frame (923 bytes).

## Notes & caveats

- **`indeces=` (plural) does NOT work for detail.** The variant `/cgi/ffdetail?indeces=1&dt=<ts>` returns a 1-byte body; detail always uses singular `index=`. The bulk action endpoint (`/cgi/fflog?action=ack|del`) takes plural `indeces=` (see `ack_alerts.md`).
- **Template substitution.** `status/ffviewf.html` fetched without query returns an iframe src of literally `../cgi/ffdetail?` (empty query). When fetched with `?index=1&dt=X`, the iframe src becomes `../cgi/ffdetail?index=1&dt=X`. The switch does server-side template substitution of query params into the HTML. Callers who skip the ffviewf wrapper and hit ffdetail directly must supply both params themselves.
- **Per-alert-type content is switch-firmware-baked.** The description / solution / other-possibilities text comes from a template in the switch firmware keyed on `type_code`. Parsing the generic `<dl>/<dt>/<dd>` structure is sufficient for Phase 3+.
- **`ffbuttons.html` is additional.** The detail page only describes WHAT happened. The action buttons (Ack / Delete / Re-Enable Port / Retest) live in a companion HTML at `status/ffbuttons.html?index=<N>&type=<T>&pt=<P>&act=<A>&sfp=<B>&se=<S>&dt=<ts>`. Our API doesn't serve ffbuttons — we provide ack/del mutations directly.
