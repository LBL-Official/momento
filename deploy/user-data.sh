#!/bin/bash
# Momento M7 paper bootstrap. No Kalshi credentials. Live trading is not armed.
set -euxo pipefail
exec > >(tee /var/log/momento-bootstrap.log) 2>&1

timedatectl set-timezone UTC

if ! command -v aws >/dev/null 2>&1; then
  dnf install -y awscli || dnf install -y aws-cli
fi

id momento >/dev/null 2>&1 || useradd --system --home-dir /var/lib/momento --create-home --shell /sbin/nologin momento
mkdir -p /var/lib/momento/config /var/lib/momento/state

BUCKET="momento-paper-artifacts-895492487332"
PREFIX="s3://${BUCKET}/m7"

ok=0
for _ in $(seq 1 40); do
  if aws s3 cp "${PREFIX}/momento-trading-engine" /usr/local/bin/momento-trading-engine --region us-east-1; then
    ok=1
    break
  fi
  sleep 3
done
if [ "$ok" != 1 ]; then
  echo "failed to download momento-trading-engine"
  exit 1
fi

chmod 0755 /usr/local/bin/momento-trading-engine
aws s3 cp "${PREFIX}/paper.toml" /var/lib/momento/config/paper.toml --region us-east-1
aws s3 cp "${PREFIX}/momento-paper.service" /etc/systemd/system/momento-paper.service --region us-east-1
aws s3 cp "${PREFIX}/mlb-strategy.json" /var/lib/momento/state/mlb-strategy.json --region us-east-1

chown -R momento:momento /var/lib/momento
chmod 0750 /var/lib/momento
chmod 0640 /var/lib/momento/config/paper.toml
chmod 0640 /var/lib/momento/state/mlb-strategy.json

if grep -R -I -E 'KALSHI_|kalshi.*(secret|api[_-]?key)|ENABLE_LIVE_TRADING' \
  /var/lib/momento /etc/systemd/system/momento-paper.service 2>/dev/null; then
  echo "REFUSING: unexpected live/credential pattern on host"
  exit 1
fi

systemctl daemon-reload
systemctl enable --now momento-paper.service
systemctl is-active momento-paper.service
