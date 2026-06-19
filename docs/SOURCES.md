# 来源与清洗规则

## 首批来源

| 来源 | 类型 | 首版状态 | 备注 |
| --- | --- | --- | --- |
| 求是网 | 政策理论 | 已实现 | 默认从目录页滚动采集最近一年，按期数归档 |
| 人民网观点/人民网评 | 评论材料 | 已实现 | 重点作为申论表达素材 |
| 中国政府网 | 政策文件 | 已实现 | 最新政策、政策解读、国务院文件 |
| 新华网时政 | 时政新闻 | 已实现 | 重大时政、新华社通稿、新华典评 |
| 四川省政府/重庆市政府 | 地方政策 | 已实现 | 地方省考/市考政策素材 |
| 国家统计局 | 数据材料 | P1 规划 | 统计公报、经济数据、图表素材 |
| 人民日报/人民网 | 新闻评论 | P2 规划 | 重要评论、理论版、人民时评 |
| 光明网理论 | 理论文章 | P2 规划 | 理论、文化、治理材料 |
| 粉笔 | 真题结构化数据/PDF | 已验证页面链路，已实现 `static/solution` JSON 标准化导入 | 登录后可答题、下载 PDF、交卷查看逐题答案解析；凭据只读环境变量 |
| 中公/华图/网络搜索 | 真题 PDF | 候选框架 | 先接公开 PDF 页面和下载链接 |
| 用户自备 PDF/Markdown | 真题 | 已实现标准化导入 | 继续支持 inbox 批量导入 |

完整来源路线图见 `docs/SOURCE_ROADMAP.md`。

## 采集字段

文章必须保留：

- `title`
- `source`
- `url`
- `published_at`
- `authors`
- `tags`
- `topics`
- `images`
- `content_hash`
- `raw_path`
- `markdown_path`
- `ingested_at`

真题候选套卷额外保留：

- `source_id`
- `source_name`
- `title`
- `url`
- `download_url`
- `exam_category`
- `exam_type`
- `region`
- `year`
- `paper_kind`
- `download_status`
- `import_status`
- `blocked_reason`

## Obsidian 路径规则

文章按来源分组。求是文章优先按期数分组；无法识别期数的来源回退为发布日期分组。

求是期数路径：

```text
vault/资料库/政策理论/qstheory/<YYYY>/<YYYY年第N期>/<title>.md
```

例如：

```text
vault/资料库/政策理论/qstheory/2026/2026年第12期/本期导读.md
```

回退日期路径：

```text
vault/资料库/政策理论/<source>/<YYYY>/<MM-DD>/<title>.md
```

发布日期仍保留在 frontmatter 的 `published_at` 字段中，文件名不重复添加日期。

## 图片归档规则

正文图片会下载到文章所在目录下的 `附件/文章标题/`：

```text
vault/资料库/政策理论/<source>/<archive-dir>/附件/<title>/<index>-<image-name>
```

求是文章示例：

```text
vault/资料库/政策理论/qstheory/2026/2026年第12期/附件/本期导读/01-image.jpg
```

文章 Markdown 使用相对路径引用本地图片，frontmatter 的 `images` 字段记录附件路径。这样 Obsidian 可以直接显示图片，也能保留离线归档能力。

只保留正文区域内的图片；分享图标、二维码、站点 logo 等网页装饰图片不进入正文。

## 真题套卷规则

真题来源只做公开合规自动化，不绕过验证码、付费、App 专属、短信验证或其他访问控制。登录后免费资源可以自动化，但账号密码只从本机环境变量读取，不写入仓库、SQLite、Markdown 或日志。

### 粉笔验证结论

2026-06-18 已在粉笔真题页验证：

