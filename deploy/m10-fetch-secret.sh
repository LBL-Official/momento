#!/bin/bash
# Load Kalshi production credentials from Secrets Manager into tmpfs.
# Must not print the secret. Must not xtrace through the fetch.
# Does not place a synthetic order.
set -euo pipefail
set +x

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
SECRET_ID="momento/kalshi/production"
OUT="/dev/shm/momento-kalshi-live.json"

umask 077
TMP=$(mktemp /dev/shm/momento-kalshi.XXXXXX)
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query SecretString \
  --output text > "$TMP"
chown momento:momento "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$OUT"
