"""Security tab operations (10 total).

Contracts in research/protocol/security/*.md.

Reads (5):
  - get_web_access_page   GET /security/web_access.html   (HTML scrape)
  - get_web_managers      GET /cgi/webMgr                  (tilde)
  - get_perports          GET /cgi/perports?GR=            (tilde)
  - get_intrusion         GET /cgi/intrusion               (tilde; empty=\\n)
  - get_ssl_state         GET /security/ssl_config.html + ssl_cert.html + ssl_menu.html (HTML scrape)

Writes (5):
  - set_device_passwords  GET /security/web_access.html?...   ⚠️ FORBIDDEN
  - set_web_manager       GET /cgi/webMgr?action=...          ⚠️ FORBIDDEN
  - set_perport           GET /cgi/perport?...                @WRITE only (never live-tested)
  - reset_intrusion_flags GET /cgi/intrusion_clear            @WRITE (low-risk)
  - set_ssl               GET /cgi/setssl?...                 ⚠️ FORBIDDEN

========================================================================
FORBIDDEN-WRITE WARNING

Four operations in this module (`set_device_passwords`, `set_web_manager`,
`set_ssl`, and any future credential/lockout-risking op) are FORBIDDEN
for automated tooling to invoke against the live switch. Risk summary:

- `set_device_passwords`: can lock every client out of the device with no
  recovery short of a physical factory-reset. Password travels cleartext
  in the query string (protocol flaw mirrored).
- `set_web_manager`: can immediately lock the client out via Authorized-
  Manager-list whitelisting; mask misconfigs make management unreachable.
- `set_ssl`: can sever the management session mid-connection by
  enabling/disabling HTTPS or regenerating the server cert.

The user runs these operations manually when they choose, with a
verified backup in hand.

In code terms, the @WRITE decorator + READ_ONLY=true env var form the
enforcement gate. Tests verify URL construction only (via respx), never
invoke the live switch.
========================================================================
"""
from __future__ import annotations

import re
from urllib.parse import quote

from procurve_client._safety import READ, WRITE
from procurve_client.errors import OperationError, ParseError
from procurve_client.models.security import (
    AccessLevel,
    AddressSelection,
    AuthorizedManager,
    CertMode,
    DeleteWebManagerRequest,
    IntrusionEntry,
    IntrusionLogResponse,
    PerportsResponse,
    PortSecurityRow,
    ResetIntrusionFlagsResponse,
    SetDevicePasswordsRequest,
    SetDevicePasswordsResponse,
    SetPerportRequest,
    SetPerportResponse,
    SetSSLRequest,
    SetSSLResponse,
    SetWebManagerRequest,
    SetWebManagerResponse,
    SSLState,
    WebAccessPage,
    WebManagersResponse,
)
from procurve_client.parsing import parse_tilde_lines
from procurve_client.transport import ProcurveTransport

# ---- URL paths --------------------------------------------------------

_WEB_ACCESS_PAGE = "/security/web_access.html"
_WEB_MGR_CGI = "/cgi/webMgr"
_PERPORTS_CGI = "/cgi/perports"
_PERPORT_WRITE_CGI = "/cgi/perport"  # singular — the write-side endpoint
_INTRUSION_CGI = "/cgi/intrusion"
_INTRUSION_CLEAR_CGI = "/cgi/intrusion_clear"
_SSL_CONFIG_PAGE = "/security/ssl_config.html"
_SSL_CERT_PAGE = "/security/ssl_cert.html"
_SSL_MENU_PAGE = "/security/ssl_menu.html"
_SETSSL_CGI = "/cgi/setssl"

# Literal submit-button value (leading/trailing spaces are load-bearing).
_APPLY_CHANGES = " Apply Changes "


# ---- Shared helpers ---------------------------------------------------


def _check_error_line(tokens: tuple[str, ...]) -> str | None:
    """Return the `error~<msg>` message if the tokens lead with `error`."""
    if tokens and tokens[0] == "error":
        return tokens[1] if len(tokens) > 1 else ""
    return None


