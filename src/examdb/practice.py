from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import db
from .ai import DeepSeekClient
from .markdown import slugify
from .models import PracticeAttempt, PracticeSession, PracticeSessionItem, QuestionReview


XINGCE_TYPES = ["常识判断", "言语理解", "数量关系", "判断推理", "资料分析"]

XINGCE_TEMPLATES = {
    "guokao-xingzheng": {
        "label": "国考行政执法",
        "total": 130,
        "sections": {"常识判断": 35, "言语理解": 30, "数量关系": 10, "判断推理": 35, "资料分析": 20},
    },
    "guokao-dishi": {
        "label": "国考地市级",
        "total": 130,
        "sections": {"常识判断": 35, "言语理解": 30, "数量关系": 10, "判断推理": 35, "资料分析": 20},
    },
    "guokao-fusheng": {
        "label": "国考副省级",
        "total": 135,
        "sections": {"常识判断": 35, "言语理解": 30, "数量关系": 15, "判断推理": 35, "资料分析": 20},
    },
}

PRACTICE_COOLDOWN_DAYS = 3


@dataclass
class PracticeSelection:
    title: str
    mode: str
    config: dict[str, Any]
    questions: list[sqlite3.Row]


def list_questions(conn: sqlite3.Connection, query: str | None = None, limit: int = 10) -> list[sqlite3.Row]:
    sql = "SELECT id, number, question_type, difficulty, stem FROM questions"
    params: list[str | int] = []
    if query:
        sql += " WHERE stem LIKE ? OR question_type LIKE ?"
        like = f"%{query}%"
        params.extend([like, like])
    sql += " ORDER BY id LIMIT ?"
    params.append(limit)
    return list(conn.execute(sql, params))


