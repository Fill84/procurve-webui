# set_members

**Tab:** configuration (Stacking subsystem)
**Kind:** write
**Source in applet:** `MemberCandidateList.java:713-799` (inside the
`pswd_dlg` branch of `processResult`). URL built at line 763
(`new URL(getCodeBase(), "../cgi/set_members" + queryString)`). The
query string is assembled by concatenation (`:727-760`) from three
ordered segments: `?addrs=<csv>`, `&nums=<csv>`, `&pass=<password>`.
Response parser at `:774-783` reads lines until empty; if the first
`~`-delimited token is `error`, the second is displayed in a
`StackDialog`.

**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(applet-driven; no static form backs this operation).

## HTTP contract

- **Method:** GET (all mutations in the stacking applet are GET with
  query-string args)
- **URL template:** `/cgi/set_members?addrs=<mac_csv>&nums=<num_csv>&pass=<password>`
- **Query params (byte-exact construction order):**

  | key | value shape | required | description | source |
  |---|---|---|---|---|
  | `addrs` | comma-separated MAC addresses with a **trailing comma** | yes | The MAC of each candidate to promote into the stack, in switch-native format (e.g. `001db3-aa0001`). Built at `:727-732` as `?addrs=` + `mac,` repeated, so the final value always ends in `,`. | `MemberCandidateList.java:727-732` |
  | `nums` | comma-separated integers 0..15 with a **trailing comma** | yes | The zero-based slot index to assign each MAC to. One number per MAC, in the same order. The applet scans `switch_number_bs` (a `BitSet` of in-use slots) and picks the next free index per candidate. Built at `:733-755`. | `MemberCandidateList.java:733-755` |
  | `pass` | raw string (possibly empty) | yes | Manager password for the candidate switches. If the user left the password field empty, `&pass=` is emitted with no value. No URL-encoding is applied. Built at `:756-760`. | `MemberCandidateList.java:756-760` |

- **Request headers:** none beyond standard.
- **Request body:** none (GET only).
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, possibly multi-line, tilde-delimited.
  Each line's first token is checked against the literal `error`; when
  matched, the second token is a human-readable error message. On
  success the applet does not consume any specific sentinel; it merely
  exits the read loop and re-polls `get_members` / `get_candidates`
  to refresh the UI (`:793-794`).

- **Success indicator:** Every line's first `~`-token is not `error`.
  An empty body also counts as success (the `while` loop simply exits).
- **Error indicators:** Any line whose first token is literally `error`.

## Field reference

Request — see the query-params table above. Construction details that
MUST be preserved byte-exactly:

- Query starts with literal `?` (single question mark).
- `addrs` comes first, `nums` second, `pass` last — always in that order.
- `addrs` value is `mac1,mac2,mac3,` — **trailing comma**, no space.
- `nums` value is `n1,n2,n3,` — **trailing comma**, no space.
- Keys are separated by `&`; values are raw (no URL-encoding applied
  by the applet's string concatenation).
- An empty password yields the literal suffix `&pass=` with nothing
  after it. The applet emits `&pass=` unconditionally
  (`:756`) then conditionally appends the password if non-empty
  (`:758-760`).

Response — same per-line `error`/OK convention as other stacking write
CGIs:

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| sentinel | line[0], `~`-token 0 | string | `str` | `error` on failure; any other value on success. |
| message | line[0], `~`-token 1 | string | `str` | Human-readable English error message; only present on error lines. Shown in `StackDialog("ERROR: " + msg)`. |

## Example request

**Add two candidates (MACs `001db3-aa0001` and `001db3-aa0002`) as
stack members 1 and 2, password `labpass`** (hypothetical — no live
test of writes):

```
GET /cgi/set_members?addrs=001db3-aa0001,001db3-aa0002,&nums=1,2,&pass=labpass HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

**Add one candidate with no password:**

```
GET /cgi/set_members?addrs=001db3-aa0001,&nums=1,&pass= HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Byte-exact construction (`MemberCandidateList.java:727-763`):

```
?addrs=<mac>,<mac>,...,&nums=<int>,<int>,...,&pass=<raw>
```

The trailing comma in `addrs` and `nums` is an artefact of the
while-loop string build (`... + mac + ","`) and MUST be preserved.

## Example response

Prepared example only — no live test of this write operation.

Success (line loop reads until empty; a single blank line satisfies
the success path):

```

```
(empty body, or any body where no line begins `error~`)

Error (inferred from parser at `MemberCandidateList.java:776-781`):

```
error~Invalid manager password for 001db3-aa0001.
```

Note: the applet reads **lines in a loop**, so a single response may
contain multiple `error~<msg>` lines (one per failing candidate). The
applet only surfaces the first via `StackDialog`.

## Pydantic sketch

```python
from pydantic import BaseModel


class SetMembersRequest(BaseModel):
    # Byte-exact: the Python client must emit trailing commas on
    # `addrs` and `nums`, in the order addrs, nums, pass.
    mac_addrs: list[str]
    switch_nums: list[int]  # 1..15, same length as mac_addrs
    manager_password: str = ""


class SetMembersError(BaseModel):
    message: str


class SetMembersResponse(BaseModel):
    ok: bool
    errors: list[SetMembersError] = []
```

## Notes & caveats

- **Switch has stacking disabled (`no stack` in CONFIG.pcc line 148).**
  We do not live-test writes; **needs live capture on a stacked
  commander** to confirm the byte-for-byte response shape on both
  success and error paths.
- **Trailing commas.** `addrs=a,b,` and `nums=1,2,` — the applet's
  `while` loop appends `mac + ","` / `n + ","` without trimming. Both
  values always end in a comma (even for a single element: `addrs=a,`).
  A Python client MUST reproduce this to avoid byte divergence.
- **No URL-encoding.** `MemberCandidateList` uses raw string
  concatenation (`"&pass=" + password`). A password containing `&`
  or `=` would corrupt the request. The applet's password dialog
  restricts input to printable ASCII but does not actively filter
  URL-reserved characters.
- **Password is sent in the clear** (as URL query-string). Anyone who
  can see the request sees the password. This is a protocol flaw, not
  a Python bug; noted here for security awareness. Phase 1 Python
  should mirror the protocol exactly but warn the user that HTTP
  Basic auth + cleartext password in URL both expose credentials.
- **Commander MAC check.** Before building the URL, the applet rejects
  attempts to add the commander's own MAC (`:293-300`) with an
  in-applet error dialog. Python should mirror this client-side guard.
- **Slot allocation.** The applet consults `switch_number_bs` (slots
  0..15, where in-use slots are bits) to pick the next free number
  (`:714-724`). If all 16 slots are full it errors before building the
  URL (`:739-746`). A Python client doing the same orchestration
  must pre-query `get_members` to compute occupancy.
- **Follow-up cleanup.** After `set_members` returns, the applet
  polls `get_members` and checks that each requested MAC now shows
  `Member Up` status (`:800-838`). Any MAC whose status is *not*
  `Member Up` triggers a second CGI call to `delete_members` to roll
  back (`:842-863`). Phase 1 Python should mirror this cleanup
  behaviour to avoid orphaned "stuck" slots on partial failures.
