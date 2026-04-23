"""Live integration tests - hit the actual switch. Run with `pytest -m live`.

All @READ operations without required parameters get a smoke test here.
Parametric reads (port=1, vlan=1, etc.) are tested in `test_live_reads_parametric.py`.
"""
from __future__ import annotations

import inspect
import os

import pytest

from procurve_client import ProcurveTransport
from procurve_client.operations import READ_OPERATIONS

pytestmark = pytest.mark.live


@pytest.fixture
async def live_transport():
    host = os.environ.get("SWITCH_HOST", "192.168.178.3")
    async with ProcurveTransport(host=host) as t:
        yield t


def _parameter_free_read_ops() -> list:
    """Read operations whose only required arg is the transport.

    Skips operations that take no transport at all (e.g. `support_redirect`,
    which returns static info with no switch call).
    """
    out = []
    for op in READ_OPERATIONS:
        all_params = list(inspect.signature(op).parameters.values())
        if not all_params:
            continue  # purely static op — not a switch smoke test target
        params = all_params[1:]  # skip `transport`
        required = [p for p in params if p.default is inspect.Parameter.empty]
        if not required:
            out.append(op)
    return out


@pytest.mark.parametrize("op", _parameter_free_read_ops(), ids=lambda o: o.__name__)
async def test_read_operation_live(live_transport, op):
    """Every parameter-free @READ operation succeeds against the live switch."""
    result = await op(live_transport)
    assert result is not None, f"{op.__name__} returned None"
