#!/usr/bin/env bash
set -euo pipefail
examdb ingest articles --source qstheory --since "${1:-2025-06-17}"
