"""Configuration-tab operations (excluding VLAN and Stacking sub-tabs).

Contracts in research/protocol/configuration/*.md.

All 24 protocol-defined operations plus 5 implicit HTML-scrape reads that
compensate for sub-tabs with no dedicated read CGI (fault detection, system,
IP, support, device features). Per _conventions.md all write endpoints use
GET with query-string args (no POST), and the misspelling `indeces=` on the
wire is preserved byte-for-byte.

Sections (one per sub-tab):
  devview      : get_bobports, set_bobports
  faultdetect  : get_faultdetect_page (scrape), set_fault_detection
  system       : get_system_page (scrape), set_system_info
  ip           : get_ip_page (scrape), set_ip_config, set_default_gateway
  ports        : get_portscfg, get_port_form, set_port_config
  qos          : get_cos_appt, set_cos_appt, get_cos_userpri, set_cos_userpri,
                 set_costos_mode, get_cos_vlanpri, set_cos_vlanpri,
                 get_dscptable, set_dscptable, get_diffserv, set_diffserv,
                 set_cosproto
  monitor      : set_monitor
  devfeatures  : get_devfeatures_page (scrape), set_device_features
  support      : get_support_page (scrape), set_support

For the QoS multi-frame submits (set_cos_appt, set_cos_userpri) the exact
wire shape is unverified on the live switch — see `# TODO: needs live
capture` notes in those functions.
"""
from __future__ import annotations

import re
from ipaddress import IPv4Address
from urllib.parse import quote_plus

from procurve_client._safety import READ, WRITE
from procurve_client.errors import ParseError
from procurve_client.models.network import (
    ConfigWriteAck,
    DeviceFeaturesPage,
    FaultDetectionPage,
    FaultSensitivity,
    IpConfigPage,
    IpMode,
    MonitorPage,
    SetDefaultGatewayRequest,
    SetDeviceFeaturesRequest,
    SetFaultDetectionRequest,
    SetIpConfigRequest,
    SetMonitorRequest,
    SetSupportRequest,
    SetSystemInfoRequest,
    SupportPage,
    SystemInfoPage,
)
from procurve_client.models.port import (
    BobDevice,
    BobPort,
    BobPortsResponse,
    PortConfig,
    PortConfigList,
    PortForm,
    PortMode,
    SetBobPortsRequest,
    SetPortConfigRequest,
)
from procurve_client.models.qos import (
    CosAppEntry,
    CosAppList,
    CosUserEntry,
    CosUserList,
    CosVlanEntry,
    CosVlanList,
    DiffservEntry,
    DiffservTable,
    DscpPolicy,
    DscpTable,
    QosWriteAck,
    SetCosApptRequest,
    SetCosProtoRequest,
    SetCosTosModeRequest,
    SetCosUserPriRequest,
    SetCosVlanPriRequest,
    SetDiffservRequest,
    SetDscpTableRequest,
)
from procurve_client.parsing import ensure_write_ok, parse_int, parse_tilde_lines
from procurve_client.transport import ProcurveTransport

# ---- URL paths --------------------------------------------------------

_GET_BOBPORTS = "/cgi/get_bobports"
_SET_BOBPORTS = "/cgi/set_bobports"
_WEB_AGENT_PAGE = "/configuration/web_agent.html"
_WEB_AGENT_CGI = "/cgi/web_agent"
_SYSTEM_PAGE = "/configuration/system.html"
_SYSTEM_CGI = "/cgi/system"
_IP1_PAGE = "/configuration/ip1.html"
_IP2_PAGE = "/configuration/ip2.html"
_IP_CGI = "/cgi/ip"
_GATEWAY_CGI = "/cgi/gateway"
_SUPPORT_PAGE = "/configuration/support.html"
_SUPPORT_CGI = "/cgi/support"
_PORTSCFG_CGI = "/cgi/get_portscfg"
_PORT_FORM_CGI = "/cgi/port_form"
_MOD_PORTS_CGI = "/cgi/mod_ports"
_COSAPP_CGI = "/cgi/cosapp"
_COSAPPF_CGI = "/cgi/cosappf"
_COSUSER_CGI = "/cgi/cosuser"
_COSUSERF_CGI = "/cgi/cosuserf"
_COSTOS_CGI = "/cgi/costos"
_COSVLAN_CGI = "/cgi/cosvlan"
_COSVLANF_CGI = "/cgi/cosvlanf"
_DSCPTABLE_GET_CGI = "/cgi/dscptable_get"
_DSCPTABLE_SET_CGI = "/cgi/dscptable_set"
_DIFFSERV_GET_CGI = "/cgi/diffserv_get"
_DIFFSERV_SET_CGI = "/cgi/diffserv_set"
_COSPROTO_CGI = "/cgi/cosproto"
_MONITOR_CGI = "/cgi/set_monitor"
_MONITOR_PAGE = "/configuration/monitor1.html"
_FEATURES_PAGE = "/configuration/features2.html"

