# ping

**Tab:** diagnostics
**Kind:** write  (issues an ICMP echo from the switch; no config change)
**Source in applet:** none — plain HTML form + JS in `ping.html`.
**Source in HTML:** `research/mirror/2026-04-23/diagnostics/ping.html` L63:
```
<form name=pgf action="../cgi/ping" target=pgsf>
<input type=hidden name=index value="0">
<input type=hidden name=interf value="0">
<input type=hidden name=action value=start>
...
<input type=radio name=tp value=1 checked> Ping Test
<input type=radio name=tp value=2>          Link Test
<input name=da ...>       (destination)
<select name=nr>  ... packets
<select name=to>  ... timeout
```

The frameset (`pingf.html`) has two children:
- `../cgi/ping` (top frame `pgsf`) — starts empty; populated by form submission.
- `ping.html` (bottom frame `pgf`) — the form UI.

## HTTP contract

- **Method:** GET  (HTML default; no `method="POST"`).
- **URL template:** `/cgi/ping?index={index}&interf={interf}&action={action}&tp={tp}&da={da}&nr={nr}&to={to}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | `index` | int | yes | Test index — starts at `0`, auto-increments. The Start button copies `parent.pgsf.document.pgf.index.value` over it before submit (each consecutive run picks up from the previous response's echoed index). |
  | `interf` | int | yes | Interface selector. Hidden field defaults to `0`. |
  | `action` | string | yes | `start` to initiate a run, `stop` to cancel an in-progress run (the Stop button submits the `parent.pgsf` form which carries `action=stop` in its response-page's form). |
  | `tp` | int | yes | Test type — `1` = Ping Test, `2` = Link Test |
  | `da` | string | yes | Destination address. For `tp=1` accepts IPv4 (0-9 + .); for `tp=2` accepts extra characters (`0-9.-abcdefABCDEF`) per `ping.html:40-42`, suggesting a MAC or IPv6-style input is acceptable for link test |
  | `nr` | int | yes | Number of packets to send. Options in the form: `1`, `5`, `10` (default), `20`. |
  | `to` | int | yes | Timeout in seconds. Options: `1`, `5`, `10`, `30`. |

- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | `text/html` | response is HTML, not tilde-delimited |

- **Response body:** HTML fragment showing "Successes: <N>" / "Failures: <N>" plus a row of 20 green/red LED images (`gled.gif` / `rled.gif`), followed by a hidden form used for subsequent invocations. See captured fixture.
- **Success indicator:** HTTP 200 with `text/html` and body containing `Successes:`.
- **Error indicators:** HTTP 200 with body missing `Successes:`, or `Failures: 20` (all-failed run).

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| index | `index` | int | `int` | >=0 | opaque continuation token; first call sends `0` |
| interface | `interf` | int | `int` | 0 default | |
| action | `action` | string | `PingAction` | `start` \| `stop` | |
| test_type | `tp` | int | `PingTestType` | `1`=ping, `2`=link | |
| destination | `da` | string | `str` | IPv4 for ping, MAC/hex for link | JS enforces allowed-char class per test type |
| packet_count | `nr` | int | `int` | {1,5,10,20} | |
| timeout_s | `to` | int | `int` | {1,5,10,30} | |

## Example request

Ping the switch's own IP once with a 5-second timeout (harmless, captured below):
```
GET /cgi/ping?index=0&interf=0&action=start&tp=1&da=192.168.178.3&nr=1&to=5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/diagnostics__ping.response.txt` (live-captured
2026-04-23 pinging switch's own IP, 1142 bytes, SHA256
`b4b419b6148d75c77738347f518bbfdf2c11fd2c530dfec68304da2d645d91a5`).

Body excerpt (whitespace preserved):
```
<center><font face=Helvetica color=black size=2></font></center><html><head></head><body bgcolor=white><center><table>
<tr><th align=left>Successes: 1</th><th align=right>Failures: 0</th></tr>
<tr><td colspan=2>
  <img src=/diagnostics/gled.gif> ... (20 LED images) ...
</td></tr></table></center>
<form name=pgf action="/cgi/ping">
    <input type=hidden name=index value=1>
    <input type=hidden name=action value="stop">
    <input type=hidden name=nr value=1>
    <input type=hidden name=su value=1>
    <input type=hidden name=at value=1>
</form></body></html>
```

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel


class PingTestType(IntEnum):
    PING = 1
    LINK = 2


class PingAction(str, Enum):  # type: ignore[name-defined]
    START = "start"
    STOP = "stop"


class PingRequest(BaseModel):
    destination: str
    test_type: PingTestType = PingTestType.PING
    packet_count: int = 10
    timeout_s: int = 5
    index: int = 0
    interface: int = 0
    action: str = "start"


class PingResponse(BaseModel):
    successes: int
    failures: int
    raw_html: str  # for the new UI to render LEDs or parse further
```

(Note: the `Enum` import for PingAction should be `from enum import Enum`.)

## Notes & caveats

- **Not in the "absolutely forbidden" set.** Ping is genuinely read-only in terms of switch configuration — it issues an ICMP or link probe and returns results. The risk is network-side (e.g., accidentally ping-flooding a critical host by running with nr=20). Defaults match the HTML (nr=10, to=5 or 10) and are safe.
- **Self-ping is harmless and useful.** The captured fixture pings `192.168.178.3` (the switch's own IP). This is the documented safe fixture. For a production-UI test the new client should prefer pinging a local reachable host chosen by the user, not auto-populate a default.
- **Index semantics.** Each response echoes `value=N+1` in its hidden `index` field; re-submitting picks the new value up. This lets the switch distinguish sequential runs in its internal log. A client that ignores `index` (always sends `0`) works too — the switch does not reject this.
- **Stop button.** The UI's Stop button submits the response-frame's form, which carries `action=stop` plus the current `index`. Our Python client will issue `GET /cgi/ping?index=<last>&action=stop&...` to cancel an in-flight test.
- Related: HTML report page (no separate CGI).
