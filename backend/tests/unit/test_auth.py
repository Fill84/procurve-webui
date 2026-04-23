"""Unit tests for auth strategies."""
from procurve_client.auth import BasicAuth, NoneAuth


def test_none_auth_emits_no_headers():
    auth = NoneAuth()
    assert auth.headers() == {}


def test_basic_auth_emits_authorization_header():
    auth = BasicAuth(username="admin", password="hunter2")  # noqa: S106
    headers = auth.headers()
    assert "Authorization" in headers
    # Standard base64 of 'admin:hunter2'
    assert headers["Authorization"] == "Basic YWRtaW46aHVudGVyMg=="


def test_basic_auth_accepts_blank_credentials():
    # Switch currently has blank/blank; this must not crash.
    auth = BasicAuth(username="", password="")
    headers = auth.headers()
    assert headers["Authorization"] == "Basic Og=="


def test_none_and_basic_auth_are_distinct_types():
    assert NoneAuth() != BasicAuth(username="", password="")
