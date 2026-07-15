# 来源扩展路线图

## 总原则

- 只采集公开可访问内容，不绕过登录、验证码、付费墙或访问控制。
- 每个来源先做小样本 adapter，再扩大采集窗口。
- 政治理论备考采集优先使用 `--profile politics-theory`，按高频考点画像筛选同类新材料；已考原文只作为校准样本。
- 原始 HTML 保存到 `data/raw/`，清洗 Markdown 保存到 vault，SQLite 保存索引。
- 来源质量优先于数量：先保证正文清洗干净、标签不过度、图片能本地化，再扩源。

## 已实现来源

| Source ID | 来源 | 重点内容 | 当前状态 |
| --- | --- | --- | --- |
| `qstheory` | 求是网读刊 | 《求是》期刊文章、正刊权威表述 | 已实现 |
| `qstheory-web` | 求是网主站栏目 | 要闻、网评、原创、政治、党建、科教、理论文选 | 已实现 |
| `people-commentary` | 人民网观点/人民网评 | 时评、申论表达、热点分析 | 已实现 |
| `gov-policy` | 中国政府网政策/要闻 | 国务院文件、规划纲要、政策解读、会议通稿 | 已实现 |
| `xinhua-politics` | 新华网时政 | 时政新闻、新华社通稿、领导人活动 | 已实现 |
| `sichuan-gov` | 四川省政府 | 四川政策、公报、省委/省政府重点材料 | 已实现 |
| `chongqing-gov` | 重庆市政府 | 重庆政策、政策解读、政府公报 | 已实现 |
| `neac-gov` | 国家民委 | 民族工作、中华民族共同体意识 | 已实现 |
| `most-gov` | 科技部 | 科技强国、科技自立自强、新质生产力 | 已实现 |
| `mohrss-gov` | 人社部 | 就业、社保、劳动权益 | 已实现 |
| `ccdi-gov` | 中央纪委国家监委 | 自我革命、全面从严治党、纪律建设 | 已实现 |
| `stats-gov` | 国家统计局 | 区域协调、社会事业、民生数据解释 | 已实现 |

文章默认按 `vault/资料库/政策理论/<source>/<YYYY>/<MM-DD>/<title>.md` 归档；求是网按期数归档。

## 高频备考画像

政治理论题的自动化采集目标是持续收集“同类、未过时、权威”的备考材料，而不是只把已考题定位到原文。推荐命令：

```bash
scripts/obsidian/collect_gov_policy_recent.sh 2025-01-01 30 "" politics-theory
scripts/obsidian/collect_xinhua_politics_recent.sh 2025-01-01 30 "" politics-theory
scripts/obsidian/collect_qstheory_recent.sh 2025-01-01 30 "" politics-theory
scripts/obsidian/collect_qstheory_web_recent.sh 2025-01-01 30 "" politics-theory
scripts/obsidian/collect_neac_gov_recent.sh 2025-01-01 20 "" politics-theory
scripts/obsidian/collect_most_gov_recent.sh 2025-01-01 20 "" politics-theory
scripts/obsidian/collect_mohrss_gov_recent.sh 2025-01-01 20 "" politics-theory
scripts/obsidian/collect_ccdi_gov_recent.sh 2025-01-01 20 "" politics-theory
scripts/obsidian/collect_stats_gov_recent.sh 2025-01-01 20 "" politics-theory
```

`politics-theory` 当前内置关键词：

```text
中国式现代化,进一步全面深化改革,二十届三中全会,二十届四中全会,十五五,
新质生产力,高质量发展,科技强国,科技自立自强,教育强国,就业优先,
高质量充分就业,人口高质量发展,中华民族共同体,民族团结进步,
党的自我革命,全面从严治党,国家安全,数字政府,数字贸易,质量强国,
共同富裕,法治,绿色低碳,城乡融合,现代化产业体系,文化强国,
国际传播,全球治理
```

可用第 5 个参数追加临时关键词：

```bash
scripts/obsidian/collect_gov_policy_recent.sh 2025-01-01 20 "" politics-theory "教育强国,质量强国,数字政府"
```

关键词维护原则：

- 优先加入真题题干、解析、官方原文中反复出现的规范提法。
- 少用过泛词，如单独的“民族”“改革”“发展”；优先用“铸牢中华民族共同体意识”“进一步全面深化改革”“高质量发展”等完整表述。
- 对专题采集，可以第 4 个参数传空字符串，只用第 5 个参数的关键词收窄结果。

## Source 能力说明

`gov-policy`：

- 从中国政府网公开 JSON 数据源读取最新政策和政策解读。
- 扫描 `gov.cn/yaowen/liebiao`，覆盖部分会议通稿和领导人活动。
- 支持 `GOV_POLICY_SEED_URLS` 和 `GOV_POLICY_SEED_FILE` 精准补采校准样本。

`xinhua-politics`：

- 扫描新华网时政、领导人、学习进行时等入口。
- 支持 `XINHUA_POLITICS_SEED_URLS` 和 `XINHUA_POLITICS_SEED_FILE` 精准补采。

`qstheory` / `qstheory-web`：

- `qstheory` 只走《求是》读刊目录，保留正刊来源边界。
- `qstheory-web` 扫描求是网主站和重点栏目，用于补要闻、网评、原创、政治、党建、科教、学习笔记、理论文选等同类备考材料。
- 主站文章中会包含部分正刊文章，重复 URL 和重复正文由 SQLite 的 `url/content_hash` 去重兜底。

`neac-gov`、`most-gov`、`mohrss-gov`、`ccdi-gov`、`stats-gov`：

- 复用官方站 adapter 基类，按公开栏目页发现文章。
- 每个来源可用 `<SOURCE_ID>_SEED_URLS` 和 `<SOURCE_ID>_SEED_FILE` 补重点材料。

`sichuan-gov` / `chongqing-gov`：

- 复用地方政府 adapter 基类。
- 四川入口补省委/省政府重点栏目；重庆入口补政策文件和政府公报栏目。

## 采集风险控制

- 默认使用公开页面的轻量 HTTP 抓取，靠 `limit`、SQLite 去重和画像过滤控制访问量。
- 不并发批量轰炸，不抓登录、验证码、付费墙或非公开接口。
- Playwright 只作为 JS 渲染页面或用户本人登录资源的兜底，不作为政策站默认批量采集方式。

## 下一批候选

| 优先级 | Source ID | 来源 | 主要用途 |
| --- | --- | --- | --- |
| P1 | `people-daily` | 人民日报公开页面 | 重要评论、理论版、人民时评 |
| P2 | `gmw-theory` | 光明网理论 | 理论文章、文化与治理材料 |
| P2 | `ndrc` | 国家发展改革委 | 宏观经济、产业政策、区域协调 |
| P2 | `mee` | 生态环境部 | 生态文明、绿色转型、污染防治 |
| P2 | `mca` | 民政部 | 基层治理、养老、社会救助、社区建设 |

## 验收标准

- 能用 `examdb ingest articles --source <source-id> --since <date> --limit 5` 跑通。
- 支持 `--profile politics-theory` 或明确说明为何不适用。
- 至少有 fixture 覆盖列表发现、正文解析、噪声过滤。
- Markdown 不保留导航、页脚、分享按钮、二维码。
- SQLite 有 `url/title/source/published_at/tags/topics/markdown_path/image_paths_json`。
- 重复运行不产生重复记录。

## 暂不主动采集

- 粉笔、中公、华图等商业题库站：只处理公开可访问下载页或用户自备文件，不做登录、付费、验证码绕过。
- 社交平台、论坛、公众号镜像：来源稳定性和版权边界不足，暂不作为自动采集来源。
