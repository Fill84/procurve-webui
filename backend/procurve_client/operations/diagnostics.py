"""Diagnostics-tab operations.

⚠️ SAFETY
    `device_reset` reboots the switch, interrupting all switched traffic
    for the duration of the boot cycle. Automated tooling must NEVER invoke
    this function — only the operator runs it manually, with a verified
    backup in hand.

    `ping` and `link_test` are technically writes because they cause the
    switch to emit ICMP/link probes, but they do not change switch state.
    They are decorated `@WRITE` so `READ_ONLY=true` blocks them by default.

Contracts from Phase 0:
- ping                      GET /cgi/ping?...&tp=1 (HTML response)
- link_test                 GET /cgi/ping?...&tp=2 (HTML response)
- get_configuration_report  GET /diagnostics/config.html
- device_reset              GET /cgi/device_reset  (FORBIDDEN)
"""
from __future__ import annotations

import re

from procurve_client._safety import READ, WRITE
from procurve_client.errors import ParseError, ProtocolError
from procurve_client.models.diagnostics import (
    ConfigurationReport,
    DeviceResetResponse,
    PingAction,
    PingResult,
    PingTestType,
)
from procurve_client.parsing import parse_running_config
from procurve_client.transport import ProcurveTransport

_PING_PATH = "/cgi/ping"
_CONFIG_REPORT_PATH = "/diagnostics/config.html"
_DEVICE_RESET_PATH = "/cgi/device_reset"

_SUCCESSES_RE = re.compile(r"Successes:\s*(\d+)")
_FAILURES_RE = re.compile(r"Failures:\s*(\d+)")
_PRE_RE = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)


def _parse_ping_html(html: str) -> PingResult:
    """Scrape `Successes: N` / `Failures: N` from the /cgi/ping HTML body."""
    sm = _SUCCESSES_RE.search(html)
    fm = _FAILURES_RE.search(html)
    if not sm or not fm:
        raise ParseError("ping response missing Successes:/Failures: counters")
    return PingResult(successes=int(sm.group(1)), failures=int(fm.group(1)), raw_html=html)


async def _ping_common(
    transport: ProcurveTransport,
    *,
    destination: str,
    test_type: PingTestType,
    packet_count: int,
    timeout_s: int,
    index: int,
    interface: int,
    action: PingAction,
) -> PingResult:
    params = {
        "index": index,
        "interf": interface,
        "action": action.value,
        "tp": int(test_type),
        "da": destination,
        "nr": packet_count,
        "to": timeout_s,
    }
    r = await transport.get(_PING_PATH, params=params)
    return _parse_ping_html(r.text)


@WRITE
async def ping(
    transport: ProcurveTransport,
    *,
    destination: str,
    packet_count: int = 10,
    timeout_s: int = 5,
    index: int = 0,
    interface: int = 0,
    action: PingAction = PingAction.START,
) -> PingResult:
    """Ping Test (tp=1).

    The switch sends ICMP echo requests to `destination`. Defaults mirror
    the HTML form (10 packets, 5-second timeout). Decorated `@WRITE`
    because although no config changes, the switch does emit packets.
    """
    return await _ping_common(
        transport,
        destination=destination,
        test_type=PingTestType.PING,
        packet_count=packet_count,
        timeout_s=timeout_s,
        index=index,
        interface=interface,
        action=action,
    )


@WRITE
async def link_test(
    transport: ProcurveTransport,
    *,
    destination: str,
    packet_count: int = 10,
    timeout_s: int = 5,
    index: int = 0,
    interface: int = 0,
    action: PingAction = PingAction.START,
) -> PingResult:
    """Link Test (tp=2).

    Same endpoint as `ping` but with tp=2. `destination` is typically a MAC
    address on the same L2 segment (dash-separated or colon-separated hex).
    """
    return await _ping_common(
        transport,
        destination=destination,
        test_type=PingTestType.LINK,
        packet_count=packet_count,
        timeout_s=timeout_s,
        index=index,
        interface=interface,
        action=action,
    )


@READ
async def get_configuration_report(
    transport: ProcurveTransport,
) -> ConfigurationReport:
    """Fetch /diagnostics/config.html and extract the running-config <pre> block.

    The <pre> contents preserve CLI line endings; do not normalize. For a
    byte-identical backup use backup.download_config — the HTML report may
    HTML-escape `<`, `>`, `&` in config strings.
    """
    r = await transport.get(_CONFIG_REPORT_PATH)
    html = r.text
    m = _PRE_RE.search(html)
    if not m:
        raise ParseError("configuration report missing <pre>...</pre> block")
    config_text = m.group(1)
    # Strip a single leading newline inside <pre>.
    if config_text.startswith("\n"):
        config_text = config_text[1:]
    return ConfigurationReport(
        raw_html=html,
        config_text=config_text,
        running_config=parse_running_config(config_text),
    )


@WRITE
async def device_reset(transport: ProcurveTransport) -> DeviceResetResponse:
    """FORBIDDEN for automation — only the operator runs this manually.

    Sends GET /cgi/device_reset. The switch reboots immediately; expect a
    TCP reset mid-response. This implementation exists for full protocol
    parity and is decorated `@WRITE` so `READ_ONLY=true` blocks it.

    See research/protocol/diagnostics/device_reset.md.
    """
    try:
        r = await transport.get(_DEVICE_RESET_PATH)
    except Exception as exc:  # noqa: BLE001 — any transport error is plausibly a reboot
        return DeviceResetResponse(initiated=True, message=f"connection closed: {exc}")
    # 200 with body — unusual, but not an error.
    if r.status_code != 200:
        raise ProtocolError(f"device_reset returned HTTP {r.status_code}")
    return DeviceResetResponse(initiated=True, message=r.text[:200] or None)
