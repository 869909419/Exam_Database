# 项目技能设计

## 设计原则

- 每个 skill 只负责一个稳定工作流。
- `SKILL.md` 保持短小，详细规则放 `references/`。
- 重复且易错的操作优先调用 `examdb` CLI 或 `scripts/`。
- skill 不绕过合规边界，不处理登录、验证码、付费墙内容。

## 技能清单

### operate-obsidian-examdb

用于在 Obsidian vault 中触发和协调项目脚本。它是入口型 skill：先判断要运行采集、导入、分类还是报表，再调用 `scripts/obsidian/` wrapper 或转到专项 skill。

典型任务：

```bash
scripts/obsidian/collect_qstheory_recent.sh
scripts/obsidian/import_inbox_papers.sh
scripts/obsidian/generate_weekly_report.sh
```

### collect-policy-materials

用于采集公开政策理论文章，清洗正文，写入 Obsidian vault 和 SQLite。

典型任务：

```bash
examdb ingest articles --source qstheory --since 2025-06-17
```

扩展来源时先阅读 `docs/SOURCE_ROADMAP.md`，每个 source adapter 必须保留原始 HTML、Markdown、SQLite 索引和本地图片附件。

### import-exam-papers

用于导入公开可下载或用户自备 PDF/Markdown 真题套卷，生成套卷笔记和数据库记录。

### classify-exam-questions

用于对已导入题目进行题型、知识点、难度分类。

### analyze-practice-results

用于读取作答记录，生成错因、复习建议、周报和错题视图。
