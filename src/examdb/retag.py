from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import db
from .ai import DeepSeekClient, suggest_policy_metadata_with_ai
from .config import Paths
from .markdown import frontmatter
from .taxonomy import POLICY_TAGS


AI_RETAGGED_STATUS = "ai-retagged"


@dataclass
class RetagChange:
    title: str
    markdown_path: Path
    old_tags: list[str]
    old_topics: list[str]
    new_tags: list[str] = field(default_factory=list)
    new_topics: list[str] = field(default_factory=list)
    out_of_sync: bool = False
    applied: bool = False
    error: str | None = None


@dataclass
class RetagResult:
    scanned: int = 0
    changes: list[RetagChange] = field(default_factory=list)
    missing_api_key: bool = False


def retag_articles(
    paths: Paths,
    *,
    source: str | None = None,
    since: date | None = None,
    limit: int | None = None,
    target_path: Path | None = None,
    only_needs_review: bool = False,
    apply: bool = False,
    client: DeepSeekClient | None = None,
) -> RetagResult:
    client = client or DeepSeekClient()
    if not getattr(client, "enabled", False):
        return RetagResult(missing_api_key=True)

    conn = db.connect(paths.db)
    db.init_schema(conn)
    rows = _article_rows(conn, source=source, since=since, target_path=target_path, paths=paths)

    result = RetagResult()
    for row in rows:
        if limit is not None and result.scanned >= limit:
            break
        note_path = paths.root / row["markdown_path"]
        if not note_path.exists():
            result.scanned += 1
            result.changes.append(
                RetagChange(
                    title=row["title"],
                    markdown_path=note_path,
                    old_tags=_json_list(row["tags_json"]),
                    old_topics=_json_list(row["topics_json"]),
                    error="markdown_missing",
                )
            )
            continue

        original = note_path.read_text(encoding="utf-8")
        metadata, body = parse_markdown_note(original)
        markdown_tags = _metadata_list(metadata.get("tags"))
        markdown_topics = _metadata_list(metadata.get("topics"))
        db_tags = _json_list(row["tags_json"])
        db_topics = _json_list(row["topics_json"])
        out_of_sync = markdown_tags != db_tags or markdown_topics != db_topics
        needs_review = out_of_sync or _has_unstable_tags(markdown_tags) or _has_unstable_tags(db_tags)
        if only_needs_review and not needs_review:
            continue

        result.scanned += 1
        change = RetagChange(
            title=str(metadata.get("title") or row["title"]),
            markdown_path=note_path,
            old_tags=markdown_tags,
            old_topics=markdown_topics,
            out_of_sync=out_of_sync,
        )
        try:
            suggestion = suggest_policy_metadata_with_ai(change.title, body, client=client, strict=True)
        except Exception as exc:
            change.error = f"deepseek_error: {exc}"
            result.changes.append(change)
            continue

        change.new_tags = suggestion.tags
        change.new_topics = suggestion.topics
        result.changes.append(change)

        if apply:
            metadata["tags"] = change.new_tags
            metadata["topics"] = change.new_topics
            metadata["status"] = AI_RETAGGED_STATUS
            note_path.write_text(render_markdown_note(metadata, body), encoding="utf-8")
            db.update_article_metadata(conn, row["id"], change.new_tags, change.new_topics, AI_RETAGGED_STATUS)
            change.applied = True

    return result


def parse_markdown_note(content: str) -> tuple[dict[str, Any], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, content

    metadata = parse_frontmatter_lines(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def parse_frontmatter_lines(lines: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.startswith(" "):
            index += 1
            continue
        if ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value:
            metadata[key] = parse_scalar(raw_value)
            index += 1
            continue

        values: list[Any] = []
        index += 1
        while index < len(lines):
            item_line = lines[index]
            if item_line.startswith("  - "):
                values.append(parse_scalar(item_line[4:].strip()))
                index += 1
                continue
            if item_line.strip() == "":
                index += 1
                continue
            break
        metadata[key] = values
    return metadata


def parse_scalar(value: str) -> Any:
    if value == '""':
        return None
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def render_markdown_note(metadata: dict[str, Any], body: str) -> str:
    return f"{frontmatter(metadata)}\n\n{body.strip()}\n"


def _article_rows(
    conn: sqlite3.Connection,
    *,
    source: str | None,
    since: date | None,
    target_path: Path | None,
    paths: Paths,
) -> list[sqlite3.Row]:
    clauses = ["markdown_path IS NOT NULL", "markdown_path != ''"]
    params: list[str] = []
    if since is not None:
        clauses.append("published_at >= ?")
        params.append(since.isoformat())
    query = f"SELECT * FROM articles WHERE {' AND '.join(clauses)} ORDER BY published_at DESC, title"
    rows = list(conn.execute(query, params))
    if source:
        rows = [row for row in rows if _row_matches_source(row, source)]
    if target_path:
        rows = [row for row in rows if _row_matches_path(row, target_path, paths)]
    return rows


def _row_matches_source(row: sqlite3.Row, source: str) -> bool:
    path = Path(row["markdown_path"])
    parts = path.parts
    return source in parts


def _row_matches_path(row: sqlite3.Row, target_path: Path, paths: Paths) -> bool:
    note_path = (paths.root / row["markdown_path"]).resolve()
    resolved_target = (paths.root / target_path).resolve() if not target_path.is_absolute() else target_path.resolve()
    if resolved_target.is_file():
        return note_path == resolved_target
    return resolved_target in note_path.parents


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return _metadata_list(parsed)


def _metadata_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _has_unstable_tags(tags: list[str]) -> bool:
    return any(tag == "待复核" or tag not in POLICY_TAGS for tag in tags)
