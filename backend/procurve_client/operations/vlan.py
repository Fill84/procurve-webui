"""Configuration → VLAN subsystem operations (15 total).

Contracts in research/protocol/configuration/vlan/*.md.

Reads (7):
  - get_vlans_all        /cgi/getVLANAll
  - list_vlans           /cgi/listVLANS
  - get_vlan_mode        /cgi/getVLANMode          (bare ON/OFF)
  - get_gvrp_mode        /cgi/getGVRPMode          (bare ON/OFF)
  - get_gvrp_ports       /cgi/getGVRPPort          (sentinel-prefixed)
  - get_vlan_ports       /cgi/getVLANPort?VLAN_ID= (sentinel-prefixed)
  - get_vlan_protocol    /cgi/getVLANProtocol?VLAN_ID=

Writes (8):
  - add_vlan             /cgi/addVLAN
  - delete_vlans         /cgi/delVLAN (duplicate-key VLAN_ID)
  - rename_vlan          /cgi/renVLAN
  - set_primary_vlan     /cgi/setPrimary
  - set_vlan_ports       /cgi/setVLANPort (interleaved PORT/MODE pairs)
  - set_gvrp_ports       /cgi/setGVRPPort (interleaved PORT/MODE pairs)
  - set_vlan_mode        /cgi/setVLANMode
  - set_gvrp_mode        /cgi/setGVRPMode

Wire-encoding notes:
  - Duplicate-key multi-select (`delete_vlans`) and interleaved pair lists
    (`set_vlan_ports`, `set_gvrp_ports`) pass a list[tuple[str, str]] to
    ProcurveTransport.get so httpx preserves the keys in the wire order.
  - Bare `ON`/`OFF` body parsers live inline — no reuse with other
    subsystems.
  - Write responses may be `OK`, `OK~<listVLANS refresh>`, or a bare error
    string. We try `unwrap_sentinel`; on ParseError we fall back to a
    leading-token check so add/del/rename can surface switch-reported
    validation errors verbatim.
"""
from __future__ import annotations

from typing import Any

from procurve_client._safety import READ, WRITE
from procurve_client.errors import OperationError, ParseError
from procurve_client.models.vlan import (
    AddVlanRequest,
    DelVlanRequest,
    GvrpPort,
    GvrpPortList,
    GvrpPortMode,
    RenVlanRequest,
    SetGvrpModeRequest,
    SetGvrpPortsRequest,
    SetPrimaryVlanRequest,
    SetVlanModeRequest,
    SetVlanPortsRequest,
    Vlan,
    VlanList,
    VlanMembership,
    VlanMembershipList,
    VlanModeFlag,
    VlanPortMode,
    VlanProtocolList,
    VlanSummary,
    VlanSummaryList,
    VlanWriteAck,
)
from procurve_client.parsing import parse_tilde_lines, parse_tilde_row
from procurve_client.transport import ProcurveTransport

# ---- URL paths --------------------------------------------------------

_GET_VLAN_ALL = "/cgi/getVLANAll"
_LIST_VLANS = "/cgi/listVLANS"
_GET_VLAN_MODE = "/cgi/getVLANMode"
_GET_GVRP_MODE = "/cgi/getGVRPMode"
_GET_GVRP_PORT = "/cgi/getGVRPPort"
_GET_VLAN_PORT = "/cgi/getVLANPort"
_GET_VLAN_PROTOCOL = "/cgi/getVLANProtocol"

_ADD_VLAN = "/cgi/addVLAN"
_DEL_VLAN = "/cgi/delVLAN"
_REN_VLAN = "/cgi/renVLAN"
_SET_PRIMARY = "/cgi/setPrimary"
_SET_VLAN_PORT = "/cgi/setVLANPort"
_SET_GVRP_PORT = "/cgi/setGVRPPort"
_SET_VLAN_MODE = "/cgi/setVLANMode"
_SET_GVRP_MODE = "/cgi/setGVRPMode"


# ---- Shared helpers ---------------------------------------------------


