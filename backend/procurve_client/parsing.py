"""Low-level response parsers used by operation functions.

Conventions established in Phase 0 (research/analysis/callback-layer.md):
- Most applet CGIs return tilde-delimited text.
- Some endpoints (mutations, many in VLAN/Stack subsystems) start responses
  with an `OK~...` or `error~<msg>` sentinel. Use `unwrap_sentinel` to handle
  the sentinel and surface switch-reported errors as OperationError.
- Status-tab CGIs are bare-row streams (no sentinel). Use `parse_tilde_lines`
  directly.
- Running-config text (CONFIG.pcc) has its own parser that preserves raw bytes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from procurve_client.errors import OperationError, ParseError

_FIRMWARE_RE = re.compile(r"Created on release #(?P<fw>[A-Z0-9.]+)")
_HOSTNAME_RE = re.compile(r'^hostname\s+"(?P<name>[^"]*)"', re.MULTILINE)


def parse_tilde_row(line: str) -> tuple[str, ...]:
    """Split a single tilde-delimited line into fields.

    A trailing empty field (from a trailing `~`) is dropped. An empty input
    returns an empty tuple.
    """
    if not line:
        return ()
    parts = line.split("~")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return tuple(parts)


def parse_tilde_lines(body: str) -> list[tuple[str, ...]]:
    """Split a multi-line tilde-delimited body into a list of field tuples.

    Blank lines (after CRLF/LF normalization) are skipped. Accepts `\\n` or
    `\\r\\n` line endings.
    """
    out: list[tuple[str, ...]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        out.append(parse_tilde_row(line))
    return out


def unwrap_sentinel(body: str) -> tuple[str, ...]:
    """Handle an `OK~...` / `error~<msg>` response.

    Returns the remaining fields on OK. Raises OperationError on error.
    Raises ParseError on an unrecognized sentinel.
    """
    # Strip a single trailing newline but keep inner content.
    text = body.rstrip("\r\n")
    if text == "OK":
        return ()
    if text.startswith("OK~"):
        return parse_tilde_row(text[len("OK~") :])
    if text == "error":
        raise OperationError("")
    if text.startswith("error~"):
        raise OperationError(text[len("error~") :])
    raise ParseError(f"unrecognized sentinel in response: {body!r}")


def parse_kv_lines(body: str) -> dict[str, str]:
    """Parse lines of the form `key=value\\n` into a dict. CRLF tolerated."""
    out: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "=" not in line:
            raise ParseError(f"expected key=value line, got: {line!r}")
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


@dataclass(frozen=True)
class RunningConfig:
    """Parsed view of a ProCurve running-config (CONFIG.pcc) text."""

    raw: str
    hostname: str
    firmware: str


def parse_running_config(body: str) -> RunningConfig:
    """Parse a running-config text into a structured view while retaining the raw bytes.

    The raw text is preserved byte-for-byte so it can be uploaded back to
    the switch to restore.
    """
    fw_match = _FIRMWARE_RE.search(body)
    name_match = _HOSTNAME_RE.search(body)
    return RunningConfig(
        raw=body,
        hostname=name_match.group("name") if name_match else "",
        firmware=fw_match.group("fw") if fw_match else "",
    )
