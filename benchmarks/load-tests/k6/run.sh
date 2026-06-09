#!/usr/bin/env bash
# k6 benchmark runner wrapper. Requires k6 installed locally.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCENARIO="${1:-single_request}"
SCRIPT="${ROOT}/benchmarks/load-tests/k6/scenario.js"

case "$SCENARIO" in
  single_request)   export BENCHMARK_VUS=1 BENCHMARK_ITERATIONS=1 BENCHMARK_STREAM=false ;;
  low_concurrency)  export BENCHMARK_VUS=2 BENCHMARK_ITERATIONS=2 BENCHMARK_STREAM=false ;;
  medium_concurrency) export BENCHMARK_VUS=5 BENCHMARK_ITERATIONS=5 BENCHMARK_STREAM=false ;;
  high_concurrency) export BENCHMARK_VUS=10 BENCHMARK_ITERATIONS=10 BENCHMARK_STREAM=false ;;
  streaming)        export BENCHMARK_VUS=2 BENCHMARK_ITERATIONS=2 BENCHMARK_STREAM=true ;;
  mixed)            export BENCHMARK_VUS=4 BENCHMARK_ITERATIONS=4 BENCHMARK_STREAM=false ;;
  *) echo "unknown scenario: $SCENARIO" >&2; exit 1 ;;
esac

export BENCHMARK_SCENARIO="$SCENARIO"
export BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
export BENCHMARK_API_KEY="${BENCHMARK_API_KEY:-test-key}"

if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 not installed; framework defined at ${SCRIPT}" >&2
  exit 0
fi

exec k6 run "$SCRIPT"
