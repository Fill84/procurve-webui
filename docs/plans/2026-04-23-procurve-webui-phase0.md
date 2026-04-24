# procurve-webui — Phase 0 (Reverse Engineering) Implementation Plan

**Goal:** Reverse-engineer the HP ProCurve 2810-24G Java applet (`agent.jar`) well enough to implement a faithful Python protocol client for every user-facing operation. No code in Phase 0 — this phase produces documentation and test fixtures only.

**Architecture:** Download all static switch assets, decompile the applet JAR with CFR, cross-reference HTML `<applet>` parameter tags against decompiled Java to map every tab / operation to a concrete HTTP request/response contract. Capture live responses of every read operation as fixtures for later unit tests.

**Tech Stack:** curl (downloads), Python 3.12 (decompile orchestration + scripts), CFR 0.152 (Java decompiler), ripgrep (code scanning), git.

**Spec:** `docs/specs/2026-04-23-procurve-webui-design.md`

**Reference backup (do not modify):** `research/backups/2026-04-23/CONFIG.pcc`, SHA256 `f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11`.

---

## File Structure for Phase 0

Phase 0 writes no production code. Deliverables are research artifacts under `research/`:

```
research/
├── applet/
│   └── agent.jar                      # already present
├── backups/2026-04-23/
│   └── CONFIG.pcc                     # already present (reference)
├── mirror/2026-04-23/                 # NEW — full HTTP mirror of switch
│   └── (all .html, images, css under the switch's paths)
├── tools/
│   └── cfr-0.152.jar                  # NEW — decompiler binary
├── decompiled/                        # NEW — 80 .java files
├── analysis/                          # NEW — intermediate cross-references
│   ├── class-groups.md
│   ├── url-literals.txt
│   └── applet-params.md
├── protocol/                          # NEW — one md per operation
│   ├── _conventions.md
│   ├── identity/
│   ├── status/
│   ├── configuration/
│   ├── security/
│   ├── diagnostics/
│   ├── support/
│   └── backup/
│       ├── download.md                # known; already partially documented
│       └── upload-restore.md          # to be reverse-engineered
└── fixtures/                          # NEW — live read-response samples
    └── (one .response.txt per read op)
```

Root files created in this phase:

```
.gitignore                 # excludes .env, __pycache__, node_modules, etc.
README.md                  # pointer to spec + current phase
research/README.md         # map of what's in research/ and how to use it
```

---

## Task 0.1: Repo bootstrap

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `research/README.md`

- [ ] **Step 1: Initialize git repo**

Run:
```bash
cd /f/DevProjects/procurve-webui
git init
git config user.email "phil.pelzer@gmail.com"
git config user.name "Phillippe Pelzer"
```
Expected: `Initialized empty Git repository in f:/DevProjects/procurve-webui/.git/`.

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
coverage.xml

# Node
node_modules/
frontend/dist/
npm-debug.log*

