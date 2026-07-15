"""Mock demo backend for procurve-webui screenshots and demos.

Serves the built frontend (`frontend/dist/`) and answers every API endpoint
with hard-coded JSON. Never touches a real switch. Useful for:

  * Reproducing the README screenshots without owning the hardware.
  * Demoing the UI in talks / blog posts.
  * Iterating on frontend styling with stable, predictable data.

Run:
    cd frontend && npm install && npm run build
    cd ../tools/mock_demo
    python demo_server.py     # listens on 127.0.0.1:8080

Then point a browser at http://127.0.0.1:8080. Any username/password is
accepted. The session cookie is stored in-memory and survives until the
process exits.
"""
from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=timezone.utc)


def _iso(d: datetime) -> str:
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


IDENTITY = {
    "system_name": "core-sw-01",
    "system_location": "Server room, rack A3",
    "system_contact": "netops@example.local",
    "uptime_centiseconds": 1_835_421_200,  # ~212 days
    "cpu_pct": 14,
    "memory_total_bytes": 67_108_864,
    "memory_free_bytes": 41_943_040,
    "product": "ProCurve Switch 2810-24G (J9021A)",
    "base_mac": "00:1D:B3:B7:0E:00",
    "serial_number": "SG948XJ021",
    "firmware_version": "N.11.78, ROM N.10.01",
    "ip_address": "192.168.1.3",
    "management_server_url": None,
}


def _port(p: int, name: str, link: str, mode: str, enabled: bool = True) -> dict[str, Any]:
    return {
        "port": p,
        "port_name": name,
        "port_type_label": "",
        "port_type": "100/1000T",
        "enabled": enabled,
        "link_status": link,
        "current_mode": mode,
        "trunk": "",
        "flow_ctrl": "off",
        "extra": 0,
    }


# 24 copper + 4 SFP to mirror the real 2810-24G
PORT_STATUS = [
    _port(1, "uplink-router", "Up", "1000FDx"),
    _port(2, "wifi-ap-lobby", "Up", "1000FDx"),
    _port(3, "wifi-ap-floor2", "Up", "1000FDx"),
    _port(4, "desk-01", "Up", "1000FDx"),
    _port(5, "desk-02", "Up", "1000FDx"),
    _port(6, "desk-03", "Down", "—", enabled=True),
    _port(7, "desk-04", "Up", "1000FDx"),
    _port(8, "desk-05", "Up", "100FDx"),
    _port(9, "printer-mfp", "Up", "100FDx"),
    _port(10, "lab-bench-1", "Up", "1000FDx"),
    _port(11, "lab-bench-2", "Down", "—", enabled=False),
    _port(12, "lab-bench-3", "Down", "—", enabled=False),
    _port(13, "voip-phone-01", "Up", "100FDx"),
    _port(14, "voip-phone-02", "Up", "100FDx"),
    _port(15, "camera-front", "Up", "100FDx"),
    _port(16, "camera-rear", "Up", "100FDx"),
    _port(17, "nas-primary", "Up", "1000FDx"),
    _port(18, "UPS-APC", "Up", "100FDx"),
    _port(19, "guest-vlan", "Up", "1000FDx"),
    _port(20, "spare", "Down", "—", enabled=True),
    _port(21, "spare", "Down", "—", enabled=False),
    _port(22, "spare", "Down", "—", enabled=False),
    _port(23, "mgmt-laptop", "Up", "1000FDx"),
    _port(24, "trunk-to-2nd-sw", "Up", "1000FDx"),
    {**_port(25, "sfp-fibre-01", "Up", "1000FDx"), "port_type": "SFP+"},
    {**_port(26, "sfp-fibre-02", "Down", "—", enabled=True), "port_type": "SFP+"},
    {**_port(27, "sfp-spare", "Down", "—", enabled=False), "port_type": "SFP+"},
    {**_port(28, "sfp-spare", "Down", "—", enabled=False), "port_type": "SFP+"},
]


def _usage(p: int, label: str, state: str, u1: int, u2: int, u3: int) -> dict[str, Any]:
    return {
        "port": p,
        "label": label,
        "state": state,
        "usage1": u1,
        "usage2": u2,
        "usage3": u3,
        "speed": "1000",
    }


