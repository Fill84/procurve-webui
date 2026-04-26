# Reddit — r/ReverseEngineering post

**Where:** https://www.reddit.com/r/ReverseEngineering/submit
**Type:** Link post.
**Flair:** "Resource" or "Code"

This subreddit appreciates the technical detail of *how* the protocol
was extracted, not "I built a UI". Lead with `agent.jar` and the Java
decompilation.

---

## Title

```
Decompiled an HP switch's Java management applet to document its CGI protocol — full clean-room reverse engineering, MIT
```

## URL

```
https://github.com/Fill84/procurve-webui/tree/main/research/protocol
```

(Direct link to the protocol docs folder, not the repo root — that's what
this audience wants to see first.)

## Body

> The HP ProCurve 2810-24G is a managed gigabit switch from ~2008 whose
> management UI is a Java applet (`agent.jar`, 183 KB, 80 class files).
> It hasn't loaded in a browser since NPAPI was removed. SSH/CLI still
> works but the GUI was the natural way to drive it for ad-hoc changes.
>
> Approach:
>
> 1. **Asset mirror** — full HTTP mirror of the switch's HTML, JS, GIFs.
>    The HTML pages carry `<param>` tags on `<applet>` elements that
>    act as a directory: which Java class implements which page, plus
>    the `basecgiurl` for that family of operations.
>
> 2. **JAR decompilation** — CFR. Picked over jd-cli/procyon because it
>    preserves original string literals where the URL constants live.
>    Output: 80 .java files I could grep through for `URL`,
>    `openConnection`, `getInputStream`, and `?` query delimiters.
>
> 3. **Per-operation protocol docs** — one Markdown file per CGI under
>    `research/protocol/<tab>/<operation>.md`, format documented in
>    `research/protocol/_conventions.md`. Each doc has URL template,
>    query parameters, response shape, validation rules sourced from
>    the decompiled Java, error patterns, and a sample request/response.
>
> 4. **Live verification (reads only)** — captured response samples to
>    `research/fixtures/`. These become unit-test inputs for the Python
>    client.
>
> 5. **Byte-match request templates for writes** — built request
>    templates from the decompiled `URLEncoder.encode` calls and asserted
>    that the Python client produces byte-identical output. Critical
>    because some firmware checks for misspelled keys literally — e.g.
>    the port-config CGI uses `indeces` (sic) instead of `indices`, and
>    the switch rejects the correctly-spelled version.
>
> Things that turned out to be interesting:
>
> - All applet operations are GET. Mutations like `addVLAN` and
>   `set_port_config` encode arguments into the query string. POST is
>   used only for `/cgi/configfile` (download) and `/cgi/upload`
>   (upload).
> - Responses are tilde-delimited ASCII, `OK~field1~field2…\r\n` or
>   `error~message\r\n`. Multi-record responses repeat the line shape.
> - The applet emits no `Authorization` header; it relies on the Java
>   plugin to reuse the browser's HTTP Basic session. The Python client
>   sends Basic explicitly when configured.
> - The switch's management CPU is small enough that high-frequency
>   probing crashes it (3+ Hz from `curl` is enough). The webui's poll
>   cadence defaults to 2 s and pauses when the browser tab is hidden.
>
> The reverse-engineering output (`research/`) is a separate deliverable
> from the webui itself — anyone wanting to write a different client
> (CLI, SNMP bridge, Ansible module, Go agent) can ignore the FastAPI/
> React layer and just read the protocol docs.
>
> Note: the binary applet (`agent.jar`) itself is NOT redistributed —
> see `research/applet/README.md` for how to mirror it from your own
> switch in a single `curl` command. The protocol docs are clean-room
> output and the project is licensed MIT.
