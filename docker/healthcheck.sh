#!/bin/sh
# Container liveness probe — hits /api/v1/health/live via the stdlib urllib
# (no curl dependency).
#
# IMPORTANT (switch read-safety): this MUST stay on the /live endpoint, which
# never contacts the switch. The old probe went to /api/v1/health, which used
# to open a fresh connection to the physical switch on every call — a 24/7
# background probe against hardware that has crashed under repeated probing.
# Switch reachability is a config concern, not a container-health concern.
#
# Honors the same PORT override entrypoint.sh passes to uvicorn.
exec python -c "
import os, sys, urllib.request
port = os.environ.get('PORT', '8080')
try:
    urllib.request.urlopen(
        f'http://127.0.0.1:{port}/api/v1/health/live', timeout=3
    ).read()
    sys.exit(0)
except Exception:
    sys.exit(1)
"
