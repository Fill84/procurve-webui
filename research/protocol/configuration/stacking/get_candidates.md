# get_candidates

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** `MemberCandidateList.java:484`
(`new URL(getCodeBase(), "../cgi/get_candidates")`). Parser at
`:569-594` reads until `line.length() <= 0` and tokenises each line
with `StringTokenizer(line, "~")` (non-returning mode — `~` tokens
discarded).
**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(frameset hosting the member/candidate list applet).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_candidates`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, **one candidate per line**,
  tilde-delimited. Per-line field layout (from parser at
  `MemberCandidateList.java:570-586`):

  ```
  <mac_addr>~<system_name>~<device_type>
  ```

  Exactly three tokens. No leading count or index. The applet right-pads
  each field for display (17 / 23 / 14 characters respectively).

  **Error path:** if the first token is the literal `error`, the second
  token is the error message and rendering stops (`:572-577`).

- **Success indicator:** First token is not the literal `error`.
- **Error indicators:** First token equals `error`; or HTTP non-200.

## Field reference

Per-line positional tokens:

| idx | token | wire type | python type | notes |
|---|---|---|---|---|
| 0 | mac_addr | string | `str` | MAC address in switch-native format (e.g. `001db3-b70e00`). |
| 1 | system_name | string | `str` | Candidate switch's system name. |
| 2 | device_type | string | `str` | Device model string, e.g. `J9021A`. If it starts with `' '`, the applet trims it (`:583-585`) — suggests the switch may sometimes left-pad. |

## Example request

```
GET /cgi/get_candidates HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/stacking__get_candidates.response.txt` (live-captured
2026-04-23, 1 byte, SHA256 `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`).

Contents (bytes): `\n` — a single LF. An empty candidate list.

Hypothetical populated response with two discovered candidates:

```
001db3-cc0001~Potential-SW1~J9021A
001db3-cc0002~Potential-SW2~J9021A
```

## Pydantic sketch

```python
from pydantic import BaseModel


class Candidate(BaseModel):
    mac_addr: str
    system_name: str
    device_type: str


class GetCandidatesResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    candidates: list[Candidate]
```

## Notes & caveats

- **Stacking disabled on this switch (`no stack` in CONFIG.pcc line 148).**
  The candidate list endpoint returns a single LF — effectively empty.
  **Needs live capture on a stacked commander within discovery range
  of at least one free candidate** to verify the populated shape and
  whether trailing tokens (status, IP) exist that the Java parser
  discards.
- **Three tokens only.** Unlike `get_members` which adds device type
  and status, `get_candidates` stops at device type. The applet does
  not read any IP or status field from this endpoint, even though
  candidate IPs are eventually sent back to `set_members` — the
  applet reuses the MAC (left token) as its identity key.
- **Hash the response for drift detection.** Because the "no discovered
  candidates" payload is just `\n`, its SHA256 is the well-known
  `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` (SHA256 of `\n`).
