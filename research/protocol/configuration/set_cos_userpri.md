# set_cos_userpri

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:**
`research/mirror/2026-04-23/configuration/cos_user1.html:31-38`
(`<form name=ip target=wrkpg action="../cgi/cosuserf">` with hidden
`action`, `addr` text field, and `ap` policy select).
`research/mirror/2026-04-23/configuration/cos_user2.html:6-15`
(`pr` priority select, used when `ap=2`).
`research/mirror/2026-04-23/configuration/cos_user3.html:4-16`
(Add/Replace/Delete buttons setting `action` and submitting).
Sub-tab key: `qos` / `ippr`.

## HTTP contract

- **Method:** GET
- **URL template:**
  `/cgi/cosuserf?action={Add|Replace|Delete}&addr={ipv4}&ap={1|2|3}&pr={0-7|255}&dscp={0-63|255}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | action | `Add` / `Replace` / `Delete` | yes | Set by the button. |
  | addr | IPv4 dotted-quad | yes | Device IP. |
  | ap | `1` / `2` / `3` | yes | Apply Policy: 1 = No Override, 2 = 802.1P, 3 = DSCP. |
  | pr | 0..7 or 255 | conditional | 802.1p priority when `ap=2`. |
  | dscp | 0..63 or 255 | conditional | DSCP codepoint when `ap=3`. The cos_user1 frame does not include a `dscp` select on this firmware (only cos_user2a which is not mirrored). **Needs live capture for `ap=3`.** |

- **Request body:** none (GET).
- **Response body:** **not live-tested.**

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| action | `action` | `Add`/`Replace`/`Delete` | enum | |
| address | `addr` | IPv4 dotted-quad | `IPv4Address` | |
| policy_mode | `ap` | `1`/`2`/`3` | enum | |
| priority_8021p | `pr` | integer | `int \| None` | Only when policy_mode=8021P. |
| dscp | `dscp` | integer | `int \| None` | Only when policy_mode=DSCP. |

## Example request

Add DSCP-46 entry for 10.0.0.5:
```
GET /cgi/cosuserf?action=Add&addr=10.0.0.5&ap=3&dscp=46 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Delete entry for 10.0.0.5:
```
GET /cgi/cosuserf?action=Delete&addr=10.0.0.5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from enum import IntEnum
from ipaddress import IPv4Address
from typing import Literal
from pydantic import BaseModel


class ApplyPolicy(IntEnum):
    NO_OVERRIDE = 1
    P_8021 = 2
    DSCP = 3


class SetCosUserPriRequest(BaseModel):
    action: Literal["Add", "Replace", "Delete"]
    address: IPv4Address
    policy_mode: ApplyPolicy
    priority_8021p: int | None = None
    dscp: int | None = None
```

## Notes & caveats

- **Two sibling frames.** `cos_user1` holds `ip` (the main form);
  `cos_user2` holds `ipdscp` (the priority select for 802.1p
  mode). The button frame `cos_user3` submits only `cos_user1.ip`.
  Cross-frame merging is likely server-side (similar quirk to
  `set_cos_appt`). Mark as unknown.
- **Related:** `get_cos_userpri`.
