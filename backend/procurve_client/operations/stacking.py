"""Configuration → Stacking subsystem operations (10 total).

Contracts in research/protocol/configuration/stacking/*.md.

Reads (7):
  - get_memsinfo          /cgi/get_memsinfo        (tilde, count + 4-token groups)
  - get_stack_cfg         /cgi/get_stack_cfg       (tilde, 8 tokens, one line)
  - get_members           /cgi/get_members         (tilde, one member per line)
  - get_candidates        /cgi/get_candidates      (tilde, one candidate per line)
  - get_view_all          /cgi/get_view_all        (tilde, one switch per line)
  - get_cmd_name          /cgi/get_cmd_name        (whitespace — unique shape)
  - get_applet_length     /cgi/get_applet_length   (whitespace — bare integer)

Writes (3):
  - set_stack_cfg         /cgi/set_stack_cfg
  - set_members           /cgi/set_members         (interleaved, cleartext pass)
  - delete_members        /cgi/delete_members      (trailing comma on nums=)

Wire quirks that MUST be preserved byte-exactly:
  - `set_members` and `delete_members` carry trailing commas on their
    CSV parameters (`addrs=a,b,` / `nums=1,2,`). We assemble the query
    string manually rather than relying on httpx's serialiser.
  - `set_members` puts the manager password in the URL query string
    in cleartext — a protocol flaw mirrored for parity. Callers must
    warn end users.
  - `get_cmd_name` is whitespace-delimited, not tilde. On non-stacked
    switches the body is `HP2810_01 Error in Pdu` (4 tokens); on a
    commander expect 7 tokens (name + 6 MAC segments).

"needs live capture" TODOs: read fixtures for 6/7 reads exist but all
were captured on a **non-stacked** switch, so the populated-shape
parsers (especially `get_view_all`, `get_candidates`, `get_memsinfo`
member groups) are driven by the Java parser semantics and not
verified byte-for-byte against real multi-member traffic.
"""
from __future__ import annotations

import httpx

from procurve_client._safety import READ, WRITE
from procurve_client.errors import OperationError, ParseError
from procurve_client.models.stacking import (
    CmdName,
    DeleteMembersRequest,
    DeleteMembersResponse,
    GetAppletLengthResponse,
    GetCandidatesResponse,
    GetMembersResponse,
    GetMemsinfoResponse,
    GetViewAllResponse,
    SetMembersError,
    SetMembersRequest,
    SetMembersResponse,
    SetStackCfgRequest,
    StackCandidate,
    StackConfig,
    StackMember,
    StackMemberInfo,
    StackWriteAck,
    ViewAllRow,
)
from procurve_client.parsing import parse_tilde_lines, parse_tilde_row
from procurve_client.transport import ProcurveTransport

# ---- URL paths --------------------------------------------------------

_GET_MEMSINFO = "/cgi/get_memsinfo"
_GET_STACK_CFG = "/cgi/get_stack_cfg"
_GET_MEMBERS = "/cgi/get_members"
_GET_CANDIDATES = "/cgi/get_candidates"
_GET_VIEW_ALL = "/cgi/get_view_all"
_GET_CMD_NAME = "/cgi/get_cmd_name"
_GET_APPLET_LENGTH = "/cgi/get_applet_length"

_SET_STACK_CFG = "/cgi/set_stack_cfg"
_SET_MEMBERS = "/cgi/set_members"
_DELETE_MEMBERS = "/cgi/delete_members"


# ---- Shared helpers ---------------------------------------------------


def _check_error_line(tokens: tuple[str, ...]) -> str | None:
    """Return the `error~<msg>` message if the line is an error, else None."""
    if tokens and tokens[0] == "error":
        return tokens[1] if len(tokens) > 1 else ""
    return None


# =====================================================================
# Reads
# =====================================================================


