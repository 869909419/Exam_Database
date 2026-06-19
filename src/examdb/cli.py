from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from . import db
from .config import Paths
from .enrichment import enrich_explanations
from .fenbi import import_fenbi_solution, parse_fenbi_solution
from .ingest import ingest_articles
from .markdown import write_question_cards
from .paper_sources import (
    auth_fenbi_login,
    discover_fenbi_papers,
    discover_paper_candidates,
    download_paper_candidates,
    fetch_fenbi_solution,
    verify_fenbi_login,
)
from .papers import import_paper
from .practice import list_questions
from .reports import weekly_report
from .retag import retag_articles
from .sync import sync_article_metadata_from_markdown
from .taxonomy import suggest_question_format, suggest_question_metadata, validate_question_type


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="examdb")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create vault/data directories and initialize SQLite schema.")

    ingest = subparsers.add_parser("ingest", help="Ingest public materials.")
    ingest_sub = ingest.add_subparsers(dest="kind", required=True)
    articles = ingest_sub.add_parser("articles")
    articles.add_argument("--source", required=True)
    articles.add_argument("--since", default=(date.today() - timedelta(days=365)).isoformat())
    articles.add_argument("--limit", type=int)
    articles.add_argument("--refresh", action="store_true", help="Re-fetch and overwrite articles that already exist in SQLite.")

    import_cmd = subparsers.add_parser("import", help="Import local materials.")
    import_sub = import_cmd.add_subparsers(dest="kind", required=True)
    paper = import_sub.add_parser("paper")
    paper.add_argument("--file", required=True)
    paper.add_argument("--source-url")
    paper.add_argument("--paper-kind")
    paper.add_argument("--source-name")
    fenbi_solution = import_sub.add_parser("fenbi-solution", help="Import Fenbi static/solution JSON with answers and explanations.")
    fenbi_solution.add_argument("--file", required=True)
    fenbi_solution.add_argument("--source-url")
    fenbi_solution.add_argument("--paper-kind")
    fenbi_solution.add_argument("--expected-sections", help="Comma-separated section names to validate before import.")
    fenbi_solution.add_argument("--expected-question-count", type=int)
    fenbi_solution.add_argument("--strict", action="store_true", help="Abort import when expected structure does not match.")

    inspect = subparsers.add_parser("inspect", help="Inspect local source files before import.")
    inspect_sub = inspect.add_subparsers(dest="kind", required=True)
    inspect_fenbi = inspect_sub.add_parser("fenbi-solution", help="Inspect Fenbi static/solution JSON structure.")
    inspect_fenbi.add_argument("--file", required=True)
    inspect_fenbi.add_argument("--paper-kind", default="行测")
    inspect_fenbi.add_argument("--expected-sections", help="Comma-separated section names to validate, in order.")
    inspect_fenbi.add_argument("--expected-question-count", type=int)
    inspect_fenbi.add_argument("--strict", action="store_true", help="Exit non-zero when expected structure does not match.")

    auth = subparsers.add_parser("auth", help="Authenticate source sessions.")
    auth_sub = auth.add_subparsers(dest="kind", required=True)
    auth_fenbi = auth_sub.add_parser("fenbi-login", help="Log in to Fenbi and save local browser storage state.")
    auth_fenbi.add_argument("--headed", action="store_true", help="Show browser while logging in.")
    auth_fenbi.add_argument("--manual", action="store_true", help="Wait for you to complete login manually.")
    auth_fenbi.add_argument("--timeout", type=int, default=180)

    fetch = subparsers.add_parser("fetch", help="Fetch source data with saved local auth.")
    fetch_sub = fetch.add_subparsers(dest="kind", required=True)
    fetch_fenbi = fetch_sub.add_parser("fenbi-solution", help="Fetch Fenbi static/solution JSON by paper id.")
    fetch_fenbi.add_argument("--paper-id", required=True, help="Fenbi paperId from the paper list URL/API.")
    fetch_fenbi.add_argument("--routecs", default="xingce")
    fetch_fenbi.add_argument("--prefix", default="xingce")
    fetch_fenbi.add_argument("--categories", default="xingce")
    fetch_fenbi.add_argument("--font-exer-id", default="3")
    fetch_fenbi.add_argument("--headed", action="store_true")
    fetch_fenbi.add_argument("--timeout", type=int, default=180)
    fetch_fenbi.add_argument("--delay-ms", type=int, default=1500)
    fetch_fenbi.add_argument("--paper-kind", default="行测")
    fetch_fenbi.add_argument("--shenlun", action="store_true", help="Shortcut for --paper-kind 申论 and routecs=shenlun.")
    fetch_fenbi.add_argument("--expected-sections", help="Comma-separated section names to validate after fetch.")
    fetch_fenbi.add_argument("--expected-question-count", type=int)
    fetch_fenbi.add_argument("--strict", action="store_true")
    fetch_fenbi.add_argument("--import", dest="import_after", action="store_true", help="Import into SQLite and vault after fetch and validation.")

    verify = subparsers.add_parser("verify", help="Verify external source access.")
    verify_sub = verify.add_subparsers(dest="kind", required=True)
    fenbi_login = verify_sub.add_parser("fenbi-login", help="Verify Fenbi login and one free PDF download.")
    fenbi_login.add_argument("--sample-url")
    fenbi_login.add_argument("--timeout", type=int, default=120)

    discover = subparsers.add_parser("discover", help="Discover source materials.")
    discover_sub = discover.add_subparsers(dest="kind", required=True)
    discover_papers = discover_sub.add_parser("papers")
    discover_papers.add_argument("--source", required=True)
    discover_papers.add_argument("--query", required=True)
    discover_papers.add_argument("--limit", type=int)
    discover_fenbi = discover_sub.add_parser("fenbi-papers", help="Discover Fenbi paper ids by label id.")
    discover_fenbi.add_argument("--label-id", required=True, help="Fenbi labelId from the paper list API/page.")
    discover_fenbi.add_argument("--paper-kind", choices=("xingce", "shenlun"), default="xingce")
    discover_fenbi.add_argument("--page-size", type=int, default=50)
    discover_fenbi.add_argument("--headed", action="store_true")
    discover_fenbi.add_argument("--timeout", type=int, default=180)

    download = subparsers.add_parser("download", help="Download discovered source materials.")
    download_sub = download.add_subparsers(dest="kind", required=True)
    download_papers = download_sub.add_parser("papers")
    download_papers.add_argument("--source")
    download_papers.add_argument("--limit", type=int)

    enrich = subparsers.add_parser("enrich", help="Enrich indexed content from external sources.")
    enrich_sub = enrich.add_subparsers(dest="kind", required=True)
    enrich_explanations_cmd = enrich_sub.add_parser("explanations", help="Queue or apply answer/explanation matches.")
    enrich_explanations_cmd.add_argument("--paper-id", required=True)
    enrich_explanations_cmd.add_argument("--source", default="fenbi")
    enrich_explanations_cmd.add_argument("--source-file", help="JSON or JSONL question explanation matches.")
    enrich_explanations_cmd.add_argument("--limit", type=int)
    enrich_explanations_cmd.add_argument("--apply", action="store_true")

    classify = subparsers.add_parser("classify", help="Classify indexed content.")
    classify_sub = classify.add_subparsers(dest="kind", required=True)
    questions = classify_sub.add_parser("questions")
    questions.add_argument("--paper-id", required=True)
    questions.add_argument("--apply", action="store_true")

    review = subparsers.add_parser("review", help="Review queues.")
    review_sub = review.add_subparsers(dest="kind", required=True)
    review_papers = review_sub.add_parser("papers")
    review_papers.add_argument("--status", default="needs_review")
    review_papers.add_argument("--limit", type=int)

    practice = subparsers.add_parser("practice", help="Practice workflow helpers.")
    practice_sub = practice.add_subparsers(dest="kind", required=True)
    start = practice_sub.add_parser("start")
    start.add_argument("--filter", default=None)

    report = subparsers.add_parser("report", help="Generate reports.")
    report_sub = report.add_subparsers(dest="kind", required=True)
    report_sub.add_parser("weekly")

    retag = subparsers.add_parser("retag", help="Re-tag indexed content.")
    retag_sub = retag.add_subparsers(dest="kind", required=True)
    retag_articles_cmd = retag_sub.add_parser("articles", help="Suggest and sync article tags/topics with DeepSeek.")
    retag_articles_cmd.add_argument("--source")
    retag_articles_cmd.add_argument("--since")
    retag_articles_cmd.add_argument("--limit", type=int)
    retag_articles_cmd.add_argument("--path")
    retag_articles_cmd.add_argument("--only-needs-review", action="store_true")
    retag_articles_cmd.add_argument("--apply", action="store_true", help="Write suggested tags/topics to Markdown and SQLite.")

    sync = subparsers.add_parser("sync", help="Synchronize indexed metadata.")
    sync_sub = sync.add_subparsers(dest="kind", required=True)
    sync_articles_cmd = sync_sub.add_parser("articles", help="Sync article tags/topics/status from Markdown into SQLite.")
    sync_articles_cmd.add_argument("--source")
    sync_articles_cmd.add_argument("--since")
    sync_articles_cmd.add_argument("--limit", type=int)
    sync_articles_cmd.add_argument("--path")
    sync_articles_cmd.add_argument("--only-changed", action="store_true")
    sync_articles_cmd.add_argument("--apply", action="store_true", help="Write Markdown frontmatter tags/topics/status into SQLite.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = Paths.from_root(args.root)

    if args.command == "init":
        paths.ensure()
        conn = db.connect(paths.db)
        db.init_schema(conn)
        print(f"Initialized ExamDB at {paths.root}")
        return 0

    if args.command == "ingest" and args.kind == "articles":
        since = date.fromisoformat(args.since)
        result = ingest_articles(args.source, since=since, paths=paths, limit=args.limit, refresh=args.refresh)
        print(f"Ingested {len(result.written)} articles")
        if result.skipped_existing:
            print(f"Skipped {result.skipped_existing} existing articles")
        for path in result.written:
            print(path)
        return 0

    if args.command == "import" and args.kind == "paper":
        paper = import_paper(
            Path(args.file).resolve(),
            paths=paths,
            source_url=args.source_url,
            paper_kind=args.paper_kind,
            source_name=args.source_name,
        )
        print(f"Imported paper {paper.id}: {paper.markdown_path} ({paper.question_count} questions)")
        return 0

    if args.command == "import" and args.kind == "fenbi-solution":
        if args.expected_sections or args.expected_question_count is not None:
            check_status = _inspect_fenbi_solution(
                Path(args.file).resolve(),
                paper_kind=args.paper_kind,
                expected_sections=args.expected_sections,
                expected_question_count=args.expected_question_count,
                strict=args.strict,
            )
            if check_status != 0:
                return check_status
        paper = import_fenbi_solution(
            Path(args.file).resolve(),
            paths=paths,
            source_url=args.source_url,
            paper_kind=args.paper_kind,
        )
        print(f"Imported Fenbi solution {paper.id}: {paper.markdown_path} ({paper.question_count} questions)")
        return 0

    if args.command == "inspect" and args.kind == "fenbi-solution":
        return _inspect_fenbi_solution(
            Path(args.file).resolve(),
            paper_kind=args.paper_kind,
            expected_sections=args.expected_sections,
            expected_question_count=args.expected_question_count,
            strict=args.strict,
        )

    if args.command == "auth" and args.kind == "fenbi-login":
        result = auth_fenbi_login(paths, headed=args.headed, manual=args.manual, timeout_seconds=args.timeout)
        if result.status == "authenticated":
            print(f"Fenbi auth saved: {result.path}")
            return 0
        print(f"Fenbi auth blocked: {result.blocked_reason}")
        return 2

    if args.command == "fetch" and args.kind == "fenbi-solution":
        paper_kind = "申论" if args.shenlun else args.paper_kind
        routecs = "shenlun" if paper_kind == "申论" else args.routecs
        result = fetch_fenbi_solution(
            paths,
            paper_id=args.paper_id,
            routecs=routecs,
            prefix=args.prefix,
            categories=args.categories,
            font_exer_id=args.font_exer_id,
            headed=args.headed,
            timeout_seconds=args.timeout,
            delay_ms=args.delay_ms,
            paper_kind=paper_kind,
        )
        if result.status != "downloaded":
            print(f"Fenbi solution fetch blocked: {result.blocked_reason}")
            return 2
        print(f"Fenbi solution saved: {result.path}")
        if result.source_url:
            print(f"Source URL: {result.source_url}")
        solution_file = paths.root / result.path
        if args.expected_sections or args.expected_question_count is not None:
            check_status = _inspect_fenbi_solution(
                solution_file,
                paper_kind=paper_kind,
                expected_sections=args.expected_sections,
                expected_question_count=args.expected_question_count,
                strict=args.strict,
            )
            if check_status != 0:
                return check_status
        if args.import_after:
            paper = import_fenbi_solution(
                solution_file,
                paths=paths,
                source_url=result.source_url,
                paper_kind=paper_kind,
            )
            print(f"Imported Fenbi solution {paper.id}: {paper.markdown_path} ({paper.question_count} questions)")
        return 0

    if args.command == "verify" and args.kind == "fenbi-login":
        result = verify_fenbi_login(paths, sample_url=args.sample_url, timeout_seconds=args.timeout)
        if result.status == "downloaded":
            print(f"Fenbi verification downloaded: {result.path}")
            return 0
        print(f"Fenbi verification blocked: {result.blocked_reason}")
        return 2

    if args.command == "discover" and args.kind == "papers":
        candidates = discover_paper_candidates(paths, source_id=args.source, query=args.query, limit=args.limit)
        print(f"Discovered {len(candidates)} paper candidates")
        for candidate in candidates:
            print(f"- {candidate.id} [{candidate.download_status}] {candidate.title}")
            print(f"  {candidate.download_url or candidate.url}")
            if candidate.blocked_reason:
                print(f"  blocked: {candidate.blocked_reason}")
        return 0

    if args.command == "discover" and args.kind == "fenbi-papers":
        try:
            listings = discover_fenbi_papers(
                paths,
                label_id=args.label_id,
                paper_kind=args.paper_kind,
                page_size=args.page_size,
                headed=args.headed,
                timeout_seconds=args.timeout,
            )
        except RuntimeError as exc:
            print(f"Fenbi paper discovery blocked: {exc}")
            return 2
        print(f"Discovered {len(listings)} Fenbi papers")
        for listing in listings:
            details = []
            if listing.date:
                details.append(listing.date)
            if listing.question_count:
                details.append(f"{listing.question_count} questions")
            suffix = f" ({', '.join(details)})" if details else ""
            print(f"- {listing.paper_id} [{listing.paper_kind}] {listing.title}{suffix}")
        return 0

    if args.command == "download" and args.kind == "papers":
        results = download_paper_candidates(paths, source_id=args.source, limit=args.limit)
        print(f"Processed {len(results)} paper candidates")
        for result in results:
            if result.status == "downloaded":
                print(f"- {result.candidate_id}: downloaded {result.path}")
            else:
                print(f"- {result.candidate_id}: blocked {result.blocked_reason}")
        return 0

    if args.command == "enrich" and args.kind == "explanations":
        source_file = Path(args.source_file) if args.source_file else None
        result = enrich_explanations(
            paths,
            paper_id=args.paper_id,
            source_name=args.source,
            source_file=source_file,
            apply=args.apply,
            limit=args.limit,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(
            f"{mode}: scanned {result.scanned} questions, "
            f"queued {result.queued}, matched {result.matched}, applied {result.applied}"
        )
        for change in result.changes:
            suffix = " applied" if change.applied else ""
            print(f"- {change.number} {change.status}{suffix}: {change.reason or ''} {change.source_id or ''}".rstrip())
        return 0

    if args.command == "classify" and args.kind == "questions":
        conn = db.connect(paths.db)
        db.init_schema(conn)
        paper_row = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (args.paper_id,)).fetchone()
        if paper_row is None:
            print(f"Paper not found: {args.paper_id}")
            return 2
        rows = db.question_rows_for_paper(conn, args.paper_id)
        changed = 0
        for row in rows:
            options = json.loads(row["options_json"])
            suggestion = suggest_question_metadata(row["stem"], options, paper_kind=paper_row["paper_kind"])
            question_type = validate_question_type(suggestion.tags[0] if suggestion.tags else None)
            question_format = suggest_question_format(row["stem"], options, paper_kind=paper_row["paper_kind"])
            print(f"- {row['number']}: {row['question_type'] or '未分类'} -> {question_type} ({suggestion.confidence})")
            if args.apply:
                knowledge_points = json.loads(row["knowledge_points_json"])
                merged_points = list(dict.fromkeys(knowledge_points + suggestion.topics))
                conn.execute(
                    """
                    UPDATE questions
                    SET question_type = ?,
                        question_format = ?,
                        knowledge_points_json = ?,
                        review_status = CASE WHEN review_status = 'verified' THEN review_status ELSE 'needs_review' END
                    WHERE id = ?
                    """,
                    (
                        question_type,
                        question_format,
                        json.dumps(merged_points, ensure_ascii=False),
                        row["id"],
                    ),
                )
                changed += 1
        if args.apply:
            conn.commit()
            write_question_cards(paths.vault, [_question_from_row(row) for row in db.question_rows_for_paper(conn, args.paper_id)])
            print(f"Applied classification to {changed} questions")
        return 0

    if args.command == "review" and args.kind == "papers":
        conn = db.connect(paths.db)
        db.init_schema(conn)
        rows = conn.execute(
            """
            SELECT id, exam_category, exam_type, region, year, paper_kind, question_count, markdown_path, quality_status
            FROM exam_papers
            WHERE quality_status = ?
            ORDER BY year DESC, region, paper_kind
            LIMIT ?
            """,
            (args.status, args.limit or 100),
        ).fetchall()
        for row in rows:
            print(
                f"{row['id']} [{row['quality_status']}] "
                f"{row['year'] or 'unknown'} {row['region']} {row['exam_type']} {row['paper_kind'] or ''} "
                f"({row['question_count']} questions) {row['markdown_path']}"
            )
        print(f"Listed {len(rows)} papers")
        return 0

    if args.command == "practice" and args.kind == "start":
        conn = db.connect(paths.db)
        db.init_schema(conn)
        rows = list_questions(conn, query=args.filter)
        for row in rows:
            print(f"{row['id']} [{row['question_type'] or '未分类'}] {row['stem'][:80]}")
        print(f"Listed {len(rows)} questions")
        return 0

    if args.command == "report" and args.kind == "weekly":
        conn = db.connect(paths.db)
        db.init_schema(conn)
        path = weekly_report(conn, paths.vault / "刷题记录" / "周报")
        print(path)
        return 0

    if args.command == "retag" and args.kind == "articles":
        since = date.fromisoformat(args.since) if args.since else None
        target_path = Path(args.path) if args.path else None
        result = retag_articles(
            paths,
            source=args.source,
            since=since,
            limit=args.limit,
            target_path=target_path,
            only_needs_review=args.only_needs_review,
            apply=args.apply,
        )
        if result.missing_api_key:
            print("未设置 DEEPSEEK_API_KEY，未执行 tags 修正。")
            print('临时预览：DEEPSEEK_API_KEY="你的_key" scripts/obsidian/retag_policy_articles.sh')
            print('写入修正：DEEPSEEK_API_KEY="你的_key" scripts/obsidian/retag_policy_articles.sh --apply')
            return 2
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode}: scanned {result.scanned} articles, suggested {len(result.changes)} updates")
        for change in result.changes:
            flags = []
            if change.out_of_sync:
                flags.append("out_of_sync")
            if change.applied:
                flags.append("applied")
            if change.error:
                flags.append(change.error)
            suffix = f" [{' | '.join(flags)}]" if flags else ""
            print(f"- {change.title}{suffix}")
            print(f"  {change.markdown_path}")
            print(f"  tags: {change.old_tags} -> {change.new_tags}")
            print(f"  topics: {change.old_topics} -> {change.new_topics}")
        if not args.apply:
            print("Dry-run only. Re-run with --apply to write Markdown and SQLite.")
        return 0

    if args.command == "sync" and args.kind == "articles":
        since = date.fromisoformat(args.since) if args.since else None
        target_path = Path(args.path) if args.path else None
        result = sync_article_metadata_from_markdown(
            paths,
            source=args.source,
            since=since,
            limit=args.limit,
            target_path=target_path,
            only_changed=args.only_changed,
            apply=args.apply,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode}: scanned {result.scanned} articles, found {len(result.changes)} SQLite updates")
        for change in result.changes:
            flags = []
            if change.applied:
                flags.append("applied")
            if change.error:
                flags.append(change.error)
            suffix = f" [{' | '.join(flags)}]" if flags else ""
            print(f"- {change.title}{suffix}")
            print(f"  {change.markdown_path}")
            print(f"  tags: {change.old_tags} -> {change.new_tags}")
            print(f"  topics: {change.old_topics} -> {change.new_topics}")
            print(f"  status: {change.old_status!r} -> {change.new_status!r}")
        if not args.apply:
            print("Dry-run only. Re-run with --apply to overwrite SQLite from Markdown.")
        return 0

    raise SystemExit("Unhandled command")


