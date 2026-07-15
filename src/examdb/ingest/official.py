from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from urllib.parse import urlparse

from examdb.ai import suggest_policy_metadata_with_ai
from examdb.cleaning import clean_article_text, extract_first, html_to_markdown, html_to_text
from examdb.ingest.html_helpers import (
    clean_html_title,
    extract_balanced_div,
    extract_date,
    extract_element_by_id,
    extract_links,
    extract_meta_content,
    extract_title,
    fetch_html,
    normalize_url,
)
from examdb.models import ArticleRecord


class OfficialArticleSource:
    name = "official"
    display_name = "官方来源"
    host = ""
    source_prefix = "官方来源"
    entry_urls: tuple[str, ...] = ()
    article_patterns: tuple[str, ...] = ()
    allowed_path_tokens: tuple[str, ...] = ()
    rejected_path_tokens: tuple[str, ...] = ()
    max_pages_env = "OFFICIAL_MAX_PAGES"
    default_max_pages = 500

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        max_pages = self._max_pages()
        for seed_url in self._seed_urls():
            if self._append_candidate(seed_url, since, urls, seen, limit):
                return urls
        for entry_url in self.entry_urls:
            if len(seen) >= max_pages or (limit is not None and len(urls) >= limit):
                break
            try:
                html = self.fetch_article_html(entry_url)
            except Exception:
                continue
            for url in extract_links(html, entry_url):
                if len(seen) >= max_pages or (limit is not None and len(urls) >= limit):
                    break
                if url in seen:
                    continue
                seen.add(url)
                self._append_candidate(url, since, urls, seen, limit)
        return urls

    def fetch_article_html(self, url: str) -> str:
        return fetch_html(url, timeout=10)

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        title = self._extract_title(html)
        text = html_to_text(html)
        published_at = self._extract_published_at(html, text) or self._date_from_url(url)
        source = self._extract_source(html, text)
        detail_html = self._extract_body_html(html)
        markdown_content, image_urls = html_to_markdown(detail_html, url)
        content = clean_article_text(markdown_content)
        if not content:
            content = clean_article_text(html_to_text(detail_html))

        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        metadata = suggest_policy_metadata_with_ai(title, content)
        return ArticleRecord(
            id=f"{self.name}-{content_hash}",
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            authors=self._extract_authors(html),
            tags=metadata.tags,
            topics=metadata.topics,
            image_urls=self._filter_body_images(image_urls),
            content=content,
            content_hash=content_hash,
        )

    def _append_candidate(
        self,
        url: str,
        since: date,
        urls: list[str],
        seen: set[str],
        limit: int | None,
    ) -> bool:
        if limit is not None and len(urls) >= limit:
            return True
        url = normalize_url(url)
        if not self._is_article_url(url):
            return False
        url_date = self._date_from_url(url)
        if url_date and date.fromisoformat(url_date) < since:
            return False
        if url not in urls:
            urls.append(url)
        return limit is not None and len(urls) >= limit

    def _extract_candidate_links_for_test(self, html: str, base_url: str) -> list[str]:
        return [url for url in extract_links(html, base_url) if self._is_article_url(url)]

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != self.host:
            return False
        path = parsed.path
        if self.allowed_path_tokens and not any(token in path for token in self.allowed_path_tokens):
            return False
        if any(token in path for token in self.rejected_path_tokens):
            return False
        if self._is_asset_url(url):
            return False
        return any(re.search(pattern, path) for pattern in self.article_patterns)

    def _is_asset_url(self, url: str) -> bool:
        lower = normalize_url(url).lower()
        return lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".mp4", ".css", ".js"))

    def _date_from_url(self, url: str) -> str | None:
        path = urlparse(url).path
        match = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", path)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        match = re.search(r"/t(20\d{2})(\d{2})(\d{2})_", path)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        match = re.search(r"/(20\d{2})(\d{2})(\d{2})/", path)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        match = re.search(r"/(20\d{2})(\d{2})/", path)
        if match:
            year, month = match.groups()
            return f"{int(year):04d}-{int(month):02d}-01"
        return None

    def _extract_title(self, html: str) -> str:
        title = (
            extract_meta_content(html, "ArticleTitle")
            or extract_meta_content(html, "articleTitle")
            or extract_meta_content(html, "title")
            or extract_title(html)
        )
        title = clean_html_title(title)
        title = re.sub(r"[_-].*(国家民委|科技部|人力资源和社会保障部|中央纪委国家监委|国家统计局).*$", "", title).strip()
        return title or "未命名文章"

    def _extract_published_at(self, html: str, text: str) -> str | None:
        for key in ["PubDate", "pubdate", "publishdate", "date", "firstpublishedtime"]:
            value = extract_meta_content(html, key)
            if value:
                parsed = extract_date(value)
                if parsed:
                    return parsed
        return extract_date(text)

    def _extract_source(self, html: str, text: str) -> str:
        source = (
            extract_meta_content(html, "ContentSource")
            or extract_meta_content(html, "source")
            or extract_first([r"(?:来源|信息来源)[:：]\s*([^\n ]+)"], text)
        )
        if source:
            return f"{self.source_prefix}-{clean_html_title(source)}"
        return self.source_prefix

    def _extract_authors(self, html: str) -> list[str]:
        author = extract_meta_content(html, "Author") or extract_meta_content(html, "author")
        if not author:
            return []
        return [item.strip() for item in re.split(r"[、,， ]+", author) if item.strip()]

    def _extract_body_html(self, html: str) -> str:
        for element_id in ["UCAP-CONTENT", "zoom", "Zoom", "article", "articleContent", "content", "detailContent", "TRS_UEDITOR"]:
            detail_html = extract_element_by_id(html, element_id)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        for attr, token in [
            ("class", "TRS_UEDITOR"),
            ("class", "article-content"),
            ("class", "article_con"),
            ("class", "content"),
            ("class", "detail-content"),
            ("class", "main-text"),
            ("class", "pages_content"),
            ("class", "xl-article"),
        ]:
            detail_html = extract_balanced_div(html, attr, token)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        return html

    def _filter_body_images(self, image_urls: list[str]) -> list[str]:
        filtered: list[str] = []
        for image_url in image_urls:
            lower = image_url.lower()
            if any(token in lower for token in ("logo", "qrcode", "qr", "icon", "share", "wx", "weixin")):
                continue
            if image_url not in filtered:
                filtered.append(image_url)
        return filtered

    def _seed_urls(self) -> list[str]:
        urls: list[str] = []
        env_value = os.getenv(f"{self.name.upper().replace('-', '_')}_SEED_URLS")
        if env_value:
            urls.extend(item.strip() for item in re.split(r"[\n,]", env_value) if item.strip())
        seed_file = os.getenv(f"{self.name.upper().replace('-', '_')}_SEED_FILE")
        if seed_file and os.path.exists(seed_file):
            with open(seed_file, encoding="utf-8") as handle:
                for line in handle:
                    value = line.strip()
                    if not value or value.startswith("#"):
                        continue
                    urls.append(value.split("|")[-1].strip())
        return urls

    def _max_pages(self) -> int:
        raw_value = os.getenv(self.max_pages_env)
        if not raw_value:
            return self.default_max_pages
        try:
            return max(1, int(raw_value))
        except ValueError:
            return self.default_max_pages


