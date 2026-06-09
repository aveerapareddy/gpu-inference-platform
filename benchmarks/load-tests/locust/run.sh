#!/usr/bin/env bash
# Locust benchmark runner wrapper. Requires locust installed locally.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCUSTFILE="${ROOT}/benchmarks/load-tests/locust/locustfile.py"
HOST="${BASE_URL:-http://127.0.0.1:8080}"

if ! command -v locust >/dev/null 2>&1; then
  echo "locust not installed; framework defined at ${LOCUSTFILE}" >&2
  exit 0
fi

exec locust -f "$LOCUSTFILE" --host "$HOST" "$@"
