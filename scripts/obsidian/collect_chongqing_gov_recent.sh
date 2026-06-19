#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

SINCE="${1:-2025-06-17}"
LIMIT="${2:-}"
REFRESH="${3:-}"

CMD=(python3 -m examdb ingest articles --source chongqing-gov --since "$SINCE")
if [[ -n "$LIMIT" ]]; then
  CMD+=(--limit "$LIMIT")
fi
if [[ "$REFRESH" == "--refresh" ]]; then
  CMD+=(--refresh)
fi

PYTHONPATH=src "${CMD[@]}"
