from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from . import db
from .config import Paths
from .markdown import question_card_path, question_markdown, write_text
from .models import Question, QuestionSource


@dataclass
class EnrichmentChange:
    question_id: str
    number: str
    status: str
    source_id: str | None = None
    applied: bool = False
    reason: str | None = None


@dataclass
class EnrichmentResult:
    scanned: int
    queued: int
    matched: int
    applied: int
    changes: list[EnrichmentChange]


def enrich_explanations(
    paths: Paths,
    paper_id: str,
    source_name: str = "fenbi",
    source_file: Path | None = None,
    apply: bool = False,
    limit: int | None = None,
) -> EnrichmentResult:
    conn = db.connect(paths.db)
    db.init_schema(conn)
    rows = db.question_rows_for_paper(conn, paper_id)
    if limit is not None:
        rows = rows[:limit]

    external_records = load_external_records(source_file) if source_file else []
    changes: list[EnrichmentChange] = []
    queued = matched = applied_count = 0

    for row in rows:
        existing_status = row["explanation_status"] or "missing"
        if existing_status in {"verified", "fetched"} and row["explanation"]:
            continue

        if external_records:
            record, confidence = best_record_match(row, external_records)
            if record and confidence in {"high", "medium"}:
                source = question_source_from_record(row, source_name, record, confidence)
                db.upsert_question_source(conn, source)
                matched += 1
                did_apply = False
                if apply and confidence == "high":
                    db.update_question_explanation(
                        conn,
                        row["id"],
                        answer=record.get("answer"),
                        explanation=record.get("explanation"),
                        explanation_source=source.source_url or source.source_name,
                        explanation_status="fetched",
                    )
                    did_apply = True
                    applied_count += 1
                    rewrite_question_card(paths, conn, row["id"])
                changes.append(
                    EnrichmentChange(
                        question_id=row["id"],
                        number=row["number"],
                        status="matched",
                        source_id=source.id,
                        applied=did_apply,
                        reason=f"{confidence}_confidence",
                    )
                )
                continue

        source = queued_question_source(row, source_name)
        db.upsert_question_source(conn, source)
        queued += 1
        changes.append(
            EnrichmentChange(
                question_id=row["id"],
                number=row["number"],
                status="queued",
                source_id=source.id,
                applied=False,
                reason="needs_external_lookup",
            )
        )

    return EnrichmentResult(scanned=len(rows), queued=queued, matched=matched, applied=applied_count, changes=changes)


def load_external_records(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, list):
            return [record for record in data if isinstance(record, dict)]
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return [record for record in data["questions"] if isinstance(record, dict)]
    records: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
    return records


def best_record_match(row, records: list[dict[str, str]]) -> tuple[dict[str, str] | None, str]:
    best: dict[str, str] | None = None
    best_score = 0.0
    for record in records:
        if record.get("question_id") and record["question_id"] == row["id"]:
            return record, "high"
        if record.get("number") and str(record["number"]) != str(row["number"]):
            continue
        score = stem_similarity(row["stem"], record.get("stem") or record.get("matched_stem") or "")
        if score > best_score:
            best = record
            best_score = score
    if best is None:
        return None, "low"
    if best_score >= 0.86:
        return best, "high"
    if best_score >= 0.68:
        return best, "medium"
    return best, "low"


def stem_similarity(left: str, right: str) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm[:80] == right_norm[:80]:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def normalize_text(value: str) -> str:
    return "".join(str(value).split())


def queued_question_source(row, source_name: str) -> QuestionSource:
    source_id = question_source_id(row["id"], source_name, None)
    return QuestionSource(
        id=source_id,
        question_id=row["id"],
        source_name=source_name,
        matched_stem=row["stem"][:300],
        match_confidence="low",
        status="needs_lookup",
        notes="Use the question stem/options to locate the official explanation on the source website.",
    )


def question_source_from_record(row, source_name: str, record: dict[str, str], confidence: str) -> QuestionSource:
    source_url = record.get("source_url") or record.get("url")
    source_id = question_source_id(row["id"], source_name, source_url or record.get("external_question_id"))
    now = datetime.now().isoformat(timespec="seconds")
    return QuestionSource(
        id=source_id,
        question_id=row["id"],
        source_name=source_name,
        source_url=source_url,
        external_question_id=record.get("external_question_id"),
        matched_stem=record.get("stem") or record.get("matched_stem"),
        matched_answer=record.get("answer"),
        matched_explanation=record.get("explanation"),
        match_confidence=confidence,
        status="matched" if confidence == "high" else "needs_review",
        fetched_at=record.get("fetched_at") or now,
        notes=record.get("notes"),
    )


def question_source_id(question_id: str, source_name: str, source_key: str | None) -> str:
    digest = hashlib.sha256(f"{question_id}:{source_name}:{source_key or 'lookup'}".encode("utf-8")).hexdigest()[:16]
    return f"qsrc-{digest}"


def rewrite_question_card(paths: Paths, conn, question_id: str) -> None:
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if row is None:
        return
    question = question_from_row(row)
    write_text(question_card_path(paths.vault, question), question_markdown(question))


def question_from_row(row) -> Question:
    return Question(
        id=row["id"],
        paper_id=row["paper_id"],
        number=row["number"],
        stem=row["stem"],
        options=json.loads(row["options_json"]),
        answer=row["answer"],
        explanation=row["explanation"],
        explanation_source=row["explanation_source"],
        explanation_status=row["explanation_status"],
        question_type=row["question_type"],
        knowledge_points=json.loads(row["knowledge_points_json"]),
        difficulty=row["difficulty"],
        source_span=row["source_span"],
        question_format=row["question_format"],
        review_status=row["review_status"],
        parse_warnings=json.loads(row["parse_warnings_json"]),
    )
