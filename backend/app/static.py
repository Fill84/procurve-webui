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

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

# Vite emits content-hashed filenames under assets/ — a changed file always
# gets a new URL, so the old URL may be cached forever.
_IMMUTABLE = "public, max-age=31536000, immutable"
# index.html references the current hashed bundles by name; browsers must
# revalidate it so a deploy is picked up on the next navigation.
_REVALIDATE = "no-cache"
# Unhashed dist-root files (favicon.svg, robots.txt): cache briefly.
_SHORT = "public, max-age=3600"


class HashedAssetFiles(StaticFiles):
    """StaticFiles that serves Vite's content-hashed bundles as immutable."""

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = _IMMUTABLE
        return response


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
    if not (dist_dir / "index.html").is_file():
        # Partial / in-progress build — refuse to mount a broken SPA rather
        # than 500 on every request.
        return
    if not (dist_dir / "assets").is_dir():
        # No hashed-bundles directory — same rationale as above.
        return

    # Serve hashed assets under /assets with long-cache headers.
    app.mount(
        "/assets",
        HashedAssetFiles(directory=dist_dir / "assets"),
        name="assets",
    )

    # Client-side routing: any unmatched GET first tries to serve a real file
    # from dist/ (favicon.svg, robots.txt, etc.) and otherwise falls through
    # to index.html so React Router can handle deep links on hard-refresh.
    dist_root = dist_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path:
            candidate = (dist_dir / full_path).resolve()
            try:
                candidate.relative_to(dist_root)
            except ValueError:
                pass
            else:
                if candidate.is_file():
                    return FileResponse(
                        candidate, headers={"Cache-Control": _SHORT}
                    )
        return FileResponse(
            dist_dir / "index.html", headers={"Cache-Control": _REVALIDATE}
        )
