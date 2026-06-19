from __future__ import annotations

import sqlite3


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
