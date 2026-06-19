#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

FILTER="${1:-}"
if [[ -n "$FILTER" ]]; then
  PYTHONPATH=src python3 -m examdb practice start --filter "$FILTER"
else
  PYTHONPATH=src python3 -m examdb practice start
fi