@READ
async def get_memsinfo(transport: ProcurveTransport) -> GetMemsinfoResponse:
    """Fetch `/cgi/get_memsinfo` — stack member-info summary.

    Body is a single tilde-delimited line:
        `<count>~<idx0>~<mac0>~<name0>~<extra0>~<idx1>~<mac1>~...`

    On our non-stacked fixture `count=0` but one commander-self group
    still follows. We parse however many complete 4-field groups are
    present after the count token; extras are tolerated.
    """
    r = await transport.get(_GET_MEMSINFO)
    text = r.text.strip()
    if not text:
        raise ParseError("get_memsinfo: empty body")
    # Do NOT use parse_tilde_row — it drops a trailing empty field from
    # the final `~`, but the 4th token per group (the "extra" field) is
    # legitimately empty on our non-stacked fixture. Split raw and keep
    # the trailing empty as data; pad with "" if the body is short by one.
    tokens = text.split("~")
    if not tokens:
        raise ParseError("get_memsinfo: no tokens")
    try:
        count = int(tokens[0])
    except ValueError as exc:
        raise ParseError(
            f"get_memsinfo: first token {tokens[0]!r} is not an integer"
        ) from exc

    members: list[StackMemberInfo] = []
    rest = tokens[1:]
    # Pad the tail if the final group is short by at most 1 token (the
    # trailing-empty-field case — most commonly on the commander self
    # record whose last field is empty).
    if len(rest) % 4 == 3:
        rest = rest + [""]
    if len(rest) % 4:
        # Short by 2+ tokens — the response was cut off mid-group; raise
        # rather than silently parsing a shorter valid member list.
        raise ParseError(
            f"get_memsinfo: truncated 4-token group stream ({len(rest)} tokens)"
        )
    for i in range(0, len(rest), 4):
        raw_idx = rest[i]
        try:
            member_index = int(raw_idx)
        except ValueError as exc:
            raise ParseError(
                f"get_memsinfo: member index {raw_idx!r} not an integer"
            ) from exc
        members.append(
            StackMemberInfo(
                member_index=member_index,
                mac_address=rest[i + 1],
                system_name=rest[i + 2],
                extra=rest[i + 3],
            )
        )
    return GetMemsinfoResponse(member_count=count, members=members)


@READ
async def get_stack_cfg(transport: ProcurveTransport) -> StackConfig:
    """Fetch `/cgi/get_stack_cfg` — 8-token stacking config line.

    # TODO: needs live capture on a commander switch — on our non-stacked
    2810 the endpoint returns HTTP 404. Parser shape is driven by
    StackConfig.java:142-150 and hypothetical example in the protocol doc.
    """
    r = await transport.get(_GET_STACK_CFG)
    text = r.text.strip()
    if not text:
        raise ParseError("get_stack_cfg: empty body")
    tokens = list(parse_tilde_row(text))
    err = _check_error_line(tuple(tokens))
    if err is not None:
        raise OperationError(err)
    if len(tokens) < 8:
        raise ParseError(
            f"get_stack_cfg: expected 8 tokens, got {len(tokens)}: {tokens!r}"
        )
    try:
        disc_interval = int(tokens[2])
    except ValueError as exc:
        raise ParseError(
            f"get_stack_cfg: disc_interval {tokens[2]!r} not an integer"
        ) from exc
    return StackConfig(
        stack_admin_state=tokens[0],
        disc_admin_state=tokens[1],
        disc_interval=disc_interval,
        stack_feature_state=tokens[3],
        stack_name=tokens[4],
        command_mac_addr=tokens[5],
        auto_grab_state=tokens[6],
        auto_join_state=tokens[7],
    )


@READ
async def get_members(transport: ProcurveTransport) -> GetMembersResponse:
    """Fetch `/cgi/get_members` — one member per line, 5 tokens each.

    Empty body (fixture shape on our non-stacked switch) is a valid
    "no members" response.

    # TODO: needs live capture on a stacked commander — the populated
    shape is inferred from MemberCandidateList.java:522-567.
    """
    r = await transport.get(_GET_MEMBERS)
    rows = parse_tilde_lines(r.text)
    if not rows:
        return GetMembersResponse(members=[])
    # First-line error sentinel per MemberCandidateList.java:535-539.
    err = _check_error_line(rows[0])
    if err is not None:
        raise OperationError(err)

    members: list[StackMember] = []
    for row in rows:
        if len(row) < 5:
            raise ParseError(
                f"get_members: expected 5 tokens per line, got {len(row)}: {row!r}"
            )
        try:
            switch_num = int(row[0])
        except ValueError as exc:
            raise ParseError(
                f"get_members: switch_num {row[0]!r} not an integer"
            ) from exc
        members.append(
            StackMember(
                switch_num=switch_num,
                mac_addr=row[1],
                system_name=row[2],
                device_type=row[3],
                status=row[4],
            )
        )
    return GetMembersResponse(members=members)


