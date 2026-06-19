from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import db
from .config import Paths
from .retag import _article_rows, _metadata_list, parse_markdown_note


@dataclass
class ArticleMetadataSyncChange:
    title: str
    markdown_path: Path
    old_tags: list[str]
    old_topics: list[str]
    old_status: str
    new_tags: list[str] = field(default_factory=list)
    new_topics: list[str] = field(default_factory=list)
    new_status: str = ""
    applied: bool = False
    error: str | None = None


@dataclass
class ArticleMetadataSyncResult:
    scanned: int = 0
    changes: list[ArticleMetadataSyncChange] = field(default_factory=list)


def sync_article_metadata_from_markdown(
    paths: Paths,
    *,
    source: str | None = None,
    since: date | None = None,
    limit: int | None = None,
    target_path: Path | None = None,
    only_changed: bool = False,
    apply: bool = False,
) -> ArticleMetadataSyncResult:
    conn = db.connect(paths.db)
    db.init_schema(conn)
    rows = _article_rows(conn, source=source, since=since, target_path=target_path, paths=paths)

    result = ArticleMetadataSyncResult()
    for row in rows:
        if limit is not None and result.scanned >= limit:
            break
        note_path = paths.root / row["markdown_path"]
        db_tags = _json_list(row["tags_json"])
        db_topics = _json_list(row["topics_json"])
        db_status = str(row["status"] or "")
        if not note_path.exists():
            result.scanned += 1
            result.changes.append(
                ArticleMetadataSyncChange(
                    title=row["title"],
                    markdown_path=note_path,
                    old_tags=db_tags,
                    old_topics=db_topics,
                    old_status=db_status,
                    error="markdown_missing",
                )
            )
            continue

        metadata, _body = parse_markdown_note(note_path.read_text(encoding="utf-8"))
        markdown_tags = _metadata_list(metadata.get("tags"))
        markdown_topics = _metadata_list(metadata.get("topics"))
        markdown_status = str(metadata.get("status") or db_status)
        changed = markdown_tags != db_tags or markdown_topics != db_topics or markdown_status != db_status
        if only_changed and not changed:
            continue

        result.scanned += 1
        if not changed:
            continue

        change = ArticleMetadataSyncChange(
            title=str(metadata.get("title") or row["title"]),
            markdown_path=note_path,
            old_tags=db_tags,
            old_topics=db_topics,
            old_status=db_status,
            new_tags=markdown_tags,
            new_topics=markdown_topics,
            new_status=markdown_status,
        )
        result.changes.append(change)

        if apply:
            db.update_article_metadata(conn, row["id"], markdown_tags, markdown_topics, markdown_status)
            change.applied = True

    return result


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return _metadata_list(parsed)