# =====================================================================
# get_web_access_page (read — HTML scrape)
# =====================================================================

_WA_USERNAME_RE = re.compile(
    r'<input\s+name=(?P<name>_UserName|_RootName)\s+value="(?P<value>[^"]*)"',
    re.IGNORECASE,
)


@READ
async def get_web_access_page(transport: ProcurveTransport) -> WebAccessPage:
    """Fetch `/security/web_access.html` — scrape the username defaults.

    The firmware always renders both username `value=""` attributes as
    empty regardless of the configured usernames (standard password-form
    security hygiene). Callers who need the actual current usernames
    should parse `running-config` via `/cgi/configfile` instead.
    """
    r = await transport.get(_WEB_ACCESS_PAGE)
    body = r.text
    fields: dict[str, str] = {}
    for m in _WA_USERNAME_RE.finditer(body):
        fields[m.group("name")] = m.group("value")
    # We don't require both fields — the switch always returns them empty;
    # a missing one still yields a valid, empty-defaults response.
    return WebAccessPage(
        operator_username=fields.get("_UserName", ""),
        manager_username=fields.get("_RootName", ""),
    )


# =====================================================================
# get_web_managers (read — tilde-delimited)
# =====================================================================


@READ
async def get_web_managers(transport: ProcurveTransport) -> WebManagersResponse:
    """Fetch `/cgi/webMgr` — authorized-manager IP list.

    Each line: `<index>~<ipad>~<ipma>~<accs>`. Empty body = empty list.
    Error shape is a single leading `error~<msg>` line per GenericList
    convention.
    """
    from ipaddress import IPv4Address

    r = await transport.get(_WEB_MGR_CGI)
    rows = parse_tilde_lines(r.text)
    if not rows:
        return WebManagersResponse(entries=[])
    err = _check_error_line(rows[0])
    if err is not None:
        raise OperationError(err)

    entries: list[AuthorizedManager] = []
    for row in rows:
        if len(row) < 4:
            raise ParseError(
                f"get_web_managers: expected 4 tokens per row, got {len(row)}: {row!r}"
            )
        try:
            idx = int(row[0])
        except ValueError as exc:
            raise ParseError(
                f"get_web_managers: index {row[0]!r} not an integer"
            ) from exc
        try:
            access = AccessLevel(row[3])
        except ValueError as exc:
            raise ParseError(
                f"get_web_managers: unknown access level {row[3]!r}"
            ) from exc
        entries.append(
            AuthorizedManager(
                index=idx,
                ip=IPv4Address(row[1]),
                mask=IPv4Address(row[2]),
                access_level=access,
            )
        )
    return WebManagersResponse(entries=entries)


# =====================================================================
# get_perports (read — tilde-delimited, per-port security rows)
# =====================================================================


