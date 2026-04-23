# get_view_all

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** `MemberCandidateList.java:491`
(`new URL(getCodeBase(), "../cgi/get_view_all")`). Parser at
`:595-613` reads until EOF and tokenises each line with
`StringTokenizer(line, "~")` (non-returning mode).
**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(frameset hosting the member/candidate list applet). Exposed when the
"show all" checkbox is selected (`MemberCandidateList.java:392-398`).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_view_all`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, **one switch per line**, tilde-delimited.

  Per-line field layout (from parser at
  `MemberCandidateList.java:596-611`):

  ```
  <mac_addr>~<system_name>~<stack_status>~<stack_name>
  ```

  Exactly four tokens per switch. The applet column-orders them for
  display as: `stack_name | mac_addr | system_name | stack_status`,
  right-padded to 21 / 17 / 23 / 25 characters (`:608-611`).

  **Error path:** if the first token is the literal `error`, the second
  token is the error message and rendering stops (`:598-603`).

- **Success indicator:** First token is not the literal `error`.
- **Error indicators:** First token equals `error`; or HTTP non-200.

## Field reference

Per-line positional tokens:

| idx | token | wire type | python type | notes |
|---|---|---|---|---|
| 0 | mac_addr | string | `str` | MAC address. |
| 1 | system_name | string | `str` | Switch's self-reported system name. |
| 2 | stack_status | string | `str` | Role / status. Observed: `Stacking Disabled`, `Others:` (for switches belonging to a different stack). On a member expect values like `Member Up`, `Commander`, etc. |
| 3 | stack_name | string | `str` | Stack name. Empty / absent when the switch isn't in a stack. On our non-stacked capture the line ends with `Others:` and the final token is missing — see caveats. |

## Example request

```
GET /cgi/get_view_all HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/stacking__get_view_all.response.txt` (live-captured
2026-04-23, 52 bytes, SHA256 `a966751da8ba0afd024954f26eb7a4887ac2fc92ed14313fb3a76768d1384694`).

Contents (bytes):
```
001db3-b70e00~HP2810_01~Stacking Disabled~Others:
```
followed by one `\n`. On our non-stacked switch the response is a
single line: this switch's MAC, sysname, a literal `Stacking Disabled`
status, and the literal token `Others:` where the parser expects a
stack name. See caveats.

Hypothetical populated response with several discovered switches:

```
001db3-aa0001~Lab-SW1~Commander~Lab
001db3-aa0002~Lab-SW2~Member Up~Lab
001db3-cc0001~Spare-SW~Stacking Disabled~
001db3-ff0001~Foreign-SW~Member Up~OtherStack
```

## Pydantic sketch

```python
from pydantic import BaseModel


class ViewAllRow(BaseModel):
    mac_addr: str
    system_name: str
    stack_status: str
    stack_name: str = ""


class GetViewAllResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    switches: list[ViewAllRow]
```

## Notes & caveats

- **Stacking disabled on this switch (`no stack` in CONFIG.pcc line 148).**
  The response shape here (`Stacking Disabled~Others:`) suggests the
  CGI emits a literal section-header token (`Others:`) when the local
  switch is not in any stack, rather than emitting a proper 4-token
  record. This may cause the Java parser to advance into an empty field
  state. **Needs live capture on a commander** to confirm:
  1. whether records for the commander itself are 4 clean tokens;
  2. whether `Others:` is a section header or a field value;
  3. how discovered foreign switches appear.
- **`Others:` literal.** The fixture ends with the string `Others:`
  (with trailing colon) rather than a blank 4th token. This may be a
  CGI-emitted header delimiter separating "this stack's switches" from
  "all other discovered switches on the segment". The Java parser does
  not branch on this and would currently populate `stack_name = "Others:"`
  for the single record. A Phase 1 parser should treat a lone `Others:`
  token specially or just pass it through and filter downstream.
- **Called when the user selects "show all"** checkbox in the stacking
  management panel (`MemberCandidateList.java:392-398`). The default
  bottom-list view is `get_candidates`.