def _parse_on_off(body: str, *, cgi: str) -> bool:
    """Parse the bare `ON`/`OFF` body emitted by get{VLAN,GVRP}Mode.

    Java applet uses `equalsIgnoreCase("ON")` (VLANfirstPanel.java:160).
    Any non-ON body is treated as OFF, matching applet behaviour; but we
    raise ParseError on completely empty responses as a defensive check.
    """
    text = body.strip()
    if not text:
        raise ParseError(f"{cgi}: empty body")
    return text.upper() == "ON"


def _pair_off_sentinel(body: str) -> tuple[str, list[str]]:
    """Split a `<sentinel>~<rest>~` body into (sentinel, remaining-tokens).

    Used by getGVRPPort and getVLANPort. Drops the trailing empty token
    from the training `~`.
    """
    tokens = list(parse_tilde_row(body.strip()))
    if not tokens:
        raise ParseError("empty sentinel-prefixed body")
    sentinel = tokens[0]
    return sentinel, tokens[1:]


def _parse_vlan_summary_stream(tokens: list[str]) -> list[VlanSummary]:
    """Chunk a flat `(id, name, id, name, ...)` token stream into pairs.

    Tolerates a trailing unpaired token (e.g. if the stream ends in a
    lone `~` that we already stripped). The applet's Java consumer
    (callURLlist) iterates in pairs regardless of line boundaries.
    """
    out: list[VlanSummary] = []
    for i in range(0, len(tokens) - 1, 2):
        raw_id = tokens[i].strip()
        name = tokens[i + 1]
        if not raw_id:
            continue
        try:
            vlan_id = int(raw_id)
        except ValueError as exc:
            raise ParseError(
                f"listVLANS: non-integer VLAN id token {raw_id!r}"
            ) from exc
        out.append(VlanSummary(vlan_id=vlan_id, vlan_name=name))
    return out


def _parse_write_response(body: str) -> VlanWriteAck:
    """Parse an add/del/ren/setPrimary-style response.

    Success body begins with `OK` (optionally followed by `~<refresh>`).
    Any other leading token is an error message; the applet pops up a
    dialog with it verbatim. We surface it as OperationError.
    """
    text = body.rstrip("\r\n").lstrip("\r\n")
    if not text:
        # Empty bodies sometimes appear on setPrimary; treat as OK.
        return VlanWriteAck(ok=True, raw_body=body or None)

    # First token check (case-insensitive OK match).
    if text.upper() == "OK":
        return VlanWriteAck(ok=True, raw_body=body or None)

    tokens = list(parse_tilde_row(text))
    if tokens and tokens[0].upper() == "OK":
        vlans = _parse_vlan_summary_stream(list(tokens[1:]))
        return VlanWriteAck(ok=True, raw_body=body, vlans=vlans)

    # Non-OK leading token — surface as OperationError with the message.
    if tokens:
        raise OperationError(tokens[0])
    raise OperationError(text)


def _parse_bare_ok(body: str) -> VlanWriteAck:
    """Parse a set{VLANMode,GVRPMode,VLANPort,GVRPPort,Primary} response.

    These endpoints return a bare `OK` on success. Per the protocol docs
    the error path is unverified live — see "needs live capture" notes.
    The applet checks the first two bytes for `OK` and treats anything
    else as an error (setVLANPort) or silently ignores (setVLANMode).
    """
    text = body.rstrip("\r\n").lstrip("\r\n")
    if not text:
        return VlanWriteAck(ok=True, raw_body=body or None)
    if text.upper().startswith("OK"):
        return VlanWriteAck(ok=True, raw_body=body)
    raise OperationError(text)


# =====================================================================
# Reads
# =====================================================================


