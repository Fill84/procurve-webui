# get_cmd_name

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** Two callers, both parse with default-whitespace
`StringTokenizer` (not `~`-delimited):
- `StackControl.java:325-346` — URL built at `:326`
  (`new URL(getCodeBase(), "../cgi/get_cmd_name")`). Reads lines until an
  empty line; on each line grabs the **first whitespace-delimited token**
  and stores it as `commandSystemName` (`:340`).
- `MemberCandidateList.java:243-267` — URL built at `:244`. Reads one
  line, grabs **seven whitespace-delimited tokens**: token 0 is the
  system name (stored into `string9`, then discarded), tokens 1-6 are
  concatenated as `AABBCC-DDEEFF` into `commanderMacAddr` (`:260`).

The two callers expect *different* wire shapes. See caveats.

**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(frameset hosting both applets).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_cmd_name`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, one line, **whitespace-delimited**
  (NOT `~`-delimited — unique among stacking CGIs). No `OK~` sentinel.

  Expected shape on a stacked commander (inferred from
  `MemberCandidateList.java:259-260`):

  ```
  <system_name> <mac1> <mac2> <mac3> <mac4> <mac5> <mac6>
  ```

  Seven whitespace-separated tokens: the commander's system name,
  followed by six individual MAC-address segments (the applet glues
  them as `mac1mac2mac3-mac4mac5mac6`). Most likely the segments are
  two-hex-digit pairs (6 bytes = 12 hex chars, which the Java
  concatenation then formats as `AABBCC-DDEEFF`).

  Observed on our non-stacked switch (fixture
  `research/fixtures/stacking__get_cmd_name.response.txt`):
  ```
  HP2810_01 Error in Pdu
  ```
  = 23 bytes (22 ASCII + `\n`). Four tokens: the system name followed
  by a literal error phrase `Error in Pdu` (stacking subsystem not
  responding because `no stack`).

- **Success indicator:** Non-empty first token that is not the literal
  phrase-start of an error message. On a true commander, expect seven
  total tokens.
- **Error indicators:** HTTP non-200; or fewer than 7 whitespace
  tokens (as seen on non-stacked switches). `StackControl` silently
  accepts whatever the first token is; `MemberCandidateList` will
  throw `NoSuchElementException` on fewer than 7 tokens.

## Field reference

Whitespace-separated tokens (positional, for `MemberCandidateList`):

| idx | token | wire type | python type | notes |
|---|---|---|---|---|
| 0 | system_name | string | `str` | Commander's sysname. Used by `StackControl` as the label `<name> - Commander` in the switcher dropdown (`:348`). |
| 1 | mac_part_1 | 2-hex string | `str` | First two hex digits of MAC. |
| 2 | mac_part_2 | 2-hex string | `str` | Next two hex digits. |
| 3 | mac_part_3 | 2-hex string | `str` | Next two hex digits. |
| 4 | mac_part_4 | 2-hex string | `str` | Next two hex digits. Applet inserts `-` before this segment. |
| 5 | mac_part_5 | 2-hex string | `str` | Next two hex digits. |
| 6 | mac_part_6 | 2-hex string | `str` | Last two hex digits. |

Concatenated `mac_part_1..6` joined as `{1}{2}{3}-{4}{5}{6}` to form
the switch-native MAC format (`001db3-b70e00`).

## Example request

```
GET /cgi/get_cmd_name HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/stacking__get_cmd_name.response.txt` (live-captured
2026-04-23, 23 bytes, SHA256
`b075fde3132530a60e03f27d60b582022712c4bc6d00bb9ad0b68fee49060ea3`).

Contents (bytes):
```
HP2810_01 Error in Pdu
```
followed by one `\n`. This is the non-stacked-switch response: the
stacking subsystem replies "Error in Pdu" instead of the six MAC
segments (MAC PDU lookup fails because there is no stack).

Hypothetical populated response on a commander with system name
`Lab-Commander` and MAC `001db3-b70e00`:

```
Lab-Commander 00 1d b3 b7 0e 00
```

## Pydantic sketch

```python
from pydantic import BaseModel


class GetCmdNameResponse(BaseModel):
    ok: bool
    system_name: str
    mac_addr: str | None = None   # None when stacking is disabled
    error_message: str | None = None
```

## Notes & caveats

- **Stacking disabled on this switch (`no stack` in CONFIG.pcc line 148).**
  The live fixture ends with `Error in Pdu` after the system name
  instead of the six MAC segments. This is an error-ish response but
  it still returns HTTP 200 with the system name as token 0 — which is
  why `StackControl.loadList(Choice)` (`:340`) accepts it (it only
  consumes token 0), while `MemberCandidateList` would crash parsing
  it. **Needs live capture on a commander** to confirm the six-segment
  MAC format.
- **Whitespace-delimited, not `~`-delimited.** Unique among stacking
  CGIs. `StringTokenizer` with no delimiter argument defaults to
  `" \t\n\r\f"`. Any whitespace character (or run of them) separates
  tokens. Python parsers should use `line.split()` with no argument.
- **Two callers, two expected shapes.** `StackControl` reads only
  token 0. `MemberCandidateList` reads seven tokens. Phase 1 Python
  should tolerate both shapes: always extract token 0 as `system_name`;
  if seven total tokens are present, also extract the MAC.
- **Called during applet bootstrap** by both classes, before any
  stacking operation can be performed.
