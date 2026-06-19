from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from urllib.parse import urlparse

from examdb.ai import suggest_policy_metadata_with_ai
from examdb.cleaning import clean_article_text, extract_first, html_to_markdown, html_to_text
from examdb.ingest.html_helpers import (
    extract_balanced_div,
    extract_date,
    extract_detail_html,
    extract_links,
    extract_title,
    fetch_html,
    normalize_url,
    url_date_from_people_url,
)
from examdb.models import ArticleRecord


INDEX_URL = "http://opinion.people.com.cn/"
DEFAULT_MAX_PAGES = 500


class PeopleCommentarySource:
    name = "people-commentary"

    def __init__(self, index_url: str = INDEX_URL) -> None:
        self.index_url = index_url

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        html = self.fetch_article_html(self.index_url)
        queue = self._extract_links(html, self.index_url, since=None)
        urls: list[str] = []
        seen: set[str] = set()
        max_pages = self._max_pages()

        while queue and (limit is None or len(urls) < limit) and len(seen) < max_pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            if self._is_article_url(url):
                url_date = url_date_from_people_url(url)
                if url_date and date.fromisoformat(url_date) < since:
                    continue
                urls.append(url)
                continue
            if not self._is_directory_url(url):
                continue
            try:
                page_html = self.fetch_article_html(url)
            except Exception:
                continue
            for child_url in self._extract_links(page_html, url, since=since):
                if child_url not in seen and child_url not in queue:
                    queue.append(child_url)
        return urls

    def fetch_article_html(self, url: str) -> str:
        return fetch_html(url)

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        title = extract_title(html)
        text = html_to_text(html)
        published_at = extract_date(text) or url_date_from_people_url(url)
        source = (
            extract_first([r"来源[:：]\s*([^\n ]+)", r"来源\s*[:：]?\s*([^\n ]+)"], text)
            or "人民网观点"
        )
        authors_text = extract_first([r"作者[:：]\s*([^\n]+)", r"作者\s+([^\n]+)"], text)
        authors = [item.strip() for item in re.split(r"[、,， ]+", authors_text or "") if item.strip()]

        detail_html = self._extract_body_html(html)
        markdown_content, image_urls = html_to_markdown(detail_html, url)
        content = clean_article_text(markdown_content)
        if not content:
            content = clean_article_text(html_to_text(detail_html))
        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        metadata = suggest_policy_metadata_with_ai(title, content)
        return ArticleRecord(
            id=f"people-commentary-{content_hash}",
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

    def _extract_links(self, html: str, base_url: str, since: date | None) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for url in extract_links(html, base_url):
            if not self._is_people_url(url):
                continue
            if self._is_asset_url(url):
                continue
            url_date = url_date_from_people_url(url)
            if since and url_date and date.fromisoformat(url_date) < since:
                continue
            if url not in seen:
                seen.add(url)
                links.append(url)
        return links

    def _is_people_url(self, url: str) -> bool:
        host = urlparse(url).netloc
        return host.endswith("opinion.people.com.cn")

    def _is_article_url(self, url: str) -> bool:
        return bool(re.search(r"opinion\.people\.com\.cn/n1/20\d{2}/\d{4}/c\d+-\d+\.html$", url))

    def _is_directory_url(self, url: str) -> bool:
        if self._is_article_url(url):
            return False
        if self._is_asset_url(url):
            return False
        return self._is_people_url(url)

    def _is_asset_url(self, url: str) -> bool:
        lower = normalize_url(url).lower()
        return lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".mp4", ".css", ".js"))

    def _filter_body_images(self, image_urls: list[str]) -> list[str]:
        filtered: list[str] = []
        for image_url in image_urls:
            lower = image_url.lower()
            if any(token in lower for token in ("logo", "weixin", "wx", "qrcode", "icon", "share")):
                continue
            if image_url not in filtered:
                filtered.append(image_url)
        return filtered

    def _extract_body_html(self, html: str) -> str:
        for attr, token in [
            ("id", "rm_txt_zw"),
            ("class", "rm_txt_con"),
            ("id", "rwb_zw"),
            ("id", "p_content"),
        ]:
            detail_html = extract_balanced_div(html, attr, token)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        return extract_detail_html(
            html,
            [
                r'<article[^>]*>(.*?)</article>',
                r'<div[^>]+class=["\'][^"\']*(?:article|text|content|show_text)[^"\']*["\'][^>]*>(.*?)(?:</div>\s*<div[^>]+class=["\'][^"\']*(?:edit|share|page|copyright)|</article>)',
            ],
        )

    def _max_pages(self) -> int:
        raw_value = os.getenv("PEOPLE_COMMENTARY_MAX_PAGES")
        if not raw_value:
            return DEFAULT_MAX_PAGES
        try:
            return max(1, int(raw_value))
        except ValueError:
            return DEFAULT_MAX_PAGES
