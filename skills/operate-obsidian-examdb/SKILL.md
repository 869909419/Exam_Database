---
name: operate-obsidian-examdb
description: Operate this Obsidian-first civil-service exam database from the vault. Use when configuring Obsidian Shell commands, running project wrapper scripts, collecting materials from Obsidian, importing papers from the vault inbox, generating reports, or coordinating the specialized ExamDB skills.
---

# Operate Obsidian ExamDB

## Overview

Use this skill as the Obsidian-facing entrypoint for ExamDB. It maps vault actions to stable wrapper scripts, then checks that Markdown and SQLite outputs land in the expected locations.

## Workflow

1. Identify the requested Obsidian action: initialize, collect policy materials, import inbox papers, fetch Fenbi papers, list practice questions, or generate a weekly report.
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
scripts/obsidian/collect_people_commentary_recent.sh
scripts/obsidian/collect_gov_policy_recent.sh
scripts/obsidian/collect_xinhua_politics_recent.sh
scripts/obsidian/collect_sichuan_gov_recent.sh
scripts/obsidian/collect_chongqing_gov_recent.sh
scripts/obsidian/import_inbox_papers.sh
scripts/obsidian/generate_weekly_report.sh
scripts/obsidian/list_practice_questions.sh
scripts/obsidian/retag_policy_articles.sh
scripts/obsidian/sync_policy_article_metadata.sh
```

Fenbi paper operations now have shell wrappers:

```bash
# Login
scripts/obsidian/fenbi_login.sh

# Discover papers by labelId
scripts/obsidian/discover_fenbi_papers.sh 1 xingce      # 国考行测
scripts/obsidian/discover_fenbi_papers.sh 1 shenlun      # 国考申论
scripts/obsidian/discover_fenbi_papers.sh 26 xingce     # 四川省考行测

# Fetch single paper
scripts/obsidian/fetch_fenbi_paper.sh 222388 --import
scripts/obsidian/fetch_fenbi_paper.sh 222388 --shenlun --import

# Batch fetch from ID file or discover JSON
scripts/obsidian/fetch_fenbi_all.sh data/paper_ids/guokao_ids.txt
scripts/obsidian/fetch_fenbi_all.sh --from-discover data/raw/papers/fenbi/paper-list/xingce-1.json
scripts/obsidian/fetch_fenbi_all.sh --shenlun data/paper_ids/guokao_shenlun_ids.txt
```

底层 CLI 仍然可用，适合脚本和调试：

```bash
PYTHONPATH=src python3 -m examdb auth fenbi-login --manual --headed
PYTHONPATH=src python3 -m examdb discover fenbi-papers --label-id 1 --paper-kind xingce
PYTHONPATH=src python3 -m examdb fetch fenbi-solution --paper-id 222388 --import
PYTHONPATH=src python3 -m examdb fetch fenbi-solution --paper-id 222388 --shenlun --import
```

## References

- Read `references/obsidian-command-rules.md` before changing Obsidian command setup.
