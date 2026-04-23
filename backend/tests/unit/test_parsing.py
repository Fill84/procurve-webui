"""Unit tests for low-level parsers."""
import pytest

from procurve_client.errors import OperationError, ParseError
from procurve_client.parsing import (
    parse_kv_lines,
    parse_running_config,
    parse_tilde_lines,
    parse_tilde_row,
    unwrap_sentinel,
)

# --- parse_tilde_row ---

def test_parse_tilde_row_simple():
    assert parse_tilde_row("a~b~c") == ("a", "b", "c")


def test_parse_tilde_row_single_field():
    assert parse_tilde_row("solo") == ("solo",)


def test_parse_tilde_row_trailing_tilde_dropped():
    # Applets commonly emit a trailing tilde; drop the empty final field.
    assert parse_tilde_row("a~b~") == ("a", "b")


def test_parse_tilde_row_empty_string():
    assert parse_tilde_row("") == ()


# --- parse_tilde_lines ---

def test_parse_tilde_lines_multiline_lf():
    body = "1~up~100\n2~down~10\n"
    assert parse_tilde_lines(body) == [("1", "up", "100"), ("2", "down", "10")]


def test_parse_tilde_lines_multiline_crlf():
    body = "1~up\r\n2~down\r\n"
    assert parse_tilde_lines(body) == [("1", "up"), ("2", "down")]


def test_parse_tilde_lines_skips_blank_lines():
    body = "1~x\n\n2~y\n"
    assert parse_tilde_lines(body) == [("1", "x"), ("2", "y")]


def test_parse_tilde_lines_empty_body():
    assert parse_tilde_lines("") == []


# --- unwrap_sentinel ---

def test_unwrap_sentinel_ok():
    # OK~<payload> → returns the rest of the first line as tilde-separated tuple
    assert unwrap_sentinel("OK~done") == ("done",)


def test_unwrap_sentinel_ok_with_multiple_fields():
    assert unwrap_sentinel("OK~vlan1~created~100") == ("vlan1", "created", "100")


def test_unwrap_sentinel_ok_bare():
    # Just "OK" with no further fields
    assert unwrap_sentinel("OK") == ()


def test_unwrap_sentinel_error_raises():
    with pytest.raises(OperationError) as exc_info:
        unwrap_sentinel("error~VLAN already exists")
    assert "VLAN already exists" in str(exc_info.value)


def test_unwrap_sentinel_error_with_empty_message():
    with pytest.raises(OperationError) as exc_info:
        unwrap_sentinel("error~")
    assert str(exc_info.value) in ("", "error")  # tolerate either rendering


def test_unwrap_sentinel_unknown_sentinel_raises_parse_error():
    with pytest.raises(ParseError):
        unwrap_sentinel("xyzzy~whatever")


def test_unwrap_sentinel_tolerates_trailing_newline():
    assert unwrap_sentinel("OK~done\n") == ("done",)


# --- parse_kv_lines ---

def test_parse_kv_lines_single_value():
    body = "hostname=HP2810_01\nuptime=123456\n"
    assert parse_kv_lines(body) == {"hostname": "HP2810_01", "uptime": "123456"}


def test_parse_kv_lines_crlf():
    body = "a=1\r\nb=2\r\n"
    assert parse_kv_lines(body) == {"a": "1", "b": "2"}


def test_parse_kv_lines_raises_on_missing_equals():
    with pytest.raises(ParseError):
        parse_kv_lines("a=1\noops\n")


def test_parse_kv_lines_skips_blank_lines():
    body = "a=1\n\nb=2\n"
    assert parse_kv_lines(body) == {"a": "1", "b": "2"}


# --- parse_running_config ---

def test_parse_running_config_header_and_hostname():
    body = (
        "; J9021A Configuration Editor; Created on release #N.11.78\r\n"
        "\r\n"
        'hostname "HP2810_01"\r\n'
        'snmp-server community "public" Unrestricted\r\n'
    )
    parsed = parse_running_config(body)
    assert parsed.hostname == "HP2810_01"
    assert parsed.firmware == "N.11.78"
    assert 'snmp-server community "public" Unrestricted' in parsed.raw


def test_parse_running_config_keeps_raw_bytes_for_round_trip():
    body = "; J9021A Configuration Editor; Created on release #N.11.78\r\nhostname \"X\"\r\n"
    parsed = parse_running_config(body)
    assert parsed.raw == body
    # Raw must round-trip byte-identically to support restore.
    assert parsed.raw.encode("ascii") == body.encode("ascii")


def test_parse_running_config_missing_header():
    # Tolerate absence of the header (some fixtures may be truncated).
    parsed = parse_running_config('hostname "X"\r\n')
    assert parsed.hostname == "X"
    assert parsed.firmware == ""
