# set_cos_appt

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:**
`research/mirror/2026-04-23/configuration/cos_app3.html:181`
(`<form name=fapp3 target=wrkpg action="../cgi/cosappf">`) —
contains the application select, the TCP/UDP radio, and a hidden
`action` input.
`research/mirror/2026-04-23/configuration/cos_app3a.html:3-5`
(`<form name=fapp3a target=wrkpg action="../cgi/cosappf">`) —
contains the `src` text box used when the application select is
"User defined".
`research/mirror/2026-04-23/configuration/cos_app4.html:22-26`
(`<form name=fap>`, not submitted directly; contains the policy-
select `ap`, used by cos_app6).
`research/mirror/2026-04-23/configuration/cos_app6.html:21-24`
(the Add/Replace/Delete buttons — they set `fapp3.action.value` to
`Add` / `Replace` / `Delete` and submit `fapp3`).
Sub-tab key in menu: `qos` / `appt`.

> **⚠ Ground-truth gap (audit F2, 2026-07-15):** this doc cites one or more
> `cos_*.html` mirror pages that are **not present** in
> `research/mirror/2026-04-23/configuration/` (only `cos_mainf.html` and
> `cos_menu.html` were captured; the per-subtab QoS pages were never
> mirrored and are not in git history). HTML-derived claims below are
> therefore unverifiable in-repo. Treat the wire contract as
> **experimental** until the QoS pages are re-mirrored or live-captured.

## HTTP contract

- **Method:** GET
- **URL template:**
  `/cgi/cosappf?action={Add|Replace|Delete}&app={app_id}&tcpudp={TCP|UDP}&src={port_number}&ap={1|2|3}&dscp={0-63|255}&pr={0-7|255}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | action | `Add` / `Replace` / `Delete` | yes | Set by the JS handler before form submit. Case-preserved (cos_app6.html:4,9,14). |
  | app | integer 0..58 | yes | Application select value. `0` = User defined; 1..58 = well-known services (see cos_app3.html's `services` array). |
  | tcpudp | `TCP` / `UDP` | yes | Radio button value (cos_app3.html:176,180). |
  | src | integer 1..65535 | required when `app=0` | Port number. Only used for "User defined"; for well-known apps, the switch uses the port from the lookup table. |
  | ap | `1`/`2`/`3` | yes | Apply Policy: `1` = No Override, `2` = 802.1P, `3` = DSCP (cos_app4.html:22-26). |
  | dscp | 0..63 or 255 | required when `ap=3` | DSCP codepoint. `255` = disabled. Value list from `cos_tosds.html:35-100` (same widget). |
  | pr | 0..7 or 255 | required when `ap=2` | 802.1p priority. `255` = no override. Value list from `cos_vlan2.html` and friends (`cos_user2.html:8-17`). |
  | dir | integer | conditional | Reset to `0` by `checkSettings()` (cos_app6.html:16-22) when `app != 0`. Purpose unverified — **needs live capture**. |

  Note: the three forms `fapp3`, `fapp3a`, `fap` sit in three
  different frames (app3, app3a, app4). On submit, cos_app6's JS
  calls `parent.app3.document.fapp3.submit()` — which submits only
  the `fapp3` form. The `src` and `ap` values from the other
  frames are not automatically merged into the single GET; they
  are read server-side from the other frames? **No — inspection of
  the JS shows no merging logic.** In practice this form likely
  relies on the browser maintaining a single-request state the
  switch correlates via cookies or prior visits. The exact wire
  shape is **unverified — needs live capture**.

- **Request headers:** none beyond standard.
- **Request body:** none (GET).
- **Response body:** **not live-tested.**
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| action | `action` | `Add`/`Replace`/`Delete` | enum | Set by the button. |
| app_id | `app` | integer | `int` | 0 = user-defined. |
| protocol | `tcpudp` | `TCP`/`UDP` | `Literal` | |
| port | `src` | integer 1..65535 | `int \| None` | Only when `app_id=0`. |
| policy_mode | `ap` | `1`/`2`/`3` | enum | NoOverride/8021P/DSCP. |
| dscp | `dscp` | integer | `int \| None` | Only when policy_mode=DSCP. |
| priority_8021p | `pr` | integer | `int \| None` | Only when policy_mode=8021P. |

## Example request

Add an entry: apply DSCP 46 (EF) to HTTP on TCP:
```
GET /cgi/cosappf?action=Add&app=21&tcpudp=TCP&ap=3&dscp=46 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Add a user-defined entry for TCP port 5060 with 802.1p priority 5:
```
GET /cgi/cosappf?action=Add&app=0&tcpudp=TCP&src=5060&ap=2&pr=5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from enum import IntEnum
from typing import Literal
from pydantic import BaseModel, model_validator


class ApplyPolicy(IntEnum):
    NO_OVERRIDE = 1
    P_8021 = 2
    DSCP = 3


class SetCosApptRequest(BaseModel):
    action: Literal["Add", "Replace", "Delete"]
    app_id: int  # 0 for user-defined
    protocol: Literal["TCP", "UDP"]
    port: int | None = None
    policy_mode: ApplyPolicy
    dscp: int | None = None  # 0..63 or 255
    priority_8021p: int | None = None  # 0..7 or 255

    @model_validator(mode="after")
    def consistency(self) -> "SetCosApptRequest":
        if self.app_id == 0 and self.port is None:
            raise ValueError("port required when app_id=0")
        if self.policy_mode == ApplyPolicy.DSCP and self.dscp is None:
            raise ValueError("dscp required for DSCP policy")
        if self.policy_mode == ApplyPolicy.P_8021 and self.priority_8021p is None:
            raise ValueError("priority_8021p required for 802.1p policy")
        return self
```

## Notes & caveats

- **Multi-frame form submit quirk.** The UI's QoS Application Type
  panel spans four sibling frames: app1 (title), app3 (application
  select), app3a (user-defined port), app4 (policy mode), app6
  (buttons). Only `fapp3` is actually submitted on click. The
  server must merge the other frames' state through session — or
  the `ap`, `dscp`, `pr`, `src` values never make it to the
  switch and the CGI accepts only `action + app + tcpudp`.
  **Needs live capture** to decide between these. Mark this a
  known unknown.
- **`fapp3.action.value` is a hidden input.** cos_app3.html:183:
  `<input type=hidden name="action">`; set by JS.
- **Related:** `get_cos_appt`.
