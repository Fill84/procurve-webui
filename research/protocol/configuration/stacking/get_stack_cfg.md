# get_stack_cfg

**Tab:** configuration (Stacking subsystem)
**Kind:** read
**Source in applet:** `StackConfig.java:125-164` — URL built at line 128
(`new URL(getCodeBase(), "../cgi/get_stack_cfg")` when `linuxFlag` is true,
otherwise `new URL(this.getUrlStr)` from the `getURL` applet param).
Response is read one line, split on `~`, and eight tokens are consumed
in order (`StackConfig.java:142-150`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/stack_config.html`
is the frameset; the stacking config applet (`StackConfig.class`) is the
consumer. No applet param for this endpoint exists in the mirrored
pages of our non-stacked switch (see caveats).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_stack_cfg`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** `Content-Type: text/html` was
  observed on our switch only because the endpoint 404'd; the successful
  shape is documented below from the Java code.
- **Response body:** plain text, **one single line**, tilde-delimited.
  No `OK~` sentinel is consumed on the success path. The applet reads
  exactly eight `~`-separated tokens, in order:

  ```
  <stack_admin_state>~<disc_admin_state>~<disc_interval>~<stack_feature_state>~<stack_name>~<command_mac_addr>~<auto_grab_state>~<auto_join_state>
  ```

  On error (inferred from `doConfigChanges` at `StackConfig.java:544-551`
  where the same parser shape is reused): first token is the literal
  string `error` and the second token is a human-readable message.

- **Success indicator:** Eight well-formed tilde-delimited tokens on
  line 1. First token is one of `commander` / `member` / other
  literal strings compared at `StackConfig.java:273, 318, 348, 376`.
- **Error indicators:** HTTP non-200 (we observed HTTP 404 on a
  non-stacked switch — see caveats), or first token equals `error`.

## Field reference

Response tokens (positional):

| idx | token | wire type | python type | semantic |
|---|---|---|---|---|
| 0 | stack_admin_state | string | `Literal["commander","member","candidate","disable"]` | Role of this switch in the stack. `StackConfig` branches on literal matches to `commander` and `member`; anything else is treated as "not in a stack". |
| 1 | disc_admin_state | string | `Literal["enable","disable"]` | Discovery protocol admin state. Compared to `enable` at `StackConfig.java:212`. |
| 2 | disc_interval | integer-as-string | `int` | Discovery interval (seconds). Placed verbatim into the `interval_tf` TextField. |
| 3 | stack_feature_state | string | `Literal["enable","disable"]` | Global stacking feature toggle. Compared at `:237`. |
| 4 | stack_name | string | `str` | Stack name (commander-only). Blank for non-commanders. |
| 5 | command_mac_addr | string | `str` | Commander MAC address (member-only). Format is switch-defined; TextField is 13 chars wide (`:309`). |
| 6 | auto_grab_state | string | `Literal["enable","disable"]` | Auto-grab toggle (commander-only). Compared at `:349`. |
| 7 | auto_join_state | string | `Literal["enable","disable"]` | Auto-join toggle (member-only). Compared at `:377`. |

## Example request

```
GET /cgi/get_stack_cfg HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Prepared example only — no live fixture. On this switch the endpoint
returned HTTP 404 (stacking feature disabled, see caveats).

Hypothetical response on a commander:

```
commander~enable~60~enable~MyStack~~enable~disable
```

Hypothetical response on a member:

```
member~enable~60~enable~~001db3-b70e00~disable~enable
```

## Pydantic sketch

```python
from typing import Literal
from pydantic import BaseModel


class StackCfg(BaseModel):
    stack_admin_state: Literal["commander", "member", "candidate", "disable"]
    disc_admin_state: Literal["enable", "disable"]
    disc_interval: int
    stack_feature_state: Literal["enable", "disable"]
    stack_name: str = ""
    command_mac_addr: str = ""
    auto_grab_state: Literal["enable", "disable"] = "disable"
    auto_join_state: Literal["enable", "disable"] = "disable"


class GetStackCfgResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    cfg: StackCfg | None = None
```

## Notes & caveats

- **Switch has stacking disabled (`no stack` in CONFIG.pcc line 148).**
  On our 2810-24G `GET /cgi/get_stack_cfg` returns `HTTP/1.1 404 Not found`
  from `eHTTP v2.0` with a 10-byte HTML body. The fixture is intentionally
  **not captured** because the 404 body would be misleading. The success
  shape above is from `StackConfig.java:142-150`.
- **Needs live capture on a commander switch** to confirm the exact byte
  layout (separator of trailing empty tokens, whether `disc_interval`
  ever has a non-integer placeholder, MAC address format with or
  without `-`).
- **No `OK~` sentinel.** Unlike most write responses, the success path
  emits bare data with no leading token. The `error` prefix (inferred
  from the `set_stack_cfg` parser sharing this shape) is the only
  sentinel to look for.
- **Applet has two URL-construction modes** (`StackConfig.java:128`):
  dev-sandbox `linuxFlag=true` uses `../cgi/get_stack_cfg` relative to
  codebase; production reads the absolute URL from the `getURL` applet
  param. Our mirror does not supply `getURL` for the bare
  `stack_config.html` page (the page is pure frameset — see
  `research/mirror/.../configuration/stack_config.html`); live switches
  presumably serve this endpoint under `/cgi/` when stacking is on.