class NeacGovSource(OfficialArticleSource):
    name = "neac-gov"
    display_name = "国家民委"
    host = "www.neac.gov.cn"
    source_prefix = "国家民委"
    max_pages_env = "NEAC_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.neac.gov.cn/seac/xwzx/index.shtml",
        "https://www.neac.gov.cn/seac/xxgk/zcjd.shtml",
        "https://www.neac.gov.cn/seac/xxgk/zcwj.shtml",
        "https://www.neac.gov.cn/seac/c103391/common_list.shtml",
    )
    article_patterns = (
        r"/seac/.+/(20\d{4}|20\d{6}|20\d{2}/\d{1,2}/\d{1,2})/.+\.(?:shtml|html)$",
        r"/seac/.+/20\d{4,6}/[^/]+\.(?:shtml|html)$",
    )
    allowed_path_tokens = ("/seac/",)


class MostGovSource(OfficialArticleSource):
    name = "most-gov"
    display_name = "科技部"
    host = "www.most.gov.cn"
    source_prefix = "科技部"
    max_pages_env = "MOST_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.most.gov.cn/kjbgz/",
        "https://www.most.gov.cn/xxgk/xinxifenlei/fdzdgknr/fgzc/",
        "https://www.most.gov.cn/xxgk/xinxifenlei/fdzdgknr/fgzc/zcjd/",
        "https://www.most.gov.cn/kjbgz/2024/",
    )
    article_patterns = (r"/.+/t20\d{6}_\d+\.html$", r"/.+/20\d{6}/t20\d{6}_\d+\.html$")


class MohrssGovSource(OfficialArticleSource):
    name = "mohrss-gov"
    display_name = "人力资源和社会保障部"
    host = "www.mohrss.gov.cn"
    source_prefix = "人社部"
    max_pages_env = "MOHRSS_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.mohrss.gov.cn/SYrlzyhshbzb/zwgk/zcwj/",
        "https://www.mohrss.gov.cn/SYrlzyhshbzb/zwgk/zcjd/",
        "https://www.mohrss.gov.cn/SYrlzyhshbzb/dongtaixinwen/",
    )
    article_patterns = (r"/.+/t20\d{6}_\d+\.html$",)
    allowed_path_tokens = ("/SYrlzyhshbzb/",)


class CcdiGovSource(OfficialArticleSource):
    name = "ccdi-gov"
    display_name = "中央纪委国家监委"
    host = "www.ccdi.gov.cn"
    source_prefix = "中央纪委国家监委"
    max_pages_env = "CCDI_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.ccdi.gov.cn/toutiaon/",
        "https://www.ccdi.gov.cn/yaowenn/",
        "https://www.ccdi.gov.cn/llxx/",
    )
    article_patterns = (r"/.+/t20\d{6}_\d+\.html$",)


class StatsGovSource(OfficialArticleSource):
    name = "stats-gov"
    display_name = "国家统计局"
    host = "www.stats.gov.cn"
    source_prefix = "国家统计局"
    max_pages_env = "STATS_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.stats.gov.cn/sj/zxfb/",
        "https://www.stats.gov.cn/sj/sjjd/",
        "https://www.stats.gov.cn/sj/tjgb/",
    )
    article_patterns = (r"/sj/.+/(20\d{4}|20\d{6}|20\d{2}/\d{1,2}/\d{1,2})/.+\.(?:html|shtml)$",)
    allowed_path_tokens = ("/sj/",)