- 题库页：`https://www.fenbi.com/spa/tiku/guide/realTest/xingce/xingce?redirect=true`
- 登录后真题列表可进入具体套卷，页面会创建练习：`/ti/exam/exercise/<exerciseKey>?routecs=xingce`
- 练习页直接渲染整套题干、选项、材料和题型模块，并提供 `下载`、`交卷`。
- `getExercise` 响应含 PDF 地址：`switchVO.pdf.urls[0]`。
- `combine/static/exercise` 响应含题干、选项、材料、题型模块，但不含完整答案解析。
- 交卷确认后进入 `/ti/exam/solution/<exerciseKey>?routecs=xingce`。
- `combine/static/solution` 响应含完整结构化数据：`materials`、`solutions`、`card`；每题包含题干、选项、解析 `solution`、正确答案 `correctAnswer`、知识点 `keypoints`。

因此粉笔首选流程调整为：

```text
登录验证 -> 发现套卷 -> 创建/进入练习 -> 获取 static/exercise -> 交卷/进入解析 -> 获取 static/solution -> 标准化入库
```

PDF 仍保留为原始套卷归档备份，不再作为粉笔首选切分入口。

粉笔自动化脚本使用项目内固定版本 Playwright。首次运行前建议安装一次本地依赖和 Chromium：

```bash
npm install
npm run playwright:install
```

如果没有本地 `node_modules/playwright`，命令会回退到 `npx --package playwright@1.61.0`。为了减少临时下载和浏览器版本差异，长期使用建议保留项目内依赖。

登录态保存命令：

```bash
FENBI_USERNAME="手机号或账号" FENBI_PASSWORD="密码" \
PYTHONPATH=src python3 -m examdb auth fenbi-login
```

如果遇到验证码、短信或人机验证，改用可见浏览器手动完成登录：

```bash
PYTHONPATH=src python3 -m examdb auth fenbi-login --manual --headed
```

登录态只保存到本机忽略目录：

```text
data/auth/fenbi/storage-state.json
```

按粉笔 `labelId` 发现套卷列表并保存原始列表 JSON：

```bash
PYTHONPATH=src python3 -m examdb discover fenbi-papers \
  --label-id 1 \
  --paper-kind xingce
```

申论列表使用 `shenlun`：

```bash
PYTHONPATH=src python3 -m examdb discover fenbi-papers \
  --label-id 1 \
  --paper-kind shenlun
```

列表结果会保存到：

```text
data/raw/papers/fenbi/paper-list/<paper-kind>-<label-id>.json
```

Shell wrapper 也支持直接调用：

```bash
scripts/obsidian/discover_fenbi_papers.sh 1 xingce
scripts/obsidian/discover_fenbi_papers.sh 126 shenlun
```

常用 `labelId`（完整参考表见 `data/paper_ids/label_ids.md`）：

| labelId | 地区/考试 | labelId (申论) |
|---------|----------|---------------|
| 1 | 国考 | 101 |
| 26 | 四川 | 126 |
| 32 | 重庆 | 132 |

申论 labelId = 行测 labelId + 100。批量抓取用：

```bash
scripts/obsidian/fetch_fenbi_all.sh data/paper_ids/guokao_ids.txt
scripts/obsidian/fetch_fenbi_all.sh --shenlun data/paper_ids/guokao_shenlun_ids.txt
scripts/obsidian/fetch_fenbi_all.sh --from-discover data/raw/papers/fenbi/paper-list/xingce-1.json
```

**行测**：按 `paperId` 自动创建练习 → 空白交卷 → 拦截 `combine/static/solution` JSON（行测必须先交卷才能拿到答案）：

```bash
PYTHONPATH=src python3 -m examdb fetch fenbi-solution \
  --paper-id 222388 \
  --expected-question-count 135 \
  --expected-sections 常识判断,言语理解与表达,数量关系,判断推理,资料分析 \
  --strict
```

**申论**：直接调 `getPaperSolution` API → CDN 静态 JSON，**不需要做交卷**，JSON 自带 `solutionAccessories` 中的参考答案、解题思路和知识拓展：

```bash
PYTHONPATH=src python3 -m examdb fetch fenbi-solution \
  --paper-id 222388 \
  --shenlun \
  --import
```

