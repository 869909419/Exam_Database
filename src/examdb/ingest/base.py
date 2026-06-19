from __future__ import annotations

from datetime import date
from typing import Protocol

from examdb.models import ArticleRecord


class ArticleSource(Protocol):
    name: str

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        ...

    def fetch_article_html(self, url: str) -> str:
        ...

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        ...
