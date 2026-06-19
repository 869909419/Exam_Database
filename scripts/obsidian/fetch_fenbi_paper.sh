#!/usr/bin/env bash
# ============================================================
# fetch_fenbi_paper.sh — 抓取单套粉笔试卷
# ============================================================
# Usage:
#   scripts/obsidian/fetch_fenbi_paper.sh 222388             # 行测
#   scripts/obsidian/fetch_fenbi_paper.sh 222388 --shenlun   # 申论
#   scripts/obsidian/fetch_fenbi_paper.sh 222388 --import    # 抓取并导入
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <paper-id> [--shenlun] [--import] [--headed]"
    exit 2
fi

PAPER_ID="$1"
shift

echo "=== 抓取粉笔试卷 ==="
echo "paperId: $PAPER_ID"
echo ""

PYTHONPATH=src python3 -m examdb fetch fenbi-solution \
    --paper-id "$PAPER_ID" \
    "$@"
