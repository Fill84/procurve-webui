# Protocol documentation conventions

Every file under `research/protocol/<tab>/<operation>.md` follows the same
template so Phase 1 can translate each doc into Python mechanically.

## Universal conventions (discovered in Phase 0 Tasks 0.7 + 0.8)

### HTTP method
- **Applet operations are all GET.** Even mutations (e.g. `addVLAN`) encode
  arguments into the query string. There is no POST anywhere in the
  decompiled applet.
- **Exceptions (POST endpoints, not applet URLs):**
  - `/cgi/configfile` — config download (GET) only; uses query-string form,
    see `backup/download_config.md`.
  - `/cgi/upload` — config upload / restore. Plain HTML form POSTing
    `multipart/form-data`. See `backup/upload_config.md`.
  Both live outside the applet's GET-only world.

### URL construction
- Applet classes build URLs in two patterns:
  - Pattern A: `getCodeBase()` + `../cgi/<cmd>` (stack family, status family, bob classes).
  - Pattern B: applet `<param name=basecgiurl>` value + `<cmd>` (VLAN family).
- In Python, we always use an absolute URL constructed from the switch host
  + the CGI path; the applet's relative-path logic is irrelevant. All CGIs
  live under `/cgi/` on the switch.

### Response format
- Content is plain text (no specific `Content-Type`; `text/plain` or absent).
- Lines are separated by `\r\n` or `\n` (be tolerant on read, do not
  normalize before hashing fixtures).
- Fields within a line are **tilde-delimited** (`~`).
- First line of a response typically opens with a sentinel:
  - `OK~<rest>` — success; remainder of response depends on operation.
  - `error~<message>` — failure; message is human-readable English.
- Some operations return multi-line bodies with multiple records; each
  record is its own tilde-delimited line.
- Binary downloads (e.g. `download_config`) are the exception: no sentinel,
  response body is raw ASCII config text.

### Authentication
- The applet itself emits no `Authorization` header. The Java Plug-in
  reuses the browser's Basic-auth session if one is active.
- In Python, the `ProcurveTransport` sends `Authorization: Basic ...` when
  a `BasicAuth` strategy is configured; otherwise no auth header is sent.
- **Currently the switch has blank user/password** — any request works
  without credentials. The code must still support Basic auth for when
  the user sets a manager password.

### Query-string quirks
- **Duplicate keys for multi-select** — some CGIs accept repeated keys,
  e.g. `delVlan?VLAN_ID=5&VLAN_ID=6&VLAN_ID=7`. `httpx` supports this via
  list-valued params: `params={"VLAN_ID": [5, 6, 7]}`.
- **Preserve the misspelling `indeces` (sic)** — used by port-config
  CGIs. Naming our Python param with the correct English would break the
  wire protocol; we mirror the switch verbatim at the HTTP layer and may
  use a prettier name only at the Pydantic field level if we map it.
- **Space-vs-plus encoding** — the applet uses `URLEncoder.encode`, which
  emits `+` for spaces. Python's `httpx`/`urllib.parse.urlencode` does the
  same by default, so no special handling is required unless a byte-match
  test fails.
- **Asterisk divergence (accepted, audit F6)** — Java's `URLEncoder` and
  browser form submits leave `*` literal; `httpx`/`quote_plus` emit `%2A`
  (verified empirically on httpx 0.28.1). Affects free-text fields only
  (`sysName`, `sysLocation`, `sysContact`, `_SuppURL`,
  `hpHttpMgMgmtSrvrURL`, `_portName`). Any RFC-conformant decoder treats
  the two identically, so this is tolerated rather than special-cased;
  revisit only if a live byte-match test fails on a value containing `*`.
- **Comma in `indeces` — two different conventions!**
  `set_bobports` (SwitchBob.java:282-293) appends the CSV comma **raw**;
  the ListPane multi-item submit path (`port_form`/`mod_ports`,
  ListPane.java:572) sends it **encoded** (`URLEncoder.encode(",")` →
  `%2C`). Mirror the specific caller, not a blanket rule (audit F4).

## File template

Every operation doc follows this structure exactly:

    # <operation_name>

    **Tab:** <identity | status | configuration | security | diagnostics | support | backup>
    **Kind:** read | write
    **Source in applet:** <Class>.java:<line-range> (one or more; or "none — HTML only" if purely form-based)
    **Source in HTML:** <mirror path> if applicable

    ## HTTP contract

    - **Method:** GET | POST
    - **URL template:** `<literal URL with {placeholders}>`
    - **Query params:** <table of name, type, required?, description>
    - **Request headers:** <table or "none">
    - **Request body:** <format + fields, or "none">
    - **Response headers (relevant):** <table or "none">
    - **Response body:** <shape description + sample>
    - **Success indicator:** <sentinel pattern or HTTP status>
    - **Error indicators:** <list>

    ## Field reference

    <table of every field on request and response: wire key, wire type, Python type, validation rule, notes>

    ## Example request

    <raw HTTP request with placeholder values>

    ## Example response

    See `research/fixtures/<tab>__<operation>.response.txt` (live-captured for reads).
    For writes: prepared example only; do not live-test.

    ## Pydantic sketch

    ```python
    class <Operation>Request(BaseModel):
        ...
    class <Operation>Response(BaseModel):
        ...
    ```

    ## Notes & caveats

    - Edge cases, validation rules from Java code, related operations, quirks.

## Naming conventions

- File names are snake_case describing the user-visible operation:
  `get_port_status.md`, `set_port_name.md`, `create_vlan.md`.
- Write operations use a verb prefix: `set_`, `create_`, `delete_`,
  `apply_`, `reset_`, `upload_`, `download_`.
- Read operations use a verb prefix too when it clarifies intent
  (`get_`, `list_`, `download_`); bare-noun filenames are reserved for
  compound reports where no verb fits naturally.
- Group by tab directory. Operations used by multiple tabs go under
  `_shared/`.
- Fixture files live under `research/fixtures/` and use the operation
  name directly: `download_config.response.txt`,
  `get_port_status.response.txt`. No tab prefix is needed because
  operation names are globally unique.

## Byte-exact fidelity for writes

For write operations, the protocol doc's "Example request" is
authoritative for the Python byte-match test. If a write request in the
decompiled Java sends duplicate keys, spaces, or misspellings, the doc
MUST preserve them exactly. The Python client must produce byte-identical
requests or the switch may reject or silently misinterpret them.

## Fixture capture rules (reads only)

- Capture with `curl -s -m 15` to keep the response raw (no progress
  bars, 15-second timeout).
- Record the byte-count and SHA256 in the doc's "Example response"
  section so later runs can assert the switch hasn't drifted.
- Never normalize line endings, strip whitespace, or edit the captured
  file; Phase 1 tests compare against it byte-for-byte.
- Re-capture dates live in the fixture directory name only when the
  fixture is ambiguous; `research/fixtures/` itself is timeless and
  overwritten on each re-capture.
