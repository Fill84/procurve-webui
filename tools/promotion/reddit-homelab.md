# Reddit — r/homelab post

**Where:** https://www.reddit.com/r/homelab/submit
**Type:** Link post (URL: GitHub release page) — and use the body field for
context. Do NOT use a "self post" with the GitHub URL only in the body;
r/homelab's automod is strict about that.

**Best timing:** Tuesday–Thursday, 14:00–18:00 UTC.

**Flair:** "Projects"

---

## Title

```
I rebuilt the management UI for a 17-year-old HP ProCurve switch because the original Java applet won't run anymore
```

## URL

```
https://github.com/Fill84/procurve-webui/releases/tag/v0.1.0
```

## Body

> Hardware: HP ProCurve Switch 2810-24G (J9021A), firmware N.11.78. Solid
> piece of kit — gigabit, managed, fanless, runs forever. The catch is
> that its management UI is a Java applet (`agent.jar`) that hasn't
> worked in a browser since Chrome killed NPAPI in 2015.
>
> So I reverse-engineered the protocol the applet uses (decompiled it
> with CFR, documented all the CGI endpoints, captured live response
> fixtures) and rebuilt the UI as a single Docker container:
>
> - Python/FastAPI backend that speaks the switch's stock eHTTP protocol
> - React 18 + Tailwind frontend with a live SVG chassis render and
>   port-traffic gauges
> - One container, one process. `docker compose up -d` and you're done.
> - Read-only by default; writes auto-take a `.pcc` backup first.
> - No Java anywhere in the stack.
>
> Screenshots in the README: https://github.com/Fill84/procurve-webui#screenshots
>
> v0.1.0 is the first public release, MIT licensed. If anyone here
> still has a 2810-series running and wants to confirm it works on their
> hardware, I'd love a reply or an issue — only J9021A is "confirmed";
> J9022A (the 48-port variant) is "likely works, untested".

## After posting

Same rule as HN: reply once briefly to early comments if there's
something useful to say, then walk away. r/homelab readers are mostly
sympathetic to "kept old hardware alive" stories so this is a friendlier
audience than HN.

Common questions:

- *"Why not pick up a Mikrotik / used Cisco for €50?"* → Honest answer:
  this switch already does the job, the project was about not throwing
  working hardware away.
- *"Does it work on the 2520 / 2510 / 2610?"* → No, those run different
  firmware lines (K.x, R.x). Same applet pattern probably exists but the
  CGI surface differs — would need its own Phase 0.
- *"Is it on Docker Hub?"* → Currently `git clone && docker build`. CI
  publishing to ghcr.io is staged (see `tools/promotion/release-docker.yml.template`).
