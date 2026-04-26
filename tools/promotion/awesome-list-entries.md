# Awesome-list submissions

Each list has its own format and review criteria. The entries below are
pre-formatted to match — copy the entry into the right alphabetical slot
in the right section, open a PR, and write the rationale below in the PR
description.

Don't open all of these the same day; awesome-list maintainers see lists
of PRs as spam patterns. Two per week is a healthy cadence.

---

## awesome-sysadmin

**Repo:** https://github.com/awesome-foss/awesome-sysadmin
**Section:** `Network Monitoring and Troubleshooting` *or*
`Configuration Management` (look at recent merged PRs to confirm the
right section). The `Networking` heading also has a "Network Configuration
Management" subsection.

**Entry to add (alphabetical order):**

```markdown
- [procurve-webui](https://github.com/Fill84/procurve-webui) — Modern Java-applet-free web UI for the HP ProCurve 2810-24G (J9021A) switch. Single Docker container, FastAPI + React, talks the switch's stock eHTTP protocol. ([Source Code](https://github.com/Fill84/procurve-webui)) `MIT` `Docker`
```

**PR title:** `Add procurve-webui — modern UI for HP ProCurve 2810-24G`

**PR description:**

> Adds a small project I open-sourced this week. It's a single-container
> replacement for the management UI of the HP ProCurve 2810-24G (J9021A)
> — a managed gigabit switch from ~2008 whose original UI is a Java
> applet that no current browser can run.
>
> The project is MIT-licensed, ships a Dockerfile + compose, has a v0.1.0
> release with screenshots in the README, and includes full protocol
> docs in `research/protocol/` for anyone who wants to write their own
> client.
>
> Confirmed against a real 2810-24G on firmware N.11.78. Falls under
> "Network Configuration Management" because it's an out-of-band
> management UI for legacy network hardware.

---

## awesome-selfhosted (less obvious fit)

**Repo:** https://github.com/awesome-selfhosted/awesome-selfhosted
**Likely section:** `Software` → `Network Configuration Management`

**Note:** awesome-selfhosted is strict about "self-hosted alternatives to
SaaS". A switch management UI is a borderline case. Read their
[CONTRIBUTING.md](https://github.com/awesome-selfhosted/awesome-selfhosted/blob/master/CONTRIBUTING.md)
first — they may redirect you to awesome-sysadmin. Still worth a try
because the audience there is exactly right.

**Entry to add:**

```markdown
- [procurve-webui](https://github.com/Fill84/procurve-webui) - Java-applet-free management UI for HP ProCurve 2810-24G (J9021A) switches. Single Docker container; speaks the switch's stock eHTTP protocol. `MIT` `Docker`
```

(Note: awesome-selfhosted uses one hyphen between name and description,
not em-dash; it cares about that.)

---

## awesome-home-lab variants

**Candidate repos** (pick the one with the most stars + most recent
commit; the homelab-list landscape changes regularly):

- https://github.com/L1cardo/awesome-home-lab
- https://github.com/awesome-foss/awesome-homelab
- https://github.com/larsbrinkhoff/awesome-homelab

**Section:** "Network Tools" or "Networking" or similar.

**Entry:**

```markdown
- [procurve-webui](https://github.com/Fill84/procurve-webui) — modern web UI for legacy HP ProCurve 2810-24G switches whose Java-applet management UI no longer works in browsers.
```

---

## awesome-network-automation

**Repo:** https://github.com/networktocode/awesome-network-automation
**Likely section:** `Tools` → `Network Configuration Management`

**Entry:**

```markdown
- [procurve-webui](https://github.com/Fill84/procurve-webui) - HP ProCurve 2810-24G management UI replacement (no Java). Includes a typed Python client (`procurve_client/`) you can `pip install` and use to script the switch directly.
```

The Python client angle is what fits this list — it's a programmable
interface, not just a UI.

---

## What to do if a PR is rejected

- "Doesn't fit our criteria" → Move on. Don't argue.
- "Format wrong" → Fix and force-push. Don't open a second PR.
- "Looks too AI-generated" → Tighten the wording manually before
  opening: shorter sentences, drop adjectives, lead with the concrete.
- No response in 4 weeks → Polite single-line bump. No more after that.
