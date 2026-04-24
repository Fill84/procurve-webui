"""Status-tab operations.

Contracts from Phase 0:
- get_device_status   GET /cgi/fflog?action=status
- get_alert_log       GET /cgi/fflog?action=list
- get_alert_detail    GET /cgi/ffdetail?index=<N>&dt=<ts>
- ack_alerts          GET /cgi/fflog?indeces=<csv>&action=ack&dt=<ts1>...
- delete_alerts       GET /cgi/fflog?indeces=<csv>&action=del&dt=<ts1>...
- get_port_status     GET /cgi/get_ports
- get_port_counters   GET /cgi/portc
- get_port_usage      GET /cgi/port_usage?LAST_PORT={n}&NUM_PORTS={m}

KEY FINDING: status-tab CGIs return bare-row tilde-delimited streams; no
`OK~`/`error~` sentinel. Use `parse_tilde_lines` directly.

The fault-log mutation endpoints (ack/delete) operate on RAM-only state
(the in-memory event list) — they do NOT touch running-config. They are
gated by `READ_ONLY` via the @WRITE decorator but the API layer skips
auto-backup (mirrors the diagnostics ping/link-test exception).
"""
from __future__ import annotations

import html
import re

from procurve_client._safety import READ, WRITE
from procurve_client.errors import ParseError
from procurve_client.models.log import (
    AlertDetail,
    AlertEvent,
    AlertLog,
    DeviceStatusBanner,
)
from procurve_client.models.network import ConfigWriteAck
from procurve_client.models.port import (
    PortCounters,
    PortCountersList,
    PortStatus,
    PortStatusList,
    PortUsage,
    PortUsageList,
)
from procurve_client.parsing import parse_tilde_lines, parse_tilde_row
from procurve_client.transport import ProcurveTransport

_FFLOG_PATH = "/cgi/fflog"
_FFDETAIL_PATH = "/cgi/ffdetail"
_GET_PORTS_PATH = "/cgi/get_ports"
_PORTC_PATH = "/cgi/portc"
_PORT_USAGE_PATH = "/cgi/port_usage"


@READ
async def get_device_status(transport: ProcurveTransport) -> DeviceStatusBanner:
    """Fetch the condensed device-status banner (first line of /cgi/fflog?action=status).

    The applet only reads the first line and tokenises on `~`; we do the same.
    On this firmware the response shape is identical to `action=list`, but the
    first line is a 2-field meta record.
    """
    r = await transport.get(_FFLOG_PATH, params={"action": "status"})
    first_line = ""
    for raw in r.text.splitlines():
        line = raw.strip()
        if line:
            first_line = line
            break
    if not first_line:
        raise ParseError("empty device-status response")
    fields = parse_tilde_row(first_line)
    if not fields:
        raise ParseError(f"device-status first line had no fields: {first_line!r}")
    # Per DeviceStatus.java:182-184, strip a leading literal "% " from description.
    def _desc(x: str | None) -> str | None:
        if x is None:
            return None
        s = x.strip()
        if s.startswith("% "):
            s = s[2:]
        return s

    return DeviceStatusBanner(
        state=fields[0],
        index=fields[1] if len(fields) > 1 else None,
        description=_desc(fields[2]) if len(fields) > 2 else None,
        ts_centiseconds=int(fields[3]) if len(fields) > 3 and fields[3] else None,
    )


@READ
async def get_alert_log(transport: ProcurveTransport) -> AlertLog:
    """Fetch /cgi/fflog?action=list — the full alert-log row stream.

    Line 1 is a meta/cursor line (2 fields). Subsequent lines are 5-field
    event rows. An empty switch emits only the meta line.
    """
    r = await transport.get(_FFLOG_PATH, params={"action": "list"})
    lines = parse_tilde_lines(r.text)
    if not lines:
        raise ParseError("empty alert-log response")
    meta = lines[0]
    if len(meta) < 2:
        raise ParseError(f"alert-log meta line missing fields: {meta!r}")
    events: list[AlertEvent] = []
    for row in lines[1:]:
        if len(row) < 5:
            raise ParseError(f"alert-log row missing fields: {row!r}")
        events.append(
            AlertEvent(
                row_id=row[0],
                alert_name=row[1],
                category=row[2],
                ts_centiseconds=int(row[3]),
                description=row[4],
            )
        )
    return AlertLog(
        latest_ts_centiseconds=int(meta[0]),
        cursor_or_count=int(meta[1]),
        events=events,
    )


