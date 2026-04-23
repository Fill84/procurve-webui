# support_redirect

**Tab:** support
**Kind:** read (static HTML — no protocol operation)
**Source in applet:** none.
**Source in HTML:**
  - `research/mirror/2026-04-23/support/index.html`
  - `research/mirror/2026-04-23/support/support_blank.html`

## Overview

The Support tab of the 2810 web UI is a pure static HTML redirect to
ProCurve's external web resources. There is no CGI endpoint, no switch
state read, and no local operation to implement.

`support/index.html` is a two-row frameset:

```
<frameset rows=0,* border=0 frameborder=0 framespacing=0>
    <frame src=support_blank.html noresize scrolling=no ...>
    <frame src="http://www.procurve.com" name=nc_view noresize ...>
        <!--http://www.hp.com:80/rnd/support/support.htm-->
</frameset>
```

The first frame is the invisible tab-sync helper (`support_blank.html`
just runs the `navAid1("support")` JavaScript that highlights the
"Support" tab in the top navigator). The second frame loads the
external URL `http://www.procurve.com`. The HTML comment shows that the
original target was `http://www.hp.com:80/rnd/support/support.htm` —
both URLs are long-since superseded by HP's current support portal
(`support.hpe.com` / Aruba ProCurve product pages).

## HTTP contract

None. The tab performs a single HTTP GET out to the public internet,
initiated by the user's browser — not by the switch. The switch is not
a participant in that request.

## Implementation guidance for the new UI

The new Python/FastAPI + React UI has three reasonable options:

1. **Omit the tab entirely.** The legacy Support tab is effectively
   dead — `procurve.com` no longer exists as a live site and the target
   URL in the mirror is a 404/redirect chain. Most modern management
   UIs drop this kind of static link.
2. **Replace with a static link.** Render a footer / About-menu item
   linking to the current Aruba/HPE support portal for the 2810 series
   (J9021A). This is the lowest-effort replacement.
3. **Embed an iframe.** If the user wants feature-parity with the old
   UI, embed an iframe pointing at the current support URL. This has
   the usual iframe caveats (CORS, X-Frame-Options, mixed-content for
   the HTTP management session loading an HTTPS external page).

No fixture is needed for this tab — there is no byte-level protocol to
lock down.

## Notes & caveats

- The original URL (`http://www.procurve.com`) is unreachable in 2026.
  The new UI should not hard-code it; at minimum point to
  `https://www.hpe.com/us/en/networking.html` or the latest Aruba
  equivalent, ideally with the link externalized to configuration so
  it can be updated without a code change.
- No switch state is exposed or consumed here; the Support tab does
  not count against the protocol inventory.
