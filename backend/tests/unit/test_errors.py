"""Unit tests for the exception hierarchy."""
from procurve_client.errors import (
    AuthError,
    OperationError,
    ParseError,
    ProcurveError,
    ProtocolError,
    SchemaError,
    TransportError,
    WriteDisabledError,
)


def test_root_is_procurve_error():
    assert issubclass(TransportError, ProcurveError)
    assert issubclass(AuthError, ProcurveError)
    assert issubclass(ProtocolError, ProcurveError)
    assert issubclass(OperationError, ProcurveError)
    assert issubclass(WriteDisabledError, ProcurveError)


def test_protocol_subclasses():
    assert issubclass(ParseError, ProtocolError)
    assert issubclass(SchemaError, ProtocolError)


def test_carries_message_and_context():
    exc = OperationError("VLAN already exists", operation="create_vlan", detail={"vlan_id": 42})
    assert str(exc) == "VLAN already exists"
    assert exc.operation == "create_vlan"
    assert exc.detail == {"vlan_id": 42}


def test_transport_error_carries_host():
    exc = TransportError("timeout", host="192.168.178.3")
    assert str(exc) == "timeout"
    assert exc.host == "192.168.178.3"


def test_write_disabled_error_default_message():
    exc = WriteDisabledError(operation="set_port_name")
    assert "READ_ONLY" in str(exc)
    assert exc.operation == "set_port_name"
