from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

from . import db
from .config import Paths
from .markdown import paper_markdown, slugify, write_question_cards, write_text
from .models import ExamPaper, Question
from .papers import infer_paper_metadata
from .taxonomy import suggest_question_format, suggest_question_metadata, validate_paper_kind, validate_question_type


CHOICE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def import_fenbi_solution(
    file_path: Path,
    paths: Paths,
    source_url: str | None = None,
    paper_kind: str | None = None,
) -> ExamPaper:
    paths.ensure()
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    title = str(payload.get("name") or file_path.stem)
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    paper_id = f"fenbi-{digest}"

    inferred_exam_type, region, year, exam_category, inferred_paper_kind = infer_paper_metadata(Path(f"{title}.md"))
    paper_kind = validate_paper_kind(paper_kind or inferred_paper_kind)

    raw_path = _archive_fenbi_json(file_path, paths, paper_id)
    questions = parse_fenbi_solution(payload, paper_id=paper_id, paper_kind=paper_kind)
    body = _solution_body_markdown(title, payload, questions)
    processed_path = paths.processed / "papers" / f"{paper_id}.md"
    write_text(processed_path, body)

    markdown_path = paths.vault / "题库" / "真题套卷" / f"{year or 'unknown'}-{region}-{paper_kind or '未知'}-{slugify(title)}.md"
    paper = ExamPaper(
        id=paper_id,
        exam_category=exam_category,
        exam_type=inferred_exam_type,
        region=region,
        year=year,
        paper_kind=paper_kind,
        source_name="粉笔",
        source_url=source_url,
        source_file=str(raw_path.relative_to(paths.root)),
        markdown_path=str(markdown_path.relative_to(paths.root)),
        question_count=len(questions),
        import_status="imported",
        quality_status="needs_review",
        parse_warnings=[] if questions else ["no_questions_parsed"],
    )
    write_text(markdown_path, paper_markdown(paper, body))

    conn = db.connect(paths.db)
    db.init_schema(conn)
    db.upsert_paper(conn, paper)
    for question in questions:
        db.upsert_question(conn, question)
    write_question_cards(paths.vault, questions)
    return paper


def parse_fenbi_solution(payload: dict[str, Any], paper_id: str, paper_kind: str | None = None) -> list[Question]:
    materials = {str(item.get("globalId")): item for item in payload.get("materials", []) if item.get("globalId")}
    card_by_key = _card_node_map(payload.get("card", {}))
    questions: list[Question] = []
    for index, item in enumerate(payload.get("solutions", []), start=1):
        global_id = str(item.get("globalId") or item.get("id") or index)
        card_node = card_by_key.get(global_id, {})
        module_name = card_node.get("module_name")
        material_keys = _material_keys(item, card_node)
        material_text = _material_text(material_keys, materials)
        stem = _join_blocks(material_text, _html_to_markdown(str(item.get("content") or "")))
        options = _options(item)
        question_type = _question_type(module_name, item, options, paper_kind)
        knowledge_points = _knowledge_points(item, module_name)
        answer = _correct_answer(item.get("correctAnswer"))
        explanation = _html_to_markdown(str(item.get("solution") or ""))
        question_format = _question_format(item, options, paper_kind)
        questions.append(
            Question(
                id=f"{paper_id}-q{index:03d}",
                paper_id=paper_id,
                number=str(index),
                stem=stem,
                options=options,
                answer=answer,
                explanation=explanation or None,
                explanation_source="fenbi_static_solution" if explanation else None,
                explanation_status="fetched" if explanation else "missing",
                question_type=question_type,
                question_format=question_format,
                knowledge_points=knowledge_points,
                source_span=_source_span(global_id, material_keys),
                review_status="needs_review",
            )
        )
    return questions


def _archive_fenbi_json(file_path: Path, paths: Paths, paper_id: str) -> Path:
    archive_dir = paths.raw / "papers" / "fenbi" / paper_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / "solution.json"
    if file_path.resolve() != target.resolve():
        shutil.copy2(file_path, target)
    return target


