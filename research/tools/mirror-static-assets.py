#!/usr/bin/env python3
"""
Scan research/mirror/<date>/*.html for referenced static assets
(images, CSS, JS, other URLs on the switch) and download any that
aren't already mirrored. Read-only against the switch.
"""
from __future__ import annotations
import argparse
import re
import sys
import urllib.request
from pathlib import Path, PurePosixPath

SWITCH_HOST = "192.168.178.3"

# Matches src=..., href=..., url(...) with quoted or unquoted values.
# ProCurve firmware emits unquoted HTML attributes (e.g. src=PNBlogo.gif).
SRC_RE = re.compile(
    r"""(?:src|href)\s*=\s*(?:"([^"#?]+)"|'([^'#?]+)'|([^\s"'>#?]+))"""
    r"""|url\(\s*["']?([^"')]+)["']?\s*\)""",
    re.IGNORECASE,
)

# Skip external hosts and mailto/javascript/http references.
SKIP_PREFIXES = ("http://", "https://", "mailto:", "javascript:", "#", "data:")

def is_asset(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in {
        "gif", "jpg", "jpeg", "png", "bmp", "ico",
        "css", "js",
        "html", "htm",
    }

def normalize(base_url_dir: str, ref: str) -> str | None:
    """Resolve an href/src ref into a URL path on the switch.

    base_url_dir is the URL directory (e.g. "/configuration/") the HTML
    file was served from. Uses PurePosixPath so this works on Windows
    (WindowsPath.resolve() adds a drive letter and breaks URL semantics).
    """
    ref = ref.strip().strip('"').strip("'")
    if not ref or any(ref.startswith(p) for p in SKIP_PREFIXES):
        return None
    if ref.startswith("/"):
        return ref
    # Resolve relative path using POSIX URL semantics.
    joined = PurePosixPath(base_url_dir) / ref
    # Manually collapse .. and . segments (PurePosixPath has no resolve()).
    parts: list[str] = []
    for part in joined.parts:
        if part in ("", "/", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", required=True, help="e.g. research/mirror/2026-04-23")
    args = ap.parse_args()

    mirror_root = Path(args.mirror).resolve()
    if not mirror_root.is_dir():
        print(f"No such directory: {mirror_root}", file=sys.stderr)
        return 2

    seen: set[str] = set()
    to_fetch: set[str] = set()

    for html in mirror_root.rglob("*.html"):
        text = html.read_text(errors="replace")
        # Compute the URL-path directory this HTML was served from.
        rel_parent = html.parent.relative_to(mirror_root).as_posix()
        base_url_dir = "/" if rel_parent in ("", ".") else "/" + rel_parent + "/"
        for m in SRC_RE.finditer(text):
            ref = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
            norm = normalize(base_url_dir, ref)
            if norm and norm not in seen:
                seen.add(norm)
                if is_asset(norm):
                    to_fetch.add(norm)

    print(f"Discovered {len(to_fetch)} candidate asset paths.")

    fetched = skipped = failed = 0
    for path in sorted(to_fetch):
        local = mirror_root / path.lstrip("/")
        if local.exists():
            skipped += 1
            continue
        url = f"http://{SWITCH_HOST}{path}"
        try:
            local.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=10) as r:
                local.write_bytes(r.read())
            fetched += 1
            print(f"  GET {path}  -> {local.relative_to(mirror_root)}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {path}  ({exc})")

    print(f"Done. fetched={fetched} skipped(existing)={skipped} failed={failed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