def _parse_yes_no(s: str) -> bool:
    v = s.strip().lower()
    if v == "yes":
        return True
    if v == "no":
        return False
    raise ParseError(f"expected Yes/No, got {s!r}")


@READ
async def get_port_status(transport: ProcurveTransport) -> PortStatusList:
    """Fetch /cgi/get_ports — one row per port, 10 fields per row.

    Wire position 2 is a hidden decorative label cell (see protocol doc);
    position 9 is a trailing integer always observed as 0.
    """
    r = await transport.get(_GET_PORTS_PATH)
    rows = parse_tilde_lines(r.text)
    ports: list[PortStatus] = []
    for row in rows:
        if len(row) < 10:
            raise ParseError(f"get_ports row had {len(row)} fields (expected 10): {row!r}")
        link = row[5].strip()
        if link not in ("Up", "Down"):
            raise ParseError(f"unexpected link_status value: {row[5]!r}")
        ports.append(
            PortStatus(
                port=int(row[0]),
                port_name=row[1],
                port_type_label=row[2],
                port_type=row[3],
                enabled=_parse_yes_no(row[4]),
                link_status=link,
                current_mode=row[6],
                trunk=row[7],
                flow_ctrl=row[8],
                extra=int(row[9]) if row[9].strip() else 0,
            )
        )
    return PortStatusList(ports=ports)


@READ
async def get_port_counters(transport: ProcurveTransport) -> PortCountersList:
    """Fetch /cgi/portc — one row per port, 10 fields per row.

    Wire position 2 is the same hidden label cell shared with /cgi/get_ports.
    Counters are SNMP-style packet counters; they wrap at 2^32.
    """
    r = await transport.get(_PORTC_PATH)
    rows = parse_tilde_lines(r.text)
    ports: list[PortCounters] = []
    for row in rows:
        if len(row) < 10:
            raise ParseError(f"portc row had {len(row)} fields (expected 10): {row!r}")
        ports.append(
            PortCounters(
                port=int(row[0]),
                port_name=row[1],
                port_type_label=row[2],
                mcast_rx=int(row[3]),
                mcast_tx=int(row[4]),
                bcast_rx=int(row[5]),
                bcast_tx=int(row[6]),
                pkts_rx=int(row[7]),
                pkts_tx=int(row[8]),
                errors_rx=int(row[9]),
            )
        )
    return PortCountersList(ports=ports)


@READ
async def get_port_usage(
    transport: ProcurveTransport,
    *,
    last_port: int = 0,
    num_ports: int = -1,
) -> PortUsageList:
    """Fetch /cgi/port_usage — rows are 6 or 7 fields each.

    `last_port` is a cursor: the switch returns rows for ports strictly
    greater than this value. Pass 0 on first fetch to get everything.
    `num_ports` is the max rows requested; the applet sends -1 on first
    fetch and 26 thereafter. Callers can mirror that, or just use -1.

    The 7th (`speed`) field is optional per PortGraph.java:919. Rows with
    6 fields and rows with 7 are both accepted.
    """
    r = await transport.get(
        _PORT_USAGE_PATH,
        params={"LAST_PORT": last_port, "NUM_PORTS": num_ports},
    )
    rows = parse_tilde_lines(r.text)
    ports: list[PortUsage] = []
    for row in rows:
        if len(row) < 6:
            raise ParseError(
                f"port_usage row had {len(row)} fields (expected 6 or 7): {row!r}"
            )
        state = row[2].strip()
        if state not in ("G", "W", "N", "R"):
            raise ParseError(f"unexpected port_usage state: {row[2]!r}")
        ports.append(
            PortUsage(
                port=int(row[0]),
                label=row[1],
                state=state,
                usage1=int(row[3]),
                usage2=int(row[4]),
                usage3=int(row[5]),
                speed=row[6] if len(row) >= 7 else None,
            )
        )
    return PortUsageList(ports=ports)