@READ
async def get_candidates(transport: ProcurveTransport) -> GetCandidatesResponse:
    """Fetch `/cgi/get_candidates` — one candidate per line, 3 tokens each.

    Empty body is a valid "no candidates" response.

    # TODO: needs live capture on a commander within discovery range of
    at least one candidate — populated shape is inferred from
    MemberCandidateList.java:569-594.
    """
    r = await transport.get(_GET_CANDIDATES)
    rows = parse_tilde_lines(r.text)
    if not rows:
        return GetCandidatesResponse(candidates=[])
    err = _check_error_line(rows[0])
    if err is not None:
        raise OperationError(err)

    candidates: list[StackCandidate] = []
    for row in rows:
        if len(row) < 3:
            raise ParseError(
                f"get_candidates: expected 3 tokens per line, got {len(row)}: {row!r}"
            )
        # Java trims leading space from device_type (:583-585).
        device_type = row[2].lstrip(" ")
        candidates.append(
            StackCandidate(
                mac_addr=row[0],
                system_name=row[1],
                device_type=device_type,
            )
        )
    return GetCandidatesResponse(candidates=candidates)


@READ
async def get_view_all(transport: ProcurveTransport) -> GetViewAllResponse:
    """Fetch `/cgi/get_view_all` — one switch per line, 4 tokens each.

    On non-stacked switches the fourth token is the literal section-header
    `Others:`; we pass it through unchanged rather than filter it out
    here (callers can check `stack_name == "Others:"`).

    # TODO: needs live capture on a commander — the populated shape is
    inferred from MemberCandidateList.java:595-613 and may vary.
    """
    r = await transport.get(_GET_VIEW_ALL)
    rows = parse_tilde_lines(r.text)
    if not rows:
        return GetViewAllResponse(switches=[])
    err = _check_error_line(rows[0])
    if err is not None:
        raise OperationError(err)

    switches: list[ViewAllRow] = []
    for row in rows:
        if len(row) < 3:
            raise ParseError(
                f"get_view_all: expected 3-4 tokens per line, got {len(row)}: {row!r}"
            )
        stack_name = row[3] if len(row) >= 4 else ""
        switches.append(
            ViewAllRow(
                mac_addr=row[0],
                system_name=row[1],
                stack_status=row[2],
                stack_name=stack_name,
            )
        )
    return GetViewAllResponse(switches=switches)


@READ
async def get_cmd_name(transport: ProcurveTransport) -> CmdName:
    """Fetch `/cgi/get_cmd_name` — whitespace-delimited (NOT tilde).

    Two observed shapes:
    - Stacked commander (7 tokens): `name s1 s2 s3 s4 s5 s6` where
      `s1..s6` are 2-hex MAC segments. We reassemble as
      `<s1><s2><s3>-<s4><s5><s6>`.
    - Non-stacked (4+ tokens, fixture shape): `HP2810_01 Error in Pdu`.
      is_stacked=False, mac_addr=None, error_message="Error in Pdu".

    # TODO: needs live capture on a commander — the 7-token MAC
    segmentation is inferred from MemberCandidateList.java:259-260.
    """
    r = await transport.get(_GET_CMD_NAME)
    text = r.text.strip()
    if not text:
        raise ParseError("get_cmd_name: empty body")
    tokens = text.split()
    if not tokens:
        raise ParseError("get_cmd_name: no tokens")
    system_name = tokens[0]

    # Stacked commander shape: exactly 7 whitespace tokens.
    if len(tokens) == 7:
        mac_addr = (
            f"{tokens[1]}{tokens[2]}{tokens[3]}-"
            f"{tokens[4]}{tokens[5]}{tokens[6]}"
        )
        return CmdName(
            is_stacked=True,
            system_name=system_name,
            mac_addr=mac_addr,
        )

    # Any other shape — non-stacked / error response from stacking subsystem.
    # Drop the system_name and treat the rest as an error phrase.
    error_message = " ".join(tokens[1:]) if len(tokens) > 1 else None
    return CmdName(
        is_stacked=False,
        system_name=system_name,
        mac_addr=None,
        error_message=error_message,
    )