PORT_USAGE = [
    _usage(1, "1", "G", 32, 8, 4),
    _usage(2, "2", "G", 14, 6, 2),
    _usage(3, "3", "G", 9, 3, 1),
    _usage(4, "4", "G", 4, 2, 1),
    _usage(5, "5", "G", 3, 1, 0),
    _usage(6, "6", "N", 0, 0, 0),
    _usage(7, "7", "G", 2, 1, 0),
    _usage(8, "8", "G", 1, 0, 0),
    _usage(9, "9", "G", 1, 0, 0),
    _usage(10, "10", "W", 41, 18, 6),
    _usage(11, "11", "N", 0, 0, 0),
    _usage(12, "12", "N", 0, 0, 0),
    _usage(13, "13", "G", 2, 1, 0),
    _usage(14, "14", "G", 2, 1, 0),
    _usage(15, "15", "G", 5, 1, 0),
    _usage(16, "16", "G", 5, 1, 0),
    _usage(17, "17", "G", 22, 4, 1),
    _usage(18, "18", "G", 1, 0, 0),
    _usage(19, "19", "G", 7, 2, 1),
    _usage(20, "20", "N", 0, 0, 0),
    _usage(21, "21", "N", 0, 0, 0),
    _usage(22, "22", "N", 0, 0, 0),
    _usage(23, "23", "G", 6, 2, 1),
    _usage(24, "24", "G", 58, 22, 9),
    _usage(25, "25", "G", 12, 4, 2),
    _usage(26, "26", "N", 0, 0, 0),
    _usage(27, "27", "N", 0, 0, 0),
    _usage(28, "28", "N", 0, 0, 0),
]

DEVICE_STATUS = {
    "state": "Operational",
    "index": "0",
    "description": "All systems normal",
    "ts_centiseconds": IDENTITY["uptime_centiseconds"],
}


def _alert(row: int, ts_offset_s: int, name: str, cat: str, desc: str) -> dict[str, Any]:
    return {
        "row_id": str(row),
        "alert_name": name,
        "category": cat,
        "ts_centiseconds": IDENTITY["uptime_centiseconds"] - ts_offset_s * 100,
        "description": desc,
    }


ALERT_LOG = {
    "latest_ts_centiseconds": IDENTITY["uptime_centiseconds"],
    "cursor_or_count": 6,
    "events": [
        _alert(6, 60 * 5, "Link change", "Information", "Port 6 (desk-03) link state changed: Up → Down"),
        _alert(5, 60 * 90, "Excessive bandwidth", "Threshold", "Port 24 utilisation exceeded 80% for 5 minutes"),
        _alert(4, 60 * 60 * 8, "Authentication", "Security", "Web manager login from 192.168.1.42"),
        _alert(3, 60 * 60 * 24, "STP topology change", "Information", "VLAN 1 spanning-tree topology change detected"),
        _alert(2, 60 * 60 * 48, "Configuration saved", "Information", "Running configuration saved to flash"),
        _alert(1, 60 * 60 * 24 * 30, "Power-on", "System", "Switch booted with firmware N.11.78"),
    ],
}


BACKUPS = [
    {
        "filename": "config-2026-04-26T0900Z-manual.pcc",
        "created_at": _iso(_NOW - timedelta(hours=2)),
        "size": 2904,
        "sha256": "f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11",
        "trigger": "manual",
    },
    {
        "filename": "config-2026-04-25T2030Z-pre-write.pcc",
        "created_at": _iso(_NOW - timedelta(hours=14)),
        "size": 2904,
        "sha256": "ad2c5e91ed9f63281b2ad5a82171c2d5e34d8dc7a55c57a08f0f8e6d6a4c2dde",
        "trigger": "pre-write",
    },
    {
        "filename": "config-2026-04-22T0300Z-scheduled.pcc",
        "created_at": _iso(_NOW - timedelta(days=4)),
        "size": 2872,
        "sha256": "11aac4b6bdac0a7e4be59c001a61f019d5f2f8e8c0c4c2a4b3a1f93ea1ae7c2f",
        "trigger": "scheduled",
    },
    {
        "filename": "config-2026-04-15T0300Z-scheduled.pcc",
        "created_at": _iso(_NOW - timedelta(days=11)),
        "size": 2840,
        "sha256": "5d8e3c2f1a7b9c4e0d6f8a2c5e1b3d7f9a0c2e4b6d8f1a3c5e7b9d1f3a5c7e9b",
        "trigger": "scheduled",
    },
]


