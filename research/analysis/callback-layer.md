# Applet callback / HTTP layer

## Executive summary — what these three classes actually are

The task brief described `Callback` / `CallbackClient` / `ResultProcessor`
as "the protocol layer: request dispatch and response handling". After
reading the decompiled source this turns out to be **incorrect**. The
three files are tiny:

- `CallbackClient.java` — 96 B, a single-method interface
  (`public void callback();` — CallbackClient.java:4-6).
- `Callback.java` — 302 B, a `Thread` subclass whose `run()` calls
  `m_client.callback()` once (Callback.java:13-15).
- `ResultProcessor.java` — 216 B, an interface with two
  `processResult(StackDialog, ...)` methods (ResultProcessor.java:6-10).

**There is no shared HTTP helper class in the applet.** Every feature
applet opens its own `URLConnection`, reads its own `InputStream`, and
parses its own tilde-delimited response. Below, each section first
explains what's in the three "callback" files, then captures the actual
HTTP conventions that are repeated (copy-pasted, really) across the
feature classes.

See `research/analysis/url-sites.txt` for the raw list of every URL
construction site (99 lines across 18 feature classes).

---

## What the three files actually do

### `CallbackClient` (interface)

```java
public interface CallbackClient {
    public void callback();
}
```
(CallbackClient.java:4-6)

Implemented by five classes: `DeviceStatus`, `GenericList`, `InfinityBob`,
`SwitchBob`, `XFishBob`. Each implementation does a URL fetch + state
refresh; the interface itself knows nothing about HTTP.

### `Callback` (Thread)

```java
public class Callback extends Thread implements Runnable {
    private CallbackClient m_client = null;
    public Callback(CallbackClient c) { this.m_client = c; }
    public void run() { this.m_client.callback(); }
}
```
(Callback.java:4-16)

Used five times in the codebase (`new Callback(this); c.start();`):
- `DeviceStatus.java:150` — schedule a refresh of status icon.
- `GenericList.java:188` — schedule a list reload.
- `InfinityBob.java:217` — fire port enable/disable after user toggle.
- `SwitchBob.java:297` — same pattern for the non-Infinity chassis.
- `XFishBob.java:317` — same pattern for XFish.

In every case the "callback" is a synchronous `URLConnection` call that
would otherwise block the AWT event dispatch thread. `Callback` exists
purely to push the blocking I/O off the EDT onto a new thread. It is
a concurrency primitive, not a protocol primitive.

### `ResultProcessor` (interface)

```java
interface ResultProcessor {
    public void processResult(StackDialog var1, Object var2);
    public void processResult(StackDialog var1, AWTEvent var2);
}
```
(ResultProcessor.java:6-10)

Implemented by `StackConfig`, `StackControl`, `MemberCandidateList`.
It is invoked by `StackDialog` (a modal OK/Cancel/Password dialog) when
the user clicks OK / Cancel / closes the window — StackDialog.java:164,
166, 172. The second argument is either a sentinel `String` ("Ok",
"Cancel") or an `AWTEvent` for the window-close case. Pure UI
dispatch — no HTTP involvement.

---

## Base URL construction (across all feature classes)

Two applet idioms are used; they are functionally similar but not
interchangeable:

- **`getDocumentBase()` + `baseCgiUrl` applet param** — the VLAN family.
  `VLANmain.init()` reads the applet parameter `basecgiurl` and stores it
  (VLANmain.java:41). The shared helper `callURL(String query)` then
  constructs `new URL(this.getDocumentBase(), this.baseCgiUrl + query)`
  (VLANmain.java:174). The same pattern is repeated inline in
  `VLANAddRemovePanel` (VLANAddRemovePanel.java:295, 321, 347, 359) via
  `this.m_applet.getBaseCgiUrl()`.
- **`getCodeBase()` + relative `../cgi/<cmd>` path** — stack / member /
  status / bob / portgraph families. Examples:
  - `StackConfig.java:128`: `new URL(this.getCodeBase(), "../cgi/get_stack_cfg")`
  - `StackConfig.java:527`: `new URL(this.getCodeBase(), "../cgi/set_stack_cfg" + string)`
  - `MemberCandidateList.java:244`: `new URL(this.getCodeBase(), "../cgi/get_cmd_name")`
  - `MemberCandidateList.java:476-491`: `get_members`, `get_candidates`, `get_view_all`
  - `MemberCandidateList.java:337, 763`: `delete_members`, `set_members`
  - `PortGraph.java:832`: `new URL(this.getCodeBase(), this.m_urlStr + "?LAST_PORT=...")`
  - `DeviceStatus.java:159`: `new URL(this.getCodeBase(), this.m_urlName)`
  - `InfinityBob.java:56, 224`: `new URL(this.getDocumentBase(), this.m_getURLname)` and `...+ this.m_query`
  - `SwitchBob.java:80, 303`: `new URL(this.getCodeBase(), this.m_getURLname)`
  - `PageButton.java:43`: absolute-or-relative — `string3.startsWith("http:") ? new URL(string3) : new URL(this.m_parent.getCodeBase(), string3)`