@READ
async def get_perports(
    transport: ProcurveTransport, *, group: str = ""
) -> PerportsResponse:
    """Fetch `/cgi/perports?GR={group}` — per-port security policy rows.

    `group` is empty on standalone 2810 switches (the applet always
    sends `GR=`). For stacked deployments the caller supplies the
    stack member index.
    """
    # Preserve the empty-key shape `?GR=` byte-exactly when group is "".
    url = f"{_PERPORTS_CGI}?GR={quote(group, safe='')}"
    r = await transport.get(url)
    rows = parse_tilde_lines(r.text)
    if not rows:
        return PerportsResponse(rows=[])
    err = _check_error_line(rows[0])
    if err is not None:
        raise OperationError(err)

    out: list[PortSecurityRow] = []
    for row in rows:
        # Live fixture example: `7~7~ ~Continuous~ ~None~1~1~1~0` = 10
        # tokens. The protocol doc enumerates 9 positions but the wire
        # shape has 10 — the trailing `0` matches the doc's "0 = not in
        # a trunk" so we treat the LAST token as `tr` and the 9th
        # (previously thought to be `tr`) as an unknown additional flag.
        #
        # TODO: needs live capture of a configured-non-continuous port
        # to disambiguate which of row[8]/row[9] is `adl` and which is
        # `tr`. Current mapping is fixture-driven.
        if len(row) < 10:
            raise ParseError(
                f"get_perports: expected 10 tokens, got {len(row)}: {row!r}"
            )
        try:
            port = int(row[0])
            sec_action = int(row[6])
            addr_limit = int(row[7])
            trunk_int = int(row[9])
        except ValueError as exc:
            raise ParseError(f"get_perports: non-integer field in {row!r}") from exc
        try:
            addr_sel = AddressSelection(row[3])
        except ValueError as exc:
            raise ParseError(
                f"get_perports: unknown address selection {row[3]!r}"
            ) from exc
        out.append(
            PortSecurityRow(
                port=port,
                port_label=row[1],
                port_name=row[2],
                address_selection=addr_sel,
                authorized_address=row[4],
                mode=row[5],
                security_action=sec_action,
                address_limit=addr_limit,
                trunk=trunk_int == 1,
            )
        )
    return PerportsResponse(rows=out)


# =====================================================================
# get_intrusion (read — tilde-delimited, empty = lone \n)
# =====================================================================


@READ
async def get_intrusion(transport: ProcurveTransport) -> IntrusionLogResponse:
    """Fetch `/cgi/intrusion` — intrusion log.

    Empty log renders as a single `\\n` byte; `parse_tilde_lines` skips
    blank lines, so we get `[]` back automatically.
    """
    r = await transport.get(_INTRUSION_CGI)
    rows = parse_tilde_lines(r.text)
    if not rows:
        return IntrusionLogResponse(entries=[])
    err = _check_error_line(rows[0])
    if err is not None:
        raise OperationError(err)

    entries: list[IntrusionEntry] = []
    for row in rows:
        if len(row) < 4:
            raise ParseError(
                f"get_intrusion: expected 4 tokens, got {len(row)}: {row!r}"
            )
        try:
            port = int(row[0])
        except ValueError as exc:
            raise ParseError(
                f"get_intrusion: port {row[0]!r} not an integer"
            ) from exc
        entries.append(
            IntrusionEntry(
                port=port,
                port_name=row[1],
                intruder_address=row[2],
                timestamp=row[3],
            )
        )
    return IntrusionLogResponse(entries=entries)


# =====================================================================
# get_ssl_state (read — HTML scrape across 3 pages)
# =====================================================================

_SSL_STATUS_RE = re.compile(r"\bvar\s+sslStatus\s*=\s*(\d+)\s*;")
_SSL_PORT_RE = re.compile(
    r'<Input\s+Type="TEXT"\s+Name="sslport"[^>]*Value="(\d+)"',
    re.IGNORECASE,
)
_SSL_CERT_STATUS_RE = re.compile(r"\bvar\s+certificateStatus\s*=\s*(\d+)\s*;")
_SSL_CRT_STAT_RE = re.compile(r"\bvar\s+crtStat\s*=\s*(\d+)\s*;")