def metadata(conn: sqlite3.Connection) -> dict[str, Any]:
    type_counts = {
        row["question_type"] or "未分类": row["total"]
        for row in conn.execute(
            """
            SELECT q.question_type, COUNT(*) AS total
            FROM questions q
            JOIN exam_papers p ON p.id = q.paper_id
            WHERE p.paper_kind = '行测'
            GROUP BY q.question_type
            ORDER BY total DESC
            """
        )
    }
    attempted = conn.execute("SELECT COUNT(*) AS total FROM practice_attempts").fetchone()["total"]
    favorite = conn.execute("SELECT COUNT(*) AS total FROM question_reviews WHERE favorite = 1").fetchone()["total"]
    mistakes = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM question_reviews qr
        JOIN practice_attempts pa ON pa.id = qr.last_attempt_id
        JOIN questions q ON q.id = qr.question_id
        JOIN exam_papers p ON p.id = q.paper_id
        WHERE p.paper_kind = '行测'
          AND pa.is_correct = 0
        """
    ).fetchone()["total"]
    return {
        "question_types": XINGCE_TYPES,
        "templates": XINGCE_TEMPLATES,
        "counts": type_counts,
        "attempted_count": attempted,
        "favorite_count": favorite,
        "mistake_count": mistakes,
    }


def create_session(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    selection = _select_questions(conn, payload)
    now = datetime.now().isoformat(timespec="seconds")
    session_id = f"practice-{uuid.uuid4().hex[:16]}"
    session = PracticeSession(
        id=session_id,
        mode=selection.mode,
        title=selection.title,
        config=selection.config,
        started_at=now,
        total_count=len(selection.questions),
    )
    db.upsert_practice_session(conn, session)
    items = [
        PracticeSessionItem(
            id=f"{session_id}-item-{index:03d}",
            session_id=session_id,
            question_id=row["id"],
            position=index,
            material_group=_material_group_from_source_span(row["source_span"]),
        )
        for index, row in enumerate(selection.questions, start=1)
    ]
    db.insert_practice_session_items(conn, items)
    return session_payload(conn, session_id)


def session_payload(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    session = conn.execute("SELECT * FROM practice_sessions WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise KeyError(session_id)
    rows = _session_item_rows(conn, session_id)
    cards = _cards_from_items(conn, rows, reveal=session["status"] == "finished")
    answered = sum(1 for row in rows if row["selected_answer"])
    correct = sum(1 for row in rows if row["is_correct"] == 1)
    return {
        "session": _session_dict(session),
        "progress": {"answered": answered, "total": len(rows), "correct": correct},
        "cards": cards,
    }


def submit_answer(conn: sqlite3.Connection, session_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = _session_item_row(conn, session_id, item_id)
    selected = _normalize_answer(str(payload.get("selected_answer") or ""))
    duration = _int_or_none(payload.get("duration_seconds"))
    now = datetime.now().isoformat(timespec="seconds")
    correct_answer = _normalize_answer(str(row["answer"] or ""))
    is_correct = bool(selected and correct_answer and selected == correct_answer)
    confidence = _int_or_none(payload.get("confidence"))
    mistake_reason = _optional_text(payload.get("mistake_reason"))
    review_note = _optional_text(payload.get("review_note"))
    favorite = bool(payload.get("favorite") or False)

    conn.execute(
        """
        UPDATE practice_session_items
        SET selected_answer = ?,
            is_correct = ?,
            duration_seconds = ?,
            answered_at = ?,
            confidence = COALESCE(?, confidence),
            mistake_reason = COALESCE(?, mistake_reason),
            review_note = COALESCE(?, review_note),
            favorite = ?
        WHERE id = ? AND session_id = ?
        """,
        (selected, int(is_correct), duration, now, confidence, mistake_reason, review_note, int(favorite), item_id, session_id),
    )
    conn.commit()

    attempt_id = f"attempt-{uuid.uuid4().hex[:16]}"
    db.insert_attempt(
        conn,
        PracticeAttempt(
            id=attempt_id,
            question_id=row["question_id"],
            selected_answer=selected,
            is_correct=is_correct,
            duration_seconds=duration,
            confidence=confidence,
            note=review_note,
            attempted_at=now,
            session_id=session_id,
            position=row["position"],
            mistake_reason=mistake_reason,
            review_note=review_note,
            updated_at=now,
        ),
    )
    db.upsert_question_review(
        conn,
        QuestionReview(
            question_id=row["question_id"],
            mistake_reason=mistake_reason,
            review_note=review_note,
            confidence=confidence,
            favorite=favorite,
            last_attempt_id=attempt_id,
            last_attempted_at=now,
            updated_at=now,
        ),
    )
    _refresh_session_counts(conn, session_id)
    return _answered_item_payload(conn, session_id, item_id)


def save_review(conn: sqlite3.Connection, session_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = _session_item_row(conn, session_id, item_id)
    existing = conn.execute(
        """
        SELECT i.mistake_reason, i.review_note, i.confidence, i.favorite,
               qr.mistake_reason AS saved_mistake_reason,
               qr.review_note AS saved_review_note,
               qr.confidence AS saved_confidence,
               qr.favorite AS saved_favorite
        FROM practice_session_items i
        LEFT JOIN question_reviews qr ON qr.question_id = i.question_id
        WHERE i.id = ? AND i.session_id = ?
        """,
        (item_id, session_id),
    ).fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    mistake_reason = _optional_text(payload.get("mistake_reason")) if "mistake_reason" in payload else _first_text(existing["mistake_reason"], existing["saved_mistake_reason"])
    review_note = _optional_text(payload.get("review_note")) if "review_note" in payload else _first_text(existing["review_note"], existing["saved_review_note"])
    confidence = _int_or_none(payload.get("confidence")) if "confidence" in payload else existing["confidence"] if existing["confidence"] is not None else existing["saved_confidence"]
    favorite = bool(payload.get("favorite")) if "favorite" in payload else bool(existing["favorite"] or existing["saved_favorite"] or False)
    conn.execute(
        """
        UPDATE practice_session_items
        SET mistake_reason = ?,
            review_note = ?,
            confidence = ?,
            favorite = ?
        WHERE id = ? AND session_id = ?
        """,
        (mistake_reason, review_note, confidence, int(favorite), item_id, session_id),
    )
    conn.commit()
    db.upsert_question_review(
        conn,
        QuestionReview(
            question_id=row["question_id"],
            mistake_reason=mistake_reason,
            review_note=review_note,
            confidence=confidence,
            favorite=favorite,
            updated_at=now,
        ),
    )
    return _answered_item_payload(conn, session_id, item_id)


def finish_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    now = datetime.now()
    session = conn.execute("SELECT * FROM practice_sessions WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise KeyError(session_id)
    started_at = datetime.fromisoformat(session["started_at"])
    wall_duration = int((now - started_at).total_seconds())
    item_duration = conn.execute(
        """
        SELECT SUM(COALESCE(duration_seconds, 0)) AS total
        FROM practice_session_items
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()["total"] or 0
    duration = max(wall_duration, int(item_duration))
    counts = _session_counts(conn, session_id)
    conn.execute(
        """
        UPDATE practice_sessions
        SET status = 'finished',
            finished_at = ?,
            total_count = ?,
            correct_count = ?,
            duration_seconds = ?
        WHERE id = ?
        """,
        (now.isoformat(timespec="seconds"), counts["total"], counts["correct"], duration, session_id),
    )
    conn.commit()
    return session_payload(conn, session_id)


