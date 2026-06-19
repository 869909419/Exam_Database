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

# 检查 Node 和 Playwright
if [ ! -d "node_modules/playwright" ] && ! command -v npx &>/dev/null; then
    echo "请先安装 Playwright：npm install && npm run playwright:install"
    exit 2
fi

PYTHONPATH=src python3 -m examdb auth fenbi-login --manual --headed