@READ
async def get_ssl_state(transport: ProcurveTransport) -> SSLState:
    """Fetch the three SSL HTML pages and merge scraped state.

    The switch exposes no tilde CGI for SSL; state is baked into JS
    initializers and HTML form attributes across three pages:

    - `ssl_config.html` → `sslStatus` (power state) + sslport value
    - `ssl_cert.html`   → `certificateStatus` (create vs. use-installed)
    - `ssl_menu.html`   → `crtStat` (CA-signed cert installed?)
    """
    r_config = await transport.get(_SSL_CONFIG_PAGE)
    r_cert = await transport.get(_SSL_CERT_PAGE)
    r_menu = await transport.get(_SSL_MENU_PAGE)

    status_m = _SSL_STATUS_RE.search(r_config.text)
    if not status_m:
        raise ParseError("ssl_config.html: missing `var sslStatus = <n>;`")
    port_m = _SSL_PORT_RE.search(r_config.text)
    # Port default is 443 per the HTML when absent; but the mirror always
    # ships it, so treat missing as a parse error.
    if not port_m:
        raise ParseError("ssl_config.html: missing sslport Value=\"...\"")

    cert_m = _SSL_CERT_STATUS_RE.search(r_cert.text)
    if not cert_m:
        raise ParseError("ssl_cert.html: missing `var certificateStatus = <n>;`")

    # crtStat may be absent on firmwares that don't render it — treat as
    # "not installed" (False) when missing rather than ParseError.
    crt_m = _SSL_CRT_STAT_RE.search(r_menu.text)
    ca_installed = crt_m is not None and int(crt_m.group(1)) == 2

    status = int(status_m.group(1))
    try:
        cert_mode = CertMode(int(cert_m.group(1)))
    except ValueError as exc:
        raise ParseError(
            f"ssl_cert.html: unknown certificateStatus value {cert_m.group(1)!r}"
        ) from exc

    return SSLState(
        ssl_enabled=status == 2,
        ssl_port=int(port_m.group(1)),
        cert_mode=cert_mode,
        ca_signed_installed=ca_installed,
    )


# =====================================================================
# set_device_passwords — FORBIDDEN write
# =====================================================================


@WRITE
async def set_device_passwords(
    transport: ProcurveTransport,
    *,
    request: SetDevicePasswordsRequest,
) -> SetDevicePasswordsResponse:
    """⚠️ FORBIDDEN for automated tooling — only the operator runs this manually.
    Users run this operation manually when they choose.

    GET `/security/web_access.html?<password fields>` — sets the Manager
    and Operator usernames/passwords. The password travels cleartext in
    the URL query string (a protocol-level flaw in the 2810 firmware
    that we mirror faithfully).

    Setting the Manager password will immediately require Basic auth on
    the next request — including the confirmation read. Callers must
    stash the new credentials before issuing this GET and retry with
    them if the first request closes the connection.

    # TODO: needs live capture under user supervision — confirmation-page
    shape and error-sentinel format are unknown (forbidden to live-test
    in Phase 0).
    """
    # Mirror the confirm fields to the primary when None.
    op_pw = request.operator_password.get_secret_value()
    op_pw2 = (
        request.operator_password_confirm.get_secret_value()
        if request.operator_password_confirm is not None
        else op_pw
    )
    root_pw = request.manager_password.get_secret_value()
    root_pw2 = (
        request.manager_password_confirm.get_secret_value()
        if request.manager_password_confirm is not None
        else root_pw
    )
    params: list[tuple[str, str]] = [
        ("_UserName", request.operator_username),
        ("_UserPasswd", op_pw),
        ("_UserPasswd2", op_pw2),
        ("_RootName", request.manager_username),
        ("_RootPasswd", root_pw),
        ("_RootPasswd2", root_pw2),
        ("apply", _APPLY_CHANGES),
    ]
    r = await transport.get(_WEB_ACCESS_PAGE, params=params)
    return SetDevicePasswordsResponse(applied=True, raw_body=r.text or None)


# =====================================================================
# set_web_manager — FORBIDDEN write
# =====================================================================


def _format_indeces_csv(items: list[int]) -> str:
    """Join row indices with commas. Empty list → empty string."""
    return ",".join(str(i) for i in items)


