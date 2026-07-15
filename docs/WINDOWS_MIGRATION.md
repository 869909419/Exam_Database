# Windows migration guide

## Migration model

Use GitHub for source code and Git history, and use an encrypted local transfer for ignored runtime data. A Git clone alone is not a complete ExamDB migration.

The authoritative database is:

```text
data/db/examdb.sqlite
```

Do not use `data/exam.db`. That path was a zero-byte local artifact and is intentionally ignored.

## 1. Prepare the source device

Stop the practice server and all collection/import jobs before copying SQLite or the vault. Confirm the repository is clean and the current branch is pushed only after reviewing unpublished commits:

```bash
git status
git branch --show-current
git log --oneline --decorate -5
```

Record the database checksum:

```bash
shasum -a 256 data/db/examdb.sqlite
```

Copy these ignored paths through an encrypted drive or another trusted encrypted channel:

```text
vault/
data/db/examdb.sqlite
data/raw/
data/processed/
scripts/obsidian/.env.local
```

Recreate `data/auth/fenbi/storage-state.json` by logging in again on Windows instead of transferring browser cookies. Do not transfer `node_modules/`, `.venv/`, Python caches, Playwright caches, or macOS `.DS_Store` files.

## 2. Install Windows prerequisites

Install:

- Git for Windows
- Python 3.11 or newer, including the `py` launcher
- Current Node.js LTS
- Obsidian, if the vault is used interactively
- ChatGPT desktop app with Codex mode

Native Windows plus PowerShell is the default supported path for this repository. WSL2 remains optional for advanced Bash workflows, but mixing WSL paths with Windows Obsidian and browsers adds complexity.

## 3. Clone and bootstrap

In Windows PowerShell:

```powershell
git clone https://github.com/869909419/Exam_Database.git
Set-Location Exam_Database
git switch feature/integrate-knowledgebase-pipeline

powershell -ExecutionPolicy Bypass -File scripts/windows/bootstrap.ps1
```

Restore the encrypted local data into the same relative paths. Do not run `examdb init` over a restored database.

## 4. Verify the restored database

Run an integrity check:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/db/examdb.sqlite'); print(c.execute('PRAGMA integrity_check').fetchone()[0])"
```

The result must be `ok`. Compare the Windows checksum with the source-device checksum:

```powershell
Get-FileHash data\db\examdb.sqlite -Algorithm SHA256
```

Run the tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/run-tests.ps1
```

Start the practice UI:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/start-practice-server.ps1
```

Then verify `http://127.0.0.1:8765/api/metadata`.

## 5. Restore credentials and Obsidian

Restore `scripts/obsidian/.env.local` through a secure channel. It must remain ignored by Git. Recreate Fenbi browser authentication:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/fenbi-login.ps1
```

Open the restored `vault/` folder as an Obsidian vault. The existing macOS Shell Commands entries contain macOS paths; replace them with templates from:

```text
skills/operate-obsidian-examdb/scripts/obsidian_commands_windows.txt
```

## 6. Platform differences

- Use `python` or `.venv\Scripts\python.exe`, not the macOS `python3` assumption.
- Use `scripts/windows/*.ps1` in PowerShell instead of `scripts/obsidian/*.sh`.
- The macOS `open` command is replaced by `Start-Process` in the Windows practice-server wrapper.
- `launchd` and `.plist` files do not work on Windows. Use Windows Task Scheduler after manually verifying the intended command.
- Do not copy `node_modules`; `bootstrap.ps1` restores it with `npm ci`.

## 7. Continue with Codex

Open the cloned repository in ChatGPT desktop, select Codex mode, and start a new local task. Ask Codex to read `AGENTS.md` and `docs/PROJECT_HANDOFF.md` before editing. Local task history should not be treated as the source of truth; Git commits and repository handoff documents are the durable project context.

## Acceptance checklist

- Correct branch is checked out and `git status` is understood.
- `data/db/examdb.sqlite` exists and `PRAGMA integrity_check` returns `ok`.
- Database SHA-256 matches the source device.
- `vault/` opens in Obsidian and expected notes/attachments are present.
- Python tests pass.
- Practice UI and `/api/metadata` load.
- Node dependencies and Playwright Chromium are installed locally.
- DeepSeek key is restored securely and remains untracked.
- Fenbi login is recreated on Windows.
- macOS automation is disabled or replaced with reviewed Windows Task Scheduler entries.
