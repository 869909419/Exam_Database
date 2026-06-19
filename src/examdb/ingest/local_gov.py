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


class LocalGovSource:
    name = "local-gov"
    display_name = "地方政府"
    host = ""
    entry_urls: tuple[str, ...] = ()
    article_pattern = r""
    source_prefix = "地方政府"
    max_pages_env = "LOCAL_GOV_MAX_PAGES"
    default_max_pages = 500
    allowed_path_tokens: tuple[str, ...] = ()
    rejected_path_tokens: tuple[str, ...] = ()

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        max_pages = self._max_pages()
        for entry_url in self.entry_urls:
            if len(seen) >= max_pages or (limit is not None and len(urls) >= limit):
                break
            try:
                html = self.fetch_article_html(entry_url)
            except Exception:
                continue
            for url in self._extract_links(html, entry_url):
                if len(seen) >= max_pages or (limit is not None and len(urls) >= limit):
                    break
                seen.add(url)
                if not self._is_article_url(url):
                    continue
                url_date = self._date_from_url(url)
                if url_date and date.fromisoformat(url_date) < since:
                    continue
                urls.append(url)
        return urls

    def fetch_article_html(self, url: str) -> str:
        return fetch_html(url, timeout=8)

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        title = self._extract_local_title(html)
        text = html_to_text(html)
        published_at = self._extract_published_at(html, text) or self._date_from_url(url)
        source = self._extract_source(html, text)
        authors = self._extract_authors(html)
        detail_html = self._extract_body_html(html)

        markdown_content, image_urls = html_to_markdown(detail_html, url)
        content = clean_article_text(markdown_content)
        if not content:
            meta_description = extract_meta_content(html, "Description")
            content = clean_article_text(meta_description or html_to_text(detail_html))

        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        metadata = suggest_policy_metadata_with_ai(title, content)
        return ArticleRecord(
            id=f"{self.name}-{content_hash}",
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            authors=authors,
            tags=metadata.tags,
            topics=metadata.topics,
            image_urls=self._filter_body_images(image_urls),
            content=content,
            content_hash=content_hash,
        )

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for url in extract_links(html, base_url):
            if not self._is_same_host(url):
                continue
            if self._is_asset_url(url):
                continue
            if url not in seen:
                seen.add(url)
                links.append(url)
        return links

    def _is_same_host(self, url: str) -> bool:
        return urlparse(url).netloc == self.host

    def _is_article_url(self, url: str) -> bool:
        path = urlparse(url).path
        if self.allowed_path_tokens and not any(token in path for token in self.allowed_path_tokens):
            return False
        if any(token in path for token in self.rejected_path_tokens):
            return False
        return bool(re.search(self.article_pattern, path))

    def _is_asset_url(self, url: str) -> bool:
        lower = normalize_url(url).lower()
        return lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".mp4", ".css", ".js"))

    def _date_from_url(self, url: str) -> str | None:
        path = urlparse(url).path
        match = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", path)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        match = re.search(r"/(20\d{2})(\d{2})/t(20\d{2})(\d{2})(\d{2})_", path)
        if match:
            _, _, year, month, day = match.groups()
            return f"{year}-{month}-{day}"
        return None

    def _extract_local_title(self, html: str) -> str:
        title = (
            extract_meta_content(html, "ArticleTitle")
            or extract_meta_content(html, "articleTitle")
            or extract_title(html)
        )
        title = clean_html_title(title)
        title = re.sub(r"[_-].*(四川省人民政府|重庆市人民政府网)$", "", title).strip()
        return title or "未命名文章"

    def _extract_published_at(self, html: str, text: str) -> str | None:
        for key in ["PubDate", "pubdate", "publishdate"]:
            value = extract_meta_content(html, key)
            if value:
                parsed = extract_date(value)
                if parsed:
                    return parsed
        return extract_date(text)

    def _extract_source(self, html: str, text: str) -> str:
        source = extract_meta_content(html, "ContentSource") or extract_meta_content(html, "source")
        if source:
            return f"{self.source_prefix}-{clean_html_title(source)}"
        source = extract_first([r"(?:来源|信息来源)[:：]\s*([^\n ]+)"], text)
        if source:
            return f"{self.source_prefix}-{source}"
        return self.source_prefix

    def _extract_authors(self, html: str) -> list[str]:
        author = extract_meta_content(html, "Author") or extract_meta_content(html, "author")
        if not author:
            return []
        if author in {self.source_prefix, self.display_name}:
            return []
        return [item.strip() for item in re.split(r"[、,， ]+", author) if item.strip()]

    def _extract_body_html(self, html: str) -> str:
        for element_id in ["cmsArticleContent", "articlecontent"]:
            detail_html = extract_element_by_id(html, element_id)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        for attr, token in [
            ("class", "contText"),
            ("class", "TRS_UEDITOR"),
            ("id", "zoom"),
            ("class", "article-content"),
            ("class", "detail-content"),
            ("class", "pages_content"),
        ]:
            detail_html = extract_balanced_div(html, attr, token)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        meta_description = extract_meta_content(html, "Description")
        if meta_description:
            return "\n".join(f"<p>{line}</p>" for line in meta_description.splitlines() if line.strip())
        return html

    def _filter_body_images(self, image_urls: list[str]) -> list[str]:
        filtered: list[str] = []
        for image_url in image_urls:
            lower = image_url.lower()
            if any(token in lower for token in ("logo", "qrcode", "icon", "share", "head-logo", "zcwjic")):
                continue
            if image_url not in filtered:
                filtered.append(image_url)
        return filtered

    def _max_pages(self) -> int:
        raw_value = os.getenv(self.max_pages_env)
        if not raw_value:
            return self.default_max_pages
        try:
            return max(1, int(raw_value))
        except ValueError:
            return self.default_max_pages


class SichuanGovSource(LocalGovSource):
    name = "sichuan-gov"
    display_name = "四川省政府"
    host = "www.sc.gov.cn"
    source_prefix = "四川省政府"
    max_pages_env = "SICHUAN_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.sc.gov.cn/",
        "https://www.sc.gov.cn/10462/c110518/list_ft.shtml",
        "https://www.sc.gov.cn/10462/10464/13298/zcjd.shtml",
        "https://www.sc.gov.cn/10462/zfwjts/zfwj.shtml",
    )
    article_pattern = r"/10462/.+/(20\d{2})/\d{1,2}/\d{1,2}/[a-z0-9]+\.shtml$"
    allowed_path_tokens = (
        "/zfwjts/",
        "/c110518/",
        "/10464/13298/",
        "/c105962s/",
        "/c110462/",
        "/10464/10856/",
    )
    rejected_path_tokens = ("/syftyg/",)


class ChongqingGovSource(LocalGovSource):
    name = "chongqing-gov"
    display_name = "重庆市政府"
    host = "www.cq.gov.cn"
    source_prefix = "重庆市政府"
    max_pages_env = "CHONGQING_GOV_MAX_PAGES"
    entry_urls = (
        "https://www.cq.gov.cn/",
        "https://www.cq.gov.cn/zwgk/zfxxgkml/szfwj/",
        "https://www.cq.gov.cn/zwgk/zfxxgkml/zcjd_120614/",
    )
    article_pattern = r"/zwgk/.+/(20\d{4})/t20\d{6}_\d+\.html$"
    allowed_path_tokens = ("/zwgk/zfxxgkml/szfwj/", "/zwgk/zfxxgkml/zcjd_120614/")