@WRITE
async def set_web_manager(
    transport: ProcurveTransport,
    *,
    request: SetWebManagerRequest,
) -> SetWebManagerResponse:
    """⚠️ FORBIDDEN for automated tooling — only the operator runs this manually.
    Users run this operation manually when they choose.

    GET `/cgi/webMgr?action=<1|2|3>&<fields>` — add/replace/delete an
    authorized-manager entry. Risk: a bad mask or deleting the client's
    own row can immediately lock the caller out of the web UI.

    The request is a discriminated union: `AddWebManagerRequest`,
    `ReplaceWebManagerRequest`, or `DeleteWebManagerRequest`.

    Field order on the wire preserves the applet's
    `submitMultipleItems('../cgi/webMgr', param-string, ...)` helper —
    `addr, mask, lvl, action, indeces` for add/replace, and just
    `action, indeces` for delete.

    # TODO: needs live capture under user supervision — response-body
    shape is unknown (forbidden to live-test in Phase 0).
    """
    params: list[tuple[str, str]]
    action_int = int(request.action)
    if isinstance(request, DeleteWebManagerRequest):
        # Delete — only action + indeces.
        params = [
            ("action", str(action_int)),
            ("indeces", _format_indeces_csv(request.indeces)),
        ]
    else:
        # Add or Replace — full add/replace schema.
        params = [
            ("addr", str(request.ip)),
            ("mask", str(request.mask)),
            ("lvl", str(int(request.level))),
            ("action", str(action_int)),
            ("indeces", _format_indeces_csv(request.indeces)),
        ]
    r = await transport.get(_WEB_MGR_CGI, params=params)
    body = r.text
    errors = [_check_error_line(row) for row in parse_tilde_lines(body)]
    first_error = next((e for e in errors if e is not None), None)
    if first_error is not None:
        return SetWebManagerResponse(
            applied=False, message=first_error, raw_body=body or None
        )
    return SetWebManagerResponse(applied=True, raw_body=body or None)


# =====================================================================
# set_perport — write (NOT forbidden, but never live-tested)
# =====================================================================


@WRITE
async def set_perport(
    transport: ProcurveTransport,
    *,
    request: SetPerportRequest,
) -> SetPerportResponse:
    """GET `/cgi/perport?GR=&tr=&pt=&indeces=&mode=&sa=&adl=` — configure
    one port's security policy.

    Not in the "absolutely forbidden" set (it's a normal data-plane
    write), but we have not live-tested it in Phase 0. Under the
    general write-safety rule we defer invocation until a verified
    backup is in hand.

    Param order mirrors the HTML form declaration (GR, tr, pt, indeces,
    mode, sa, adl). The `indeces` misspelling is preserved on the wire.

    # TODO: needs live capture — response-body shape is unverified.
    # TODO: needs live capture — values for PortSecurityMode other than
    1/2/5 and SecurityActionCode 2/3 are inferred from the HTML label
    order; full enum set is unconfirmed.
    """
    params: list[tuple[str, str]] = [
        ("GR", request.group),
        ("tr", str(request.trunk)),
        ("pt", str(request.port)),
        ("indeces", _format_indeces_csv(request.indeces)),
        ("mode", str(int(request.mode))),
        ("sa", str(int(request.security_action))),
        ("adl", str(request.address_limit)),
    ]
    r = await transport.get(_PERPORT_WRITE_CGI, params=params)
    body = r.text
    errors = [_check_error_line(row) for row in parse_tilde_lines(body)]
    first_error = next((e for e in errors if e is not None), None)
    if first_error is not None:
        return SetPerportResponse(
            applied=False, message=first_error, raw_body=body or None
        )
    return SetPerportResponse(applied=True, raw_body=body or None)


# =====================================================================
# reset_intrusion_flags — write (low-risk; @WRITE only)
# =====================================================================


