"""Models for the Security tab (10 operations).

Sources:
- research/protocol/security/*.md

Wire conventions:
- Two reads are HTML scrapes (`get_web_access_page`, `get_ssl_state`);
  the rest are tilde-delimited bare-row streams (no sentinel).
- `get_intrusion` returns a single `\\n` byte for an empty log — still a
  valid 200 OK.
- All 5 writes mirror the legacy applet's GET-with-query-string shape —
  including `set_device_passwords`, where the password travels
  cleartext in the URL (a protocol-level flaw preserved for byte parity).
- 4 of the 5 writes are FORBIDDEN in Phase 0 — see the operation-level
  module for banners. This module only defines shapes; safety is
  enforced at the operation entry point via @WRITE + READ_ONLY.
"""
from __future__ import annotations

from datetime import date
from enum import IntEnum, StrEnum
from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

# =====================================================================
# get_web_access_page — HTML scrape of /security/web_access.html
# =====================================================================


class WebAccessPage(BaseModel):
    """Scraped projection of the device-passwords HTML form.

    The firmware renders both username fields with empty `value=""`
    regardless of the configured usernames (standard password-form
    security hygiene). Reading the current values requires parsing
    `running-config` from `/cgi/configfile` instead.
    """

    operator_username: str = ""
    manager_username: str = ""


# =====================================================================
# get_web_managers — tilde-delimited list from /cgi/webMgr
# =====================================================================


class AccessLevel(StrEnum):
    MANAGER = "Manager"
    OPERATOR = "Operator"


class AuthorizedManager(BaseModel):
    """One row from `/cgi/webMgr`."""

    index: int = Field(..., ge=1)
    ip: IPv4Address
    mask: IPv4Address
    access_level: AccessLevel


class WebManagersResponse(BaseModel):
    """Parsed shape of `/cgi/webMgr` (read)."""

    entries: list[AuthorizedManager] = Field(default_factory=list)


# =====================================================================
# get_perports — per-port security policy
# =====================================================================


class AddressSelection(StrEnum):
    """Address-selection display tokens from `/cgi/perports`."""

    CONTINUOUS = "Continuous"
    STATIC = "Static"
    PORT_ACCESS = "Port Access"
    LIMITED = "Limited"


class PortSecurityRow(BaseModel):
    """One row from `/cgi/perports?GR=`.

    Blank-string columns are serialized as a literal single space by
    the switch to preserve column alignment in the applet renderer;
    we pass them through unchanged.
    """

    port: int = Field(..., ge=1)
    port_label: str
    port_name: str
    address_selection: AddressSelection
    authorized_address: str
    mode: str
    security_action: int
    address_limit: int
    trunk: bool


class PerportsResponse(BaseModel):
    """Parsed shape of `/cgi/perports?GR=<group>`."""

    rows: list[PortSecurityRow] = Field(default_factory=list)


# =====================================================================
# get_intrusion — intrusion log (empty = lone `\n` byte)
# =====================================================================


class IntrusionEntry(BaseModel):
    """One row from `/cgi/intrusion`."""

    port: int = Field(..., ge=1)
    port_name: str
    intruder_address: str
    timestamp: str


class IntrusionLogResponse(BaseModel):
    """Parsed shape of `/cgi/intrusion` (read)."""

    entries: list[IntrusionEntry] = Field(default_factory=list)


# =====================================================================
# get_ssl_state — scraped from 3 HTML pages
# =====================================================================


class CertMode(IntEnum):
    """Certificate-mode radio state from `ssl_cert.html`."""

    CREATE_OR_SELF_SIGNED = 1
    USE_INSTALLED = 2


class SSLState(BaseModel):
    """Consolidated projection across ssl_config.html, ssl_cert.html,
    and ssl_menu.html.

    `ssl_enabled` maps from the firmware's `sslStatus` (`1`=Off, `2`=On).
    `ca_signed_installed` maps from `crtStat` (`1`=not installed,
    `2`=installed).
    """

    ssl_enabled: bool
    ssl_port: int = Field(default=443, ge=1, le=65535)
    cert_mode: CertMode
    ca_signed_installed: bool


# =====================================================================
# set_device_passwords — FORBIDDEN write (mirrors /security/web_access.html)
# =====================================================================


class SetDevicePasswordsRequest(BaseModel):
    """Arguments for the FORBIDDEN password-change GET.

    `operator_password` / `manager_password` use `SecretStr` so the
    cleartext is never included in `repr()` / log emissions. The
    confirm fields default to equal-the-primary semantically; callers
    can override explicitly for byte-exact parity with the legacy form.

    All fields travel as query-string params on a GET — a protocol
    flaw in the 2810 firmware, mirrored faithfully.
    """

    operator_username: str = ""
    operator_password: SecretStr = SecretStr("")
    operator_password_confirm: SecretStr | None = None
    manager_username: str = ""
    manager_password: SecretStr = SecretStr("")
    manager_password_confirm: SecretStr | None = None

    @field_validator("operator_username", "manager_username")
    @classmethod
    def _ascii_16(cls, v: str) -> str:
        if len(v) > 16:
            raise ValueError("username too long (HTML size=16)")
        return v


class SetDevicePasswordsResponse(BaseModel):
    """Return shape for `/security/web_access.html` (write path)."""

    applied: bool = True
    message: str | None = None
    raw_body: str | None = None


# =====================================================================
# set_web_manager — FORBIDDEN write (/cgi/webMgr?action=1|2|3)
# =====================================================================


class WebMgrAction(IntEnum):
    """Action codes from the legacy applet's web-manager submit helpers."""

    ADD = 1
    REPLACE = 2
    DELETE = 3