The `<applet>` tag in each HTML page supplies `getURL` / `setURL` / `basecgiurl`
parameters (see `InfinityBob.java:47-54`, `SwitchBob.java:70-77`,
`StackConfig.java:116-117`) with sensible defaults like
`../cgi/get_bobports` and `../cgi/set_bobports`.

**No global session token or language parameter is ever injected.** The
applet relies entirely on the browser's own session state for any
authorization (see "Session / auth" below).

## Request shape

### GET vs POST split

**Everything is GET.** No `setRequestMethod("POST")`, no `setDoOutput(true)`,
no `getOutputStream()` anywhere in the decompiled source:

```
$ grep 'setRequestMethod\|setRequestProperty\|getOutputStream\|
      setDoOutput\|Content-Type\|POST' research/decompiled/*.java
(no matches)
```

Every mutating operation encodes its arguments into the query string and
issues a plain `URLConnection.getInputStream()`:

- `VLANAddRemovePanel.addVlan()` constructs
  `"addVLAN?VLAN_ID=" + ... + "&VLAN_NAME=" + URLEncoder.encode(name)`
  (VLANAddRemovePanel.java:287-288).
- `VLANAddRemovePanel.delVlan()` —
  `"delVLAN?VLAN_ID=" + id + "&VLAN_ID=" + id + ...` (VLANAddRemovePanel.java:309-319).
- `VLANAddRemovePanel.renameVlan()` — `"renVLAN?VLAN_ID=...&VLAN_NAME=..."`
  (VLANAddRemovePanel.java:333-339).
- `StackConfig` `apply_changes` button — builds `"../cgi/set_stack_cfg" + queryString`
  where `queryString` is a `&`-joined series of `key=value` pairs
  (StackConfig.java:527, 530).
- `InfinityBob.setEnableForSelectedPorts(boolean)` builds
  `"?ifAdminStatus=1&indeces=1,2,3,..."` (InfinityBob.java:202-213) and
  fires it via `Callback` thread → `callback()` → `new URL(..., m_setURLname + m_query)`
  (InfinityBob.java:222-233).
- `DeviceStatus.refresh()` — `"&tslch=" + URLEncoder.encode(...) + "&lindex=" + ...`
  (DeviceStatus.java:158).

### Headers

No headers are set explicitly. Every `URLConnection` is configured with
only the three standard knobs:
```java
uRLConnection.setDoInput(true);
uRLConnection.setAllowUserInteraction(false);
uRLConnection.setUseCaches(false);
```
(pattern repeated at VLANmain.java:183-185, VLANAddRemovePanel.java:247-249,
StackConfig.java:137-139, 539-541, InfinityBob.java:77-79, SwitchBob.java:130-132,
DeviceStatus.java:161-163, StackControl.java:78-80, PortGraph.java:834-836,
MemberCandidateList.java:253-255 and others.)

- **User-Agent**: Not set. Whatever the Java Plug-in defaults to.
- **Content-Type**: Not set (no request body).
- **Cookie**: Not set. Not used. Not used. (see Session / auth.)
- **Authorization**: Not set. (see Session / auth.)

### Request body

Not used. Every call is a zero-body GET. See VLANAddRemovePanel.java:175-187
(`callURLwithUpdate`) and VLANmain.java:169-188 (`callURL`) for the canonical
shape: open connection → set three input flags → `getInputStream()`.

## Response shape

### Content-Type expected

The code never inspects `Content-Type`. It unconditionally wraps the
response stream as

```java
new BufferedReader(new InputStreamReader(uRLConnection.getInputStream()))
```
(VLANmain.java:186, VLANAddRemovePanel.java:185, 250, StackConfig.java:140, 542,
InfinityBob.java:80, DeviceStatus.java:164, PortGraph.java:837,
MemberCandidateList.java:256, 349, 523, 774, 856, StackControl.java:81, 126, 337,
355, SwitchBob.java:133, XFishBob.java:88, ListPane.java:478).

In practice the CGI responses are plain text (one record per line, fields
separated by `~`). The browser's `Content-Type` header is ignored.

### Parsing strategy

**Line-based, tilde-delimited, using `StringTokenizer`.** The pattern is
uniform across feature classes:

```java
while ((line = reader.readLine()) != null) {
    line.trim();
    if (line.length() == 0) line = reader.readLine();
    StringTokenizer st = new StringTokenizer(line, "~");
    ...
}
```
(see VLANAddRemovePanel.java:186-205 for the canonical example, also
DeviceStatus.java:177-181, InfinityBob.java:114-145, PortGraph parsing,
StackConfig.java:142-150, MemberCandidateList:523+.)

Some responses use a secondary `|` delimiter for multi-line error
messages inside a single tilde field (VLANAddRemovePanel.java:207-212):

```java
StringTokenizer stringTokenizer2 = new StringTokenizer(string4, "|");
while (stringTokenizer2.hasMoreTokens()) {
    string5 = string5 + stringTokenizer2.nextToken() + "\n";
}
```

### Sentinel strings

Convention: the **first tilde field** on a line is a status sentinel.

- `"OK"` — success. Subsequent tokens are the payload. Example:
  VLANAddRemovePanel.java:197 — `if (string4.equalsIgnoreCase("OK")) { ... addItem(id, name, 0) }`.
- `"error"` (lowercase) — failure. The next token is the human-readable message.
  Example: StackConfig.java:546-549 —
  `if (string3.equals("error")) { String msg = st.nextToken(); new StackDialog("ERROR: " + msg, ...); }`.

If the first token is neither `"OK"` nor `"error"`, the data is treated
as already-payload (e.g. `listVLANS` returns bare `id~name~id~name...` rows
without a leading status — see `callURLlist` at VLANAddRemovePanel.java:240-280).

## Exceptions / error handling

Three categories, handled uniformly:

- `MalformedURLException` — caught at the URL construction site. Response
  is always `System.err.println(this.getClass().getName() + malformedURLException);`
  and the method returns without reaching the network call. Examples:
  VLANmain.java:177-179, VLANAddRemovePanel.java:299-301 (addVlan),
  325-327 (delVlan), 351-353 (renVlan), 363-365 (getDataForList),
  StackConfig.java:130-132, 533-535.
- `IOException` — caught around the read loop. Same pattern:
  `System.err.println(this.getClass().getName() + iOException);` and
  silently return. Examples: VLANAddRemovePanel.java:235-237, 277-279,
  StackConfig.java:161-163, 554-556, DeviceStatus.java:172-175,
  MemberCandidateList.java multiple places.
- Generic `Exception` — used in the Bob classes as a catch-all.
  `InfinityBob.java:94-98` catches `Exception` during port-state parse,
  logs it, and preserves the previous `m_ps` string to avoid a half-updated
  display. `InfinityBob.java:230-232` wraps the `callback()` URL call
  in a catch-`Exception` that only logs.

**How errors surface to the user:**

- **Server-reported errors (response starts with `error~...`):** a modal
  dialog is shown. `StackConfig` uses `StackDialog` (StackConfig.java:549);
  the VLAN subsystem uses `VLANDialog` (VLANAddRemovePanel.java:213-214,
  290). No retry — the dialog just closes.
- **Network errors (MalformedURL / IO):** silent. The only user-visible
  effect is the UI failing to update. These errors go to `System.err`
  (i.e. the Java Plug-in console), never to the web page.
- **User input validation errors (before the HTTP call):** caught locally
  and shown via `VLANDialog` or `ErrorDialog`. E.g.
  VLANAddRemovePanel.java:290 — illegal `~` character in VLAN name.

## Session / auth

**The applet does no authentication of its own.** No `Authorization`
header is ever set, no cookie is ever read or written, no login form
is ever submitted. Confirmed by:

```
$ grep 'Authorization\|Cookie\|setRequestProperty' research/decompiled/*.java
(no matches)
```

Auth is the browser's responsibility. The switch's embedded web server
sits in front of every `../cgi/*` endpoint; when the applet calls
`URLConnection.openConnection()`, the Java Plug-in piggybacks on the
browser's HTTP session (including any `Authorization: Basic ...` cookie
jar / credentials already negotiated for the applet's origin). If the
user is not authenticated, the GET will 401 or redirect, the
`BufferedReader` will fail, and the applet will silently drop the
request (see "Exceptions" above — no special handling).

This matches the 2006-era convention of HTTP Basic auth on the
switch's web port with the browser caching credentials for the
duration of the window.

## Notes / quirks

1. **The task brief framed the three classes as an HTTP layer; they
   are not.** They are a tiny thread-off-the-EDT helper plus a modal-dialog
   callback interface. The real HTTP convention (tilde-delimited GETs with
   `OK~` / `error~` sentinel) is duplicated inline in roughly 15 feature
   classes and is captured above.
