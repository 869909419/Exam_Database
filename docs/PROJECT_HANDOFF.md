# Project handoff

Last refreshed: 2026-07-15

## Current development line

- Working branch: `feature/integrate-knowledgebase-pipeline`
- Remote repository: `https://github.com/869909419/Exam_Database.git`
- The July 2026 local work added the practice system, source automation, official-source collection, source analysis, and practice-page UI improvements.
- Before device migration, unpublished history was audited to exclude local logs and the invalid zero-byte `data/exam.db` artifact.

Always verify the live branch and commit state with Git; this document is a handoff summary, not a replacement for repository history.

## Runtime state that Git does not contain

- `data/db/examdb.sqlite`: authoritative SQLite database
- `vault/`: Obsidian knowledge base and generated review/article material
- `data/raw/`: downloaded source material
- `data/processed/`: processed source material
- `scripts/obsidian/.env.local`: DeepSeek credential
- `data/auth/fenbi/storage-state.json`: device-local browser authentication; recreate on a new device

Never infer database completeness from the Git checkout alone.

## Known product work

The latest UI commit notes identify these unfinished areas:

1. Add a dedicated Shenlun practice page/workflow.
2. Add the AI analysis API and connect it to the practice experience.
3. Improve the practice UI visual system and consistency.
4. Review generated/local artifacts carefully before committing or publishing them.

Before implementing any of these, inspect the current UI and database contract, then propose a narrow plan with tests and migration implications.

## Windows continuation

1. Follow `docs/WINDOWS_MIGRATION.md`.
2. Run `scripts/windows/bootstrap.ps1`.
3. Restore and integrity-check `data/db/examdb.sqlite` before writes.
4. Run `scripts/windows/run-tests.ps1`.
5. Start the practice UI with `scripts/windows/start-practice-server.ps1`.
6. Recreate Fenbi login rather than copying browser cookies.

## Suggested first Codex prompt on Windows

```text
Take over this ExamDB repository on native Windows. Read AGENTS.md,
docs/PROJECT_LOGIC.md, docs/ARCHITECTURE.md, docs/DATABASE.md,
docs/WINDOWS_MIGRATION.md, and docs/PROJECT_HANDOFF.md first.

Do not modify anything yet. Inspect Git status, confirm that
data/db/examdb.sqlite is the authoritative database, run its integrity check,
and run the test suite. Report the current state, migration risks, and the
smallest recommended next task. Never initialize over or replace the restored
database without explicit approval.
```