@READ
async def get_applet_length(
    transport: ProcurveTransport, *, member_num: int | None = None
) -> GetAppletLengthResponse:
    """Fetch `/cgi/get_applet_length` — single integer token.

    When `member_num` is None (or 0) the URL is the commander path
    `/cgi/get_applet_length`; otherwise the commander proxies to
    `/sw{N}/cgi/get_applet_length` per StackControl.java:115.
    """
    if member_num is None or member_num == 0:
        url = _GET_APPLET_LENGTH
    else:
        if not (1 <= member_num <= 15):
            raise ValueError(f"member_num {member_num} out of range 1..15")
        url = f"/sw{member_num}/cgi/get_applet_length"
    r = await transport.get(url)
    text = r.text.strip()
    if not text:
        raise ParseError("get_applet_length: empty body")
    # Whitespace-delimited; take only the first token of the first line.
    first_token = text.split()[0]
    try:
        applet_length = int(first_token)
    except ValueError as exc:
        raise ParseError(
            f"get_applet_length: first token {first_token!r} not an integer"
        ) from exc
    return GetAppletLengthResponse(applet_length=applet_length)


# =====================================================================
# Writes
# =====================================================================


def _parse_stack_write_response(body: str) -> StackWriteAck:
    """Parse a `set_stack_cfg` response.

    Success path: first token is not `error` (typically empty or `OK~`).
    Error path: first token is `error`, second token is message.
    """
    text = body.strip()
    if not text:
        return StackWriteAck(ok=True, raw_body=body or None)
    tokens = list(parse_tilde_row(text))
    err = _check_error_line(tuple(tokens))
    if err is not None:
        raise OperationError(err)
    return StackWriteAck(ok=True, raw_body=body)


@WRITE
async def set_stack_cfg(
    transport: ProcurveTransport, *, request: SetStackCfgRequest
) -> StackWriteAck:
    """Set stacking config via `/cgi/set_stack_cfg?<k=v&...>`.

    The applet emits fields in a fixed order (`dp, di, sf, cs, sn, js,
    ma, ag, aj`) and diff-emits only the fields that changed. Python
    callers may emit any subset; we preserve the applet's key order.

    No URL-encoding per StackConfig.java:442-520. We emit the query
    string manually to avoid httpx applying quoting to `sn` / `ma`
    values that the switch does not expect to be percent-encoded.

    # TODO: needs live capture on a stacked commander — error-shape
    parser is driven by StackConfig.java:544-550 only.
    """
    # Fixed applet order.
    field_order: list[tuple[str, object | None]] = [
        ("dp", request.dp),
        ("di", request.di),
        ("sf", request.sf),
        ("cs", request.cs),
        ("sn", request.sn),
        ("js", request.js),
        ("ma", request.ma),
        ("ag", request.ag),
        ("aj", request.aj),
    ]
    parts = [f"{k}={v}" for k, v in field_order if v is not None]
    if not parts:
        # The applet short-circuits at StackConfig.java:522-524 when the
        # diff is empty. Mirror that: no-op.
        return StackWriteAck(ok=True, raw_body=None)
    url = f"{_SET_STACK_CFG}?{'&'.join(parts)}"
    r = await transport.get(url)
    return _parse_stack_write_response(r.text)


def _collect_error_lines(body: str) -> list[SetMembersError]:
    """Extract every `error~<msg>` line from a multi-line set_members body."""
    errors: list[SetMembersError] = []
    for row in parse_tilde_lines(body):
        err = _check_error_line(row)
        if err is not None:
            errors.append(SetMembersError(message=err))
    return errors


