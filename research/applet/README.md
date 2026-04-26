# research/applet/ — `agent.jar` reference

The original Java applet `agent.jar` is **not redistributed in this
repository**. It is HPE's compiled software; reverse-engineering it for
interoperability is permissible in most jurisdictions (see e.g. EU
Software Directive Art. 6, US 17 USC §1201(f)), but redistributing the
binary itself is not.

## Where to obtain it

The applet is shipped by the switch itself. Mirror it directly from the
hardware once, then drop the resulting `agent.jar` into this directory.

```bash
# Replace 192.0.2.3 with your switch IP. Switch HTTP, no auth on factory firmware.
curl -fsS http://192.0.2.3/classes/agent.jar -o research/applet/agent.jar
```

## Reference SHA256

The Phase 0 reverse engineering was performed against:

```
agent.jar
  size:   183,453 bytes
  sha256: <fill-in-after-mirroring>
  source: HP ProCurve 2810-24G (J9021A), firmware N.11.78
```

If your switch ships a different firmware, the applet will likely have
a different SHA256 — reuse the Phase 0 protocol docs as a starting
point and re-decompile only the classes whose URL surface differs.

## Decompilation

The Phase 0 plan (`docs/plans/2026-04-23-procurve-webui-phase0.md`) used
[CFR](https://www.benf.org/other/cfr/). Output goes to
`research/decompiled/`, which is git-ignored — regenerate locally,
don't commit.