@READ
async def get_vlans_all(transport: ProcurveTransport) -> VlanList:
    """Fetch `/cgi/getVLANAll` — full per-VLAN metadata (family=1).

    Multi-line stream, one VLAN per line, tilde-delimited with no
    sentinel. Each row has 8 fields on family=1; the `None` literal
    represents an empty port list.
    """
    r = await transport.get(_GET_VLAN_ALL)
    rows = parse_tilde_lines(r.text)
    if not rows:
        raise ParseError("getVLANAll: empty body")
    out: list[Vlan] = []
    for row in rows:
        if len(row) < 8:
            raise ParseError(
                f"getVLANAll row had {len(row)} fields (expected 8): {row!r}"
            )
        try:
            vid = int(row[0])
        except ValueError as exc:
            raise ParseError(
                f"getVLANAll: non-integer VLAN id {row[0]!r}"
            ) from exc
        out.append(
            Vlan(
                vlan_id=vid,
                vlan_name=row[1],
                vlan_type=row[2],
                tagged_ports=row[3],
                gvrp_ports=row[4],
                untagged_ports=row[5],
                forbid_ports=row[6],
                auto_ports=row[7],
            )
        )
    return VlanList(vlans=out)


@READ
async def list_vlans(transport: ProcurveTransport) -> VlanSummaryList:
    """Fetch `/cgi/listVLANS` — a flat `(id, name)` pair stream.

    Single line, tilde-delimited, no sentinel. A trailing `~` is present
    after the final name.
    """
    r = await transport.get(_LIST_VLANS)
    # The body is a single line (or rarely with a leading blank line per
    # VLANAddRemovePanel.java:253-255); flatten to tokens.
    tokens: list[str] = []
    for row in parse_tilde_lines(r.text):
        tokens.extend(row)
    vlans = _parse_vlan_summary_stream(tokens)
    return VlanSummaryList(vlans=vlans)


@READ
async def get_vlan_mode(transport: ProcurveTransport) -> VlanModeFlag:
    """Fetch `/cgi/getVLANMode` — bare `ON`/`OFF` body.

    Note: the applet only invokes this on family=0 (Voyager). Our 2810 is
    family=1, but the CGI is still reachable.
    """
    r = await transport.get(_GET_VLAN_MODE)
    return VlanModeFlag(enabled=_parse_on_off(r.text, cgi="getVLANMode"))


@READ
async def get_gvrp_mode(transport: ProcurveTransport) -> VlanModeFlag:
    """Fetch `/cgi/getGVRPMode` — bare `ON`/`OFF` body."""
    r = await transport.get(_GET_GVRP_MODE)
    return VlanModeFlag(enabled=_parse_on_off(r.text, cgi="getGVRPMode"))


@READ
async def get_gvrp_ports(transport: ProcurveTransport) -> GvrpPortList:
    """Fetch `/cgi/getGVRPPort` — GVRP sentinel + per-port triples.

    When `gvrp_enable` is OFF, the mode column for non-trunk ports is
    uninitialised garbage (observed `-2141579148`). We surface those as
    `mode=None` so the caller can render them as "undefined" rather than
    misinterpret them as valid GVRP modes.
    """
    r = await transport.get(_GET_GVRP_PORT)
    sentinel, rest = _pair_off_sentinel(r.text)
    gvrp_enable = sentinel.upper() == "ON"

    ports: list[GvrpPort] = []
    # Triples: (port_name, port_id, mode)
    for i in range(0, len(rest) - 2, 3):
        port_name = rest[i]
        try:
            port_id = int(rest[i + 1])
        except ValueError as exc:
            raise ParseError(
                f"getGVRPPort: non-integer port_id {rest[i + 1]!r}"
            ) from exc
        raw_mode = rest[i + 2]
        mode: GvrpPortMode | None
        try:
            mode_int = int(raw_mode)
        except ValueError:
            # Non-integer (shouldn't happen on this firmware) — treat as undefined.
            mode = None
        else:
            # Uninitialised slot when GVRP is globally OFF → undefined.
            mode = GvrpPortMode(mode_int) if mode_int in (0, 1, 2) else None
        ports.append(GvrpPort(port_name=port_name, port_id=port_id, mode=mode))
    return GvrpPortList(gvrp_enable=gvrp_enable, ports=ports)


