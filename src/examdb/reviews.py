from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import db
from .config import Paths
from .markdown import frontmatter, slugify, write_text
from .models import QuestionReview
from .retag import parse_markdown_note


@dataclass
class ReviewSyncChange:
    question_id: str
    markdown_path: Path
    old_mistake_reason: str | None = None
    old_review_note: str | None = None
    old_confidence: int | None = None
    old_favorite: bool = False
    new_mistake_reason: str | None = None
    new_review_note: str | None = None
    new_confidence: int | None = None
    new_favorite: bool = False
    applied: bool = False
    error: str | None = None


@dataclass
class ReviewSyncResult:
    scanned: int = 0
    changes: list[ReviewSyncChange] = field(default_factory=list)


def write_question_review_cards(conn: sqlite3.Connection, vault: Path) -> list[Path]:
    rows = _review_rows(conn)
    written: list[Path] = []
    for row in rows:
        path = _review_card_path(vault, row)
        content = _review_markdown(row, path)
        written.append(write_text(path, content))
        conn.execute(
            "UPDATE question_reviews SET markdown_path = ?, updated_at = ? WHERE question_id = ?",
            (
                str(path.relative_to(vault.parent)),
                datetime.now().isoformat(timespec="seconds"),
                row["question_id"],
            ),
        )
    conn.commit()
    return written


def sync_reviews_from_markdown(
    paths: Paths,
    *,
    target_path: Path | None = None,
    apply: bool = False,
) -> ReviewSyncResult:
    conn = db.connect(paths.db)
    db.init_schema(conn)
    rows = _review_rows(conn)
    result = ReviewSyncResult()
    for row in rows:
        note_path = _resolved_review_path(paths, row)
        if target_path is not None and not _path_matches(paths, note_path, target_path):
            continue
        result.scanned += 1
        if not note_path.exists():
            result.changes.append(ReviewSyncChange(question_id=row["question_id"], markdown_path=note_path, error="markdown_missing"))
            continue
        metadata, body = parse_markdown_note(note_path.read_text(encoding="utf-8"))
        new_mistake_reason = _text(metadata.get("mistake_reason")) or _section(body, "错因")
        new_review_note = _section(body, "复盘")
        new_confidence = _int(metadata.get("confidence"))
        new_favorite = bool(metadata.get("favorite") or False)
        changed = (
            new_mistake_reason != row["mistake_reason"]
            or new_review_note != row["review_note"]
            or new_confidence != row["confidence"]
            or new_favorite != bool(row["favorite"])
        )
        if not changed:
            continue
        change = ReviewSyncChange(
            question_id=row["question_id"],
            markdown_path=note_path,
            old_mistake_reason=row["mistake_reason"],
            old_review_note=row["review_note"],
            old_confidence=row["confidence"],
            old_favorite=bool(row["favorite"]),
            new_mistake_reason=new_mistake_reason,
            new_review_note=new_review_note,
            new_confidence=new_confidence,
            new_favorite=new_favorite,
        )
        result.changes.append(change)
        if apply:
            db.upsert_question_review(
                conn,
                QuestionReview(
                    question_id=row["question_id"],
                    mistake_reason=new_mistake_reason,
                    review_note=new_review_note,
                    confidence=new_confidence,
                    favorite=new_favorite,
                    markdown_path=str(note_path.relative_to(paths.root)),
                    updated_at=datetime.now().isoformat(timespec="seconds"),
                ),
            )
            change.applied = True
    return result


def _review_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT qr.*, q.stem, q.answer, q.explanation, q.question_type,
                   q.knowledge_points_json, q.number, p.year, p.region, p.exam_type,
                   pa.selected_answer, pa.is_correct, pa.duration_seconds
            FROM question_reviews qr
            JOIN questions q ON q.id = qr.question_id
            JOIN exam_papers p ON p.id = q.paper_id
            LEFT JOIN practice_attempts pa ON pa.id = qr.last_attempt_id
            WHERE qr.favorite = 1
               OR qr.mistake_reason IS NOT NULL
               OR qr.review_note IS NOT NULL
               OR pa.is_correct = 0
            ORDER BY qr.updated_at DESC
            """
        )
    )


def _review_markdown(row: sqlite3.Row, path: Path) -> str:
    metadata: dict[str, Any] = {
        "question_id": row["question_id"],
        "question_type": row["question_type"],
        "mistake_reason": row["mistake_reason"],
        "confidence": row["confidence"],
        "favorite": bool(row["favorite"]),
        "last_attempted_at": row["last_attempted_at"],
        "selected_answer": row["selected_answer"],
        "is_correct": None if row["is_correct"] is None else bool(row["is_correct"]),
        "duration_seconds": row["duration_seconds"],
    }
    lines = [
        frontmatter(metadata),
        "",
        f"# {row['question_type'] or '未分类'}错题复盘",
        "",
        f"来源：{row['year'] or '未知'} {row['region']}{row['exam_type']} 第 {row['number']} 题",
        "",
        "## 题干",
        "",
        row["stem"].strip(),
        "",
        "## 答案与解析",
        "",
        f"答案：{row['answer'] or ''}",
        "",
        row["explanation"] or "",
        "",
        "## 错因",
        "",
        row["mistake_reason"] or "",
        "",
        "## 复盘",
        "",
        row["review_note"] or "",
    ]
    return "\n".join(lines).strip() + "\n"


def _review_card_path(vault: Path, row: sqlite3.Row) -> Path:
    section = slugify(row["question_type"] or "未分类")
    filename = f"{slugify(row['question_id'])}.md"
    return vault / "刷题记录" / "错题本" / section / filename


def _resolved_review_path(paths: Paths, row: sqlite3.Row) -> Path:
    if row["markdown_path"]:
        return paths.root / row["markdown_path"]
    return _review_card_path(paths.vault, row)


def _path_matches(paths: Paths, note_path: Path, target_path: Path) -> bool:
    target = target_path if target_path.is_absolute() else paths.root / target_path
    target = target.resolve()
    note = note_path.resolve()
    return note == target if target.is_file() else target in note.parents


def _section(body: str, heading: str) -> str | None:
    marker = f"## {heading}"
    if marker not in body:
        return None
    rest = body.split(marker, 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return _text(rest)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