# Literal submit-button values preserved for byte-exact replay.
_APPLY_CHANGES = " Apply Changes "
_APPLY_SETTINGS = " Apply Settings "


# ---- Shared helpers ---------------------------------------------------

def _parse_yes_no(s: str) -> bool:
    v = s.strip().lower()
    if v == "yes":
        return True
    if v == "no":
        return False
    raise ParseError(f"expected Yes/No, got {s!r}")


def _parse_enable_disable(s: str) -> bool:
    v = s.strip().lower()
    if v == "enable":
        return True
    if v == "disable":
        return False
    raise ParseError(f"expected Enable/Disable, got {s!r}")


def _bob_bool(s: str) -> bool:
    """SwitchBob.java parses `1`/`on` as true (SwitchBob.java:218,220)."""
    v = s.strip().lower()
    return v in ("1", "on", "yes")


def _format_ports_csv(ports: list[int]) -> str:
    """Join port numbers with commas, matching SwitchBob.java:291."""
    return ",".join(str(p) for p in ports)


# =====================================================================
# devview sub-tab: get_bobports / set_bobports
# =====================================================================

@READ
async def get_bobports(transport: ProcurveTransport) -> BobPortsResponse:
    """Fetch /cgi/get_bobports — the device-view chassis + port rollup.

    Line 1 is a 2-field device record; subsequent lines are port rows.
    The 2810-24G emits no intermediate card lines, but defensive parsing
    tolerates them.
    """
    r = await transport.get(_GET_BOBPORTS)
    rows = parse_tilde_lines(r.text)
    if not rows:
        raise ParseError("empty /cgi/get_bobports response")
    dev_row = rows[0]
    if len(dev_row) < 2:
        raise ParseError(f"/cgi/get_bobports device line missing fields: {dev_row!r}")
    device = BobDevice(
        codename=dev_row[0],
        port_count=parse_int(dev_row[1], context="get_bobports port_count"),
    )

    ports: list[BobPort] = []
    for row in rows[1:]:
        # A card-info line has exactly one token (per SwitchBob.parseCardInfo).
        if len(row) == 1:
            continue
        if row[0].strip().lower() == "none":
            continue
        if len(row) < 5:
            raise ParseError(f"bobports row had {len(row)} fields: {row!r}")
        ports.append(
            BobPort(
                port=parse_int(row[0], context="get_bobports port"),
                kind=row[1],
                label=row[2],
                link=_bob_bool(row[3]),
                enabled=_bob_bool(row[4]),
                mode=row[5] if len(row) > 5 and row[5].strip() else None,
                poe=parse_int(row[6], context="get_bobports poe")
                if len(row) > 6 and row[6].strip()
                else None,
            )
        )
    return BobPortsResponse(device=device, ports=ports)


@WRITE
async def set_bobports(
    transport: ProcurveTransport,
    *,
    request: SetBobPortsRequest,
) -> ConfigWriteAck:
    """Bulk-enable or -disable ports via /cgi/set_bobports.

    Wire-level: `ifAdminStatus=1|2` + `indeces=<csv>`. The misspelling
    `indeces` is preserved on the wire. Response body is not consumed by
    the legacy UI; unverified shape (presumed OK~...).

    The query is assembled manually so the CSV comma stays literal (httpx
    params would emit %2C, which the firmware's own comma-splitting echo
    parser suggests it does not decode — see _conventions.md).
    """
    csv = _format_ports_csv(request.ports)
    admin = "1" if request.enable else "2"
    r = await transport.get(f"{_SET_BOBPORTS}?ifAdminStatus={admin}&indeces={csv}")
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# faultdetect sub-tab
# =====================================================================

_FFS_RE = re.compile(r"\bffs\s*=\s*(\d+)\s*;")
_DPS_RE = re.compile(r"\bdps\s*=\s*(\d+)\s*;")