def stats(conn: sqlite3.Connection, days: int = 30) -> dict[str, Any]:
    since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    rows = list(
        conn.execute(
            """
            SELECT p.*, q.question_type, q.knowledge_points_json
            FROM practice_attempts p
            JOIN questions q ON q.id = p.question_id
            JOIN exam_papers ep ON ep.id = q.paper_id
            WHERE p.attempted_at >= ? AND ep.paper_kind = '行测'
            ORDER BY p.attempted_at
            """,
            (since,),
        )
    )
    return {
        "since": since,
        "total": len(rows),
        "by_date": _aggregate(rows, lambda row: row["attempted_at"][:10]),
        "by_type": _aggregate(rows, lambda row: row["question_type"] or "未分类"),
        "by_knowledge": _aggregate_knowledge(rows),
    }


def analyze_session_with_ai(conn: sqlite3.Connection, session_id: str, client: DeepSeekClient | None = None) -> dict[str, Any]:
    client = client or DeepSeekClient()
    if not client.enabled:
        conn.execute("UPDATE practice_sessions SET ai_status = ? WHERE id = ?", ("missing_api_key", session_id))
        conn.commit()
        return {"status": "missing_api_key", "summary": None}
    payload = session_payload(conn, session_id)
    rows = _session_item_rows(conn, session_id)
    compact_items = [
        {
            "number": row["position"],
            "question_type": row["question_type"],
            "knowledge_points": _json_list(row["knowledge_points_json"]),
            "selected_answer": row["selected_answer"],
            "answer": row["answer"],
            "is_correct": bool(row["is_correct"]),
            "duration_seconds": row["duration_seconds"],
            "mistake_reason": row["mistake_reason"],
            "review_note": row["review_note"],
        }
        for row in rows
    ]
    system = "你是公务员行测刷题复盘助手。请用中文输出简洁、可执行的复盘建议。"
    user = json.dumps(
        {
            "session": payload["session"],
            "progress": payload["progress"],
            "items": compact_items,
            "requirements": ["指出薄弱题型和知识点", "总结主要错因", "给出下一次练习建议"],
        },
        ensure_ascii=False,
    )
    try:
        result = client.chat_json(system, user)
    except Exception as exc:
        conn.execute("UPDATE practice_sessions SET ai_status = ? WHERE id = ?", (f"error: {exc}", session_id))
        conn.commit()
        return {"status": "error", "summary": None, "error": str(exc)}
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = json.dumps(result, ensure_ascii=False, indent=2)
    generated_at = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        UPDATE practice_sessions
        SET ai_summary = ?,
            ai_status = 'generated',
            ai_generated_at = ?
        WHERE id = ?
        """,
        (summary.strip(), generated_at, session_id),
    )
    conn.commit()
    return {"status": "generated", "summary": summary.strip(), "generated_at": generated_at}


def recent_sessions(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    return [
        _session_dict(row)
        for row in conn.execute(
            "SELECT * FROM practice_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
    ]


def _select_questions(conn: sqlite3.Connection, payload: dict[str, Any]) -> PracticeSelection:
    mode = str(payload.get("mode") or "section")
    if mode == "mock":
        template_id = str(payload.get("template") or "guokao-xingzheng")
        template = XINGCE_TEMPLATES.get(template_id)
        if template is None:
            raise ValueError(f"Unsupported template: {template_id}")
        selected: list[sqlite3.Row] = []
        used: set[str] = set()
        for question_type, count in template["sections"].items():
            rows = _candidate_questions(conn, [question_type], int(count), used)
            selected.extend(rows)
            used.update(row["id"] for row in rows)
        return PracticeSelection(
            title=str(template["label"]),
            mode="mock",
            config={"template": template_id, "sections": template["sections"]},
            questions=selected,
        )
    if mode == "favorites":
        count = max(1, min(int(payload.get("count") or 20), 200))
        rows = _favorite_questions(conn, count)
        return PracticeSelection(
            title=f"重点专项 {len(rows)}题",
            mode="favorites",
            config={"count": count},
            questions=rows,
        )
    if mode == "mistakes":
        count = max(1, min(int(payload.get("count") or 20), 200))
        rows = _mistake_questions(conn, count)
        return PracticeSelection(
            title=f"错题专项 {len(rows)}题",
            mode="mistakes",
            config={"count": count},
            questions=rows,
        )

    question_type = payload.get("question_type")
    question_types = payload.get("question_types")
    if isinstance(question_types, list):
        types = [str(item) for item in question_types if str(item) in XINGCE_TYPES]
    elif question_type in XINGCE_TYPES:
        types = [str(question_type)]
    else:
        types = ["常识判断"]
    count = max(1, min(int(payload.get("count") or 10), 200))
    rows = _candidate_questions(conn, types, count, set())
    return PracticeSelection(
        title=f"{'、'.join(types)}专项 {len(rows)}题",
        mode="section",
        config={"question_types": types, "count": count},
        questions=rows,
    )


def _candidate_questions(
    conn: sqlite3.Connection,
    question_types: list[str],
    limit: int,
    exclude_ids: set[str],
) -> list[sqlite3.Row]:
    if question_types == ["资料分析"]:
        return _candidate_material_questions(conn, limit, exclude_ids)
    placeholders = ",".join("?" for _ in question_types)
    params: list[Any] = list(question_types)
    excluded = ""
    if exclude_ids:
        excluded_placeholders = ",".join("?" for _ in exclude_ids)
        excluded = f"AND q.id NOT IN ({excluded_placeholders})"
        params.extend(sorted(exclude_ids))
    cooldown_cutoff = _cooldown_cutoff()
    params.extend([cooldown_cutoff, cooldown_cutoff, cooldown_cutoff])
    params.append(limit)
    return list(
        conn.execute(
            f"""
            SELECT q.*, p.year, p.region, p.exam_type, p.paper_kind
            FROM questions q
            JOIN exam_papers p ON p.id = q.paper_id
            LEFT JOIN question_reviews qr ON qr.question_id = q.id
            LEFT JOIN practice_attempts last_pa ON last_pa.id = qr.last_attempt_id
            WHERE p.paper_kind = '行测'
              AND q.question_type IN ({placeholders})
              {excluded}
            ORDER BY
              CASE
                WHEN qr.last_attempted_at IS NULL AND COALESCE(qr.favorite, 0) = 1 THEN 0
                WHEN qr.last_attempted_at IS NULL THEN 1
                WHEN COALESCE(qr.favorite, 0) = 1 AND qr.last_attempted_at < ? THEN 2
                WHEN last_pa.is_correct = 0 AND qr.last_attempted_at < ? THEN 3
                WHEN qr.last_attempted_at < ? THEN 4
                WHEN COALESCE(qr.favorite, 0) = 1 THEN 5
                WHEN last_pa.is_correct = 0 THEN 6
                ELSE 7
              END,
              CASE WHEN qr.last_attempted_at IS NULL THEN 0 ELSE 1 END,
              qr.last_attempted_at,
              random()
            LIMIT ?
            """,
            params,
        )
    )


def _candidate_material_questions(
    conn: sqlite3.Connection,
    limit: int,
    exclude_ids: set[str],
) -> list[sqlite3.Row]:
    excluded = ""
    params: list[Any] = []
    if exclude_ids:
        excluded_placeholders = ",".join("?" for _ in exclude_ids)
        excluded = f"AND q.id NOT IN ({excluded_placeholders})"
        params.extend(sorted(exclude_ids))
    cooldown_cutoff = _cooldown_cutoff()
    params.extend([cooldown_cutoff, cooldown_cutoff, cooldown_cutoff])
    rows = list(
        conn.execute(
            f"""
            SELECT q.*, p.year, p.region, p.exam_type, p.paper_kind
            FROM questions q
            JOIN exam_papers p ON p.id = q.paper_id
            LEFT JOIN question_reviews qr ON qr.question_id = q.id
            LEFT JOIN practice_attempts last_pa ON last_pa.id = qr.last_attempt_id
            WHERE p.paper_kind = '行测'
              AND q.question_type = '资料分析'
              {excluded}
            ORDER BY
              CASE
                WHEN qr.last_attempted_at IS NULL AND COALESCE(qr.favorite, 0) = 1 THEN 0
                WHEN qr.last_attempted_at IS NULL THEN 1
                WHEN COALESCE(qr.favorite, 0) = 1 AND qr.last_attempted_at < ? THEN 2
                WHEN last_pa.is_correct = 0 AND qr.last_attempted_at < ? THEN 3
                WHEN qr.last_attempted_at < ? THEN 4
                WHEN COALESCE(qr.favorite, 0) = 1 THEN 5
                WHEN last_pa.is_correct = 0 THEN 6
                ELSE 7
              END,
              CASE WHEN qr.last_attempted_at IS NULL THEN 0 ELSE 1 END,
              qr.last_attempted_at,
              random()
            """,
            params,
        )
    )
    groups: dict[str, list[sqlite3.Row]] = {}
    singles: list[sqlite3.Row] = []
    for row in rows:
        group = _material_group_from_source_span(row["source_span"])
        if group:
            groups.setdefault(group, []).append(row)
        else:
            singles.append(row)

    selected: list[sqlite3.Row] = []
    for group_rows in groups.values():
        group_rows.sort(key=_question_sort_key)
        selected.extend(group_rows)
        if len(selected) >= limit:
            return selected
    selected.extend(singles[: max(0, limit - len(selected))])
    return selected


def _favorite_questions(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT q.*, p.year, p.region, p.exam_type, p.paper_kind
            FROM questions q
            JOIN exam_papers p ON p.id = q.paper_id
            JOIN question_reviews qr ON qr.question_id = q.id
            WHERE p.paper_kind = '行测'
              AND qr.favorite = 1
            ORDER BY
              CASE WHEN qr.last_attempted_at IS NULL THEN 0 ELSE 1 END,
              qr.last_attempted_at,
              random()
            LIMIT ?
            """,
            (limit,),
        )
    )