# ---- Alert detail / ack / delete ---------------------------------------

# Regexes for parsing the /cgi/ffdetail HTML body. Per the rest of this
# codebase (see get_faultdetect_page, get_system_page, get_port_form)
# we prefer regex over a full HTML parser — the per-alert-type templates
# are baked into the switch firmware and stable across reloads.
_FFD_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)
_FFD_HDR_RE = re.compile(
    r"""hdr\(\s*['"]([^'"]*)['"]\s*,\s*['"](\d+)['"]\s*,\s*"""
    r"""['"](\d+)['"]\s*,\s*['"](\d+)['"]\s*\)""",
    re.IGNORECASE,
)
_FFD_BUTTONS_RE = re.compile(
    r"ffbuttons\.html\?[^\"']*?type=(\d+)[^\"']*?act=(\d+)",
    re.IGNORECASE,
)
# Description: <dt><b>Description:</b> <dd>...up to next <dt> or </dl>
_FFD_DESCRIPTION_RE = re.compile(
    r"<dt>\s*<b>\s*Description:\s*</b>\s*(?:<dd>)?(.*?)"
    r"(?=<dt>|</dl>)",
    re.IGNORECASE | re.DOTALL,
)
_FFD_SOLUTION_BLOCK_RE = re.compile(
    r"<dt>\s*<b>\s*Solution:\s*</b>\s*<ul>(.*?)</ul>",
    re.IGNORECASE | re.DOTALL,
)
_FFD_LI_RE = re.compile(
    r"<li>(.*?)(?=<li>|</ul>|\Z)", re.IGNORECASE | re.DOTALL
)
_FFD_OTHER_POSSIBILITIES_RE = re.compile(
    r"<dt>\s*<b>\s*Other Possibilities:\s*</b>\s*(?:<dd>)?(.*?)"
    r"(?=<dt>|</dl>)",
    re.IGNORECASE | re.DOTALL,
)


def _clean_html_text(s: str | None) -> str | None:
    """Strip stray tags / collapse whitespace / decode entities.

    The <dd> blocks may contain `<p>`, line breaks, and trailing whitespace.
    Returns None if the cleaned text is empty.
    """
    if s is None:
        return None
    # Strip residual HTML tags (the <dt><b>...</b> regex captures content
    # up to the next <dt>; that content can include `<p>` separators).
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


