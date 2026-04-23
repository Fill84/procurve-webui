# Class grouping — agent.jar (ProCurve 2810-24G)

Grouped by apparent responsibility after reading the decompiled source in
`research/decompiled/`. 50 `.java` files; CFR collapsed anonymous inner classes
into their enclosing source files. Original agent.jar had 80 `.class` entries.

Sizes below come from `research/analysis/class-sizes.txt`.

---

## A. Navigation / page framework

- `PageSelector` (5002 B) — tab/button bar applet hosted by `menu.html`
  and `nctabs.html`. Reads its tabs from applet `<param>` tags.
- `PageButton` (8732 B) — a single tab/button; constructs its target
  URL via `getCodeBase()` unless the param value already starts with
  `http:` (PageButton.java:43).

## B. Device rendering (visual switch chassis)

Visual / paint code. Not directly part of the protocol surface, but still
loads port-state data from CGIs through the InfinityBob / SwitchBob / XFishBob
base classes. We mine these for URL literals.

- `Drawable` (43333 B) — primitive port/LED drawable (largest file).
- `SwitchBob` (13371 B) — common base for 8k/16h Bobs. Has a hard-coded
  `http://192.32.36.78/cgi/get_bobports[2]` fallback (SwitchBob.java:109, 118).
- `GenericBob` (23110 B), `Sw16hBob` (2799 B), `Sw8kBob` (3909 B),
  `SwGammaBob` (4006 B), `SwMinnie_meBob` (4649 B), `SwToontownBob` (4655 B),
  `SwStrongbadBob` (5030 B) — per-model renderers. `SwStrongbadBob` is the
  likely renderer for the J9021A chassis (2810-24G).
- `TomcatBob` (2474 B) — another renderer variant.
- `InfinityBob` (10166 B) — Infinity chassis; implements `CallbackClient`
  and uses `Callback` threads to POST-via-GET port enable/disable (see
  `setEnableForSelectedPorts` + `callback()` at InfinityBob.java:200-233).
- `XFishBob` (17034 B) — similar pattern to InfinityBob; implements
  `CallbackClient` and uses `Callback` threads.
- `BleachImageFilter` (1085 B) — image filter used for dimming icons.
- `ColorCache` (2056 B) — color interning for AWT primitives.

## C. Port counters / graphs

- `PortGraph` (38341 B) — live port traffic gauge applet (hosted by
  `status/portgraph.html`). Polls `?LAST_PORT=...&NUM_PORTS=...` (PortGraph.java:832).
- `YScale` (2774 B) — graph Y-axis tick helper.

## D. VLAN subsystem

- `VLANmain` (7131 B) — applet entry point. Reads `basecgiurl` param and
  defines the `callURL(String query)` helper (VLANmain.java:165-188) that
  every VLAN subpanel shares.
- `VLANAddRemovePanel` (17732 B) — add / remove / rename operations
  (`addVLAN?`, `delVLAN?`, `renVLAN?`, `listVLANS`).
- `VLANDialog` (2970 B) — modal error dialog for VLAN subsystem.
- `VLANTable` (11027 B) — tabular display.
- `VLANLine` (8126 B), `VLANmultiLineLabel` (1195 B) — list row widgets.
- `VLANfirstPanel` (9275 B) — landing view.
- `VLANgvrpPanel` (6996 B) — GVRP mode panel.
- `VLANmodifyPanel` (9845 B) — port-membership modification.
- `VLANprotocolPanel` (4937 B) — protocol-VLAN editor (Alpha family only).

## E. Stacking subsystem

- `StackConfig` (23797 B) — applet reading `get_stack_cfg` / `set_stack_cfg`
  CGIs (StackConfig.java:128, 527).
- `StackControl` (16931 B) — companion applet for member/candidate control;
  mentions `../cgi/get_members`, `../cgi/get_cmd_name`,
  `../cgi/get_applet_length` (StackControl.java:107, 318, 326).
- `StackControlButton` (538 B) — button variant used in stack control UI.
- `StackDialog` (7262 B) — modal OK/Cancel dialog that dispatches results
  via the `ResultProcessor` interface (StackDialog.java:164-172).

