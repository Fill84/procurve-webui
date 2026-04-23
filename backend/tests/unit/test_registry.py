"""Smoke tests: verify the public API re-exports and the operations registry."""
import procurve_client
from procurve_client._safety import is_read, is_write
from procurve_client.operations import ALL_OPERATIONS, READ_OPERATIONS, WRITE_OPERATIONS


def test_top_level_exports():
    for name in (
        "ProcurveTransport",
        "NoneAuth",
        "BasicAuth",
        "ProcurveError",
        "TransportError",
        "AuthError",
        "ProtocolError",
        "OperationError",
        "WriteDisabledError",
    ):
        assert hasattr(procurve_client, name), f"missing top-level export: {name}"


def test_every_operation_has_read_or_write_marker():
    assert ALL_OPERATIONS, "registry must not be empty - Phase 1 operations should be registered"
    for op in ALL_OPERATIONS:
        assert is_read(op) or is_write(op), f"{op.__name__}: missing @READ or @WRITE"


def test_read_and_write_registries_partition_all():
    assert set(READ_OPERATIONS).isdisjoint(WRITE_OPERATIONS)
    assert set(READ_OPERATIONS) | set(WRITE_OPERATIONS) == set(ALL_OPERATIONS)


def test_expected_operation_count():
    # Phase 1 Task 1.11 total: roughly 70+ operations across all tabs.
    assert len(ALL_OPERATIONS) >= 70, f"only {len(ALL_OPERATIONS)} operations registered"


def test_known_operations_present():
    # Spot-check a representative sample.
    names = {op.__name__ for op in ALL_OPERATIONS}
    must_have = {
        "download_config",
        "upload_config",
        "read_identity_page",
        "get_port_status",
        "get_vlans_all",
        "add_vlan",
        "set_vlan_ports",
        "get_memsinfo",
        "get_web_managers",
        "ping",
    }
    missing = must_have - names
    assert not missing, f"missing operations in registry: {missing}"
