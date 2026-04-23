# URL literals & operation tokens extracted from agent.jar

Generated 2026-04-23 from `research/decompiled/*.java`; raw hits in
`url-literals.txt`.

The raw `grep -oE` in Task 0.8 Step 1 produces some noise from unrelated
ternary expressions that happened to contain a `?`, e.g. lines like
`" + (drawable.isConnected() ? "` or `") ? new Label("`. Those are
preserved in the raw `.txt` but intentionally excluded here — only
strings that actually participate in URL construction are categorised.

## HTML pages (frame navigation)

These appear in `new URL(...)`/`showDocument(...)` constructions that
retarget a browser frame; they are not protocol endpoints.

- `"../orig_index.html"` — fallback redirect when a stack member has no
  per-member page.
  - Origin: `StackControl.java:267`
- `"../" + <swName> + "/orig_index.html"` — the concatenated variant,
  used when the closeup landed on a specific switch sub-mirror.
  - Origin: `StackControl.java:270`
- `"../stacking/smgmt.html"` — the stacking management landing page.
  - Origin: `StackControl.java:287`
- `"../stacking/scloseup.html"` — the per-member closeup page the
  StackControl opens on double-click / row-activate.
  - Origin: `StackControl.java:299`
- `"../configuration/espModuleError.html"` — shown when
  `get_espData?SLOT_ID=` returns too short a response; the applet bounces
  the frame to this error page.
  - Origin: `GenericBob.java:390`

## /cgi endpoints (protocol commands) — the actual operation URLs

Grouped by feature area. For each endpoint we list the literal path, the
Java class that builds it, and the query-string parameter names the
applet is known to send. All operations are HTTP GET (see Task 0.7
findings); mutations encode their arguments into the query string.

### Port / device view (Bob family — the front-panel renderer)

- `"../cgi/get_bobports"` — fetch per-port status for the front-panel
  drawing (link up/down, speed, admin state, etc.). Default when the
  applet's `getURL` param is unset.
  - Built in: `SwitchBob.java:72` (populates `m_getURLname`; used at
    `SwitchBob.java:80` as `new URL(getCodeBase(), m_getURLname)`).
  - Also the default in `InfinityBob.java:49` and `XFishBob.java:56`,
    but with an absolute `/cgi/get_bobports` root (no `../`).
  - Params sent: none at GET time; the URL is the bare endpoint.
- `"../cgi/set_bobports"` — set port admin state from the front-panel
  checkbox group.
  - Built in: `SwitchBob.java:76` (`m_setURLname`), consumed at
    `SwitchBob.java:303` as `new URL(getCodeBase(), m_setURLname + m_query)`.
  - Also `InfinityBob.java:53` and `XFishBob.java:60` (absolute root).
  - Params sent: `ifAdminStatus` (`1`=enable / `2`=disable),
    `indeces` (comma-separated port numbers — note the misspelling).
- `"../cgi/port_usage"` — default `URL` for the port-usage graph panel
  when the `URL` applet param is unset.
  - Built in: `PortGraph.java:129`; consumed at `PortGraph.java:832`.
  - Params sent: `LAST_PORT`, `NUM_PORTS`.

### Stacking — member & candidate management (Commander view)

- `"../cgi/get_memsinfo"` — list configured stack members (initial load
  for the Stack Management tab).
  - Built in: `StackControl.java:67`.
  - Params sent: none.
- `"../cgi/get_stack_cfg"` — fetch the stack-wide config record
  (commander IP, stack name, auto-grab/auto-join, etc.).
  - Built in: `StackConfig.java:128`.
  - Params sent: none.
- `"../cgi/set_stack_cfg"` — apply the stack-wide config form.
  - Built in: `StackConfig.java:527` (`new URL(getCodeBase(), "../cgi/set_stack_cfg" + string)` where `string` is the encoded form state).
  - Params sent: variable — the whole form submitted as a query string.
