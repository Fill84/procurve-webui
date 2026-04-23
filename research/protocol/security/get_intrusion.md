# get_intrusion

**Tab:** security
**Kind:** read
**Source in applet:** `GenericList.class` — `dataURL=../cgi/intrusion`.
**Source in HTML:** `research/mirror/2026-04-23/security/intrusion1.html` (live-fetched 2026-04-23). Applet at L30:

```
<applet code=GenericList.class ... name=list ...>
    <param name=dataURL value="../cgi/intrusion">
    <param name=titles  value="Port~Port Name~Intruder Address~Date / Time">
    <param name=columns value="100~200:x~480~630:t">
    <param name=params  value="pt~.~ia~ti">
</applet>
```

A secondary frame (`intrusion2.html`) shows a summary line (`Port(s) with Intrusion Flag: None`) and a `Reset Alert Flags` button that submits to `/cgi/intrusion_clear` — see `security/reset_intrusion_flags.md` for that write.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/intrusion`
- **Query params:** none.
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | (plain text / unset) | |

- **Response body:** zero or more tilde-delimited records. Empty list renders as a single `\n` (the 1-byte captured fixture proves this). Per-record schema from `params`:

  ```
  <pt>~<port_name>~<ia>~<ti>
  ```

  | position | field (from `params`) | wire meaning |
  |---|---|---|
  | 1 | `pt` | port number |
  | 2 | (pass-through) | port name (free text) |
  | 3 | `ia` | intruder MAC address |
  | 4 | `ti` | date/time string |

- **Success indicator:** HTTP 200; any body (including lone newline) is success.
- **Error indicators:** body starting with `error~`.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| port | `pt` | int as ASCII | `int` | |
| port_name | position 2 | string | `str` | |
| intruder_address | `ia` | string | `str` | MAC in dash notation (XX-XX-XX-XX-XX-XX) |
| timestamp | `ti` | string | `str` | switch-local time format; `:t` in applet `columns` means render-as-time |

## Example request

```
GET /cgi/intrusion HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/security__get_intrusion.response.txt`
(live-captured 2026-04-23, 1 byte, SHA256
`01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`).

Body: single `\n` character (empty log — no intrusions recorded on this switch).

## Pydantic sketch

```python
from pydantic import BaseModel


class IntrusionEntry(BaseModel):
    port: int
    port_name: str
    intruder_address: str
    timestamp: str


class IntrusionLogResponse(BaseModel):
    entries: list[IntrusionEntry]
```

## Notes & caveats

- The empty-log case is a single `\n` byte, not an empty response — preserve this in fixture comparison.
- The "flagged ports" summary shown by `intrusion2.html` (`Port(s) with Intrusion Flag: None`) is baked into that HTML page on render by the switch; it is effectively a second, independent read of the same state. The new UI can either re-render that summary from the `/cgi/intrusion` rows or fetch `intrusion2.html` for the pre-rendered string.
- Related: `reset_intrusion_flags.md` (write — clear the alert flags).
