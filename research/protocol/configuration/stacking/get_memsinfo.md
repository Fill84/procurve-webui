# get_memsinfo

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** `StackControl.java:67-97` — URL built at line 71
(`new URL(getCodeBase(), "../cgi/get_memsinfo")`). Parser reads until an
empty line, keeps the **last** non-empty line, then parses its first
tilde-delimited token as an integer member count (`:95`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(frameset hosting the StackControl applet).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_memsinfo`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, single line (may be followed by blank
  lines), tilde-delimited. No `OK~` sentinel.

  Wire layout (inferred from parser at `StackControl.java:95-103`):
  ```
  <member_count>~<member0_id>~<tokX>~<tokY>~<tokZ>~<member1_id>~...
  ```
  The first token is the member count `N` as an integer. The rest is
  `N+1` groups of **four tokens each** (member index 0 is the commander
  itself). The parser only keeps the first token of each group
  (`object2 = string3.substring(0, string3.indexOf("~"))` at `:100`) and
  skips three subsequent `~`-delimited fields (`:101-103`). The
  semantics of the three skipped tokens per member are not explicit in
  the decompiled code.

  **Observed on our non-stacked switch** (fixture
  `research/fixtures/stacking__get_memsinfo.response.txt`):
  ```
  0~0~001db3-b70e00~HP2810_01~
  ```
  = 30 bytes, trailing `\n\n`. That's `member_count=0`, then one group
  of four fields for the commander itself: `0` (index), `001db3-b70e00`
  (MAC), `HP2810_01` (system name), empty string.

- **Success indicator:** First token parses as a non-negative integer.
- **Error indicators:** First token is not numeric (the Java code would
  throw `NumberFormatException` at `:95`; not caught explicitly).

## Field reference

| idx within group | token | wire type | python type | notes |
|---|---|---|---|---|
| 0 | member_index | integer-as-string | `int` | `0` for the commander slot, `1..15` for additional members. |
| 1 | member_mac | string | `str` | MAC address, typically `xxxxxx-xxxxxx` format. |
| 2 | system_name | string | `str` | Switch's self-reported system name. |
| 3 | (unknown) | string | `str` | Empty on our capture. Possibly status or role. **Needs live capture.** |

## Example request

```
GET /cgi/get_memsinfo HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/stacking__get_memsinfo.response.txt` (live-captured
2026-04-23, 30 bytes, SHA256 `bc8f3f27c8c916141753b737fcf1c157f07928ef1c57ddf6617d1a6bc0ffedcd`).

Contents (bytes):
```
0~0~001db3-b70e00~HP2810_01~
```
followed by two `\n` bytes.

## Pydantic sketch

```python
from pydantic import BaseModel


class MemberInfo(BaseModel):
    member_index: int
    mac_address: str
    system_name: str
    extra: str = ""   # unknown trailing token


class GetMemsinfoResponse(BaseModel):
    member_count: int
    members: list[MemberInfo]
```

## Notes & caveats

- **Stacking disabled on this switch (`no stack` in CONFIG.pcc line 148).**
  The fixture captured with `member_count=0` plus one commander-self
  record. The shape of the response when `member_count > 0` is inferred
  from the parser loop at `StackControl.java:99-137` — each additional
  member contributes another `ID~field1~field2~field3~` group, but the
  exact content of those three trailing fields has not been verified
  on a live stacked setup. **Needs live capture on a stacked commander.**
- **No newline delimiter between records.** Everything is one long
  `~`-separated string on a single line; record boundaries are
  positional (every 4 tokens = one member, after the leading count).
- **Used by StackControl's `getTest()` method** to seed a second round
  of per-member `get_applet_length` polls. Not called in the normal
  render path on non-stacked switches.