def _mistake_questions(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT q.*, p.year, p.region, p.exam_type, p.paper_kind
            FROM questions q
            JOIN exam_papers p ON p.id = q.paper_id
            JOIN question_reviews qr ON qr.question_id = q.id
            JOIN practice_attempts pa ON pa.id = qr.last_attempt_id
            WHERE p.paper_kind = '行测'
              AND pa.is_correct = 0
            ORDER BY
              qr.last_attempted_at,
              random()
            LIMIT ?
            """,
            (limit,),
        )
    )


def _session_item_rows(conn: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT i.*, q.paper_id, q.number, q.stem, q.options_json, q.answer,
                   q.explanation, q.question_type, q.question_format,
                   q.knowledge_points_json, q.difficulty, q.source_span,
                   p.year, p.region, p.exam_type, p.paper_kind,
                   qr.mistake_reason AS saved_mistake_reason,
                   qr.review_note AS saved_review_note,
                   qr.confidence AS saved_confidence,
                   qr.favorite AS saved_favorite
            FROM practice_session_items i
            JOIN questions q ON q.id = i.question_id
            JOIN exam_papers p ON p.id = q.paper_id
            LEFT JOIN question_reviews qr ON qr.question_id = q.id
            WHERE i.session_id = ?
            ORDER BY i.position
            """,
            (session_id,),
        )
    )


