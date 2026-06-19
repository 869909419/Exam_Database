from __future__ import annotations

import re
import subprocess
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from examdb.cleaning import extract_first


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(normalize_url(urljoin(self.base_url, href)))


def fetch_html(url: str, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": "ExamDB/0.1 (+public research archive)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        return fetch_html_with_curl(url, timeout=timeout)


def fetch_html_with_curl(url: str, timeout: int = 20) -> str:
    completed = subprocess.run(
        [
            "curl",
            "-L",
            "--max-time",
            str(timeout),
            "-A",
            "ExamDB/0.1 (+public research archive)",
            url,
        ],
        check=True,
        capture_output=True,
    )
    return completed.stdout.decode("utf-8", errors="replace")


def extract_links(html: str, base_url: str) -> list[str]:
    parser = LinkExtractor(base_url)
    parser.feed(html)
    return parser.links


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme and url.startswith("//"):
        url = f"http:{url}"
        parsed = urlparse(url)
    url = parsed._replace(fragment="").geturl()
    return url.rstrip()


def clean_html_title(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"[_-]\s*(人民网|观点频道|求是网|新华网).*$", "", title).strip()
    return title


def extract_title(html: str) -> str:
    candidates = re.findall(r"<h1[^>]*>(.*?)</h1>", html, flags=re.S)
    candidates.extend(re.findall(r"<title[^>]*>(.*?)</title>", html, flags=re.S))
    for candidate in candidates:
        title = clean_html_title(candidate)
        if title:
            return title
    return "未命名文章"


def extract_meta_content(html: str, name: str) -> str | None:
    patterns = [
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']{re.escape(name)}["\']',
    ]
    return extract_first(patterns, html)


def extract_date(text: str) -> str | None:
    cn_date = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", text)
    if cn_date:
        year, month, day = cn_date.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    iso_date = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", text)
    if iso_date:
        year, month, day = iso_date.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    slash_date = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", text)
    if slash_date:
        year, month, day = slash_date.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None


def extract_detail_html(html: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.S)
        if match:
            return match.group(1)
    return html


def extract_balanced_div(html: str, attr: str, token: str) -> str | None:
    if attr == "class":
        pattern = rf"<div\b(?=[^>]*class=[\"'][^\"']*{re.escape(token)}[^\"']*[\"'])[^>]*>"
    else:
        pattern = rf"<div\b(?=[^>]*{re.escape(attr)}=[\"']{re.escape(token)}[\"'])[^>]*>"
    match = re.search(pattern, html, flags=re.I | re.S)
    if not match:
        return None

    depth = 1
    content_start = match.end()
    tag_pattern = re.compile(r"</?div\b[^>]*>", flags=re.I)
    for tag_match in tag_pattern.finditer(html, content_start):
        tag = tag_match.group(0).lower()
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[content_start : tag_match.start()]
        else:
            depth += 1
    return None


def extract_element_by_id(html: str, element_id: str) -> str | None:
    pattern = rf"<(?P<tag>[a-zA-Z0-9]+)\b(?=[^>]*id=[\"']{re.escape(element_id)}[\"'])[^>]*>"
    match = re.search(pattern, html, flags=re.I | re.S)
    if not match:
        return None

    tag_name = match.group("tag")
    depth = 1
    content_start = match.end()
    tag_pattern = re.compile(rf"</?{re.escape(tag_name)}\b[^>]*>", flags=re.I)
    for tag_match in tag_pattern.finditer(html, content_start):
        tag = tag_match.group(0).lower()
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[content_start : tag_match.start()]
        else:
            depth += 1
    return None


def url_date_from_people_url(url: str) -> str | None:
    match = re.search(r"/n1/(20\d{2})/(\d{4})/", url)
    if not match:
        return None
    year, month_day = match.groups()
    return f"{year}-{month_day[:2]}-{month_day[2:]}"
