# dev.to article — long-form

**Where:** https://dev.to/new
**Recommended tags:** `reverseengineering`, `homelab`, `python`, `react`,
`networking` (4 max).
**Cover image:** use `docs/screenshots/03-status.png` from the repo.
**Canonical URL:** `https://github.com/Fill84/procurve-webui` (set under
"Editor settings" → "Canonical URL" so Google credits the GitHub repo, not
dev.to).

---

## Title

```
Reverse-engineering a 17-year-old Java applet to give an enterprise switch a new web UI
```

## Subtitle / "What's it about" field

```
HP killed Java in browsers. The switch still works. So I decompiled the management applet, documented all 50+ CGI endpoints, and rebuilt the UI in FastAPI + React.
```

---

## Body

There's an HP ProCurve Switch 2810-24G (J9021A) in my server room. It's
a 24-port managed gigabit switch from circa 2008. Solid hardware,
fanless after a year of break-in, runs forever, draws ~30 W. There's
exactly one thing wrong with it: its management UI is a Java applet
(`agent.jar`) and no current browser will run it.

I had three options:

1. Buy a new switch. (Working hardware to landfill, ~€200 for a
   replacement. Felt wrong.)
2. Stick to the CLI forever and never click anything again. (Doable, but
   for "rename ports 13 and 14 to 'lab-bench-1' and 'lab-bench-2'" the
   GUI is a much better tool.)
3. Reverse-engineer the protocol the applet uses and rebuild the UI.

This is about option 3.

## Phase 0 — what's in `agent.jar`

The applet weighs 183 KB. It contains 80 `.class` files. Every HTML page
on the switch has an `<applet>` tag that names a class plus a bunch of
`<param>` entries — page title, table-column metadata, the `basecgiurl`
for that family of operations, and so on. The HTML pages themselves
don't contain the URLs to the CGI endpoints; those are baked into the
Java bytecode.

So step one: full HTTP mirror of the switch's static assets. `wget --mirror`
walks the entire `/identity/`, `/status/`, `/configuration/`, `/security/`,
`/diagnostics/`, `/support/` tree and gives you all the HTML, JS, and
GIF files plus `agent.jar` itself.

Step two: decompile. I picked **CFR** (`https://www.benf.org/other/cfr/`)
over jd-cli and procyon because CFR preserves original string literals
where the URL constants live — exactly the thing you want when the
operation URLs are embedded as `private static final String` fields.

```bash
java -jar cfr.jar agent.jar --outputdir research/decompiled/
```

Output: 80 `.java` files. Most are utility classes — table renderers,
event dispatchers, dialog boxes. The interesting ones are:

- `PageSelector` — top-level navigation (which class handles which tab).
- `CallbackClient` — generic HTTP request builder. URL constants live
  here.
- `ResultProcessor` — response parser, hard-codes the response format.
- `DeviceStatus` / `VLANmain` / `StackConfig` / etc. — one class per
  page, each with a `getURL()`-style method that builds the operation's
  query string.

A couple of `grep` runs (`URL`, `openConnection`, `getInputStream`, `?`)
gave me the full list of CGI endpoints the applet talks to: ~50 GET
operations and 2 POSTs (config download and config upload).

## What the protocol actually looks like

Every reverse engineering project has a moment where you go "wait,
*all* of it is like that?" Mine was when I realised:

**Every applet operation is a GET. Even mutations.**

```
http://192.168.1.3/cgi/addVLAN?VLAN_ID=5&VLAN_NAME=Guest
http://192.168.1.3/cgi/set_port_config?indeces=18&NM=UPS-APC&...
http://192.168.1.3/cgi/delVlan?VLAN_ID=5&VLAN_ID=6&VLAN_ID=7
```

Yes, you delete VLANs by GET-ting a URL with the IDs in the query string,
and yes, multi-select uses repeated query keys. POST is only used for
the binary config download (`/cgi/configfile`) and upload (`/cgi/upload`).

Responses are equally minimalist: plain ASCII, tilde-delimited fields,
`OK~field1~field2~field3\r\n` for success, `error~message\r\n` for
failure. Multi-record responses repeat the line shape.

```
OK~1~UPS-APC~~100/1000T~Yes~Up~1000FDx~~off~0
OK~2~wifi-ap-lobby~~100/1000T~Yes~Up~1000FDx~~off~0
OK~3~wifi-ap-floor2~~100/1000T~Yes~Up~1000FDx~~off~0
```

