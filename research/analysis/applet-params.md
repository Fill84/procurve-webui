# Applet `<param>` cross-reference

Generated 2026-04-23 from `research/mirror/2026-04-23/`; raw hits in
`applet-params.raw.txt` (case-insensitive `<param name=` grep —
`configuration/vlan.html` and `status/portgraph.html` use uppercase
`<APPLET>` / `<Param>` so a literal lowercase match would miss them).

Sections are listed in the order `grep -rliE '<applet'` returned the
files (alphabetical within the mirror tree).

## /configuration/device_view.html

Applet: `XFishBob.class` (`archive=agent.jar`, `codebase=../classes`,
`name=bob`, `width=822`, `height=120`).

- `offLED=787878` — hex colour for an LED in its "off" state.
- `getURL=../cgi/get_bobports` — endpoint the applet polls to load
  per-port state (overrides the class default; see `XFishBob.java:54`).
- `setURL=../cgi/set_bobports` — endpoint used to push admin-state
  changes (see `XFishBob.java:60`).
- `isdual=true` — model is a dual-row front panel.
- `statusLine=5~115~000000~Helvetica~0~11~ProCurve Switch 2810-24G Closeup View.~`
  — x~y~colour~font~style~size~text; the footer banner under the
  rendered front panel.
- `components=...` (multi-line macro block) — the full front-panel
  geometry spec: transceiver groups, port banks, LEDs, console box,
  logo placement. Parsed by `XFishBob` via the `GenericBob`
  component-DSL reader.

## /configuration/menu.html

Applet: `PageSelector.class` (`archive=agent.jar`, `name=Buttons`,
`width=100%`, `height=70`, `codebase=../classes`).

- `target=nc_view` — frame name clicks are retargeted to.
- `columns=4` — four buttons per row in the rendered grid.
- `buttons=` (tilde-delimited, comma-separated) — twelve sub-tabs:
  `devview~Device View~../configuration/device_viewf.html~selected`,
  `faultdetect~Fault Detection~../configuration/web_agentf.html`,
  `system~System Info~../configuration/systemf.html`,
  `ip~IP Configuration~../configuration/ipf.html`,
  `ports~Port Configuration~../configuration/portsf.html`,
  `qos~Quality of Service~../configuration/cos_mainf.html`,
  `monitor~Monitor Port~../configuration/monitorf.html`,
  `devfeatures~Device Features~../configuration/featuresf.html`,
  `stacking~Stacking~../configuration/stack_configf.html`,
  `vlan~VLAN Configuration~../configuration/vlan.html`,
  `support~Support/Mgmt URL~../configuration/supportf.html`,
  `uploadf~Upload/Download~../configuration/configfilef.html`.
- `selection=devview` — the initially-raised button.

## /configuration/ports1.html

Applet: `GenericList.class` (`archive=agent.jar`, `name=list`,
`codebase=../classes`, `width=100%`, `height=100%`).

- `dataURL=../cgi/get_portscfg` — row-data endpoint (GET, tilde-delimited
  response per Task 0.7).
- `formURL=../cgi/port_form` — per-row edit target (click -> form).
- `target=nc_view` — frame to navigate into on form open.
- `titles=Port~Port Name~Port%Type~Enabled~?Status~Config%Mode~?Trunk~Flow%Control`
  — column headers (tilde-delimited; `%` is a decoded-space escape,
  leading `?` marks a column that can be toggled hidden).
- `columns=60~150:x~240~330~339:h~420~429:h~510` — pixel x-positions;
  `:x` = extensible/resizeable, `:h` = hidden by default.
- `params=.~.~.~.~.~.~.~.~.` — per-column render/edit type; `.` is the
  default (plain text).

## /configuration/vlan.html

Applet: `VLANmain.class` (`archive=agent.jar`, `name=VLANmain`,
`codebase=../classes`, `width=100%`, `height=100%`). Note: tags are
uppercase in this file (`<APPLET>`, `<Param>`).

- `family=1` — switch family discriminator read by `VLANmain`; decides
  which VLAN feature set (e.g. protocol panel, GVRP panel) to expose.
- `basecgiurl=../cgi/` — the prefix the VLAN applet joins to every
  command string (`addVLAN`, `delVLAN`, `getVLANAll`, …). Corresponds
  to `VLANmain.java:28, 41` (`PARAM_baseCgiUrl = "basecgiurl"`).

## /diagnostics/menu.html

Applet: `PageSelector.class` (`archive=agent.jar`, `name=Buttons`,
`codebase=../classes`, `width=100%`, `height=22`).

- `target=nc_view` — content frame.
- `buttons=` — three diagnostics sub-tabs:
  `ping~Ping / Link Test~../diagnostics/pingf.html~selected`,
  `reset~Device Reset...~../diagnostics/resetf.html`,
  `config~Configuration Report~../diagnostics/configf.html`.

## /ncidbar.html

Applet: `DeviceStatus.class` (`archive=agent.jar`, `name=DeviceStatus`,
`codebase=classes`, `width=400`, `height=26`). The persistent
top-of-page status banner.

- `url=../cgi/fflog?action=status` — polled endpoint for the device
  alert/status line.
- `delay=30` — poll interval in seconds.
- `clickUrl=../ncfw_b.html?index=` — click-through URL (index is
  appended when the user clicks an alert).
