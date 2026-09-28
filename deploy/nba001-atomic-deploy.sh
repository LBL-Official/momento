#!/usr/bin/env bash
# Install / upgrade momento-nba-001.service on the MLB live host.
# Operator SSM only. Never VITAL_AWS_CONTROL. Never touches momento-live.service,
# /usr/local/bin/momento-trading-engine, live.toml, or MLB state.
# Process up is not success: require a fresh status.json heartbeat whose
# binary_sha256 equals the expected digest and whose mode equals the requested mode.
set -euo pipefail

BUNDLE="${1:?s3:// prefix holding the nba001 build bundle (ends with /)}"
EXPECTED="${2:?expected sha256 of momento-nba-001}"
MODE="${3:?live_data_only | shadow}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

case "$MODE" in
  live_data_only|shadow) ;;
  *) echo "nba001 deploy refuses mode=$MODE (live is not deployable: production orders are compiled out)" >&2; exit 78 ;;
esac

UNIT=momento-nba-001.service
BIN=/usr/local/bin/momento-nba-001
NEW=/usr/local/bin/momento-nba-001.new
CFG=/etc/momento/nba-001.toml
CONTRACT_DIR=/etc/momento/nba-001
CONTRACT=$CONTRACT_DIR/execution_contract.json
STATE=/var/lib/momento/nba-001
FETCH=/usr/local/libexec/nba001-fetch-secret.sh
STAGE=$(mktemp -d /tmp/nba001-stage.XXXXXX)
trap 'rm -rf "$STAGE"' EXIT
MLB_BIN=/usr/local/bin/momento-trading-engine

mlb_fingerprint() {
  printf '%s %s %s' \
    "$(systemctl is-active momento-live.service || true)" \
    "$(systemctl show -p MainPID --value momento-live.service || true)" \
    "$(sha256sum "$MLB_BIN" 2>/dev/null | awk '{print $1}')"
}
MLB_BEFORE=$(mlb_fingerprint)

aws s3 cp "${BUNDLE}SHA256" "$STAGE/SHA256" --region "$REGION" --only-show-errors
for f in $(awk '{print $2}' "$STAGE/SHA256"); do
  aws s3 cp "${BUNDLE}${f}" "$STAGE/$f" --region "$REGION" --only-show-errors
done
for f in momento-nba-001 nba-001.toml execution_contract.json momento-nba-001.service nba001-fetch-secret.sh; do
  test -f "$STAGE/$f"
done
(cd "$STAGE" && sha256sum -c SHA256 --quiet)
test "$(sha256sum "$STAGE/momento-nba-001" | awk '{print $1}')" = "$EXPECTED"
file "$STAGE/momento-nba-001" | grep -q "ARM aarch64"
CONTRACT_SHA=$(sha256sum "$STAGE/execution_contract.json" | awk '{print $1}')

install -d -o momento -g momento -m 0750 "$STATE"
install -d -o root -g momento -m 0750 "$CONTRACT_DIR"
install -o root -g root -m 0755 "$STAGE/nba001-fetch-secret.sh" "$FETCH"
install -o root -g momento -m 0640 "$STAGE/execution_contract.json" "$CONTRACT"
sed -e "s#^contract_path = .*#contract_path = \"$CONTRACT\"#" \
    -e "s#^mode = .*#mode = \"$MODE\"#" \
    "$STAGE/nba-001.toml" > "$STAGE/nba-001.host.toml"
grep -q "^mode = \"$MODE\"" "$STAGE/nba-001.host.toml"
grep -q '^enabled = false' "$STAGE/nba-001.host.toml"
install -o root -g momento -m 0640 "$STAGE/nba-001.host.toml" "$CFG"

UNIT_CHANGED=1
if [[ -f /etc/systemd/system/$UNIT ]] && cmp -s "$STAGE/momento-nba-001.service" "/etc/systemd/system/$UNIT"; then
  UNIT_CHANGED=0
fi
install -o root -g root -m 0644 "$STAGE/momento-nba-001.service" "/etc/systemd/system/$UNIT"

BAK=""
if [[ -f "$BIN" ]]; then
  CURRENT=$(sha256sum "$BIN" | awk '{print $1}')
  BAK="${BIN}.${CURRENT:0:8}.bak"
  cp -a "$BIN" "$BAK"
fi
install -o root -g root -m 0755 "$STAGE/momento-nba-001" "$NEW"
mv -f "$NEW" "$BIN"
test "$(sha256sum "$BIN" | awk '{print $1}')" = "$EXPECTED"

rollback() {
  echo "DEPLOY_FAIL" >&2
  if [[ -n "$BAK" ]]; then
    echo "restoring $BAK" >&2
    cp -a "$BAK" "$NEW"
    mv -f "$NEW" "$BIN"
    systemctl restart "$UNIT" || true
  else
    systemctl disable --now "$UNIT" || true
  fi
  journalctl -u "$UNIT" -n 30 --no-pager -o cat >&2 || true
}

[[ "$UNIT_CHANGED" == 1 ]] && systemctl daemon-reload
systemctl enable "$UNIT" >/dev/null
systemctl restart "$UNIT"

ok=0
for _ in $(seq 1 36); do
  sleep 5
  systemctl is-active --quiet "$UNIT" || continue
  [[ -f "$STATE/status.json" ]] || continue
  if python3 - "$STATE/status.json" "$EXPECTED" "$MODE" "$CONTRACT_SHA" <<'PY'
import json, sys, time
path, sha, mode, csha = sys.argv[1:5]
s = json.load(open(path))
fresh = time.time() - int(s.get("heartbeat_at") or 0) <= 90
ok = (fresh and s.get("binary_sha256") == sha and str(s.get("config_mode")).lower() == mode
      and s.get("contract_sha256") == csha and s.get("submits") is False
      and s.get("production_orders_compiled") is False)
sys.exit(0 if ok else 1)
PY
  then
    ok=1
    break
  fi
done

MLB_AFTER=$(mlb_fingerprint)
if [[ "$MLB_BEFORE" != "$MLB_AFTER" ]]; then
  echo "MLB fingerprint changed during NBA deploy: before=[$MLB_BEFORE] after=[$MLB_AFTER]" >&2
  rollback
  exit 1
fi
if [[ "$ok" != 1 ]]; then
  rollback
  exit 1
fi

echo "DEPLOY_OK sha=$EXPECTED mode=$MODE contract=${CONTRACT_SHA:0:12} backup=${BAK:-none}"
echo "mlb_unchanged=[$MLB_AFTER]"
echo "running != healthy != executing; production_orders_compiled=false"
