# get_members

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** `MemberCandidateList.java:476`
(`new URL(getCodeBase(), "../cgi/get_members")`) — parser at
`:522-567`; also `StackControl.java:318` with parser at `:358-393`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(frameset hosting the member/candidate list applet).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_members`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, **one member per line**,
  tilde-delimited. Lines are consumed until `string.length() <= 0`.

  Per-line field layout (reconstructed from `MemberCandidateList.java:532-564`
  using `StringTokenizer(line, "~", true)` — i.e. delimiter tokens
  themselves are returned, which is why the parser consumes them
  explicitly):

  ```
  <switch_num>~<mac_addr>~<system_name>~<device_type>~<status>
  ```

  The applet consumes separator tokens between each data field, and
  uses a special case: if the third data token is literally `~` (i.e.
  a field is empty), it substitutes `" "` (a single space) for both
  `string4` and `string3` and skips one further token
  (`MemberCandidateList.java:545-551`).

  **Error path:** if the first token is the literal `error`, the second
  token (after the separator) is the error message shown in a
  `StackDialog` (`MemberCandidateList.java:535-539`).

- **Success indicator:** First token is numeric (switch number) and not
  equal to `error`.
- **Error indicators:** First token equals `error`; or an empty body
  (no member records).

## Field reference

Per-line positional tokens (after stripping `~` separator tokens):

| idx | token | wire type | python type | notes |
|---|---|---|---|---|
| 0 | switch_num | integer-as-string | `int` | Stack member index 0..15. Used as `sw{N}` in per-member URL prefixes. |
| 1 | mac_addr | string | `str` | MAC in switch-native format (e.g. `001db3-b70e00`). |
| 2 | system_name | string | `str` | Sysname. If empty, the applet inserts a literal `" "` placeholder. |
| 3 | device_type | string | `str` | Device model string, e.g. `J9021A`. May be empty (triggers the space-substitution branch). |
| 4 | status | string | `str` | Operational status; `Member Up` is the accepted value (`StackControl.java:386`). Other values cause the member to be skipped from the list. |

## Example request

```
GET /cgi/get_members HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/stacking__get_members.response.txt` (live-captured
2026-04-23, 2 bytes, SHA256 `75a11da44c802486bc6f65640aa48a730f0f684c5c07a42ba3cd1735eb3fb070`).

Contents (bytes): `\n\n` — just two LFs. An empty member list.

Hypothetical populated response on a 3-member stack:

```
1~001db3-aa0001~Lab-SW1~J9021A~Member Up
2~001db3-aa0002~Lab-SW2~J9021A~Member Up
3~001db3-aa0003~Lab-SW3~J9021A~Missing
```

## Pydantic sketch

```python
from pydantic import BaseModel


class Member(BaseModel):
    switch_num: int
    mac_addr: str
    system_name: str
    device_type: str
    status: str


class GetMembersResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    members: list[Member]
```

## Notes & caveats

- **Stacking disabled on this switch (`no stack` in CONFIG.pcc line 148).**
  The live fixture is empty (`\n\n`). **Needs live capture on a stacked
  commander** to verify the per-line byte layout, in particular the
  separator handling when `device_type` is truly blank.
- **Empty-field handling is subtle.** The parser uses
  `StringTokenizer(line, "~", true)` so separator tokens are returned.
  When the parser sees a `~` where it expected a data token (i.e. two
  consecutive `~~`), it substitutes `" "` and skips one extra
  token. Python parsers should treat the line as raw `str.split("~")`
  and handle empty strings naturally rather than replicating the
  Java walker.
- **Status filter.** `StackControl.loadList` skips every line whose
  status is not `Member Up` (`:386-389`). `MemberCandidateList` keeps
  all records but uses them for different purposes (stack operations).
- **Called by two classes.** `StackControl.loadList` populates the
  top-bar member-switcher choice; `MemberCandidateList.loadList(1)`
  populates the left-hand list of the add/remove panel and feeds the
  parser-comparison logic in `processResult` (`:808-838`).
