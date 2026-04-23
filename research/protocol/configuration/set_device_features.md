# set_device_features

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** four different sibling HTML pages, one per
`(single-vs-multi-VLAN, cripStat)` combination. All four write to
slightly different CGI endpoints with an overlapping set of fields.

| Page | Form action CGI | Triggering condition |
|---|---|---|
| `configuration/features2.html:74` | `/cgi/feature_set` | `vlanCount == 1`, `cripStat == "0"` (this switch) |
| `configuration/features2c.html:75` | `/cgi/feature2_set` | `vlanCount == 1`, `cripStat == "1"` |
| `configuration/features2a.html:67` + `configuration/features2b.html:86` | `/cgi/globalfeature_set` (STP-only, from 2a) + `/cgi/vlanfeature_set` (IGMP-only, per-VLAN, from 2b) | `vlanCount > 1`, `cripStat == "0"` |
| `configuration/features2a.html:67` + `configuration/features2d.html:57` | `/cgi/globalfeature_set` (STP) + `/cgi/vlan2feature_set` (IGMP, cripStat) | `vlanCount > 1`, `cripStat == "1"` |

The mode switch happens at `featuresf.html:15-41` — JavaScript
`initForm()` writes the correct `<frameset>` based on
`vlanCount`/`cripStat` (both injected by the server). On the
2810-24G observed here, `vlanCount = 1` and `cripStat = "0"`, so
only `feature_set` is in play.

Sub-tab key: `devfeatures` (menu.html:47).

## HTTP contract

All four endpoints share the same shape; the field set varies.

### /cgi/feature_set (single-VLAN default — this switch)

Source: features2.html:74-117. Both IGMP and STP in one form.

- **Method:** GET
- **URL template:** `/cgi/feature_set?indeces={vlan_id_or_0}&hpSwitchIgmpState={1|2}&hpSwitchStpAdminStatus={1|2}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | integer | yes | Hidden field (features2.html:75). Typically `1` for the default VLAN. |
  | hpSwitchIgmpState | `1`/`2` | yes | `1` = On, `2` = Off. |
  | hpSwitchStpAdminStatus | `1`/`2` | yes | `1` = On, `2` = Off. |

### /cgi/feature2_set (single-VLAN, cripStat=1)

Source: features2c.html:75-118. Same field set as `feature_set`.
The endpoint name is a firmware variant; identical wire shape.

- **URL template:** `/cgi/feature2_set?indeces={vlan}&hpSwitchIgmpState={1|2}&hpSwitchStpAdminStatus={1|2}`

### /cgi/globalfeature_set (multi-VLAN, global portion)

Source: features2a.html:67. Covers STP only (STP is a
switch-global feature).

- **URL template:** `/cgi/globalfeature_set?indeces={vlan}&hpSwitchStpAdminStatus={1|2}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | integer | yes | Hidden field (features2a.html:69), default `1`. |
  | hpSwitchStpAdminStatus | `1`/`2` | yes | `1` = On, `2` = Off. |

### /cgi/vlanfeature_set (multi-VLAN, per-VLAN portion)

Source: features2b.html:86-107. Covers IGMP only, per selected
VLAN.

