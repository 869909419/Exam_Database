---
name: collect-policy-materials
description: Collect public civil-service policy materials into this Obsidian exam vault. Use when gathering articles from 求是网, 人民日报, 人民网评, government websites, or other public sources, then cleaning HTML, assigning tags, writing Markdown, and updating SQLite.
---

# Collect Policy Materials

## Workflow

1. Confirm the source is public and does not require login, payment, captcha bypass, or access-control workarounds.
2. Prefer the project CLI for deterministic collection:

```bash
examdb ingest articles --source qstheory --since 2025-06-17
```

3. Review generated notes under `vault/资料库/政策理论/`.
4. Check that each note has stable frontmatter: `title/source/url/published_at/authors/tags/topics/hash/raw_path/ingested_at/status`.
5. If AI is used, treat it as a validator and tag suggester; do not let AI invent source metadata.

## References

- Read `references/source-rules.md` before adding a new source adapter or changing cleaning rules.
