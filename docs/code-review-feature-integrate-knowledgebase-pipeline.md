# Code Review and Fix Log: feature/integrate-knowledgebase-pipeline

**审查日期**: 2026-06-19
**修复日期**: 2026-06-19
**审查分支**: `feature/integrate-knowledgebase-pipeline` (vs `main`)
**原始审查范围**: 16 个文件，+566/-19 行

---

## 修复结果概览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已修复 | 14 | 已在当前工作树中修复，并补充或更新相关测试/文档 |
| ⏳ 后续设计债 | 1 | 不影响当前功能正确性，建议后续统一建模 |
| **合计** | **15** | 原始审查发现项 |

本轮同时修复了原审查补充说明中提到的 `FenbiFetchResult` dataclass 字段顺序问题。

---

## 本轮修复涉及文件

- `src/examdb/paper_sources.py`
- `scripts/playwright/fenbi_list_papers.mjs`
- `scripts/obsidian/fetch_fenbi_all.sh`
- `scripts/obsidian/discover_fenbi_papers.sh`
- `scripts/obsidian/fenbi_login.sh`
- `tests/test_db_and_papers.py`
- `docs/SOURCES.md`
- `docs/OBSIDIAN_INTEGRATION.md`
- `skills/operate-obsidian-examdb/SKILL.md`
- `skills/operate-obsidian-examdb/scripts/obsidian_commands.txt`
- `vault/自动化/Obsidian 调用脚本指南.md`（vault 被 `.gitignore` 忽略，需作为本地 Obsidian 文档保存）

---

## 验证结果