No JSON, no XML, no Content-Type. The first line of every response
contains the success/error sentinel. Wire position 2 in port-status
records is a hidden decorative label cell ("UPS" on labelled ports,
single space otherwise) that the GUI uses for asset tagging. Wire
position 9 is a trailing integer always observed as `0`; I preserved
it as `_extra` for round-trip fidelity, but I have no idea what it's
for.

## The misspelling that mattered

The port-configuration CGI takes a query parameter for which ports to
operate on. In the decompiled Java:

```java
String query = "indeces=" + ports.stream()
    .map(String::valueOf)
    .collect(Collectors.joining(","));
```

That's not a typo on my part. It's spelled `indeces` in the firmware
and Java code. The switch checks for that exact string. If you "fix"
it to the correctly-spelled `indices`, the firmware silently accepts
the request and applies it to no ports.

This is why my Python client has byte-for-byte fidelity asserted in
unit tests. Each write operation has a "request template" derived from
the decompiled Java (`expected_query = "indeces=18&NM=UPS-APC&..."`)
and the test compares the bytes the client produces against the template
character-by-character. If the URL encoder ever decides to URL-encode a
comma, or a `+` becomes a `%20`, the test fails before any byte goes on
the wire.

A few other quirks worth remembering for anyone hitting this kind of
firmware:

- The applet's `URLEncoder.encode` emits `+` for spaces (the standard
  Java behavior, but contrast with `urllib.parse.quote` which emits
  `%20` by default). httpx and `urlencode` from Python's stdlib match
  the Java behavior; `requests`' default does too. Just don't get
  clever and switch encoders mid-stream.
- The applet emits no `Authorization` header. The Java plugin reuses
  the browser's HTTP Basic session. The Python client sends Basic
  explicitly when configured; on factory firmware blank user / blank
  password works.
- The switch's management CPU has been observed to crash under
  high-frequency probing — ~3 Hz from `curl` in a loop is enough.
  My poll cadence defaults to 2 seconds, and the UI pauses polls when
  the browser tab is hidden.

## Building it back up

Once the protocol was documented, the rebuild was conventional:

- **`procurve_client/`** — pure-Python async library. Pydantic v2 for
  every request and response, one operation per CGI, decorated `@READ`
  or `@WRITE`. The decorators carry metadata (no behavior) so a
  `READ_ONLY=true` env flag can short-circuit every write at runtime.
- **`app/`** — FastAPI on top of the client. One router per tab, sessions
  signed with itsdangerous, switch credentials kept only in backend RAM
  and the browser cookie (no separate user database). WebSocket for
  live port traffic.
- **`frontend/`** — React 18, TanStack Router/Query, Tailwind, Recharts.
  TypeScript types are generated from the FastAPI `/openapi.json` via
  `openapi-typescript` — no hand-written API types.
- **One Docker container** that runs uvicorn and serves the pre-built
  React bundle from the same FastAPI process. `docker compose up -d`
  and you're done.

## Stuff I'd do differently

- **The protocol docs are the most valuable output.** The UI is nice
  but anyone could re-implement it in a weekend. The
  `research/protocol/` tree lets someone build an Ansible module, a
  Prometheus exporter, an SNMP bridge, or a Go agent without ever
  decompiling anything. If you're reverse-engineering legacy hardware
  and you don't want to feel like you're starting from zero in three
  years when you forget how it worked, write the protocol docs first.
- **Keep the binary out of the repo.** The original applet is HPE's
  software; redistributing it is murky. The `research/applet/` README
  shows a one-line `curl` to mirror it from your own switch — that
  scales legally and respectfully.
- **Don't poll the switch from CI.** Live tests are useful locally,
  catastrophic in CI. They're marked with a pytest marker and never
  run by default.

## Try it

```bash
git clone https://github.com/Fill84/procurve-webui.git
cd procurve-webui
cp .env.example .env
# Edit .env: SWITCH_HOST + a random SESSION_SECRET
docker compose up -d
```

Repo + screenshots + protocol docs:
**https://github.com/Fill84/procurve-webui**

If you've got a J9022A (the 48-port variant) or any other 2810-series
running and want to confirm whether the same protocol works on yours,
that'd be amazing — open an issue.