`2025` 年之前的国考行测通常使用传统五板块：

```text
常识判断,言语理解与表达,数量关系,判断推理,资料分析
```

`2026` 国考行测已验证存在新结构，例如副省级：

```text
政治理论,常识判断,言语理解与表达,数量关系,判断推理,资料分析
```

抓取后立即导入：

```bash
PYTHONPATH=src python3 -m examdb fetch fenbi-solution \
  --paper-id 222388 \
  --expected-question-count 135 \
  --expected-sections 常识判断,言语理解与表达,数量关系,判断推理,资料分析 \
  --strict \
  --import
```

已保存的粉笔 `static/solution` JSON 也可单独检查或入库：

```bash
PYTHONPATH=src python3 -m examdb inspect fenbi-solution \
  --file data/raw/papers/fenbi/paper-222388/solution.json \
  --expected-question-count 135 \
  --expected-sections 常识判断,言语理解与表达,数量关系,判断推理,资料分析 \
  --strict
```

```bash
PYTHONPATH=src python3 -m examdb import fenbi-solution \
  --file data/raw/papers/fenbi/<paper-id>/solution.json \
  --source-url "https://spa.fenbi.com/ti/exam/solution/<exerciseKey>?routecs=xingce" \
  --paper-kind 行测
```

导入时的分类规则：

- `card` 章节用于题型模块：政治理论归入常识判断并保留为知识点，言语理解与表达归入言语理解，数量关系/判断推理/资料分析/常识判断直接映射。
- `solutions[].keypoints[].name` 进入 `knowledge_points`。
- `correctAnswer.choice` 从粉笔 0 基索引转换为 A/B/C/D。
- `solution` 进入解析，`explanation_source=fenbi_static_solution`，每题仍默认 `review_status=needs_review` 等待精校。
- AI 仅用于低置信补全或复核，不作为粉笔结构化解析的首选来源。

自动爬取必须限速：单套卷串行处理，页面操作和接口请求之间保留 3-8 秒间隔；遇到验证码、短信校验、扫码、人机验证或异常风控立即退出并记录 blocked reason。

公开页面 PDF 发现和下载命令：

```bash
PYTHONPATH=src python3 -m examdb discover papers --source fenbi --query "https://example.com/papers.html" --limit 5
PYTHONPATH=src python3 -m examdb download papers --source fenbi --limit 5
```

下载成功的 PDF 进入：

```text
data/raw/papers/<source>/<candidate-id>/
```

导入后的标准化文本进入：

```text
data/processed/papers/<paper-id>.md
```

最终 Obsidian 套卷和题卡进入：

```text
vault/题库/真题套卷/
vault/题库/题目卡片/
```

非粉笔 PDF 不默认包含完整答案解析。题目切分后，需要单独执行解析补全阶段：

```bash
PYTHONPATH=src python3 -m examdb enrich explanations --paper-id paper-xxx --source fenbi
```

这个命令会为缺少解析的题目建立 `question_sources` 待查询任务。抓取到粉笔等网站题目详情后，可用 JSON 或 JSONL 导入并保守匹配：

```bash
PYTHONPATH=src python3 -m examdb enrich explanations \
  --paper-id paper-xxx \
  --source fenbi \
  --source-file data/processed/papers/fenbi-matches.jsonl \
  --apply
```

JSONL 每行建议字段：

```json
{"number":"1","stem":"题干文本","answer":"A","explanation":"解析文本","source_url":"https://...","external_question_id":"..."}
```

只有高置信匹配会写回 `questions.answer/explanation`，AI 不能把生成内容伪装成粉笔解析；AI 生成解析必须单独标记来源和状态。

## 清洗原则

优先用规则清洗，再让 AI 做质量检查。

需要移除：

- 顶部导航、面包屑、频道入口。
- 分享、字号、打印、纠错、责任编辑。
- 推荐阅读、相关新闻、更多链接。
- 版权声明、ICP备案、页脚。
- 空行堆叠和明显重复段落。

