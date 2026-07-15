#!/usr/bin/env bash
# ============================================================
# fetch_fenbi_daemon.sh — 后台自主抓取粉笔真题入库
# ============================================================
# 功能：
#   1. 按 label 发现新卷 → 过滤已入库 → 逐个抓取+导入
#   2. 多层随机延迟 + 长间隔防锁号
#   3. 所有标签订阅无新卷时自动退出
#
# 用法：
#   scripts/obsidian/fetch_fenbi_daemon.sh
#
#   caffeinate -i scripts/obsidian/fetch_fenbi_daemon.sh   # 防休眠
#
# 环境变量覆盖（均有保守默认值）：
#   LABEL_IDS       — 空格分隔 labelId（默认: 1 26 32 → 国考/四川/重庆）
#   PAPER_KINDS     — xingce shenlun
#   BATCH_DELAY     — 每卷基础延迟秒数（默认: 60）
#   BATCH_JITTER    — 额外随机上限（默认: 40，即每卷间隔 60~100s）
#   MAX_PER_LABEL   — 每 label 每轮最多（默认: 8）
#   PAUSE_LABELS    — label 间暂停秒数（默认: 300 → 5min）
#   INTERVAL_HOURS  — 循环间隔小时（默认: 2）
#   YEAR_FROM       — 只抓此年份之后（默认: 2019）
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ── 配置 ──
: "${LABEL_IDS:=1 26 32}"
: "${PAPER_KINDS:=xingce shenlun}"
: "${BATCH_DELAY:=60}"
: "${BATCH_JITTER:=40}"
: "${MAX_PER_LABEL:=8}"
: "${PAUSE_LABELS:=300}"
: "${INTERVAL_HOURS:=2}"
: "${YEAR_FROM:=2019}"
: "${LOG_FILE:=data/fetch_daemon.log}"
LOG_FILE="${LOG_FILE}"  # expand relative path

AUTH_STATE="data/auth/fenbi/storage-state.json"
LOCK_FILE="/tmp/fetch_fenbi_daemon.lock"
_STOP_REQUESTED=0
mkdir -p "$(dirname "$LOG_FILE")"

# ── 工具 ──
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

rnd_delay() {
    python3 -c "import random; print(${1:-$BATCH_DELAY} + random.randint(0, ${2:-$BATCH_JITTER}))"
}

cleanup() {
    _STOP_REQUESTED=1
    log "⏹ 收到终止信号，等待当前操作完成后退出..."
    rm -f "$LOCK_FILE"
}
trap cleanup SIGINT SIGTERM SIGHUP

# ── 去重：已入库名称 ──
_archived_names() {
    python3 -c "
import json, os
names = set()
for d in os.listdir('data/raw/papers/fenbi'):
    if not d.startswith('fenbi-'):
        continue
    sf = f'data/raw/papers/fenbi/{d}/solution.json'
    if not os.path.isfile(sf):
        continue
    try:
        with open(sf, encoding='utf-8') as f:
            names.add(json.load(f).get('name', ''))
    except:
        pass
for n in sorted(names):
    print(n)
"
}

# ── 单 label 发现+抓取 ──
process_label() {
    local label_id="$1"; local paper_kind="$2"; local name="$3"

    local dfile="data/raw/papers/fenbi/paper-list/${paper_kind}-${label_id}.json"
    log "  [$name/$paper_kind] 发现套卷..."

    if ! PYTHONPATH=src python3 -m examdb discover fenbi-papers \
        --label-id "$label_id" --paper-kind "$paper_kind" --page-size 50 \
        >> "$LOG_FILE" 2>&1; then
        log "  [$name/$paper_kind] ❌ 发现失败，跳过"
        return 0
    fi

    if [ ! -f "$dfile" ]; then
        log "  [$name/$paper_kind] 无发现结果"
        return 0
    fi

    # 计算待抓取列表（倒序按日期、过滤年份、去重）
    local archived_tmp
    archived_tmp="$(mktemp)"
    _archived_names > "$archived_tmp"

    local pending_tmp
    pending_tmp="$(mktemp)"
    python3 -c "
import json, sys, os

with open('$dfile', encoding='utf-8') as f:
    data = json.load(f)

with open('$archived_tmp') as f:
    archived = set(line.strip() for line in f if line.strip())

# 已抓未入库的 paper-{id} 目录
fetched = set()
for d in os.listdir('data/raw/papers/fenbi'):
    if d.startswith('paper-') and d != 'paper-list':
        if os.path.isfile(f'data/raw/papers/fenbi/{d}/solution.json'):
            fetched.add(d.replace('paper-', ''))

papers = sorted(
    [p for p in data.get('papers',[]) if p.get('paperId') and p.get('name')],
    key=lambda p: p.get('date',''), reverse=True
)

kept = 0
for p in papers:
    if p.get('date','') < '${YEAR_FROM}-01-01':
        continue
    pid = str(p['paperId'])
    if p['name'] in archived or pid in fetched:
        continue
    print(pid)
    kept += 1
    if kept >= ${MAX_PER_LABEL}:
        break
" > "$pending_tmp" 2>/dev/null

    local pending=()
    while IFS= read -r pid; do
        [ -n "$pid" ] && pending+=("$pid")
    done < "$pending_tmp"

    rm -f "$archived_tmp" "$pending_tmp"

    local pcount="${#pending[@]}"
    log "  [$name/$paper_kind] 待抓 $pcount 套"

    if [ "$pcount" -eq 0 ]; then
        return 0
    fi

    local ok=0 fail=0
    for pid in "${pending[@]}"; do
        [ "$_STOP_REQUESTED" -eq 1 ] && break

        local delay
        delay=$(rnd_delay "$BATCH_DELAY" "$BATCH_JITTER")
        log "    ▶ paper=$pid (间隔 ${delay}s)..."

        local args=(--paper-id "$pid")
        [ "$paper_kind" = "shenlun" ] && args+=(--shenlun)
        args+=(--import)  # 抓了立刻入库

        if PYTHONPATH=src python3 -m examdb fetch fenbi-solution "${args[@]}" >> "$LOG_FILE" 2>&1; then
            ok=$((ok + 1))
            log "    ✓ paper=$pid 完成"
        else
            fail=$((fail + 1))
            log "    ✗ paper=$pid 失败"
        fi

        sleep "$delay"
    done

    log "  [$name/$paper_kind] ✅$ok ✗$fail"
}

