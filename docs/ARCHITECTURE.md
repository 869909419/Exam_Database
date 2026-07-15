# 技术架构

## 目录

- `vault/`：Obsidian vault，所有最终可读笔记都写入这里。
- `data/raw/`：原始网页、PDF、文本提取结果。
- `data/processed/`：清洗后的中间 Markdown 或文本。
- `data/db/examdb.sqlite`：默认 SQLite 数据库。
- `src/examdb/`：Python CLI 与核心逻辑。
- `skills/`：项目随附的 Claude Code/类似 agent skill。
- `docs/`：项目设计、来源、分类、技能规范。

## CLI

首版 CLI 使用标准库 `argparse`，避免依赖安装阻塞。

```bash
examdb init
examdb ingest articles --source qstheory --since 2025-06-17
examdb verify fenbi-login
examdb discover papers --source fenbi --query "https://example.com/papers.html"
examdb download papers --source fenbi
examdb import paper --file path/to/paper.pdf
examdb import fenbi-solution --file data/raw/papers/fenbi/<paper-id>/solution.json --paper-kind 行测
examdb enrich explanations --paper-id paper-id --source fenbi
examdb classify questions --paper-id paper-id --apply
examdb review papers --status needs_review
examdb practice start --filter "国考 言语理解"
examdb report weekly
examdb analyze politics-sources --years 2025,2026 --paper-kind 行测 --knowledge-point 政治理论
```

## SQLite

SQLite 保存稳定结构：

- `articles`：政策理论文章索引。
- `paper_candidates`：候选真题套卷、下载状态、阻塞原因和本地 PDF 路径。
- `exam_papers`：套卷来源、地区、年份、导入状态。
- `questions`：题干、选项、答案、解析、题型、知识点。
- `question_sources`：每题外部答案解析来源、匹配置信度和抓取状态。
- `practice_attempts`：作答、正确性、耗时、信心、备注。

Markdown frontmatter 和 SQLite 字段保持同名优先，便于 Dataview 和脚本互通。

## Source Adapter

每个来源实现相同接口：

- `list_article_urls(since, limit)`：列出候选文章 URL。
- `fetch_article_html(url)`：读取原始 HTML。
- `parse_article_html(html, url)`：输出 `ArticleRecord`。

当前已实现 `qstheory`、`qstheory-web`、`people-commentary`、`gov-policy`、`xinhua-politics`、`sichuan-gov`、`chongqing-gov`、`neac-gov`、`most-gov`、`mohrss-gov`、`ccdi-gov` 和 `stats-gov`。其他来源先登记为 placeholder，按 `docs/SOURCE_ROADMAP.md` 逐个实现 adapter。

当前登记的 source id：

- `qstheory`
- `qstheory-web`
- `people-commentary`
- `gov`（兼容旧命令，等同 `gov-policy`）
- `gov-policy`
- `xinhua-politics`
- `stats-gov`
- `people-daily`
- `gmw-theory`
- `sichuan-gov`
- `chongqing-gov`
- `neac-gov`
- `most-gov`
- `mohrss-gov`
- `ccdi-gov`

`qstheory` 的特殊规则：

- 年度目录和期刊目录只用于发现正文，不作为文章入库。
- 文章优先按期数归档：`qstheory/YYYY/YYYY年第N期/title.md`。
- 正文图片保存在同一期文件夹下的 `附件/title/`。
- 非期刊来源默认按发布日期归档：`source/YYYY/MM-DD/title.md`。

`qstheory-web` 的特殊规则：

- 只扫描求是网主站和重点栏目，不主动展开 `/qs/` 读刊目录。
- 与读刊 adapter 重复的正刊文章依靠 SQLite 的 `url/content_hash` 去重。
- 推荐搭配 `--profile politics-theory`，把主站广谱文章收敛为备考材料。

`people-commentary` 使用非期刊日期归档，并复用正文图片本地化、SQLite upsert、Markdown frontmatter 输出流程。

`gov-policy` 使用中国政府网公开 JSON 数据源发现最新政策和政策解读文章，正文优先从 `UCAP-CONTENT` 提取，使用非期刊日期归档，并复用图片本地化与 SQLite 去重流程。`gov` 是 `gov-policy` 的兼容别名。

`xinhua-politics` 从新华网时政频道发现公开文章，限制 URL 为 `www.news.cn/politics/YYYYMMDD/.../c.html`，正文优先从 `detailContent` 提取。

`sichuan-gov` 和 `chongqing-gov` 复用地方政府 adapter 基类，从政府首页、政策文件和政策解读栏目发现文章，正文优先从政府站点常见正文容器提取，必要时用页面元数据兜底。

`neac-gov`、`most-gov`、`mohrss-gov`、`ccdi-gov` 和 `stats-gov` 复用官方站 adapter 基类，服务政治理论高频来源画像中的民族、科技、就业、自我革命和统计数据主题。

`examdb ingest articles` 支持 `--profile politics-theory` 和 `--keywords`，用于按备考画像收集同类新材料，而不是只定位已考原文。

`examdb analyze politics-sources` 从已导入题目中抽取来源证据，可用于校准采集画像；加 `--apply` 后写入 `question_sources`，不覆盖原题解析。

## AI 调用

AI 是可选增强，不是采集流程的单点依赖。

- 没有 `DEEPSEEK_API_KEY` 时，系统使用规则标签和占位分析。
- 有 key 时，后续可通过 OpenAI-compatible Chat Completions 调用 DeepSeek。
- AI 输出必须经过字段校验后才能写入 SQLite。
- `examdb retag articles` 是主动修正命令；未临时传入 `DEEPSEEK_API_KEY` 时会安全退出，不写入 Markdown 或 SQLite。

## Obsidian 集成

第一阶段不开发插件。通过以下方式集成：

- 目录结构和 Markdown frontmatter。
- 模板文件。
- Dataview 查询笔记。
- CLI 和 skill 作为外部自动化入口。
