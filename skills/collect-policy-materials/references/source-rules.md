# Source Rules

- Keep raw HTML in `data/raw/articles/<source>/`.
- Keep cleaned intermediate Markdown in `data/processed/articles/<source>/`.
- Write 求是 notes to `vault/资料库/政策理论/qstheory/<YYYY>/<YYYY年第N期>/<title>.md` when `source` contains an issue like `《求是》2026/12`.
- For sources without issue metadata, write notes to `vault/资料库/政策理论/<source>/<YYYY>/<MM-DD>/<title>.md`.
- Download article body images to `附件/<title>/` under the same archive folder as the article and reference them with relative Markdown image links.
- Do not keep site logos, share buttons, QR codes, or footer images as article images.
- For `people-commentary`, only collect public `opinion.people.com.cn` article pages matching `/n1/YYYY/MMDD/...html`; skip external domains, channels, topics, static assets, videos, and old dates.
- For `gov-policy`, use the public China Government Network JSON feeds for latest policies and policy interpretations; only collect `www.gov.cn/zhengce/` article pages ending in `content_*.htm`, and skip topic/index pages.
- For `xinhua-politics`, only collect `www.news.cn/politics/YYYYMMDD/.../c.html`; skip photo/video channels, topic pages, QR codes, and share images.
- For `sichuan-gov` and `chongqing-gov`, keep to official government domains and prioritize policy files, policy interpretations, government work reports, livelihood, and grassroots governance materials.
- Preserve source URL, published date, authors, and content hash.
- Remove navigation, related links, footer, sharing tools, editor labels, and repeated boilerplate.
- Assign 2-6 policy tags from `docs/TAXONOMY.md`.
- Do not scrape private, paid, login-only, or captcha-protected content.
