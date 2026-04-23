# get_port_counters

**Tab:** status
**Kind:** read
**Source in applet:** `GenericList.java:29, 177-179` (reads the
`dataURL` applet param and passes it to `ListPane.loadData`;
`ListPane.java:471-474` opens the GET and reads the tilde-delimited
rows).
**Source in HTML:** `research/mirror/2026-04-23/status/portc1.html:32-41`
(the `GenericList` applet host; dataURL = `../cgi/portc`). Manual
refresh button is in `research/mirror/2026-04-23/status/portc2.html:22-24`
(`submitMultipleItems('../cgi/portc', '', '_loopback', false, false)`).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/portc`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, LF-separated lines, tilde-delimited
  fields. One row per physical port, in port-number order (1..N).
  No leading `OK~` sentinel — bare-row stream like all `GenericList`
  dataURLs.

  Each row has 10 fields (portc1.html:37 declares 9 rendered
  columns; the wire emits one extra leading/middle field — the
  hidden label cell shared with `get_port_status`):

  Column headers from portc1.html:37 —
  `Port~Port Name~MCast%Rx~MCast%Tx~BCast%Rx~BCast%Tx~Pkts%Rx~Pkts%Tx~Errors%Rx`

  Layout:
  ```
  <port>~<port_name>~<port_type_label>~<mcast_rx>~<mcast_tx>~<bcast_rx>~<bcast_tx>~<pkts_rx>~<pkts_tx>~<errors_rx>
  ```
  positions vs columns:
  - position 0 `<port>` → "Port"
  - position 1 `<port_name>` → "Port Name"
  - position 2 `<port_type_label>` → (hidden / decorative; matches
    position 2 of `get_ports` — `UPS` on port 18 in the observed
    capture, space otherwise)
  - position 3 `<mcast_rx>` → "MCast Rx"
  - position 4 `<mcast_tx>` → "MCast Tx"
  - position 5 `<bcast_rx>` → "BCast Rx"
  - position 6 `<bcast_tx>` → "BCast Tx"
  - position 7 `<pkts_rx>` → "Pkts Rx"
  - position 8 `<pkts_tx>` → "Pkts Tx"
  - position 9 `<errors_rx>` → "Errors Rx"

  All counters are decimal integers. Observed values span up to the
  millions — assume 32-bit unsigned counters that wrap. Units are
  **packets**, not bytes (counter names are `Pkts`, `MCast`, `BCast`).

- **Success indicator:** HTTP 200 with at least one tilde-delimited
  row whose first token parses as an integer port number.
- **Error indicators:** Non-200 HTTP; HTML body instead of text.

## Field reference

| field | wire position | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| port | 0 | decimal integer | `int` | `>= 1` | 1-based port number. |
| port_name | 1 | string | `str` | may be empty | e.g. `1-Dyn1`. |
| port_type_label | 2 | string | `str` | may be `" "` | Hidden label column (e.g. `UPS` on the observed fixture's port 18). |
| mcast_rx | 3 | decimal integer | `int` | `>= 0` | Multicast packets received. |
| mcast_tx | 4 | decimal integer | `int` | `>= 0` | Multicast packets transmitted. |
| bcast_rx | 5 | decimal integer | `int` | `>= 0` | Broadcast packets received. |
| bcast_tx | 6 | decimal integer | `int` | `>= 0` | Broadcast packets transmitted. |
| pkts_rx | 7 | decimal integer | `int` | `>= 0` | Total packets received. |
| pkts_tx | 8 | decimal integer | `int` | `>= 0` | Total packets transmitted. |
| errors_rx | 9 | decimal integer | `int` | `>= 0` | Receive errors. |

## Example request

```
GET /cgi/portc HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_port_counters.response.txt` (live-captured
2026-04-23, 887 bytes, SHA256
`c9c9b1ae80f9045065983dbb225db9132615adaf18dfa64a397d3bca999944f4`).

Excerpt:
```
1~1-Dyn1~ ~1220~39709~65~183~57659~2174938~0
2~2-Dyn1~ ~1220~58671~125~38902~2200694~347978~0
...
18~18~UPS~0~22930~852~38478~852~61427~0
...
24~24~ ~0~21661~1~39329~5216814~3309506~0
```

## Pydantic sketch

```python
from pydantic import BaseModel


class PortCounters(BaseModel):
    port: int
    port_name: str
    port_type_label: str = ""
    mcast_rx: int
    mcast_tx: int
    bcast_rx: int
    bcast_tx: int
    pkts_rx: int
    pkts_tx: int
    errors_rx: int


class PortCountersList(BaseModel):
    ports: list[PortCounters]
```

## Notes & caveats

- **Counters are packet counts, not bytes.** The Status > Port
  Counters tab does not expose byte-level traffic; `get_port_usage`
  (the gauge applet) provides link utilisation percentages derived
  from the switch's internal byte counters but does not return raw
  byte counts either. To get byte-level counters you need the
  Configuration > Port Details dialog, whose formURL is
  `/status/portdf.html` (portc1.html:35) — currently out of scope
  (not mapped in url-literals.md; **needs live capture / further
  investigation**).
- **Counter wrap.** These are SNMP-style counters; they wrap at
  2^32 and will decrement on wrap in naive subtraction math. A
  Python client tracking deltas must tolerate wrap.
- **Per-port detail dialog.** The "Details for Selected Port"
  button in portc2.html:25 navigates to
  `../status/portdf.html?indeces=<port>` (via
  `submitMultipleItems`). That form is not documented here; would
  be a separate `get_port_counter_details` operation.
- **`onlyOneSelection=1`.** portc1.html:33 — the UI constrains the
  Details dialog to a single selected row. No implication for the
  `/cgi/portc` GET itself.
- **Refresh interval.** `delay=10` — 10-second auto-refresh in
  the UI. Mirror the same cadence in the Python polling loop for
  UI parity.
- **Whitespace cells** as in `get_port_status`: position 2 contains
  a literal single space when no label is set.