# Env & secrets
.env
.env.local
*.pem
*.key

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Research intermediates that are large or reproducible
research/tools/*.jar
research/decompiled/

# Keep backups and mirror in git? YES — they are source-of-truth for Phase 0+
# (so no rule here to exclude them)
```

- [ ] **Step 3: Create `README.md`**

```markdown
# procurve-webui

Modern replacement web UI for the HP ProCurve 2810-24G (J9021A) switch.
Built because the original Java-applet UI no longer runs in modern browsers.

**Target switch:** `http://192.168.178.3` (model J9021A, firmware N.11.78)

## Status

- **Phase 0 — Reverse engineering:** in progress
- Phase 1 — Python `procurve_client` library: pending
- Phase 2 — Docker + read-only UI: later session
- Phase 3+ — Write-capable UI: later sessions

## Documents

- Design spec: [`docs/specs/2026-04-23-procurve-webui-design.md`](docs/specs/2026-04-23-procurve-webui-design.md)
- Phase 0 plan: [`docs/plans/2026-04-23-procurve-webui-phase0.md`](docs/plans/2026-04-23-procurve-webui-phase0.md)
- Phase 1 plan: [`docs/plans/2026-04-23-procurve-webui-phase1.md`](docs/plans/2026-04-23-procurve-webui-phase1.md)

## Research artifacts

See [`research/README.md`](research/README.md).
```

- [ ] **Step 4: Create `research/README.md`**

```markdown
# Research artifacts

This directory holds everything needed to understand the ProCurve 2810-24G
protocol without re-examining the switch or applet from scratch. It is the
Phase 0 output.

## Contents

- `applet/agent.jar` — the original Java applet, byte-for-byte.
- `backups/<date>/CONFIG.pcc` — switch config snapshots. The
  `2026-04-23/CONFIG.pcc` file is the user-verified reference baseline
  used for write-testing roll-back during development. **Do not modify.**
- `mirror/<date>/` — full HTTP asset mirror of the switch.
- `tools/` — decompiler binaries (not committed to git — see `.gitignore`).
- `decompiled/` — `.java` files from CFR (not committed; regenerate with
  the decompile task).
- `analysis/` — intermediate cross-reference notes (class groups, URL
  literal extraction, applet parameter maps).
- `protocol/` — one markdown file per applet operation, documenting the
  HTTP contract.
- `fixtures/` — live response samples captured from read-only operations.
  These become unit-test inputs in Phase 1.
```

- [ ] **Step 5: Stage + commit initial scaffolding and existing artifacts**

Run:
```bash
cd /f/DevProjects/procurve-webui
git add .gitignore README.md research/README.md \
        docs/specs/ \
        docs/plans/ \
        research/applet/agent.jar \
        research/backups/
git status
```
Expected: shows the added files (including `agent.jar`, `CONFIG.pcc`, specs, plans, scaffold files) as staged.

Run:
```bash
git commit -m "chore: bootstrap repo with design spec, phase plans, and reference backup"
```
Expected: commit succeeds; commit message as above.

---

## Task 0.2: Mirror the switch's HTML pages

**Files:**
- Create: `research/mirror/2026-04-23/` and subdirectories mirroring the switch's paths

**Background:** The switch serves a frameset-based UI. HTML pages carry `<applet>` tags whose `param` values are a de-facto directory of operations.

- [ ] **Step 1: Create the mirror script**

**File:** `research/tools/mirror-switch.sh`
```bash
#!/usr/bin/env bash
# Download every known HTML/CSS/image path on the switch into research/mirror/<date>/.
# This is a READ-ONLY operation; no switch state is modified.
set -euo pipefail

SWITCH="${SWITCH_HOST:-192.168.178.3}"
OUT="${1:-research/mirror/$(date +%F)}"
mkdir -p "$OUT"

# Known tab roots (from initial recon)
PATHS=(
  "/"
  "/home.html"
  "/banner.html"
  "/regf.html"
  "/ncfw_b.html"
  "/ncidbar.html"
  "/nctabs.html"
  "/nccont_b.html"
  "/bNotice.html"
  "/blank.html"

  "/identity/index.html"
  "/status/index.html"
  "/status/menu.html"
  "/status/overviewf.html"
  "/status/overview.html"
  "/status/overview2.html"
  "/status/alert.html"
  "/status/portgraph.html"
  "/status/portcf.html"
  "/status/portStatusf.html"

  "/configuration/index.html"
  "/configuration/menu.html"
  "/configuration/device_viewf.html"
  "/configuration/web_agentf.html"
  "/configuration/systemf.html"
  "/configuration/ipf.html"
  "/configuration/portsf.html"
  "/configuration/cos_mainf.html"
  "/configuration/monitorf.html"
  "/configuration/featuresf.html"
  "/configuration/stack_configf.html"
  "/configuration/vlan.html"
  "/configuration/supportf.html"
  "/configuration/configfilef.html"
  "/configuration/configfileSingle.html"
  "/configuration/uploadConfile.html"

  "/security/index.html"
  "/security/menu.html"

  "/diagnostics/index.html"
  "/diagnostics/menu.html"
  "/diagnostics/pingf.html"
  "/diagnostics/resetf.html"
  "/diagnostics/configf.html"
  "/diagnostics/config.html"

  "/support/index.html"
  "/support/support_blank.html"
)

for p in "${PATHS[@]}"; do
  local_path="$OUT$p"
  # For trailing-slash paths, save as index.html
  if [[ "$p" == */ ]]; then
    local_path="${local_path}index.html"
  fi
  mkdir -p "$(dirname "$local_path")"
  echo "GET $p -> $local_path"
  # --fail prints nothing on 4xx/5xx and returns non-zero; we tolerate 404s
  # because not every path above necessarily exists on every firmware.
  curl -s -m 15 -o "$local_path" "http://$SWITCH$p" || {
    echo "  (failed — deleting empty file if present)"
    [ -s "$local_path" ] || rm -f "$local_path"
  }
done

echo "---"
echo "Downloaded files:"
find "$OUT" -type f | sort
```

- [ ] **Step 2: Run the mirror script**

Run:
```bash
cd /f/DevProjects/procurve-webui
chmod +x research/tools/mirror-switch.sh
./research/tools/mirror-switch.sh
```
Expected: a list of GET operations, each followed by either success or a `(failed — deleting empty file if present)` note. Final listing shows ~30+ `.html` files under `research/mirror/2026-04-23/`.

- [ ] **Step 3: Spot-check one known-good and one known-unusual file**

Run:
```bash
wc -l research/mirror/2026-04-23/home.html research/mirror/2026-04-23/configuration/menu.html
head -5 research/mirror/2026-04-23/configuration/menu.html
```
Expected: `home.html` is several dozen lines; `configuration/menu.html` starts with `<html>` and contains an `<applet` tag referring to `agent.jar`.

- [ ] **Step 4: Commit the mirror**

Run:
```bash
git add research/tools/mirror-switch.sh research/mirror/
git commit -m "phase0: add switch asset mirror (scripts + 2026-04-23 snapshot)"
```
Expected: commit succeeds.

---

## Task 0.3: Mirror referenced images and CSS

**Files:**
- Create: `research/tools/mirror-static-assets.py` (Python scanner)
- Create: files in `research/mirror/2026-04-23/` for every referenced asset

**Background:** The HTML pages reference images, GIFs, CSS. We scan the downloaded HTML for src/href and pull those files too.

- [ ] **Step 1: Write the asset-discovery script**

**File:** `research/tools/mirror-static-assets.py`
```python
#!/usr/bin/env python3
"""
Scan research/mirror/<date>/*.html for referenced static assets
(images, CSS, JS, other URLs on the switch) and download any that
aren't already mirrored. Read-only against the switch.
"""
from __future__ import annotations
import argparse
import re
import sys
import urllib.request
from pathlib import Path

SWITCH_HOST = "192.168.178.3"