@WRITE
async def reset_intrusion_flags(
    transport: ProcurveTransport,
) -> ResetIntrusionFlagsResponse:
    """GET `/cgi/intrusion_clear` — clear all intrusion alert flags.

    The submit button has no `name` attribute per the HTML
    (`intrusion2.html:8`), so the browser omits it and the request
    carries no query string. We mirror that byte-exactly.

    Low-risk — only clears cosmetic alert flags; does not reconfigure
    anything or erase the intrusion log itself. Still gated by @WRITE
    / READ_ONLY per the general write-safety rule.

    # TODO: needs live capture — response-body shape is unverified.
    """
    r = await transport.get(_INTRUSION_CLEAR_CGI)
    body = r.text
    errors = [_check_error_line(row) for row in parse_tilde_lines(body)]
    first_error = next((e for e in errors if e is not None), None)
    if first_error is not None:
        raise OperationError(first_error)
    return ResetIntrusionFlagsResponse(applied=True, raw_body=body or None)


# =====================================================================
# set_ssl — FORBIDDEN write
# =====================================================================


@WRITE
async def set_ssl(
    transport: ProcurveTransport,
    *,
    request: SetSSLRequest,
) -> SetSSLResponse:
    """⚠️ FORBIDDEN for automated tooling — only the operator runs this manually.
    Users run this operation manually when they choose.

    GET `/cgi/setssl?action=<1|2>&prt=...&certific=...&...` — configure
    the SSL subsystem (enable/disable HTTPS, swap or create server
    certificate, etc.). Invoking this can sever the current management
    session mid-connection or regenerate the server cert at a moment
    that breaks the browser's trust chain.

    Top three fields (`action`, `prt`, `certific`) are always emitted.
    Certificate-creation fields are included when `cert_mode ==
    CREATE_OR_SELF_SIGNED` AND `enabled == ON`, matching the JS helper
    `submitApply()` in `ssl_cert1.html`.

    # TODO: needs live capture under user supervision — full parameter
    set beyond (action, prt, certific) is inferred from the HTML form
    names; the JS that appends them to the URL was truncated in the
    mirrored source. Response-body shape is unknown.
    """
    params: list[tuple[str, str]] = [
        ("action", str(int(request.enabled))),
        ("prt", str(request.port)),
        ("certific", str(int(request.cert_mode))),
    ]
    # Cert-creation fields only when creating / self-signing AND enabled.
    if (
        request.cert_mode == 3  # CertificMode.CREATE_OR_SELF_SIGNED
        and int(request.enabled) == 2  # SSLActionCode.ON
    ):
        if request.cert_type is not None:
            params.append(("certtype", str(int(request.cert_type))))
        if request.rsa_key is not None:
            params.append(("rsakey", str(int(request.rsa_key))))
        if request.validity_start is not None:
            params.append(("startdatem", str(request.validity_start.month)))
            params.append(("startdated", str(request.validity_start.day)))
            params.append(("startdatey", str(request.validity_start.year)))
        if request.validity_end is not None:
            params.append(("enddatem", str(request.validity_end.month)))
            params.append(("enddated", str(request.validity_end.day)))
            params.append(("enddatey", str(request.validity_end.year)))
        if request.common_name is not None:
            params.append(("cn", request.common_name))
        if request.organization_name is not None:
            params.append(("orgname", request.organization_name))
        if request.organization_unit is not None:
            params.append(("orgunit", request.organization_unit))
        if request.city is not None:
            params.append(("city", request.city))
        if request.state is not None:
            params.append(("state", request.state))
        if request.country is not None:
            params.append(("country", request.country))
    r = await transport.get(_SETSSL_CGI, params=params)
    body = r.text
    # Defensive error-line parsing.
    errors = [_check_error_line(row) for row in parse_tilde_lines(body)]
    first_error = next((e for e in errors if e is not None), None)
    if first_error is not None:
        return SetSSLResponse(applied=False, message=first_error, raw_body=body or None)
    return SetSSLResponse(applied=True, raw_body=body or None)


# Acknowledge unused imports (we re-export via models if the caller wants).
__all__ = [
    "get_intrusion",
    "get_perports",
    "get_ssl_state",
    "get_web_access_page",
    "get_web_managers",
    "reset_intrusion_flags",
    "set_device_passwords",
    "set_perport",
    "set_ssl",
    "set_web_manager",
]

