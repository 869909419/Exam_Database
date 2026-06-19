from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from examdb import db
from examdb.config import Paths
from examdb.ingest.gov_policy import GovPolicySource
from examdb.ingest.local_gov import ChongqingGovSource, SichuanGovSource
from examdb.ingest.people_commentary import PeopleCommentarySource
from examdb.ingest.qstheory import QSTheorySource
from examdb.ingest.placeholders import PlaceholderSource
from examdb.ingest.xinhua_politics import XinhuaPoliticsSource
from examdb.markdown import article_markdown, slugify, write_text
from examdb.models import ArticleRecord


SOURCES = {
    "qstheory": QSTheorySource,
    "people-daily": lambda: PlaceholderSource("people-daily"),
    "people-commentary": PeopleCommentarySource,
    "gov": GovPolicySource,
    "gov-policy": GovPolicySource,
    "xinhua-politics": XinhuaPoliticsSource,
    "gmw-theory": lambda: PlaceholderSource("gmw-theory"),
    "stats-gov": lambda: PlaceholderSource("stats-gov"),
    "sichuan-gov": SichuanGovSource,
    "chongqing-gov": ChongqingGovSource,
}


@dataclass
class IngestResult:
    written: list[Path]
    skipped_existing: int = 0


def get_source(name: str):
    if name not in SOURCES:
        known = ", ".join(sorted(SOURCES))
        raise ValueError(f"Unsupported source '{name}'. Available: {known}")
    return SOURCES[name]()


def ingest_articles(
    source_name: str,
    since: date,
    paths: Paths,
    limit: int | None = None,
    refresh: bool = False,
) -> IngestResult:
    paths.ensure()
    source = get_source(source_name)
    conn = db.connect(paths.db)
    db.init_schema(conn)

    written: list[Path] = []
    skipped_existing = 0
    discovery_limit = article_discovery_limit(limit, refresh)
    for url in source.list_article_urls(since=since, limit=discovery_limit):
        if limit is not None and len(written) >= limit:
            break
        if not refresh and db.article_exists(conn, url):
            skipped_existing += 1
            continue
        html = source.fetch_article_html(url)
        raw_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        raw_path = paths.raw / "articles" / source_name / f"{raw_id}.html"
        write_text(raw_path, html)

        article = source.parse_article_html(html, url)
        article.raw_path = str(raw_path.relative_to(paths.root))
        vault_path = article_vault_path(paths, source_name, article)
        processed_path = article_processed_path(paths, source_name, article)
        localize_article_images(paths, source_name, article, vault_path)
        markdown = article_markdown(article)
        write_text(processed_path, markdown)
        article.markdown_path = str(vault_path.relative_to(paths.root))
        write_text(vault_path, article_markdown(article))
        db.upsert_article(conn, article)
        written.append(vault_path)
    return IngestResult(written=written, skipped_existing=skipped_existing)


def article_discovery_limit(limit: int | None, refresh: bool) -> int | None:
    if refresh or limit is None:
        return limit
    return limit + max(50, limit * 5)


def article_vault_path(paths: Paths, source_name: str, article: ArticleRecord) -> Path:
    archive_dir = article_archive_dir(article)
    filename = f"{slugify(article.title)}.md"
    return paths.vault / "资料库" / "政策理论" / source_name / archive_dir / filename


def article_processed_path(paths: Paths, source_name: str, article: ArticleRecord) -> Path:
    archive_dir = article_archive_dir(article)
    filename = f"{slugify(article.title)}.md"
    return paths.processed / "articles" / source_name / archive_dir / filename


def article_archive_dir(article: ArticleRecord) -> Path:
    issue_dir = article_issue_dir(article.source)
    if issue_dir:
        return issue_dir
    return article_date_dir(article.published_at)


def article_issue_dir(source: str) -> Path | None:
    match = re.search(r"《求是》\s*(20\d{2})/(\d{1,2})", source)
    if not match:
        return None
    year, issue = match.groups()
    return Path(year) / f"{year}年第{int(issue)}期"


def article_date_dir(published_at: str | None) -> Path:
    if not published_at:
        return Path("unknown")
    parts = published_at.split("-")
    if len(parts) >= 3:
        return Path(parts[0]) / f"{parts[1]}-{parts[2]}"
    if len(parts) >= 2:
        return Path(parts[0]) / parts[1]
    return Path(published_at)


def localize_article_images(paths: Paths, source_name: str, article: ArticleRecord, vault_path: Path) -> None:
    if not article.image_urls:
        return
    image_dir = article_image_dir(vault_path, article)
    replacements: dict[str, str] = {}
    image_paths: list[str] = []
    for index, image_url in enumerate(article.image_urls, start=1):
        if not image_url.startswith(("http://", "https://")):
            continue
        filename = image_filename(image_url, index)
        image_path = image_dir / filename
        try:
            download_binary(image_url, image_path)
        except Exception:
            continue
        relative_to_note = os.path.relpath(image_path, start=vault_path.parent)
        relative_to_note = Path(relative_to_note).as_posix()
        replacements[image_url] = relative_to_note
        image_paths.append(str(image_path.relative_to(paths.root)))
    for remote_url, local_path in replacements.items():
        article.content = article.content.replace(remote_url, local_path)
    article.image_paths = image_paths


def article_image_dir(vault_path: Path, article: ArticleRecord) -> Path:
    return vault_path.parent / "附件" / slugify(article.title)


def image_filename(image_url: str, index: int) -> str:
    path = unquote(urlparse(image_url).path)
    name = Path(path).name
    name = slugify(name, fallback=f"image-{index:02d}")
    if "." not in name:
        name = f"{name}.jpg"
    return f"{index:02d}-{name}"


def download_binary(url: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return path
    request = Request(url, headers={"User-Agent": "ExamDB/0.1 (+public research archive)"})
    with urlopen(request, timeout=30) as response:
        path.write_bytes(response.read())
    return path