@READ
async def get_vlan_ports(
    transport: ProcurveTransport, *, vlan_id: int
) -> VlanMembershipList:
    """Fetch `/cgi/getVLANPort?VLAN_ID=<id>` — per-port membership list."""
    if not (1 <= vlan_id <= 4094):
        raise ValueError(f"vlan_id {vlan_id} out of range 1..4094")
    r = await transport.get(_GET_VLAN_PORT, params={"VLAN_ID": vlan_id})
    sentinel, rest = _pair_off_sentinel(r.text)
    gvrp_enable = sentinel.upper() == "ON"

    ports: list[VlanMembership] = []
    for i in range(0, len(rest) - 2, 3):
        port_name = rest[i]
        try:
            port_id = int(rest[i + 1])
        except ValueError as exc:
            raise ParseError(
                f"getVLANPort: non-integer port_id {rest[i + 1]!r}"
            ) from exc
        try:
            mode_int = int(rest[i + 2])
        except ValueError as exc:
            raise ParseError(
                f"getVLANPort: non-integer mode {rest[i + 2]!r}"
            ) from exc
        if mode_int not in (0, 1, 2, 3):
            raise ParseError(
                f"getVLANPort: mode {mode_int} not in 0..3 for port {port_name}"
            )
        ports.append(
            VlanMembership(
                port_name=port_name,
                port_id=port_id,
                mode=VlanPortMode(mode_int),
            )
        )
    return VlanMembershipList(
        vlan_id=vlan_id, gvrp_enable=gvrp_enable, ports=ports
    )


@READ
async def get_vlan_protocol(
    transport: ProcurveTransport, *, vlan_id: int
) -> VlanProtocolList:
    """Fetch `/cgi/getVLANProtocol?VLAN_ID=<id>` — protocol filter list.

    Empty body is a valid "no protocols assigned" response on family=1
    switches (like our 2810). Not an error.
    """
    if not (1 <= vlan_id <= 4094):
        raise ValueError(f"vlan_id {vlan_id} out of range 1..4094")
    r = await transport.get(_GET_VLAN_PROTOCOL, params={"VLAN_ID": vlan_id})
    text = r.text.strip()
    if not text:
        return VlanProtocolList(vlan_id=vlan_id, protocols=[])
    tokens = [t for t in parse_tilde_row(text) if t]
    return VlanProtocolList(vlan_id=vlan_id, protocols=list(tokens))


# =====================================================================
# Writes
# =====================================================================


@WRITE
async def add_vlan(
    transport: ProcurveTransport, *, request: AddVlanRequest
) -> VlanWriteAck:
    """Create a VLAN via `/cgi/addVLAN?VLAN_ID=<id>&VLAN_NAME=<name>`.

    Response is `OK~<listVLANS refresh>` or `<error>~<refresh>`.
    """
    params: dict[str, Any] = {
        "VLAN_ID": request.vlan_id,
        "VLAN_NAME": request.vlan_name,
    }
    r = await transport.get(_ADD_VLAN, params=params)
    return _parse_write_response(r.text)


@WRITE
async def delete_vlans(
    transport: ProcurveTransport, *, request: DelVlanRequest
) -> VlanWriteAck:
    """Delete one or more VLANs via `/cgi/delVLAN?VLAN_ID=<id>&VLAN_ID=<id>...`.

    The duplicate-key pattern is load-bearing — do NOT collapse to a
    comma-list. httpx preserves list-valued dict entries as repeating keys,
    which matches the applet's manual string-concat at
    VLANAddRemovePanel.java:314-317.
    """
    params = {"VLAN_ID": list(request.vlan_ids)}
    r = await transport.get(_DEL_VLAN, params=params)
    return _parse_write_response(r.text)


@WRITE
async def rename_vlan(
    transport: ProcurveTransport, *, request: RenVlanRequest
) -> VlanWriteAck:
    """Rename a VLAN via `/cgi/renVLAN?VLAN_ID=<id>&VLAN_NAME=<name>`."""
    params: dict[str, Any] = {
        "VLAN_ID": request.vlan_id,
        "VLAN_NAME": request.vlan_name,
    }
    r = await transport.get(_REN_VLAN, params=params)
    return _parse_write_response(r.text)


