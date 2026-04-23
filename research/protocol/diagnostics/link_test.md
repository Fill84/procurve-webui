# link_test

**Tab:** diagnostics
**Kind:** write  (issues a link probe; no config change)
**Source in applet:** none — same HTML form as `ping`, with the test-type radio switched to `tp=2`.
**Source in HTML:** `research/mirror/2026-04-23/diagnostics/ping.html` — see `diagnostics/ping.md` for the shared form definition. The only wire difference is `tp=2` instead of `tp=1`.

## HTTP contract

- **Method:** GET.
- **URL template:** same as `ping` — `/cgi/ping?index={index}&interf={interf}&action={action}&tp=2&da={da}&nr={nr}&to={to}`.
- **Query params:** identical to `ping` except `tp=2`. The JS in `ping.html` (L34-56) uses a different allowed-characters set when `tp` radio is `2`:
  - tp=1 (ping): `0123456789.` (IPv4 dotted-quad)
  - tp=2 (link): `0123456789.-abcdefABCDEF` (permits MAC-dash or hex — link-test target is typically a MAC address on the same L2)
- **Response body:** same HTML shape as `ping` — `Successes: <N>` / `Failures: <N>` plus LED row.
- **Success indicator:** HTTP 200 with body containing `Successes:`.
- **Error indicators:** body missing `Successes:`.

## Field reference

Same as `ping` — see `diagnostics/ping.md`. Only the interpretation of `destination` differs (MAC address in link mode vs. IPv4 in ping mode).

## Example request (prepared — NOT live-tested)

Link test to a hypothetical local MAC:
```
GET /cgi/ping?index=0&interf=0&action=start&tp=2&da=00-1b-44-11-3a-b7&nr=10&to=5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Not captured separately — link-test response shape is identical to
`ping`. Re-running `diagnostics__ping.response.txt` capture with `tp=2`
and a MAC target is deferred to Phase 1 Task 1.14 under user supervision.

## Pydantic sketch

Covered by the shared `PingRequest` model in `ping.md`; client code
selects `test_type=PingTestType.LINK` (value 2).

## Notes & caveats

- Same endpoint as `ping`; documented separately because the Diagnostics UI treats them as distinct features (different radio button → different input validation → different semantic).
- The firmware may respond with failures for all 20 LED slots when the MAC is not on any connected port — this is expected, not an error.
- Related: `ping.md`, same `/cgi/ping` endpoint.
