#!/bin/bash
# Load Kalshi *demo* credentials from Secrets Manager into tmpfs.
# Must not print the secret. Must not xtrace through the fetch.
# Must not fetch momento/kalshi/production.
# Does not place a synthetic order.
set -euo pipefail
set +x

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
SECRET_ID="${JUMP_BOT_DEMO_SECRET_ID:-momento/kalshi/demo}"
OUT="${MOMENTO_KALSHI_SECRET_FILE:?demo fetch requires MOMENTO_KALSHI_SECRET_FILE}"
case "$OUT" in
  /dev/shm/momento-kalshi-demo-*.json) ;;
  *)
    echo "demo fetch refuses a shared secret path" >&2
    exit 78
    ;;
esac

case "$SECRET_ID" in
  *production*|*prod*)
    echo "demo fetch refuses a production secret id" >&2
    exit 78
    ;;
esac

umask 077
TMP=$(mktemp /dev/shm/momento-kalshi-demo.XXXXXX)
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query SecretString \
  --output text > "$TMP"
chown momento:momento "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$OUT"
