# getVLANProtocol

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANprotocolPanel.java:95` (called through
`VLANmain.callURL("getVLANProtocol?VLAN_ID=" + vlanId)`); logged at
`VLANprotocolPanel.java:96-97` as `/cgi/getVLANProtocol?VLAN_ID=`;
parsed at `VLANprotocolPanel.java:98-113`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/getVLANProtocol?VLAN_ID={vlan_id}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer | yes | VLAN to query. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, tilde-delimited tokens where
  each token is a protocol name. **No sentinel.** The applet
  appends each token to a TextArea with a newline after each.

  Layout:
  ```
  <protocol_1>~<protocol_2>~<protocol_3>~...
  ```

- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200; empty body (valid on switches
  that don't support protocol VLANs — like our 2810).

## Field reference

| field | wire type | python type | notes |
|---|---|---|---|
| protocol | string | `str` | Protocol filter name (e.g. `IP`, `IPX`, `AppleTalk`). |

## Example request

```
GET /cgi/getVLANProtocol?VLAN_ID=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__getVLANProtocol.response.txt`
(live-captured 2026-04-23, 0 bytes — empty body; args `VLAN_ID=1`,
the DEFAULT_VLAN).

On our 2810 the endpoint exists but returns an empty response
because protocol-VLAN support is an Alpha-family feature
(`VLANmain.m_protocolVlan == 1`), and our switch is `family=1`
(Infinity). The Java applet never instantiates
`VLANprotocolPanel` on our device, but the CGI is still reachable.

On an Alpha-family switch with protocols assigned, the body would
look like:
```
IP~IPX~AppleTalk~
```

## Pydantic sketch

```python
from pydantic import BaseModel


class GetVlanProtocolResponse(BaseModel):
    vlan_id: int
    protocols: list[str]
```

## Notes & caveats

- **Read-only endpoint.** There is no `setVLANProtocol` — the
  protocol panel has only a Back button (`VLANprotocolPanel.java:60-62`).
  Protocol-to-VLAN assignment must therefore be done via CLI / SNMP
  on supported devices, then viewed here.
- **No sentinel.** Unlike most VLAN CGIs, the response carries no
  `OK~` prefix. An empty body is a valid "no protocols assigned"
  result, not an error.
- **Not called on our 2810.** Because `family=1` and
  `m_protocolVlan=0`, the applet does not create the protocol
  panel. Python clients that target the 2810 may omit this
  operation from their public API.
</content>
</invoke>