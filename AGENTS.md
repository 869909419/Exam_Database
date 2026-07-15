# ExamDB project instructions

## Project facts

- ExamDB is a Python 3.11+ project with an Obsidian vault, a local SQLite database, and Playwright-based Fenbi collection helpers.
- Run the CLI from the repository root with `python -m examdb` after installing the project in editable mode.
- The authoritative database is `data/db/examdb.sqlite`. `data/exam.db` is not a valid database path and must not be recreated or committed.
- The local Obsidian knowledge base is `vault/`.
- Read `docs/PROJECT_LOGIC.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, and `docs/PROJECT_HANDOFF.md` before making broad changes.

## Data and secret safety

- Never delete, replace, initialize over, or bulk-rewrite `data/db/examdb.sqlite` unless the user explicitly authorizes that exact operation and a backup exists.
- Do not commit `vault/`, `data/db/`, `data/raw/`, `data/processed/`, `data/auth/`, log files, `.env` files, or browser storage state.
- Treat `scripts/obsidian/.env.local` and `data/auth/fenbi/storage-state.json` as credentials.
- Prefer preview/dry-run modes before commands that write tags, metadata, reviews, or imported papers.

## Supported local workflows

- macOS/Linux wrappers live in `scripts/obsidian/`.
- Windows PowerShell wrappers live in `scripts/windows/`.
- On Windows, run `powershell -ExecutionPolicy Bypass -File scripts/windows/bootstrap.ps1` once, then use the other PowerShell wrappers.
- The macOS `launchd` plist is not portable to Windows. Use Windows Task Scheduler only after validating the underlying command interactively.

## Verification

- Run the full test suite with `python -m unittest discover -s tests`.
- Verify a migrated database with SQLite `PRAGMA integrity_check` before any write operation.
- For practice UI changes, start the local server and verify `http://127.0.0.1:8765` plus `/api/metadata`.
- Preserve unrelated user changes and inspect `git status` before staging or committing.