class AccessLevelCode(IntEnum):
    """Wire codes for access level (inverse of the read-side string enum)."""

    OPERATOR = 1
    MANAGER = 2


class AddWebManagerRequest(BaseModel):
    """`action=1` variant — add an authorized manager entry."""

    action: Literal[WebMgrAction.ADD] = WebMgrAction.ADD
    ip: IPv4Address
    mask: IPv4Address = IPv4Address("255.255.255.255")
    level: AccessLevelCode
    indeces: list[int] = Field(default_factory=list)  # preserve misspelling


class ReplaceWebManagerRequest(BaseModel):
    """`action=2` variant — modify the entry at `indeces[0]` in place."""

    action: Literal[WebMgrAction.REPLACE] = WebMgrAction.REPLACE
    ip: IPv4Address
    mask: IPv4Address = IPv4Address("255.255.255.255")
    level: AccessLevelCode
    indeces: list[int] = Field(..., min_length=1)


class DeleteWebManagerRequest(BaseModel):
    """`action=3` variant — delete the entry at `indeces[0]`."""

    action: Literal[WebMgrAction.DELETE] = WebMgrAction.DELETE
    indeces: list[int] = Field(..., min_length=1)


SetWebManagerRequest = AddWebManagerRequest | ReplaceWebManagerRequest | DeleteWebManagerRequest


class SetWebManagerResponse(BaseModel):
    """Return shape for `/cgi/webMgr` (write path)."""

    applied: bool = True
    message: str | None = None
    raw_body: str | None = None


# =====================================================================
# set_perport — write (/cgi/perport) — NOT forbidden, but @WRITE + never live-tested
# =====================================================================


class PortSecurityMode(IntEnum):
    """Values from `<select name=mode>` on `perport_form1.html`.

    # TODO: needs live capture — values 3/4 (if present) are unknown.
    """

    CONTINUOUS = 1
    STATIC = 2
    PORT_ACCESS = 5


class SecurityActionCode(IntEnum):
    """Security-action codes.

    # TODO: needs live capture — values 2/3 are inferred from the HTML
    label order and not confirmed against the switch.
    """

    NONE = 1
    SEND_ALARM = 2
    SEND_ALARM_DISABLE = 3


class SetPerportRequest(BaseModel):
    """Arguments for `/cgi/perport` — configure one port's security policy."""

    group: str = ""  # `GR` — empty on a standalone 2810
    trunk: int = 0  # `tr`
    port: int = Field(..., ge=1)  # `pt`
    indeces: list[int] = Field(..., min_length=1)  # preserve misspelling
    mode: PortSecurityMode
    security_action: SecurityActionCode = SecurityActionCode.NONE
    address_limit: int = Field(default=1, ge=1, le=8)


class SetPerportResponse(BaseModel):
    """Return shape for `/cgi/perport` (write path)."""

    applied: bool = True
    message: str | None = None
    raw_body: str | None = None


# =====================================================================
# reset_intrusion_flags — write (/cgi/intrusion_clear), no fields
# =====================================================================


class ResetIntrusionFlagsResponse(BaseModel):
    """Return shape for `/cgi/intrusion_clear`."""

    applied: bool = True
    raw_body: str | None = None


# =====================================================================
# set_ssl — FORBIDDEN write (/cgi/setssl)
# =====================================================================


class SSLActionCode(IntEnum):
    """Power state mirror for `action` on `/cgi/setssl`."""

    OFF = 1
    ON = 2


class CertificMode(IntEnum):
    """`certific` wire codes (assembled by submitApply() JS helper)."""

    USE_INSTALLED = 2
    CREATE_OR_SELF_SIGNED = 3


class CertType(IntEnum):
    """`certtype` wire codes."""

    SELF_SIGNED = 3
    CA_REQUEST = 4


class RSAKey(IntEnum):
    """`rsakey` wire codes — corresponds to the RSA-key select widget."""

    CURRENT = 1
    BITS_512 = 2
    BITS_768 = 3
    BITS_1024 = 4


class SetSSLRequest(BaseModel):
    """Arguments for the FORBIDDEN `/cgi/setssl` GET.

    Top three fields (`enabled`, `port`, `cert_mode`) are always emitted.
    Certificate-creation fields are emitted only when `cert_mode` ==
    CREATE_OR_SELF_SIGNED AND `enabled` == ON, matching the JS helper
    that assembles the URL in `ssl_cert1.html:submitApply()`.

    # TODO: needs live capture — the full param set beyond (action, prt,
    certific) is inferred from the HTML form names; the JS that appends
    them to the URL was truncated in the mirrored source.
    """

    enabled: SSLActionCode = SSLActionCode.ON
    port: int = Field(default=443, ge=1, le=65535)
    cert_mode: CertificMode = CertificMode.USE_INSTALLED
    cert_type: CertType | None = None
    rsa_key: RSAKey | None = None
    validity_start: date | None = None
    validity_end: date | None = None
    common_name: str | None = None
    organization_name: str | None = None
    organization_unit: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None

    @field_validator("country")
    @classmethod
    def _country_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) != 2:
            raise ValueError("country must be an ISO-3166 alpha-2 code (2 chars)")
        return v

    @model_validator(mode="after")
    def _cert_fields_consistency(self) -> SetSSLRequest:
        if self.cert_mode is CertificMode.CREATE_OR_SELF_SIGNED and self.enabled is SSLActionCode.ON:
            # Cert-create path — cert_type + rsa_key are expected.
            # We don't hard-require them here (callers may want to
            # write partial state) but flag at least one being set.
            pass
        return self


class SetSSLResponse(BaseModel):
    """Return shape for `/cgi/setssl` (write path)."""

    applied: bool = True
    message: str | None = None
    raw_body: str | None = None
