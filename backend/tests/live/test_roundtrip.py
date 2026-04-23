"""One-time end-to-end round-trip test under explicit per-run user approval.

This test is the sole live-write  ever executes against the switch during
development. It is marked `roundtrip` (in addition to `live`) so it is opt-in
and never runs by default. It is guarded by the `READ_ONLY=false` env var.

Workflow (matches feedback_switch_write_safety.md):
  1. Pre-state matches baseline — else STOP.
  2. Read current port 18 form (so we can submit a minimal change).
  3. Execute the write (change port 18 name UPS → UPS-TEST, preserve other fields).
  4. Verify the write landed.
  5. Restore via upload_config.
  6. Verify restore brought the switch back to the reference baseline.
  7. If any step fails: STOP and notify user; do NOT attempt remediation.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from procurve_client import ProcurveTransport
from procurve_client.models.backup import ConfigBackup
from procurve_client.models.port import SetPortConfigRequest
from procurve_client.operations.backup import download_config, upload_config
from procurve_client.operations.configuration import get_port_form, set_port_config

pytestmark = [pytest.mark.live, pytest.mark.roundtrip]

REFERENCE_SHA = "f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11"


def _reference_backup() -> ConfigBackup:
    path = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "backups"
        / "2026-04-23"
        / "CONFIG.pcc"
    )
    # Read as bytes to preserve CRLF exactly (the SHA was computed over raw
    # bytes from the switch), then decode as ASCII for the text field.
    raw = path.read_bytes()
    return ConfigBackup.from_text(raw.decode("ascii"))


async def test_roundtrip_port18_name(monkeypatch):
    """Change port 18 name UPS → UPS-TEST → verify → restore → verify. User-approved 2026-04-23."""
    monkeypatch.setenv("READ_ONLY", os.environ.get("READ_ONLY", "false"))
    baseline = _reference_backup()
    assert baseline.sha256 == REFERENCE_SHA, (
        f"reference backup file has drifted: got {baseline.sha256}, expected {REFERENCE_SHA}"
    )

    host = os.environ.get("SWITCH_HOST", "192.168.178.3")

    async with ProcurveTransport(host=host) as t:
        # 1. Pre-state matches baseline
        pre = await download_config(t)
        assert pre.sha256 == REFERENCE_SHA, (
            f"live switch diverged from baseline: live={pre.sha256} "
            f"baseline={REFERENCE_SHA}. Refusing to run write-test. "
            f"See memory/feedback_switch_write_safety.md."
        )

        # 2. Read current port 18 form so we can preserve everything except name.
        current = await get_port_form(t, ports=[18])
        assert current.port_name == "UPS", (
            f"unexpected current name for port 18: {current.port_name!r} (expected 'UPS')"
        )

        # 3. Execute the write — only the name changes; all other fields echoed.
        req = SetPortConfigRequest(
            ports=[18],
            name="UPS-TEST",
            admin_enabled=current.admin_enabled,
            mode=current.mode,
            flow_control_enabled=current.flow_control_enabled,
        )
        await set_port_config(t, request=req)

        # 4. Verify the write landed.
        post_write = await download_config(t)
        assert post_write.sha256 != REFERENCE_SHA, "write had no effect (SHA unchanged)"
        interface_block_18 = _extract_interface_block(post_write.text, 18)
        assert 'name "UPS-TEST"' in interface_block_18, (
            f"UPS-TEST name not in port 18 block: {interface_block_18!r}"
        )
        assert 'name "UPS"' not in interface_block_18 or (
            'name "UPS-TEST"' in interface_block_18
            and interface_block_18.count('name "UPS"') == interface_block_18.count('name "UPS-TEST"')
        ), f"old UPS name still present in port 18 block: {interface_block_18!r}"

        # 5. Restore baseline.
        await upload_config(t, backup=baseline)

        # 6. Verify restore succeeded — must match reference EXACTLY.
        post_restore = await download_config(t)
        if post_restore.sha256 != REFERENCE_SHA:
            diff = _diff(baseline.text, post_restore.text)
            pytest.fail(
                f"restore did not return switch to baseline.\n"
                f"expected SHA {REFERENCE_SHA}\n"
                f"got      SHA {post_restore.sha256}\n"
                f"Diff (first 50 lines):\n{diff}\n"
                f"STOP: Do not attempt further writes. "
                f"Notify user before running further write-tests."
            )


def _extract_interface_block(cfg: str, port: int) -> str:
    """Return the `interface <port>` block up to its closing `exit`."""
    marker = f"interface {port}"
    idx = cfg.find(marker)
    if idx < 0:
        return ""
    end = cfg.find("\nexit", idx)
    return cfg[idx : end + 5] if end >= 0 else cfg[idx:]


def _diff(expected: str, actual: str, max_lines: int = 50) -> str:
    import difflib

    d = difflib.unified_diff(
        expected.splitlines(keepends=False),
        actual.splitlines(keepends=False),
        fromfile="baseline",
        tofile="live-after-restore",
        n=3,
    )
    lines = list(d)
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines truncated)"]
    return "\n".join(lines)
