# Security Policy

## Supported versions

Only the latest tagged release (and `main`) receive security fixes.

## Reporting a vulnerability

Please use **GitHub private vulnerability reporting** on this repository
(Security tab → "Report a vulnerability"). If that is unavailable, email the
maintainer address listed in `backend/pyproject.toml`.

Please do NOT open public issues for security problems — this tool holds
switch admin credentials in memory and can write to network hardware, so
give the fix a head start.

## Scope and threat model

The intended deployment is a **single trusted admin on a trusted LAN**,
published on `127.0.0.1` by default, plain HTTP (the managed switch itself
only speaks HTTP). Reports most valuable to this project:

- authentication/session bypasses,
- anything that lets a page or peer trigger **switch writes** without the
  READ_ONLY + auto-backup + host-confirmation gates,
- anything that lets an unauthenticated party induce **switch traffic
  amplification** (this hardware crashes under load — see the read-safety
  notes in CONTRIBUTING.md),
- credential leaks into logs, responses, or the build context.

Absence of TLS/HSTS on the default localhost deployment is a known,
documented trade-off, not a vulnerability.
