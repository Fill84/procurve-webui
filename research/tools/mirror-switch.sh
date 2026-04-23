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
