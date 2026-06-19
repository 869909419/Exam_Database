# Obsidian Command Rules

- Use Shell commands or another explicit user-configured Obsidian command runner; do not assume Obsidian can execute shell by itself.
- Prefer `scripts/obsidian/*.sh` because they resolve the project root and set `PYTHONPATH`.
- Do not store API keys in vault notes or plugin settings. Use environment variables such as `DEEPSEEK_API_KEY`.
- Import user-provided papers through `vault/待导入/真题/` and `scripts/obsidian/import_inbox_papers.sh`.
- After each run, verify that Markdown output exists in the expected vault directory and that `data/db/examdb.sqlite` was updated when appropriate.
