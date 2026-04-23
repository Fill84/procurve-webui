"""Tests for /api/v1/identity.

Strategy: monkeypatch `read_identity_page` in the router module so we don't
need a real transport. Override `get_transport` to a no-op sentinel.
"""
from __future__ import annotations

from collections.abc import Iterator
from ipaddress import IPv4Address

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.identity as identity_module
from app.deps import get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.device import DeviceIdentity


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.168.178.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    return Settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    a = create_app()
    a.state.settings = settings
    return a


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _fake_identity() -> DeviceIdentity:
    return DeviceIdentity(
        system_name="HP2810_01",
        system_location="lab",
        system_contact="admin@example.com",
        uptime_centiseconds=123_456,
        cpu_pct=3,
        memory_total_bytes=134_217_728,
        memory_free_bytes=67_108_864,
        product="ProCurve Switch 2810-24G (J9021A)",
        base_mac="00:1D:B3:B7:0E:00",
        serial_number="SG123ABCDE",
        firmware_version="N.11.78, ROM N.10.01",
        ip_address=IPv4Address("192.168.178.3"),
        management_server_url=None,
    )


def test_get_identity_happy_path(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _fake_identity()

    async def fake_read(transport: object) -> DeviceIdentity:
        return fake

    monkeypatch.setattr(identity_module, "read_identity_page", fake_read)
    app.dependency_overrides[get_transport] = lambda: object()
    try:
        r = client.get("/api/v1/identity")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["system_name"] == "HP2810_01"
        assert body["base_mac"] == "00:1D:B3:B7:0E:00"
        assert body["ip_address"] == "192.168.178.3"
        assert body["management_server_url"] is None
    finally:
        app.dependency_overrides.clear()


def test_get_identity_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/identity")
    assert r.status_code == 401
