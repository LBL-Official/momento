#!/usr/bin/env bash
# Atomic install of /usr/local/bin/momento-trading-engine on the live host.
# Operator SSM/SCP only. Never VITAL_AWS_CONTROL. Never edit live.toml.
# Process up is not success. Require recon_cleared + Healthy + submit enabled.
set -euo pipefail

EXPECTED="${1:?expected sha256 of incoming aarch64 binary}"
SRC="${2:?local path or s3:// URI of the verified binary}"
BIN=/usr/local/bin/momento-trading-engine
NEW=/usr/local/bin/momento-trading-engine.new
UNIT=momento-live.service
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

if [[ "$SRC" == s3://* ]]; then
  aws s3 cp "$SRC" "$NEW" --region "$REGION"
else
  cp -a "$SRC" "$NEW"
fi
chmod 0755 "$NEW"
file "$NEW" | grep -q "ARM aarch64"
ACTUAL=$(sha256sum "$NEW" | awk '{print $1}')
test "$ACTUAL" = "$EXPECTED"

CURRENT=$(sha256sum "$BIN" | awk '{print $1}')
BAK="${BIN}.${CURRENT:0:8}.bak"
cp -a "$BIN" "$BAK"
# Never overwrite the running inode in place.
mv -f "$NEW" "$BIN"
test "$(sha256sum "$BIN" | awk '{print $1}')" = "$EXPECTED"

rollback() {
  echo "DEPLOY_FAIL restoring $BAK" >&2
  cp -a "$BAK" "$NEW"
  chmod 0755 "$NEW"
  file "$NEW" | grep -q "ARM aarch64"
  mv -f "$NEW" "$BIN"
  systemctl restart "$UNIT"
}

systemctl restart "$UNIT"
sleep 2
systemctl is-active --quiet "$UNIT" || { rollback; exit 1; }

# Persist may already be Healthy. recon_cleared is sufficient but not
# required. Judge the last housekeeping_ok / heartbeat only. Early
# preflight Ambiguous is ok. Do not force Healthy. Do not edit persist.
ok=0
for _ in $(seq 1 24); do
  journal=$(journalctl -u "$UNIT" --since "120 seconds ago" --no-pager -o cat || true)
  last_hk=$(echo "$journal" | grep "momento housekeeping_ok " | tail -n 1 || true)
  last_hb=$(echo "$journal" | grep "momento heartbeat " | tail -n 1 || true)
  if echo "$last_hk" | grep -q "recon=Healthy" \
    && echo "$last_hk" | grep -q "order_submission=enabled" \
    && echo "$last_hk" | grep -q "unknown=false"; then
    ok=1
    break
  fi
  if echo "$last_hb" | grep -q "reconciliation=healthy" \
    && echo "$last_hb" | grep -q "order_submission=enabled" \
    && echo "$last_hb" | grep -q "unknown_orders=0"; then
    ok=1
    break
  fi
  sleep 5
done

INSTALLED=$(sha256sum "$BIN" | awk '{print $1}')
if [[ "$ok" != 1 || "$INSTALLED" != "$EXPECTED" ]]; then
  rollback
  echo "trading stays disabled; persist was not edited" >&2
  exit 1
fi

echo DEPLOY_OK sha="$INSTALLED" backup="$BAK"
echo "start != armed != submit"
