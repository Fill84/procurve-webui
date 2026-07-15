# Mirror capture 2026-07-15 — QoS sub-pages

Supplementary capture closing audit finding F2: the 2026-04-23 mirror only
included `cos_mainf.html` / `cos_menu.html`; the per-subtab QoS pages the
protocol docs cite were missing.

Captured with the project's own `ProcurveTransport` (serialized requests,
3 s pacing per the read-safety rule) from 192.168.178.3, firmware state as
of this date. 22 pages under `configuration/`:

- Frameset/menu: `cos_menu1`, `cos_menu3`
- Application priority: `cos_appf` (frameset), `cos_app1`–`cos_app6`
  (incl. `cos_app3a`, `cos_app5`, `cos_app5a` — the src/DSCP/802.1p
  picker frames; `cos_app5*` were not cited by any doc before this capture)
- Device (per-IP) priority: `cos_user1`–`cos_user3`
- VLAN priority: `cos_vlan0`–`cos_vlan3`
- ToS / DiffServ: `cos_tos`, `cos_tosds`, `cos_dscpt`
- Protocol priority: `cos_proto`

Key observations recorded in the protocol docs' 2026-07-15 banners:
form field names + select value domains all match the implementation;
the cross-frame submit orchestration (applet-era) remains the only
unverified part of the QoS write contracts.
