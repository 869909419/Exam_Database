# ExamDB：交给 Windows 版 ChatGPT/Codex 的完整迁移指南

> 使用方法：把本文件放在 `Exam_Database` 项目根目录，并与项目数据一起复制到 Windows。然后在 Windows 版 ChatGPT 桌面应用中选择 **Codex** 模式，打开项目文件夹，把本文件交给它并说：**“请严格按照这份指南完成迁移，先检查，确认安全后再执行。”**

## 一、迁移目标与当前项目快照

目标：将 ExamDB 从 macOS 完整迁移到原生 Windows 环境，并保留代码、Git 历史、SQLite 题库、Obsidian 知识库、采集数据和项目上下文。

当前项目基线：

```text
GitHub: https://github.com/869909419/Exam_Database.git
分支: feature/integrate-knowledgebase-pipeline
最低应包含提交: 5943ef0c888797fe2375f79ad44cca27e3b959f1
真实数据库: data/db/examdb.sqlite
无效路径: data/exam.db（0 字节旧文件，不得使用）
```

本指南生成时数据库校验值：

```text
SHA-256: 4bf65fcc38558abc35d306526103ff49ebaa2e668cfb5b0bd64fe007d60a2bb5
```

如果迁移前又使用过刷题、导入、采集或同步功能，数据库校验值会改变。此时应在 Mac 上重新运行：

```bash
shasum -a 256 data/db/examdb.sqlite
```

并把新值记录下来，Windows 端以最后一次记录的值为准。

## 二、在 Mac 上需要复制的内容

### 最简单的传输方式

关闭刷题服务器、Obsidian 写入操作、采集脚本和粉笔后台任务，然后通过加密移动硬盘直接复制整个：

```text
/Users/liuyigedabu/Documents/Exam_Database
```

复制整个目录可以同时保留 Git 仓库和未纳入 Git 的本地数据。请勿把整个项目压缩包上传到普通 ChatGPT 对话；应在 Windows 桌面应用中直接打开本地文件夹。

这些内容必须成功复制：

```text
Exam_Database/
├── .git/                         # Git 历史；隐藏目录
├── AGENTS.md                     # Codex 项目规则
├── WINDOWS_CHATGPT_MIGRATION.md  # 本指南
├── src/                          # Python 源码
├── tests/                        # 测试
├── docs/                         # 项目文档和交接说明
├── scripts/windows/              # Windows PowerShell 脚本
├── skills/                       # 项目内技能规则
├── vault/                        # Obsidian 知识库，约 415 MB
└── data/
    ├── db/examdb.sqlite          # 真实数据库，约 41 MB
    ├── raw/                      # 原始采集数据，约 83 MB
    └── processed/                # 处理后数据，约 41 MB
```

以下内容不需要复制，或者复制后应在 Windows 删除并重新生成：

```text
node_modules/
.venv/
__pycache__/
.pytest_cache/
.playwright-cli/
.DS_Store
```

### 密钥与登录状态

`scripts/obsidian/.env.local` 含 DeepSeek API Key。只能通过加密移动硬盘或密码管理器传输，不得上传到聊天、GitHub、网盘公开链接或截图中。

`data/auth/fenbi/storage-state.json` 相当于浏览器登录凭据。推荐不复制，在 Windows 上重新登录生成。

## 三、交给 Windows ChatGPT/Codex 的执行指令

以下内容是给 Windows 版 ChatGPT/Codex 的正式任务说明。

---

### 你的角色

你正在 Windows 原生环境中接管 ExamDB 项目。请负责完成环境迁移、数据校验和运行验证。先检查，再执行；每一步都要保留用户数据。

### 强制安全规则

1. 首先完整阅读：
   - `AGENTS.md`
   - `WINDOWS_CHATGPT_MIGRATION.md`
   - `docs/PROJECT_HANDOFF.md`
   - `docs/PROJECT_LOGIC.md`
   - `docs/ARCHITECTURE.md`
   - `docs/DATABASE.md`
   - `docs/OBSIDIAN_INTEGRATION.md`
2. `data/db/examdb.sqlite` 是唯一真实数据库。
3. 如果真实数据库已经存在，禁止运行 `examdb init`，禁止创建新数据库覆盖它。
4. 禁止删除、清空、替换或批量重写 `data/db/examdb.sqlite`、`vault/`、`data/raw/`、`data/processed/`。
5. 禁止读取后输出 API Key、Cookie、浏览器 storage state 或其他密钥内容。
6. 禁止把 `.env.local`、`data/auth/`、数据库、日志或 `vault/` 提交到 Git。
7. 数据库缺失、SHA-256 不符或完整性检查不是 `ok` 时，立即停止写入操作并向用户报告；不得用空数据库代替。
8. 不要运行 macOS 的 `.sh`、`open`、`launchctl` 或 `.plist` 自动化。Windows 使用 `scripts/windows/*.ps1`。
9. 在测试和验收完成前不要推送新提交。
10. 安装系统软件、修改 Windows 任务计划或进行其他管理员级操作前，先向用户说明并申请许可。

### 阶段 1：只读审计

先在项目根目录运行以下只读检查：

