"""Unit tests for shared Pydantic helpers."""
import pytest
from pydantic import ValidationError

from procurve_client.models._base import MacAddress, PortNumber, VlanId


def test_mac_address_accepts_colon_separated():
    m = MacAddress(value="aa:bb:cc:dd:ee:ff")
    assert m.value == "AA:BB:CC:DD:EE:FF"


def test_mac_address_accepts_dash_separated():
    m = MacAddress(value="AA-BB-CC-DD-EE-FF")
    assert m.value == "AA:BB:CC:DD:EE:FF"


def test_mac_address_accepts_procurve_format():
    # ProCurve sometimes emits MACs as 6-byte hex with no separators.
    m = MacAddress(value="aabbccddeeff")
    assert m.value == "AA:BB:CC:DD:EE:FF"


def test_mac_address_rejects_short():
    with pytest.raises(ValidationError):
        MacAddress(value="aa:bb:cc:dd:ee")


def test_mac_address_rejects_invalid_chars():
    with pytest.raises(ValidationError):
        MacAddress(value="gg:hh:ii:jj:kk:ll")


def test_port_number_bounds():
    assert PortNumber(value=1).value == 1
    assert PortNumber(value=24).value == 24
    with pytest.raises(ValidationError):
        PortNumber(value=0)
    with pytest.raises(ValidationError):
        PortNumber(value=25)


def test_vlan_id_bounds():
    assert VlanId(value=1).value == 1
    assert VlanId(value=4094).value == 4094
    with pytest.raises(ValidationError):
        VlanId(value=0)
    with pytest.raises(ValidationError):
        VlanId(value=4095)
