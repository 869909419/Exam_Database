# Obsidian 集成说明

## 结论

Obsidian 本身不直接执行 Python CLI。第一版支持两种入口：

- 终端手动运行 `scripts/obsidian/*.sh`。
- Obsidian 社区插件 Shell commands -> 本仓库 shell wrapper -> `examdb` CLI。

这样做的好处：

- 不需要开发 Obsidian 插件。
- 所有逻辑仍在 Python CLI 和 skill 中，便于测试和复用。
- 后续可以把同一组脚本接到快捷键、侧边栏按钮、Commander 或 Buttons。

## Wrapper 脚本

脚本都在 `scripts/obsidian/`：

- `init_examdb.sh`
- `collect_qstheory_recent.sh`
- `collect_people_commentary_recent.sh`
- `collect_gov_policy_recent.sh`
- `collect_xinhua_politics_recent.sh`
- `collect_sichuan_gov_recent.sh`
- `collect_chongqing_gov_recent.sh`
- `import_inbox_papers.sh`
- `generate_weekly_report.sh`
- `list_practice_questions.sh`
- `retag_policy_articles.sh`
- `sync_policy_article_metadata.sh`
- `fenbi_login.sh`
- `discover_fenbi_papers.sh`
- `fetch_fenbi_paper.sh`
- `fetch_fenbi_all.sh`

这些脚本会自动切到项目根目录，并设置 `PYTHONPATH=src`。

## 终端手动运行

```bash
cd /Users/liuyigedabu/Documents/Exam_Database
scripts/obsidian/init_examdb.sh
scripts/obsidian/collect_qstheory_recent.sh 2025-06-17 1
scripts/obsidian/collect_people_commentary_recent.sh 2025-06-17 3
scripts/obsidian/collect_gov_policy_recent.sh 2025-06-17 3
scripts/obsidian/collect_xinhua_politics_recent.sh 2025-06-17 3
scripts/obsidian/collect_sichuan_gov_recent.sh 2025-06-17 3
scripts/obsidian/collect_chongqing_gov_recent.sh 2025-06-17 3
scripts/obsidian/import_inbox_papers.sh
scripts/obsidian/generate_weekly_report.sh
scripts/obsidian/list_practice_questions.sh
```

粉笔真题链路使用 Playwright。首次运行前，在项目根目录安装一次本地依赖：

```bash
npm install
npm run playwright:install
```

登录态保存到 `data/auth/fenbi/storage-state.json`，不要提交。

### Shell Wrapper（推荐）

```bash
scripts/obsidian/fenbi_login.sh                                   # 手动登录
scripts/obsidian/discover_fenbi_papers.sh 1 xingce               # 发现国考行测
scripts/obsidian/discover_fenbi_papers.sh 26 shenlun             # 发现四川省考申论
scripts/obsidian/fetch_fenbi_paper.sh 222388 --import            # 单套行测
scripts/obsidian/fetch_fenbi_paper.sh 222388 --shenlun --import  # 单套申论
scripts/obsidian/fetch_fenbi_all.sh data/paper_ids/guokao_ids.txt  # 批量抓取
scripts/obsidian/fetch_fenbi_all.sh --from-discover data/raw/papers/fenbi/paper-list/xingce-1.json
```

labelId 参考表见 `data/paper_ids/label_ids.md`。

### 底层 CLI（同样可用）

遇到验证码或短信验证时，用可见浏览器手动登录：

```bash
PYTHONPATH=src python3 -m examdb auth fenbi-login --manual --headed
```

发现粉笔行测套卷：

```bash
PYTHONPATH=src python3 -m examdb discover fenbi-papers --label-id 1 --paper-kind xingce
```

发现粉笔申论套卷：

```bash
PYTHONPATH=src python3 -m examdb discover fenbi-papers --label-id 1 --paper-kind shenlun
```

抓取并导入行测解析：

```bash
PYTHONPATH=src python3 -m examdb fetch fenbi-solution \
  --paper-id 222388 \
  --expected-question-count 135 \
  --expected-sections 常识判断,言语理解与表达,数量关系,判断推理,资料分析 \
  --strict \
  --import
```

抓取并导入申论解析：

```bash
PYTHONPATH=src python3 -m examdb fetch fenbi-solution \
  --paper-id 222388 \
  --shenlun \
  --import
```

DeepSeek key 可以写入脚本旁的私有配置文件。先复制模板：

```bash
cp scripts/obsidian/.env.local.example scripts/obsidian/.env.local
```

然后编辑 `scripts/obsidian/.env.local`：

```bash
DEEPSEEK_API_KEY="你的_key"
```

真实 `.env.local` 已被 `.gitignore` 忽略，不要提交。配置后可以直接预览文章 tags/topics 修正，不写入文件：

```bash
scripts/obsidian/retag_policy_articles.sh
```

确认预览结果后写入 Markdown frontmatter 和 SQLite：

```bash
scripts/obsidian/retag_policy_articles.sh --apply
```

限定来源和数量：

```bash
scripts/obsidian/retag_policy_articles.sh --source gov-policy --limit 10 --apply
```

