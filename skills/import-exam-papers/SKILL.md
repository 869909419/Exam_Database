---
name: import-exam-papers
description: Import public or user-provided civil-service exam papers into this Obsidian exam vault. Use for PDF, Markdown, or text papers that should become structured paper notes, question cards, and SQLite records.
---

# Import Exam Papers

## Workflow

1. Confirm the paper is public, openly downloadable, or user-provided.
2. Run the deterministic importer:

```bash
examdb import paper --file path/to/paper.pdf
```

3. Check the generated paper under `vault/题库/真题套卷/`.
4. Check generated question cards under `vault/题库/题目卡片/`.
5. If PDF extraction is weak, manually provide or produce a copyable Markdown version, then re-import that Markdown.

## References

- Read `references/paper-import-rules.md` before changing parsing, metadata, or source policy.
