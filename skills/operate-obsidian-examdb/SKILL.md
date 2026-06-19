---
name: operate-obsidian-examdb
description: Operate this Obsidian-first civil-service exam database from the vault. Use when configuring Obsidian Shell commands, running project wrapper scripts, collecting materials from Obsidian, importing papers from the vault inbox, generating reports, or coordinating the specialized ExamDB skills.
---

# Operate Obsidian ExamDB

## Overview

Use this skill as the Obsidian-facing entrypoint for ExamDB. It maps vault actions to stable wrapper scripts, then checks that Markdown and SQLite outputs land in the expected locations.

## Workflow

1. Identify the requested Obsidian action: initialize, collect policy materials, import inbox papers, list practice questions, or generate a weekly report.
2. Prefer wrapper scripts in `scripts/obsidian/` instead of calling Python modules directly.
3. After running a script, verify the relevant vault folder:
   - `vault/资料库/政策理论/`
   - `vault/题库/真题套卷/`
   - `vault/题库/题目卡片/`
   - `vault/刷题记录/周报/`
4. For deeper content work, hand off to the focused skill:
   - `collect-policy-materials`
   - `import-exam-papers`
   - `classify-exam-questions`
   - `analyze-practice-results`

## Commands

```bash
scripts/obsidian/init_examdb.sh
scripts/obsidian/collect_qstheory_recent.sh
scripts/obsidian/import_inbox_papers.sh
scripts/obsidian/generate_weekly_report.sh
scripts/obsidian/list_practice_questions.sh
scripts/obsidian/retag_policy_articles.sh
scripts/obsidian/sync_policy_article_metadata.sh
```

## References

- Read `references/obsidian-command-rules.md` before changing Obsidian command setup.
