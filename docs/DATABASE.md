# 数据库架构

## 概述

SQLite 数据库位于 `data/db/examdb.sqlite`。前端 Obsidian vault 中的 Markdown 文件主要由数据库导出生成；文章元数据和刷题复盘字段支持受控的 Markdown -> SQLite 同步。

## ER 关系

```
articles (656篇时政文章) ──独立── 用于常识判断考点溯源

exam_papers ──1:N──▶ questions
                         │
                         ├──1:N──▶ practice_attempts (历史作答流水)
                         ├──1:N──▶ practice_session_items (会话题目队列)
                         ├──1:1──▶ question_reviews (最新复盘状态)
                         └──1:N──▶ question_sources (题目溯源)

practice_sessions ──1:N──▶ practice_session_items

paper_candidates (试卷候选，空) ──独立── 粉笔试卷发现流水线
```

## 表结构

### exam_papers（试卷，118 行）

```sql
CREATE TABLE exam_papers (
    id TEXT PRIMARY KEY,              -- "fenbi-8bc8a55c5e12185a"
    exam_type TEXT NOT NULL,          -- "国考" / "省考" / "事业编"
    region TEXT NOT NULL,             -- "全国" / "四川" / "重庆"
    year INTEGER,                     -- 2026
    exam_category TEXT NOT NULL,      -- "公务员" / "事业编"
    paper_kind TEXT,                  -- "行测" / "申论" / "职测" / "公基"
    source_name TEXT,                 -- "粉笔" / "local"
    source_url TEXT,                  -- 粉笔链接
    source_file TEXT NOT NULL,        -- "data/raw/papers/fenbi/fenbi-xxx/solution.json"
    markdown_path TEXT NOT NULL,      -- "vault/题库/真题套卷/2026-全国-行测-xxx.md"
    question_count INTEGER DEFAULT 0, -- 130
    import_status TEXT NOT NULL,      -- "imported"
    quality_status TEXT DEFAULT 'needs_review',
    parse_warnings_json TEXT DEFAULT '[]'
);
```

### questions（题目，6679 行）

```sql
CREATE TABLE questions (
    id TEXT PRIMARY KEY,                    -- "fenbi-8bc8a55c5e12185a-q111"
    paper_id TEXT NOT NULL REFERENCES exam_papers(id),
    number TEXT NOT NULL,                   -- 题号 "1" ~ "130"
    stem TEXT NOT NULL,                     -- 题干（含材料）
    options_json TEXT NOT NULL,             -- {"A": "...", "B": "..."}
    answer TEXT,                            -- "A" / "ABCD"（多选）
    explanation TEXT,                       -- 解析
    question_type TEXT,                     -- "常识判断" / "资料分析" / "言语理解" / ...
    knowledge_points_json TEXT NOT NULL,    -- ["资料分析", "统计表", "混合增长率"]
    difficulty TEXT DEFAULT 'medium',       -- 全部 "medium"，未分级
    source_span TEXT,                       -- "fenbi:3_1_ijsi4;materials:4_1_50dqa"
    question_format TEXT,                   -- "单选" / "多选" / "材料题组"
    review_status TEXT DEFAULT 'needs_review',
    parse_warnings_json TEXT DEFAULT '[]',
    explanation_source TEXT,                -- "fenbi_static_solution"
    explanation_status TEXT DEFAULT 'missing'
);
```

关键字段说明：
- `knowledge_points_json`：每题独立的考点列表，如 `["资料分析", "统计表", "混合增长率"]`
- `difficulty`：当前全部是 `"medium"`，未做难度分级
- `question_format`：`"材料题组"` 表示资料分析类共享材料的题组（5 道题共享一份材料）
- `source_span`：记录该题对应的粉笔 ID 和材料 ID，用于题组归类

### articles（时政文章，656 行）

```sql
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,              -- "xinhua-politics" / "qstheory" / "people-commentary" / ...
    url TEXT NOT NULL UNIQUE,
    published_at TEXT,
    authors_json TEXT NOT NULL,
    raw_path TEXT,
    markdown_path TEXT,                -- vault 中的路径
    tags_json TEXT NOT NULL,           -- ["政治理论", "重要会议讲话"]
    topics_json TEXT NOT NULL,         -- 考点归类
    content_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,              -- "parsed" / "ai-retagged" / "needs_review"
    ingested_at TEXT NOT NULL,
    image_urls_json TEXT DEFAULT '[]',
    image_paths_json TEXT DEFAULT '[]'
);
```

### practice_attempts（历史作答流水）

```sql
CREATE TABLE practice_attempts (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id),
    session_id TEXT,                   -- 所属练习会话
    position INTEGER,                  -- 会话中的题号
    selected_answer TEXT,              -- 用户选择的答案
    is_correct INTEGER,                -- 0/1
    duration_seconds INTEGER,          -- 作答耗时
    confidence INTEGER,                -- 信心度 (1-5)
    note TEXT,                         -- 用户笔记
    mistake_reason TEXT,               -- 错因
    review_note TEXT,                  -- 复盘记录
    updated_at TEXT,
    attempted_at TEXT NOT NULL         -- 作答时间
);
```

