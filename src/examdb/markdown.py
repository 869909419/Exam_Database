from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import ArticleRecord, ExamPaper, Question


def slugify(value: str, fallback: str = "untitled") -> str:
    value = re.sub(r"[\\/:*?\"<>|#\[\]]+", "-", value).strip()
    value = re.sub(r"\s+", "-", value)
    value = value.strip(".-")
    return value or fallback


def yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def article_markdown(article: ArticleRecord) -> str:
    metadata = {
        "title": article.title,
        "source": article.source,
        "url": article.url,
        "published_at": article.published_at,
        "authors": article.authors,
        "tags": article.tags,
        "topics": article.topics,
        "images": article.image_paths,
        "hash": article.content_hash,
        "raw_path": article.raw_path,
        "ingested_at": article.ingested_at,
        "status": article.status,
    }
    return f"{frontmatter(metadata)}\n\n# {article.title}\n\n{article.content.strip()}\n"


def paper_markdown(paper: ExamPaper, body: str) -> str:
    metadata = {
        "paper_id": paper.id,
        "exam_category": paper.exam_category,
        "exam_type": paper.exam_type,
        "region": paper.region,
        "year": paper.year,
        "paper_kind": paper.paper_kind,
        "source_name": paper.source_name,
        "source_url": paper.source_url,
        "source_file": paper.source_file,
        "question_count": paper.question_count,
        "import_status": paper.import_status,
        "quality_status": paper.quality_status,
        "parse_warnings": paper.parse_warnings,
    }
    return f"{frontmatter(metadata)}\n\n# {paper.year or '未知年份'} {paper.region}{paper.exam_type}真题\n\n{body.strip()}\n"


def question_markdown(question: Question) -> str:
    metadata = {
        "question_id": question.id,
        "paper_id": question.paper_id,
        "number": question.number,
        "question_type": question.question_type,
        "knowledge_points": question.knowledge_points,
        "difficulty": question.difficulty,
        "answer": question.answer,
        "explanation_source": question.explanation_source,
        "explanation_status": question.explanation_status,
        "source_span": question.source_span,
        "question_format": question.question_format,
        "review_status": question.review_status,
        "parse_warnings": question.parse_warnings,
    }
    options = "\n".join(f"- {key}. {value}" for key, value in question.options.items())
    return (
        f"{frontmatter(metadata)}\n\n"
        f"# 第 {question.number} 题\n\n"
        f"{question.stem.strip()}\n\n"
        f"{options}\n\n"
        f"## 解析\n\n{question.explanation or ''}\n"
    )


def write_question_cards(vault: Path, questions: list[Question]) -> list[Path]:
    written: list[Path] = []
    material_groups: dict[str, list[Question]] = {}
    singles: list[Question] = []
    for question in questions:
        material_group = _material_group_from_source_span(question.source_span)
        if material_group:
            material_groups.setdefault(material_group, []).append(question)
        else:
            singles.append(question)

    grouped_ids: set[str] = set()
    for group_key, group_questions in material_groups.items():
        if len(group_questions) < 2:
            singles.extend(group_questions)
            continue
        group_questions.sort(key=_question_sort_key)
        written.append(write_text(grouped_question_card_path(vault, group_key, group_questions), grouped_question_markdown(group_questions)))
        grouped_ids.update(question.id for question in group_questions)

    for question in singles:
        if question.id in grouped_ids:
            continue
        written.append(write_text(question_card_path(vault, question), question_markdown(question)))
    return written


def question_card_path(vault: Path, question: Question) -> Path:
    section = slugify(question.knowledge_points[0] if question.knowledge_points else question.question_type or "未分类")
    filename = f"{int(question.number):03d}.md" if question.number.isdigit() else f"{slugify(question.number, fallback='题目')}.md"
    base = vault / "题库" / "题目卡片" / question.paper_id / section
    material_group = _material_group_from_source_span(question.source_span)
    if material_group:
        base = base / material_group
    return base / filename


def grouped_question_card_path(vault: Path, material_group: str, questions: list[Question]) -> Path:
    first = questions[0]
    section = slugify(first.knowledge_points[0] if first.knowledge_points else first.question_type or "未分类")
    start = questions[0].number
    end = questions[-1].number
    if start.isdigit() and end.isdigit():
        filename = f"{int(start):03d}-{int(end):03d}-材料题组.md"
    else:
        filename = f"{start}-{end}-材料题组.md"
    return vault / "题库" / "题目卡片" / first.paper_id / section / material_group / filename


def grouped_question_markdown(questions: list[Question]) -> str:
    first = questions[0]
    material, _ = _split_material(first.stem)
    knowledge_points = list(dict.fromkeys(point for question in questions for point in question.knowledge_points))
    metadata = {
        "paper_id": first.paper_id,
        "question_ids": [question.id for question in questions],
        "numbers": [question.number for question in questions],
        "question_type": first.question_type,
        "question_format": "材料题组",
        "knowledge_points": knowledge_points,
        "explanation_status": "fetched" if all(question.explanation_status == "fetched" for question in questions) else "partial",
        "source_span": first.source_span,
        "review_status": "needs_review",
    }
    lines = [frontmatter(metadata), "", f"# 第 {questions[0].number}-{questions[-1].number} 题 材料题组", ""]
    if material:
        lines.extend(["## 材料", "", material, ""])
    for question in questions:
        _, stem = _split_material(question.stem)
        lines.extend([f"## 第 {question.number} 题", "", stem.strip(), ""])
        for key, value in question.options.items():
            lines.append(f"- {key}. {value}")
        if question.answer:
            lines.extend(["", f"**答案：{question.answer}**"])
        if question.explanation:
            lines.extend(["", "### 解析", "", question.explanation])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


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


def _question_sort_key(question: Question) -> tuple[int, str]:
    return (int(question.number), "") if question.number.isdigit() else (10**9, question.number)
