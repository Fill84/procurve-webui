# get_port_usage

**Tab:** status
**Kind:** read
**Source in applet:** `PortGraph.java:127-130` (reads the `URL`
param, default `../cgi/port_usage`); `PortGraph.java:824-843`
(`updatePortData()` constructs the full URL and opens the GET);
`PortGraph.java:897-925` (`parsePortInfo()` tokenizes each row on
`~`).
**Source in HTML:** `research/mirror/2026-04-23/status/portgraph.html:27-30`
(the `PortGraph` applet host, with `URL=../cgi/port_usage`,
`pollRate=10000`). The applet is itself hosted inside
`research/mirror/2026-04-23/status/overviewf.html:8-10` (a frameset
sibling to the alert log), so it appears on the Status > Overview
page.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/port_usage?LAST_PORT={last_port}&NUM_PORTS={num_ports}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | LAST_PORT | int | yes | Cursor: the last port already fetched. On the first call, pass `0`. The switch returns rows for ports strictly greater than this value, until it has returned `NUM_PORTS` ports (or all remaining ports when `NUM_PORTS=-1`). After parsing, the applet updates its internal `m_lastPortRead` to the highest port seen (PortGraph.java:910). |
  | NUM_PORTS | int | yes | Maximum rows to return. The applet sends `-1` on its first fetch (when its row cache `m_label` is empty) to drain the whole switch, then `26` on subsequent refreshes — PortGraph.java:832 (`this.m_label.isEmpty() ? "&NUM_PORTS=-1" : "&NUM_PORTS=" + 26`). The literal `26` appears to be a magic constant slightly larger than the 24-port chassis to cover uplinks or future slots. |

  Construction: PortGraph.java:832:
  `new URL(getCodeBase(), m_urlStr + "?LAST_PORT=" + m_lastPortRead + "&NUM_PORTS=" + <-1 or 26>)`

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, LF-separated lines, tilde-delimited
  fields. One row per port. No sentinel — bare row stream. Each row
  is 7 fields, parsed at PortGraph.java:910-919:

  ```
  <port>~<label>~<state>~<usage1>~<usage2>~<usage3>~<speed>
  ```
  positions (variable-name mapping from PortGraph.java):
  - position 0 `<port>` → `m_lastPortRead` (int); sets the cursor.
  - position 1 `<label>` (`string7`) → rendered port label on the
    x-axis. If longer than 3 chars, truncated to 1 or 2 chars by
    the applet (PortGraph.java:912-914).
  - position 2 `<state>` (`string6`) → single-char status code:
    - `G` — green / good / up (PortGraph.java:643 — only `G` ports
      are clickable in the graph).
    - `W` — white / warning / down-but-enabled.
    - `N` — not present / disabled.
    - `R` — red / error (PortGraph.java:926-928 sets
      `m_redPort = true`).
  - position 3 `<usage1>` (`string5`) → first utilisation-bar
    segment (integer percent 0..100). Rendered as the lowest stack
    in the bar.
  - position 4 `<usage2>` (`string4`) → second utilisation
    segment (integer percent).
  - position 5 `<usage3>` (`string3`) → third utilisation
    segment (integer percent). The tooltip shows the sum
    `usage1 + usage2 + usage3` as total utilisation
    (PortGraph.java:572-574).
  - position 6 `<speed>` (`string2`) → rendered speed string, e.g.
    `1Gbs`, `100Mbs`. Optional — `hasMoreTokens()` check at
    PortGraph.java:919.

- **Success indicator:** HTTP 200 with at least one tilde-delimited
  row whose first token parses as an integer port number.
- **Error indicators:** Non-200 HTTP; Java-side `SecurityException`
  triggers a frame navigation to `securityURL`
  (PortGraph.java:854-860) — the configured fallback page is
  `../securitymsg.html` (portgraph.html:29).

## Field reference