def _question_from_row(row):
    from .models import Question

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


def _inspect_fenbi_solution(
    file_path: Path,
    paper_kind: str | None,
    expected_sections: str | None,
    expected_question_count: int | None,
    strict: bool,
) -> int:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    title = payload.get("name") or file_path.stem
    sections = _fenbi_sections(payload.get("card", {}))
    questions = parse_fenbi_solution(payload, paper_id="inspect", paper_kind=paper_kind)
    material_groups: dict[str, list[str]] = {}
    for question in questions:
        material_key = _material_key_from_source_span(question.source_span)
        if material_key:
            material_groups.setdefault(material_key, []).append(question.number)

    print(f"Title: {title}")
    print(f"Questions: {len(questions)}")
    print("Sections:")
    for section in sections:
        start = section["numbers"][0] if section["numbers"] else "?"
        end = section["numbers"][-1] if section["numbers"] else "?"
        print(f"- {section['name']}: {start}-{end} ({len(section['numbers'])})")
    print("Material groups:")
    for material_key, numbers in sorted(material_groups.items(), key=lambda item: int(item[1][0]) if item[1][0].isdigit() else 10**9):
        if len(numbers) < 2:
            continue
        print(f"- {numbers[0]}-{numbers[-1]}: {material_key} ({len(numbers)})")

    errors: list[str] = []
    if expected_question_count is not None and len(questions) != expected_question_count:
        errors.append(f"expected {expected_question_count} questions, got {len(questions)}")
    if expected_sections:
        expected = [item.strip() for item in expected_sections.split(",") if item.strip()]
        actual = [section["name"] for section in sections]
        if actual != expected:
            errors.append(f"expected sections {expected}, got {actual}")
    if errors:
        print("Structure check: FAILED")
        for error in errors:
            print(f"- {error}")
        return 2 if strict else 0
    print("Structure check: OK")
    return 0


def _fenbi_sections(card: dict) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    for section in card.get("children") or []:
        if not isinstance(section, dict):
            continue
        numbers: list[str] = []
        for child in section.get("children") or []:
            if isinstance(child, dict) and child.get("nodeType") == 2:
                numbers.append(str(len(numbers) + 1))
        sections.append({"name": str(section.get("name") or ""), "numbers": numbers})
    offset = 0
    for section in sections:
        numbers = section["numbers"]
        if isinstance(numbers, list):
            section["numbers"] = [str(offset + index + 1) for index in range(len(numbers))]
            offset += len(numbers)
    return sections


def _material_key_from_source_span(source_span: str | None) -> str | None:
    if not source_span:
        return None
    for part in source_span.split(";"):
        if part.startswith("materials:"):
            return part.split(":", 1)[1].split(",", 1)[0]
    return None
