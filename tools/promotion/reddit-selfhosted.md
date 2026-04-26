# Reddit — r/selfhosted post

**Where:** https://www.reddit.com/r/selfhosted/submit
**Type:** Link post (URL: GitHub repo).
**Flair:** "Release" or "Self-Hosted"
**Note:** r/selfhosted's automod requires a real description in the body
(not just the URL). Keep the body short and Docker-forward.

---

## Title

```
procurve-webui v0.1.0 — self-hosted Java-applet-free management UI for HP ProCurve 2810-24G switches
```

## URL

```
https://github.com/Fill84/procurve-webui
```

## Body

> If you're running an old HP ProCurve 2810-24G in your homelab and
> can't open its web UI any more (Java applet, RIP), here's a single-
> container replacement:
>
> ```
> git clone https://github.com/Fill84/procurve-webui.git
> cd procurve-webui
> cp .env.example .env
> # edit .env: SWITCH_HOST + a random SESSION_SECRET
> docker compose up -d
> ```
>
> Then http://localhost:8080. Switch is the identity provider, so log
> in with whatever user/password the switch already expects (blank/blank
> on factory firmware).
>
> Stack: Python/FastAPI + React 18, talks the switch's stock HTTP
> protocol — no Java, no SNMP setup, no separate database. Read-only by
> default; write endpoints auto-take a `.pcc` backup before any change.
> Backups tab lets you list/diff/restore them later. MIT licensed.
>
> Screenshots in the README. Bind defaults to `127.0.0.1:8080`; if you
> expose to the LAN do TLS-termination with Caddy/Traefik first because
> HTTPS isn't built in yet (v0.2.0 territory).
