from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from . import db
from .models import QuestionSource


SOURCE_TYPES = {
    "central_document",
    "leader_speech_or_meeting",
    "qstheory_article",
    "party_report",
    "local_policy",
    "ministry_policy",
    "media_explainer",
    "textbook_marxism",
}


@dataclass(frozen=True)
class PoliticsSourceEvidence:
    question_id: str
    paper_id: str
    year: int | None
    region: str
    number: str
    stem: str
    source_type: str
    source_title: str
    event_date: str | None
    evidence_text: str
    confidence: str


def analyze_politics_sources(
    conn: sqlite3.Connection,
    *,
    years: list[int],
    paper_kind: str,
    knowledge_point: str,
    dedupe: str = "stem",
) -> list[PoliticsSourceEvidence]:
    rows = _politics_question_rows(conn, years=years, paper_kind=paper_kind, knowledge_point=knowledge_point)
    if dedupe == "stem":
        rows = _dedupe_rows_by_stem(rows)
    elif dedupe != "none":
        raise ValueError("dedupe must be 'stem' or 'none'")
    return [_analyze_row(row) for row in rows]


def apply_politics_sources(
    conn: sqlite3.Connection,
    evidences: list[PoliticsSourceEvidence],
    *,
    years: list[int],
    paper_kind: str,
    knowledge_point: str,
    dedupe: str = "stem",
) -> int:
    evidence_by_stem = {normalize_stem(evidence.stem): evidence for evidence in evidences}
    rows = _politics_question_rows(conn, years=years, paper_kind=paper_kind, knowledge_point=knowledge_point)
    written = 0
    now = datetime.now().isoformat(timespec="seconds")
    for row in rows:
        key = normalize_stem(row["stem"]) if dedupe == "stem" else None
        evidence = evidence_by_stem.get(key or "") if key else _analyze_row(row)
        if evidence is None:
            continue
        source_id = stable_question_source_id(row["id"], evidence.source_type, evidence.source_title)
        notes = json.dumps(
            {
                "source_type": evidence.source_type,
                "source_title": evidence.source_title,
                "event_date": evidence.event_date,
                "evidence_text": evidence.evidence_text,
                "analysis": "politics-sources",
            },
            ensure_ascii=False,
        )
        db.upsert_question_source(
            conn,
            QuestionSource(
                id=source_id,
                question_id=row["id"],
                source_name=evidence.source_type,
                matched_stem=row["stem"],
                matched_answer=row["answer"],
                matched_explanation=evidence.evidence_text,
                match_confidence=evidence.confidence,
                status="matched" if evidence.confidence in {"high", "medium"} else "needs_review",
                fetched_at=now,
                notes=notes,
                created_at=now,
                updated_at=now,
            ),
        )
        written += 1
    return written


def format_evidences(evidences: list[PoliticsSourceEvidence]) -> str:
    lines = ["year\tregion\tnumber\tsource_type\tsource_title\tevent_date\tconfidence\tevidence_text"]
    for evidence in evidences:
        lines.append(
            "\t".join(
                [
                    str(evidence.year or ""),
                    evidence.region,
                    evidence.number,
                    evidence.source_type,
                    evidence.source_title,
                    evidence.event_date or "",
                    evidence.confidence,
                    _one_line(evidence.evidence_text),
                ]
            )
        )
    return "\n".join(lines)


def stable_question_source_id(question_id: str, source_type: str, source_title: str) -> str:
    digest = hashlib.sha256(f"{question_id}:{source_type}:{source_title}".encode("utf-8")).hexdigest()[:16]
    return f"qs-{digest}"


def normalize_stem(stem: str) -> str:
    return re.sub(r"\s+", "", stem or "")


def _politics_question_rows(
    conn: sqlite3.Connection,
    *,
    years: list[int],
    paper_kind: str,
    knowledge_point: str,
) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in years)
    params: list[str | int] = [*years, paper_kind, f"%{knowledge_point}%"]
    return list(
        conn.execute(
            f"""
            SELECT q.id, q.paper_id, q.number, q.stem, q.answer, q.explanation,
                   p.year, p.region, p.exam_type, p.markdown_path
            FROM questions q
            JOIN exam_papers p ON p.id = q.paper_id
            WHERE p.year IN ({placeholders})
              AND p.paper_kind = ?
              AND q.knowledge_points_json LIKE ?
            ORDER BY p.year, p.region, p.markdown_path, CAST(q.number AS INTEGER), q.number
            """,
            params,
        )
    )