def _session_item_row(conn: sqlite3.Connection, session_id: str, item_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT i.*, q.answer
        FROM practice_session_items i
        JOIN questions q ON q.id = i.question_id
        WHERE i.session_id = ? AND i.id = ?
        """,
        (session_id, item_id),
    ).fetchone()
    if row is None:
        raise KeyError(item_id)
    return row


def _answered_item_payload(conn: sqlite3.Connection, session_id: str, item_id: str) -> dict[str, Any]:
    session = conn.execute("SELECT status FROM practice_sessions WHERE id = ?", (session_id,)).fetchone()
    row = next(row for row in _session_item_rows(conn, session_id) if row["id"] == item_id)
    return {"item": _item_dict(conn, row, reveal=bool(session and session["status"] == "finished")), "progress": session_payload(conn, session_id)["progress"]}


def _cards_from_items(conn: sqlite3.Connection, rows: list[sqlite3.Row], *, reveal: bool) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        material_group = row["material_group"]
        if material_group:
            grouped: list[sqlite3.Row] = []
            while index < len(rows) and rows[index]["material_group"] == material_group:
                grouped.append(rows[index])
                index += 1
            material, _stem = _split_material(grouped[0]["stem"])
            cards.append(
                {
                    "kind": "material_group",
                    "material_group": material_group,
                    "title": f"第 {grouped[0]['position']}-{grouped[-1]['position']} 题",
                    "material": material,
                    "items": [_item_dict(conn, item, reveal=reveal) for item in grouped],
                }
            )
            continue
        cards.append(
            {
                "kind": "single",
                "material_group": None,
                "title": f"第 {row['position']} 题",
                "material": "",
                "items": [_item_dict(conn, row, reveal=reveal)],
            }
        )
        index += 1
    return cards


def _item_dict(conn: sqlite3.Connection, row: sqlite3.Row, *, reveal: bool) -> dict[str, Any]:
    _material, stem = _split_material(row["stem"])
    return {
        "id": row["id"],
        "question_id": row["question_id"],
        "position": row["position"],
        "paper_id": row["paper_id"],
        "number": row["number"],
        "source": f"{row['year'] or '未知'} {row['region']}{row['exam_type']}",
        "stem": stem,
        "options": json.loads(row["options_json"] or "{}"),
        "question_type": row["question_type"],
        "question_format": row["question_format"],
        "knowledge_points": _json_list(row["knowledge_points_json"]),
        "difficulty": row["difficulty"],
        "selected_answer": row["selected_answer"],
        "is_correct": None if row["is_correct"] is None else bool(row["is_correct"]),
        "duration_seconds": row["duration_seconds"],
        "answered_at": row["answered_at"],
        "review_note": row["review_note"] if row["review_note"] is not None else row["saved_review_note"],
        "mistake_reason": row["mistake_reason"] if row["mistake_reason"] is not None else row["saved_mistake_reason"],
        "confidence": row["confidence"] if row["confidence"] is not None else row["saved_confidence"],
        "favorite": bool(row["favorite"] or row["saved_favorite"] or False),
        "answer": row["answer"] if reveal else None,
        "explanation": row["explanation"] if reveal else None,
        "related_questions": _related_questions(conn, row) if reveal else [],
        "recent_attempts": _recent_attempts(conn, row["question_id"]) if reveal else [],
    }


def _related_questions(conn: sqlite3.Connection, row: sqlite3.Row, limit: int = 5) -> list[dict[str, Any]]:
    points = _json_list(row["knowledge_points_json"])
    if not points:
        return []
    like = f"%{points[0]}%"
    return [
        {
            "question_id": item["id"],
            "paper_id": item["paper_id"],
            "number": item["number"],
            "question_type": item["question_type"],
            "stem": item["stem"][:80],
        }
        for item in conn.execute(
            """
            SELECT id, paper_id, number, question_type, stem
            FROM questions
            WHERE id != ? AND knowledge_points_json LIKE ?
            ORDER BY random()
            LIMIT ?
            """,
            (row["question_id"], like, limit),
        )
    ]


def _recent_attempts(conn: sqlite3.Connection, question_id: str, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "selected_answer": row["selected_answer"],
            "is_correct": None if row["is_correct"] is None else bool(row["is_correct"]),
            "duration_seconds": row["duration_seconds"],
            "attempted_at": row["attempted_at"],
        }
        for row in conn.execute(
            """
            SELECT selected_answer, is_correct, duration_seconds, attempted_at
            FROM practice_attempts
            WHERE question_id = ?
            ORDER BY attempted_at DESC
            LIMIT ?
            """,
            (question_id, limit),
        )
    ]


def _session_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "mode": row["mode"],
        "title": row["title"],
        "config": json.loads(row["config_json"] or "{}"),
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "total_count": row["total_count"],
        "correct_count": row["correct_count"],
        "duration_seconds": row["duration_seconds"],
        "ai_summary": row["ai_summary"],
        "ai_status": row["ai_status"],
        "ai_generated_at": row["ai_generated_at"],
    }


def _session_counts(conn: sqlite3.Connection, session_id: str) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
        FROM practice_session_items
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    return {"total": row["total"] or 0, "correct": row["correct"] or 0}


def _refresh_session_counts(conn: sqlite3.Connection, session_id: str) -> None:
    counts = _session_counts(conn, session_id)
    conn.execute(
        "UPDATE practice_sessions SET total_count = ?, correct_count = ? WHERE id = ?",
        (counts["total"], counts["correct"], session_id),
    )
    conn.commit()


def _aggregate(rows: list[sqlite3.Row], key_fn) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        bucket = buckets.setdefault(key, {"label": key, "total": 0, "correct": 0, "duration_sum": 0, "duration_count": 0})
        _add_attempt(bucket, row)
    return [_finish_bucket(bucket) for bucket in sorted(buckets.values(), key=lambda item: item["label"])]


def _aggregate_knowledge(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        for point in _json_list(row["knowledge_points_json"])[:3]:
            bucket = buckets.setdefault(
                point,
                {"label": point, "total": 0, "correct": 0, "duration_sum": 0, "duration_count": 0},
            )
            _add_attempt(bucket, row)
    finished = [_finish_bucket(bucket) for bucket in buckets.values()]
    return sorted(finished, key=lambda item: item["total"], reverse=True)[:20]


def _add_attempt(bucket: dict[str, Any], row: sqlite3.Row) -> None:
    bucket["total"] += 1
    if row["is_correct"] == 1:
        bucket["correct"] += 1
    if row["duration_seconds"] is not None:
        bucket["duration_sum"] += row["duration_seconds"]
        bucket["duration_count"] += 1


def _finish_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    total = bucket["total"]
    correct = bucket["correct"]
    duration_count = bucket["duration_count"]
    return {
        "label": bucket["label"],
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0,
        "avg_duration": bucket["duration_sum"] / duration_count if duration_count else 0,
        "total_duration": bucket["duration_sum"],
    }


def _material_group_from_source_span(source_span: str | None) -> str | None:
    if not source_span:
        return None
    match = re.search(r"(?:^|;)materials:([^;]+)", source_span)
    if not match:
        return None
    first_key = match.group(1).split(",")[0].strip()
    if not first_key:
        return None
    return f"材料-{slugify(first_key, fallback='material')}"


def _split_material(stem: str) -> tuple[str, str]:
    if not stem.startswith("【材料】"):
        return "", stem
    marker = "\n\n"
    if marker not in stem:
        return stem.removeprefix("【材料】").strip(), ""
    material, question_stem = stem.split(marker, 1)
    return material.removeprefix("【材料】").strip(), question_stem.strip()


def _question_sort_key(row: sqlite3.Row) -> tuple[int, str]:
    number = str(row["number"])
    return (int(number), "") if number.isdigit() else (10**9, number)


def _normalize_answer(value: str) -> str:
    letters = [char for char in value.upper().replace("，", ",") if char.isalnum()]
    return "".join(sorted(dict.fromkeys(letters)))


def _cooldown_cutoff() -> str:
    return (datetime.now() - timedelta(days=PRACTICE_COOLDOWN_DAYS)).isoformat(timespec="seconds")


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(*values: object) -> str | None:
    for value in values:
        text = _optional_text(value)
        if text:
            return text
    return None