@WRITE
async def set_primary_vlan(
    transport: ProcurveTransport, *, request: SetPrimaryVlanRequest
) -> VlanWriteAck:
    """Promote a VLAN to primary via `/cgi/setPrimary?VLAN_ID=<id>`.

    # TODO: needs live capture — the applet drains the response without
    inspecting it (VLANAddRemovePanel.java:421-428) so the exact success
    / failure body shape is unverified. We treat bare `OK` or empty body
    as success and non-OK bodies as OperationError.
    """
    params = {"VLAN_ID": request.vlan_id}
    r = await transport.get(_SET_PRIMARY, params=params)
    return _parse_bare_ok(r.text)


@WRITE
async def set_vlan_ports(
    transport: ProcurveTransport, *, request: SetVlanPortsRequest
) -> VlanWriteAck:
    """Set per-port VLAN membership via `/cgi/setVLANPort`.

    Wire order: `VLAN_ID=<id>&PORT=<p>&MODE=<m>&PORT=<p>&MODE=<m>...`.
    The PORT/MODE interleaving is load-bearing — httpx groups same-named
    keys when serialising a list-of-tuples (see QueryParams docs), so we
    assemble the raw query string manually and embed it in the path to
    force byte-exact order matching the applet's manual concat at
    VLANmodifyPanel.java:120-127. Callers should only include ports whose
    mode actually changed (mirroring `getChangedPortsID`).
    """
    parts: list[str] = [f"VLAN_ID={request.vlan_id}"]
    for change in request.changes:
        parts.append(f"PORT={change.port_id}")
        parts.append(f"MODE={change.mode}")
    url = f"{_SET_VLAN_PORT}?{'&'.join(parts)}"
    r = await transport.get(url)
    return _parse_bare_ok(r.text)


@WRITE
async def set_vlan_mode(
    transport: ProcurveTransport, *, request: SetVlanModeRequest
) -> VlanWriteAck:
    """Enable / disable VLAN support globally via `/cgi/setVLANMode?MODE=<n>`.

    Wire encoding: `1` = enable, `2` = disable (NOT 0/1). **Requires a
    device reboot** to take effect — the applet pops up a reboot dialog
    before hitting this CGI. Python callers must surface this to end
    users.

    # TODO: needs live capture — the error body format is unverified; the
    applet silently ignores non-OK responses at VLANfirstPanel.java:198.
    """
    params = {"MODE": request.to_wire_mode()}
    r = await transport.get(_SET_VLAN_MODE, params=params)
    return _parse_bare_ok(r.text)


@WRITE
async def set_gvrp_mode(
    transport: ProcurveTransport, *, request: SetGvrpModeRequest
) -> VlanWriteAck:
    """Enable / disable GVRP globally via `/cgi/setGVRPMode?MODE=<n>`.

    Wire encoding: `1` = enable, `2` = disable. Unlike `setVLANMode` this
    does not require a reboot (per the applet's UI path).

    # TODO: needs live capture — error body format unverified.
    """
    params = {"MODE": request.to_wire_mode()}
    r = await transport.get(_SET_GVRP_MODE, params=params)
    return _parse_bare_ok(r.text)


@WRITE
async def set_gvrp_ports(
    transport: ProcurveTransport, *, request: SetGvrpPortsRequest
) -> VlanWriteAck:
    """Set per-port GVRP mode via `/cgi/setGVRPPort`.

    No VLAN_ID prefix (GVRP state is per-port, not per-VLAN). Same
    interleaved PORT/MODE pattern as `setVLANPort`; assembled manually to
    beat httpx's same-key grouping.

    # TODO: needs live capture — the applet reads the body but never
    inspects it; we assume bare `OK` on success.
    """
    parts: list[str] = []
    for change in request.changes:
        parts.append(f"PORT={change.port_id}")
        parts.append(f"MODE={change.mode}")
    url = f"{_SET_GVRP_PORT}?{'&'.join(parts)}"
    r = await transport.get(url)
    return _parse_bare_ok(r.text)
