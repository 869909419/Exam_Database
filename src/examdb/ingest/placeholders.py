from __future__ import annotations

from datetime import date

from examdb.models import ArticleRecord


class PlaceholderSource:
    def __init__(self, name: str) -> None:
        self.name = name

    def list_article_urls(self, since: date, limit: int | None = None) -> list[str]:
        return []

    def fetch_article_html(self, url: str) -> str:
        raise NotImplementedError(f"Source '{self.name}' does not have a fetcher yet.")

    def parse_article_html(self, html: str, url: str) -> ArticleRecord:
        raise NotImplementedError(f"Source '{self.name}' does not have a parser yet.")