2. **Hard-coded debug IP in SwitchBob.** SwitchBob.java:109, 118 fall
   back to `http://192.32.36.78/cgi/get_bobports[2]` when `m_psURL` is
   null and `linux_flag` is set. This looks like an HP internal dev
   fixture that shipped in the release. Worth noting if we ever run
   the applet in a sandbox — it'll try to contact that address.
3. **`StackConfig` has two URL modes** (StackConfig.java:128, 530):
   a `linuxFlag` branch using `getCodeBase() + "../cgi/get_stack_cfg"`,
   and a non-Linux branch using `this.getUrlStr` / `this.setUrlStr` verbatim
   (which, per init at lines 116-117, come from `getURL` / `setURL`
   applet params and are treated as already-absolute URLs — they're
   `new URL(string)` rather than resolved against a base).
4. **`VLANAddRemovePanel.delVlan` sends duplicate `VLAN_ID=` params
   for multi-select** (VLANAddRemovePanel.java:314). So the server-side
   CGI must accept repeated keys.
5. **`InfinityBob` serializes port indices with a comma** rather than
   repeating the key (`indeces=1,2,3`) — InfinityBob.java:211. (Note
   the misspelling "indeces" is preserved in the wire format; whatever
   we write server-side must accept the misspelling.)
6. **No caching.** Every call sets `setUseCaches(false)` — presumably
   to work around the Java Plug-in's otherwise-aggressive URLConnection
   cache.
7. **Concurrency.** The only concurrency primitive is `Callback`:
   fire-and-forget thread. There is no request queue, no cancellation,
   no timeout. A slow CGI will leave a zombie Java thread blocked in
   `readLine()` until the OS closes the socket.
8. **Response stream is not closed in all paths.** `VLANAddRemovePanel.callURLwithUpdate`
   only closes the `BufferedReader` if it reached end-of-stream cleanly
   (VLANAddRemovePanel.java:223-225 inside the try, not in a `finally`). On
   `IOException` it leaks. Cosmetic concern for our analysis only.

## Citation index

- `CallbackClient.java:4-6` — single-method interface `public void callback();`
- `Callback.java:4-16` — `Thread` subclass whose `run()` invokes
  `m_client.callback()`; used to move CGI calls off the AWT event thread.
- `ResultProcessor.java:6-10` — two-method interface
  `processResult(StackDialog, Object|AWTEvent)`; dispatched from
  `StackDialog.java:164, 166, 172` on OK / Cancel / window-close.
- `VLANmain.java:41` — reads `basecgiurl` applet param.
- `VLANmain.java:165-188` — canonical `callURL` helper:
  `new URL(getDocumentBase(), baseCgiUrl + query)` → GET → `BufferedReader`.
- `VLANAddRemovePanel.java:175-238` — `callURLwithUpdate`: full
  request/response cycle with `OK~` / error-tokenization logic.
- `VLANAddRemovePanel.java:287-288` — mutation via query string
  (`addVLAN?VLAN_ID=...&VLAN_NAME=...`) with `URLEncoder.encode` for the name.
- `VLANAddRemovePanel.java:309-328` — `delVlan` repeats `VLAN_ID=` per selection.
- `StackConfig.java:116-117` — reads `getURL` / `setURL` applet params.
- `StackConfig.java:128, 527-530` — dual URL modes (linuxFlag vs. absolute
  param URL).
- `StackConfig.java:546-549` — canonical `error~<msg>` handling →
  `new StackDialog("ERROR: " + msg, ...)`.
- `InfinityBob.java:47-54` — reads `getURL` / `setURL` applet params with
  defaults `/cgi/get_bobports`, `/cgi/set_bobports`.
- `InfinityBob.java:200-233` — `setEnableForSelectedPorts` +
  `Callback(this).start()` + `callback()` — the canonical "fire an async
  mutation" pattern.
- `SwitchBob.java:109, 118` — hard-coded fallback to
  `http://192.32.36.78/cgi/get_bobports[2]`.
- `DeviceStatus.java:145-188` — polling status applet; uses `Callback`
  and parses `state~index~description~timestamp`.
- `MemberCandidateList.java:244, 337, 476-491, 763, 845` — every
  `../cgi/*_members` / `*_candidates` / `*_cmd_name` / `*_view_all` site.
- `PortGraph.java:832` — `?LAST_PORT=<n>&NUM_PORTS=<n>` query-string
  parameters.
- `PageButton.java:43` — URL resolution logic in the page-selector tabs.
- `url-sites.txt` — full line-by-line list of all 99 URL construction
  sites across the applet.
