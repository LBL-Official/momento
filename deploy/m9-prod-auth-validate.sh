#!/bin/bash
# M9 one-shot: load Kalshi production credentials from Secrets Manager into tmpfs,
# run read-only auth validation, then delete the secret file.
# Must not print the secret. Must not xtrace through the fetch.
# Does not start live trading. Does not place orders.
set -euo pipefail
set +x

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
SECRET_ID="momento/kalshi/production"
BIN="/usr/local/bin/momento-prod-auth-validate"

if [[ ! -x "$BIN" ]]; then
  echo "missing $BIN"
  exit 1
fi

TMP=$(mktemp /dev/shm/momento-kalshi.XXXXXX)
cleanup() {
  rm -f "$TMP"
}
trap cleanup EXIT
chmod 600 "$TMP"

aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query SecretString \
  --output text > "$TMP"

export MOMENTO_KALSHI_ENV=production
export MOMENTO_KALSHI_SECRET_FILE="$TMP"
"$BIN"
