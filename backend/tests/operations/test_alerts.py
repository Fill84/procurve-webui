"""Unit tests for alert-log mutation operations.

Covers `get_alert_detail` (HTML scrape), `ack_alerts` (bulk POST→GET, comma
literal indeces, repeated dt= per event), and `delete_alerts` (same shape
with action=del). Read-only enforcement is verified for both writes.

All tests mock the transport via respx; no live switch I/O.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.log import AlertEvent
from procurve_client.operations.status import (
    ack_alerts,
    delete_alerts,
    get_alert_detail,
)
from procurve_client.transport import ProcurveTransport


def _read_fixture(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="utf-8")


def _event(row_id: str, ts: int) -> AlertEvent:
    """Build a minimal AlertEvent for ack/del wire tests."""
    return AlertEvent(
        row_id=row_id,
        alert_name="",
        category="",
        ts_centiseconds=ts,
        description="",
    )


# ---- get_alert_detail ---------------------------------------------------


@respx.mock
async def test_get_alert_detail_parses_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_alert_detail.response.html")
    route = respx.get("http://192.0.2.3/cgi/ffdetail").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        detail = await get_alert_detail(t, index=1, ts_centiseconds=11094915)
    assert route.called
    q = route.calls.last.request.url.params
    assert q["index"] == "1"
    assert q["dt"] == "11094915"

    # Title = <title> tag
    assert detail.title == "Loss of Link"
    # hdr(...) call: severity / port / ts
    assert detail.severity == 3
    assert detail.affected_port == 10
    assert detail.ts_centiseconds == 11094915
    # ffbuttons setTimeout discriminators
    assert detail.type_code == 11
    assert detail.act_code == 2
    # Sections
    assert detail.description == (
        "The connection to the devices on port 10 has been lost."
    )
    assert detail.other_possibilities == (
        "The cable is damaged or severed. If so, replace the cable."
    )
    # raw_html preserved for debuggability
    assert "<title>Loss of Link</title>" in detail.raw_html
    # Echo of the request index into the model
    assert detail.index == 1


@respx.mock
async def test_get_alert_detail_solution_list_parsed(
    fixtures_dir: Path,
) -> None:
    body = _read_fixture(fixtures_dir, "get_alert_detail.response.html")
    respx.get("http://192.0.2.3/cgi/ffdetail").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        detail = await get_alert_detail(t, index=1, ts_centiseconds=11094915)
    # The fixture has three <li> bullets in the Solution block.
    assert len(detail.solution) == 3
    assert detail.solution[0].startswith("If the cable has been removed")
    assert "troubleshoot that device" in detail.solution[1]
    assert "re-enable the port" in detail.solution[2]


@respx.mock
async def test_get_alert_detail_minimal_missing_fields() -> None:
    """Bare minimum: just <title> + hdr(...). No <dl> body sections."""
    minimal = (
        "<html><head><title>X</title></head>"
        "<body><script>hdr('X', '1', '0', '1');</script></body></html>"
    )
    respx.get("http://192.0.2.3/cgi/ffdetail").mock(
        return_value=Response(200, text=minimal)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        detail = await get_alert_detail(t, index=42, ts_centiseconds=1)
    assert detail.title == "X"
    assert detail.severity == 1
    assert detail.affected_port == 0
    assert detail.ts_centiseconds == 1
    # No ffbuttons line in this minimal body — type_code/act_code default to 0
    assert detail.type_code == 0
    assert detail.act_code == 0
    # No description / solution / other_possibilities sections
    assert detail.description is None
    assert detail.solution == []
    assert detail.other_possibilities is None
    # echo of request index
    assert detail.index == 42


@respx.mock
async def test_get_alert_detail_empty_response_raises_parse_error() -> None:
    """Stale dt or bad index returns a 1-byte body in the wild."""
    respx.get("http://192.0.2.3/cgi/ffdetail").mock(
        return_value=Response(200, text=" ")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_alert_detail(t, index=999, ts_centiseconds=0)


# ---- ack_alerts wire format --------------------------------------------


@respx.mock
async def test_ack_alerts_wire_format_single(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        ack = await ack_alerts(t, events=[_event("1", 11094915)])
    assert ack.ok is True
    assert route.called
    q = route.calls.last.request.url.params
    assert q["indeces"] == "1"
    assert q["action"] == "ack"
    # Single event → one dt param
    assert list(q.get_list("dt")) == ["11094915"]


@respx.mock
async def test_ack_alerts_wire_format_multi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-event ack: comma literal CSV + repeated dt= in event order."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await ack_alerts(
            t,
            events=[
                _event("1", 11094915),
                _event("2", 12000000),
            ],
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "1,2"
    assert q["action"] == "ack"
    # dt repeated in the same order as the indeces CSV
    assert list(q.get_list("dt")) == ["11094915", "12000000"]
    # Wire ordering: indeces, action, then dt's in event order — and the
    # comma MUST be a literal (not %2C) per ack_alerts.md: the firmware's
    # echo parser splits on the literal comma, so the query is assembled
    # manually instead of via httpx params.
    raw_query = route.calls.last.request.url.query.decode("ascii")
    assert raw_query.startswith("indeces=1,2&action=ack&dt=11094915&dt=12000000")


@respx.mock
async def test_ack_alerts_respects_read_only_via_safety_decorator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await ack_alerts(t, events=[_event("1", 1)])


async def test_ack_alerts_rejects_empty_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wire requires at least one event — empty CSV is malformed."""
    monkeypatch.setenv("READ_ONLY", "false")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ValueError):
            await ack_alerts(t, events=[])


# ---- delete_alerts wire format -----------------------------------------


@respx.mock
async def test_delete_alerts_wire_format_single(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        ack = await delete_alerts(t, events=[_event("1", 11094915)])
    assert ack.ok is True
    q = route.calls.last.request.url.params
    assert q["indeces"] == "1"
    assert q["action"] == "del"
    assert list(q.get_list("dt")) == ["11094915"]


@respx.mock
async def test_delete_alerts_wire_format_multi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await delete_alerts(
            t,
            events=[
                _event("1", 11094915),
                _event("2", 12000000),
            ],
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "1,2"
    assert q["action"] == "del"
    assert list(q.get_list("dt")) == ["11094915", "12000000"]


@respx.mock
async def test_delete_alerts_respects_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await delete_alerts(t, events=[_event("1", 1)])
