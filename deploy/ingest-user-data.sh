#!/bin/bash
# DATA-INGEST host bootstrap. No Kalshi credentials. Live trading is not armed.
set -euxo pipefail
exec > >(tee /var/log/momento-ingest-bootstrap.log) 2>&1

timedatectl set-timezone UTC
dnf install -y awscli gcc git tar gzip || dnf install -y aws-cli gcc git tar gzip

if [[ ! -f /swapfile ]]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 0600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

id momento >/dev/null 2>&1 || useradd --system --home-dir /var/lib/momento --create-home --shell /sbin/nologin momento
mkdir -p /var/lib/momento/ingest /var/lib/momento/cloud-lake /opt/momento-src

BUCKET="__INGEST_BUCKET__"
REGION="us-east-1"
PREFIX="s3://${BUCKET}/bootstrap"

ok=0
for _ in $(seq 1 40); do
  if aws s3 cp "${PREFIX}/momento-ingest-src.tar.gz" /tmp/momento-ingest-src.tar.gz --region "$REGION"; then
    ok=1
    break
  fi
  sleep 5
done
if [[ "$ok" != 1 ]]; then
  echo "failed to download ingest source"
  exit 1
fi

tar -xzf /tmp/momento-ingest-src.tar.gz -C /opt/momento-src --strip-components=1
chown -R momento:momento /opt/momento-src /var/lib/momento

if [[ ! -x /usr/local/bin/momento-research-ingest ]]; then
  su -s /bin/bash momento -c 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.85.0'
  su -s /bin/bash momento -c 'source /var/lib/momento/.cargo/env && cd /opt/momento-src && cargo build -p momento-research-ingest-app --release'
  cp /opt/momento-src/target/release/momento-research-ingest /usr/local/bin/momento-research-ingest
  chmod 0755 /usr/local/bin/momento-research-ingest
fi

aws s3 cp "${PREFIX}/momento-ingest-weekly.sh" /usr/local/bin/momento-ingest-weekly.sh --region "$REGION"
aws s3 cp "${PREFIX}/momento-research-ingest.service" /etc/systemd/system/momento-research-ingest.service --region "$REGION"
chmod 0755 /usr/local/bin/momento-ingest-weekly.sh

cat >/etc/momento-ingest.env <<EOF
MOMENTO_INGEST_BUCKET=${BUCKET}
AWS_REGION=${REGION}
MOMENTO_INGEST_CLOUD_STATUS=DEPLOYED
MOMENTO_INGEST_KEEP_ALIVE=0
EOF
chmod 0640 /etc/momento-ingest.env
mkdir -p /etc/systemd/system/momento-research-ingest.service.d
cat >/etc/systemd/system/momento-research-ingest.service.d/override.conf <<EOF
[Service]
EnvironmentFile=/etc/momento-ingest.env
EOF

if grep -R -I -E 'ENABLE_LIVE_TRADING|KALSHI_API_KEY|kalshi.*(secret|private)' \
  /var/lib/momento /etc/systemd/system/momento-research-ingest.service /usr/local/bin/momento-ingest-weekly.sh 2>/dev/null; then
  echo "REFUSING: unexpected live/credential pattern on ingest host"
  exit 1
fi

systemctl daemon-reload
systemctl enable momento-research-ingest.service
echo "bootstrap complete; weekly unit enabled (EventBridge starts the instance)"
