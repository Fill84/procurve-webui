"""SPA static-file hosting for the built React frontend.

The frontend is built into `dist/` by the Vite pipeline. In production the
Docker image copies that tree into `/app/frontend/dist`. Mounting this:

* serves hashed bundles under `/assets/*` directly (long-cache friendly),
* falls through every unmatched GET to `index.html` so that client-side
  routing (React Router) works on hard-refresh / deep links.

The mount is skipped gracefully when the dist directory is missing so that
local dev (backend-only, no built frontend) keeps working.

IMPORTANT: `mount_static` MUST be called AFTER every `/api/v1/*` and `/ws/*`
route is registered — the SPA fallback is a catch-all and would shadow them
otherwise.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_static(app: FastAPI, dist_dir: Path) -> None:
    """Mount the built frontend at `/` with SPA fallback.

    Args:
        app: The FastAPI app; all API/WS routes must already be registered.
        dist_dir: Path to the built Vite `dist/` directory. If it does not
            exist (typical during dev before `npm run build`), the mount is
            skipped silently.
    """
    if not dist_dir.is_dir():
        # During dev the frontend may not be built yet — skip gracefully.
        return

    # Serve hashed assets under /assets with long-cache headers.
    app.mount(
        "/assets",
        StaticFiles(directory=dist_dir / "assets"),
        name="assets",
    )

    # Client-side routing: any unmatched GET falls through to index.html.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        return FileResponse(dist_dir / "index.html")
