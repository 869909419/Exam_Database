from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import db
from .config import Paths
from .markdown import paper_markdown, slugify, write_question_cards, write_text
from .models import ExamPaper, Question
from .taxonomy import (
    suggest_question_format,
    suggest_question_metadata,
    validate_paper_kind,
    validate_question_type,
)


@dataclass
class ExtractedText:
    text: str
    quality_status: str = "needs_review"
    warnings: list[str] = field(default_factory=list)


def extract_text(path: Path) -> str:
    return extract_paper_text(path).text


def extract_paper_text(path: Path) -> ExtractedText:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return ExtractedText(path.read_text(encoding="utf-8"), quality_status="needs_review")
    if suffix == ".pdf":
        return extract_pdf_text(path)
    raise ValueError(f"Unsupported paper file type: {path.suffix}")


def extract_pdf_text(path: Path) -> ExtractedText:
    warnings: list[str] = []
    text = ""
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(path)) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        warnings.append(f"pdfplumber unavailable or failed: {type(exc).__name__}")

    if not text.strip():
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            warnings.append(f"pypdf unavailable or failed: {type(exc).__name__}")

    stripped = text.strip()
    if not stripped:
        return ExtractedText(
            f"[PDF text extraction unavailable]\n\nSource file: {path}",
            quality_status="needs_ocr",
            warnings=warnings + ["empty_text"],
        )
    if len(stripped) < 500:
        warnings.append("low_text_volume")
        return ExtractedText(text, quality_status="needs_review", warnings=warnings)
    return ExtractedText(text, quality_status="parsed", warnings=warnings)


def infer_paper_metadata(path: Path) -> tuple[str, str, int | None, str, str]:
    name = path.stem
    year_match = re.search(r"(20\d{2})", name)
    year = int(year_match.group(1)) if year_match else None
    exam_category = "事业编" if any(keyword in name for keyword in ("事业编", "事业单位", "职测", "综应", "公基")) else "公务员"

    if "四川" in name:
        exam_type, region = "省考", "四川"
    elif "重庆" in name:
        exam_type, region = "省考", "重庆"
    elif "事业" in name or exam_category == "事业编":
        exam_type, region = "事业编", "全国"
    elif "国考" in name or "国家公务员" in name:
        exam_type, region = "国考", "全国"
    else:
        exam_type, region = "国考", "全国"

    if "申论" in name:
        paper_kind = "申论"
    elif "职测" in name or "职业能力" in name:
        paper_kind = "职测"
    elif "综应" in name or "综合应用" in name:
        paper_kind = "综应"
    elif "公基" in name or "公共基础" in name:
        paper_kind = "公基"
    else:
        paper_kind = "行测"
    return exam_type, region, year, exam_category, paper_kind


def parse_questions(text: str, paper_id: str, paper_kind: str | None = None) -> list[Question]:
    answer_map = parse_answer_map(text)
    explanation_map = parse_explanations(text)
    body_text = strip_answer_sections(text)
    pattern = re.compile(r"(?:^|\n)\s*(\d{1,3})[.、]\s*(.+?)(?=\n\s*\d{1,3}[.、]\s+|\Z)", re.S)
    questions: list[Question] = []
    for match in pattern.finditer(body_text):
        number, body = match.groups()
        body = body.strip()
        options = parse_options(body)
        stem = parse_stem(body)
        if not stem:
            continue
        suggestion = suggest_question_metadata(stem, options, paper_kind=paper_kind)
        question_type = validate_question_type(suggestion.tags[0] if suggestion.tags else None)
        question_format = suggest_question_format(stem, options, paper_kind=paper_kind)
        warnings: list[str] = []
        if not options and paper_kind in {None, "行测", "职测", "公基"}:
            warnings.append("missing_options")
        if number not in answer_map:
            warnings.append("missing_answer")
        if number not in explanation_map:
            warnings.append("missing_explanation")
        qid = hashlib.sha256(f"{paper_id}:{number}:{stem}".encode("utf-8")).hexdigest()[:16]
        questions.append(
            Question(
                id=f"q-{qid}",
                paper_id=paper_id,
                number=number,
                stem=stem,
                options=options,
                answer=answer_map.get(number),
                explanation=explanation_map.get(number),
                explanation_source="source_file" if number in explanation_map else None,
                explanation_status="fetched" if number in explanation_map else "missing",
                question_type=question_type,
                question_format=question_format,
                knowledge_points=suggestion.topics,
                difficulty="medium",
                source_span=body[:500],
                review_status="needs_review",
                parse_warnings=warnings,
            )
        )
    return questions


