# set_cos_vlanpri

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_vlan1.html:17`
(`<form name=vlanpr target=wrkpg action=../cgi/cosvlanf>`), with
the `dscp` select at lines 22-87 and the priority select at
cos_vlan2.html:17-27. Submit is triggered from cos_vlan3.html's
`Modify` button which calls `parent.vlan1.vlanpr.submit()`.
Sub-tab key: `qos` / `vlanPriority`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/cosvlanf?dscp={0-63|255}&pr={0-7|255}&indeces={vlan_id}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | dscp | 0..63 or 255 | yes | DSCP codepoint. `255` = Disabled (no DSCP policy). Source: cos_vlan1.html:22. |
  | pr | 0..7 or 255 | yes | 802.1p priority. `255` = No Override. Source: cos_vlan2.html:17. |
  | indeces | integer | yes | VLAN ID to modify. Selected in the GenericList applet in cos_vlan0.html; appended by the applet's `submitForm()` as `indeces=<vlanId>`. Note the misspelling. |

  Cross-field rule (cos_vlan1.html:8-10, cos_vlan2.html:6-10):
  setting a non-255 `dscp` forces `pr` back to default in the
  sibling frame; setting a non-255 `pr` forces `dscp` similarly.
  The two values are mutually exclusive in practice.

- **Request body:** none (GET).
- **Response body:** **not live-tested.**

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| dscp | `dscp` | integer | `int` | 0..63 or 255. |
| priority_8021p | `pr` | integer | `int` | 0..7 or 255. |
| vlan_id | `indeces` | integer | `int` | |

## Example request

Assign DSCP 46 to VLAN 1:
```
GET /cgi/cosvlanf?dscp=46&pr=255&indeces=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Assign 802.1p priority 5 to VLAN 1:
```
GET /cgi/cosvlanf?dscp=255&pr=5&indeces=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Clear VLAN 1 priority:
```
GET /cgi/cosvlanf?dscp=255&pr=255&indeces=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from pydantic import BaseModel, model_validator


class SetCosVlanPriRequest(BaseModel):
    vlan_id: int  # wire: indeces
    dscp: int = 255  # 0..63 or 255
    priority_8021p: int = 255  # 0..7 or 255

    @model_validator(mode="after")
    def mutually_exclusive(self) -> "SetCosVlanPriRequest":
        if self.dscp != 255 and self.priority_8021p != 255:
            raise ValueError("set only one of dscp / priority_8021p at a time")
        return self
```

## Notes & caveats

- **Form `action` attribute omits quotes.** cos_vlan1.html:17
  reads `action=../cgi/cosvlanf` (no quotes). Browsers tolerate
  this. No functional difference.
- **Related:** `get_cos_vlanpri`.