- **URL template:** `/cgi/vlanfeature_set?indeces={vlan_id}&hpSwitchIgmpState={1|2}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | integer | yes | VLAN ID; populated from the `vlan_menu` select (features2b.html:75-79) and fed through the `loadNewVlan()` navigation that reloads this frame with a new `indeces` URL param. |
  | hpSwitchIgmpState | `1`/`2` | yes | |

### /cgi/vlan2feature_set (multi-VLAN, cripStat=1 variant of vlanfeature_set)

Source: features2d.html:57. Same field set as
`vlanfeature_set`.

- **URL template:** `/cgi/vlan2feature_set?indeces={vlan_id}&hpSwitchIgmpState={1|2}`

### Shared contract

- **Request body:** none (GET).
- **Response body:** **not live-tested.**
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| vlan_id | `indeces` | integer | `int` | `1` on single-VLAN switches; actual VLAN ID in multi-VLAN. |
| igmp | `hpSwitchIgmpState` | `1`/`2` | `bool` | True → `1` (On), False → `2` (Off). Absent in `/cgi/globalfeature_set`. |
| spanning_tree | `hpSwitchStpAdminStatus` | `1`/`2` | `bool` | Absent in `/cgi/vlanfeature_set` and `/cgi/vlan2feature_set`. |

## Reading the current values

No dedicated read CGI. Values are injected into the HTML:
```
var _igmp   = 1 ;
var _st     = 2 ;
```
(features2.html:49-50, features2c.html:49-50). On multi-VLAN
pages, `features2b.html:6` uses `var _igmp = Invalid OID ;`
meaning the server didn't populate IGMP for the default selection
— **that's a page-generator quirk, not a protocol one**.

The `initForm()` at features2.html:52-56 sets the select index
from these JS vars. Python scrapers should regex-match
`var _igmp\s*=\s*(\d+|"?Invalid OID"?)\s*;` and similar for `_st`.

## Example requests

Single-VLAN, set IGMP On + STP Off (common case on this switch):
```
GET /cgi/feature_set?indeces=1&hpSwitchIgmpState=1&hpSwitchStpAdminStatus=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Multi-VLAN, enable STP globally:
```
GET /cgi/globalfeature_set?indeces=1&hpSwitchStpAdminStatus=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Multi-VLAN, enable IGMP on VLAN 10:
```
GET /cgi/vlanfeature_set?indeces=10&hpSwitchIgmpState=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operations, not
live-tested.

## Pydantic sketch

```python
from enum import Enum
from pydantic import BaseModel


class FeatureEndpoint(str, Enum):
    SINGLE_VLAN = "/cgi/feature_set"
    SINGLE_VLAN_CRIP = "/cgi/feature2_set"
    MULTI_VLAN_GLOBAL = "/cgi/globalfeature_set"
    MULTI_VLAN_PER_VLAN = "/cgi/vlanfeature_set"
    MULTI_VLAN_PER_VLAN_CRIP = "/cgi/vlan2feature_set"


class SetDeviceFeaturesRequest(BaseModel):
    endpoint: FeatureEndpoint
    vlan_id: int = 1  # wire: indeces
    igmp: bool | None = None  # wire: hpSwitchIgmpState; None = omit
    spanning_tree: bool | None = None  # wire: hpSwitchStpAdminStatus; None = omit
```

## Notes & caveats

- **Five endpoints, three shapes.** `feature_set` and `feature2_set`
  are wire-identical; the switch picks between them by firmware
  variant (`cripStat`). `vlanfeature_set` and `vlan2feature_set`
  are likewise wire-identical.
- **Why not collapse?** Because the switch expects the exact path
  the HTML form action specifies — sending `IGMP` + `STP` to
  `/cgi/globalfeature_set` would reject the IGMP (no handler) and
  silently set only STP. Python callers must select the endpoint
  that matches the current page-generator variant; scraping
  `featuresf.html` / `features2*.html` before writing is the
  safest way.
- **`cripStat` semantics.** The JS variable `cripStat` (features2.html
  source — set server-side) is `"0"` in the mirror. Meaning is
  undocumented, but the switch-side code path is consistent: treat
  it as a firmware-feature flag. A Python client may discover it
  by scraping `featuresf.html`.
- **Multi-VLAN submits two forms.** features2b.html:30-55's
  `doSubmit()` calls `parent.dftf.document.devFeatures.submit()`
  (global/STP) and then `document.devFeatures.submit()` (per-VLAN
  IGMP). Python equivalents should issue both GETs in that order
  when VLAN count > 1.
- **Related:** `get_device_features` — not a separate CGI; use
  HTML scraping of `features2*.html`.
