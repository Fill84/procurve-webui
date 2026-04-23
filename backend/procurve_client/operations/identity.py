"""Identity-tab operations.

Contract from Phase 0: research/protocol/identity/read_identity_page.md

The Identity tab is a pure-static HTML page that interpolates values into
JavaScript string literals which then feed document.write(). There is no
CGI. Parsing is a regex scrape over the raw HTML body.
"""
from __future__ import annotations

import re
from ipaddress import IPv4Address

from procurve_client._safety import READ
from procurve_client.errors import ParseError
from procurve_client.models.device import DeviceIdentity
from procurve_client.transport import ProcurveTransport

_IDENTITY_PATH = "/identity/identity.html"

# Marker that confirms we received the identity page (not a 401 HTML).
_MARKER = "System Name:"

# The page HTML is broken in known places (missing `</font>` on IP Address and
# Management Server rows), so we can't rely on `</font></th>` as the label
# delimiter — we accept either `</font></th>` or `</th>`. The value cell is
# the text between the next `<td>` and the following `</td>` or `</font></td>`.
_NAMED_CELL_RE_TMPL = (
    r"{label}\s*:\s*(?:</font>)?</th>.*?<td>(?P<value>.*?)</td>"
)


def _extract_named_cell(body: str, label: str) -> str:
    """Grab the cell value following the `<label>:` header.

    The HTML is built by string concatenation across many JS literals, so
    the extracted span includes the interstitial `" +\n    "   ` garbage
    between chunks. We strip tags, quotes, ` +`, newlines, and
    backslash-`n` escapes, then collapse whitespace.
    """
    pattern = re.compile(_NAMED_CELL_RE_TMPL.format(label=re.escape(label)), re.DOTALL)
    m = pattern.search(body)
    if not m:
        raise ParseError(f"identity page missing cell for label {label!r}")
    raw = m.group("value")
    # Strip HTML tags (font, etc).
    text = re.sub(r"<[^>]+>", " ", raw)
    # Strip the JS string-concatenation artefacts. The raw page glues
    # literals together as: `"literal1" +\n    "literal2"+\n    "literal3"`
    # — we drop the quotes and `+` joiners and backslash-n escapes.
    text = text.replace("\\n", " ")
    # Any `"` or `+` surrounded by whitespace is a join artefact.
    text = re.sub(r'["+]', " ", text)
    # Normalize whitespace.
    return re.sub(r"\s+", " ", text).strip()


def _extract_uptime_centis(body: str) -> int:
    """Extract the integer argument to `ft("...")` immediately after `System Up-Time:`."""
    pattern = re.compile(
        r'System Up-Time\s*:\s*(?:</font>)?</th>.*?ft\s*\(\s*"(\d+)"\s*\)', re.DOTALL
    )
    m = pattern.search(body)
    if not m:
        raise ParseError("identity page missing ft() uptime argument")
    return int(m.group(1))


def _extract_memory(body: str) -> tuple[int, int]:
    """Extract `Total - <n>` / `Free - <n>` from the System Memory cell."""
    cell = _extract_named_cell(body, "System Memory")
    total_m = re.search(r"Total\s*-\s*(\d+)", cell)
    free_m = re.search(r"Free\s*-\s*(\d+)", cell)
    if not total_m or not free_m:
        raise ParseError(f"System Memory cell did not match expected format: {cell!r}")
    return int(total_m.group(1)), int(free_m.group(1))


def _extract_management_url(body: str) -> str | None:
    """Extract the arg passed to link() in the Management Server cell.

    link("") renders "(None)" → map to None.
    """
    pattern = re.compile(
        r'Management Server\s*:\s*(?:</font>)?</th>.*?link\s*\(\s*"([^"]*)"\s*\)',
        re.DOTALL,
    )
    m = pattern.search(body)
    if not m:
        raise ParseError("identity page missing link() argument")
    url = m.group(1).strip()
    return url or None


def _extract_base_mac(body: str) -> str:
    """Parse `00 1d b3 b7 0e 00` → `00:1D:B3:B7:0E:00`."""
    cell = _extract_named_cell(body, "Base MAC Address")
    parts = cell.strip().split()
    if len(parts) != 6 or not all(re.fullmatch(r"[0-9a-fA-F]{2}", p) for p in parts):
        raise ParseError(f"Base MAC cell did not match hex-octet format: {cell!r}")
    return ":".join(p.upper() for p in parts)


def _extract_product(body: str) -> str:
    """`ProCurve Switch 2810-24G   (J9021A)` → collapse to single-spaced."""
    cell = _extract_named_cell(body, "Product")
    # Collapse ` (` to ` (` with a single space between marketing name and part.
    return re.sub(r"\s+", " ", cell).strip()


@READ
async def read_identity_page(transport: ProcurveTransport) -> DeviceIdentity:
    """Fetch /identity/identity.html and parse the baked-in switch identity.

    The page is rendered server-side with values interpolated into JS
    string literals. No runtime CGI call is involved.
    """
    r = await transport.get(_IDENTITY_PATH)
    body = r.text
    if _MARKER not in body:
        raise ParseError(f"identity page missing marker {_MARKER!r}")

    mem_total, mem_free = _extract_memory(body)
    cpu_pct_str = _extract_named_cell(body, "System CPU Util(%)")
    ip_raw = _extract_named_cell(body, "IP Address")
    # The IP cell has a trailing "</td></tr>" that the named-cell regex does
    # not consume when `</font>` is absent from that cell. Strip to the IPv4.
    ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", ip_raw)
    if not ip_match:
        raise ParseError(f"IP Address cell did not contain an IPv4 literal: {ip_raw!r}")

    return DeviceIdentity(
        system_name=_extract_named_cell(body, "System Name"),
        system_location=_extract_named_cell(body, "System Location"),
        system_contact=_extract_named_cell(body, "System Contact"),
        uptime_centiseconds=_extract_uptime_centis(body),
        cpu_pct=int(cpu_pct_str),
        memory_total_bytes=mem_total,
        memory_free_bytes=mem_free,
        product=_extract_product(body),
        base_mac=_extract_base_mac(body),
        serial_number=_extract_named_cell(body, "Serial Number"),
        firmware_version=_extract_named_cell(body, "Version"),
        ip_address=IPv4Address(ip_match.group(0)),
        management_server_url=_extract_management_url(body),
    )
