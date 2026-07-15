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
    session_id: str | None = None
    position: int | None = None
    mistake_reason: str | None = None
    review_note: str | None = None
    updated_at: str | None = None


@dataclass
class PracticeSession:
    id: str
    mode: str
    title: str
    config: dict
    status: str = "active"
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: str | None = None
    total_count: int = 0
    correct_count: int = 0
    duration_seconds: int | None = None
    ai_summary: str | None = None
    ai_status: str = "not_requested"
    ai_generated_at: str | None = None


@dataclass
class PracticeSessionItem:
    id: str
    session_id: str
    question_id: str
    position: int
    material_group: str | None = None
    selected_answer: str | None = None
    is_correct: bool | None = None
    duration_seconds: int | None = None
    answered_at: str | None = None
    review_note: str | None = None
    mistake_reason: str | None = None
    confidence: int | None = None
    favorite: bool = False


@dataclass
class QuestionReview:
    question_id: str
    mistake_reason: str | None = None
    review_note: str | None = None
    confidence: int | None = None
    favorite: bool = False
    last_attempt_id: str | None = None
    last_attempted_at: str | None = None
    markdown_path: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