例如预览求是网 30 篇：

```bash
scripts/obsidian/retag_policy_articles.sh --source qstheory --limit 30
```

确认后写入：

```bash
scripts/obsidian/retag_policy_articles.sh --source qstheory --limit 30 --apply
```

注意参数必须带名字，例如使用 `--source qstheory --limit 30`，不要写成 `qstheory 30`。

如果只想处理 Markdown 与 SQLite 不一致、包含 `待复核` 或非法 tags 的文章：

```bash
scripts/obsidian/retag_policy_articles.sh --only-needs-review --apply
```

也可以不用 `.env.local`，运行时临时覆盖：

```bash
DEEPSEEK_API_KEY="你的_key" scripts/obsidian/retag_policy_articles.sh --apply
```

两种方式可以同时存在；命令前临时传入的 `DEEPSEEK_API_KEY` 优先级更高，未传入时才读取 `scripts/obsidian/.env.local`。

手动修改 Markdown frontmatter 后，可以预览 SQLite 将如何被覆盖：

```bash
scripts/obsidian/sync_policy_article_metadata.sh --source qstheory --limit 30 --only-changed
```

确认后写入 SQLite：

```bash
scripts/obsidian/sync_policy_article_metadata.sh --source qstheory --limit 30 --only-changed --apply
```

同步单篇文章：

```bash
scripts/obsidian/sync_policy_article_metadata.sh --path "vault/资料库/政策理论/gov-policy/2026/06-17/国务院关于印发《实施就业优先战略“十五五”规划》的通知.md" --apply
```

采集脚本默认会跳过 SQLite 中已经存在的 URL。需要强制重新下载并覆盖旧 Markdown 时，在第三个参数传入 `--refresh`：

```bash
scripts/obsidian/collect_qstheory_recent.sh 2025-06-17 5 --refresh
scripts/obsidian/collect_people_commentary_recent.sh 2025-06-17 5 --refresh
scripts/obsidian/collect_gov_policy_recent.sh 2025-06-17 5 --refresh
scripts/obsidian/collect_xinhua_politics_recent.sh 2025-06-17 5 --refresh
scripts/obsidian/collect_sichuan_gov_recent.sh 2025-06-17 5 --refresh
scripts/obsidian/collect_chongqing_gov_recent.sh 2025-06-17 5 --refresh
```

如果脚本没有执行权限：

```bash
chmod +x scripts/obsidian/*.sh
```

底层 CLI 也可以直接运行：

```bash
PYTHONPATH=src python3 -m examdb ingest articles --source qstheory --since 2025-06-17 --limit 1
PYTHONPATH=src python3 -m examdb ingest articles --source people-commentary --since 2025-06-17 --limit 3
PYTHONPATH=src python3 -m examdb ingest articles --source gov-policy --since 2025-06-17 --limit 3
PYTHONPATH=src python3 -m examdb ingest articles --source xinhua-politics --since 2025-06-17 --limit 3
PYTHONPATH=src python3 -m examdb ingest articles --source sichuan-gov --since 2025-06-17 --limit 3
PYTHONPATH=src python3 -m examdb ingest articles --source chongqing-gov --since 2025-06-17 --limit 3
```

粉笔真题底层 CLI：

```bash
PYTHONPATH=src python3 -m examdb auth fenbi-login --manual --headed
PYTHONPATH=src python3 -m examdb discover fenbi-papers --label-id 1 --paper-kind xingce
PYTHONPATH=src python3 -m examdb discover fenbi-papers --label-id 1 --paper-kind shenlun
PYTHONPATH=src python3 -m examdb fetch fenbi-solution --paper-id 222388 --import
PYTHONPATH=src python3 -m examdb fetch fenbi-solution --paper-id 222388 --shenlun --import
```

DeepSeek retag 的底层 CLI：

```bash
DEEPSEEK_API_KEY="你的_key" PYTHONPATH=src python3 -m examdb retag articles --source gov-policy --limit 10 --apply
```

不要把 `DEEPSEEK_API_KEY` 写入正式脚本、vault 笔记或 Obsidian 插件配置；需要落盘时只写入 `scripts/obsidian/.env.local`。

默认去重逻辑是先按 URL 查 SQLite，已存在则跳过下载；需要刷新旧文章时加 `--refresh`：

```bash
PYTHONPATH=src python3 -m examdb ingest articles --source people-commentary --since 2025-06-17 --limit 3 --refresh
```

## Obsidian 内部笔记

Vault 中已加入说明笔记：

- `vault/自动化/Obsidian 调用脚本指南.md`

建议把它作为自动化首页，里面列出了可复制到 Shell commands 插件的命令。

## Skill 整合

新增 `operate-obsidian-examdb` skill，负责：

- 判断用户想在 Obsidian 里触发哪类流程。
- 调用 `scripts/obsidian/` 中的 wrapper。
- 检查输出文件是否进入正确 vault 目录。
- 必要时转交专项 skill：`collect-policy-materials`、`import-exam-papers`、`classify-exam-questions`、`analyze-practice-results`。
