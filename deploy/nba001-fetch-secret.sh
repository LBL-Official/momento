#!/bin/bash
# Load Kalshi production credentials for NBA Bot 001 into its own tmpfs file.
# The worker links no submission adapter; the credential signs GET requests only.
# Must not print the secret. Must not xtrace through the fetch.
# Must not write the MLB secret path.
set -euo pipefail
set +x

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
SECRET_ID="${NBA001_SECRET_ID:-momento/kalshi/production}"
OUT="${MOMENTO_KALSHI_SECRET_FILE:?nba001 fetch requires MOMENTO_KALSHI_SECRET_FILE}"
case "$OUT" in
  /dev/shm/momento-kalshi-nba-001.json) ;;
  *)
    echo "nba001 fetch refuses a shared secret path" >&2
    exit 78
    ;;
esac

umask 077
TMP=$(mktemp /dev/shm/momento-kalshi-nba-001.XXXXXX)
if ! aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query SecretString \
  --output text > "$TMP" 2>/dev/null; then
  rm -f "$TMP"
  echo "nba001 fetch: secret unavailable; worker will report RECONCILIATION_HOLD" >&2
  exit 0
fi
chmod 600 "$TMP"
mv "$TMP" "$OUT"
