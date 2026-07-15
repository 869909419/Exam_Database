from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from examdb.ai import suggest_policy_metadata_with_ai
from examdb.cleaning import clean_article_text, extract_first, html_to_markdown, html_to_text
from examdb.models import ArticleRecord


INDEX_URL = "https://www.qstheory.cn/qs/mulu.htm"
WEB_INDEX_URL = "https://www.qstheory.cn/"
WEB_ENTRY_URLS = (
    WEB_INDEX_URL,
    "https://www.qstheory.cn/qsyw/index.htm",
    "https://www.qstheory.cn/qswp.htm",
    "https://www.qstheory.cn/qslgxd/index.htm",
    "https://www.qstheory.cn/politics/index.htm",
    "https://www.qstheory.cn/cpc/index.htm",
    "https://www.qstheory.cn/science/index.htm",
    "https://www.qstheory.cn/qszq/xxbj/index.htm",
    "https://www.qstheory.cn/qszq/llwx/index.htm",
    "https://www.qstheory.cn/v9zhuanqu/zhuanqu/llzt/index.htm",
)
WEB_DIRECTORY_PATH_TOKENS = (
    "/qsyw/",
    "/qswp",
    "/qslgxd/",
    "/politics/",
    "/cpc/",
    "/science/",
    "/qszq/",
    "/v9zhuanqu/",
)
DEFAULT_MAX_PAGES = 2000
DEFAULT_WEB_MAX_PAGES = 160


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        href = attrs_map.get("href")
        if href:
            self.links.append(urljoin(self.base_url, href))