- `"../cgi/get_members"` — fetch the current member list for the
  MemberCandidateList panel (left column).
  - Built in: `MemberCandidateList.java:476` and `StackControl.java:318`.
  - Params sent: none.
- `"../cgi/get_candidates"` — fetch discovered (unjoined) candidate
  switches (right column of the add/remove dialog).
  - Built in: `MemberCandidateList.java:484`.
  - Params sent: none.
- `"../cgi/get_view_all"` — fetch the combined members+candidates view.
  - Built in: `MemberCandidateList.java:491`.
  - Params sent: none.
- `"../cgi/set_members"` — add selected candidates to the stack. The
  path is postfixed with an already-encoded query string built earlier.
  - Built in: `MemberCandidateList.java:762` (trace) / `:763` (URL).
  - Params sent: `nums` (comma-separated candidate indices) and
    `addrs` (comma-separated IP addresses), assembled at
    `MemberCandidateList.java:727` and `:733`.
- `"../cgi/delete_members"` — remove selected members from the stack.
  - Built in: `MemberCandidateList.java:337` and `:845`.
  - Params sent: `nums` (comma-separated member indices), see
    `MemberCandidateList.java:335` and `:842`.
- `"../cgi/get_cmd_name"` — fetch the commander's own identifying
  string. Used for the "You are: X" label.
  - Built in: `MemberCandidateList.java:244` and `StackControl.java:326`.
  - Params sent: none.
- `"../cgi/get_applet_length"` — small handshake used to measure the
  stack-applet payload size before doing full polls; also reused to
  probe per-member switch webpages at
  `"../sw" + N + "/cgi/get_applet_length"` (see `StackControl.java:114`).
  - Built in: `StackControl.java:107`.
  - Params sent: none.

### Device features / hardware info

- `"../cgi/get_espData?SLOT_ID="` — fetch ESP (extended switch product)
  module data for a given slot. Concatenated with the slot ID integer.
  - Built in: `GenericBob.java:371`.
  - Params sent: `SLOT_ID`.

### VLAN — the Configuration > VLAN Configuration tab

These are the applet's VLAN protocol commands. They are written as
bare command names; the applet joins them to `getBaseCgiUrl()` (which
itself comes from the `basecgiurl` applet param — see Task 0.9) when
the applet is running against the real switch. When `VLANmain.local`
is true (development mode), the raw command is used instead.

- `"getVLANAll"` — list all configured VLANs (table populate).
  - Built in: `VLANTable.java:181` (uses `"../cgi/getVLANAll"` against
    real switch, bare `"getVLANAll"` in local mode).
  - Params sent: none.
- `"addVLAN"` — create a new VLAN.
  - Built in: `VLANAddRemovePanel.java:287`.
  - Params sent: `VLAN_ID`, `VLAN_NAME` (URL-encoded).
- `"delVLAN"` — delete one or more VLANs.
  - Built in: `VLANAddRemovePanel.java:309`, args appended at `:314`.
  - Params sent: repeating `VLAN_ID` keys, `&`-separated.
- `"renVLAN"` — rename a VLAN.
  - Built in: `VLANAddRemovePanel.java:333`, args appended at `:338-339`.
  - Params sent: `VLAN_ID`, `VLAN_NAME` (URL-encoded).
- `"setPrimary?VLAN_ID="` — set the primary VLAN.
  - Built in: `VLANAddRemovePanel.java:421`.
  - Params sent: `VLAN_ID`.
- `"getVLANPort?VLAN_ID="` — load the per-port membership view for one
  VLAN (opens the Modify dialog).
  - Built in: `VLANmodifyPanel.java:190`; logged at `:191` as
    `/cgi/getVLANPort?VLAN_ID=`.
  - Params sent: `VLAN_ID`.
- `"setVLANPort?VLAN_ID="` — apply port-membership edits for one VLAN.
  - Built in: `VLANmodifyPanel.java:127`.
  - Params sent: `VLAN_ID`, plus the port-state body assembled by the
    panel's `string` variable.
