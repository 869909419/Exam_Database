from __future__ import annotations

import hashlib
import json
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
    extract_detail_html,
    extract_title,
    fetch_html,
    normalize_url,
)
from examdb.models import ArticleRecord


LATEST_JSON_URL = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"
INTERPRETATION_JSON_URL = "https://www.gov.cn/zhengce/jiedu/ZCJD_QZ.json"
YAOWEN_INDEX_URL = "https://www.gov.cn/yaowen/liebiao/"
DEFAULT_MAX_RECORDS = 800


class GovPolicySource:
    name = "gov-policy"

    def __init__(
        self,
        latest_json_url: str = LATEST_JSON_URL,
        interpretation_json_url: str = INTERPRETATION_JSON_URL,
        yaowen_index_url: str = YAOWEN_INDEX_URL,
    ) -> None:
        self.latest_json_url = latest_json_url
        self.interpretation_json_url = interpretation_json_url
        self.yaowen_index_url = yaowen_index_url

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for seed_url in self._seed_urls():
            if not self._is_article_url(seed_url):
                continue
            parsed_date = self._date_from_url(seed_url)
            if parsed_date and date.fromisoformat(parsed_date) < since:
                continue
            if seed_url not in seen:
                seen.add(seed_url)
                urls.append(seed_url)
            if limit is not None and len(urls) >= limit:
                return urls

        records = []
        records.extend(self._fetch_records(self.latest_json_url))
        records.extend(self._fetch_records(self.interpretation_json_url))
        for url in self._records_to_urls(records, since=since, limit=None):
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if limit is not None and len(urls) >= limit:
                return urls

        for url in self._yaowen_urls(since=since):
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if limit is not None and len(urls) >= limit:
                return urls
        return urls

    def fetch_article_html(self, url: str) -> str:
        return fetch_html(url)

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        title = self._extract_gov_title(html)
        text = html_to_text(html)
        published_at = self._extract_published_at(html, text)
        source = self._extract_source(html, text, url)
        authors = self._extract_authors(html)
        detail_html = self._extract_body_html(html)

        markdown_content, image_urls = html_to_markdown(detail_html, url)
        content = clean_article_text(markdown_content)
        if not content:
            content = clean_article_text(html_to_text(detail_html))

        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        metadata = suggest_policy_metadata_with_ai(title, content)
        return ArticleRecord(
            id=f"gov-policy-{content_hash}",
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

    def _fetch_records(self, json_url: str) -> list[dict]:
        try:
            payload = self.fetch_article_html(json_url)
        except Exception:
            return []
        try:
            records = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(records, list):
            return []
        return [record for record in records if isinstance(record, dict)]

    def _records_to_urls(self, records: list[dict], since: date, limit: int | None = None) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        max_records = self._max_records()
        for record in records[:max_records]:
            url = str(record.get("URL") or "").strip()
            published_at = str(record.get("DOCRELPUBTIME") or "").strip()
            if not url or not self._is_article_url(url):
                continue
            parsed_date = extract_date(published_at)
            if parsed_date and date.fromisoformat(parsed_date) < since:
                continue
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if limit is not None and len(urls) >= limit:
                break
        return urls

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(normalize_url(url))
        if parsed.netloc != "www.gov.cn":
            return False
        if not parsed.path.startswith(("/zhengce/", "/yaowen/")):
            return False
        if parsed.path.endswith("/index.htm"):
            return False
        return bool(re.search(r"/content_\d+\.htm$", parsed.path))

    def _date_from_url(self, url: str) -> str | None:
        match = re.search(r"/(20\d{2})(\d{2})/", url)
        if match:
            year, month = match.groups()
            return f"{year}-{month}-01"
        return None

    def _yaowen_urls(self, since: date) -> list[str]:
        try:
            html = self.fetch_article_html(self.yaowen_index_url)
        except Exception:
            return []
        from examdb.ingest.html_helpers import extract_links

        urls: list[str] = []
        seen: set[str] = set()
        for url in extract_links(html, self.yaowen_index_url):
            if not self._is_article_url(url):
                continue
            parsed_date = self._date_from_url(url)
            if parsed_date and date.fromisoformat(parsed_date) < since:
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _extract_gov_title(self, html: str) -> str:
        title = extract_first([r"标\s*题[:：]?\s*</h2>\s*<p[^>]*>(.*?)</p>"], html)
        if title:
            return clean_html_title(title)
        title = extract_title(html)
        title = re.sub(r"_.*?中国政府网$", "", title).strip()
        return title or "未命名文章"

    def _extract_published_at(self, html: str, text: str) -> str | None:
        for pattern in [
            r'<meta[^>]+name=["\']firstpublishedtime["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+name=["\']lastmodifiedtime["\'][^>]+content=["\']([^"\']+)',
            r"发布日期[:：]?\s*</h2>\s*<p[^>]*>(.*?)</p>",
        ]:
            value = extract_first([pattern], html)
            if value:
                parsed = extract_date(value)
                if parsed:
                    return parsed
        return extract_date(text)

    def _extract_source(self, html: str, text: str, url: str) -> str:
        source = extract_first([r"来源[:：]\s*([^\n ]+)"], text)
        if source:
            return source
        office = extract_first([r"发文机关[:：]?\s*</h2>\s*<p[^>]*>(.*?)</p>"], html)
        if office:
            return f"中国政府网-{clean_html_title(office)}"
        if "/jiedu/" in url:
            return "中国政府网-政策解读"
        return "中国政府网-最新政策"

    def _extract_authors(self, html: str) -> list[str]:
        author = extract_first([r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)'], html)
        if not author:
            return []
        return [item.strip() for item in re.split(r"[、,， ]+", author) if item.strip()]

    def _extract_body_html(self, html: str) -> str:
        for attr, token in [
            ("id", "UCAP-CONTENT"),
            ("class", "pages_content"),
            ("class", "article"),
        ]:
            detail_html = extract_balanced_div(html, attr, token)
            if detail_html and len(clean_article_text(html_to_text(detail_html))) >= 20:
                return detail_html
        return extract_detail_html(
            html,
            [
                r'<article[^>]*>(.*?)</article>',
                r'<div[^>]+class=["\'][^"\']*(?:article|content|pages_content|TRS_UEDITOR)[^"\']*["\'][^>]*>(.*?)</div>',
            ],
        )

    def _filter_body_images(self, image_urls: list[str]) -> list[str]:
        filtered: list[str] = []
        for image_url in image_urls:
            lower = image_url.lower()
            if any(token in lower for token in ("logo", "qrcode", "icon", "share", "/images/150.jpg")):
                continue
            if image_url not in filtered:
                filtered.append(image_url)
        return filtered

    def _max_records(self) -> int:
        raw_value = os.getenv("GOV_POLICY_MAX_RECORDS")
        if not raw_value:
            return DEFAULT_MAX_RECORDS
        try:
            return max(1, int(raw_value))
        except ValueError:
            return DEFAULT_MAX_RECORDS

    def _seed_urls(self) -> list[str]:
        urls: list[str] = []
        raw_value = os.getenv("GOV_POLICY_SEED_URLS")
        if raw_value:
            urls.extend(item.strip() for item in re.split(r"[\n,]", raw_value) if item.strip())
        seed_file = os.getenv("GOV_POLICY_SEED_FILE")
        if seed_file and os.path.exists(seed_file):
            with open(seed_file, encoding="utf-8") as handle:
                for line in handle:
                    value = line.strip()
                    if not value or value.startswith("#"):
                        continue
                    urls.append(value.split("|")[-1].strip())
        return urls