# ── 单轮 ──
run_round() {
    local round="$1"
    local total_pending=0

    log ""
    log "══════════ 第 $round 轮 ══════════"

    # 校验登录态
    if [ ! -f "$AUTH_STATE" ]; then
        log "❌ 缺少 $AUTH_STATE，请先登录"
        return 2
    fi

    for lid in $LABEL_IDS; do
        [ "$_STOP_REQUESTED" -eq 1 ] && break
        local lname="$lid"
        case "$lid" in 1) lname="国考";; 26) lname="四川";; 32) lname="重庆";; esac

        for pk in $PAPER_KINDS; do
            [ "$_STOP_REQUESTED" -eq 1 ] && break
            local elid="$lid"
            [ "$pk" = "shenlun" ] && elid=$((lid + 100))

            process_label "$elid" "$pk" "$lname"

            # label 之间长间隔
            log "  ⏳ label 间暂停 ${PAUSE_LABELS}s..."
            sleep "$PAUSE_LABELS"
        done
    done

    log "══════════ 第 $round 轮结束 ══════════"
}

# ── 判断是否还有待抓 ──
pending_total() {
    python3 -c "
import json, os

archived = set()
for d in os.listdir('data/raw/papers/fenbi'):
    if not d.startswith('fenbi-'):
        continue
    sf = f'data/raw/papers/fenbi/{d}/solution.json'
    if not os.path.isfile(sf):
        continue
    try:
        with open(sf, encoding='utf-8') as f:
            archived.add(json.load(f).get('name', ''))
    except:
        pass

fetched = set()
for d in os.listdir('data/raw/papers/fenbi'):
    if d.startswith('paper-') and d != 'paper-list':
        if os.path.isfile(f'data/raw/papers/fenbi/{d}/solution.json'):
            fetched.add(d.replace('paper-', ''))

label_map = {}
for lid_s in '${LABEL_IDS}'.split():
    lid = int(lid_s)
    for pk in '${PAPER_KINDS}'.split():
        elid = lid + 100 if pk == 'shenlun' else lid
        key = f'{elid}:{pk}'
        # 尝试读取 paper-list
        plist = f'data/raw/papers/fenbi/paper-list/{pk}-{elid}.json'
        if not os.path.isfile(plist):
            continue
        with open(plist, encoding='utf-8') as f:
            data = json.load(f)
        count = 0
        for p in data.get('papers', []):
            if not p.get('paperId') or not p.get('name'):
                continue
            if p.get('date','') < '${YEAR_FROM}-01-01':
                continue
            pid = str(p['paperId'])
            if p['name'] in archived or pid in fetched:
                continue
            count += 1
        label_map[key] = count

total = sum(label_map.values())
if total == 0:
    print('DONE')
else:
    for k, v in sorted(label_map.items()):
        if v > 0:
            print(f'  {k}: {v}')
    print(f'TOTAL: {total}')
"
}

# ── 主入口 ──

# macOS 兼容的 PID 锁（替代 flock）
if [ -f "$LOCK_FILE" ]; then
    old_pid=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "已有 daemon 在运行 (pid=$old_pid)"
        exit 1
    fi
    # 旧锁过期，清理
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"

touch "$LOG_FILE"

log "╔══════════════════════════════════╗"
log "║  粉笔后台抓取守护进程           ║"
log "╠══════════════════════════════════╣"
log "║ LABEL_IDS:     $LABEL_IDS"
log "║ PAPER_KINDS:   $PAPER_KINDS"
log "║ YEAR_FROM:     $YEAR_FROM"
log "║ 每卷间隔:      ${BATCH_DELAY}s + rand(0~${BATCH_JITTER})s"
log "║ label 间暂停:  ${PAUSE_LABELS}s"
log "║ 循环间隔:      ${INTERVAL_HOURS}h"
log "║ 每 label 上限: $MAX_PER_LABEL"
log "║ PID:           $$"
log "╚══════════════════════════════════╝"

# 先显示初始缺口
log "当前待抓取："
pending_total | while IFS= read -r line; do log "  $line"; done

round=1
while true; do
    run_round "$round"

    # 检查是否全部完成
    remaining=$(pending_total)
    log "剩余待抓："
    echo "$remaining" | while IFS= read -r line; do log "  $line"; done

    if echo "$remaining" | grep -q '^DONE$'; then
        log ""
        log "🎉 全部完成！所有标签订阅的 2019+ 卷已入库。"
        break
    fi

    # 如果收到退出信号，停止循环
    if [ "$_STOP_REQUESTED" -eq 1 ]; then
        log "收到停止信号，退出循环"
        break
    fi

    wait_sec=$((INTERVAL_HOURS * 3600))
    log ""
    log "⏳ 下一轮在 ${INTERVAL_HOURS}h 后开始..."
    log "  (可随时 Ctrl+C 安全退出)"
    sleep "$wait_sec"
    round=$((round + 1))
done

rm -f "$LOCK_FILE"
log "守护进程结束"
