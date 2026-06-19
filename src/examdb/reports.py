from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .markdown import frontmatter, write_text


def weekly_report(conn: sqlite3.Connection, output_dir: Path) -> Path:
    since = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    rows = list(
        conn.execute(
            """
            SELECT q.question_type, COUNT(*) AS total,
                   SUM(CASE WHEN p.is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                   AVG(p.duration_seconds) AS avg_duration
            FROM practice_attempts p
            JOIN questions q ON q.id = p.question_id
            WHERE p.attempted_at >= ?
            GROUP BY q.question_type
            ORDER BY total DESC
            """,
            (since,),
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{datetime.now().date()}-刷题周报.md"
    metadata = {
        "report_type": "weekly",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "since": since,
    }
    lines = [frontmatter(metadata), "", "# 刷题周报", ""]
    if not rows:
        lines.append("最近 7 天还没有作答记录。")
    else:
        lines.append("| 题型 | 作答数 | 正确数 | 正确率 | 平均耗时 |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for row in rows:
            total = row["total"] or 0
            correct = row["correct"] or 0
            rate = correct / total if total else 0
            duration = row["avg_duration"] or 0
            lines.append(f"| {row['question_type'] or '未分类'} | {total} | {correct} | {rate:.0%} | {duration:.1f}s |")
    return write_text(path, "\n".join(lines) + "\n")