@READ
async def get_alert_detail(
    transport: ProcurveTransport,
    *,
    index: int,
    ts_centiseconds: int,
) -> AlertDetail:
    """GET /cgi/ffdetail?index=<N>&dt=<ts> → parsed HTML detail page.

    Per get_alert_detail.md the HTML body has:
      * <title> = human-readable event category
      * inline `hdr(title, dt, port, severity)` script call
      * `setTimeout` line referencing `ffbuttons.html?...&type=<T>&...&act=<A>`
      * `<dl>` body with Description / Solution / Other Possibilities sections

    The `dt` query param doubles as an integrity token — a stale value
    yields a 1-byte body. We surface that as ParseError.
    """
    r = await transport.get(
        _FFDETAIL_PATH,
        params={"index": index, "dt": ts_centiseconds},
    )
    body = r.text
    if len(body.strip()) < 20:
        # Observed: stale dt or bad index yields ~1-byte body.
        raise ParseError(
            f"ffdetail: empty/short response for index={index} dt={ts_centiseconds}"
        )

    title_m = _FFD_TITLE_RE.search(body)
    if not title_m:
        raise ParseError("ffdetail: missing <title>")
    title = title_m.group(1).strip()

    hdr_m = _FFD_HDR_RE.search(body)
    if not hdr_m:
        raise ParseError("ffdetail: missing hdr(...) call")
    # hdr(ti, dt, pt, se) — re-parse as our authoritative source for the
    # ts/port/severity fields; the <title> stays as `title`.
    severity = int(hdr_m.group(4))
    affected_port = int(hdr_m.group(3))
    hdr_ts = int(hdr_m.group(2))

    # ffbuttons setTimeout line gives type_code + act_code.
    btn_m = _FFD_BUTTONS_RE.search(body)
    if btn_m:
        type_code = int(btn_m.group(1))
        act_code = int(btn_m.group(2))
    else:
        # Some alert types may not emit the buttons-frame line; treat as 0.
        type_code = 0
        act_code = 0

    desc_m = _FFD_DESCRIPTION_RE.search(body)
    description = _clean_html_text(desc_m.group(1)) if desc_m else None

    solution: list[str] = []
    sol_m = _FFD_SOLUTION_BLOCK_RE.search(body)
    if sol_m:
        for li in _FFD_LI_RE.finditer(sol_m.group(1)):
            cleaned = _clean_html_text(li.group(1))
            if cleaned:
                solution.append(cleaned)

    op_m = _FFD_OTHER_POSSIBILITIES_RE.search(body)
    other_possibilities = _clean_html_text(op_m.group(1)) if op_m else None

    return AlertDetail(
        index=index,
        ts_centiseconds=hdr_ts,
        title=title,
        severity=severity,
        affected_port=affected_port,
        type_code=type_code,
        act_code=act_code,
        description=description,
        solution=solution,
        other_possibilities=other_possibilities,
        raw_html=body,
    )


def _build_fflog_action_params(
    *,
    events: list[AlertEvent],
    action: str,
) -> list[tuple[str, str]]:
    """Build the wire query for /cgi/fflog ack/del.

    Encoding:
      * `indeces=<csv>` (literal comma — not %2C — per the applet)
      * `action=<ack|del>`
      * one `dt=<ts_centiseconds>` per event, in the same order as `indeces`.

    Returns a list-of-tuples so httpx preserves repeated `dt=` params.
    """
    if not events:
        raise ValueError("events must be non-empty")
    csv = ",".join(e.row_id for e in events)
    params: list[tuple[str, str]] = [
        ("indeces", csv),
        ("action", action),
    ]
    for e in events:
        params.append(("dt", str(e.ts_centiseconds)))
    return params


@WRITE
async def ack_alerts(
    transport: ProcurveTransport,
    *,
    events: list[AlertEvent],
) -> ConfigWriteAck:
    """GET /cgi/fflog?indeces=<csv>&action=ack&dt=<ts1>[&dt=<ts2>...]

    Bulk acknowledge. Per ack_alerts.md the wire is GET-only (no POST),
    and the comma in `indeces` is a literal — not `%2C`. The `dt` param
    is repeated once per event in the same order as the `indeces` CSV.

    NOTE: the applet's `_loopback` target means it discards the response
    body and re-fetches the alert log. We mirror by returning a generic
    ConfigWriteAck with the raw body for debuggability.
    """
    params = _build_fflog_action_params(events=events, action="ack")
    r = await transport.get(_FFLOG_PATH, params=params)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)


@WRITE
async def delete_alerts(
    transport: ProcurveTransport,
    *,
    events: list[AlertEvent],
) -> ConfigWriteAck:
    """GET /cgi/fflog?indeces=<csv>&action=del&dt=<ts1>[&dt=<ts2>...]

    Bulk delete. Wire-identical to ack except for `action=del`.
    """
    params = _build_fflog_action_params(events=events, action="del")
    r = await transport.get(_FFLOG_PATH, params=params)
    return ConfigWriteAck(ok=True, raw_body=r.text or None)
