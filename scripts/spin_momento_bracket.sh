#!/usr/bin/env bash
# Operator spin-up for the Momento Systems bracket.
# Restarts ROLLER :8791, ensures :5190 and :5179, then probes NBA + NCAAB query.
# Frontend must never invoke this. Does not start W9 or live trading.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/ROLLER/.venv/bin/python"
LOG_DIR="${TMPDIR:-/tmp}/momento-spin"
mkdir -p "${LOG_DIR}"

listen_pid() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
}

stop_port() {
  local port="$1"
  local pid
  pid="$(listen_pid "${port}")"
  if [[ -z "${pid}" ]]; then
    return 0
  fi
  kill "${pid}" 2>/dev/null || true
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if [[ -z "$(listen_pid "${port}")" ]]; then
      return 0
    fi
    sleep 0.2
  done
  kill -9 "${pid}" 2>/dev/null || true
}

daemon() {
  local cwd="$1"
  local log="$2"
  shift 2
  "${PYTHON}" - "${cwd}" "${log}" "$@" <<'PY'
import os
import subprocess
import sys

cwd, log, *cmd = sys.argv[1:]
os.makedirs(os.path.dirname(log) or ".", exist_ok=True)
with open(log, "ab", buffering=0) as fh:
    subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
print(f"STARTED {' '.join(cmd)}")
PY
}

wait_http() {
  local url="$1"
  local name="$2"
  local n=0
  while (( n < 80 )); do
    if curl -sf "${url}" >/dev/null; then
      echo "READY ${name} ${url}"
      return 0
    fi
    n=$((n + 1))
    sleep 0.25
  done
  echo "UNAVAILABLE ${name} ${url}" >&2
  return 1
}

if [[ ! -x "${PYTHON}" ]]; then
  echo "UNAVAILABLE ROLLER venv python at ${PYTHON}" >&2
  exit 1
fi

echo "Restarting ROLLER API :8791"
stop_port 8791
daemon "${ROOT}/ROLLER" "${LOG_DIR}/terminal_api.log" "${PYTHON}" scripts/terminal_api.py
wait_http "http://127.0.0.1:8791/health" "ROLLER"

if [[ -z "$(listen_pid 5190)" ]]; then
  echo "Starting Momento Systems :5190"
  daemon "${ROOT}/frontend/momento-systems" "${LOG_DIR}/momento-systems.log" npm run dev
else
  echo "Momento Systems :5190 already listening"
fi
wait_http "http://127.0.0.1:5190/" "bracket"

if [[ -z "$(listen_pid 5179)" ]]; then
  echo "Starting ROLLER / Jump :5179"
  daemon "${ROOT}/frontend/roller-terminal" "${LOG_DIR}/roller-terminal.log" npm run dev
else
  echo "ROLLER terminal :5179 already listening"
fi
wait_http "http://127.0.0.1:5179/" "database"

echo "Probing /momento/systems and NBA/NCAAB query"
"${PYTHON}" - <<'PY'
import json
import sys
import urllib.request

def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode())

systems = get("http://127.0.0.1:8791/momento/systems")
if systems.get("count") != 19:
    print(f"UNAVAILABLE systems count={systems.get('count')}", file=sys.stderr)
    sys.exit(1)
print(f"READY systems count={systems['count']}")

body = get("http://127.0.0.1:8791/momento/connection")
print(json.dumps({
    "connected": body.get("connected"),
    "detail": body.get("detail"),
    "nba": body.get("markets", {}).get("nba", {}),
    "ncaab": body.get("markets", {}).get("ncaab", {}),
    "research_query": {
        key: {
            "status": row.get("status"),
            "execution_path": row.get("execution_path"),
            "available": row.get("available"),
        }
        for key, row in (body.get("research_query") or {}).items()
    },
}, indent=2))
nba = (body.get("markets") or {}).get("nba") or {}
ncaab = (body.get("markets") or {}).get("ncaab") or {}
if nba.get("query") != "OK" or ncaab.get("query") != "OK":
    print("UNAVAILABLE NBA/NCAAB warehouse query", file=sys.stderr)
    sys.exit(1)
if not body.get("connected"):
    print("UNAVAILABLE connection", file=sys.stderr)
    sys.exit(1)
print("READY NBA query")
print("READY NCAAB query")
print("OPEN http://127.0.0.1:5190/")
print("DATABASE http://127.0.0.1:5179/")
print("JUMP http://127.0.0.1:5179/?app=jump")
PY
