---
name: analyze-practice-results
description: Analyze practice attempts in this Obsidian exam vault. Use when generating mistake summaries, weekly reports, review priorities, wrong-question notes, or AI-assisted explanations from SQLite practice data.
---

# Analyze Practice Results

## Workflow

1. Generate deterministic statistics first:

```bash
examdb report weekly
```

2. Read recent `practice_attempts`, related question cards, and the generated weekly report.
3. Summarize weak question types, recurring knowledge points, time sinks, and confidence mismatches.
4. Write review notes under `vault/刷题记录/`.
5. Do not overwrite raw attempt records; append analysis notes.

## References

- Read `references/practice-analysis-rules.md` before generating coaching advice.
