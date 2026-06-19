# 来源扩展路线图

## 总原则

- 只采集公开可访问内容，不绕过登录、验证码、付费墙或访问控制。
- 每个来源先做小样本 adapter，再扩大采集窗口。
- 原始 HTML 保存到 `data/raw/`，清洗 Markdown 保存到 vault，SQLite 保存索引。
- 文章正文、图片、来源 URL、发布时间、栏目/期数信息必须可追溯。
- 来源质量优先于数量：先保证正文清洗干净、标签不过度、图片能本地化，再扩源。

## 已实现来源

| Source ID | 来源 | 重点内容 | 当前状态 | 归档规则 |
| --- | --- | --- | --- | --- |
| `qstheory` | 求是网 | 《求是》期刊文章、理论文章 | 已实现 | 按期数：`qstheory/YYYY/YYYY年第N期/title.md` |
| `people-commentary` | 人民网观点/人民网评 | 时评、申论表达、热点分析 | 已实现 | 按日期：`people-commentary/YYYY/MM-DD/title.md` |
| `gov-policy` | 中国政府网政策/政策解读 | 最新政策、国务院文件、政策问答 | 已实现 | 按日期：`gov-policy/YYYY/MM-DD/title.md` |
| `xinhua-politics` | 新华网时政 | 时政新闻、新华社通稿、新华典评 | 已实现 | 按日期：`xinhua-politics/YYYY/MM-DD/title.md` |
| `sichuan-gov` | 四川省政府 | 四川本地政策、政策解读、地方治理素材 | 已实现 | 按日期：`sichuan-gov/YYYY/MM-DD/title.md` |
| `chongqing-gov` | 重庆市政府 | 重庆本地政策、政策解读、地方治理素材 | 已实现 | 按日期：`chongqing-gov/YYYY/MM-DD/title.md` |

`qstheory` 当前能力：

- 从目录页展开年度目录、期刊目录、正文文章。
- 支持最近一年滚动窗口。
- 正文图片下载到同一期文件夹下的 `附件/title/`。
- 自动生成保守版 `tags` 和 `topics`，DeepSeek 可选复核。

`people-commentary` 当前能力：

- 从人民网观点入口页发现同域公开文章。
- 优先匹配人民网常见文章 URL：`/n1/YYYY/MMDD/...html`。
- 解析标题、来源、发布时间、作者、正文、正文图片。
- 正文图片下载到同一日期目录下的 `附件/title/`。
- 跳过外域链接、静态资源、旧日期文章。

`gov-policy` 当前能力：

- 从中国政府网公开 JSON 数据源读取最新政策和政策解读。
- 只保留 `www.gov.cn/zhengce/` 下的 `content_*.htm` 政策正文页。
- 解析标题、发布机构/来源、发布时间、作者、正文、正文图片。
- 正文图片下载到同一日期目录下的 `附件/title/`。
- 跳过专题首页、专栏首页、外域链接、旧日期文章和装饰图片。

`xinhua-politics` 当前能力：

- 从新华网时政频道发现公开文章。
- 只保留 `www.news.cn/politics/YYYYMMDD/.../c.html` 文章页。
- 解析标题、来源、发布时间、正文和正文图片。
- 跳过图片频道、专题页、二维码、分享图和静态资源。

`sichuan-gov` / `chongqing-gov` 当前能力：

- 从省/市政府首页、政策文件、政策解读栏目发现公开文章。
- 优先服务地方省考/市考素材，保留本地政策文件和政策解读。
- 解析政府网站元数据、正文容器、发布时间、来源和正文图片。
- 对四川站点启用 curl fallback，以应对 urllib TLS 握手偶发超时。

## 下一批优先来源

| 优先级 | Source ID | 来源 | 主要用途 | 初始入口 | 归档建议 |
| --- | --- | --- | --- | --- | --- |
| P1 | `stats-gov` | 国家统计局 | 统计公报、经济数据、图表材料 | `https://www.stats.gov.cn/` | 按年度+主题 |
| P2 | `people-daily` | 人民日报/人民网 | 重要评论、理论版、人民时评 | 人民网/人民日报公开页面 | 按栏目+日期 |
| P2 | `gmw-theory` | 光明网理论 | 理论文章、文化与治理材料 | `https://theory.gmw.cn/` | 按栏目+日期 |
| P2 | `mohrss` | 人社部 | 就业、社保、人才、劳动权益 | `https://www.mohrss.gov.cn/` | 按主题+日期 |
| P2 | `ndrc` | 国家发展改革委 | 宏观经济、产业政策、区域协调 | `https://www.ndrc.gov.cn/` | 按主题+日期 |
| P2 | `mee` | 生态环境部 | 生态文明、绿色转型、污染防治 | `https://www.mee.gov.cn/` | 按主题+日期 |
| P2 | `mca` | 民政部 | 基层治理、养老、社会救助、社区建设 | `https://www.mca.gov.cn/` | 按主题+日期 |

## Adapter 实现顺序

1. `stats-gov`：重点抓统计公报和数据解读，不追求全站采集。
2. `people-daily`：优先做人民日报公开评论/理论类材料，不做全站。
3. `mohrss`、`ndrc`、`mee`、`mca`：按申论高频主题逐个落地。

候选来源备忘录见 `docs/SOURCE_BACKLOG.md`。

## 每个新来源的验收标准

- 能用 `examdb ingest articles --source <source-id> --since <date> --limit 5` 跑通。
- 至少 3 个 fixture 覆盖：普通文章、带图文章、噪声较多文章。
- Markdown 不保留导航、页脚、分享按钮、二维码。
- 图片本地化到文章同级归档目录下的 `附件/`。
- SQLite 有 `url/title/source/published_at/tags/topics/markdown_path/image_paths_json`。
- 重复运行不产生重复记录。

## 暂不主动采集

- 粉笔、中公、华图等商业题库站：只处理公开可访问下载页或用户自备文件，不做登录、付费、验证码绕过。
- 社交平台、论坛、公众号镜像：来源稳定性和版权边界不足，暂不作为自动采集来源。