def _dedupe_rows_by_stem(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    seen: set[str] = set()
    deduped: list[sqlite3.Row] = []
    for row in rows:
        key = normalize_stem(row["stem"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _analyze_row(row: sqlite3.Row) -> PoliticsSourceEvidence:
    stem = row["stem"] or ""
    explanation = row["explanation"] or ""
    source_type, title, event_date, evidence, confidence = infer_politics_source(stem, explanation)
    return PoliticsSourceEvidence(
        question_id=row["id"],
        paper_id=row["paper_id"],
        year=row["year"],
        region=row["region"],
        number=row["number"],
        stem=stem,
        source_type=source_type,
        source_title=title,
        event_date=event_date,
        evidence_text=evidence,
        confidence=confidence,
    )


def infer_politics_source(stem: str, explanation: str) -> tuple[str, str, str | None, str, str]:
    text = f"{stem}\n{explanation}"

    qstheory = _match_qstheory(text)
    if qstheory:
        return qstheory

    document = _match_document(text)
    if document:
        return document

    report = _match_party_report(text)
    if report:
        return report

    media = _match_media_explainer(text)
    if media:
        return media

    speech = _match_speech_or_meeting(text)
    if speech:
        return speech

    textbook = _match_textbook_marxism(text)
    if textbook:
        return textbook

    return ("media_explainer", "待人工核验题源", None, _one_line(explanation or stem)[:260], "low")


def _match_qstheory(text: str) -> tuple[str, str, str | None, str, str] | None:
    patterns = [
        r"《求是》杂志(?:发表|刊发)(?:了)?(?:习近平总书记)?(?:的)?(?:重要文章|署名文章)?《(?P<title>[^》]+)》",
        r"《求是》(?:杂志)?(?:发表|刊发)(?:的)?习近平总书记(?:重要文章|署名文章)?《(?P<title>[^》]+)》",
        r"第\d+期《求是》杂志(?:发表|刊发)(?:了)?(?:习近平总书记)?(?:重要文章)?《(?P<title>[^》]+)》",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            evidence = _sentence_around(text, match.start())
            return ("qstheory_article", f"《{match.group('title')}》", _extract_date(evidence), evidence, "high")
    return None


def _match_document(text: str) -> tuple[str, str, str | None, str, str] | None:
    for match in re.finditer(r"《(?P<title>[^》]+)》", text):
        title = match.group("title")
        if not _looks_like_policy_document(title):
            continue
        evidence = _sentence_around(text, match.start())
        source_type = "local_policy" if _looks_like_local_policy(title) else "central_document"
        if _looks_like_ministry_policy(title):
            source_type = "ministry_policy"
        return (source_type, f"《{title}》", _extract_nearby_date(text, match.start()) or _extract_date(evidence), evidence, "high")
    return None


def _match_party_report(text: str) -> tuple[str, str, str | None, str, str] | None:
    match = re.search(r"(党的)?二十大报告|政府工作报告", text)
    if not match:
        return None
    evidence = _sentence_around(text, match.start())
    title = "党的二十大报告" if "二十大" in match.group(0) else "政府工作报告"
    return ("party_report", title, _extract_date(evidence), evidence, "high")


def _match_media_explainer(text: str) -> tuple[str, str, str | None, str, str] | None:
    pattern = r"(?P<source>人民网|国家统计局(?:官网)?|中央纪委国家监委官网|学习时报)[^。；\n]*《(?P<title>[^》]+)》"
    match = re.search(pattern, text)
    if not match:
        return None
    evidence = _sentence_around(text, match.start())
    return ("media_explainer", f"{match.group('source')}《{match.group('title')}》", _extract_date(evidence), evidence, "medium")


def _match_speech_or_meeting(text: str) -> tuple[str, str, str | None, str, str] | None:
    date_prefix = r"(?P<date>20\d{2}年\d{1,2}月\d{1,2}日(?:至\d{1,2}日)?)"
    event_words = r"(?:会议|座谈会|集体学习|考察|讲话|大会|研讨班|峰会|致辞|贺词|活动|全会)"
    match = re.search(date_prefix + rf"(?P<body>[^。\n]{{0,120}}{event_words}[^。\n]{{0,80}})", text)
    if match:
        evidence = _sentence_around(text, match.start())
        title = _clean_event_title(match.group("body"))
        return ("leader_speech_or_meeting", title, _extract_date(match.group("date")), evidence, "medium")

    undated = re.search(r"(中央[^。\n]{0,80}(?:会议|座谈会|全会)|全国[^。\n]{0,80}(?:会议|大会))", text)
    if undated:
        evidence = _sentence_around(text, undated.start())
        return ("leader_speech_or_meeting", _clean_event_title(undated.group(1)), _extract_date(evidence), evidence, "medium")
    return None


def _match_textbook_marxism(text: str) -> tuple[str, str, str | None, str, str] | None:
    keywords = (
        "马克思主义",
        "唯物辩证法",
        "矛盾",
        "实践观",
        "政治经济学",
        "商品的价值量",
        "量变",
        "质变",
        "系统思维",
        "联系具有普遍性",
    )
    if any(keyword in text for keyword in keywords):
        evidence = _sentence_around(text, 0) if text else ""
        return ("textbook_marxism", "马克思主义基础理论/教材型知识", None, evidence[:260], "medium")
    return None


def _looks_like_policy_document(title: str) -> bool:
    policy_tokens = (
        "决定",
        "建议",
        "意见",
        "规划",
        "纲要",
        "条例",
        "通知",
        "行动计划",
        "白皮书",
        "报告",
        "学习纲要",
        "读本",
    )
    authority_tokens = (
        "中共中央",
        "国务院",
        "中央办公厅",
        "国务院办公厅",
        "国家",
        "中国共产党",
        "四川省委",
        "重庆市委",
        "四川省",
        "重庆市",
        "习近平新时代中国特色社会主义思想",
    )
    return any(token in title for token in policy_tokens) and (
        any(token in title for token in authority_tokens) or len(title) <= 32
    )


def _looks_like_local_policy(title: str) -> bool:
    return any(token in title for token in ("四川省委", "重庆市委", "四川省第", "重庆市第", "四川省人民政府", "重庆市人民政府"))


def _looks_like_ministry_policy(title: str) -> bool:
    return any(token in title for token in ("教育部", "科技部", "人力资源社会保障部", "国家民委", "国家统计局"))


def _extract_date(text: str) -> str | None:
    match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_nearby_date(text: str, offset: int) -> str | None:
    window_start = max(0, offset - 180)
    window_end = min(len(text), offset + 180)
    return _extract_date(text[window_start:window_end])


def _sentence_around(text: str, offset: int) -> str:
    start = max(text.rfind("。", 0, offset), text.rfind("\n", 0, offset), text.rfind("；", 0, offset))
    end_candidates = [pos for pos in (text.find("。", offset), text.find("\n", offset), text.find("；", offset)) if pos != -1]
    end = min(end_candidates) if end_candidates else min(len(text), offset + 260)
    return _one_line(text[start + 1 : end + 1])[:420]


def _clean_event_title(value: str) -> str:
    value = re.sub(r"^(，|,|在|于|出版的第\d+期|中共中央总书记、国家主席、中央军委主席习近平)", "", value)
    value = re.sub(r"（以下简称[^）]+）", "", value)
    return _one_line(value).strip("，, ：:。")[:80] or "习近平重要讲话/会议通稿"


def _one_line(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def add_analyze_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    analyze = subparsers.add_parser("analyze", help="Analyze indexed exam content.")
    analyze_sub = analyze.add_subparsers(dest="kind", required=True)
    politics = analyze_sub.add_parser("politics-sources", help="Extract source evidence for political theory questions.")
    politics.add_argument("--years", default="2025,2026")
    politics.add_argument("--paper-kind", default="行测")
    politics.add_argument("--knowledge-point", default="政治理论")
    politics.add_argument("--dedupe", choices=("stem", "none"), default="stem")
    politics.add_argument("--apply", action="store_true", help="Write extracted evidence to question_sources.")
