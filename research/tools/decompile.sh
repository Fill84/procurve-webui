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
