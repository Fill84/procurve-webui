# set_stack_cfg

**Tab:** configuration (Stacking subsystem)
**Kind:** write
**Source in applet:** `StackConfig.java:436-558` (`doConfigChanges`) —
builds a `?key=value&key=value...` query string by diffing the current
form state against the last-loaded `get_stack_cfg` record, then opens
`new URL(getCodeBase(), "../cgi/set_stack_cfg" + string)` at line 527
(dev) or `new URL(this.setUrlStr + string)` at line 530 (production).
Response is read single-line and split on `~`; if the first token is
`error` the second token becomes the error-dialog text
(`:543-551`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/sstart.html`
has a bare-minimum HTML form (`action=../cgi/set_stack_cfg`) used only
for the "Disable stacking" path (`sf=2`); the full multi-field form is
applet-driven.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/set_stack_cfg?<k=v pairs joined by &>`
- **Query params:** every parameter is **optional** and only emitted
  if its form value differs from the last-loaded state. The applet
  builds the query in this order, inserting `&` between fields it
  decides to include:

  | key | values | meaning | source |
  |---|---|---|---|
  | `dp` | `1`=enable, `2`=disable | Discovery-protocol admin state | `StackConfig.java:442, 445` |
  | `di` | integer | Discovery interval in seconds (raw `interval_tf.getText()`) | `:451` |
  | `sf` | `1`=enable, `2`=disable | Stacking feature state | `:458, 464` |
  | `cs` | `1`=create, `2`=stop creating | "Create Stack" commander toggle | `:471, 478` |
  | `sn` | string | Stack name (raw `stack_name_tf.getText()`) — only emitted when `cs` is | `:472, 479` |
  | `js` | `1`=join, `2`=stop joining | "Join Stack" member toggle | `:486, 493` |
  | `ma` | string | Commander MAC address (raw `command_mac_addr_tf.getText()`) — only emitted when `js` is | `:487, 494` |
  | `ag` | `1`=enable, `2`=disable | Auto-grab (commander-only) | `:501, 507` |
  | `aj` | `1`=enable, `2`=disable | Auto-join (member-only) | `:514, 519` |

- **Request headers:** none beyond standard.
- **Request body:** none (GET only).
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, **single line**, tilde-delimited.
  On success the body is any line whose first token is **not** the
  literal `error`. The applet does not inspect success payloads further
  (`StackConfig.java:546`). Upon success the applet re-polls
  `get_stack_cfg` to refresh the displayed state (`:430`).

  On error the first token is literally `error` and the second token
  is a human-readable message shown in a `StackDialog("ERROR: " + msg)`
  dialog (`:548-549`).

- **Success indicator:** First token is not the literal string `error`.
- **Error indicators:** First token equals `error`.

## Field reference

Request — see the query-params table above. All values are transmitted
**un-encoded** (the Java code uses raw string concatenation, not
`URLEncoder.encode`). For `sn` (stack name) and `ma` (MAC) this means
characters like space would be sent literally, which would break URL
parsing; however the applet's TextField widgets restrict input to
printable ASCII + digits respectively.

Response:

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| sentinel | 0 | string | `str` | `error` on failure; any other token on success. |
| message | 1 | string | `str` | Human-readable English error message; only present on the error path. |

## Example request

**Disable stacking entirely** (matches the `sstart.html` static form):

```
GET /cgi/set_stack_cfg?sf=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

**Enable stacking, set this switch as commander, name it `Lab`,
turn on auto-grab** (hypothetical; diff from a stock disabled state):

```
GET /cgi/set_stack_cfg?sf=1&cs=1&sn=Lab&ag=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

**Join an existing stack as member with commander MAC
`001db3-b70e00`** (hypothetical):

```
GET /cgi/set_stack_cfg?js=1&ma=001db3-b70e00 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Byte-exact construction (`StackConfig.java:442-520`): the query starts
with literal `?`, each subsequent included key is prefixed with `&`,
and each key is followed immediately by `=` and the value. No
URL-encoding. Key ordering is fixed by the applet's if-chain: `dp`, `di`,
`sf`, `cs`, `sn`, `js`, `ma`, `ag`, `aj`.

## Example response

Prepared example only — no live test of this write operation.

Success (observed shape from the sister `get_stack_cfg` endpoint;
success path in Java consumes no tokens beyond the first):

```
OK~
```

Error (inferred from parser at `StackConfig.java:544-550`):

```
error~Stacking must be enabled before creating a stack.
```

## Pydantic sketch

```python
from typing import Literal
from pydantic import BaseModel, Field


class SetStackCfgRequest(BaseModel):
    dp: Literal[1, 2] | None = None
    di: int | None = None
    sf: Literal[1, 2] | None = None
    cs: Literal[1, 2] | None = None
    sn: str | None = None
    js: Literal[1, 2] | None = None
    ma: str | None = None
    ag: Literal[1, 2] | None = None
    aj: Literal[1, 2] | None = None


class SetStackCfgResponse(BaseModel):
    ok: bool
    error_message: str | None = None
```

## Notes & caveats

- **Switch has stacking disabled (`no stack` in CONFIG.pcc line 148).**
  We do not live-test writes and cannot confirm behaviour on this
  switch without flipping the global flag first. **Needs live capture
  on a stacked setup.**
- **No URL-encoding.** Values are concatenated raw. For `sn` (stack
  name) and `ma` (MAC), any characters the applet's form allows but
  the URL parser rejects would corrupt the request. Python clients
  should apply their own encoding only if the applet-rejected character
  set is ever relaxed; for byte-exact parity with the applet, emit raw.
- **Diff-only emission.** The applet only emits fields whose form value
  differs from the last-loaded state — a no-op submit produces a URL
  of exactly `?` (length 1) and the applet short-circuits without
  sending (`StackConfig.java:522-524`). Python clients should either
  replicate this diffing or send only changed fields explicitly.
- **`sn` without `cs` / `ma` without `js` is never emitted.** They are
  only included inside the `cs=...` and `js=...` branches respectively,
  preceded by `&sn=` / `&ma=` immediately after the toggle.
- **URL-construction modes** mirror `get_stack_cfg`: dev-sandbox uses
  `../cgi/set_stack_cfg` relative to codebase; production reads the
  absolute URL from the `setURL` applet param. Our mirror does not
  supply `setURL` on `stack_config.html` — the bare path
  `/cgi/set_stack_cfg` is the canonical Python target.
