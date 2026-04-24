"""Tests for the Security tab (10 operations).

4 of 5 writes are FORBIDDEN per memory/feedback_switch_write_safety.md
(`set_device_passwords`, `set_web_manager`, `set_ssl`). These tests
verify ONLY the URL-construction path via respx mocks and the READ_ONLY
gate — no live switch is contacted.
"""
from __future__ import annotations

from datetime import date
from ipaddress import IPv4Address
from pathlib import Path

import pytest
import respx
from httpx import Response
from pydantic import SecretStr

from procurve_client.errors import OperationError, ParseError, WriteDisabledError
from procurve_client.models.security import (
    AccessLevel,
    AccessLevelCode,
    AddressSelection,
    AddWebManagerRequest,
    CertificMode,
    CertMode,
    CertType,
    DeleteWebManagerRequest,
    PortSecurityMode,
    ReplaceWebManagerRequest,
    ResetIntrusionFlagsResponse,
    RSAKey,
    SecurityActionCode,
    SetDevicePasswordsRequest,
    SetPerportRequest,
    SetSSLRequest,
    SSLActionCode,
)
from procurve_client.operations.security import (
    get_intrusion,
    get_perports,
    get_ssl_state,
    get_web_access_page,
    get_web_managers,
    reset_intrusion_flags,
    set_device_passwords,
    set_perport,
    set_ssl,
    set_web_manager,
)
from procurve_client.transport import ProcurveTransport

HOST = "http://192.0.2.3"


def _fixture(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "research" / "fixtures" / name).read_text(encoding="utf-8")


# =====================================================================
# get_web_access_page (HTML scrape)
# =====================================================================


@respx.mock
async def test_get_web_access_page_live_fixture() -> None:
    body = _fixture("security__get_web_access_page.response.txt")
    respx.get(f"{HOST}/security/web_access.html").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        page = await get_web_access_page(t)
    # Firmware always renders both username values as empty.
    assert page.operator_username == ""
    assert page.manager_username == ""