- `clickTarget=proxyf` — frame to open the click-through in.
- `text1=ProCurve Switch 2810-24G (J9021A)` — static device label
  rendered to the left of the polled status.

## /nctabs.html

Applet: `PageSelector.class` (emitted via `document.write`;
`archive=agent.jar`, `name=Tabs`, `codebase=classes`, `width=101%`,
IE-specific `height=100%` vs `height=38` for other browsers). The
top-level six-tab row.

- `target=nccontent` — frame that each tab's page loads into.
- `type=tabs` — selects the tab-row render mode on `PageSelector`
  (vs. a button grid).
- `buttons=` (with `i18n` attribute) — the six top-level tabs:
  `identity~Identity~../identity/index.html`,
  `status~Status~../status/index.html~selected`,
  `configuration~Configuration~../configuration/index.html`,
  `security~Security~../security/index.html`,
  `diagnostics~Diagnostics~../diagnostics/index.html`,
  `support~Support~../support/index.html`.

## /security/menu.html

Applet: `PageSelector.class` (`archive=agent.jar`,
`codebase=../classes`, `name=Buttons`, `width=100%`, `height=22`).

- `target=nc_view` — content frame.
- `columns=5` — five buttons per row.
- `buttons=` (with `i18n`) — five security sub-tabs:
  `passwords~Device Passwords~../security/web_accessf.html~selected`,
  `authaddr~Authorized Addresses~../security/web_mgrf.html`,
  `perports~Port Security~../security/perportsf.html`,
  `intrusion~Intrusion Log~../security/intrusionf.html`,
  `ssl~SSL~../security/ssl_menuf.html`.

## /status/menu.html

Applet: `PageSelector.class` (`archive=agent.jar`,
`codebase=../classes`, `name=Buttons`, `width=100%`, `height=22`).

- `target=nc_view` — content frame.
- `buttons=` — three status sub-tabs:
  `overview~Overview~../status/overviewf.html~selected`,
  `portc~Port Counters~../status/portcf.html`,
  `portstatus~Port Status~../status/portStatusf.html`.

## /status/overview.html

Applet: `GenericList.class` (`archive=agent.jar`, `name=list`,
`codebase=../classes`, `width=100%`, `height=100%`). The Fault-Detect /
alert-log grid.

- `dataURL=../cgi/fflog?action=list` — row-data endpoint.
- `formURL=../status/overview2.html` — row-click target.
- `target=fft` — frame for the form page.
- `titles=Status~Alert~Date / Time~Description` — four columns.
- `columns=62:i~210:m~400:t~600:w` — pixel positions; `:i`=icon,
  `:m`=mono/label, `:t`=timestamp, `:w`=wide/wraps.
- `params=.~.~dt~.` — the third column is rendered with the `dt`
  date/time formatter.
- `images=11~10~2~3~4` — icon indices used by the status column.
- `delay=15` — auto-refresh poll interval (seconds).
- `sortColumn=2` — initial sort is by Date/Time.
- `sortAscending=no` — newest first.
- `incremental=yes` — poll fetches append-only deltas.

## /status/portc1.html

Applet: `GenericList.class` (`archive=agent.jar`, `name=list`,
`codebase=../classes`, `width=100%`, `height=100%`). The Port Counters
grid.

- `onlyOneSelection=1` — single-row select (port-detail dialog can
  only take one port).
- `dataURL=../cgi/portc` — row-data endpoint (per-port counters).
- `formURL=../status/portdf.html` — per-port detail form.
- `target=nc_view` — content frame.
- `titles=Port~Port Name~MCast%Rx~MCast%Tx~BCast%Rx~BCast%Tx~Pkts%Rx~Pkts%Tx~Errors%Rx`
  — nine columns.
- `columns=65~155:x~230~305~380~455~530~605~999` — pixel x-positions.
- `params=.~.~.~.~.~.~.~.~.` — all columns plain text.
- `delay=10` — 10-second auto-refresh.

## /status/portgraph.html

Applet: `PortGraph.class` (`archive=agent.jar`, `name=PortGraph`,
`codebase=../classes`, `width=95%`, `height=95%`). Note: uppercase
`<Param>` tags in this file.

- `URL=../cgi/port_usage` — data endpoint for the port-usage chart
  (overrides the `PortGraph.java:127` default).
- `securityURL=../securitymsg.html` — page loaded when the chart hits a
  credential/permission error.
- `pollRate=10000` — poll interval in milliseconds (10 s).

## /status/portStatus1.html

Applet: `GenericList.class` (`archive=agent.jar`, `name=list`,
`codebase=../classes`, `width=100%`, `height=100%`). The Port Status
grid.

- `dataURL=../cgi/get_ports` — row-data endpoint.
- `target=nc_view` — content frame (no per-row form is provided).
- `titles=Port~Port Name~Port Type~Enabled~Link%Status~Current%Mode~?Trnk~Flow Ctrl`
  — eight columns (`?Trnk` is optional/toggleable).
- `columns=65~155:x~230~305~380~455~464:h~555` — pixel positions
  (`:x` extensible, `:h` hidden by default).
- `params=.~.~.~.~.~.~.~.` — all plain text.
