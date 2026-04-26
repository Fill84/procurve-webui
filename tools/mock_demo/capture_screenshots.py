"""Capture README screenshots from the running mock demo backend.

Prerequisites:
    pip install playwright
    python -m playwright install chromium

    # Then in another terminal:
    python tools/mock_demo/demo_server.py --port 8090

Then:
    python tools/mock_demo/capture_screenshots.py
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
SHOTS_DIR = REPO_ROOT / "docs" / "screenshots"


async def _wait_idle(page) -> None:  # type: ignore[no-untyped-def]
    """Best-effort wait until the React Query layer is settled."""
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(800)


async def main(base_url: str) -> None:
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        # 1. Login screen ---------------------------------------------------
        await page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        await _wait_idle(page)
        await page.screenshot(path=str(SHOTS_DIR / "01-login.png"))
        print(" wrote 01-login.png")

        # Submit blank login (mock accepts anything).
        await page.fill("#username", "manager")
        await page.fill("#password", "demo")
        await page.click("button[type=submit]")
        await page.wait_for_url(f"{base_url}/", timeout=5000)
        await _wait_idle(page)

        # 2. Identity tab ---------------------------------------------------
        await page.screenshot(path=str(SHOTS_DIR / "02-identity.png"))
        print(" wrote 02-identity.png")

        # 3. Status tab -----------------------------------------------------
        await page.goto(f"{base_url}/status", wait_until="domcontentloaded")
        await _wait_idle(page)
        # Allow chart layout to settle.
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(SHOTS_DIR / "03-status.png"), full_page=True)
        print(" wrote 03-status.png (full page)")

        # 4. Support tab (replaces port-detail; the port-detail child route is
        # nested under /status without an Outlet so it cannot render alongside
        # the chassis view in current code).
        await page.goto(f"{base_url}/support", wait_until="domcontentloaded")
        await _wait_idle(page)
        await page.screenshot(path=str(SHOTS_DIR / "04-support.png"))
        print(" wrote 04-support.png")

        # 5. Configuration tab ---------------------------------------------
        await page.goto(f"{base_url}/configuration", wait_until="domcontentloaded")
        await _wait_idle(page)
        await page.screenshot(path=str(SHOTS_DIR / "05-configuration.png"), full_page=True)
        print(" wrote 05-configuration.png (full page)")

        # 6. Security tab ---------------------------------------------------
        await page.goto(f"{base_url}/security", wait_until="domcontentloaded")
        await _wait_idle(page)
        await page.screenshot(path=str(SHOTS_DIR / "06-security.png"), full_page=True)
        print(" wrote 06-security.png (full page)")

        # 7. Diagnostics tab ------------------------------------------------
        await page.goto(f"{base_url}/diagnostics", wait_until="domcontentloaded")
        await _wait_idle(page)
        await page.screenshot(path=str(SHOTS_DIR / "07-diagnostics.png"), full_page=True)
        print(" wrote 07-diagnostics.png (full page)")

        # 8. Backups tab ----------------------------------------------------
        await page.goto(f"{base_url}/backups", wait_until="domcontentloaded")
        await _wait_idle(page)
        await page.screenshot(path=str(SHOTS_DIR / "08-backups.png"), full_page=True)
        print(" wrote 08-backups.png (full page)")

        await browser.close()
        print(f"All screenshots written to {SHOTS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    args = parser.parse_args()
    asyncio.run(main(args.base_url))