## F. Core UI primitives

Generic AWT widgets shared by multiple subsystems. None of them open
connections directly except `ListPane` (a list widget that pages through
results via `getCodeBase() + formURL + ...`).

- `GenericList` (9182 B) — list container; also implements `CallbackClient`.
- `GenericTable` (9865 B) — tabular view primitive.
- `GenericRowEntry` (10441 B) — row model.
- `ListLine` (873 B), `ListPane` (42690 B), `ListTitle` (4193 B),
  `MultiList` (11504 B).
- `MemberCandidateList` (39484 B) — second largest file; the stack
  member/candidate picker. Talks to `../cgi/get_cmd_name`,
  `../cgi/get_members`, `../cgi/get_candidates`, `../cgi/get_view_all`,
  `../cgi/delete_members`, `../cgi/set_members` (see MemberCandidateList.java:243-500).
- `MonitorList` (1680 B) — small monitor-port list.

## G. Status / device state

- `DeviceStatus` (8564 B) — polling applet that shows overall switch
  status icon (`status/<n>d.gif`). Uses `Callback` thread to refresh
  (DeviceStatus.java:145-152).

## H. Threading / UI callback interfaces (NOT HTTP)

**Surprise finding:** despite the task brief framing these as "HTTP
callback machinery", the three classes are NOT an HTTP layer. They are
tiny threading / dialog-callback primitives.

- `Callback` (302 B) — `extends Thread implements Runnable`; its only
  job is to call `m_client.callback()` on a background thread
  (Callback.java:9-15).
- `CallbackClient` (96 B) — single-method interface
  `public void callback()` (CallbackClient.java:4-6). Implemented by
  `InfinityBob`, `SwitchBob`, `XFishBob`, `GenericList`, `DeviceStatus`.
- `ResultProcessor` (216 B) — interface with two `processResult(
  StackDialog, Object)` / `(StackDialog, AWTEvent)` methods
  (ResultProcessor.java:6-10). Implemented by `StackConfig`,
  `StackControl`, `MemberCandidateList`. It is the OK/Cancel dispatch
  for `StackDialog`.

All real HTTP I/O lives in the feature classes themselves (D, E, F.MemberCandidateList,
B.InfinityBob/XFishBob/SwitchBob, C.PortGraph, G.DeviceStatus, A.PageButton).

See `research/analysis/callback-layer.md` for full analysis.

## I. Utility / misc

- `Assert` (835 B) — debug-assert helper (probably `assertNotNull`-style).
- `Util` (2335 B) — string/number utilities.
- `ErrorDialog` (1841 B) — AWT error dialog (single string parameter).
- `ToolTipTimer` (723 B) — hover tooltip delay timer.
- `PasswdTextField` (656 B) — masked text field used by StackDialog
  (calls `ResultProcessor.processResult` on Enter — PasswdTextField.java:23).

---

## Missing / unexpected

- The initial brief listed `Callback` / `CallbackClient` / `ResultProcessor`
  as the "HTTP callback machinery — highest priority". After reading the
  source, they are **not** an HTTP layer. See note under group H above and
  the full write-up in `callback-layer.md`. The real URL-construction
  convention lives inside each feature applet (e.g. `VLANmain.callURL`,
  `StackConfig.get_stack_cfg_url`, `InfinityBob.updateStatus`) — there
  is no shared HTTP helper class.
- No other expected classes are missing; every class listed in the
  task brief appears in `research/decompiled/` and is accounted for above.
- No unexpected classes — every `.java` file in the decompiled output
  is placed in one of groups A-I.

---

## Next steps

1. (Done) Confirm group H — see `callback-layer.md`.
2. Analyze `PageSelector` / `PageButton` (group A) to extract the full
   list of applet pages and their parameter layouts.
3. Walk each feature group (D, E, F.MemberCandidateList, C) and extract
   every URL literal + query-string parameter.
4. Cross-reference extracted URLs with the HTML mirror
   (`research/mirror/2026-04-23/`) to confirm parameter layout.
