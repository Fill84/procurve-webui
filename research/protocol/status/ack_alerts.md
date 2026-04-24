# ack_alerts

**Tab:** status
**Kind:** write (fault-log mutation — does NOT modify running-config; affects only the in-memory event list)
**Source in applet:**
- Bulk path: `status/overview3.html` (live-fetched 2026-04-24) → `ackEvents()` calls `submitMultipleItems('../cgi/fflog', 'action=ack', '_loopback', true, false)`; the wire URL is built by `ListPane.submitMultipleItems` in `research/decompiled/ListPane.java:560` — see the same file for the encoding rules.
- Single-event path: `status/ffbuttons.html` (captured 2026-04-24) uses `parent.fff.location='../cgi/ffaction?indeces=<N>&action=ack'`.

## HTTP contract

This operation has **two wire variants** that both produce the same semantic effect — acknowledging one or more events in the fault log.

### Variant A — bulk (`/cgi/fflog`)

- **Method:** GET
- **URL template:** `/cgi/fflog?indeces=<csv>&action=ack&dt=<ts1>[&dt=<ts2>…]`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | CSV decimal (URL-encoded comma `%2C`, applet uses literal `,`) | yes | Row IDs of the events being acked (position 0 of each fflog row). |
  | action | literal `ack` | yes | Distinguishes ack from del. |
  | dt | decimal int | yes, repeated | One per selected event, in the same order as `indeces`. The applet appends the `ts_centiseconds` from column index 3 (`params=.~.~dt~.` in overview.html) for every selected row. Acts as an integrity token — a stale `dt` will be rejected. |

- **Request body:** none.
- **Response status:** HTTP 200 on success.
- **Response body:** empty or a short ack marker (not inspected by the applet — `_loopback` target means the applet drops the response and re-fetches `cgi/fflog?action=list` on a subsequent click).

### Variant B — single event (`/cgi/ffaction`)

- **Method:** GET
- **URL template:** `/cgi/ffaction?indeces=<single-index>&action=ack`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | decimal int (no commas in the observed single-event case) | yes | One `row_id`. |
  | action | literal `ack` | yes | |

- No `dt` param in this variant — the switch apparently treats the ffaction endpoint as a shortcut.
- Observed in the source of `status/ffbuttons.html`; not live-tested.

### Choice

For our backend, **prefer variant A** (the bulk path) for both single and multi-event ack calls — one code path, one format. The ffaction shortcut is documented for completeness but not used.

## Example request (variant A)

```
GET /cgi/fflog?indeces=1&action=ack&dt=11094915 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Multi-event:

```
GET /cgi/fflog?indeces=1%2C2&action=ack&dt=11094915&dt=11120000 HTTP/1.1
```

## Example response

**Not captured.** Writes have not been live-tested per the operator's write-safety rule (`memory/feedback_switch_write_safety.md`). The applet discards the response body (`_loopback` target → it re-GETs `cgi/fflog?action=list` to refresh the table). Likely shape: HTTP 200 with empty or minimal body. On rejection (e.g. stale `dt`) the applet presumably still shows the old event — the switch signals failure by keeping the row in the list rather than by the response body.

## Notes & caveats

- **NO auto-backup required.** Acking events changes only the fault-log in RAM, not the switch's running-config. Unlike every other `@WRITE` endpoint in Phase 3 we do NOT need `write_with_autobackup` before this — the `download_config`/`upload_config` round trip would be wasteful and doesn't protect against anything (the fault log isn't part of the backed-up config). Our `app/api/status.py` ack endpoint follows the same exception we made for ping/link-test.
- **Still `require_writable` gated.** `READ_ONLY=true` blocks ack/del via the normal gate so a read-only operator can't tamper with the log.
- **Semantic behaviour.** The applet's "Acknowledge" button on events is an operator-workflow flag — it marks the event as seen but does NOT remove it. Delete is the removal action.
- **Alert log as the source of truth.** After an ack the next `GET /cgi/fflog?action=list` should reflect the acked state (column/icon may change, or the row may be visually demoted; the exact rendering is controlled by the `images=11~10~2~3~4` applet param and is irrelevant to our structured API).
- **`dt` ordering.** The applet emits one `dt=` per selected row, in the same iteration order as the `indeces=` CSV. Our caller must preserve that ordering: for `indeces=1,2` the query must end with `&dt=<ts-of-row-1>&dt=<ts-of-row-2>`.