需要保留：

- 标题、作者、来源、发布时间。
- 正文段落、编号、小标题、引用。
- 政策关键词和规范表述。

## 求是网首版规则

- 默认目录页：`https://www.qstheory.cn/qs/mulu.htm`
- 默认采集窗口：当前日期往前一年。
- 从年度目录展开期刊目录，再从期刊目录展开正文文章。
- 文章 URL 以 `qstheory.cn` 域名、日期路径、`c.html` 结尾为主要候选。
- 期刊目录页不入库，只用于发现正文文章。
- 文章按 `source: 《求是》YYYY/N` 解析期数并归档。

## 人民网观点规则

- 默认入口页：`http://opinion.people.com.cn/`
- Source ID：`people-commentary`
- 文章 URL 优先匹配：`opinion.people.com.cn/n1/YYYY/MMDD/...html`
- 归档路径：`vault/资料库/政策理论/people-commentary/YYYY/MM-DD/title.md`
- 正文图片放在文章同级目录下：`附件/title/`
- 只采集人民网观点域名下公开文章，跳过外域链接、栏目页、专题页、图片、视频和静态资源。

命令示例：

```bash
PYTHONPATH=src python3 -m examdb ingest articles --source people-commentary --since 2025-06-17 --limit 5
```

## 中国政府网规则

- 默认数据源：
  - `https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json`
  - `https://www.gov.cn/zhengce/jiedu/ZCJD_QZ.json`
- Source ID：`gov-policy`
- 兼容别名：`gov`
- 文章 URL 只保留 `www.gov.cn/zhengce/` 下的 `content_*.htm` 页面。
- 跳过专题首页、专栏首页、外域链接、静态资源和非政策正文页。
- 正文优先提取 `UCAP-CONTENT`，回退到 `pages_content` / `article`。
- 归档路径：`vault/资料库/政策理论/gov-policy/YYYY/MM-DD/title.md`
- 正文图片放在文章同级目录下：`附件/title/`
- 站点 logo、分享图、二维码和 `/images/150.jpg` 等分享封面不进入正文图片。

命令示例：

```bash
PYTHONPATH=src python3 -m examdb ingest articles --source gov-policy --since 2025-06-17 --limit 5
```

## 新华网时政规则

- 默认入口页：`https://www.news.cn/politics/`
- Source ID：`xinhua-politics`
- 文章 URL 只保留：`www.news.cn/politics/YYYYMMDD/.../c.html`
- 正文优先提取 `detailContent`，跳过责任编辑、相关新闻、二维码和分享图。
- 归档路径：`vault/资料库/政策理论/xinhua-politics/YYYY/MM-DD/title.md`

命令示例：

```bash
PYTHONPATH=src python3 -m examdb ingest articles --source xinhua-politics --since 2025-06-17 --limit 5
```

## 四川/重庆政府网站规则

- Source ID：
  - `sichuan-gov`
  - `chongqing-gov`
- 默认入口页：
  - 四川：省政府首页、政策文件、政策解读、政策文件库相关栏目。
  - 重庆：市政府首页、政策文件库、政策解读栏目。
- 只采集本域公开 HTML 文章页，跳过外域链接、下载附件、静态资源、专题首页。
- 正文优先提取 `contText`、`TRS_UEDITOR`、`zoom` 等政府站点常见正文容器，必要时用 `Description` 元数据兜底。
- 归档路径：
  - `vault/资料库/政策理论/sichuan-gov/YYYY/MM-DD/title.md`
  - `vault/资料库/政策理论/chongqing-gov/YYYY/MM-DD/title.md`

命令示例：

```bash
PYTHONPATH=src python3 -m examdb ingest articles --source sichuan-gov --since 2025-06-17 --limit 5
PYTHONPATH=src python3 -m examdb ingest articles --source chongqing-gov --since 2025-06-17 --limit 5
```
