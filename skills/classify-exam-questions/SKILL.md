---
name: classify-exam-questions
description: Classify civil-service exam questions in this Obsidian exam vault. Use when assigning question_type, knowledge_points, difficulty, paper metadata, or AI-assisted taxonomy labels for 国考, 四川省考, and 重庆省考 questions.
---

# Classify Exam Questions

## Workflow

1. Read `docs/TAXONOMY.md` before classifying.
2. Use existing fields on question notes and SQLite rows; do not invent unsupported taxonomy names.
3. Assign exactly one `question_type` from the approved taxonomy.
4. Keep `difficulty` as `medium` unless the stem, source, or practice data supports `easy` or `hard`.
5. Use AI for suggestions, then validate output against the taxonomy before writing.

## References

- Read `references/classification-rules.md` for classification defaults and edge cases.
