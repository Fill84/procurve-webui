# get_applet_length

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** `StackControl.java:106-138` — URL built two ways:
- For the commander (n==0, `:107`):
  `new URL(getCodeBase(), "../cgi/get_applet_length")`.
- For each member (n>=1, `:115`):
  `new URL(getCodeBase(), "../sw" + memberId + "/cgi/get_applet_length")`
  (per-member pass-through path prefix).

Parser at `:126-131` reads lines until empty, tokenises each with the
default-whitespace `StringTokenizer`, and concatenates the first token
of every non-empty line followed by `~`. For n==0 the first token seeds
the accumulator; for n>=1 it is appended. Final return value shape:
`<len0>~<len1>~<len2>~...~` (one `~`-terminated integer per member
slot).
**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(frameset hosting StackControl). Used internally by `getTest()` to
seed per-member applet lengths before rendering the main stack UI.

## HTTP contract

- **Method:** GET
- **URL template:**
  - Commander: `/cgi/get_applet_length`
  - Member N: `/sw{N}/cgi/get_applet_length` (where N is the switch
    number returned by `get_memsinfo` at slot >=1)
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, typically a **single line**,
  whitespace-delimited (NOT `~`). The applet consumes only the first
  whitespace-delimited token of each non-empty line. The token is an
  integer — Java code uses it as `string + "~"` (string concatenation),
  so downstream callers parse it lazily as an int.

  Observed on our non-stacked switch (commander URL, fixture
  `research/fixtures/stacking__get_applet_length.response.txt`):
  ```
  150
  ```
  = 4 bytes (`150\n`). One integer token on one line.

- **Success indicator:** First non-empty line starts with an integer.
- **Error indicators:** HTTP non-200; or non-integer first token
  (would cause `NumberFormatException` downstream if the caller
  attempts int conversion; the Java code does not do this explicitly).

## Field reference

| idx | token | wire type | python type | notes |
|---|---|---|---|---|
| 0 | applet_length | integer-as-string | `int` | Likely the size (in bytes or units) of the per-member applet's state payload, used by `getTest()` to pre-allocate display resources. Exact semantic unit is not clear from decompiled code. Our commander returned `150`. |

## Example request

```
GET /cgi/get_applet_length HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

For member 1:
```
GET /sw1/cgi/get_applet_length HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/stacking__get_applet_length.response.txt`
(live-captured 2026-04-23, 4 bytes, SHA256
`9a7f91a861f59c0cb27f0af9323d158fdab7740d5e3c8016a60f4b04c0fc41e0`).

Contents (bytes):
```
150
```
followed by one `\n`.

## Pydantic sketch

```python
from pydantic import BaseModel


class GetAppletLengthResponse(BaseModel):
    applet_length: int
```

## Notes & caveats

- **Semantic meaning unclear.** The name "applet length" suggests a
  byte-count of either the per-member status payload or of the
  embedded sub-applet's data. The applet never uses the value for
  arithmetic — it just concatenates it into a `~`-separated string
  that `getTest()` returns. **Needs live capture on a stacked
  commander** with multiple members to see the full multi-slot shape.
- **Per-member URL path.** For member N (`>=1`), the URL is prefixed
  with `/sw{N}/cgi/` rather than `/cgi/`. This is the switch's
  pass-through mechanism where the commander proxies CGIs to a member
  via a URL prefix. Phase 1 Python must preserve this path pattern
  when talking to a commander about its members; on a standalone
  switch only the unprefixed `/cgi/get_applet_length` path is valid.
- **Whitespace-delimited, not `~`-delimited.** Like `get_cmd_name`,
  the single-token response uses default Java `StringTokenizer`.
  Python should use `line.split()[0]`.
- **Not user-facing.** This endpoint is an internal bootstrap detail
  for `StackControl.getTest()`. Phase 1 does not need to surface it
  to end users; it exists only for protocol completeness.
