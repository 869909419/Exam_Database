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


INDEX_URL = "https://www.news.cn/politics/"
ENTRY_URLS = (
    INDEX_URL,
    "https://www.news.cn/politics/leaders/",
    "https://www.news.cn/politics/xxjxs/",
)
DEFAULT_MAX_PAGES = 300


class XinhuaPoliticsSource:
    name = "xinhua-politics"

    def __init__(self, index_url: str = INDEX_URL, entry_urls: tuple[str, ...] | None = None) -> None:
        self.index_url = index_url
        self.entry_urls = entry_urls or ENTRY_URLS

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for seed_url in self._seed_urls():
            if not self._append_url(seed_url, since, urls, seen, limit):
                continue
            return urls
        for entry_url in self.entry_urls:
            if len(seen) >= self._max_pages() or (limit is not None and len(urls) >= limit):
                break
            try:
                html = self.fetch_article_html(entry_url)
            except Exception:
                continue
            for url in self._extract_links(html, entry_url):
                if len(seen) >= self._max_pages():
                    break
                if self._append_url(url, since, urls, seen, limit):
                    return urls
        return urls

    def fetch_article_html(self, url: str) -> str:
        return fetch_html(url)

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        title = self._extract_xinhua_title(html)
        text = html_to_text(html)
        published_at = self._extract_published_at(html, text) or self._date_from_url(url)
        source = self._extract_source(text)
        detail_html = self._extract_body_html(html)
        markdown_content, image_urls = html_to_markdown(detail_html, url)
        content = clean_article_text(markdown_content)
        if not content:
            content = clean_article_text(html_to_text(detail_html))

        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        metadata = suggest_policy_metadata_with_ai(title, content)
        return ArticleRecord(
            id=f"xinhua-politics-{content_hash}",
            title=title,
            source=source,
            url=url,
            published_at=published_at,
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
            if not self._is_xinhua_url(url):
                continue
            if self._is_asset_url(url):
                continue
            if url not in seen:
                seen.add(url)
                links.append(url)
        return links

    def _is_xinhua_url(self, url: str) -> bool:
        return urlparse(url).netloc.endswith("news.cn")

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return bool(re.search(r"/politics/(?:leaders/)?20\d{6}/[a-z0-9]+/c\.html$", parsed.path))

    def _is_asset_url(self, url: str) -> bool:
        lower = normalize_url(url).lower()
        return lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".mp4", ".css", ".js"))

    def _date_from_url(self, url: str) -> str | None:
        match = re.search(r"/politics/(?:leaders/)?(20\d{2})(\d{2})(\d{2})/", url)
        if not match:
            return None
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    def _append_url(self, url: str, since: date, urls: list[str], seen: set[str], limit: int | None) -> bool:
        if limit is not None and len(urls) >= limit:
            return True
        if not self._is_article_url(url):
            return False
        url_date = self._date_from_url(url)
        if url_date and date.fromisoformat(url_date) < since:
            return False
        if url in seen:
            return False
        seen.add(url)
        urls.append(url)
        return limit is not None and len(urls) >= limit

    def _extract_xinhua_title(self, html: str) -> str:
        title = extract_first([r'<span[^>]+class=["\']title["\'][^>]*>(.*?)</span>'], html)
        if title:
            return clean_html_title(title)
        title = extract_meta_content(html, "ArticleTitle") or extract_title(html)
        return re.sub(r"[-_].*新华网$", "", clean_html_title(title)).strip() or "未命名文章"

    def _extract_published_at(self, html: str, text: str) -> str | None:
        pubdate = extract_meta_content(html, "PubDate")
        if pubdate:
            parsed = extract_date(pubdate)
            if parsed:
                return parsed
        parsed = extract_date(text)
        if parsed:
            return parsed
        match = re.search(r"(20\d{2})\s*(\d{2})/(\d{2})\s*(\d{2}:\d{2}:\d{2})?", text)
        if match:
            year, month, day, _ = match.groups()
            return f"{year}-{month}-{day}"
        return None

    def _extract_source(self, text: str) -> str:
        return extract_first([r"来源[:：]\s*([^\n]+)"], text) or "新华网-时政"

    def _extract_body_html(self, html: str) -> str:
        detail_content = extract_element_by_id(html, "detailContent")
        if detail_content and len(clean_article_text(html_to_text(detail_content))) >= 20:
            return detail_content
        for attr, token in [("id", "detailContent"), ("id", "detail"), ("class", "main-left")]:
            detail_html = extract_balanced_div(html, attr, token)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        return html

    def _filter_body_images(self, image_urls: list[str]) -> list[str]:
        filtered: list[str] = []
        for image_url in image_urls:
            lower = image_url.lower()
            if any(token in lower for token in ("qrcode", "qr", "code", "logo", "share", "app.png", "zxcode")):
                continue
            if image_url not in filtered:
                filtered.append(image_url)
        return filtered

    def _max_pages(self) -> int:
        raw_value = os.getenv("XINHUA_POLITICS_MAX_PAGES")
        if not raw_value:
            return DEFAULT_MAX_PAGES
        try:
            return max(1, int(raw_value))
        except ValueError:
            return DEFAULT_MAX_PAGES

    def _seed_urls(self) -> list[str]:
        urls: list[str] = []
        raw_value = os.getenv("XINHUA_POLITICS_SEED_URLS")
        if raw_value:
            urls.extend(item.strip() for item in re.split(r"[\n,]", raw_value) if item.strip())
        seed_file = os.getenv("XINHUA_POLITICS_SEED_FILE")
        if seed_file and os.path.exists(seed_file):
            with open(seed_file, encoding="utf-8") as handle:
                for line in handle:
                    value = line.strip()
                    if not value or value.startswith("#"):
                        continue
                    urls.append(value.split("|")[-1].strip())
        return urls
