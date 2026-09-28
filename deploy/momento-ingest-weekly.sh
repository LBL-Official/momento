#!/bin/bash
# Weekly DATA-INGEST. Does not arm live trading. Does not write Data-Real.
set -euo pipefail

BUCKET="${MOMENTO_INGEST_BUCKET:?MOMENTO_INGEST_BUCKET required}"
REGION="${AWS_REGION:-us-east-1}"
OUT="${MOMENTO_INGEST_OUT:-/var/lib/momento/ingest}"
LAKE="${MOMENTO_INGEST_LAKE:-/var/lib/momento/cloud-lake}"

mkdir -p "$OUT" "$LAKE"
aws s3 sync "s3://${BUCKET}/state/" "$OUT/" --region "$REGION" || true

/usr/local/bin/momento-research-ingest weekly \
  --authorize-network ENABLE_RESEARCH_INGEST_NETWORK \
  --invoke-w2 \
  --out "$OUT" \
  --lake "$LAKE"

aws s3 sync "$OUT/" "s3://${BUCKET}/state/" --region "$REGION"

if [[ "${MOMENTO_INGEST_KEEP_ALIVE:-0}" != "1" ]]; then
  shutdown -h now
fi