@respx.mock
async def test_get_web_access_page_synthetic_populated() -> None:
    # Defensive: even if a firmware variant populated value=...,
    # we scrape it verbatim.
    synthetic = (
        '<html><form action="web_access.html">'
        '<input name=_UserName value="operator" size=16>'
        '<input name=_RootName value="admin" size=16>'
        "</form></html>"
    )
    respx.get(f"{HOST}/security/web_access.html").mock(
        return_value=Response(200, text=synthetic)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        page = await get_web_access_page(t)
    assert page.operator_username == "operator"
    assert page.manager_username == "admin"


# =====================================================================
# get_web_managers
# =====================================================================


@respx.mock
async def test_get_web_managers_live_fixture() -> None:
    body = _fixture("security__get_web_managers.response.txt")
    respx.get(f"{HOST}/cgi/webMgr").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_web_managers(t)
    assert len(res.entries) == 2
    e0 = res.entries[0]
    assert e0.index == 1
    assert e0.ip == IPv4Address("192.168.178.22")
    assert e0.mask == IPv4Address("255.255.255.255")
    assert e0.access_level is AccessLevel.MANAGER
    assert res.entries[1].ip == IPv4Address("192.168.178.100")


@respx.mock
async def test_get_web_managers_empty_list() -> None:
    respx.get(f"{HOST}/cgi/webMgr").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_web_managers(t)
    assert res.entries == []


@respx.mock
async def test_get_web_managers_error_sentinel_raises() -> None:
    respx.get(f"{HOST}/cgi/webMgr").mock(
        return_value=Response(200, text="error~unexpected\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError):
            await get_web_managers(t)


@respx.mock
async def test_get_web_managers_unknown_access_level_raises() -> None:
    respx.get(f"{HOST}/cgi/webMgr").mock(
        return_value=Response(
            200, text="1~192.168.178.22~255.255.255.255~SuperAdmin\n"
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_web_managers(t)


# =====================================================================
# get_perports
# =====================================================================


@respx.mock
async def test_get_perports_live_fixture() -> None:
    body = _fixture("security__get_perports.response.txt")
    # The URL preserves the empty `?GR=` key.
    respx.get(f"{HOST}/cgi/perports").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_perports(t)
    # 14 ports in the captured fixture.
    assert len(res.rows) == 14
    r0 = res.rows[0]
    assert r0.port == 7
    assert r0.port_label == "7"
    assert r0.port_name == " "  # literal single space preserved
    assert r0.address_selection is AddressSelection.CONTINUOUS
    assert r0.authorized_address == " "
    assert r0.mode == "None"
    assert r0.security_action == 1
    assert r0.address_limit == 1
    assert r0.trunk is False
    # UPS port: port 18 has a real name.
    ups = next(r for r in res.rows if r.port == 18)
    assert ups.port_name == "UPS"


@respx.mock
async def test_get_perports_empty_body() -> None:
    respx.get(f"{HOST}/cgi/perports").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_perports(t)
    assert res.rows == []


@respx.mock
async def test_get_perports_group_param_preserved() -> None:
    route = respx.get(f"{HOST}/cgi/perports").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await get_perports(t, group="3")
    url = str(route.calls.last.request.url)
    assert url.endswith("?GR=3")


@respx.mock
async def test_get_perports_empty_group_still_emits_key() -> None:
    route = respx.get(f"{HOST}/cgi/perports").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await get_perports(t)
    url = str(route.calls.last.request.url)
    assert url.endswith("?GR=")


# =====================================================================
# get_intrusion
# =====================================================================


@respx.mock
async def test_get_intrusion_live_fixture_empty() -> None:
    body = _fixture("security__get_intrusion.response.txt")
    # Live fixture is a single `\n` byte — empty log.
    assert body == "\n"
    respx.get(f"{HOST}/cgi/intrusion").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_intrusion(t)
    assert res.entries == []


@respx.mock
async def test_get_intrusion_populated_synthetic() -> None:
    respx.get(f"{HOST}/cgi/intrusion").mock(
        return_value=Response(
            200,
            text=(
                "5~Lab-Port~00-11-22-33-44-55~2026-04-23 14:32:01\n"
                "7~ ~AA-BB-CC-DD-EE-FF~2026-04-23 14:33:17\n"
            ),
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_intrusion(t)
    assert len(res.entries) == 2
    assert res.entries[0].port == 5
    assert res.entries[0].port_name == "Lab-Port"
    assert res.entries[0].intruder_address == "00-11-22-33-44-55"
    assert res.entries[1].timestamp == "2026-04-23 14:33:17"


@respx.mock
async def test_get_intrusion_error_sentinel_raises() -> None:
    respx.get(f"{HOST}/cgi/intrusion").mock(
        return_value=Response(200, text="error~log unavailable\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError):
            await get_intrusion(t)


# =====================================================================
# get_ssl_state
# =====================================================================


@respx.mock
async def test_get_ssl_state_live_fixtures() -> None:
    config_body = _fixture("security__get_ssl_config_page.response.txt")
    cert_body = _fixture("security__get_ssl_cert_mode_page.response.txt")
    # No ssl_menu fixture on disk — emulate the crtStat=1 (no CA cert) case.
    menu_body = "<html><script>var crtStat = 1 ;</script></html>"
    respx.get(f"{HOST}/security/ssl_config.html").mock(
        return_value=Response(200, text=config_body)
    )
    respx.get(f"{HOST}/security/ssl_cert.html").mock(
        return_value=Response(200, text=cert_body)
    )
    respx.get(f"{HOST}/security/ssl_menu.html").mock(
        return_value=Response(200, text=menu_body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        state = await get_ssl_state(t)
    # Live fixture: sslStatus=1 (Off), certificateStatus=1 (create/self-signed).
    assert state.ssl_enabled is False
    assert state.ssl_port == 443
    assert state.cert_mode is CertMode.CREATE_OR_SELF_SIGNED
    assert state.ca_signed_installed is False


@respx.mock
async def test_get_ssl_state_enabled_with_installed_cert() -> None:
    respx.get(f"{HOST}/security/ssl_config.html").mock(
        return_value=Response(
            200,
            text=(
                '<script>var sslStatus = 2 ;</script>'
                '<Input Type="TEXT" Name="sslport" Size=5 Value="8443">'
            ),
        )
    )
    respx.get(f"{HOST}/security/ssl_cert.html").mock(
        return_value=Response(
            200, text="<script>var certificateStatus = 2 ;</script>"
        )
    )
    respx.get(f"{HOST}/security/ssl_menu.html").mock(
        return_value=Response(200, text="<script>var crtStat = 2 ;</script>")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        state = await get_ssl_state(t)
    assert state.ssl_enabled is True
    assert state.ssl_port == 8443
    assert state.cert_mode is CertMode.USE_INSTALLED
    assert state.ca_signed_installed is True


@respx.mock
async def test_get_ssl_state_missing_status_raises() -> None:
    respx.get(f"{HOST}/security/ssl_config.html").mock(
        return_value=Response(200, text="<html>no ssl var here</html>")
    )
    respx.get(f"{HOST}/security/ssl_cert.html").mock(
        return_value=Response(
            200, text="<script>var certificateStatus = 1 ;</script>"
        )
    )
    respx.get(f"{HOST}/security/ssl_menu.html").mock(
        return_value=Response(200, text="<script>var crtStat = 1 ;</script>")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_ssl_state(t)


# =====================================================================
# set_device_passwords (FORBIDDEN — only URL construction + READ_ONLY guard)
# =====================================================================


async def test_set_device_passwords_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_device_passwords(
                t,
                request=SetDevicePasswordsRequest(
                    manager_username="admin",
                    manager_password=SecretStr("hunter2"),
                ),
            )


@respx.mock
async def test_set_device_passwords_url_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies URL construction only — never invokes the live switch."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/security/web_access.html").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_device_passwords(
            t,
            request=SetDevicePasswordsRequest(
                operator_username="oper",
                operator_password=SecretStr("opsecret"),
                manager_username="admin",
                manager_password=SecretStr("rootsecret"),
            ),
        )
    url = str(route.calls.last.request.url)
    # All six password/username fields + apply, in declared order.
    assert "_UserName=oper" in url
    assert "_UserPasswd=opsecret" in url
    assert "_UserPasswd2=opsecret" in url  # mirrored from primary when confirm is None
    assert "_RootName=admin" in url
    assert "_RootPasswd=rootsecret" in url
    assert "_RootPasswd2=rootsecret" in url
    # The Apply button value has leading/trailing spaces. httpx encodes
    # spaces in query strings as `+` (form-urlencoded rule), which the
    # 2810 accepts per the HTML form default.
    assert "apply=+Apply+Changes+" in url
    assert res.applied is True


@respx.mock
async def test_set_device_passwords_explicit_confirm_mismatch_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the caller passes an explicit confirm that differs, we emit both
    values byte-exactly (server validates equality)."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/security/web_access.html").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_device_passwords(
            t,
            request=SetDevicePasswordsRequest(
                manager_password=SecretStr("primary"),
                manager_password_confirm=SecretStr("confirmed"),
            ),
        )
    url = str(route.calls.last.request.url)
    assert "_RootPasswd=primary" in url
    assert "_RootPasswd2=confirmed" in url


def test_set_device_passwords_rejects_long_username() -> None:
    with pytest.raises(ValueError):
        SetDevicePasswordsRequest(
            operator_username="x" * 17,
        )


# =====================================================================
# set_web_manager (FORBIDDEN — discriminated union + READ_ONLY guard)
# =====================================================================


async def test_set_web_manager_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_web_manager(
                t,
                request=AddWebManagerRequest(
                    ip=IPv4Address("192.168.178.42"),
                    level=AccessLevelCode.MANAGER,
                ),
            )


@respx.mock
async def test_set_web_manager_add_wire_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/webMgr").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_web_manager(
            t,
            request=AddWebManagerRequest(
                ip=IPv4Address("192.168.178.42"),
                mask=IPv4Address("255.255.255.255"),
                level=AccessLevelCode.MANAGER,
            ),
        )
    url = str(route.calls.last.request.url)
    assert "addr=192.168.178.42" in url
    assert "mask=255.255.255.255" in url
    assert "lvl=2" in url
    assert "action=1" in url
    # Add with no indeces → empty value.
    assert "indeces=" in url
    assert res.applied is True


@respx.mock
async def test_set_web_manager_replace_wire_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/webMgr").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_web_manager(
            t,
            request=ReplaceWebManagerRequest(
                ip=IPv4Address("192.168.178.7"),
                level=AccessLevelCode.OPERATOR,
                indeces=[2],
            ),
        )
    url = str(route.calls.last.request.url)
    assert "addr=192.168.178.7" in url
    assert "lvl=1" in url
    assert "action=2" in url
    assert "indeces=2" in url


@respx.mock
async def test_set_web_manager_delete_omits_addr_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/webMgr").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_web_manager(
            t, request=DeleteWebManagerRequest(indeces=[2])
        )
    url = str(route.calls.last.request.url)
    assert "action=3" in url
    assert "indeces=2" in url
    assert "addr=" not in url
    assert "mask=" not in url
    assert "lvl=" not in url


@respx.mock
async def test_set_web_manager_error_response_captured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/webMgr").mock(
        return_value=Response(200, text="error~Access denied\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_web_manager(
            t, request=DeleteWebManagerRequest(indeces=[1])
        )
    assert res.applied is False
    assert res.message == "Access denied"


# =====================================================================
# set_perport (NOT forbidden, but @WRITE + READ_ONLY guard)
# =====================================================================


async def test_set_perport_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_perport(
                t,
                request=SetPerportRequest(
                    port=18,
                    indeces=[18],
                    mode=PortSecurityMode.STATIC,
                ),
            )


@respx.mock
async def test_set_perport_wire_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/perport").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_perport(
            t,
            request=SetPerportRequest(
                port=18,
                indeces=[18],
                mode=PortSecurityMode.STATIC,
                security_action=SecurityActionCode.SEND_ALARM,
                address_limit=2,
            ),
        )
    url = str(route.calls.last.request.url)
    # Param order mirrors the HTML form declaration.
    assert "GR=" in url
    assert "tr=0" in url
    assert "pt=18" in url
    assert "indeces=18" in url
    assert "mode=2" in url
    assert "sa=2" in url
    assert "adl=2" in url
    assert res.applied is True


@respx.mock
async def test_set_perport_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/perport").mock(
        return_value=Response(200, text="error~port is trunked\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_perport(
            t,
            request=SetPerportRequest(
                port=1,
                indeces=[1],
                mode=PortSecurityMode.CONTINUOUS,
            ),
        )
    assert res.applied is False
    assert res.message == "port is trunked"


# =====================================================================
# reset_intrusion_flags (low-risk; @WRITE only — no FORBIDDEN banner)
# =====================================================================


async def test_reset_intrusion_flags_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await reset_intrusion_flags(t)


@respx.mock
async def test_reset_intrusion_flags_bare_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/intrusion_clear").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await reset_intrusion_flags(t)
    url = str(route.calls.last.request.url)
    # Submit button has no name attr → no query string.
    assert url.endswith("/cgi/intrusion_clear")
    assert "?" not in url
    assert isinstance(res, ResetIntrusionFlagsResponse)
    assert res.applied is True


@respx.mock
async def test_reset_intrusion_flags_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/intrusion_clear").mock(
        return_value=Response(200, text="error~not authorized\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError):
            await reset_intrusion_flags(t)


# =====================================================================
# set_ssl (FORBIDDEN — URL construction + READ_ONLY guard)
# =====================================================================


async def test_set_ssl_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_ssl(
                t,
                request=SetSSLRequest(
                    enabled=SSLActionCode.ON,
                    port=443,
                    cert_mode=CertificMode.USE_INSTALLED,
                ),
            )


@respx.mock
async def test_set_ssl_minimal_wire_shape_installed_cert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setssl").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_ssl(
            t,
            request=SetSSLRequest(
                enabled=SSLActionCode.ON,
                port=443,
                cert_mode=CertificMode.USE_INSTALLED,
            ),
        )
    url = str(route.calls.last.request.url)
    assert "action=2" in url
    assert "prt=443" in url
    assert "certific=2" in url
    # No cert-create fields when cert_mode=USE_INSTALLED.
    assert "certtype=" not in url
    assert "rsakey=" not in url
    assert "cn=" not in url


@respx.mock
async def test_set_ssl_full_cert_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setssl").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_ssl(
            t,
            request=SetSSLRequest(
                enabled=SSLActionCode.ON,
                port=443,
                cert_mode=CertificMode.CREATE_OR_SELF_SIGNED,
                cert_type=CertType.SELF_SIGNED,
                rsa_key=RSAKey.BITS_1024,
                validity_start=date(2026, 1, 1),
                validity_end=date(2036, 1, 1),
                common_name="HP2810_01",
                organization_name="Example",
                organization_unit="IT",
                city="Kamer",
                state="NH",
                country="NL",
            ),
        )
    url = str(route.calls.last.request.url)
    assert "action=2" in url
    assert "certific=3" in url
    assert "certtype=3" in url
    assert "rsakey=4" in url
    assert "startdatem=1" in url
    assert "startdatey=2026" in url
    assert "enddatey=2036" in url
    assert "cn=HP2810_01" in url
    assert "orgname=Example" in url
    assert "country=NL" in url


@respx.mock
async def test_set_ssl_off_omits_cert_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setssl").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_ssl(
            t,
            request=SetSSLRequest(
                enabled=SSLActionCode.OFF,
                port=443,
                cert_mode=CertificMode.CREATE_OR_SELF_SIGNED,
                cert_type=CertType.SELF_SIGNED,
                rsa_key=RSAKey.BITS_512,
            ),
        )
    url = str(route.calls.last.request.url)
    assert "action=1" in url  # OFF
    # Cert-create fields suppressed when not ON, even if cert_mode is CREATE.
    assert "certtype=" not in url
    assert "rsakey=" not in url


def test_set_ssl_rejects_invalid_country_length() -> None:
    with pytest.raises(ValueError):
        SetSSLRequest(country="Netherlands")


# =====================================================================
# All forbidden write ops respect READ_ONLY (grouped redundancy test)
# =====================================================================


async def test_all_forbidden_writes_blocked_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default READ_ONLY=true (unset env) must block all FORBIDDEN writes."""
    monkeypatch.delenv("READ_ONLY", raising=False)
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_device_passwords(
                t, request=SetDevicePasswordsRequest()
            )
        with pytest.raises(WriteDisabledError):
            await set_web_manager(
                t,
                request=AddWebManagerRequest(
                    ip=IPv4Address("192.168.178.1"),
                    level=AccessLevelCode.MANAGER,
                ),
            )
        with pytest.raises(WriteDisabledError):
            await set_ssl(t, request=SetSSLRequest())
        # set_perport and reset_intrusion_flags are @WRITE too.
        with pytest.raises(WriteDisabledError):
            await set_perport(
                t,
                request=SetPerportRequest(
                    port=1,
                    indeces=[1],
                    mode=PortSecurityMode.CONTINUOUS,
                ),
            )
        with pytest.raises(WriteDisabledError):
            await reset_intrusion_flags(t)
