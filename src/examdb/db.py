from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ArticleRecord, ExamPaper, PaperCandidate, PracticeAttempt, Question, QuestionSource


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published_at TEXT,
            authors_json TEXT NOT NULL,
            raw_path TEXT,
            markdown_path TEXT,
            tags_json TEXT NOT NULL,
            topics_json TEXT NOT NULL,
            image_urls_json TEXT NOT NULL DEFAULT '[]',
            image_paths_json TEXT NOT NULL DEFAULT '[]',
            content_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exam_papers (
            id TEXT PRIMARY KEY,
            exam_category TEXT NOT NULL DEFAULT '公务员',
            exam_type TEXT NOT NULL,
            region TEXT NOT NULL,
            year INTEGER,
            paper_kind TEXT,
            source_name TEXT,
            source_url TEXT,
            source_file TEXT NOT NULL,
            markdown_path TEXT NOT NULL,
            question_count INTEGER NOT NULL DEFAULT 0,
            import_status TEXT NOT NULL,
            quality_status TEXT NOT NULL DEFAULT 'needs_review',
            parse_warnings_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            paper_id TEXT NOT NULL,
            number TEXT NOT NULL,
            stem TEXT NOT NULL,
            options_json TEXT NOT NULL,
            answer TEXT,
            explanation TEXT,
            explanation_source TEXT,
            explanation_status TEXT NOT NULL DEFAULT 'missing',
            question_type TEXT,
            question_format TEXT,
            knowledge_points_json TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium',
            source_span TEXT,
            review_status TEXT NOT NULL DEFAULT 'needs_review',
            parse_warnings_json TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (paper_id) REFERENCES exam_papers(id)
        );

        CREATE TABLE IF NOT EXISTS paper_candidates (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            download_url TEXT,
            exam_category TEXT NOT NULL DEFAULT '公务员',
            exam_type TEXT,
            region TEXT,
            year INTEGER,
            paper_kind TEXT,
            download_status TEXT NOT NULL DEFAULT 'pending',
            import_status TEXT NOT NULL DEFAULT 'pending',
            blocked_reason TEXT,
            notes TEXT,
            local_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS question_sources (
            id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT,
            external_question_id TEXT,
            matched_stem TEXT,
            matched_answer TEXT,
            matched_explanation TEXT,
            match_confidence TEXT NOT NULL DEFAULT 'low',
            status TEXT NOT NULL DEFAULT 'needs_lookup',
            fetched_at TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        );

        CREATE TABLE IF NOT EXISTS practice_attempts (
            id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            selected_answer TEXT,
            is_correct INTEGER,
            duration_seconds INTEGER,
            confidence INTEGER,
            note TEXT,
            attempted_at TEXT NOT NULL,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        );
        """
    )
    ensure_column(conn, "articles", "image_urls_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "articles", "image_paths_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "exam_papers", "exam_category", "TEXT NOT NULL DEFAULT '公务员'")
    ensure_column(conn, "exam_papers", "paper_kind", "TEXT")
    ensure_column(conn, "exam_papers", "source_name", "TEXT")
    ensure_column(conn, "exam_papers", "quality_status", "TEXT NOT NULL DEFAULT 'needs_review'")
    ensure_column(conn, "exam_papers", "parse_warnings_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "questions", "explanation_source", "TEXT")
    ensure_column(conn, "questions", "explanation_status", "TEXT NOT NULL DEFAULT 'missing'")
    ensure_column(conn, "questions", "question_format", "TEXT")
    ensure_column(conn, "questions", "review_status", "TEXT NOT NULL DEFAULT 'needs_review'")
    ensure_column(conn, "questions", "parse_warnings_json", "TEXT NOT NULL DEFAULT '[]'")
    conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def article_exists(conn: sqlite3.Connection, url: str) -> bool:
    row = conn.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,)).fetchone()
    return row is not None


def update_article_metadata(
    conn: sqlite3.Connection,
    article_id: str,
    tags: list[str],
    topics: list[str],
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE articles
        SET tags_json = ?,
            topics_json = ?,
            status = ?
        WHERE id = ?
        """,
        (
            json.dumps(tags, ensure_ascii=False),
            json.dumps(topics, ensure_ascii=False),
            status,
            article_id,
        ),
    )
    conn.commit()