class QSTheorySource:
    name = "qstheory"

    def __init__(self, index_url: str = INDEX_URL) -> None:
        self.index_url = index_url

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        html = self.fetch_article_html(self.index_url)
        queue = self._extract_article_urls(html, self.index_url, None)
        queue.extend(self._extract_directory_urls(html, self.index_url, since))
        urls: list[str] = []
        seen_pages: set[str] = set()
        max_pages = self._max_pages()

        while queue and (limit is None or len(urls) < limit) and len(seen_pages) < max_pages:
            page_url = queue.pop(0)
            if page_url in seen_pages:
                continue
            if self._is_index_url(page_url):
                continue
            seen_pages.add(page_url)
            try:
                page_html = self.fetch_article_html(page_url)
            except Exception:
                continue
            page_date = self._extract_date(html_to_text(page_html))
            if self._is_listing_page(page_html):
                child_article_urls = self._extract_article_urls(page_html, page_url, since)
                if self._is_issue_listing_page(page_html):
                    for child_url in child_article_urls:
                        if child_url not in urls:
                            urls.append(child_url)
                        if limit is not None and len(urls) >= limit:
                            break
                else:
                    for child_url in child_article_urls:
                        if child_url not in seen_pages and child_url not in queue:
                            queue.append(child_url)
                for child_url in self._extract_directory_urls(page_html, page_url, since):
                    if child_url not in seen_pages and child_url not in queue:
                        queue.append(child_url)
                continue
            if page_date and date.fromisoformat(page_date) < since:
                continue
            urls.append(page_url)
        return urls

    def fetch_article_html(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "ExamDB/0.1 (+public research archive)"})
        with urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        title = (
            extract_first([r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"], html)
            or "未命名文章"
        )
        title = re.sub(r"[_-].*$", "", title).strip()

        text = html_to_text(html)
        published_at = self._extract_date(text)
        source = extract_first([r"来源[:：]\s*([^\n ]+)", r"来源\s+([^\n ]+)"], text) or "求是网"
        authors_text = extract_first([r"作者[:：]\s*([^\n]+)"], text)
        authors = [item.strip() for item in re.split(r"[、,， ]+", authors_text or "") if item.strip()]
        detail_html = self._detail_html(html)
        markdown_content, image_urls = html_to_markdown(detail_html, url)
        content = clean_article_text(markdown_content)
        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        metadata = suggest_policy_metadata_with_ai(title, content)
        article_id = f"{self.name}-{content_hash}"
        return ArticleRecord(
            id=article_id,
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            authors=authors,
            tags=metadata.tags,
            topics=metadata.topics,
            image_urls=image_urls,
            content=content,
            content_hash=content_hash,
        )

    def _extract_article_urls(self, html: str, base_url: str, since: date | None) -> list[str]:
        parser = LinkExtractor(base_url)
        parser.feed(html)
        urls: list[str] = []
        seen: set[str] = set()
        for url in parser.links:
            if "qstheory.cn" not in url or not url.endswith("/c.html"):
                continue
            url_date = self._url_date(url)
            if since and url_date and url_date < since:
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _extract_directory_urls(self, html: str, base_url: str, since: date | None = None) -> list[str]:
        parser = LinkExtractor(base_url)
        parser.feed(html)
        urls: list[str] = []
        seen: set[str] = set()
        for url in parser.links:
            if "qstheory.cn" not in url or url == base_url:
                continue
            if self._is_index_url(url):
                continue
            if url.endswith("/c.html") or url.lower().endswith((".jpg", ".png", ".pdf")):
                continue
            if "/qs/" not in url and "mulu" not in url:
                continue
            url_date = self._url_date(url)
            if since and url_date and url_date < since:
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
            if len(urls) >= 30:
                break
        return urls

    def _is_listing_page(self, html: str) -> bool:
        title = self._page_title(html)
        if "目录" in title:
            return True
        if re.search(r"《求是》20\d{2}年", title):
            return True
        if re.fullmatch(r"20\d{2}年", title):
            return True
        return False

    def _is_issue_listing_page(self, html: str) -> bool:
        title = self._page_title(html)
        return bool(re.search(r"第\d+期", title) and "目录" in title)

    def _page_title(self, html: str) -> str:
        title = (
            extract_first([r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"], html)
            or ""
        )
        return re.sub(r"\s+", "", title)

    def _detail_html(self, html: str) -> str:
        match = re.search(r'<div[^>]+id=["\']detailContent["\'][^>]*>(.*?)(?:</div>\s*</div>\s*<div class=["\']xl_ewm|</div>\s*</div>\s*<div class=["\']fs-text)', html, re.S)
        if match:
            return match.group(1)
        return html

    def _url_date(self, url: str) -> date | None:
        compact = re.search(r"/(20\d{6})/", url)
        if compact:
            value = compact.group(1)
            return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:]}")
        dashed = re.search(r"/(20\d{2})-(\d{2})/(\d{2})/", url)
        if dashed:
            year, month, day = dashed.groups()
            return date.fromisoformat(f"{year}-{month}-{day}")
        return None

    def _is_index_url(self, url: str) -> bool:
        normalized = url.rstrip("/")
        return normalized in {
            "https://www.qstheory.cn/qs/mulu.htm",
            "http://www.qstheory.cn/qs/mulu.htm",
            self.index_url.rstrip("/"),
        }

    def _extract_date(self, text: str) -> str | None:
        cn_date = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", text)
        if cn_date:
            year, month, day = cn_date.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        iso_date = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", text)
        if iso_date:
            year, month, day = iso_date.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return None

    def _max_pages(self) -> int:
        raw_value = os.getenv("QSTHEORY_MAX_PAGES")
        if not raw_value:
            return DEFAULT_MAX_PAGES
        try:
            return max(1, int(raw_value))
        except ValueError:
            return DEFAULT_MAX_PAGES


class QSTheoryWebSource(QSTheorySource):
    name = "qstheory-web"

    def __init__(self, entry_urls: tuple[str, ...] | None = None) -> None:
        super().__init__(WEB_INDEX_URL)
        self.entry_urls = entry_urls or WEB_ENTRY_URLS

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        urls: list[str] = []
        seen_urls: set[str] = set()
        queue = list(self.entry_urls)
        seen_pages: set[str] = set()
        max_pages = self._max_web_pages()

        while queue and (limit is None or len(urls) < limit) and len(seen_pages) < max_pages:
            page_url = queue.pop(0)
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                page_html = self.fetch_article_html(page_url)
            except Exception:
                continue
            for article_url in self._extract_article_urls(page_html, page_url, since):
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                urls.append(article_url)
                if limit is not None and len(urls) >= limit:
                    break
            if limit is not None and len(urls) >= limit:
                break
            for child_url in self._extract_web_directory_urls(page_html, page_url, since):
                if child_url not in seen_pages and child_url not in queue:
                    queue.append(child_url)
        return urls

    def _extract_web_directory_urls(self, html: str, base_url: str, since: date | None) -> list[str]:
        parser = LinkExtractor(base_url)
        parser.feed(html)
        urls: list[str] = []
        seen: set[str] = set()
        for url in parser.links:
            if not self._is_web_directory_url(url):
                continue
            url_date = self._url_date(url)
            if since and url_date and url_date < since:
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
            if len(urls) >= 40:
                break
        return urls

    def _is_web_directory_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc not in {"www.qstheory.cn", "qstheory.cn"}:
            return False
        path = parsed.path
        if not path or path in {"/", "/index.htm"}:
            return False
        if "/qs/" in path or "mulu" in path:
            return False
        if path.endswith("/c.html"):
            return False
        if path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".pdf", ".mp4", ".css", ".js")):
            return False
        if not path.endswith((".htm", ".html", "/")):
            return False
        return any(token in path for token in WEB_DIRECTORY_PATH_TOKENS)

    def _max_web_pages(self) -> int:
        raw_value = os.getenv("QSTHEORY_WEB_MAX_PAGES")
        if not raw_value:
            return DEFAULT_WEB_MAX_PAGES
        try:
            return max(1, int(raw_value))
        except ValueError:
            return DEFAULT_WEB_MAX_PAGES
