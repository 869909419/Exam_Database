#!/usr/bin/env bash
# ============================================================
# discover_fenbi_papers.sh — 发现粉笔套卷列表
# ============================================================
# Usage:
#   scripts/obsidian/discover_fenbi_papers.sh 1 xingce     # 国考行测
#   scripts/obsidian/discover_fenbi_papers.sh 1 shenlun     # 国考申论
#   scripts/obsidian/discover_fenbi_papers.sh 26 xingce    # 四川省考行测
#   scripts/obsidian/discover_fenbi_papers.sh 126 shenlun  # 四川省考申论
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <label-id> [xingce|shenlun]"
    echo ""
    echo "行测 labelId 参考："
    echo "  1=国考  26=四川  32=重庆  (详见 data/paper_ids/label_ids.md)"
    echo "申论 labelId = 行测 labelId + 100"
    exit 2
fi

LABEL_ID="$1"
PAPER_KIND="${2:-xingce}"

if [ "$PAPER_KIND" != "xingce" ] && [ "$PAPER_KIND" != "shenlun" ]; then
    echo "Usage: $0 <label-id> [xingce|shenlun]"
    echo ""
    echo "行测 labelId 参考："
    echo "  1=国考  26=四川  32=重庆  (详见 data/paper_ids/label_ids.md)"
    echo "申论 labelId = 行测 labelId + 100"
    exit 2
fi

echo "=== 发现粉笔套卷 ==="
echo "labelId: $LABEL_ID  paperKind: $PAPER_KIND"
echo ""

PYTHONPATH=src python3 -m examdb discover fenbi-papers \
    --label-id "$LABEL_ID" \
    --paper-kind "$PAPER_KIND"