def upsert_article(conn: sqlite3.Connection, article: ArticleRecord) -> None:
    values = (
        article.title,
        article.source,
        article.url,
        article.published_at,
        json.dumps(article.authors, ensure_ascii=False),
        article.raw_path,
        article.markdown_path,
        json.dumps(article.tags, ensure_ascii=False),
        json.dumps(article.topics, ensure_ascii=False),
        json.dumps(article.image_urls, ensure_ascii=False),
        json.dumps(article.image_paths, ensure_ascii=False),
        article.content_hash,
        article.status,
        article.ingested_at,
        article.url,
        article.content_hash,
    )
    cursor = conn.execute(
        """
        UPDATE articles
        SET title = ?,
            source = ?,
            url = ?,
            published_at = ?,
            authors_json = ?,
            raw_path = ?,
            markdown_path = ?,
            tags_json = ?,
            topics_json = ?,
            image_urls_json = ?,
            image_paths_json = ?,
            content_hash = ?,
            status = ?,
            ingested_at = ?
        WHERE url = ? OR content_hash = ?
        """,
        values,
    )
    if cursor.rowcount:
        conn.commit()
        return

    conn.execute(
        """
        INSERT INTO articles (
            id, title, source, url, published_at, authors_json, raw_path,
            markdown_path, tags_json, topics_json, image_urls_json, image_paths_json,
            content_hash, status, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article.id,
            article.title,
            article.source,
            article.url,
            article.published_at,
            json.dumps(article.authors, ensure_ascii=False),
            article.raw_path,
            article.markdown_path,
            json.dumps(article.tags, ensure_ascii=False),
            json.dumps(article.topics, ensure_ascii=False),
            json.dumps(article.image_urls, ensure_ascii=False),
            json.dumps(article.image_paths, ensure_ascii=False),
            article.content_hash,
            article.status,
            article.ingested_at,
        ),
    )
    conn.commit()


def upsert_paper(conn: sqlite3.Connection, paper: ExamPaper) -> None:
    conn.execute(
        """
        INSERT INTO exam_papers (
            id, exam_category, exam_type, region, year, paper_kind, source_name,
            source_url, source_file, markdown_path, question_count, import_status,
            quality_status, parse_warnings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            exam_category=excluded.exam_category,
            exam_type=excluded.exam_type,
            region=excluded.region,
            year=excluded.year,
            paper_kind=excluded.paper_kind,
            source_name=excluded.source_name,
            source_url=excluded.source_url,
            source_file=excluded.source_file,
            markdown_path=excluded.markdown_path,
            question_count=excluded.question_count,
            import_status=excluded.import_status,
            quality_status=excluded.quality_status,
            parse_warnings_json=excluded.parse_warnings_json
        """,
        (
            paper.id,
            paper.exam_category,
            paper.exam_type,
            paper.region,
            paper.year,
            paper.paper_kind,
            paper.source_name,
            paper.source_url,
            paper.source_file,
            paper.markdown_path,
            paper.question_count,
            paper.import_status,
            paper.quality_status,
            json.dumps(paper.parse_warnings, ensure_ascii=False),
        ),
    )
    conn.commit()


def upsert_question(conn: sqlite3.Connection, question: Question) -> None:
    conn.execute(
        """
        INSERT INTO questions (
            id, paper_id, number, stem, options_json, answer, explanation,
            explanation_source, explanation_status, question_type, question_format,
            knowledge_points_json, difficulty, source_span, review_status, parse_warnings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            stem=excluded.stem,
            options_json=excluded.options_json,
            answer=excluded.answer,
            explanation=excluded.explanation,
            explanation_source=excluded.explanation_source,
            explanation_status=excluded.explanation_status,
            question_type=excluded.question_type,
            question_format=excluded.question_format,
            knowledge_points_json=excluded.knowledge_points_json,
            difficulty=excluded.difficulty,
            source_span=excluded.source_span,
            review_status=excluded.review_status,
            parse_warnings_json=excluded.parse_warnings_json
        """,
        (
            question.id,
            question.paper_id,
            question.number,
            question.stem,
            json.dumps(question.options, ensure_ascii=False),
            question.answer,
            question.explanation,
            question.explanation_source,
            question.explanation_status,
            question.question_type,
            question.question_format,
            json.dumps(question.knowledge_points, ensure_ascii=False),
            question.difficulty,
            question.source_span,
            question.review_status,
            json.dumps(question.parse_warnings, ensure_ascii=False),
        ),
    )
    conn.commit()


def upsert_paper_candidate(conn: sqlite3.Connection, candidate: PaperCandidate) -> None:
    conn.execute(
        """
        INSERT INTO paper_candidates (
            id, source_id, source_name, title, url, download_url, exam_category,
            exam_type, region, year, paper_kind, download_status, import_status,
            blocked_reason, notes, local_path, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source_name=excluded.source_name,
            title=excluded.title,
            download_url=excluded.download_url,
            exam_category=excluded.exam_category,
            exam_type=excluded.exam_type,
            region=excluded.region,
            year=excluded.year,
            paper_kind=excluded.paper_kind,
            download_status=excluded.download_status,
            import_status=excluded.import_status,
            blocked_reason=excluded.blocked_reason,
            notes=excluded.notes,
            local_path=excluded.local_path,
            updated_at=excluded.updated_at
        """,
        (
            candidate.id,
            candidate.source_id,
            candidate.source_name,
            candidate.title,
            candidate.url,
            candidate.download_url,
            candidate.exam_category,
            candidate.exam_type,
            candidate.region,
            candidate.year,
            candidate.paper_kind,
            candidate.download_status,
            candidate.import_status,
            candidate.blocked_reason,
            candidate.notes,
            candidate.local_path,
            candidate.created_at,
            candidate.updated_at,
        ),
    )
    conn.commit()


def list_paper_candidates(
    conn: sqlite3.Connection,
    source_id: str | None = None,
    download_status: str | None = None,
    import_status: str | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[str | int] = []
    if source_id:
        clauses.append("source_id = ?")
        params.append(source_id)
    if download_status:
        clauses.append("download_status = ?")
        params.append(download_status)
    if import_status:
        clauses.append("import_status = ?")
        params.append(import_status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM paper_candidates {where} ORDER BY updated_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(sql, params))


def update_paper_candidate_status(
    conn: sqlite3.Connection,
    candidate_id: str,
    *,
    download_status: str | None = None,
    import_status: str | None = None,
    blocked_reason: str | None = None,
    local_path: str | None = None,
) -> None:
    fields: list[str] = []
    params: list[str] = []
    if download_status is not None:
        fields.append("download_status = ?")
        params.append(download_status)
    if import_status is not None:
        fields.append("import_status = ?")
        params.append(import_status)
    if blocked_reason is not None:
        fields.append("blocked_reason = ?")
        params.append(blocked_reason)
    if local_path is not None:
        fields.append("local_path = ?")
        params.append(local_path)
    fields.append("updated_at = datetime('now')")
    params.append(candidate_id)
    conn.execute(f"UPDATE paper_candidates SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()


def question_rows_for_paper(conn: sqlite3.Connection, paper_id: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY CAST(number AS INTEGER)", (paper_id,)))


def upsert_question_source(conn: sqlite3.Connection, source: QuestionSource) -> None:
    conn.execute(
        """
        INSERT INTO question_sources (
            id, question_id, source_name, source_url, external_question_id,
            matched_stem, matched_answer, matched_explanation, match_confidence,
            status, fetched_at, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source_url=excluded.source_url,
            external_question_id=excluded.external_question_id,
            matched_stem=excluded.matched_stem,
            matched_answer=excluded.matched_answer,
            matched_explanation=excluded.matched_explanation,
            match_confidence=excluded.match_confidence,
            status=excluded.status,
            fetched_at=excluded.fetched_at,
            notes=excluded.notes,
            updated_at=excluded.updated_at
        """,
        (
            source.id,
            source.question_id,
            source.source_name,
            source.source_url,
            source.external_question_id,
            source.matched_stem,
            source.matched_answer,
            source.matched_explanation,
            source.match_confidence,
            source.status,
            source.fetched_at,
            source.notes,
            source.created_at,
            source.updated_at,
        ),
    )
    conn.commit()


def list_question_sources(
    conn: sqlite3.Connection,
    question_id: str | None = None,
    status: str | None = None,
    source_name: str | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[str] = []
    if question_id:
        clauses.append("question_id = ?")
        params.append(question_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if source_name:
        clauses.append("source_name = ?")
        params.append(source_name)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return list(conn.execute(f"SELECT * FROM question_sources {where} ORDER BY updated_at DESC", params))


def update_question_explanation(
    conn: sqlite3.Connection,
    question_id: str,
    *,
    answer: str | None,
    explanation: str | None,
    explanation_source: str | None,
    explanation_status: str,
) -> None:
    conn.execute(
        """
        UPDATE questions
        SET answer = COALESCE(?, answer),
            explanation = COALESCE(?, explanation),
            explanation_source = ?,
            explanation_status = ?
        WHERE id = ?
        """,
        (answer, explanation, explanation_source, explanation_status, question_id),
    )
    conn.commit()


def insert_attempt(conn: sqlite3.Connection, attempt: PracticeAttempt) -> None:
    conn.execute(
        """
        INSERT INTO practice_attempts (
            id, question_id, selected_answer, is_correct, duration_seconds,
            confidence, note, attempted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt.id,
            attempt.question_id,
            attempt.selected_answer,
            None if attempt.is_correct is None else int(attempt.is_correct),
            attempt.duration_seconds,
            attempt.confidence,
            attempt.note,
            attempt.attempted_at,
        ),
    )
    conn.commit()
