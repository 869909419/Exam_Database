# Windows PowerShell entry points

Run these commands from the repository root in Windows PowerShell.

## First-time setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/bootstrap.ps1
powershell -ExecutionPolicy Bypass -File scripts/windows/run-tests.ps1
```

## Common commands

```powershell
# Start the practice UI and open the browser.
powershell -ExecutionPolicy Bypass -File scripts/windows/start-practice-server.ps1

# Recreate Fenbi browser authentication on this Windows device.
powershell -ExecutionPolicy Bypass -File scripts/windows/fenbi-login.ps1

# Collect articles. Omit -Since to use the CLI default.
powershell -ExecutionPolicy Bypass -File scripts/windows/collect-recent.ps1 -Source qstheory -Since 2026-01-01 -Limit 5

# Preview retagging; add -Apply only after reviewing the preview.
powershell -ExecutionPolicy Bypass -File scripts/windows/retag-articles.ps1 -Source qstheory -Limit 10

# Preview Markdown-to-SQLite metadata synchronization.
powershell -ExecutionPolicy Bypass -File scripts/windows/sync-articles.ps1 -Source qstheory -OnlyChanged

# Discover and fetch Fenbi papers.
powershell -ExecutionPolicy Bypass -File scripts/windows/discover-fenbi-papers.ps1 -LabelId 1 -PaperKind xingce
powershell -ExecutionPolicy Bypass -File scripts/windows/fetch-fenbi-paper.ps1 -PaperId 222388 -Import

# Generate the practice weekly report.
powershell -ExecutionPolicy Bypass -File scripts/windows/generate-weekly-report.ps1

# Pass any CLI arguments through the generic wrapper from PowerShell.
& scripts/windows/examdb.ps1 -ExamDbArguments @("practice", "start", "--filter", "常识判断")
```

The wrappers require `.venv`, created by `bootstrap.ps1`. They always resolve the repository root relative to their own location, so the project can live on any Windows drive or folder.

The macOS `scripts/obsidian/com.examdb.fetch-fenbi-daemon.plist` file is not supported on Windows. Validate a command interactively before recreating it with Windows Task Scheduler.
