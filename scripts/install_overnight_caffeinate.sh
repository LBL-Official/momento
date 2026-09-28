#!/bin/bash
# Prevent idle/system sleep so overnight ingest can finish.
# Leave the Mac plugged in. A closed MacBook lid can still sleep.
set -euo pipefail
ROOT="/Users/user/Desktop/Momento"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$ROOT/logs"

write_plist() {
  local label="$1" program="$2" keep_success="$3"
  local dest="$AGENTS/${label}.plist"
  if [ "$keep_success" = "always" ]; then
    keep='  <key>KeepAlive</key>
  <true/>'
  else
    keep='  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>'
  fi
  cat >"$dest" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${program}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
${keep}
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/${label}.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/${label}.log</string>
</dict>
</plist>
EOF
  launchctl unload "$dest" 2>/dev/null || true
  launchctl load "$dest"
  echo "loaded $label"
}

chmod +x "$ROOT/scripts/mlb_canonical_catchup.sh" \
  "$ROOT/scripts/mlb_kalshi_backfill_watchdog.sh" \
  "$ROOT/scripts/mlb_orderbook_loop.sh" \
  "$ROOT/scripts/install_overnight_caffeinate.sh"

cat >"$AGENTS/com.momento.caffeinate.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.momento.caffeinate</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string>
    <string>-dims</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/user/Desktop/Momento/logs/com.momento.caffeinate.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/user/Desktop/Momento/logs/com.momento.caffeinate.log</string>
</dict>
</plist>
EOF
launchctl unload "$AGENTS/com.momento.caffeinate.plist" 2>/dev/null || true
launchctl load "$AGENTS/com.momento.caffeinate.plist"
echo "loaded com.momento.caffeinate"

write_plist com.momento.mlb-catchup "$ROOT/scripts/mlb_canonical_catchup.sh" onfail
write_plist com.momento.mlb-backfill-watchdog "$ROOT/scripts/mlb_kalshi_backfill_watchdog.sh" onfail
write_plist com.momento.mlb-orderbook "$ROOT/scripts/mlb_orderbook_loop.sh" always

echo "---"
launchctl list | grep com.momento || true
pgrep -fl 'caffeinate -dims|mlb_canonical_catchup|mlb_kalshi_backfill|mlb_orderbook_loop' || true
