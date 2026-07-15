#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

HOST="${EXAMDB_PRACTICE_HOST:-127.0.0.1}"
PORT="${EXAMDB_PRACTICE_PORT:-8765}"
URL="http://${HOST}:${PORT}"

if command -v open >/dev/null 2>&1; then
  (
    for _ in {1..40}; do
      if curl -fsS "$URL/api/metadata" >/dev/null 2>&1; then
        open -a "Google Chrome" "$URL" >/dev/null 2>&1 || open "$URL" >/dev/null 2>&1 || true
        exit 0
      fi
      sleep 0.25
    done
    open -a "Google Chrome" "$URL" >/dev/null 2>&1 || open "$URL" >/dev/null 2>&1 || true
  ) &
fi

echo "ExamDB practice UI: $URL"
PYTHONPATH=src python3 -m examdb practice serve --host "$HOST" --port "$PORT"
