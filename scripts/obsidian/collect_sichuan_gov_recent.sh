#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

SINCE="${1:-2025-06-17}"
LIMIT="${2:-}"
REFRESH="${3:-}"
PROFILE="${4:-}"
KEYWORDS="${5:-}"

CMD=(python3 -m examdb ingest articles --source sichuan-gov --since "$SINCE")
if [[ -n "$LIMIT" ]]; then
  CMD+=(--limit "$LIMIT")
fi
if [[ "$REFRESH" == "--refresh" ]]; then
  CMD+=(--refresh)
fi
if [[ -n "$PROFILE" ]]; then
  CMD+=(--profile "$PROFILE")
fi
if [[ -n "$KEYWORDS" ]]; then
  CMD+=(--keywords "$KEYWORDS")
fi

PYTHONPATH=src "${CMD[@]}"
