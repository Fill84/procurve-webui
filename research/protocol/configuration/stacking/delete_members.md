# delete_members

**Tab:** configuration (Stacking subsystem)
**Kind:** write
**Source in applet:** Two call sites in `MemberCandidateList.java`,
both using identical URL construction:
- `MemberCandidateList.java:311-367` — user-initiated "Remove Member"
  button. URL built at line 337
  (`new URL(getCodeBase(), "../cgi/delete_members" + queryString)`);
  query is `?nums=<n1>,<n2>,...,` with a trailing comma (built at
  `:328-335`).
- `MemberCandidateList.java:841-864` — automatic rollback after a
  failed `set_members` (any candidate whose post-add status is not
  `Member Up` is removed). URL built at `:845`, query built at
  `:842-843` with identical shape.

Response parser at `:350-351` (and `:857-858`) reads lines until
empty; the content of each line is discarded. There is no explicit
error handling — the applet blindly accepts whatever the CGI returns
and re-polls `get_members` afterwards (`:360-361`).

**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
(applet-driven; no static form backs this operation).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/delete_members?nums=<num_csv>`
- **Query params (byte-exact construction order):**

  | key | value shape | required | description | source |
  |---|---|---|---|---|
  | `nums` | comma-separated switch-numbers with a **trailing comma** | yes | Slot indices (1..15) of the members to remove. Built as `?nums=` + `<n>,` repeated. Always ends in `,` even for a single member. | `MemberCandidateList.java:328-335` |

- **Request headers:** none beyond standard.
- **Request body:** none (GET only).
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. Parser reads lines until an empty
  line (`while ((string3 = bufferedReader.readLine()) != null && string3.length() > 0)`),
  does nothing with each line, then exits. There is **no sentinel
  inspection** — the applet neither checks for `error~` nor consumes
  an `OK~` prefix. Based on convention with sibling write CGIs
  (`set_stack_cfg`, `set_members`) the success shape is probably empty
  or `OK~`, and the error shape probably starts with `error~<msg>`,
  but the applet does not use this and so it is not enforced.

- **Success indicator:** HTTP 200; applet ignores body content.
- **Error indicators:** HTTP non-200; any IOException during read.
  Body-level error shape is not parsed by the applet — a Python client
  *should* still inspect it for `error~<msg>` as a defensive measure.

## Field reference

Request — see the query-params table above. Construction details that
MUST be preserved byte-exactly:

- Query starts with literal `?`.
- Single key: `nums`.
- Value is `n1,n2,n3,` — **trailing comma**, no space.
- Numbers are decimal integers with no zero-padding (Java's
  `Integer.toString` output via `String` concatenation).

Response — byte-exact body is not inspected. If we choose to inspect
it defensively in Phase 1 Python, the convention would be:

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| sentinel | line[0], `~`-token 0 | string | `str` | `error` on failure; anything else on success. Not inspected by the Java applet, but inferred convention. |
| message | line[0], `~`-token 1 | string | `str` | Human-readable English error; only present on error. |

## Example request

**Remove member 2 from the stack** (hypothetical — no live test of
writes):

```
GET /cgi/delete_members?nums=2, HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

**Remove members 2, 5, and 7:**

```
GET /cgi/delete_members?nums=2,5,7, HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Byte-exact construction (`MemberCandidateList.java:328-337`):

```
?nums=<int>,<int>,...,
```

The trailing comma is an artefact of the while-loop append
(`string = string + (String)object + ","`) and MUST be preserved.

## Example response

Prepared example only — no live test of this write operation.

Success (applet does not inspect the body; any HTTP 200 with an
eventual empty-line terminator satisfies the success path):

```

```
(empty body)

Error (inferred — applet does not parse but Python may):

```
error~Invalid member number 17.
```

## Pydantic sketch

```python
from pydantic import BaseModel


class DeleteMembersRequest(BaseModel):
    # Byte-exact: emit as `?nums=1,2,3,` with trailing comma.
    switch_nums: list[int]


class DeleteMembersResponse(BaseModel):
    ok: bool
    # The applet never inspects these; Python may surface them
    # defensively.
    error_message: str | None = None
```

## Notes & caveats

- **Switch has stacking disabled (`no stack` in CONFIG.pcc line 148).**
  We do not live-test writes; **needs live capture on a stacked
  commander** to confirm whether the body is empty, `OK~`, or carries
  a per-slot ack. The applet's blind-consume design means the wire
  shape has been undocumented in practice for 20+ years.
- **Trailing comma.** `nums=1,2,` — must be preserved. Even for a
  single element: `nums=2,`. See `MemberCandidateList.java:332`:
  `string = string + (String)object + ","`.
- **No URL-encoding.** Integer values are ASCII digits; no encoding
  issue arises in practice, but a Python client should not invoke
  `quote_plus` on the numbers (it's a no-op anyway).
- **No response-body parsing in the applet.** A Python client is
  free to parse `error~<msg>` defensively and surface it, since doing
  so will never cause divergence from the applet's behaviour (the
  applet ignores body content). Recommended.
- **Used in two flows:**
  1. **Explicit user removal** (`:311`): triggered by the "Remove
     Member" button with one or more user-selected member rows.
  2. **Automatic rollback** (`:841`): after `set_members` completes,
     the applet verifies each requested MAC reached `Member Up` status
     via `get_members`; any MAC that did not reach that state triggers
     a `delete_members` call to free its slot. Python must replicate
     this rollback sequence to avoid orphaned stuck slots.
- **Followed by `Thread.sleep(1000)`** in the explicit-removal flow
  (`:355`) before re-polling `get_members` and `get_candidates`. The
  switch apparently needs ~1 second to propagate the removal. Python
  should apply a similar settle delay (or poll with exponential
  backoff) before trusting the re-query.