| field | wire position | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| port | 0 | decimal integer | `int` | `>= 1` | 1-based port number. |
| label | 1 | string | `str` | | Rendered label; if >3 chars, the applet truncates. Python client should keep the full label. |
| state | 2 | single char | `Literal['G', 'W', 'N', 'R']` | one of G/W/N/R | G=up, W=down (enabled), N=disabled/absent, R=error. |
| usage1 | 3 | decimal integer | `int` | `0..100` | First utilisation segment (percent). |
| usage2 | 4 | decimal integer | `int` | `0..100` | Second segment. |
| usage3 | 5 | decimal integer | `int` | `0..100` | Third segment. |
| speed | 6 | string | `str \| None` | optional | e.g. `1Gbs`, `100Mbs`, `10Mbs`. |

## Example request

```
GET /cgi/port_usage?LAST_PORT=0&NUM_PORTS=-1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Subsequent poll (after first fetch has cached all ports):
```
GET /cgi/port_usage?LAST_PORT=24&NUM_PORTS=26 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

(The applet's cursor behaviour means `LAST_PORT` climbs as ports
are read; when it exceeds the last port on the switch, the server
presumably returns an empty body or wraps — this needs live testing
to confirm behaviour of a 26-port request on a 24-port switch.)

## Example response

See `research/fixtures/get_port_usage.response.txt` (live-captured
2026-04-23 with `LAST_PORT=0&NUM_PORTS=-1`, 441 bytes, SHA256
`c57d9578f646515af5b07de7a78f82ee1f3923b71517567f5bfdc521b09dd76c`).

Excerpt:
```
1~1~G~0~0~0~1Gbs
2~2~G~0~0~0~1Gbs
...
11~11~W~0~0~0~1Gbs
...
18~18~G~0~0~0~100Mbs
...
23~23~N~0~0~0~1Gbs
24~24~G~0~0~0~1Gbs
```

Note: all utilisation values in the capture were `0` because the
switch reports percentage of link capacity averaged over the poll
window (10 s per portgraph.html:30), and the observed LAN was idle.
A noisy port would show non-zero values in any of the three
`usage*` slots.

## Pydantic sketch

```python
from typing import Literal
from pydantic import BaseModel


class PortUsage(BaseModel):
    port: int
    label: str
    state: Literal["G", "W", "N", "R"]
    usage1: int
    usage2: int
    usage3: int
    speed: str | None = None

    @property
    def total_usage_pct(self) -> int:
        return self.usage1 + self.usage2 + self.usage3


class PortUsageList(BaseModel):
    ports: list[PortUsage]
```

## Notes & caveats

- **Polling cadence.** The applet polls at `pollRate=10000` ms
  (10 s — portgraph.html:30). Each poll is a full GET (no streaming
  / long-poll), so this is a read-on-interval operation, not a
  persistent connection.
- **`LAST_PORT` is a cursor, not a filter.** The applet increments
  `m_lastPortRead` as it parses each row (PortGraph.java:910) and
  uses the last value as `LAST_PORT` on the next call. This is
  designed to support split responses where the server returns a
  subset per request. In practice, on a 24-port switch with
  `NUM_PORTS=-1`, one GET returns everything; on subsequent polls
  with `NUM_PORTS=26`, the same 24 ports are returned and the
  cursor resets (implicit behaviour of the switch CGI —
  **needs confirmation under live polling over several minutes**).
- **Three `usage*` slots.** Semantically these appear to be stacked
  buckets of utilisation (possibly unicast / multicast / broadcast,
  or RX / TX / combined). The applet draws them as a segmented bar
  (PortGraph.java:367) but never labels them individually. The
  tooltip shows the sum. Without SNMP cross-reference, **the
  precise meaning of each slot is unknown** — mark as a follow-up.
- **`securityURL` fallback.** On a Java `SecurityException` (i.e.
  applet sandboxed against the switch origin), PortGraph redirects
  the frame to `../securitymsg.html`. Not applicable to our Python
  client.
- **Empty body handling.** PortGraph silently accepts empty
  responses (the `while ((string = readLine()) != null)` loop just
  doesn't enter). A Python client should do the same.
- **Label truncation quirk.** The applet truncates labels to 1-2
  chars when longer than 3 — this is purely a rendering decision.
  Our Python model should NOT apply this truncation.
