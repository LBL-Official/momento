#!/bin/bash
set -euo pipefail
for label in com.momento.auto-roller.verify com.momento.auto-roller.ingest; do
  dest="$HOME/Library/LaunchAgents/${label}.plist"
  launchctl unload "$dest" 2>/dev/null || true
  rm -f "$dest"
  echo "unloaded $label"
done
