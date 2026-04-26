# Hacker News — Show HN post

**Where:** https://news.ycombinator.com/submit
**Best timing:** Tuesday–Thursday, 13:00–18:00 UTC (08:00–13:00 US Eastern).
Avoid Mondays and weekends.

---

## Title

Use one of these (all under 80 chars, the soft cap that gets truncated on
the front page):

```
Show HN: A modern web UI for the HP ProCurve 2810-24G switch (no Java)
```

```
Show HN: Reverse-engineered an HP switch's dead Java applet to give it a new UI
```

```
Show HN: Procurve-webui – Java-applet-free management UI for old HP switches
```

The first one is the most accessible. Use that.

## URL field

```
https://github.com/Fill84/procurve-webui
```

## Text field (optional but recommended)

> Hi HN,
>
> Like a lot of homelabs, mine still has an HP ProCurve 2810-24G (J9021A)
> sitting in the rack. Great hardware — gigabit, managed, fanless after a
> 12-month break-in, very stable. The catch: its management UI is a Java
> applet (`agent.jar`) that no modern browser will run.
>
> Rather than buy a new switch I spent a few weekends reverse-engineering
> the protocol. The applet talks to ~50 CGI endpoints with tilde-delimited
> ASCII responses (`OK~field1~field2…`). I decompiled it with CFR,
> documented every endpoint under `research/protocol/`, captured live
> response fixtures, and built a typed Python client around it. Then a
> FastAPI service on top, then a React 18 SPA, all in one Docker
> container.
>
> What's there now (v0.1.0):
>
> - Live switch chassis render with per-port LEDs
> - Port-utilisation graph fed by a WebSocket
> - Read + write for Identity / Status / Configuration / Security /
>   Diagnostics / Backups / Support tabs
> - Read-only by default; writes are pre-backed-up automatically
> - Switch is the identity provider — no separate user database
>
> The protocol layer (`procurve_client/`) is a separate, pip-installable
> Python package, so if you just want to script your switch from Python
> you can skip the UI entirely.
>
> A few things I learned along the way that might be interesting:
>
> - Every "mutation" in the applet is a GET — even VLAN creation. POST is
>   only used for config download/upload.
> - The applet's URL encoder spells "indices" as `indeces` (sic) and the
>   firmware checks for that exact misspelling. Byte-for-byte fidelity
>   matters; my write tests assert against templates derived from the
>   decompiled Java.
> - This switch's management CPU is small enough that high-frequency
>   probing crashes it. The default poll interval is 2 s and the UI
>   pauses polls when the tab is hidden.
>
> Apache 2.0 — sorry, MIT. Hardware target is the J9021A on firmware
> N.11.78; other 2810-series boards probably work but I have no way to
> test them. Confirmation reports very welcome.
>
> Repo + screenshots: https://github.com/Fill84/procurve-webui

## After posting — first 30 minutes (one-shot)

If the post gets any comments at all in the first 30 minutes, reply to
each one *once*, briefly, and only if you have something useful to add
("good point", "no I haven't tried X but here's why", "yes that's
documented at link…"). After 30 min, walk away. No replies = ignored,
which is fine.

Common comments to be ready for:

- *"Why not just use SNMP?"* → SNMP only covers monitoring; this also
  does writes (port config, VLAN, etc.) without needing CLI access.
- *"Why bother, just buy a new switch?"* → Anti-e-waste angle; the
  hardware works fine.
- *"Did HPE complain about agent.jar?"* → No, and the binary itself
  isn't redistributed; users mirror it from their own switch.
- *"Is this AGPL-tainted?"* → No, MIT licensed.

## Don't

- Don't resubmit if it flops. One Show HN per project, ever.
- Don't ask anyone to upvote you. HN's vote-ring detection is good and
  killing the post via mod action is worse than a flop.
- Don't post the same wording on Reddit on the same day. Wait at least
  48 hours so HN doesn't see the cross-post and downrank.
