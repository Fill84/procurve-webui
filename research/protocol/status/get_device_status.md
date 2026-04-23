# get_device_status

**Tab:** status (and the persistent top banner on every page)
**Kind:** read
**Source in applet:** `DeviceStatus.java:53` (reads `url` param),
`DeviceStatus.java:154-188` (`refresh()` opens GET and parses the
tilde-delimited single-line response).
**Source in HTML:** `research/mirror/2026-04-23/ncidbar.html:83-90` —
the persistent device-status banner applet. Hosted on every page
(via `home.html`'s frameset), not only the Status tab, but the Status
tab's `alert.html` / `overview2.html` refresh button at
`research/mirror/2026-04-23/status/overview2.html:9`
(`parent.parent.parent.ncidbar.document.DeviceStatus.updateState();`)
also triggers this same applet's refresh.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/fflog?action=status`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | action | literal `status` | yes | Selects the condensed status-banner variant of the fault-log CGI. (The list variant is `action=list` — see `get_alert_log.md`.) |

  Note: `DeviceStatus.java:158` appends `&tslch=<centiseconds-since-last-change>&lindex=<last-index>` to the **body** string (`object`), but this string is never used — it is shadowed on the next line (`:159`) where the URL is constructed from `m_urlName` directly without appending `object`. The `tslch`/`lindex` params are dead code in the decompile. **Do not send them.**

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. The applet reads exactly one line
  (`DeviceStatus.java:165` — `string = bufferedReader.readLine();`)
  and tokenizes it on `~` (`DeviceStatus.java:177-181`):

  Single line, up to 4 tilde-delimited fields:
  ```
  <state>~<index>~<description>~<ts_centiseconds>
  ```

  Field semantics per `DeviceStatus.java:178-181`:
  - `state` — required; one of the names enumerated in the
    `states` applet param (not set by ncidbar.html, so the applet
    default applies — `m_States` is `null` in this deployment). The
    observed value `1` corresponds to the `10d.gif` status icon
    indirectly via `images=11~10~2~3~4` in overview.html. For a
    healthy idle switch, expect `unknown` or `normal`; for an alert
    condition, a code matching the image index.
  - `index` — optional, string. Links to a specific alert row
    (used by the click-through to `../ncfw_b.html?index=`).
  - `description` — optional, human-readable; trimmed at
    `DeviceStatus.java:180`. The applet strips the first literal
    `"% "` if present (`DeviceStatus.java:182-184`).
  - `ts_centiseconds` — optional, integer (stored in
    `m_TimeOfLastChange`; compared later to support change
    detection).

  **Observed quirk:** the live fixture for this switch returns the
  same payload shape as `action=list` (two lines), despite the
  applet reading only the first. The second line (if present) is
  ignored.

- **Success indicator:** HTTP 200, single-line first record with at
  least one `~`-field.
- **Error indicators:** On IOException or MalformedURL, the applet
  silently keeps its previous state. Non-200 HTTP → applet drops the
  update.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| state | position 0 of line 1 | string | `str` (or enum over the values in the `states` applet param) | required | Maps to one of the status icons in `classes/status/<state>d.gif`. |
| index | position 1 of line 1 | string | `str \| None` | optional | Row-id to open on click. |
| description | position 2 of line 1 | string | `str \| None` | optional; `.strip()` then strip leading `"% "` prefix | Human-readable. |
| ts_centiseconds | position 3 of line 1 | decimal integer | `int \| None` | `>= 0` | Centiseconds of the last change. |

## Example request

```
GET /cgi/fflog?action=status HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_device_status.response.txt` (live-captured
2026-04-23, 90 bytes, SHA256
`04b45708f24fbe6a359df775b992391f5ed19a6a2399990bb56f878a3d414390`).

Full capture:
```
2842990~1
1~10 3~Loss of link~3644720~Lost connection to multiple devices on port: 10.

```

The applet only consumes line 1 (`2842990~1`): `state=2842990`,
`index=1`. In this deployment the switch appears to emit the same
payload for `action=list` and `action=status`, with the first line
being a cursor rather than a true state record. The applet's
behaviour (ignoring line 2) explains why the banner just shows an
icon indexed by `state` — the meaningful alert detail actually comes
from line 2, which is only consumed via the `action=list` view.

## Pydantic sketch

```python
from pydantic import BaseModel


class DeviceStatusBanner(BaseModel):
    state: str
    index: str | None = None
    description: str | None = None
    ts_centiseconds: int | None = None
```

## Notes & caveats

- **Dead-code `tslch` / `lindex` params.** `DeviceStatus.java:158`
  builds a query string `"&tslch=...&lindex=..."` into a local
  `object` variable, but the URL constructed on the next line
  (`DeviceStatus.java:159`) is `new URL(getCodeBase(), m_urlName)` —
  it ignores `object`. Our Python client should **not** send
  `tslch` / `lindex`.
- **Poll interval.** `ncidbar.html:86` sets `delay=30`, so the
  applet re-fetches every 30 seconds.
- **Same CGI, different action.** `/cgi/fflog` multiplexes on
  `action`. See `get_alert_log.md` for the `action=list` variant
  that returns the full row list.
- **Response shape is protocol-quirky.** On this specific firmware
  (N.11.78) the `action=status` response appears to be identical
  to `action=list` rather than a condensed single-line status. The
  applet's `readLine()` + first-line parse still works because the
  first line is a 2-field meta record. Any client following the
  applet's rules (read first line, split on `~`, take fields 0-3)
  will be tolerant of this.
- **Banner is global.** The `DeviceStatus` applet lives in
  `ncidbar.html`, which is loaded by the top frameset for every
  navigation — the status indicator in the upper-right of the UI.
  It is not unique to the Status tab, but its CGI is the logical
  root of the Status family and belongs under `status/`.
- **Click-through URL.** When the user clicks the banner,
  `DeviceStatus.java:204-207` navigates to
  `../ncfw_b.html?index=<m_CurrentIndex>` in the `proxyf` frame.
  That's a pure HTML page redirect; no extra CGI involvement.
