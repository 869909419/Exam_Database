#!/usr/bin/env bash
# ============================================================
# fetch_fenbi_all.sh — 批量拉取粉笔试卷
# ============================================================
# Usage:
#   # 从文件读取 paperId 列表，逐个抓取
#   scripts/obsidian/fetch_fenbi_all.sh data/paper_ids/guokao_ids.txt
#
#   # 申论批量
#   scripts/obsidian/fetch_fenbi_all.sh --shenlun data/paper_ids/guokao_shenlun_ids.txt
#
#   # 直接传入多个 paperId
#   scripts/obsidian/fetch_fenbi_all.sh 222388 222389 222390
#
#   # 抓取后导入 SQLite 和 vault
#   scripts/obsidian/fetch_fenbi_all.sh --import data/paper_ids/guokao_ids.txt
#
#   # 从 discover 输出的 JSON 列表抓取
#   scripts/obsidian/fetch_fenbi_all.sh --from-discover data/raw/papers/fenbi/paper-list/xingce-1.json
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ── parse flags ──
SHENLUN_FLAG=""
HEADED_FLAG=""
IMPORT_FLAG=""
FROM_DISCOVER=""
IDS_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --shenlun)
            SHENLUN_FLAG="--shenlun"
            shift
            ;;
        --headed)
            HEADED_FLAG="--headed"
            shift
            ;;
        --import)
            IMPORT_FLAG="--import"
            shift
            ;;
        --no-import)
            IMPORT_FLAG=""
            shift
            ;;
        --from-discover)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "Missing value for --from-discover"
                exit 2
            fi
            FROM_DISCOVER="$2"
            shift 2
            ;;
        *)
            if [[ "$1" == --* ]]; then
                echo "Unknown option: $1"
                exit 2
            fi
            IDS_ARGS+=("$1")
            shift
            ;;
    esac
done

# ── collect IDs ──
IDS=()

if [ -n "$FROM_DISCOVER" ]; then
    # Read from JSON discover output
    if [ ! -f "$FROM_DISCOVER" ]; then
        echo "Discover file not found: $FROM_DISCOVER"
        exit 2
    fi
    while IFS= read -r id; do
        [ -n "$id" ] && IDS+=("$id")
    done < <(python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
for p in data.get("papers", []):
    print(p.get("paperId", ""))
' "$FROM_DISCOVER")
elif [ ${#IDS_ARGS[@]} -gt 0 ] && [ -f "${IDS_ARGS[0]}" ]; then
    # Read from plain text file
    while IFS= read -r line; do
        line="${line//$'\r'/}"
        line="${line%%#*}"
        line="${line// /}"
        [ -n "$line" ] && IDS+=("$line")
    done < "${IDS_ARGS[0]}"
else
    IDS=("${IDS_ARGS[@]}")
fi

if [ ${#IDS[@]} -eq 0 ]; then
    echo "Usage: $0 [--shenlun] [--headed] [--from-discover <json>] <ids.txt|paper_id1 paper_id2...>"
    echo ""
    echo "Examples:"
    echo "  $0 data/paper_ids/guokao_ids.txt"
    echo "  $0 --shenlun data/paper_ids/guokao_shenlun_ids.txt"
    echo "  $0 --import data/paper_ids/guokao_ids.txt"
    echo "  $0 --from-discover data/raw/papers/fenbi/paper-list/xingce-1.json"
    echo "  $0 222388 222389"
    exit 1
fi

# ── check auth ──
AUTH_STATE="data/auth/fenbi/storage-state.json"
if [ ! -f "$AUTH_STATE" ]; then
    echo "未找到登录态。请先登录："
    echo "  scripts/obsidian/fenbi_login.sh"
    exit 2
fi

# ── batch fetch ──
TOTAL=${#IDS[@]}
SUCCESS=0
FAILED=0
BATCH_DELAY="${FENBI_BATCH_DELAY:-10}"
if [[ ! "$BATCH_DELAY" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "FENBI_BATCH_DELAY must be a non-negative number, got: $BATCH_DELAY"
    exit 2
fi

echo "============================================"
echo "粉笔批量抓取 — $TOTAL 套"
echo "============================================"
echo ""

for i in "${!IDS[@]}"; do
    pid="${IDS[$i]}"
    idx=$((i + 1))
    echo "[$idx/$TOTAL] 正在抓取 paper $pid..."

    CMD=(python3 -m examdb fetch fenbi-solution --paper-id "$pid")
    [ -n "$SHENLUN_FLAG" ] && CMD+=("$SHENLUN_FLAG")
    [ -n "$HEADED_FLAG" ] && CMD+=("$HEADED_FLAG")
    [ -n "$IMPORT_FLAG" ] && CMD+=("$IMPORT_FLAG")

    if PYTHONPATH=src "${CMD[@]}"; then
        SUCCESS=$((SUCCESS + 1))
        echo "  ✓ 完成"
    else
        FAILED=$((FAILED + 1))
        echo "  ✗ 失败"
    fi

    if [ "$idx" -lt "$TOTAL" ]; then
        echo "  等待 ${BATCH_DELAY}s..."
        sleep "$BATCH_DELAY"
    fi
    echo ""
done

echo "============================================"
echo "批量完成：成功 $SUCCESS，失败 $FAILED（共 $TOTAL）"
echo "============================================"

[ "$FAILED" -eq 0 ] && exit 0 || exit 1
