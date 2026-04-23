"""Per-operation live tests for read ops that require arguments."""
import os

import pytest

from procurve_client import ProcurveTransport
from procurve_client.operations.configuration import get_port_form
from procurve_client.operations.status import get_port_usage
from procurve_client.operations.vlan import get_vlan_ports, get_vlan_protocol

pytestmark = pytest.mark.live


@pytest.fixture
async def live_transport():
    host = os.environ.get("SWITCH_HOST", "192.168.178.3")
    async with ProcurveTransport(host=host) as t:
        yield t


async def test_get_vlan_ports_vlan1(live_transport):
    # DEFAULT_VLAN is always present
    result = await get_vlan_ports(live_transport, vlan_id=1)
    assert result is not None


async def test_get_vlan_protocol_vlan1(live_transport):
    # On this 2810 firmware, this returns empty - but the endpoint must still succeed.
    result = await get_vlan_protocol(live_transport, vlan_id=1)
    assert result is not None  # empty list is fine


async def test_get_port_usage_first_page(live_transport):
    # get_port_usage accepts optional last_port / num_ports kwargs with defaults;
    # exercise the pagination path here with an explicit window.
    result = await get_port_usage(live_transport, last_port=10, num_ports=10)
    assert result is not None


async def test_get_port_form_port1(live_transport):
    # Per-port form metadata for port 1 (always exists on a 24-port switch).
    result = await get_port_form(live_transport, ports=[1])
    assert result is not None
