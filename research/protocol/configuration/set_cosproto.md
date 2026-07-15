# set_cosproto

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_proto.html:17`
(`<FORM name=cos1 action="../cgi/cosproto" onSubmit="return protoWarning();">`).
Sub-tab key: note: the QoS menu panel `cos_menu3.html?ldPage=1`
redirects to `cos_proto.html`, but on this switch that panel is not
exposed in the QoS sub-menu (only panels 2-7 appear in
`cos_menu1.html`). The page is still served.

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
- **URL template:** `/cgi/cosproto` (plus per-protocol priority
  fields; see below).
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | (per-protocol) | integer | yes | The form's `<table>` at cos_proto.html:19 is meant to list one row per protocol; each row would have its own priority select. On this firmware the table body is empty, so the form submits only the `Apply` button value. |
  | Apply | literal `Apply Changes` | submit button | The input is `<input type="Submit" name="Apply" value="Apply Changes">`. |

  The observed form is effectively empty — there are no editable
  rows. **Exact wire shape is unknown** until a switch model with
  active protocol-priority rules is available.

- **Request body:** none (GET).
- **Response body:** **not live-tested.**

## Field reference

TBD — **needs live capture on a switch that exposes the Protocol
Priority sub-panel with populated rows.** The 2810-24G running this
firmware does not expose protocol-priority rules, so the panel is
empty.

## Example request

Empty-form submit (what the UI would send with no rows):
```
GET /cgi/cosproto?Apply=Apply+Changes HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
# Model deferred — requires live protocol-row schema.
# Placeholder:
from pydantic import BaseModel


class SetCosProtoRequest(BaseModel):
    # Expected fields: a dict[protocol_id, priority_8021p]
    # Not derivable without a populated form capture.
    apply: str = "Apply Changes"
```

## Notes & caveats

- **Empty on this switch.** The `<table>` body is empty. The panel
  is not listed in `cos_menu1.html`'s button bar either (only
  panels 2-7 are shown). This operation is effectively a dead
  endpoint on the 2810-24G.
- **Related:** `set_cos_vlanpri` (VLAN-priority table).
- **Marked as `unknown — needs live capture`.**
