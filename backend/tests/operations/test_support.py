"""Unit tests for Support-tab operation.

The Support tab is a static redirect with no switch protocol; the test
verifies only that the SupportInfo model contains the expected fields.
"""
from procurve_client.operations.support import support_redirect


async def test_support_redirect_returns_info_without_switch_call() -> None:
    info = await support_redirect()
    # Legacy URL preserved for parity.
    assert info.legacy_url == "http://www.procurve.com"
    # Modern replacement suggested for new UIs.
    assert info.current_url.startswith("https://www.hpe.com")
    # Marked unavailable — the original domain no longer resolves.
    assert info.available is False
    assert "procurve.com" in info.note