每次提交答案都会新增一条流水记录。它保留历史，不会因为后续重做而覆盖旧记录。

### practice_sessions（练习会话）

```sql
CREATE TABLE practice_sessions (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,                -- section / mock / favorites / mistakes
    title TEXT NOT NULL,
    config_json TEXT NOT NULL,         -- 题型、题量、组卷模板等配置
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER,
    ai_summary TEXT,
    ai_status TEXT NOT NULL DEFAULT 'not_requested',
    ai_generated_at TEXT
);
```

用于记录一次专项练习、随机组卷、重点专项或错题专项。

### practice_session_items（会话题目队列）

```sql
CREATE TABLE practice_session_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES practice_sessions(id),
    question_id TEXT NOT NULL REFERENCES questions(id),
    position INTEGER NOT NULL,
    material_group TEXT,               -- 资料分析共享材料分组
    selected_answer TEXT,
    is_correct INTEGER,
    duration_seconds INTEGER,
    answered_at TEXT,
    review_note TEXT,
    mistake_reason TEXT,
    confidence INTEGER,
    favorite INTEGER NOT NULL DEFAULT 0,
    UNIQUE(session_id, position)
);
```

这是一次练习里的题目队列和当前作答状态。资料分析在 UI 中按共享材料展示，但此表仍按单题记录答案、正确率、耗时和复盘。

### question_reviews（最新复盘状态）

```sql
CREATE TABLE question_reviews (
    question_id TEXT PRIMARY KEY REFERENCES questions(id),
    mistake_reason TEXT,
    review_note TEXT,
    confidence INTEGER,
    favorite INTEGER NOT NULL DEFAULT 0,
    last_attempt_id TEXT,
    last_attempted_at TEXT,
    markdown_path TEXT,
    updated_at TEXT NOT NULL
);
```

每题只保存一份最新学习状态。错题池由 `last_attempt_id` 指向的最近一次作答是否错误决定；重点题由 `favorite = 1` 决定。

### question_sources（题目溯源，空表）

