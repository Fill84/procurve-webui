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

from procurve_client.errors import OperationError, ParseError, ProtocolError

_FIRMWARE_RE = re.compile(r"Created on release #(?P<fw>[A-Z0-9.]+)")
_HOSTNAME_RE = re.compile(r'^hostname\s+"(?P<name>[^"]*)"', re.MULTILINE)


def ensure_write_ok(status_code: int, body: str) -> None:
    """Shared post-write response check for endpoints with unverified bodies.

    Many configuration/status write CGIs have response shapes that were never
    captured live, so operations used to return ``ok=True`` unconditionally —
    meaning a rejected write was reported to the operator as success. This
    check is deliberately conservative (no false failures on unknown-but-fine
    bodies): it raises only on

    * a non-200 status (`ProtocolError`), or
    * a body that *starts* with the applet's ``error~`` sentinel or an
      ``error:`` token (`OperationError`) — the convention the VLAN/stacking
      subsystems already parse.

    Callers still return ``ok=True`` afterwards; the difference is that the
    two known failure signatures now surface instead of vanishing.
    """
    if status_code != 200:
        raise ProtocolError(
            f"switch write returned HTTP {status_code}: body={body[:200]!r}"
        )
    text = body.strip()
    lowered = text.lower()
    if lowered.startswith("error~") or lowered.startswith("error:"):
        raise OperationError(text[:200])


def parse_int(raw: str, *, context: str) -> int:
    """``int()`` for wire tokens that raises typed `ParseError`, not ValueError.

    Use for every integer conversion of switch-originated text so that a
    garbage body surfaces as a handled protocol error instead of a raw
    ValueError → generic 500.
    """
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ParseError(f"{context}: expected integer, got {raw!r}") from exc


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
