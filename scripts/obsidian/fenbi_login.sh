#!/usr/bin/env bash
# ============================================================
# fenbi_login.sh — 粉笔登录 wrapper
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== 粉笔登录 ==="
echo "项目根目录: $PROJECT_ROOT"
echo ""

MANUAL_FLAG="--manual"
HEADED_FLAG="--headed"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manual)
            MANUAL_FLAG="--manual"
            shift
            ;;
        --auto)
            MANUAL_FLAG=""
            shift
            ;;
        --headed)
            HEADED_FLAG="--headed"
            shift
            ;;
        --headless)
            HEADED_FLAG=""
            shift
            ;;
        --timeout)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "Missing value for --timeout"
                exit 2
            fi
            EXTRA_ARGS+=("--timeout" "$2")
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--manual|--auto] [--headed|--headless] [--timeout seconds]"
            exit 2
            ;;
    esac
done

# 检查 Node 和 Playwright
if [ ! -d "node_modules/playwright" ] && ! command -v npx &>/dev/null; then
    echo "请先安装 Playwright：npm install && npm run playwright:install"
    exit 2
fi

CMD=(python3 -m examdb auth fenbi-login)
[ -n "$MANUAL_FLAG" ] && CMD+=("$MANUAL_FLAG")
[ -n "$HEADED_FLAG" ] && CMD+=("$HEADED_FLAG")
CMD+=("${EXTRA_ARGS[@]}")

PYTHONPATH=src "${CMD[@]}"