SYSTEM_INFO = {
    "mac_address": IDENTITY["base_mac"],
    "name": IDENTITY["system_name"],
    "location": IDENTITY["system_location"],
    "contact": IDENTITY["system_contact"],
}


IP_CONFIG = {
    "vlan_id": 1,
    "mode": 2,
    "ip_address": IDENTITY["ip_address"],
    "subnet_mask": "255.255.255.0",
    "gateway": "192.168.1.1",
}


PORT_CONFIG_LIST = {
    "ports": [
        {
            "port": p["port"],
            "port_name": p["port_name"],
            "port_type_label": p.get("port_type_label", ""),
            "port_type": p["port_type"],
            "enabled": p["enabled"],
            "config_status": ".",
            "config_mode": "Auto" if p["link_status"] == "Up" else "—",
            "trunk": "",
            "flow_control": False,
        }
        for p in PORT_STATUS
    ]
}


DEVICE_FEATURES = {
    "vlan_count": 1,
    "crip_stat": "0",
    "igmp": True,
    "spanning_tree": True,
}


FAULT_DETECTION = {
    "sensitivity": 32,
    "dps": None,
}


MONITOR_PAGE = {
    "enabled": False,
    "candidate_dest_ports": list(range(1, 29)),
    "selected_dest_port": None,
}


BOB_PORTS = {
    "device": {"codename": "2810-24G", "port_count": 24},
    "ports": [
        {
            "port": p["port"],
            "kind": p["port_type"],
            "label": p["port_name"],
            "link": p["link_status"] == "Up",
            "enabled": p["enabled"],
            "mode": p["current_mode"] if p["link_status"] == "Up" else None,
            "poe": None,
        }
        for p in PORT_STATUS
    ],
}


WEB_ACCESS = {"operator_username": "operator", "manager_username": "manager"}

WEB_MANAGERS = {
    "entries": [
        {
            "index": 1,
            "ip": "192.168.1.0",
            "mask": "255.255.255.0",
            "access_level": "Manager",
        },
        {
            "index": 2,
            "ip": "10.0.0.0",
            "mask": "255.255.0.0",
            "access_level": "Operator",
        },
    ]
}


PERPORTS = {
    "rows": [
        {
            "port": p["port"],
            "port_label": "",
            "port_name": p["port_name"],
            "address_selection": "Continuous",
            "authorized_address": " ",
            "mode": "Send Alarm",
            "security_action": 1,
            "address_limit": 1,
            "trunk": False,
        }
        for p in PORT_STATUS[:24]
    ]
}


INTRUSION_LOG = {
    "entries": [
        {
            "port": 7,
            "port_name": "desk-04",
            "intruder_address": "AA:BB:CC:11:22:33",
            "timestamp": "10 mins",
        }
    ]
}


SSL_STATE = {
    "ssl_enabled": False,
    "ssl_port": 443,
    "cert_mode": 1,
    "ca_signed_installed": False,
}


SUPPORT_INFO = {
    "legacy_url": "http://www.procurve.com",
    "current_url": "https://www.hpe.com/us/en/networking.html",
    "available": False,
    "note": (
        "The legacy Support tab redirected to http://www.procurve.com, which is "
        "unreachable in 2026. Use `current_url` instead."
    ),
}


SUPPORT_PAGE_CONFIG = {
    "support_url": "https://www.hpe.com/us/en/networking.html",
    "mgmt_url": "",
}


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="procurve-webui mock demo",
    version="0.0.0-mock",
    description="Hard-coded mock backend for screenshots and demos.",
)

SESSION_COOKIE = "procurve_session"
_SESSIONS: dict[str, datetime] = {}


def _ensure_session(request: Request, response: Response) -> bool:
    """Auto-issue a session cookie on first hit so the demo just works."""
    token = request.cookies.get(SESSION_COOKIE)
    if token and token in _SESSIONS:
        return True
    new_token = secrets.token_urlsafe(24)
    _SESSIONS[new_token] = _NOW + timedelta(hours=8)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=new_token,
        max_age=8 * 3600,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
    return True


@app.post("/api/v1/auth/login")
async def login(request: Request, response: Response) -> JSONResponse:
    token = secrets.token_urlsafe(24)
    expires = _NOW + timedelta(hours=8)
    _SESSIONS[token] = expires
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=8 * 3600,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
    return JSONResponse({"session_id": token, "expires_at": _iso(expires)})


