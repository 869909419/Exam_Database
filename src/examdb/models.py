from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ArticleRecord:
    id: str
    title: str
    source: str
    url: str
    published_at: str | None
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    content: str = ""
    content_hash: str = ""
    raw_path: str | None = None
    markdown_path: str | None = None
    status: str = "parsed"
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class ExamPaper:
    id: str
    exam_type: str
    region: str
    year: int | None
    source_url: str | None
    source_file: str
    markdown_path: str
    question_count: int = 0
    import_status: str = "imported"
    exam_category: str = "公务员"
    paper_kind: str | None = None
    source_name: str | None = None
    quality_status: str = "needs_review"
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class Question:
    id: str
    paper_id: str
    number: str
    stem: str
    options: dict[str, str] = field(default_factory=dict)
    answer: str | None = None
    explanation: str | None = None
    explanation_source: str | None = None
    explanation_status: str = "missing"
    question_type: str | None = None
    knowledge_points: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    source_span: str | None = None
    question_format: str | None = None
    review_status: str = "needs_review"
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class PaperCandidate:
    id: str
    source_id: str
    source_name: str
    title: str
    url: str
    download_url: str | None = None
    exam_category: str = "公务员"
    exam_type: str | None = None
    region: str | None = None
    year: int | None = None
    paper_kind: str | None = None
    download_status: str = "pending"
    import_status: str = "pending"
    blocked_reason: str | None = None
    notes: str | None = None
    local_path: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class QuestionSource:
    id: str
    question_id: str
    source_name: str
    source_url: str | None = None
    external_question_id: str | None = None
    matched_stem: str | None = None
    matched_answer: str | None = None
    matched_explanation: str | None = None
    match_confidence: str = "low"
    status: str = "needs_lookup"
    fetched_at: str | None = None
    notes: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class PracticeAttempt:
    id: str
    question_id: str
    selected_answer: str | None
    is_correct: bool | None
    duration_seconds: int | None
    confidence: int | None
    note: str | None
    attempted_at: str