def _card_node_map(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any], current_name: str | None = None) -> None:
        name = str(node.get("name") or current_name or "")
        if node.get("nodeType") == 2 and node.get("key"):
            result[str(node["key"])] = {
                "module_name": name,
                "materialKeys": [str(key) for key in node.get("materialKeys") or []],
            }
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child, name)

    if isinstance(card, dict):
        walk(card)
    return result


def _material_keys(item: dict[str, Any], card_node: dict[str, Any]) -> list[str]:
    keys = [str(key) for key in item.get("materialKeys") or []]
    keys.extend(str(key) for key in card_node.get("materialKeys") or [])
    return list(dict.fromkeys(keys))


def _material_text(material_keys: list[str], materials: dict[str, dict[str, Any]]) -> str:
    blocks: list[str] = []
    for key in material_keys:
        material = materials.get(str(key))
        if material:
            text = _html_to_markdown(str(material.get("content") or ""))
            if text:
                blocks.append(f"【材料】\n{text}")
    return "\n\n".join(blocks)


def _source_span(global_id: str, material_keys: list[str]) -> str:
    parts = [f"fenbi:{global_id}"]
    if material_keys:
        parts.append(f"materials:{','.join(material_keys)}")
    return ";".join(parts)


def _options(item: dict[str, Any]) -> dict[str, str]:
    for accessory in item.get("accessories") or []:
        raw_options = accessory.get("options")
        if isinstance(raw_options, list):
            return {
                CHOICE_LETTERS[index]: _html_to_markdown(str(option))
                for index, option in enumerate(raw_options)
                if index < len(CHOICE_LETTERS)
            }
    return {}


def _correct_answer(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    choice = value.get("choice")
    if choice is None:
        return None
    parts = re.split(r"[,，\s]+", str(choice).strip())
    letters: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            index = int(part)
            if 0 <= index < len(CHOICE_LETTERS):
                letters.append(CHOICE_LETTERS[index])
        else:
            letters.append(part.upper())
    return "".join(letters) or None


def _question_type(module_name: str | None, item: dict[str, Any], options: dict[str, str], paper_kind: str | None) -> str | None:
    mapping = {
        "政治理论": "常识判断",
        "言语理解与表达": "言语理解",
        "常识判断": "常识判断",
        "数量关系": "数量关系",
        "判断推理": "判断推理",
        "资料分析": "资料分析",
    }
    if module_name in mapping:
        return validate_question_type(mapping[module_name])
    suggestion = suggest_question_metadata(_html_to_markdown(str(item.get("content") or "")), options, paper_kind=paper_kind)
    return validate_question_type(suggestion.tags[0] if suggestion.tags else None)


def _question_format(item: dict[str, Any], options: dict[str, str], paper_kind: str | None) -> str:
    correct = item.get("correctAnswer")
    if isinstance(correct, dict) and str(correct.get("type") or "") in {"202", "203"}:
        return "多选"
    return suggest_question_format(_html_to_markdown(str(item.get("content") or "")), options, paper_kind=paper_kind)


def _knowledge_points(item: dict[str, Any], module_name: str | None) -> list[str]:
    points = []
    if module_name:
        points.append(module_name)
    for point in item.get("keypoints") or []:
        if isinstance(point, dict) and point.get("name"):
            points.append(str(point["name"]))
    return list(dict.fromkeys(points))


def _solution_body_markdown(title: str, payload: dict[str, Any], questions: list[Question]) -> str:
    lines = [f"# {title}", ""]
    for question in questions:
        lines.append(f"## 第 {question.number} 题")
        lines.append("")
        lines.append(question.stem)
        lines.append("")
        for key, value in question.options.items():
            lines.append(f"- {key}. {value}")
        if question.answer:
            lines.extend(["", f"**答案：{question.answer}**"])
        if question.explanation:
            lines.extend(["", "### 解析", "", question.explanation])
        lines.append("")
    if payload.get("card"):
        lines.extend(["", "## 来源结构", "", "```json", json.dumps(payload["card"], ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines).strip() + "\n"


def _html_to_markdown(value: str) -> str:
    text = value or ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<p\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"<img\b[^>]*src=[\"']([^\"']+)[\"'][^>]*>", lambda m: f"![]({_absolute_url(m.group(1))})", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\u00a0", " ")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _absolute_url(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _join_blocks(*blocks: str) -> str:
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())
