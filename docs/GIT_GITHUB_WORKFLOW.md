# Git and GitHub Workflow

本文档记录本项目如何用 Git 做本地版本管理，以及如何连接 GitHub 做远程备份和协作。

当前项目建议：

- Git 管理代码、测试、脚本、项目文档、技能规则、配置模板。
- 不把本地数据、数据库、密钥、缓存、`vault/` 目录提交到 GitHub。
- 每次完成一个明确的小阶段就提交一次，不把大量无关修改混成一个提交。

## 一、当前项目状态

项目目录：

```bash
cd /Users/liuyigedabu/Documents/Exam_Database
```

当前 Git 状态：

```bash
git status
```

当前分支：

```bash
git branch --show-current
```

查看是否已经绑定 GitHub：

```bash
git remote -v
```

如果没有输出，说明还没有绑定远程仓库。

本项目当前 GitHub 仓库：

```text
https://github.com/869909419/Exam_Database.git
```

## 二、.gitignore 策略

本项目应提交：

- `src/`：项目源码。
- `tests/`：测试代码和测试 fixtures。
- `docs/`：技术文档。
- `skills/`：项目内 Codex/agent 技能规则。
- `scripts/`：可复用脚本。
- `pyproject.toml`：Python 项目配置。
- `.env.local.example`：环境变量模板。
- `data/**/.gitkeep`：保留必要空目录。

本项目不应提交：

- `vault/`：Obsidian 知识库本体，内容会持续变化且体积可能增长。
- `.DS_Store`：macOS 自动生成文件。
- `.env`、`.env.local`、`.env.*`：密钥和本地环境变量。
- `data/db/*.sqlite`：本地数据库。
- `data/raw/`、`data/processed/`、`data/auth/`：本地采集数据、处理中间产物、认证数据。
- `.venv/`、`__pycache__/`、`.pytest_cache/` 等本地缓存。
- `.playwright-cli/`、`playwright-report/`、`test-results/` 等自动化缓存。

如果误把应忽略文件加入索引，用：

```bash
git rm -r --cached vault
git rm --cached .DS_Store
git rm --cached data/.DS_Store
git add .gitignore
```

`--cached` 只从 Git 索引中移除，不删除本地文件。

## 三、第一次本地提交

查看当前变更：

```bash
git status
```

把应该提交的文件加入暂存区：

```bash
git add .gitignore docs src tests scripts skills pyproject.toml data/db/.gitkeep data/raw/.gitkeep data/processed/.gitkeep
```

如果需要把 Obsidian 顶层配置也提交：

```bash
git add .obsidian
```

确认暂存区内容：

```bash
git status
git diff --cached --stat
```

创建第一次提交：

```bash
git commit -m "Initial project setup"
```

查看提交结果：

```bash
git log --oneline -5
```

## 四、创建 GitHub 远程仓库

在 GitHub 网页中新建仓库，建议仓库名：

```text
Exam_Database
```

第一次创建时建议保持空仓库：

- 不勾选 Add README。
- 不勾选 Add .gitignore。
- 不勾选 license。

因为本地项目已经有这些内容，空仓库最容易连接。

## 五、绑定 GitHub 远程仓库

本项目使用的远程仓库地址：

```text
https://github.com/869909419/Exam_Database.git
```

绑定命令：

```bash
git remote add origin https://github.com/869909419/Exam_Database.git
```

检查远程仓库：

```bash
git remote -v
```

第一次推送：

```bash
git push -u origin main
```

`-u` 会把本地 `main` 和远程 `origin/main` 关联起来。之后直接执行 `git push` 就可以。

## 六、日常工作流

每次开始工作前：

```bash
git status
git pull
```

修改代码、文档或脚本后，先看改了什么：

```bash
git status
git diff
```

选择性暂存文件：

```bash
git add src/examdb/cli.py tests/test_new_sources.py docs/GIT_GITHUB_WORKFLOW.md
```

如果确认所有未忽略文件都要提交：

```bash
git add .
```

提交：

```bash
git commit -m "Add source sync workflow"
```

推送到 GitHub：

```bash
git push
```

## 七、提交信息写法

提交信息应该说明“这次做了什么”，不要写太笼统。

推荐：

```bash
git commit -m "Add policy article sync command"
git commit -m "Ignore local Obsidian vault data"
git commit -m "Add tests for paper import"
git commit -m "Document GitHub workflow"
```

不推荐：

```bash
git commit -m "update"
git commit -m "fix"
git commit -m "stuff"
```

## 八、分支管理

小项目可以长期使用 `main` 分支。遇到较大改动时，新建功能分支：

```bash
git switch -c feature/paper-import
```

在分支上提交：

```bash
git add src tests docs
git commit -m "Add paper import parser"
git push -u origin feature/paper-import
```

回到主分支：

```bash
git switch main
```

合并功能分支：

```bash
git merge feature/paper-import
git push
```

删除已经合并的本地分支：

```bash
git branch -d feature/paper-import
```

删除远程分支：

```bash
git push origin --delete feature/paper-import
```

## 九、撤销和恢复

查看提交历史：

```bash
git log --oneline --graph --decorate -20
```

查看某个文件的修改：

```bash
git diff src/examdb/cli.py
```

取消某个文件的暂存：

```bash
git restore --staged src/examdb/cli.py
```

丢弃某个文件的工作区修改：

```bash
git restore src/examdb/cli.py
```

注意：`git restore 文件名` 会放弃本地未提交修改，执行前务必确认。

撤销最近一次提交，但保留文件修改：

```bash
git reset --soft HEAD~1
```

不建议随便使用：

```bash
git reset --hard
```

它会丢弃本地修改，除非非常明确知道后果，否则不要执行。

## 十、常见问题

### 1. 为什么 `vault/` 不进 Git？

`vault/` 是 Obsidian 工作区和资料库本体，里面会包含大量自动采集资料、附件、阅读状态和个人复习内容。它更像本地数据资产，不像项目源码。把它放进 GitHub 会让仓库快速变大，也容易把私人学习资料推到远程。

### 2. 如果以后想同步 vault 怎么办？

建议用独立方案：

- Obsidian Sync。
- iCloud Drive / OneDrive / Dropbox。
- 单独建一个私有仓库，只管理 vault。
- 用 Git LFS 管理大附件。

不要和源码仓库混在一起。

### 3. 为什么 `.env.local.example` 可以提交？

`.env.local.example` 不放真实密钥，只写变量名和示例值。它帮助新环境知道需要哪些配置。

真实文件如 `.env.local` 不能提交。

### 4. 如何确认没有密钥要提交？

提交前检查：

```bash
git status
git diff --cached
```

也可以搜索常见密钥字段：

```bash
rg "API_KEY|SECRET|TOKEN|PASSWORD|COOKIE" .
```

如果发现密钥已经进入提交历史，需要立即轮换密钥，并清理 Git 历史。

## 十一、推荐操作顺序

当前项目建议下一步按这个顺序走：

```bash
git status
git add docs/GIT_GITHUB_WORKFLOW.md
git diff --cached --stat
git commit -m "Initial project setup"
git remote add origin https://github.com/869909419/Exam_Database.git
git push -u origin main
```

如果还没有创建 GitHub 仓库，先完成 GitHub 网页上的新建仓库，再执行 `git remote add origin ...`。