# Matches src="..." href="..." url(...) with relative or absolute paths.
SRC_RE = re.compile(
    r"""(?:src|href)\s*=\s*["']([^"'#?]+)["']|url\(\s*["']?([^"')]+)["']?\s*\)""",
    re.IGNORECASE,
)

# Skip external hosts and mailto/javascript/http references.
SKIP_PREFIXES = ("http://", "https://", "mailto:", "javascript:", "#", "data:")

def is_asset(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in {
        "gif", "jpg", "jpeg", "png", "bmp", "ico",
        "css", "js",
        "html", "htm",
    }

def normalize(base_dir: Path, ref: str) -> str | None:
    ref = ref.strip().strip('"').strip("'")
    if not ref or any(ref.startswith(p) for p in SKIP_PREFIXES):
        return None
    if ref.startswith("/"):
        return ref
    # Resolve relative path
    base = base_dir.as_posix().split("research/mirror/", 1)[1]
    base = "/" + base.split("/", 1)[1] if "/" in base else "/"
    joined = (Path(base) / ref).resolve().as_posix()
    # Force leading slash
    return joined if joined.startswith("/") else "/" + joined

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", required=True, help="e.g. research/mirror/2026-04-23")
    args = ap.parse_args()

    mirror_root = Path(args.mirror).resolve()
    if not mirror_root.is_dir():
        print(f"No such directory: {mirror_root}", file=sys.stderr)
        return 2

    seen: set[str] = set()
    to_fetch: set[str] = set()

    for html in mirror_root.rglob("*.html"):
        text = html.read_text(errors="replace")
        for m in SRC_RE.finditer(text):
            ref = m.group(1) or m.group(2) or ""
            norm = normalize(html.parent, ref)
            if norm and norm not in seen:
                seen.add(norm)
                if is_asset(norm):
                    to_fetch.add(norm)

    print(f"Discovered {len(to_fetch)} candidate asset paths.")

    fetched = skipped = failed = 0
    for path in sorted(to_fetch):
        local = mirror_root / path.lstrip("/")
        if local.exists():
            skipped += 1
            continue
        url = f"http://{SWITCH_HOST}{path}"
        try:
            local.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=10) as r:
                local.write_bytes(r.read())
            fetched += 1
            print(f"  GET {path}  -> {local.relative_to(mirror_root)}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {path}  ({exc})")

    print(f"Done. fetched={fetched} skipped(existing)={skipped} failed={failed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the asset mirror**

Run:
```bash
python3 research/tools/mirror-static-assets.py --mirror research/mirror/2026-04-23
```
Expected: reports a list of GET operations for any assets not already present; final summary like `Done. fetched=N skipped=M failed=K`. `failed` should be 0 or very small (only for assets the switch doesn't actually serve).

- [ ] **Step 3: Commit the asset mirror**

Run:
```bash
git add research/tools/mirror-static-assets.py research/mirror/
git commit -m "phase0: mirror static assets referenced by switch HTML"
```
Expected: commit succeeds.

---

## Task 0.4: Install the CFR decompiler

**Files:**
- Create: `research/tools/cfr-0.152.jar` (downloaded)
- Create: `research/tools/decompile.sh`

- [ ] **Step 1: Download CFR**

Run:
```bash
mkdir -p research/tools
curl -sSL -o research/tools/cfr-0.152.jar \
  https://github.com/leibnitz27/cfr/releases/download/0.152/cfr-0.152.jar
ls -la research/tools/cfr-0.152.jar
```
Expected: `cfr-0.152.jar` present, size around 2 MB.

- [ ] **Step 2: Verify Java runtime is available**

Run:
```bash
java -version
```
Expected: prints a Java version (any >= 8 is fine for CFR). If missing, install OpenJDK via the system package manager (`scoop install openjdk` on Windows, `apt install default-jre` on Debian) before continuing.

- [ ] **Step 3: Write the decompile helper**

**File:** `research/tools/decompile.sh`
```bash
#!/usr/bin/env bash
# Decompile research/applet/agent.jar into research/decompiled/
# Overwrites any previous output.
set -euo pipefail
JAR="research/applet/agent.jar"
CFR="research/tools/cfr-0.152.jar"
OUT="research/decompiled"

if [ ! -f "$CFR" ]; then
  echo "CFR not found at $CFR" >&2
  exit 1
fi
if [ ! -f "$JAR" ]; then
  echo "Applet JAR not found at $JAR" >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"
echo "Decompiling $JAR ..."
java -jar "$CFR" "$JAR" \
  --outputdir "$OUT" \
  --silent true \
  --comments false \
  --showversion false \
  --recover true
echo "Produced $(find "$OUT" -name '*.java' | wc -l) Java files."
```

Run:
```bash
chmod +x research/tools/decompile.sh
```

- [ ] **Step 4: Commit the decompiler setup**

Run:
```bash
git add research/tools/decompile.sh
# Note: cfr-0.152.jar is excluded via .gitignore — user re-downloads on fresh clone.
git commit -m "phase0: add CFR decompiler setup and wrapper script"
```
Expected: commit succeeds (does not include the JAR).

---

## Task 0.5: Decompile agent.jar

**Files:**
- Create: 80 `.java` files under `research/decompiled/` (not committed to git)

- [ ] **Step 1: Run the decompiler**

Run:
```bash
./research/tools/decompile.sh
```
Expected: `Produced 80 Java files.` (might be slightly different if CFR collapses synthetic classes).

- [ ] **Step 2: Sanity-check a representative file**

Run:
```bash
ls research/decompiled | head -20
wc -l research/decompiled/PageSelector.java research/decompiled/VLANmain.java
head -30 research/decompiled/PageSelector.java
```
Expected: list of `.java` files; `head` output shows a valid Java class, with a package-less `public class PageSelector extends Applet` or similar. If output looks like garbled bytecode or single-line mush, re-run with `--comments true --showversion true` and inspect for errors.

- [ ] **Step 3: No commit needed (gitignored)**

The decompiled sources are reproducible from `agent.jar`; they are explicitly not committed.

---

## Task 0.6: Classify the 80 classes by responsibility

**Files:**
- Create: `research/analysis/class-groups.md`

**Background:** Before diving into operations, we group classes so we can focus on the ones that matter. Many `*Bob.class` files are visual renders of different switch models — irrelevant for our protocol work.

- [ ] **Step 1: List class names with sizes**

Run:
```bash
ls -la research/decompiled/ | awk 'NR>1 {printf "%6d  %s\n", $5, $NF}' | sort -n > research/analysis/class-sizes.txt
wc -l research/analysis/class-sizes.txt
```
Expected: file with 80 lines, sorted by size ascending.

- [ ] **Step 2: Create class-groups.md with groupings**

**File:** `research/analysis/class-groups.md`
```markdown
# Class grouping — agent.jar (ProCurve 2810-24G)

Grouped by apparent responsibility after a first look at `research/decompiled/`.
Update this file as analysis proceeds.

## A. Navigation / page framework
- `PageSelector` — tab / button bar applet hosted by `menu.html` and `nctabs.html`. Reads its buttons from applet `<param>` tags.
- `PageButton` — individual tab/button.

## B. Device rendering (visual switch chassis)
- `Drawable`, `SwitchBob`, `GenericBob`, `Sw16hBob`, `Sw8kBob`, `SwGammaBob`, `SwMinnie_meBob`, `SwStrongbadBob`, `SwToontownBob`, `TomcatBob`, `InfinityBob`, `XFishBob`, `BleachImageFilter`, `ColorCache`
  - These are visual code. `SwStrongbadBob` is the likely renderer for the J9021A chassis. Not needed for protocol, but we mine string literals anyway in case URLs live here.

## C. Port counters / graphs
- `PortGraph` (21 KB — largest) — the live port traffic gauge applet (hosted by `status/portgraph.html`).
- `YScale` — graph Y-axis helper.

## D. VLAN subsystem
- `VLANAddRemovePanel` + `$1..$6`
- `VLANDialog` + `$1..$2`
- `VLANTable` + `$1`
- `VLANLine`, `VLANmultiLineLabel`
- `VLANfirstPanel` + `$1..$4`
- `VLANgvrpPanel` + `$1..$5`
- `VLANmodifyPanel` + `$1..$5`
- `VLANprotocolPanel` + `$1`
- `VLANmain` — entry point

## E. Stacking subsystem
- `StackConfig`, `StackControl`, `StackControlButton`, `StackDialog`

## F. Core UI primitives
- `GenericList`, `GenericTable` + `$1`, `GenericRowEntry`
- `ListLine`, `ListPane`, `ListTitle`, `MultiList` + `$1`
- `MemberCandidateList`, `MonitorList`

## G. Status / device state
- `DeviceStatus`

## H. HTTP callback machinery ★
- `Callback`, `CallbackClient`, `ResultProcessor`
  - These are the protocol layer: request dispatch and response handling. Highest priority to understand.

## I. Utility / misc
- `Assert`, `Util`
- `ErrorDialog`
- `ToolTipTimer`
- `PasswdTextField`

## Next steps
1. Fully analyze group H (CallbackClient) — establishes the base URL and HTTP conventions.
2. Analyze PageSelector (group A) — shows how operations are declared in `<applet>` params.
3. Walk through each feature group (D, E, G, C) and extract URL literals.
4. Cross-reference extracted URLs with the HTML mirror for parameter layout.
```

- [ ] **Step 3: Commit the classification**

Run:
```bash
git add research/analysis/class-sizes.txt research/analysis/class-groups.md
git commit -m "phase0: classify 80 applet classes by responsibility"
```
Expected: commit succeeds.

---

## Task 0.7: Analyze the HTTP callback layer (CallbackClient / ResultProcessor / Callback)

**Files:**
- Create: `research/analysis/callback-layer.md`

**Background:** These three classes implement the generic request/response plumbing. Understanding them tells us the URL format, HTTP method, and response parsing strategy shared by ALL operations.

- [ ] **Step 1: Dump the three class files**

Run:
```bash
head -200 research/decompiled/CallbackClient.java
head -200 research/decompiled/Callback.java
head -200 research/decompiled/ResultProcessor.java
```
Expected: see source with class declarations, methods, and calls to `java.net.URL`, `openConnection`, `getInputStream`, etc. Note field names and method signatures.

- [ ] **Step 2: Grep for all URL construction sites across the applet**

Run:
```bash
grep -n "openConnection\|new URL\|getInputStream\|DataInputStream\|HttpURLConnection\|POST\|getOutputStream" research/decompiled/*.java | tee research/analysis/url-sites.txt
wc -l research/analysis/url-sites.txt
```
Expected: a list of line-hits. Expect dozens of matches concentrated in CallbackClient + ResultProcessor + a handful of feature classes (e.g. VLANmain, StackConfig).

- [ ] **Step 3: Write up the callback protocol**

**File:** `research/analysis/callback-layer.md`

Read the three source files and answer in this doc (with line-number citations in `research/decompiled/<file>:line` format):

```markdown
# Applet callback / HTTP layer

## Base URL construction
- Where is the base URL computed? (Expect `getCodeBase()` or `getDocumentBase()` in an applet `init()`)
- Are there any URL parameters injected globally (e.g. session token, language)?

## Request shape
- GET vs POST split: which operations use which method?
- Headers emitted explicitly (User-Agent, Content-Type, Cookie, ...)
- Request body encoding for POSTs (form-encoded? custom pipe-delimited? binary?)

## Response shape
- Response content-type the code expects
- Parsing strategy (line-based? delimiter? fixed offsets?)
- Sentinel strings for success vs error

## Exceptions / error handling
- Which Java exceptions are caught where?
- How does the applet surface errors back to the user?

## Session / auth
- Any cookies read or stored?
- Basic-auth handling path? (`Authorization` header usage)

## Citation index
- `CallbackClient.java:NN` — <what happens here>
- `ResultProcessor.java:NN` — <what happens here>
- `Callback.java:NN` — <what happens here>
```

Fill in every section from the actual source. Leave no "TBD" lines — if an item truly doesn't apply, write `Not used.` with the line citation that established that.

- [ ] **Step 4: Commit the analysis**

Run:
```bash
git add research/analysis/url-sites.txt research/analysis/callback-layer.md
git commit -m "phase0: analyze HTTP callback layer (CallbackClient/ResultProcessor/Callback)"
```
Expected: commit succeeds.

---

## Task 0.8: Extract every URL string literal from the applet

**Files:**
- Create: `research/analysis/url-literals.txt`
- Create: `research/analysis/url-literals.md`

- [ ] **Step 1: Extract string literals ending in known patterns**

Run:
```bash
grep -oE '"[^"]*(\.html|\.cgi|/cgi/[^"]*|\?[^"]*|\.txt)"' research/decompiled/*.java \
  | sort -u \
  > research/analysis/url-literals.txt
wc -l research/analysis/url-literals.txt
head -30 research/analysis/url-literals.txt
```
Expected: file with dozens of unique quoted-string hits that look like URL fragments — e.g. `"/cgi/configfile?"`, `"status/portStatusf.html"`.

- [ ] **Step 2: Grep for all `<param>` strings to find operation names**

Run:
```bash
grep -oE '"(get|set|add|del|mod|show|list|apply|save|load|upload|download|action|op|cmd|target)=[^"]*"' research/decompiled/*.java \
  | sort -u \
  >> research/analysis/url-literals.txt
```
Expected: appends operation-like tokens. Some classes may hardcode `?op=...` strings.

- [ ] **Step 3: Organize and annotate**

**File:** `research/analysis/url-literals.md`

Go through `url-literals.txt` and group the hits:

```markdown
# URL literals & operation tokens extracted from agent.jar

Generated by grep on 2026-04-23; see `url-literals.txt` for the raw list.

## HTML pages (frame navigation)
- `"/status/portStatusf.html"` — in `<class>.java`
- ...

## /cgi endpoints (protocol calls)
- `"/cgi/configfile"` — config download/upload (see `protocol/backup/*.md`)
- ... (add every /cgi hit)

## Operation tokens
- `"op=..."` — where used, with class reference
- ...

## Suspicious / unknown
- Anything that doesn't fit the above buckets — keep separate for investigation.
```

Every entry must carry at least one `<class>.java:<line>` citation so future work can trace it back.

- [ ] **Step 4: Commit**

Run:
```bash
git add research/analysis/url-literals.txt research/analysis/url-literals.md
git commit -m "phase0: enumerate URL literals and operation tokens from decompiled applet"
```
Expected: commit succeeds.

---

## Task 0.9: Map every `<applet>` param in the mirrored HTML

**Files:**
- Create: `research/analysis/applet-params.md`

**Background:** HTML pages invoke the applet with `<param name=... value=...>` tags. These often enumerate the operations per page: which buttons, which callback URLs, which selection is default.

- [ ] **Step 1: Grep the mirror**

Run:
```bash
grep -rE '<param\s+name=' research/mirror/2026-04-23/ \
  | tee research/analysis/applet-params.raw.txt \
  | wc -l
```
Expected: dozens of matches, one per `<param>` tag across all mirrored HTML.

- [ ] **Step 2: Write a human-readable cross-reference**

**File:** `research/analysis/applet-params.md`
```markdown
# Applet parameters per mirrored HTML page

One section per HTML page that embeds an `<applet>`. Each row lists the
parameter name, parameter value, and (where obvious) the operation it
enables.

## /status/menu.html
- `target=nc_view` — target frame name
- `buttons=overview~Overview~../status/overviewf.html~selected,
          portc~Port Counters~../status/portcf.html,
          portstatus~Port Status~../status/portStatusf.html` — three
  sub-tabs under Status.

## /configuration/menu.html
- `target=nc_view`
- `buttons=<twelve entries — devview, faultdetect, system, ip, ports,
          qos, monitor, devfeatures, stacking, vlan, support, uploadf>`
- `selection=devview`

## ... (one section per HTML file)
```

Complete a section for every HTML file in the mirror that contains an `<applet>` tag. Use `grep -l '<applet' research/mirror/2026-04-23/` to enumerate them.

- [ ] **Step 3: Commit**

Run:
```bash
git add research/analysis/applet-params.raw.txt research/analysis/applet-params.md
git commit -m "phase0: cross-reference applet <param> tags across mirrored HTML"
```
Expected: commit succeeds.

---

## Task 0.10: Establish protocol doc conventions

**Files:**
- Create: `research/protocol/_conventions.md`

- [ ] **Step 1: Write the conventions doc**

**File:** `research/protocol/_conventions.md`
```markdown
# Protocol documentation conventions

Every file under `research/protocol/<tab>/<operation>.md` follows
the same template so Phase 1 can translate each doc into Python with
a purely mechanical read.

## Template

```
# <operation_name>

**Tab:** <identity | status | configuration | security | diagnostics | support | backup>
**Kind:** read | write
**Source in applet:** <Class>.java:<line-range> (one or more)
**Source in HTML:** <path>#<fragment> if applicable

## HTTP contract

- **Method:** GET | POST | (other)
- **URL template:** `<literal URL with {placeholders}>`
- **Query params:** <table of name, type, required?, description>
- **Request headers:** <table>
- **Request body:** <format + fields, or "none">
- **Response headers (relevant):** <table or "none">
- **Response body:** <shape description + sample>
- **Success indicator:** <HTTP 200 is enough | specific body substring | etc.>
- **Error indicators:** <list>

## Field reference

<table of every field on request and response: Java field name,
wire representation, Python type, validation rule, notes>

## Example request (prepared, NOT live-tested for writes)

```
<full raw HTTP request with placeholder values>
```

## Example response (live-captured for reads)

See `research/fixtures/<operation>.response.txt`.

## Pydantic sketch

```python
class <Operation>Request(BaseModel):
    ...

class <Operation>Response(BaseModel):
    ...
```

## Notes & caveats

- Edge cases, validation rules from Java code, related operations, known
  quirks.
```

## Naming conventions

- File names are snake_case, describing the user-visible operation:
  `get_port_status.md`, `set_port_name.md`, `create_vlan.md`.
- For write operations, include the verb (`set_`, `create_`, `delete_`,
  `apply_`, `reset_`, `upload_`, `download_`).
- Group by tab directory (`identity/`, `status/`, ...). Operations used
  by multiple tabs live under `_shared/`.
```

- [ ] **Step 2: Create the per-tab directories**

Run:
```bash
mkdir -p research/protocol/{identity,status,configuration,security,diagnostics,support,backup,_shared}
```

- [ ] **Step 3: Commit**

Run:
```bash
git add research/protocol/_conventions.md research/protocol/
git commit -m "phase0: protocol doc conventions and per-tab directories"
```
Expected: commit succeeds.

---

## Task 0.11: Document the backup download operation (already known)

**Files:**
- Create: `research/protocol/backup/download.md`

**Background:** We already know this contract from reconnaissance. Capturing it first as a worked example.

- [ ] **Step 1: Write the doc**

**File:** `research/protocol/backup/download.md`
```markdown
# download_config

**Tab:** backup
**Kind:** read
**Source in applet:** none (the applet exposes this via the HTML form,
not bytecode). See `research/analysis/url-literals.md` for any passing
references.
**Source in HTML:** `research/mirror/2026-04-23/configuration/configfileSingle.html`

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/configfile?idx={idx}&fg={fg}&D1=Download`
- **Query params:**
  | name | type | required | description |
  |---|---|---|---|
  | idx | int | yes | Config slot index. 1 = Primary, 2 = Secondary. |
  | fg  | int | yes | Selected config file, matches `idx` in the default form (JS does `idx = fg` on submit). |
  | D1  | const "Download" | yes | Form submit button name. Distinguishes download from delete. |
- **Request headers:** none required
- **Request body:** none
- **Response headers (relevant):**
  | header | value | notes |
  |---|---|---|
  | Content-Type | `application/octet-stream; file="CONFIG.pcc"` | note the unusual `file=` parameter |
  | Content-Disposition | `attachment; filename="CONFIG.pcc"` | |
- **Response body:** ASCII text with CRLF line terminators, same syntax as
  `show running-config` on the CLI. Starts with `; J9021A Configuration
  Editor; Created on release #<firmware>`. Ends after the last
  configuration line.
- **Success indicator:** HTTP 200 with Content-Type header matching
  `application/octet-stream`. A 200 response with `text/html` means the
  form wasn't interpreted as a download — retry with explicit `D1`
  parameter.
- **Error indicators:** Non-200 HTTP; `text/html` response body
  indicates the switch fell through to the default HTML UI.

## Field reference

| field | wire | python | validation | notes |
|---|---|---|---|---|
| idx | query string | `Literal[1, 2]` | 1 or 2 | Primary or Secondary |
| fg  | query string | `Literal[1, 2]` | must match idx | JS asserts this |

## Example request

```
GET /cgi/configfile?idx=1&fg=1&D1=Download HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response (live-captured)

See `research/fixtures/download_config.response.txt` (captured 2026-04-23;
CONFIG.pcc contents, 2904 bytes, SHA256
`f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11`).

## Pydantic sketch

```python
from typing import Literal
from pydantic import BaseModel

class DownloadConfigRequest(BaseModel):
    idx: Literal[1, 2] = 1
    fg: Literal[1, 2] = 1

class DownloadConfigResponse(BaseModel):
    text: str        # the raw running-config
    sha256: str      # computed hex digest
    size: int        # byte length
```

## Notes & caveats

- The raw response is used both as a human-readable snapshot AND as the
  upload body to restore via `upload_config` (see
  `upload-restore.md`). Round-trip fidelity must be preserved — do NOT
  normalize line endings or strip whitespace on the client.
- The empty-form submission (no `D1=Download`) returns a confirmation
  HTML page instead of the file. This is a quirk of the CGI: only the
  submit-button name identifies the action.
```

- [ ] **Step 2: Capture the fixture**

Run:
```bash
mkdir -p research/fixtures
curl -s -m 15 -o research/fixtures/download_config.response.txt \
  "http://192.168.178.3/cgi/configfile?idx=1&fg=1&D1=Download"
wc -c research/fixtures/download_config.response.txt
sha256sum research/fixtures/download_config.response.txt
```
Expected: file with 2904 bytes (current firmware), SHA256 matching the reference backup. If different: switch state has changed since 2026-04-23 — investigate before continuing (see write-safety rule).

- [ ] **Step 3: Commit**

Run:
```bash
git add research/protocol/backup/download.md research/fixtures/download_config.response.txt
git commit -m "phase0: document download_config operation + capture fixture"
```
Expected: commit succeeds.

---

## Task 0.12: Reverse-engineer the backup upload/restore mechanism

**Files:**
- Create: `research/protocol/backup/upload-restore.md`

**Background:** Upload is a write op. We only reverse-engineer it — we do not live-test it without user go-ahead per the safety rule.

- [ ] **Step 1: Inspect the upload HTML**

Run:
```bash
cat research/mirror/2026-04-23/configuration/uploadConfile.html
```
Expected: HTML form with file-input, action attribute, hidden form fields (expect something like `action="../cgi/configfile"`, method="POST", enctype="multipart/form-data").

- [ ] **Step 2: Grep for upload string literals**

Run:
```bash
grep -rn "multipart\|enctype\|Content-Disposition\|uploadConfile\|uploadImgfile\|boundary" research/decompiled/ research/mirror/2026-04-23/
```
Expected: zero or more hits identifying the upload contract.

- [ ] **Step 3: Write the doc**

**File:** `research/protocol/backup/upload-restore.md`

Fill the template completely, using the HTML form definition and any supporting Java code:

```markdown
# upload_config

**Tab:** backup
**Kind:** write
**Source in HTML:** `research/mirror/2026-04-23/configuration/uploadConfile.html`
**Source in applet:** <list any Java class references, or "none — this is a plain HTML form">

## HTTP contract

- **Method:** POST
- **URL template:** `<from form action attribute>`
- **Request headers:**
  | header | value | notes |
  |---|---|---|
  | Content-Type | `multipart/form-data; boundary=<boundary>` | |
- **Request body:** <multipart parts — name, value/filename, content-type per part>
- **Response body:** <what does the switch return? HTML page, plain text?>
- **Success indicator:** <HTTP code + body pattern>
- **Error indicators:** <list>

## Multipart parts (detailed)

<for each form field in the HTML:>
- `name=<field>`, `filename=<file>` (if file), `Content-Type: <type>`, body = <description>

## Example request

```
POST <path> HTTP/1.1
Host: 192.168.178.3
Content-Type: multipart/form-data; boundary=---BOUNDARY
Content-Length: <len>

-----BOUNDARY
Content-Disposition: form-data; name="<field>"

<value>
-----BOUNDARY
Content-Disposition: form-data; name="<file-field>"; filename="CONFIG.pcc"
Content-Type: application/octet-stream

<raw CONFIG.pcc bytes>
-----BOUNDARY--
```

## Pydantic sketch

```python
class UploadConfigRequest(BaseModel):
    idx: Literal[1, 2] = 1      # target slot
    config_bytes: bytes          # raw CONFIG.pcc contents, CRLF preserved

class UploadConfigResponse(BaseModel):
    accepted: bool
    message: str | None = None
```

## Notes & caveats

- **This operation is not live-tested.** First round-trip
  demonstration happens only under explicit user approval in
  Task 1.17 of the Phase 1 plan.
- Applying an upload may require a reboot or a `copy tftp`-style commit.
  Check the HTML / Java for a subsequent "apply" or "reload" step and
  document it here.
- If the upload changes the active slot immediately (no reboot), the
  restore-verify workflow in the dev-time safety rule is a single-step
  operation. If a reboot is required, document the reboot URL too.
```

Complete every section. No TBDs. If a field's meaning can only be guessed, mark it **explicitly** as `unknown — needs live capture under user supervision before use`.

- [ ] **Step 4: Commit**

Run:
```bash
git add research/protocol/backup/upload-restore.md
git commit -m "phase0: document upload_config / restore mechanism (no live test)"
```
Expected: commit succeeds.

---

## Task 0.13 – 0.18: Document each tab's operations

**Background:** These six tasks follow the same pattern. Each task covers one tab and produces one protocol doc per operation in that tab plus fixtures for every read operation. They cannot be fully pre-enumerated in this plan because the operation list emerges from the analysis.

For each tab:

### Task 0.13: Identity tab
### Task 0.14: Status tab
### Task 0.15: Configuration tab
### Task 0.16: Security tab
### Task 0.17: Diagnostics tab
### Task 0.18: Support tab

Each of these tasks follows this template (shown once here; the executor repeats it per tab):

**Files per task:**
- Create: `research/protocol/<tab>/<op_name>.md` — one per operation discovered
- Create: `research/fixtures/<tab>__<op_name>.response.txt` — one per **read** operation
- Update: `research/analysis/class-groups.md` — refine class->tab mapping as understanding grows

- [ ] **Step 1: Identify operations in this tab**

From `research/analysis/applet-params.md`, list each `<applet>` button for this tab (e.g. for Configuration: `devview`, `faultdetect`, `system`, `ip`, `ports`, `qos`, `monitor`, `devfeatures`, `stacking`, `vlan`, `support`, `uploadf`). Each button maps to one sub-page, which typically corresponds to one or two operations (usually a `get` + a `set`).

- [ ] **Step 2: For each operation, read the relevant Java + HTML**

Use `research/analysis/class-groups.md` and `research/analysis/url-literals.md` to find the source. Example for VLAN: `VLANmain.java`, `VLANTable.java`, `VLANAddRemovePanel.java`, `VLANmodifyPanel.java`, plus `configuration/vlan.html`.

- [ ] **Step 3: Write one protocol doc per operation**

Use the template from `research/protocol/_conventions.md`. Cite source files with line numbers. Fill every section. No TBDs.

- [ ] **Step 4: For every read operation, capture a live fixture**

Run (example):
```bash
curl -s -m 15 -o research/fixtures/<tab>__<op_name>.response.txt \
  "http://192.168.178.3<url-from-doc>"
head research/fixtures/<tab>__<op_name>.response.txt
wc -c research/fixtures/<tab>__<op_name>.response.txt
```
Expected: file contains whatever the switch returns for that operation. Validate the format matches what the protocol doc predicts. If it doesn't: the doc is wrong — fix the doc.

- [ ] **Step 5: For every write operation, verify the request template**

Verify by **static analysis only** (no live POST). Read the Java bytecode-level request-build code and confirm every byte of the example request in the doc. Byte-level accuracy matters because Phase 1 will byte-match the request in unit tests.

- [ ] **Step 6: Commit per-tab**

Run:
```bash
git add research/protocol/<tab>/ research/fixtures/<tab>__*.response.txt research/analysis/class-groups.md
git commit -m "phase0: document <tab>-tab operations (<N> ops, <M> read fixtures captured)"
```
Expected: commit succeeds.

**Tab ordering rationale:** the Status and Identity tabs have the simplest operations (pure reads of device state); doing them first tames the protocol. Configuration is the largest (VLAN + ports + stacking is a sub-plan in itself). Security and Diagnostics are medium. Support is mostly a static link to HP's website + the config-download entry point which is already covered.

---

## Task 0.19: Phase 0 gate — readiness for Phase 1

**Files:**
- Create: `research/phase0-status.md`

- [ ] **Step 1: Write the status summary**

**File:** `research/phase0-status.md`
```markdown
# Phase 0 completion status

Phase 0 is DONE when every section below has a concrete answer.

## Checklist

- [ ] All 80 applet classes classified in `analysis/class-groups.md`.
- [ ] `analysis/callback-layer.md` describes URL construction, method
      choice, encoding, parsing, error handling, session/auth for the
      callback plumbing, with source citations.
- [ ] Every HTML file in `mirror/2026-04-23/` that embeds an applet has
      a section in `analysis/applet-params.md`.
- [ ] Every `/cgi/*` endpoint referenced in `analysis/url-literals.md`
      has a corresponding protocol doc under `protocol/<tab>/` OR is
      explicitly marked as not-user-facing.
- [ ] Every user-facing operation has a protocol doc that fills
      every section of `_conventions.md`.
- [ ] Every read operation has a fixture in `fixtures/`.
- [ ] `protocol/backup/download.md` + `protocol/backup/upload-restore.md`
      both complete. Upload-restore clearly flags any `unknown` fields.
- [ ] Unknowns are listed here with a reason and a mitigation plan.

## Unknowns / open items

<empty if everything is covered; otherwise list them here>

## Counts (for sanity)

- Operations documented: <N>
- Read fixtures captured: <M>
- Write operations without live verification: <K>  (expected to match N_writes)
```

- [ ] **Step 2: Fill the checklist, verify each item**

Either tick every box or block Phase 1 and go back to the relevant task.

- [ ] **Step 3: Commit and tag**

Run:
```bash
git add research/phase0-status.md
git commit -m "phase0: completion status — Phase 0 closed"
git tag -a phase0-complete -m "Phase 0 reverse-engineering deliverables complete"
```
Expected: commit and tag succeed.

---

## Self-review — Phase 0 plan

Spec coverage (§5 of the spec):

- §5.1 Asset mirror — Tasks 0.2, 0.3 ✓
- §5.2 JAR decompilation — Tasks 0.4, 0.5 ✓
- §5.3 Protocol documentation — Tasks 0.10, 0.11, 0.13–0.18 ✓
- §5.4 Live verification — Step 4 of Tasks 0.11, 0.13–0.18 (read fixtures) ✓
- §5.5 Backup feasibility — Task 0.11 + Task 0.12 (already-verified + upload RE) ✓
- §5.6 Deliverables — Task 0.19 gate verifies all deliverables present ✓

Spec §7 safety rules are enforced in Task 0.12: no live-test of upload without user go-ahead.

Placeholder scan: no "TBD" or "add appropriate ..." directives. Tasks 0.13–0.18 are parameterized (one task per tab) but each step is concrete. This is unavoidable because the operation list emerges from the analysis; per-operation steps would be speculative.
