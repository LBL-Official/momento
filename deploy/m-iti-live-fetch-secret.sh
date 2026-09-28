#!/bin/bash
# Load Kalshi production credentials for an isolated ITI live unit.
# Must not print the secret. Must not xtrace through the fetch.
# Must not use the factory /var/lib/momento/state path.
# Does not place a synthetic order.
set -euo pipefail
set +x

INSTANCE="${MOMENTO_LIVE_INSTANCE:-}"
case "$INSTANCE" in
  mlb-001|mlb-bot-one|"")
    echo "isolated ITI live fetch refuses the factory mlb-001 instance" >&2
    exit 78
    ;;
esac

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
SECRET_ID="momento/kalshi/production"
OUT="/dev/shm/momento-kalshi-live-${INSTANCE}.json"

umask 077
TMP=$(mktemp /dev/shm/momento-kalshi-live.XXXXXX)
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query SecretString \
  --output text > "$TMP"
chown momento:momento "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$OUT"