@READ
async def get_faultdetect_page(transport: ProcurveTransport) -> FaultDetectionPage:
    """Scrape /configuration/web_agent.html for the current sensitivity.

    The switch injects `ffs=<int>;` and `dps=<int>;` near the top of the
    body. Returns them verbatim. This is the only read path — the applet
    has no CGI for fault-detection state.
    """
    r = await transport.get(_WEB_AGENT_PAGE)
    body = r.text
    m = _FFS_RE.search(body)
    if not m:
        raise ParseError("web_agent.html: missing `ffs=<digits>;` injection")
    ffs_int = int(m.group(1))
    try:
        sensitivity = FaultSensitivity(ffs_int)
    except ValueError as exc:
        raise ParseError(f"unknown ffs value {ffs_int}") from exc
    dps_match = _DPS_RE.search(body)
    return FaultDetectionPage(
        sensitivity=sensitivity,
        dps=int(dps_match.group(1)) if dps_match else None,
    )


@WRITE
async def set_fault_detection(
    transport: ProcurveTransport,
    *,
    request: SetFaultDetectionRequest,
) -> ConfigWriteAck:
    """Set fault-detection sensitivity via /cgi/web_agent?ffs=<n>."""
    params = {"ffs": int(request.sensitivity)}
    r = await transport.get(_WEB_AGENT_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# system sub-tab
# =====================================================================

_SYS_INPUT_RE = re.compile(
    r'<input\s+name=(?P<name>sysName|sysLocation|sysContact)'
    r'\s+value="(?P<value>[^"]*)"',
    re.IGNORECASE,
)
_SYS_MAC_RE = re.compile(
    r'MAC Address:\s*</th>\s*<td>\s*<b>\s*'
    r'([0-9a-fA-F]{2}(?:[ :\-][0-9a-fA-F]{2}){5})\s*</b>',
    re.IGNORECASE | re.DOTALL,
)


@READ
async def get_system_page(transport: ProcurveTransport) -> SystemInfoPage:
    """Scrape /configuration/system.html for name/location/contact + MAC.

    The MAC is rendered as space-separated hex octets; we normalise to
    canonical colon-separated uppercase to match `DeviceIdentity.base_mac`.
    """
    r = await transport.get(_SYSTEM_PAGE)
    body = r.text
    fields: dict[str, str] = {}
    for m in _SYS_INPUT_RE.finditer(body):
        fields[m.group("name")] = m.group("value")
    for key in ("sysName", "sysLocation", "sysContact"):
        if key not in fields:
            raise ParseError(f"system.html: missing <input name={key}>")
    mac_m = _SYS_MAC_RE.search(body)
    if not mac_m:
        raise ParseError("system.html: missing MAC Address cell")
    mac_raw = mac_m.group(1)
    parts = re.split(r"[ :\-]", mac_raw.strip())
    mac = ":".join(p.upper() for p in parts)
    return SystemInfoPage(
        mac_address=mac,
        name=fields["sysName"],
        location=fields["sysLocation"],
        contact=fields["sysContact"],
    )


@WRITE
async def set_system_info(
    transport: ProcurveTransport,
    *,
    request: SetSystemInfoRequest,
) -> ConfigWriteAck:
    """Write system name/location/contact via /cgi/system.

    Emits the literal `apply=" Apply Changes "` submit-button value
    (with leading/trailing spaces) byte-exactly, per _conventions.md.
    """
    params = {
        "indeces": 0,
        "sysName": request.name,
        "sysLocation": request.location,
        "sysContact": request.contact,
        "apply": _APPLY_CHANGES,
    }
    r = await transport.get(_SYSTEM_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# ip sub-tab
# =====================================================================

_IP_VLAN_RE = re.compile(r'<input[^>]*name=VLAN[^>]*value=(\d+)', re.IGNORECASE)
_IP_MODE_RE = re.compile(r'<input[^>]*name=mode[^>]*value=(\d+)', re.IGNORECASE)
_IP_ADDR_CELL_RE = re.compile(
    r'IP Address:.*?<td>.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
    re.IGNORECASE | re.DOTALL,
)
_IP_MASK_CELL_RE = re.compile(
    r'Subnet Mask:.*?<td>.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
    re.IGNORECASE | re.DOTALL,
)
_IP_GATEWAY_JS_RE = re.compile(
    r'defaultGateway\s*=\s*"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"'
)
_IP_GATEWAY_INPUT_RE = re.compile(
    r'<input[^>]*name=rt[^>]*value="(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"',
    re.IGNORECASE,
)


@READ
async def get_ip_page(transport: ProcurveTransport) -> IpConfigPage:
    """Scrape /configuration/ip2.html + /configuration/ip1.html for IP state.

    Both frames must be fetched: ip2.html carries VLAN/mode/IP/mask and
    ip1.html carries the gateway. Matches the legacy two-frame arrangement.
    """
    r2 = await transport.get(_IP2_PAGE)
    r1 = await transport.get(_IP1_PAGE)
    body2, body1 = r2.text, r1.text

    vlan_m = _IP_VLAN_RE.search(body2)
    mode_m = _IP_MODE_RE.search(body2)
    if not vlan_m or not mode_m:
        raise ParseError("ip2.html: missing VLAN/mode hidden inputs")
    ip_m = _IP_ADDR_CELL_RE.search(body2)
    mask_m = _IP_MASK_CELL_RE.search(body2)
    gw_m = _IP_GATEWAY_INPUT_RE.search(body1) or _IP_GATEWAY_JS_RE.search(body1)
    if not gw_m:
        raise ParseError("ip1.html: missing default gateway")
    try:
        mode = IpMode(int(mode_m.group(1)))
    except ValueError as exc:
        raise ParseError(
            f"ip2.html: unknown IP mode {mode_m.group(1)!r}"
        ) from exc
    return IpConfigPage(
        vlan_id=int(vlan_m.group(1)),
        mode=mode,
        ip_address=_parse_ipv4(ip_m.group(1), context="ip2.html IP address")
        if ip_m
        else None,
        subnet_mask=mask_m.group(1) if mask_m else None,
        gateway=_parse_ipv4(gw_m.group(1), context="ip1.html gateway"),
    )


def _parse_ipv4(raw: str, *, context: str) -> IPv4Address:
    """IPv4Address() with ParseError — dotted-digit regexes admit 999.1.1.1."""
    try:
        return IPv4Address(raw)
    except ValueError as exc:
        raise ParseError(f"{context}: invalid IPv4 literal {raw!r}") from exc


@WRITE
async def set_ip_config(
    transport: ProcurveTransport,
    *,
    request: SetIpConfigRequest,
) -> ConfigWriteAck:
    """Write VLAN/mode/gateway together via /cgi/ip.

    Emits the submit-button value with leading/trailing spaces.
    Can break connectivity — see protocol doc. Caller must opt-in.
    """
    params = {
        "rt": str(request.gateway),
        "VLAN": request.vlan_id,
        "mode": int(request.mode),
        "apply": _APPLY_CHANGES,
    }
    r = await transport.get(_IP_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


@WRITE
async def set_default_gateway(
    transport: ProcurveTransport,
    *,
    request: SetDefaultGatewayRequest,
) -> ConfigWriteAck:
    """Set only the default gateway via /cgi/gateway."""
    params = {"rt": str(request.gateway)}
    r = await transport.get(_GATEWAY_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# ports sub-tab
# =====================================================================

@READ
async def get_portscfg(transport: ProcurveTransport) -> PortConfigList:
    """Fetch /cgi/get_portscfg — per-port configuration rows (10 fields).

    GenericList-driven bare-row stream, no sentinel.
    """
    r = await transport.get(_PORTSCFG_CGI)
    rows = parse_tilde_lines(r.text)
    ports: list[PortConfig] = []
    for row in rows:
        if len(row) < 10:
            raise ParseError(
                f"get_portscfg row had {len(row)} fields (expected 10): {row!r}"
            )
        ports.append(
            PortConfig(
                port=parse_int(row[0], context="getPortsCfg port"),
                port_name=row[1],
                port_type_label=row[2],
                port_type=row[3],
                enabled=_parse_yes_no(row[4]),
                config_status=row[5],
                config_mode=row[6],
                trunk=row[7],
                flow_control=_parse_enable_disable(row[8]),
                extra=parse_int(row[9], context="getPortsCfg extra")
                if row[9].strip()
                else 0,
            )
        )
    return PortConfigList(ports=ports)


_PF_INDECES_RE = re.compile(
    r'<Input\s+Type="?hidden"?\s+Name="?indeces"?\s+Value="?([^">\s]+)"?',
    re.IGNORECASE,
)
_PF_PORTNAME_RE = re.compile(
    r'<Input\s+Type="?text"?\s+Name="?_portName"?[^>]*value="([^"]*)"',
    re.IGNORECASE,
)
_PF_ADMIN_RE = re.compile(
    r'<Input\s+Type="?RADIO"?\s+Name="?hpSwitchPortAdminStatus"?'
    r'\s+Value=(\d+)[^>]*\s+Checked',
    re.IGNORECASE,
)
_PF_MODE_RE = re.compile(
    r'<Select\s+Name="?hpSwitchPortFastEtherMode"?.*?</Select>',
    re.IGNORECASE | re.DOTALL,
)
_PF_FLOW_RE = re.compile(
    r'<Select\s+Name="?hpSwitchPortFlowControl"?.*?</Select>',
    re.IGNORECASE | re.DOTALL,
)
_PF_OPTION_SELECTED_RE = re.compile(
    r'<option\s+value=(\d+)[^>]*selected', re.IGNORECASE
)


def _parse_indeces_csv(s: str) -> list[int]:
    """Split a CSV/`%2C`-joined port list into ints. Empty → []."""
    s = s.strip()
    if not s:
        return []
    return [
        parse_int(x, context="indeces csv") for x in re.split(r"[,]|%2C", s) if x
    ]


@READ
async def get_port_form(
    transport: ProcurveTransport,
    *,
    ports: list[int],
) -> PortForm:
    """Fetch /cgi/port_form?indeces=<csv> — the per-port edit form.

    Parses the HTML body to recover the current values (admin status, mode,
    flow control, port name). Uses regex rather than a full HTML parser to
    avoid a dependency; the form is stable across firmware versions.
    """
    if not ports:
        raise ValueError("ports must be non-empty")
    params = {"indeces": _format_ports_csv(ports)}
    r = await transport.get(_PORT_FORM_CGI, params=params)
    body = r.text

    indeces_m = _PF_INDECES_RE.search(body)
    if not indeces_m:
        raise ParseError("port_form: missing hidden indeces input")
    echoed = _parse_indeces_csv(indeces_m.group(1))

    name_m = _PF_PORTNAME_RE.search(body)
    admin_m = _PF_ADMIN_RE.search(body)
    mode_block_m = _PF_MODE_RE.search(body)
    flow_block_m = _PF_FLOW_RE.search(body)
    if not (admin_m and mode_block_m and flow_block_m):
        raise ParseError("port_form: missing one or more form fields")

    mode_sel = _PF_OPTION_SELECTED_RE.search(mode_block_m.group(0))
    flow_sel = _PF_OPTION_SELECTED_RE.search(flow_block_m.group(0))
    if not mode_sel or not flow_sel:
        raise ParseError("port_form: no selected <option> in mode/flow select")

    return PortForm(
        ports=echoed,
        port_name=name_m.group(1) if name_m else "",
        admin_enabled=admin_m.group(1) == "1",
        mode=PortMode(int(mode_sel.group(1))),
        # flow: value=2 → Enabled, value=1 → Disabled
        flow_control_enabled=flow_sel.group(1) == "2",
    )


@WRITE
async def set_port_config(
    transport: ProcurveTransport,
    *,
    request: SetPortConfigRequest,
) -> ConfigWriteAck:
    """Modify per-port config via /cgi/mod_ports.

    Preserves the `_portName` underscore and `indeces` misspelling
    byte-exactly; emits `apply=+Apply+Settings+` on the wire (quote_plus of
    " Apply Settings ", matching the applet's URLEncoder.encode).

    The query is assembled manually so the `indeces` CSV comma stays
    literal (httpx params would emit %2C — see _conventions.md); the
    user-supplied port name is quote_plus-encoded like the applet did.
    """
    query = "&".join(
        [
            f"indeces={_format_ports_csv(request.ports)}",
            f"_portName={quote_plus(request.name)}",
            f"hpSwitchPortAdminStatus={'1' if request.admin_enabled else '2'}",
            f"hpSwitchPortFastEtherMode={int(request.mode)}",
            f"hpSwitchPortFlowControl={'2' if request.flow_control_enabled else '1'}",
            f"apply={quote_plus(_APPLY_SETTINGS)}",
        ]
    )
    r = await transport.get(f"{_MOD_PORTS_CGI}?{query}")
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# qos sub-tab
# =====================================================================

@READ
async def get_cos_appt(transport: ProcurveTransport) -> CosAppList:
    """Fetch /cgi/cosapp — application → priority entries.

    Empty-list responses are single-byte (just `\\n`) — tolerated by
    parse_tilde_lines returning []. The wire row has a port-number suffix
    like `http (80)` in position 0; position 1 is the numeric port.
    """
    r = await transport.get(_COSAPP_CGI)
    rows = parse_tilde_lines(r.text)
    entries: list[CosAppEntry] = []
    for row in rows:
        if len(row) < 5:
            raise ParseError(f"cosapp row had {len(row)} fields: {row!r}")
        proto = row[2].strip().upper()
        if proto not in ("TCP", "UDP"):
            raise ParseError(f"unexpected cosapp type: {row[2]!r}")
        entries.append(
            CosAppEntry(
                application_name=row[0],
                port_number=parse_int(row[1], context="getCosAppt port_number"),
                type=proto,
                dscp=row[3],
                priority=row[4],
            )
        )
    return CosAppList(entries=entries)


@WRITE
async def set_cos_appt(
    transport: ProcurveTransport,
    *,
    request: SetCosApptRequest,
) -> QosWriteAck:
    """Submit /cgi/cosappf with the merged 4-frame form state.

    # TODO: needs live capture — the legacy UI's submit only sends the
    `fapp3` form's fields; whether the switch also picks up `ap`, `dscp`,
    `pr`, `src` from sibling-frame forms (via session state) is unverified.
    Python client eagerly emits all known fields.
    """
    params: dict[str, int | str] = {
        "action": request.action,
        "app": request.app_id,
        "tcpudp": request.protocol,
        "ap": int(request.policy_mode),
    }
    if request.port is not None:
        params["src"] = request.port
    if request.dscp is not None:
        params["dscp"] = request.dscp
    if request.priority_8021p is not None:
        params["pr"] = request.priority_8021p
    r = await transport.get(_COSAPPF_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


@READ
async def get_cos_userpri(transport: ProcurveTransport) -> CosUserList:
    """Fetch /cgi/cosuser — per-device QoS entries. Empty = no rows."""
    r = await transport.get(_COSUSER_CGI)
    rows = parse_tilde_lines(r.text)
    entries: list[CosUserEntry] = []
    for row in rows:
        if len(row) < 3:
            raise ParseError(f"cosuser row had {len(row)} fields: {row!r}")
        entries.append(
            CosUserEntry(
                ip_address=IPv4Address(row[0].strip()),
                dscp_policy=row[1],
                priority=row[2],
            )
        )
    return CosUserList(entries=entries)


@WRITE
async def set_cos_userpri(
    transport: ProcurveTransport,
    *,
    request: SetCosUserPriRequest,
) -> QosWriteAck:
    """Submit /cgi/cosuserf — add/replace/delete a device-priority entry.

    # TODO: needs live capture — same multi-frame submit quirk as
    set_cos_appt. The `pr` select lives in a sibling frame (cos_user2) and
    may or may not be merged server-side.
    """
    params: dict[str, int | str] = {
        "action": request.action,
        "addr": str(request.address),
        "ap": int(request.policy_mode),
    }
    if request.priority_8021p is not None:
        params["pr"] = request.priority_8021p
    if request.dscp is not None:
        params["dscp"] = request.dscp
    r = await transport.get(_COSUSERF_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


@WRITE
async def set_costos_mode(
    transport: ProcurveTransport,
    *,
    request: SetCosTosModeRequest,
) -> QosWriteAck:
    """Set the switch-wide ToS interpretation mode via /cgi/costos."""
    params = {
        "hpSwitchCosTosConfigMode": int(request.mode),
        "indeces": 0,
    }
    r = await transport.get(_COSTOS_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


@READ
async def get_cos_vlanpri(transport: ProcurveTransport) -> CosVlanList:
    """Fetch /cgi/cosvlan — one 4-field row per VLAN."""
    r = await transport.get(_COSVLAN_CGI)
    rows = parse_tilde_lines(r.text)
    entries: list[CosVlanEntry] = []
    for row in rows:
        if len(row) < 4:
            raise ParseError(f"cosvlan row had {len(row)} fields: {row!r}")
        entries.append(
            CosVlanEntry(
                vlan_id=parse_int(row[0], context="getCosVlanPri vlan_id"),
                vlan_label=row[1],
                dscp_policy=row[2],
                priority=row[3],
            )
        )
    return CosVlanList(entries=entries)


@WRITE
async def set_cos_vlanpri(
    transport: ProcurveTransport,
    *,
    request: SetCosVlanPriRequest,
) -> QosWriteAck:
    """Assign DSCP or 802.1p priority to a VLAN via /cgi/cosvlanf."""
    params = {
        "dscp": request.dscp,
        "pr": request.priority_8021p,
        "indeces": request.vlan_id,
    }
    r = await transport.get(_COSVLANF_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


@READ
async def get_dscptable(transport: ProcurveTransport) -> DscpTable:
    """Fetch /cgi/dscptable_get — 64-row DSCP → 802.1p mapping."""
    r = await transport.get(_DSCPTABLE_GET_CGI)
    rows = parse_tilde_lines(r.text)
    out: list[DscpPolicy] = []
    for row in rows:
        if len(row) < 3:
            raise ParseError(f"dscptable row had {len(row)} fields: {row!r}")
        out.append(
            DscpPolicy(
                row_index=parse_int(row[0], context="getDscpTable row_index"),
                codepoint=row[1],
                priority_label=row[2],
            )
        )
    return DscpTable(rows=out)


@WRITE
async def set_dscptable(
    transport: ProcurveTransport,
    *,
    request: SetDscpTableRequest,
) -> QosWriteAck:
    """Update a single row of the DSCP → 802.1p map via /cgi/dscptable_set.

    `row_index = codepoint + 1`. `pr=255` means "No Override".
    """
    params = {
        "indeces": request.row_index,
        "pr": request.priority_8021p,
    }
    r = await transport.get(_DSCPTABLE_SET_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


@READ
async def get_diffserv(transport: ProcurveTransport) -> DiffservTable:
    """Fetch /cgi/diffserv_get — 64-row inbound DSCP policy table."""
    r = await transport.get(_DIFFSERV_GET_CGI)
    rows = parse_tilde_lines(r.text)
    out: list[DiffservEntry] = []
    for row in rows:
        if len(row) < 4:
            raise ParseError(f"diffserv row had {len(row)} fields: {row!r}")
        out.append(
            DiffservEntry(
                row_index=parse_int(row[0], context="getDiffserv row_index"),
                inbound_codepoint=row[1],
                dscp_policy=row[2],
                priority_label=row[3],
            )
        )
    return DiffservTable(rows=out)


@WRITE
async def set_diffserv(
    transport: ProcurveTransport,
    *,
    request: SetDiffservRequest,
) -> QosWriteAck:
    """Rewrite the DSCP policy for an inbound codepoint via /cgi/diffserv_set.

    # TODO: needs live capture — the write only carries `dscp`; whether the
    priority (802.1p) is preserved or cleared server-side is undocumented.
    """
    params = {
        "indeces": request.row_index,
        "dscp": request.dscp,
    }
    r = await transport.get(_DIFFSERV_SET_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


@WRITE
async def set_cosproto(
    transport: ProcurveTransport,
    *,
    request: SetCosProtoRequest | None = None,
) -> QosWriteAck:
    """Submit /cgi/cosproto — the Protocol-Priority form.

    # TODO: needs live capture — on the 2810-24G the form's <table> body is
    empty, so the UI only submits the `Apply Changes` button. On a switch
    that exposes protocol rules, additional per-protocol fields appear.
    Wire shape of those fields is unknown.
    """
    params = {"Apply": (request or SetCosProtoRequest()).apply}
    r = await transport.get(_COSPROTO_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return QosWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# monitor sub-tab
# =====================================================================

_MON_PROBE_RE = re.compile(r'var\s+probeStatus\s*=\s*(\d+)\s*;')
_MON_SELECT_BLOCK_RE = re.compile(
    r'<Select\s+Name="?monitoringPort"?.*?</Select>',
    re.IGNORECASE | re.DOTALL,
)
_MON_OPTION_RE = re.compile(
    r'<option\s+value=(\d+)(?P<sel>[^>]*selected)?',
    re.IGNORECASE,
)


@READ
async def get_monitor_page(transport: ProcurveTransport) -> MonitorPage:
    """Scrape /configuration/monitor1.html for mirroring state.

    Not listed in the 24 required ops — added as a convenience read for
    the monitor sub-tab (otherwise write-only). Safe to drop if counts
    run over budget.
    """
    r = await transport.get(_MONITOR_PAGE)
    body = r.text
    m = _MON_PROBE_RE.search(body)
    if not m:
        raise ParseError("monitor1.html: missing probeStatus injection")
    # probeStatus: 1 = monitoring on, 2 = off (per monitor1.html:32).
    enabled = m.group(1) == "1"

    candidates: list[int] = []
    selected: int | None = None
    sel_block = _MON_SELECT_BLOCK_RE.search(body)
    if sel_block:
        for opt in _MON_OPTION_RE.finditer(sel_block.group(0)):
            port = int(opt.group(1))
            candidates.append(port)
            if opt.group("sel"):
                selected = port
    return MonitorPage(
        enabled=enabled,
        candidate_dest_ports=candidates,
        selected_dest_port=selected,
    )


@WRITE
async def set_monitor(
    transport: ProcurveTransport,
    *,
    request: SetMonitorRequest,
) -> ConfigWriteAck:
    """Enable or disable port mirroring via /cgi/set_monitor.

    `portCopyStatus=4` enables (requires dest_port + source_mask);
    `portCopyStatus=2` disables (emits no other fields).
    # TODO: needs live capture — the `portCopySourceMask` bitmask endianness
    (bit 0 = port 1 or port 0?) is unverified.
    """
    if not request.enabled:
        params: dict[str, int | str] = {"portCopyStatus": 2}
    else:
        # The model_validator on SetMonitorRequest guarantees both are non-None
        # when enabled=True; mypy can't see through that so we narrow here.
        if request.dest_port is None or request.source_mask is None:
            raise ValueError("enabling monitoring requires dest_port and source_mask")
        params = {
            "portCopyStatus": 4,
            "portCopyDest": request.dest_port,
            "portCopySourceMask": request.source_mask,
        }
    r = await transport.get(_MONITOR_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# devfeatures sub-tab
# =====================================================================

_FEATURES_IGMP_RE = re.compile(r'var\s+_igmp\s*=\s*(.+?)\s*;')
_FEATURES_ST_RE = re.compile(r'var\s+_st\s*=\s*(.+?)\s*;')
_FEATURES_VLANCOUNT_RE = re.compile(r'var\s+vlanCount\s*=\s*(\d+)\s*;')


def _parse_feature_flag(raw: str) -> bool | None:
    """Decode an injected JS feature flag.

    The template emits `1` (On), `2` (Off), or a literal string like
    `Invalid OID` on multi-VLAN variants where the default VLAN lookup
    failed. Returns None ONLY for the documented `Invalid OID` sentinel;
    any other unexpected value raises ParseError so new firmware revisions
    surface as a parser bug rather than silently becoming None.
    """
    v = raw.strip().strip('"')
    if v == "1":
        return True
    if v == "2":
        return False
    if v == "Invalid OID":
        return None
    raise ParseError(f"unknown feature-flag value {v!r}")


@READ
async def get_devfeatures_page(transport: ProcurveTransport) -> DeviceFeaturesPage:
    """Scrape /configuration/features2.html for IGMP + STP state."""
    r = await transport.get(_FEATURES_PAGE)
    body = r.text
    igmp_m = _FEATURES_IGMP_RE.search(body)
    st_m = _FEATURES_ST_RE.search(body)
    vc_m = _FEATURES_VLANCOUNT_RE.search(body)
    if not igmp_m or not st_m:
        raise ParseError(
            "features2.html: missing _igmp / _st injected vars"
        )
    return DeviceFeaturesPage(
        vlan_count=int(vc_m.group(1)) if vc_m else 1,
        igmp=_parse_feature_flag(igmp_m.group(1)),
        spanning_tree=_parse_feature_flag(st_m.group(1)),
    )


@WRITE
async def set_device_features(
    transport: ProcurveTransport,
    *,
    request: SetDeviceFeaturesRequest,
) -> ConfigWriteAck:
    """Write IGMP / STP feature flags to the correct endpoint variant.

    The switch serves one of five endpoint paths depending on
    `(vlanCount, cripStat)` page-generator state. Caller picks the path via
    `request.endpoint`; `igmp` / `spanning_tree` may be None to omit the
    corresponding field (e.g. globalfeature_set has no IGMP).
    """
    params: dict[str, int | str] = {"indeces": request.vlan_id}
    if request.igmp is not None:
        params["hpSwitchIgmpState"] = "1" if request.igmp else "2"
    if request.spanning_tree is not None:
        params["hpSwitchStpAdminStatus"] = "1" if request.spanning_tree else "2"
    r = await transport.get(request.endpoint, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


# =====================================================================
# support sub-tab
# =====================================================================

_SUP_URL_RE = re.compile(
    r'<input\s+name=(?P<name>_SuppURL|hpHttpMgMgmtSrvrURL)'
    r'\s+value="(?P<value>[^"]*)"',
    re.IGNORECASE,
)


@READ
async def get_support_page(transport: ProcurveTransport) -> SupportPage:
    """Scrape /configuration/support.html for the two URL fields."""
    r = await transport.get(_SUPPORT_PAGE)
    body = r.text
    fields: dict[str, str] = {}
    for m in _SUP_URL_RE.finditer(body):
        fields[m.group("name")] = m.group("value")
    if "_SuppURL" not in fields or "hpHttpMgMgmtSrvrURL" not in fields:
        raise ParseError("support.html: missing URL input(s)")
    return SupportPage(
        support_url=fields["_SuppURL"],
        mgmt_url=fields["hpHttpMgMgmtSrvrURL"],
    )


@WRITE
async def set_support(
    transport: ProcurveTransport,
    *,
    request: SetSupportRequest,
) -> ConfigWriteAck:
    """Write the two support URLs via /cgi/support.

    Preserves the `_SuppURL` underscore prefix and the submit-button value
    with leading/trailing spaces byte-exactly.
    """
    params = {
        "indeces": 0,
        "_SuppURL": request.support_url,
        "hpHttpMgMgmtSrvrURL": request.mgmt_url,
        "apply": _APPLY_CHANGES,
    }
    r = await transport.get(_SUPPORT_CGI, params=params)
    ensure_write_ok(r.status_code, r.text)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)
