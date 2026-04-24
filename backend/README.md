# procurve_client

Async Python client library for the HP ProCurve 2810-24G (J9021A) switch.
Talks to the switch using the same HTTP protocol the legacy Java applet used.

## Install (dev)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # (Windows Git Bash / WSL: .venv/bin/activate)
pip install -e ".[dev]"
```

## Run tests

```bash
pytest                         # unit + mocked-operation tests only
pytest -m live                 # live reads against 192.0.2.3 (requires access)
pytest -m roundtrip            # write-verify-restore (requires user approval)
```

## Public API

All operations are `async` and take a `ProcurveTransport` as first argument.
Operations are grouped by tab and imported from `procurve_client.operations`.

```python
from procurve_client import ProcurveTransport
from procurve_client.operations.backup import download_config

async def main():
    async with ProcurveTransport(host="192.0.2.3") as t:
        cfg = await download_config(t)
        print(cfg.size, cfg.sha256)
```

See `docs/superpowers/specs/2026-04-23-procurve-webui-design.md` for the
architecture background.
