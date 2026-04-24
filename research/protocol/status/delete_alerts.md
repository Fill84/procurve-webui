# delete_alerts

**Tab:** status
**Kind:** write (fault-log mutation — does NOT modify running-config)
**Source in applet:**
- Bulk path: `status/overview3.html:24-30` → `warnUser()` calls `submitMultipleItems('../cgi/fflog', 'action=del', '_loopback', true, true)` after a `confirm(...)` browser dialog. The trailing `true` (second boolean) means the items are also removed from the local Vector immediately (ListPane.java:560, `bl2` branch).
- Single-event path: `status/ffbuttons.html` — `parent.fff.location='../cgi/ffaction?indeces=<N>&action=del'`.

## HTTP contract

Wire encoding is **identical to `ack_alerts.md`** — the only difference is the literal `action=del` instead of `action=ack`.

### Variant A — bulk (`/cgi/fflog`, preferred)

- **Method:** GET
- **URL template:** `/cgi/fflog?indeces=<csv>&action=del&dt=<ts1>[&dt=<ts2>…]`
- One `dt=` per event, in the same order as the `indeces=` CSV.
- `_loopback` target means the applet discards the response and re-fetches `/cgi/fflog?action=list` to refresh.

### Variant B — single event (`/cgi/ffaction`, alternate)

- **URL template:** `/cgi/ffaction?indeces=<single-index>&action=del`
- No `dt` param.

### Choice

Use variant A for the backend (single code path for both one-event and multi-event).

## Example request

```
GET /cgi/fflog?indeces=1&action=del&dt=11094915 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

**Not captured.** Same reason as `ack_alerts.md` — live writes are gated by the operator's write-safety rule.

## Notes & caveats

- **Confirmation is a UI concern.** The applet wraps `warnUser()` in a `confirm("Are you sure you want to delete the selected events?")` JS prompt before firing the HTTP call. Our React UI must reproduce this — a `window.confirm` or a small modal. No typed-IP confirm needed (the operation is neither persistent-config nor lockout-capable).
- **NO auto-backup required.** Same reasoning as ack — the fault log is not part of the backed-up running-config. Skip `write_with_autobackup`.
- **Still `require_writable` gated.** `READ_ONLY=true` blocks this.
- **Idempotency.** Sending del for an already-removed row presumably is a no-op (HTTP 200, fault-log state unchanged). Not tested — worth verifying on first live run.
- **Cascading behaviour.** When the last alert is deleted, `GET /cgi/fflog?action=list` returns just the cursor line and no rows — already handled by our `AlertLog` parser (empty `events`).
