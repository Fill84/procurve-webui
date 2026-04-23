# get_alert_log

**Tab:** status
**Kind:** read
**Source in applet:** `GenericList.java:29, 177-179` (the `dataURL`
param is read at init, then passed to `ListPane.loadData` which opens
a GET against it via `new URL(getCodeBase(), dataURL)` — see
`ListPane.java:471-474`).
**Source in HTML:** `research/mirror/2026-04-23/status/overview.html`
(the applet host), with a manual `Refresh` button in
`research/mirror/2026-04-23/status/overview2.html:7-8` that re-submits
the same URL via `submitMultipleItems('../cgi/fflog', 'action=list', ...)`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/fflog?action=list`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | action | literal `list` | yes | Selects the list-view of the Fault Detection / alert log. Other known action is `status` — see `get_device_status.md`. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** none inspected by the applet
  (it unconditionally wraps the stream in `BufferedReader`; see
  `research/analysis/callback-layer.md` "Content-Type expected").
- **Response body:** plain text, LF-separated lines, tilde-delimited
  fields. Unlike most CGIs on this switch, the response does **not**
  begin with `OK~` or `error~` — the `GenericList` list view is a
  pure row stream. First line is a header/meta line; subsequent lines
  are row records. Empty trailing line is present.

  Line 1 — meta/cursor line (2 fields):
  ```
  <latest_event_ts_centiseconds>~<total_events_or_cursor>
  ```
  Example: `2842990~1`

  Lines 2..N — one row per alert event (5 fields; aligned with the
  four rendered columns declared by overview.html:38 `titles=Status~
  Alert~Date / Time~Description` plus a leading row-index / icon
  token):
  ```
  <index>~<alert_name>~<category>~<ts_centiseconds>~<description>
  ```
  Example:
  `1~10 3~Loss of link~3644720~Lost connection to multiple devices on port: 10.`

  The `images=11~10~2~3~4` applet param (overview.html:41) maps the
  first token (or severity code) to one of five icon indices in the
  Status column.

- **Success indicator:** HTTP 200 with tilde-delimited body. No
  per-line sentinel.
- **Error indicators:** HTTP non-200, or HTML error page in lieu of
  tilde-delimited text (the applet silently drops these per
  callback-layer.md).

## Field reference

Meta line (line 1):

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| latest_ts_centiseconds | position 0 | decimal integer | `int` | `>= 0` | sysUpTime (centiseconds) of the most recent event; used for cursor/polling. |
| cursor_or_count | position 1 | decimal integer | `int` | `>= 0` | Possibly total-events-since-boot or incremental cursor. |

Row line (one per event, lines 2..N):

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| row_id / severity | position 0 | string | `str` or `int` | | Consumed as row key and as the severity-icon lookup into the `images` param. In the observed fixture the value is `1`. |
| alert_name | position 1 | string | `str` | | e.g. `10 3`. Format is opaque; corresponds to the overview.html `Alert` column. |
| category | position 2 | string | `str` | | Human-readable category, e.g. `Loss of link`. |
| ts_centiseconds | position 3 | decimal integer | `int` | `>= 0` | Event timestamp in centiseconds (since boot). Rendered via the `dt` column formatter (overview.html:40 `params=.~.~dt~.`). |
| description | position 4 | string | `str` | | Full description text. May include a period and free-form text. |

## Example request

```
GET /cgi/fflog?action=list HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_alert_log.response.txt` (live-captured
2026-04-23, 90 bytes, SHA256
`09a83020ed209dc945207bb4157248cb20b4412aab3b8d979cc3099b9044507f`).

Full capture:
```
2842990~1
1~10 3~Loss of link~3644720~Lost connection to multiple devices on port: 10.

```

## Pydantic sketch

```python
from pydantic import BaseModel


class AlertEvent(BaseModel):
    row_id: str
    alert_name: str
    category: str
    ts_centiseconds: int
    description: str


class AlertLog(BaseModel):
    latest_ts_centiseconds: int
    cursor_or_count: int
    events: list[AlertEvent]
```

## Notes & caveats

- **No sentinel.** Unlike VLAN / stack operations, this CGI does not
  prefix its response with `OK~`. Do not reject the body if the first
  token is not `OK`. (See `research/analysis/callback-layer.md`
  "Sentinel strings" — the bare-row variant is used by `listVLANS` and
  by every `GenericList` dataURL.)
- **`action=status` variant.** The same CGI also serves
  `?action=status` (used by the persistent top-banner
  `DeviceStatus` applet — `ncidbar.html:85`); documented separately
  as `get_device_status.md`. Different response shape.
- **Polling / incremental.** `overview.html:42-45` sets
  `delay=15` (15-second auto-refresh) and `incremental=yes` — the
  applet re-GETs every 15 s and treats the stream as append-only.
  The first-line cursor presumably supports that, but no query-string
  cursor parameter is sent by the applet; each refresh is a full GET
  of the same URL.
- **Timestamps are centiseconds, not ms.** Matches the Identity-tab
  uptime convention.
- **Manual refresh** from overview2.html passes query string
  `action=list` via `submitMultipleItems('../cgi/fflog',
  'action=list', '_loopback', false, false);` (overview2.html:7-8).
  The two-string form gets joined with `'?'` by the callback
  (`GenericList.submitMultipleItems`), producing the same URL.
- **Delete / Ack / Open Event buttons** on overview2.html:13-20 do
  NOT hit `fflog` directly; they navigate the frame to
  `../status/overview3.html?exec=...` which runs further JavaScript.
  Those mutations are out of scope for Phase 0 Status docs (writes
  are forbidden) and will be analyzed separately if we ever need
  them.
- **Empty log.** When the switch has no alerts, only the meta line
  (and trailing newline) is returned; the `events` list is empty.