```powershell
Get-Location
git status -sb
git branch --show-current
git log --oneline --decorate -5
git remote -v

Test-Path AGENTS.md
Test-Path scripts\windows\bootstrap.ps1
Test-Path data\db\examdb.sqlite
Test-Path vault

git --version
py --version
python --version
node --version
npm --version
```

要求：

- 当前分支应为 `feature/integrate-knowledgebase-pipeline`。
- Git 历史应包含提交 `5943ef0` 或其后续提交。
- 如果项目是直接从 Mac 复制的且 `.git/` 存在，不要重新 `git init`。
- 如果工作区有修改，先列出修改，不得直接覆盖或清理。
- 如果缺少 Git、Python 3.11+ 或 Node.js LTS，报告缺失项并征得同意后安装。

完成审计后先给用户一个简短报告，再继续后面的安全步骤。

### 阶段 2：校验数据库和传输完整性

先计算 Windows 端数据库 SHA-256：

```powershell
Get-FileHash data\db\examdb.sqlite -Algorithm SHA256
```

与 Mac 迁移前最后记录的校验值比较。本指南生成时的值是：

```text
4bf65fcc38558abc35d306526103ff49ebaa2e668cfb5b0bd64fe007d60a2bb5
```

如果用户在生成指南后又使用过数据库，应以用户提供的新值为准。

用可用的 Python 运行只读完整性检查：

```powershell
py -3.11 -c "import sqlite3; c=sqlite3.connect('data/db/examdb.sqlite'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()"
```

必须得到：

```text
ok
```

同时记录以下目录是否存在及大致大小：

```powershell
Get-ChildItem vault -Recurse -File | Measure-Object -Property Length -Sum
Get-ChildItem data\raw -Recurse -File | Measure-Object -Property Length -Sum
Get-ChildItem data\processed -Recurse -File | Measure-Object -Property Length -Sum
```

不要输出这些目录中的私密文件内容。

### 阶段 3：清除不可复用缓存

在确认这些目录只是从 Mac 复制来的依赖或缓存后，可以删除并重新生成：

```text
node_modules/
.venv/
__pycache__/
.pytest_cache/
.playwright-cli/
```

不得删除 `.git/`、`vault/` 或 `data/`。

如果目录是否安全可删不明确，先询问用户。

### 阶段 4：建立 Windows 环境

确认已经安装 Python 3.11+ 和 Node.js LTS 后，在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/bootstrap.ps1
```

该脚本应完成：

- 创建 `.venv`
- 安装 ExamDB Python 项目
- 使用 `npm ci` 安装 Node 依赖
- 安装 Playwright Chromium

如果某一步失败，保留完整错误信息并诊断；不要通过初始化或删除数据库来规避环境错误。

### 阶段 5：运行验证

运行测试：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/run-tests.ps1
```

迁移前基线是：

```text
Ran 65 tests
OK
```

测试数量未来可以增加，但不应出现失败。

启动刷题服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/start-practice-server.ps1
```

验证：

```text
http://127.0.0.1:8765
http://127.0.0.1:8765/api/metadata
```

确认页面可以加载、题库元数据可以读取，并且启动过程没有创建第二个空数据库。

### 阶段 6：恢复 Obsidian 与登录能力

1. 安装 Obsidian 后，把项目中的 `vault/` 作为 vault 打开。
2. 检查笔记、附件、错题记录和模板是否存在。
3. macOS Shell Commands 中的绝对路径不能继续使用。
4. Windows 命令模板位于：

```text
skills/operate-obsidian-examdb/scripts/obsidian_commands_windows.txt
```

5. 使用以下脚本在 Windows 重新登录粉笔：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/fenbi-login.ps1
```

6. DeepSeek Key 应保存在本地 `scripts/obsidian/.env.local`，不要在聊天中显示其值。

### 阶段 7：最终验收与汇报

完成后向用户提供一份验收报告，至少包含：

```text
项目路径：
Windows 版本：
当前 Git 分支：
当前提交：
工作区是否干净：
Python 版本：
Node/npm 版本：
数据库路径：
数据库 SHA-256：
PRAGMA integrity_check：
测试结果：
刷题页面：
API metadata：
Obsidian vault：
粉笔登录：
尚未完成事项：
```

只有以下条件全部满足，才可以宣布迁移完成：

- Git 分支和提交正确。
- `data/db/examdb.sqlite` 存在。
- SHA-256 与源设备记录一致。
- `PRAGMA integrity_check` 返回 `ok`。
- `vault/`、`data/raw/` 和 `data/processed/` 已恢复。
- Python 测试全部通过。
- 刷题页面和 `/api/metadata` 可以访问。
- 密钥与登录状态未进入 Git。
- Windows PowerShell 脚本可以运行。

---

## 四、迁移完成后的第一个开发任务

迁移验收完成后，不要立刻大规模改代码。先阅读 `docs/PROJECT_HANDOFF.md` 并向用户确认下一项工作。目前已记录的候选任务包括：

1. 申论刷题页面。
2. AI 分析接口。
3. 刷题页面视觉与交互优化。

每次开发前先检查 Git 状态，修改后运行完整测试；数据库写入操作必须先确认备份和影响范围。