# ---------------------------------------------------------------------
# Internal helpers (no @WRITE gate)
# ---------------------------------------------------------------------
# Pattern note: the public `delete_members` carries the `@WRITE` decorator
# (the canonical READ_ONLY boundary). `_delete_members_impl` below is the
# shared URL-building and HTTP helper it delegates to. Internal callers
# that are already inside a gated write path (e.g. `set_members` rollback)
# invoke the impl directly so rollback cannot be suppressed by a race on
# the env var. The impl is NEVER called from outside this module.


async def _delete_members_impl(
    transport: ProcurveTransport, nums: list[int]
) -> httpx.Response:
    """Internal helper: issue `/cgi/delete_members?nums=<n1>,<n2>,`.

    Used by the public `delete_members` (after @WRITE check) and by
    `set_members` rollback (already inside a @WRITE-gated call).
    No @WRITE decorator on this helper by design — see the pattern note
    above.
    """
    nums_csv = ",".join(str(n) for n in nums) + ","
    url = f"{_DELETE_MEMBERS}?nums={nums_csv}"
    return await transport.get(url)


@WRITE
async def set_members(
    transport: ProcurveTransport,
    *,
    request: SetMembersRequest,
    auto_rollback: bool = True,
) -> SetMembersResponse:
    """Add members to the stack via `/cgi/set_members`.

    WARNING: manager password travels cleartext in the URL query
    string — this is a protocol-level security issue in the Java
    applet we mirror faithfully. Tell your users.

    Wire shape (byte-exact, MUST preserve trailing commas and param
    order):
        ?addrs=<mac1>,<mac2>,&nums=<n1>,<n2>,&pass=<raw>

    When `auto_rollback=True` (default, mirroring the applet), any
    non-empty error response triggers a follow-up `delete_members`
    call with the same `switch_nums` to free the slots. The applet
    only rolls back MACs whose post-add status is not `Member Up`
    (MemberCandidateList.java:800-863); we take the cruder approach
    of rolling back all requested slots on any error since we do not
    orchestrate the follow-up `get_members` poll here.

    # TODO: needs live capture — the response body parser is inferred
    from MemberCandidateList.java:774-783; we assume per-line
    `error~<msg>` / empty-success.
    """
    if len(request.mac_addrs) != len(request.switch_nums):
        raise ValueError(
            "mac_addrs and switch_nums must have the same length"
        )

    # Build the query string manually to preserve the trailing commas and
    # the exact addrs/nums/pass order. httpx would collapse or re-order.
    addrs_csv = ",".join(request.mac_addrs) + ","
    nums_csv = ",".join(str(n) for n in request.switch_nums) + ","
    query = f"addrs={addrs_csv}&nums={nums_csv}&pass={request.manager_password}"
    url = f"{_SET_MEMBERS}?{query}"

    r = await transport.get(url)
    errors = _collect_error_lines(r.text)

    if errors and auto_rollback:
        # Auto-rollback: free the slots we just tried to claim.
        # Call the internal impl directly — we're inside an already-gated
        # write path, and rollback must always run even if the READ_ONLY
        # env var is flipped mid-operation.
        rollback_req = DeleteMembersRequest(switch_nums=request.switch_nums)
        await _delete_members_impl(transport, rollback_req.switch_nums)
        return SetMembersResponse(
            ok=False,
            errors=errors,
            raw_body=r.text,
            rollback_performed=True,
        )

    return SetMembersResponse(
        ok=not errors,
        errors=errors,
        raw_body=r.text,
        rollback_performed=False,
    )


@WRITE
async def delete_members(
    transport: ProcurveTransport, *, request: DeleteMembersRequest
) -> DeleteMembersResponse:
    """Remove members from the stack via `/cgi/delete_members`.

    Wire shape (byte-exact): `?nums=<n1>,<n2>,` — trailing comma
    preserved per MemberCandidateList.java:328-335.

    Applet blind-consumes the body; we inspect for `error~<msg>`
    defensively.

    # TODO: needs live capture — the applet never parses the response
    body so the success / error shapes are not verified on the wire.
    """
    r = await _delete_members_impl(transport, request.switch_nums)

    errors = _collect_error_lines(r.text)
    if errors:
        return DeleteMembersResponse(
            ok=False,
            error_message=errors[0].message,
            raw_body=r.text,
        )
    return DeleteMembersResponse(ok=True, raw_body=r.text or None)