```sql
CREATE TABLE question_sources (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id),
    source_name TEXT NOT NULL,         -- "xinhua-politics" / "qstheory"
    source_url TEXT,                   -- 原文链接
    external_question_id TEXT,
    matched_stem TEXT,                 -- 匹配到的原文段落
    matched_answer TEXT,
    matched_explanation TEXT,
    match_confidence TEXT DEFAULT 'low',
    status TEXT DEFAULT 'needs_lookup',
    fetched_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

用于记录每道真题的考点来源——对应哪篇时政文章、哪个政策文件。当前为空。

### paper_candidates（试卷候选，空表）

```sql
CREATE TABLE paper_candidates (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    download_url TEXT,
    exam_category TEXT DEFAULT '公务员',
    exam_type TEXT,
    region TEXT,
    year INTEGER,
    paper_kind TEXT,
    download_status TEXT DEFAULT 'pending',
    import_status TEXT DEFAULT 'pending',
    blocked_reason TEXT,
    notes TEXT,
    local_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

粉笔试卷发现流水线使用：存储待下载的试卷 URL，下载后导入 `exam_papers`。当前为空。

## 前后端联通

### 数据流向

```
┌──────────────────────────────────────────────────────────┐
│                   vault/*.md（前端 - Obsidian）            │
│                                                          │
│  资料库/政策理论/ (articles)      题库/题目卡片/ (questions) │
│  ├─ tags      ◄──双向──►         ├─ knowledge_points        │
│  ├─ topics    ◄──双向──►         ├─ question_type           │
│  └─ status    ◄──双向──►         ├─ answer                  │
│                    │             └─ explanation             │
│                    │                          ▲             │
└────────────────────┼──────────────────────────┼─────────────┘
        sync/retag   │          import/enrich    │
                     ▼                          │
┌──────────────────────────────────────────────────────────┐
│          data/db/examdb.sqlite（后端 - SQLite）            │
│                                                          │
│  articles                           questions            │
│  ├─ tags_json      ◄── 双向 ──►    ├─ knowledge_points_json│
│  ├─ topics_json    ◄── 双向 ──►    ├─ answer              │
│  └─ status         ◄── 双向 ──►    └─ explanation         │
│                                                          │
│  exam_papers ──1:N──► questions                          │
└──────────────────────────────────────────────────────────┘
```

### 各方向操作明细

| 方向 | 操作 | 核心函数 | 覆盖范围 |
|------|------|----------|----------|
| **DB → MD** | `import fenbi-solution` | `import_fenbi_solution()` → `write_question_cards()` | 整卷 + 全部单题 card |
| **DB → MD** | `import paper` | `import_paper()` → `write_question_cards()` | 整卷 + 全部单题 card |
| **DB → MD** | enrichment 单题重写 | `rewrite_question_card()` | 单道题的 `.md` |
| **DB → MD** | 错题复盘卡导出 | `write_question_review_cards()` | `question_reviews` 允许字段 |
| **MD → DB** | 文章元数据同步 | `sync_article_metadata_from_markdown()` | articles 的 tags/topics/status |
| **MD → DB** | 复盘字段同步 | `sync_reviews_from_markdown()` | question_reviews 的错因/复盘/信心/重点 |
| **DB ↔ MD** | AI 重标注 | `retag_articles()` → 写 MD + 写 DB | articles 双向写入 |

### 题卡和复盘卡的同步现状

**`questions` 表 → vault 题卡 `.md` 是单向的：DB 是数据源，题卡由 DB 生成。**

- 在 Obsidian 里手动改题卡 frontmatter（如 `knowledge_points`），**数据库不会自动感知**，下次重新导入试卷会被覆盖
- `question_reviews` 有独立复盘卡，允许从 Obsidian 回写 `mistake_reason`、`review_note`、`confidence`、`favorite`
- 原始题干、选项、答案、解析、知识点不从复盘卡回写，避免污染导入源
- `parse_frontmatter_lines()`（`src/examdb/retag.py`）**只解析扁平列表**（`  - "value"` 格式），不支持嵌套 dict

### 资料分析材料题组的特殊处理

资料分析试题在 DB 中**每道小题独立存储**（各有各的 `knowledge_points_json`），但 vault 题卡以"材料题组"形式合并为单个 `.md`。

题卡 frontmatter 使用带题号前缀的扁平列表：

```yaml
question_format: "材料题组"
knowledge_points:
  - "111: 资料分析、统计表、混合增长率"
  - "112: 资料分析、统计表、两期比重"
  - "113: 资料分析、统计表、混合增长率"
  - "114: 资料分析、增长量比较、统计表"
  - "115: 资料分析、现期比重、统计表"
```

题卡正文中每道小题有内联考点：

```markdown
## 第 111 题
...题目...

**考点：资料分析、统计表、混合增长率**

**答案：C**
```

此格式对应代码 `src/examdb/markdown.py` 中的 `grouped_question_markdown()`。

## 刷题系统逻辑

- 打开方式：`scripts/obsidian/start_practice_server.sh` 或 `examdb practice serve --host 127.0.0.1 --port 8765`。
- 页面入口：`http://127.0.0.1:8765/`。
- 专项练习：按五大行测版块抽题。
- 随机组卷：内置国考行政执法、地市级、副省级模板。
- 重点专项：题卡中“标重点”会写入 `question_reviews.favorite`，后续可单独练重点题。
- 错题专项：最近一次作答错误的题进入错题池；再次做对后离开错题池。
- 普通抽题优先级：未做题优先，其次是冷却期后的重点题、错题和久未练题；近期刚做过的重点题/错题不会立刻反复出现。
- 作答后才展示答案、解析和知识点，避免资料分析等题型被考点提前提示。

## 刷题系统仍需关注的问题

1. **难度未分级** — `difficulty` 字段全是 `"medium"`，刷题时无法按难度递进。
2. **考点无层级** — `knowledge_points` 是扁平列表，无父子分类（如「增长率」→「混合增长率」），统计分析粒度粗。
3. **题卡修改不回写 DB** — 如需“Obsidian 修改考点 -> 自动同步 DB”，需新增受控的 `questions` 元数据同步，当前只允许复盘字段回写。
4. **申论刷题未完整实现** — 一期只预留入口，后续再做答案上传、AI 批改、复盘报告和素材关联。

## 相关源码

| 模块 | 职责 |
|------|------|
| `src/examdb/db.py` | 数据库连接、建表、全部 CRUD |
| `src/examdb/models.py` | Question / ExamPaper / ArticleRecord 数据类 |
| `src/examdb/fenbi.py` | 粉笔 JSON 解析 → Question 对象 |
| `src/examdb/papers.py` | 通用试卷文本解析 → Question 对象 |
| `src/examdb/markdown.py` | Question → Markdown 题卡渲染（单题 + 材料题组） |
| `src/examdb/sync.py` | Markdown → DB 同步（仅 articles） |
| `src/examdb/practice.py` | 刷题会话、抽题、作答、统计和 AI 分析 |
| `src/examdb/practice_server.py` | 本地 Web UI 和 JSON API 服务 |
| `src/examdb/reviews.py` | 错题复盘卡导出和复盘字段回写 |
| `src/examdb/retag.py` | AI 标注 articles 的 tags/topics，含 frontmatter 解析器 |
| `src/examdb/enrichment.py` | 解析增强、外部记录匹配、单题 card 重写 |
| `src/examdb/cli.py` | CLI 命令入口 |
