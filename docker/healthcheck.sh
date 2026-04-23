#!/bin/sh
# Liveness probe — hits /api/v1/health via the stdlib urllib (no curl dependency).
# The health endpoint returns 200 when the switch is reachable and 503 otherwise.
# We treat 503 as "container is alive, switch is unreachable" — that is a config
# problem, not a container problem — so both 200 and 503 count as healthy here.
exec python -c "
import sys, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3).read()
    sys.exit(0)
except urllib.error.HTTPError as e:
    sys.exit(0 if e.code == 503 else 1)
except Exception:
    sys.exit(1)
"
