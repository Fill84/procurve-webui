# research/backups/ — reference config snapshots

Switch configuration backups (`.pcc` files) are **not committed to this
repository**. They contain operator-specific data (hostname, SNMP
contact / location, authorised-managers IP allow-list, …) that is not
appropriate to redistribute.

The original development workflow used a single user-verified
"reference baseline" backup as a write-test rollback target — see
[§7 of the design spec](../../docs/specs/2026-04-23-procurve-webui-design.md#7-safety-rules-development-time)
for the invariant.

## Recreating a baseline locally

```bash
curl -fsS "http://192.0.2.3/cgi/configfile?idx=1&fg=1&D1=Download" \
  -o research/backups/$(date -u +%Y-%m-%d)/CONFIG.pcc
```

Capture the SHA256 alongside it so write-test scripts can verify that
the post-restore config matches the pre-write state byte-for-byte.

```bash
sha256sum research/backups/2026-04-23/CONFIG.pcc
```

## Production backup management

End-user backup management (taking, listing, diffing, restoring) is
handled inside the running container by the **Backups** tab — see the
top-level [README](../../README.md#feature-tour). Those backups land in
the volume mounted at `/app/backups` inside the container, **not** in
this `research/` tree.
