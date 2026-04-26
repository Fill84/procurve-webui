# Reddit — r/networking post

**Where:** https://www.reddit.com/r/networking/submit
**Type:** Link post.
**Flair:** "Other"
**Important:** r/networking is more skeptical than r/homelab. Lead with the
technical content (the reverse-engineering), not the "I built a tool"
angle.

---

## Title

```
Reverse-engineered the management protocol for HP ProCurve 2810-24G — open-source replacement web UI
```

## URL

```
https://github.com/Fill84/procurve-webui
```

## Body

> The 2810-series web UI is a Java applet that no current browser can
> load. SSH/CLI still works, but for "show me port 17 right now" or
> "rename ports 13–14" the GUI was the natural tool. So I worked through
> the applet's HTTP protocol and built a clean replacement.
>
> Most of what's interesting is in `research/protocol/` — one Markdown
> file per CGI endpoint, with URL template, query parameters, response
> shape, validation rules sourced from the decompiled Java, and a live
> response fixture for the read endpoints. Patterns I noticed:
>
> - All applet operations are GET, even mutations. `addVLAN`,
>   `set_port_config`, `delVlan` — query string only. Only config
>   download/upload uses POST.
> - Tilde-delimited ASCII responses with an `OK~…` / `error~…` sentinel
>   on the first line. Multi-record responses repeat the line shape.
> - Some query keys are misspelled in the firmware (`indeces` for
>   "indices") and the firmware checks for them literally; the Python
>   client preserves wire-level fidelity and asserts byte-for-byte
>   against templates derived from decompilation.
> - Auth is HTTP Basic; on factory firmware blank user/blank password
>   works. The webui supports both transparently — switch is the
>   identity provider, no separate user database.
>
> Implementation: Python/FastAPI backend with a typed `procurve_client`
> library (Pydantic v2 models for everything, async, ~90% coverage),
> React 18 SPA, single Docker container. Read-only by default; writes
> automatically take a pre-write backup of the running config.
>
> https://github.com/Fill84/procurve-webui
>
> Confirmed working on J9021A firmware N.11.78. If anyone here has
> J9022A (48-port) or another 2810 firmware in production and wants to
> confirm it works, please open an issue — that table in the README has
> exactly one row in "confirmed" and lots of "likely, untested".

## What r/networking will probably ask

- *"What about Aruba's CX or AOS-S newer kit?"* → Out of scope; this is
  about keeping legacy 2810-series alive. Newer kit has working web UIs.
- *"Did you try OpenWRT or any FOSS firmware?"* → 2810 doesn't support
  it, the bootloader is signed.
- *"Why FastAPI and not Go/Rust?"* → Reach. Pydantic v2 + FastAPI gets
  you OpenAPI types for free, and the audience for this is mostly homelab
  / sysadmin folks who'd rather hack on Python than Rust.
- *"Is there a chance HPE pulls a takedown?"* → The binary applet isn't
  redistributed (`research/applet/README.md` explains how to mirror it
  from your own switch); the protocol docs are clean-room reverse
  engineering for interoperability, which is permitted under EU
  Software Directive Art. 6 and US 17 USC §117/§1201(f).
