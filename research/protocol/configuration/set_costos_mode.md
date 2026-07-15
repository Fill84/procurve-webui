# set_costos_mode

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_tos.html:25`
(`<FORM name=cos1 action=../cgi/costos>`), with the
`hpSwitchCosTosConfigMode` select at lines 29-33 and a hidden
`indeces=0` input at line 39.
Sub-tab key: `qos` / `typofs` (Type Of Service).

> **Re-mirrored 2026-07-15 (closes audit F2):** the QoS sub-pages are now
> captured in `research/mirror/2026-07-15/configuration/` (22 pages,
> including `cos_app1/5/5a.html` which no doc had cited). Verified against
> the live HTML: CGI endpoint paths, submitted-form field names, and every
> `<select>` value domain (dscp 0-63, 802.1p 0-7, `255` sentinel where
> offered, apply-policy 1-3, app id 0-58, ToS mode 1-3) match this doc and
> the implementation. Still open: the multi-frame submit orchestration —
> the plain HTML form for cosappf/cosuserf/cosvlanf carries only a subset
> of the documented params (sibling frames hold the rest in unsubmitted
> forms, e.g. both pickers in `cos_app5(.a).html` are named `pr`); the
> applet merged them at submit time (GenericList `params`/`indeces`
> mechanism). Response bodies remain uncaptured.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/costos?hpSwitchCosTosConfigMode={1|2|3}&indeces=0`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | hpSwitchCosTosConfigMode | `1`/`2`/`3` | yes | `1` = Disabled, `2` = IP Precedence, `3` = Differential Services. |
  | indeces | literal `0` | yes | Hidden field (cos_tos.html:39). |

- **Request body:** none (GET).
- **Response body:** **not live-tested.**
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| mode | `hpSwitchCosTosConfigMode` | `1`/`2`/`3` | enum | |
| indeces | `indeces` | literal `0` | `int = 0` | |

## Reading the current value

No dedicated CGI. cos_tos.html:10 contains:
```
document.cos1.hpSwitchCosTosConfigMode.options[1 - 1].selected = true;
```
i.e. a server-side template substitutes the current mode into the
`options[<mode> - 1].selected = true` expression. On this fixture
the literal `1 - 1` evaluates to option index 0 (Disabled). Python
scraper regex should match `options\[(\d+) - 1\]\.selected`.

## Example request

Enable Differential Services mode:
```
GET /cgi/costos?hpSwitchCosTosConfigMode=3&indeces=0 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel


class CosTosMode(IntEnum):
    DISABLED = 1
    IP_PRECEDENCE = 2
    DIFFSERV = 3


class SetCosTosModeRequest(BaseModel):
    mode: CosTosMode
    # indeces is always 0 and emitted by the serialiser
```

## Notes & caveats

- **Global toggle.** This CGI sets the switch-wide ToS
  interpretation mode. Individual DSCP policies live in
  `set_diffserv` and `set_dscptable`.
- **No corresponding read CGI.** Only HTML scraping.