- `"getVLANProtocol?VLAN_ID="` — load the protocol-filter settings for
  one VLAN (opens the Protocol dialog).
  - Built in: `VLANprotocolPanel.java:95`; logged at `:96-97` as
    `/cgi/getVLANProtocol?VLAN_ID=`.
  - Params sent: `VLAN_ID`.
- `"setVLANMode?MODE="` — global VLAN-mode toggle (the top-level
  enable/disable radio on the first panel).
  - Built in: `VLANfirstPanel.java:188`.
  - Params sent: `MODE` (integer code from the radio group).
- `"setGVRPMode?MODE="` — enable/disable GVRP globally.
  - Built in: `VLANfirstPanel.java:190`.
  - Params sent: `MODE`.
- `"setGVRPPort?"` — set GVRP per-port settings.
  - Built in: `VLANgvrpPanel.java:119` (the preceding
    `string` is the assembled port-state body).
  - Params sent: per-port tokens built in `VLANgvrpPanel`.

## Operation tokens (`key=` patterns appearing in URL construction)

Collected for reuse when writing Python request models in later tasks.

- `VLAN_ID=` — VLAN feature area (add/del/ren/modify/protocol/setPrimary).
  Duplicate-keyed for multi-select in `delVLAN`.
  - `VLANAddRemovePanel.java:287, 314, 338, 421`,
    `VLANmodifyPanel.java:127, 190`, `VLANprotocolPanel.java:95`.
- `VLAN_NAME=` — VLAN create/rename.
  - `VLANAddRemovePanel.java:287, 338` (URL-encoded).
- `MODE=` — `setVLANMode`, `setGVRPMode`.
  - `VLANfirstPanel.java:188, 190`.
- `ifAdminStatus=` — port up/down (`1` / `2`).
  - `InfinityBob.java:202`, `SwitchBob.java:282`, `XFishBob.java:290`.
- `indeces=` — comma-separated port indices (misspelled in-wire).
  - `InfinityBob.java:202`, `ListPane.java:562, 625`,
    `SwitchBob.java:282`, `XFishBob.java:290`.
- `nums=` — stack member/candidate indices (`set_members` /
  `delete_members`).
  - `MemberCandidateList.java:335, 733, 842`.
- `addrs=` — candidate IPs (`set_members`).
  - `MemberCandidateList.java:727`.
- `SLOT_ID=` — ESP module slot number.
  - `GenericBob.java:371`.
- `LAST_PORT=` / `NUM_PORTS=` — port-usage graph pagination.
  - `PortGraph.java:832`.

## Applet-param → URL keys

- `basecgiurl` — read at `VLANmain.java:28, 41`; used to prefix VLAN
  command names into a full URL. This is the hook HTML pages use to
  retarget the VLAN applet at a different CGI root.
- `getURL` — read at `SwitchBob.java:70`, `InfinityBob.java:47`,
  `XFishBob.java:54`; overrides `get_bobports`.
- `URL` (port-usage graph) — read at `PortGraph.java:127`; overrides
  `port_usage`.

## Suspicious / unknown

- Hard-coded dev IPs `http://192.32.36.78/cgi/get_bobports` and
  `http://192.32.36.78/cgi/get_bobports2` — HP-internal testing
  leftover per Task 0.7. Appear as dead branches in
  `SwitchBob.java:109` / `:118`. Ignored for protocol docs.
- `Call CGI :: /cgi/getVLANPort?VLAN_ID=` and
  `Call CGI :: /cgi/getVLANProtocol?VLAN_ID=` are log-line prefixes
  from `VLANmodifyPanel.java:191` and `VLANprotocolPanel.java:96, 97`;
  the grep picked them up as a single literal because of the embedded
  `/cgi/...`. They are not separate URLs.
- Bare `"?"`, `"?ifAdminStatus="`, `"?LAST_PORT="`, `"?nums="`,
  `"?addrs="`, `"VLAN_ID="`, `"indeces="` — fragments, not endpoints.
  Each is documented in the operation-tokens section above.
