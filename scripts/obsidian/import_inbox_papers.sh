#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INBOX="$PROJECT_ROOT/vault/待导入/真题"
ARCHIVE="$INBOX/已导入"

cd "$PROJECT_ROOT"
mkdir -p "$ARCHIVE"

shopt -s nullglob
files=("$INBOX"/*.md "$INBOX"/*.txt "$INBOX"/*.pdf)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No papers found in $INBOX"
  exit 0
fi

for file in "${files[@]}"; do
  echo "Importing $file"
  PYTHONPATH=src python3 -m examdb import paper --file "$file"
  mv "$file" "$ARCHIVE/$(basename "$file")"
done