def parse_options(body: str) -> dict[str, str]:
    matches = re.findall(r"(?:^|\n)\s*([A-E])[.、]\s*([^\n]+)", body)
    return {key: value.strip() for key, value in matches}


def parse_stem(body: str) -> str:
    stem = re.split(r"\n\s*[A-E][.、]\s*", body.strip(), maxsplit=1)[0]
    return stem.strip()


def parse_answer_map(text: str) -> dict[str, str]:
    answers: dict[str, str] = {}
    answer_section = _section_after_keywords(text, ("答案", "参考答案"))
    if not answer_section:
        return answers
    for number, answer in re.findall(r"(\d{1,3})[.、：:\s]+([A-E]+|正确|错误|对|错)", answer_section):
        answers[number] = answer.strip()
    return answers


def parse_explanations(text: str) -> dict[str, str]:
    section = _section_after_keywords(text, ("解析", "参考解析", "答案解析"))
    if not section:
        return {}
    explanations: dict[str, str] = {}
    pattern = re.compile(r"(?:^|\n)\s*(\d{1,3})[.、]\s*(.+?)(?=\n\s*\d{1,3}[.、]\s+|\Z)", re.S)
    for number, explanation in pattern.findall(section):
        explanations[number] = explanation.strip()
    return explanations


def strip_answer_sections(text: str) -> str:
    marker = re.search(r"(?:^|\n)\s*(?:参考答案|答案解析|答案|解析)\s*(?:\n|$)", text)
    return text[: marker.start()] if marker else text


def _section_after_keywords(text: str, keywords: tuple[str, ...]) -> str:
    pattern = "|".join(re.escape(keyword) for keyword in keywords)
    match = re.search(rf"(?:^|\n)\s*(?:{pattern})\s*(?:\n|$)(.+)", text, re.S)
    return match.group(1) if match else ""


def import_paper(
    file_path: Path,
    paths: Paths,
    source_url: str | None = None,
    paper_kind: str | None = None,
    source_name: str | None = None,
) -> ExamPaper:
    paths.ensure()
    file_path = file_path.resolve()
    extracted = extract_paper_text(file_path)
    digest_source = f"{source_url or file_path}:{extracted.text}".encode("utf-8")
    digest = hashlib.sha256(digest_source).hexdigest()[:16]
    inferred_exam_type, region, year, exam_category, inferred_paper_kind = infer_paper_metadata(file_path)
    paper_kind = validate_paper_kind(paper_kind or inferred_paper_kind)
    paper_id = f"paper-{digest}"

    raw_path = archive_source_file(file_path, paths, source_name or "local", paper_id)
    processed_path = paths.processed / "papers" / f"{paper_id}.md"
    write_text(processed_path, extracted.text.strip() + "\n")

    questions = parse_questions(extracted.text, paper_id, paper_kind=paper_kind)
    quality_status = extracted.quality_status
    if not questions and quality_status == "parsed":
        quality_status = "needs_review"
        extracted.warnings.append("no_questions_parsed")

    title_slug = slugify(file_path.stem)
    markdown_path = paths.vault / "题库" / "真题套卷" / f"{year or 'unknown'}-{region}-{paper_kind or '未知'}-{title_slug}.md"
    paper = ExamPaper(
        id=paper_id,
        exam_category=exam_category,
        exam_type=inferred_exam_type,
        region=region,
        year=year,
        paper_kind=paper_kind,
        source_name=source_name,
        source_url=source_url,
        source_file=str(raw_path.relative_to(paths.root)),
        markdown_path=str(markdown_path.relative_to(paths.root)),
        question_count=len(questions),
        import_status="imported",
        quality_status=quality_status,
        parse_warnings=extracted.warnings,
    )
    write_text(markdown_path, paper_markdown(paper, extracted.text))

    conn = db.connect(paths.db)
    db.init_schema(conn)
    db.upsert_paper(conn, paper)
    for question in questions:
        db.upsert_question(conn, question)
    write_question_cards(paths.vault, questions)
    return paper


def archive_source_file(file_path: Path, paths: Paths, source_name: str, paper_id: str) -> Path:
    safe_source = slugify(source_name, fallback="local")
    archive_dir = paths.raw / "papers" / safe_source / paper_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"source{file_path.suffix.lower()}"
    try:
        if file_path.resolve() != target.resolve():
            shutil.copy2(file_path, target)
    except FileNotFoundError:
        shutil.copy2(file_path, target)
    return target