@app.post("/api/v1/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _SESSIONS.pop(token, None)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/v1/auth/whoami")
async def whoami(request: Request, response: Response) -> JSONResponse:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or token not in _SESSIONS:
        return JSONResponse(
            {"detail": "no session"}, status_code=401
        )
    expires = _SESSIONS[token]
    return JSONResponse({"username": "demo", "expires_at": _iso(expires)})


@app.get("/api/v1/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "switch_reachable": True})


@app.get("/api/v1/identity")
async def identity() -> dict[str, Any]:
    return IDENTITY


# Status -------------------------------------------------------------------

@app.get("/api/v1/status/device")
async def device_status() -> dict[str, Any]:
    return DEVICE_STATUS


@app.get("/api/v1/status/ports")
async def status_ports() -> dict[str, Any]:
    return {"ports": PORT_STATUS}


@app.get("/api/v1/status/port-usage")
async def status_port_usage() -> dict[str, Any]:
    return {"ports": PORT_USAGE}


@app.get("/api/v1/status/counters")
async def status_counters() -> dict[str, Any]:
    return {
        "ports": [
            {
                "port": p["port"],
                "port_name": p["port_name"],
                "port_type_label": "",
                "mcast_rx": 1234 * p["port"],
                "mcast_tx": 567 * p["port"],
                "bcast_rx": 2345 * p["port"],
                "bcast_tx": 890 * p["port"],
                "pkts_rx": 1_234_567 * p["port"],
                "pkts_tx": 987_654 * p["port"],
                "errors_rx": 0,
            }
            for p in PORT_STATUS
        ]
    }


@app.get("/api/v1/status/alert-log")
async def alerts() -> dict[str, Any]:
    return ALERT_LOG


@app.get("/api/v1/status/alerts/{idx}")
async def alert_detail(idx: int) -> dict[str, Any]:
    return {
        "row_id": str(idx),
        "alert_name": "Link change",
        "category": "Information",
        "description": f"Detail for event {idx} (mock).",
        "ts_centiseconds": IDENTITY["uptime_centiseconds"] - idx * 100,
        "raw_html": "<p>Mock HTML detail</p>",
    }


# Configuration -----------------------------------------------------------

@app.get("/api/v1/configuration/system")
async def cfg_system() -> dict[str, Any]:
    return SYSTEM_INFO


@app.get("/api/v1/configuration/ip")
async def cfg_ip() -> dict[str, Any]:
    return IP_CONFIG


@app.get("/api/v1/configuration/ports")
async def cfg_ports() -> dict[str, Any]:
    return PORT_CONFIG_LIST


@app.get("/api/v1/configuration/ports/{port}")
async def cfg_port_form(port: int) -> dict[str, Any]:
    return {
        "ports": [port],
        "port_name": f"port-{port}",
        "admin_enabled": True,
        "mode": 5,  # PortMode.AUTO
        "flow_control_enabled": False,
    }


@app.get("/api/v1/configuration/device-features")
async def cfg_device_features() -> dict[str, Any]:
    return DEVICE_FEATURES


@app.get("/api/v1/configuration/fault-detection")
async def cfg_fault_detection() -> dict[str, Any]:
    return FAULT_DETECTION


@app.get("/api/v1/configuration/monitor")
async def cfg_monitor() -> dict[str, Any]:
    return MONITOR_PAGE


@app.get("/api/v1/configuration/bob-ports")
async def cfg_bob_ports() -> dict[str, Any]:
    return BOB_PORTS


@app.get("/api/v1/configuration/support-page")
async def cfg_support_page() -> dict[str, Any]:
    return SUPPORT_PAGE_CONFIG


@app.get("/api/v1/configuration/qos/cos")
async def qos_cos() -> dict[str, Any]:
    return {"entries": []}


@app.get("/api/v1/configuration/qos/user-pri")
async def qos_user() -> dict[str, Any]:
    return {"entries": []}


@app.get("/api/v1/configuration/qos/vlan-pri")
async def qos_vlan() -> dict[str, Any]:
    return {"entries": []}


@app.get("/api/v1/configuration/qos/dscp")
async def qos_dscp() -> dict[str, Any]:
    # DscpTable: 64 rows on real firmware; two representative ones suffice.
    return {
        "rows": [
            {"row_index": 1, "codepoint": "000000", "priority_label": "No-override"},
            {"row_index": 47, "codepoint": "101110", "priority_label": "7"},
        ]
    }


@app.get("/api/v1/configuration/qos/diffserv")
async def qos_diffserv() -> dict[str, Any]:
    return {
        "rows": [
            {
                "row_index": 47,
                "inbound_codepoint": "101110",
                "dscp_policy": "101110",
                "priority_label": "7",
            },
        ]
    }


# Security ----------------------------------------------------------------

@app.get("/api/v1/security/web-access")
async def sec_web_access() -> dict[str, Any]:
    return WEB_ACCESS


@app.get("/api/v1/security/web-managers")
async def sec_web_managers() -> dict[str, Any]:
    return WEB_MANAGERS


@app.get("/api/v1/security/per-port")
async def sec_per_port() -> dict[str, Any]:
    return PERPORTS


@app.get("/api/v1/security/intrusion")
async def sec_intrusion() -> dict[str, Any]:
    return INTRUSION_LOG


@app.get("/api/v1/security/ssl-state")
async def sec_ssl_state() -> dict[str, Any]:
    return SSL_STATE


# Diagnostics -------------------------------------------------------------

@app.get("/api/v1/diagnostics/configuration-report")
async def diag_config_report() -> dict[str, Any]:
    return {
        "raw_html": "<pre>Running configuration:\n\nhostname \"core-sw-01\"\n…</pre>",
        "config_text": (
            "Running configuration:\n\n"
            f"hostname \"{IDENTITY['system_name']}\"\n"
            f"snmp-server contact \"{IDENTITY['system_contact']}\"\n"
            f"snmp-server location \"{IDENTITY['system_location']}\"\n"
            "\n"
            "vlan 1\n"
            "   name \"DEFAULT_VLAN\"\n"
            "   untagged 1-28\n"
            "   ip address dhcp-bootp\n"
            "   exit\n"
            "\n"
            "spanning-tree\n"
            "fault-finder broadcast-storm sensitivity medium\n"
            "fault-finder loop-protect sensitivity medium\n"
        ),
    }


# Support -----------------------------------------------------------------

@app.get("/api/v1/support")
async def support() -> dict[str, Any]:
    return SUPPORT_INFO


# Backups -----------------------------------------------------------------

@app.get("/api/v1/backups")
async def backups_list() -> list[dict[str, Any]]:
    return BACKUPS


@app.get("/api/v1/backups/live-sha")
async def backups_live_sha() -> dict[str, Any]:
    return {"sha256": BACKUPS[0]["sha256"]}


@app.get("/api/v1/backups/{filename}/diff")
async def backups_diff(filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        "--- live\n+++ stored\n@@ -10,3 +10,3 @@\n   untagged 1-28\n-   ip address 192.168.1.3 255.255.255.0\n+   ip address dhcp-bootp\n   exit\n",
        media_type="text/plain",
    )


# ---------------------------------------------------------------------------
# Static SPA + auto-issue session
# ---------------------------------------------------------------------------

@app.middleware("http")
async def auto_session(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/") and request.url.path != "/api/v1/auth/whoami":
        # Auto-issue a session cookie on every API hit so the demo "just works"
        # without forcing the user to log in. We only do this when the response
        # was not a 401 already (so login flow still works if testing it).
        token = request.cookies.get(SESSION_COOKIE)
        if not token or token not in _SESSIONS:
            new_token = secrets.token_urlsafe(24)
            _SESSIONS[new_token] = _NOW + timedelta(hours=8)
            response.set_cookie(
                key=SESSION_COOKIE,
                value=new_token,
                max_age=8 * 3600,
                httponly=True,
                samesite="strict",
                secure=False,
                path="/",
            )
    return response


def _mount_spa(app: FastAPI) -> None:
    if not FRONTEND_DIST.exists():
        @app.get("/{full_path:path}")
        async def _missing(full_path: str) -> JSONResponse:
            return JSONResponse(
                {
                    "error": "frontend not built",
                    "expected": str(FRONTEND_DIST),
                    "fix": "cd frontend && npm install && npm run build",
                },
                status_code=503,
            )
        return

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> Response:
        # Real files served first.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        # Otherwise SPA index.
        return FileResponse(FRONTEND_DIST / "index.html")


_mount_spa(app)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
