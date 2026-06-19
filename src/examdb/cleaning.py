from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin


class TextExtractor(HTMLParser):
    block_tags = {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        normalized = re.sub(r"\s+", " ", data).strip()
        if normalized:
            self.parts.append(normalized)

    def text(self) -> str:
        return "\n".join(part.strip() for part in self.parts if part.strip())


class MarkdownExtractor(HTMLParser):
    block_tags = {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3", "h4"}

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.parts: list[str] = []
        self.image_urls: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if self._skip_depth:
            return
        if tag in self.block_tags:
            self.parts.append("\n")
        if tag == "img":
            attrs_map = dict(attrs)
            src = attrs_map.get("src")
            if not src:
                return
            image_url = urljoin(self.base_url, src)
            alt = attrs_map.get("alt") or attrs_map.get("data-name") or "image"
            if image_url not in self.image_urls:
                self.image_urls.append(image_url)
            self.parts.append(f"\n![{alt}]({image_url})\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if self._skip_depth:
            return
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        normalized = re.sub(r"\s+", " ", data).strip()
        if normalized:
            self.parts.append(normalized)

    def markdown(self) -> str:
        return "\n".join(part.strip() for part in self.parts if part.strip())


NOISE_PATTERNS = [
    r"^责任编辑[:：].*",
    r"^来源[:：]\s*$",
    r"^字号[:：].*",
    r"^打印\s*$",
    r"^分享.*",
    r"^扫一扫.*",
    r"^相关链接.*",
    r"^推荐阅读.*",
    r"^更多.*",
    r"^版权声明.*",
    r"^ICP备案.*",
    r"^【纠错】.*",
    r"^理论资源导航$",
    r"^扫描二维码.*",
    r"^网站编辑\s*-.*",
    r"^标签\s*-.*",
    r"^【网站声明】.*",
    r"^010090\d+.*",
]


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


def html_to_markdown(html: str, base_url: str) -> tuple[str, list[str]]:
    parser = MarkdownExtractor(base_url)
    parser.feed(html)
    return parser.markdown(), parser.image_urls


def clean_article_text(text: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if any(re.search(pattern, line) for pattern in NOISE_PATTERNS):
            continue
        if len(line) <= 2 and line in {"|", "-", "_"}:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n\n".join(lines)


def extract_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.S)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return None