已运行并通过：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
node --check scripts/playwright/fenbi_list_papers.mjs
bash -n scripts/obsidian/fetch_fenbi_all.sh scripts/obsidian/discover_fenbi_papers.sh scripts/obsidian/fenbi_login.sh
git diff --check
```

新增回归覆盖：

- `discover_fenbi_papers()` 保留 `exerciseCount=0`，不会折叠成 `None`。
- Obsidian shell wrappers 语法有效。
- `discover_fenbi_papers.sh` 缺少 labelId 时失败。
- `fetch_fenbi_all.sh` 未知 flag 不会被当作 paperId。

---

## 问题处理明细

### 1. ✅ 已修复 - `paper_sources.py` 将真实零题量折叠为 `None`

原问题：

```python
question_count=int(item.get("exerciseCount") or 0) or None
```

`exerciseCount: 0` 会变成 `None`，无法区分真实 0 和字段缺失。

处理：

- 改为显式判空：字段存在时执行 `int(...)`，字段缺失时才是 `None`。
- 增加测试覆盖 `exerciseCount=0` 和缺失字段两个分支。

说明：

复核时发现原审查里“写入数据库”的表述偏重；当前路径主要是发现列表 listing/CLI 输出。但零值语义丢失确实成立，已修。

---

### 2. ✅ 已修复 - `fetch_fenbi_all.sh` 将 shell 变量拼进 Python 字符串

原问题：

```bash
data = json.load(open('$FROM_DISCOVER'))
```

路径中含单引号会导致 Python 语法错误，也存在本地代码注入风险。

处理：

- 改为通过 `sys.argv[1]` 传递 `--from-discover` 文件路径。
- 使用 `open(..., encoding="utf-8")` 读取 JSON。

---

### 3. ✅ 已修复 - `fenbi_list_papers.mjs` fallback 页面导航失败被静默吞掉

原问题：

```javascript
await page.goto(listUrl, { waitUntil: "domcontentloaded", timeout: timeoutMs }).catch(() => {});
```

网络错误或页面不可达时可能输出空列表并以 0 退出。

处理：

- 移除静默 `catch`。
- API 抓取失败时输出错误并尝试页面 fallback。
- API 和 fallback 都无法发现任何试卷时抛错并退出非 0。

---

### 4. ✅ 已修复 - `fenbi_list_papers.mjs` 只抓 `toPage=0`

原问题：

```javascript
const apiUrl = `.../papers?toPage=0&pageSize=${pageSize}&labelId=${labelId}`;
```

标签下试卷数量超过 `pageSize` 时会静默丢后续页面。

处理：

- 新增 API 分页循环。
- 默认最多抓 `FENBI_MAX_PAGES=20` 页，避免接口异常时无限循环。
- 当返回数量小于 `pageSize` 时停止。

---

### 5. ✅ 已修复 - `fenbi_list_papers.mjs` response 异步处理竞态

原问题：

`page.on("response", async ...)` 中读取 body 是异步的，滚动结束后可能还没处理完就消费 `captured`。

处理：

- 对匹配的 response 建立 `pendingResponses` 集合。
- fallback 滚动后再次等待 `networkidle`。
- 使用 `Promise.allSettled(...)` 等待已捕获 response 处理完成。

---

### 6. ✅ 已修复 - `fenbi_list_papers.mjs` 环境变量数字解析缺少校验

原问题：

```javascript
const networkIdleTimeout = Number(process.env.FENBI_NETWORK_IDLE_MS || 15000);
```

`FENBI_NETWORK_IDLE_MS=abc` 会得到 `NaN`。

处理：

- 新增 `parseIntegerEnv(...)`。
- 校验 `FENBI_PAGE_SIZE`、`FENBI_TIMEOUT_MS`、`FENBI_NETWORK_IDLE_MS`、`FENBI_SCROLL_DELAY_MS`、`FENBI_MAX_PAGES`。
- 非法值直接报错退出。

---

### 7. ✅ 已修复 - JS/Python 两层都无法区分题量 0 和缺失

原问题：

```javascript
exerciseCount: item.paperMeta?.exerciseCount || 0
```

以及 Python 层的 `or None` 会进一步丢失语义。

处理：

- JS 层改为 `item.paperMeta?.exerciseCount ?? null`。
- Python 层改为显式判空。
- 测试覆盖已补充。

---

### 8. ✅ 已修复 - `fetch_fenbi_all.sh` 未知 flag 被当作 paperId

原问题：

`--timeout 300` 等未知参数会落入 ID 列表。

处理：

- `*)` 分支中检测 `--*` 并报 `Unknown option`。
- 对 `--from-discover` 缺少值的情况也做了校验。
- 测试覆盖 `--timeout` 会退出 2。

---

### 9. ✅ 已修复 - `fetch_fenbi_all.sh` 未处理 CRLF 行尾

原问题：

Windows CRLF 文件中的 `\r` 会污染 paperId。

处理：

- 读取 ID 文件时执行 `line="${line//$'\r'/}"`。

---

### 10. ✅ 已修复 - `FENBI_BATCH_DELAY` 非数字导致中途崩溃

原问题：

```bash
sleep "$BATCH_DELAY"
```

`FENBI_BATCH_DELAY=abc` 会在首套抓取后才失败。

处理：

- 批量开始前校验 `FENBI_BATCH_DELAY` 必须是非负数字。
- 非法值直接退出 2。

---

### 11. ✅ 已修复 - `FENBI_HEADLESS=false` 仍被当作 headless

原问题：

```javascript
const headless = process.env.FENBI_HEADLESS !== "0";
```

处理：

- 新增 `parseHeadless(...)`。
- `0`、`false`、`no` 都表示非 headless。

---

### 12. ✅ 已修复 - `fetch_fenbi_all.sh` 默认自动 `--import`

原问题：

批量 wrapper 默认导入 SQLite 和 vault，和底层 CLI 的显式 `--import` 语义不一致。

处理：

- 默认只保存 JSON。
- 用户显式加 `--import` 时才导入 SQLite 和 vault。
- 保留 `--no-import` 兼容旧命令。
- 更新 `docs/SOURCES.md`、`docs/OBSIDIAN_INTEGRATION.md`、skill 命令说明和 vault 使用指南。

---

### 13. ✅ 已修复 - `discover_fenbi_papers.sh` 静默默认 labelId=1

原问题：

不传 labelId 时静默发现国考行测。

处理：

- 缺少第一个参数时报 usage 并退出 2。
- 测试覆盖。

---

### 14. ✅ 已修复 - `fenbi_login.sh` 硬编码 `--manual --headed`

原问题：

wrapper 只支持手动可见浏览器登录，屏蔽底层自动登录/headless 能力。

处理：

- 默认仍保持最稳的 `--manual --headed`。
- 新增 `--auto`、`--headless`、`--timeout` 参数。
- 未知参数会报错。

---

### 15. ⏳ 后续设计债 - `paper_kind` 与 `routecs` 双命名体系

原问题：

```python
script_name = "fenbi_fetch_shenlun_solution.mjs" if paper_kind == "申论" or routecs == "shenlun" else "fenbi_fetch_solution.mjs"
```

`paper_kind` 使用中文值，`routecs` 使用英文值，两个参数编码了相近概念。

处理状态：

- 本轮未做大重构，以避免扩大改动范围。
- 当前行测/申论路径行为保持不变。
- 建议后续将粉笔试卷类型统一成内部枚举，例如 `FenbiPaperKind.XINGCE` / `FenbiPaperKind.SHENLUN`，再在 CLI 边界做中英文/routecs 映射。

后续建议：

- 在 `fetch_fenbi_solution()` 入口归一化 `paper_kind` 和 `routecs`。
- 对不支持的组合显式报错，而不是静默回落到行测脚本。
- 为新增 `职测`、`综应` 等类型预留明确失败路径。

---

## 补充问题处理

### ✅ 已修复 - `FenbiFetchResult` dataclass 字段顺序

原问题：

`paper_kind` 有默认值却排在无默认值 `status` 之前，会导致 dataclass 初始化错误。

处理：

- 调整字段顺序，将 `status` 放在默认值字段前。
- `PYTHONPATH=src python3 -m compileall -q src tests` 已通过。

---

## 后续维护建议

- 若继续扩展粉笔来源，优先处理第 15 项类型建模问题。
- 若 `fenbi_list_papers.mjs` 需要真实网络回归，建议增加一个手动 smoke checklist，而不是默认 CI 访问粉笔。
- vault 内部说明笔记目前被 `.gitignore` 忽略；如果希望团队共享，需要单独调整 Git 策略或将精简版同步到 `docs/OBSIDIAN_INTEGRATION.md`。
