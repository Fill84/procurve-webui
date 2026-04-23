"""Models for the Configuration → Stacking subsystem.

Sources:
- research/protocol/configuration/stacking/*.md (10 ops)

Wire conventions (see individual protocol docs):
- Most stacking reads are tilde-delimited. Two exceptions
  (`get_cmd_name`, `get_applet_length`) use whitespace-delimited shapes.
- Write responses follow a per-line `error~<msg>` / implicit-success
  convention. `set_stack_cfg` uses the same shape; `delete_members` is
  blind-consumed by the Java applet but we parse it defensively.
- `set_members` carries a manager password in the URL query string in
  cleartext — a protocol-level security issue we mirror faithfully.
- `set_members` and `delete_members` require **trailing commas** on
  their `addrs` / `nums` CSV values (byte-exact quirk of the Java
  while-loop concatenation).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---- get_memsinfo ------------------------------------------------------


class StackMemberInfo(BaseModel):
    """One 4-field group from `/cgi/get_memsinfo`.

    The parser drops tokens 1-3 only in the Java applet; we preserve all
    three in `mac_address`, `system_name`, and `extra` so future UIs can
    surface the full shape once the semantics of the trailing field are
    confirmed on a live stacked capture.
    """

    member_index: int
    mac_address: str
    system_name: str
    extra: str = ""


class GetMemsinfoResponse(BaseModel):
    """Parsed shape of `/cgi/get_memsinfo`."""

    member_count: int
    members: list[StackMemberInfo]


# ---- get_stack_cfg -----------------------------------------------------


StackAdminState = Literal["commander", "member", "candidate", "disable"]
EnableDisable = Literal["enable", "disable"]


class StackConfig(BaseModel):
    """Global stacking configuration as reported by `/cgi/get_stack_cfg`.

    Eight ordered tokens per the Java `StackConfig.java:142-150` parser.
    """

    stack_admin_state: str
    disc_admin_state: str
    disc_interval: int
    stack_feature_state: str
    stack_name: str = ""
    command_mac_addr: str = ""
    auto_grab_state: str = "disable"
    auto_join_state: str = "disable"


# ---- get_members -------------------------------------------------------


class StackMember(BaseModel):
    """One record from `/cgi/get_members`.

    Fields are five positional tokens per line; the Java applet uses
    `StringTokenizer(line, "~", true)` with space-substitution when
    `device_type` is empty — we keep the raw string (may be empty).
    """

    switch_num: int
    mac_addr: str
    system_name: str
    device_type: str
    status: str


class GetMembersResponse(BaseModel):
    """Parsed shape of `/cgi/get_members`."""

    members: list[StackMember]


# ---- get_candidates ----------------------------------------------------


class StackCandidate(BaseModel):
    """One row from `/cgi/get_candidates`."""

    mac_addr: str
    system_name: str
    device_type: str


class GetCandidatesResponse(BaseModel):
    """Parsed shape of `/cgi/get_candidates`."""

    candidates: list[StackCandidate]


# ---- get_view_all ------------------------------------------------------


class ViewAllRow(BaseModel):
    """One row from `/cgi/get_view_all`.

    On non-stacked switches the fourth token is a literal `Others:`
    section-header (see protocol doc caveats); we pass it through so
    callers can filter or display it verbatim.
    """

    mac_addr: str
    system_name: str
    stack_status: str
    stack_name: str = ""


class GetViewAllResponse(BaseModel):
    """Parsed shape of `/cgi/get_view_all`."""

    switches: list[ViewAllRow]


# ---- get_cmd_name ------------------------------------------------------


class CmdName(BaseModel):
    """Parsed shape of `/cgi/get_cmd_name` (whitespace-delimited body).

    Two callers, two shapes:
    - `StackControl.java` reads only token 0 (system name).
    - `MemberCandidateList.java` reads 7 tokens: name + 6 MAC segments.

    On our non-stacked switch the body is `HP2810_01 Error in Pdu` —
    four tokens, the last three forming the literal error phrase. In
    that case `is_stacked=False` and `mac_addr=None`.

    On a commander expect 7 tokens: the MAC is reassembled as
    `<s1><s2><s3>-<s4><s5><s6>` (switch-native format).
    """

    is_stacked: bool
    system_name: str
    mac_addr: str | None = None
    error_message: str | None = None


# ---- get_applet_length -------------------------------------------------


class GetAppletLengthResponse(BaseModel):
    """Parsed shape of `/cgi/get_applet_length` (bare integer)."""

    applet_length: int


# ---- set_stack_cfg -----------------------------------------------------


class SetStackCfgRequest(BaseModel):
    """Arguments for `/cgi/set_stack_cfg`.

    Every field is optional; only non-None fields are emitted on the
    wire. Key-ordering is fixed by the Java applet's if-chain at
    `StackConfig.java:442-520`: dp, di, sf, cs, sn, js, ma, ag, aj.

    Values `1` / `2` map to enable / disable for `dp`, `sf`, `cs`,
    `js`, `ag`, `aj`. `sn` and `ma` are arbitrary strings (no
    URL-encoding applied by the applet).
    """

    dp: Literal[1, 2] | None = None
    di: int | None = None
    sf: Literal[1, 2] | None = None
    cs: Literal[1, 2] | None = None
    sn: str | None = None
    js: Literal[1, 2] | None = None
    ma: str | None = None
    ag: Literal[1, 2] | None = None
    aj: Literal[1, 2] | None = None


# ---- set_members -------------------------------------------------------


class SetMembersRequest(BaseModel):
    """Arguments for `/cgi/set_members`.

    SECURITY NOTE: `manager_password` travels cleartext in the URL
    query string — this is a protocol-level flaw in the Java applet
    we mirror faithfully for byte parity. Anyone who can see the HTTP
    request sees the password. Tell your users.

    Wire shape (byte-exact):
        ?addrs=<mac1>,<mac2>,&nums=<n1>,<n2>,&pass=<raw>

    Trailing commas on `addrs` / `nums` are load-bearing — a Java
    `while` loop artefact. Order addrs, nums, pass is fixed.
    """

    mac_addrs: list[str] = Field(..., min_length=1)
    switch_nums: list[int] = Field(..., min_length=1)
    manager_password: str = ""  # noqa: S105 -- intentional cleartext mirror

    @field_validator("switch_nums")
    @classmethod
    def _validate_nums(cls, v: list[int]) -> list[int]:
        for n in v:
            if not (0 <= n <= 15):
                raise ValueError(f"switch_num {n} out of range 0..15")
        return v

    @field_validator("mac_addrs")
    @classmethod
    def _validate_macs(cls, v: list[str]) -> list[str]:
        for m in v:
            if not m:
                raise ValueError("mac_addr cannot be empty")
            if "," in m or "&" in m or "~" in m:
                raise ValueError(f"mac_addr {m!r} contains reserved character")
        return v


class SetMembersError(BaseModel):
    """One error line from a multi-line `set_members` error body."""

    message: str


class SetMembersResponse(BaseModel):
    """Return shape for `/cgi/set_members`.

    `ok` is True iff no line starts with `error~`. `rollback_performed`
    is True when auto-rollback triggered a follow-up `delete_members`
    call because the top-level call returned error lines.
    """

    ok: bool = True
    errors: list[SetMembersError] = Field(default_factory=list)
    raw_body: str | None = None
    rollback_performed: bool = False


# ---- delete_members ----------------------------------------------------


class DeleteMembersRequest(BaseModel):
    """Arguments for `/cgi/delete_members`.

    Wire shape (byte-exact): `?nums=1,2,3,` — trailing comma preserved.
    """

    switch_nums: list[int] = Field(..., min_length=1)

    @field_validator("switch_nums")
    @classmethod
    def _validate_nums(cls, v: list[int]) -> list[int]:
        for n in v:
            if not (0 <= n <= 15):
                raise ValueError(f"switch_num {n} out of range 0..15")
        return v


class DeleteMembersResponse(BaseModel):
    """Return shape for `/cgi/delete_members`.

    Applet blind-consumes the body; we inspect defensively for
    `error~<msg>` lines so callers can surface switch-reported errors.
    """

    ok: bool = True
    error_message: str | None = None
    raw_body: str | None = None


# ---- Shared write ack --------------------------------------------------


class StackWriteAck(BaseModel):
    """Return shape for `/cgi/set_stack_cfg`.

    Success path has any non-`error` leading token (typically empty
    body or `OK~`). Error path has first token `error` and second
    token the human-readable message.
    """

    ok: bool = True
    raw_body: str | None = None
