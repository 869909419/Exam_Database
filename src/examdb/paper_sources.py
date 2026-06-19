from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from . import db
from .config import Paths
from .markdown import slugify
from .models import PaperCandidate
from .papers import infer_paper_metadata


SOURCE_NAMES = {
    "fenbi": "粉笔",
    "offcn": "中公",
    "huatu": "华图",
    "web": "网络搜索",
    "manual": "手工来源",
}


@dataclass
class DownloadResult:
    candidate_id: str
    status: str
    path: str | None = None
    blocked_reason: str | None = None


@dataclass
class FenbiFetchResult:
    paper_id: str
    exercise_key: str | None
    paper_kind: str = "行测"
    status: str
    path: str | None = None
    source_url: str | None = None
    blocked_reason: str | None = None


@dataclass
class FenbiPaperListing:
    paper_id: str
    title: str
    paper_kind: str
    label_id: str
    date: str | None = None
    difficulty: str | None = None
    question_count: int | None = None
    combine_key: str | None = None


def discover_paper_candidates(paths: Paths, source_id: str, query: str, limit: int | None = None) -> list[PaperCandidate]:
    paths.ensure()
    conn = db.connect(paths.db)
    db.init_schema(conn)
    source_name = SOURCE_NAMES.get(source_id, source_id)
    candidates = _discover_from_url(source_id, source_name, query, limit) if _is_url(query) else [
        _search_intent_candidate(source_id, source_name, query)
    ]
    for candidate in candidates:
        db.upsert_paper_candidate(conn, candidate)
    return candidates


def discover_fenbi_papers(
    paths: Paths,
    *,
    label_id: str,
    paper_kind: str = "xingce",
    page_size: int = 50,
    headed: bool = False,
    timeout_seconds: int = 180,
) -> list[FenbiPaperListing]:
    paths.ensure()
    script = paths.root / "scripts" / "playwright" / "fenbi_list_papers.mjs"
    try:
        command = _playwright_command(paths, script)
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc

    auth_state = paths.root / "data" / "auth" / "fenbi" / "storage-state.json"
    output_file = paths.raw / "papers" / "fenbi" / "paper-list" / f"{paper_kind}-{label_id}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if auth_state.exists():
        env["FENBI_AUTH_STATE"] = str(auth_state)
    env["FENBI_LABEL_ID"] = label_id
    env["FENBI_PAPER_KIND"] = paper_kind
    env["FENBI_PAGE_SIZE"] = str(page_size)
    env["FENBI_OUTPUT_FILE"] = str(output_file)
    env["FENBI_HEADLESS"] = "0" if headed else "1"
    env["FENBI_TIMEOUT_MS"] = str(timeout_seconds * 1000)

    try:
        completed = subprocess.run(command, cwd=paths.root, env=env, text=True, capture_output=True, timeout=timeout_seconds + 30)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("fenbi paper discovery timed out") from exc
    if completed.returncode != 0:
        reason = _sanitize_playwright_output(completed.stderr or completed.stdout)
        raise RuntimeError(reason or "fenbi paper discovery failed")
    try:
        payload = json.loads(output_file.read_text(encoding="utf-8")) if output_file.exists() else _last_json_line(completed.stdout)
    except Exception as exc:
        raise RuntimeError(f"could not parse fenbi paper discovery result: {exc}") from exc

    listings: list[FenbiPaperListing] = []
    for item in payload.get("papers") or []:
        paper_id = str(item.get("paperId") or "")
        title = str(item.get("name") or "")
        if not paper_id or not title:
            continue
        listings.append(
            FenbiPaperListing(
                paper_id=paper_id,
                title=title,
                paper_kind=paper_kind,
                label_id=label_id,
                date=str(item.get("date") or "") or None,
                difficulty=str(item.get("difficulty") or "") or None,
                question_count=int(item.get("exerciseCount") or 0) or None,
                combine_key=str(item.get("combineKey") or "") or None,
            )
        )
    return listings


def download_paper_candidates(paths: Paths, source_id: str | None = None, limit: int | None = None) -> list[DownloadResult]:
    paths.ensure()
    conn = db.connect(paths.db)
    db.init_schema(conn)
    rows = db.list_paper_candidates(conn, source_id=source_id, download_status="pending", limit=limit)
    results: list[DownloadResult] = []
    for row in rows:
        download_url = row["download_url"]
        if not download_url:
            reason = "missing_download_url"
            db.update_paper_candidate_status(conn, row["id"], download_status="blocked", blocked_reason=reason)
            results.append(DownloadResult(candidate_id=row["id"], status="blocked", blocked_reason=reason))
            continue
        target = _candidate_pdf_path(paths, row)
        try:
            download_pdf(download_url, target)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            db.update_paper_candidate_status(conn, row["id"], download_status="blocked", blocked_reason=reason)
            results.append(DownloadResult(candidate_id=row["id"], status="blocked", blocked_reason=reason))
            continue
        local_path = str(target.relative_to(paths.root))
        db.update_paper_candidate_status(conn, row["id"], download_status="downloaded", local_path=local_path)
        results.append(DownloadResult(candidate_id=row["id"], status="downloaded", path=local_path))
    return results


def verify_fenbi_login(paths: Paths, sample_url: str | None = None, timeout_seconds: int = 120) -> DownloadResult:
    paths.ensure()
    username = os.environ.get("FENBI_USERNAME")
    password = os.environ.get("FENBI_PASSWORD")
    if not username or not password:
        return DownloadResult(
            candidate_id="fenbi-login",
            status="blocked",
            blocked_reason="missing FENBI_USERNAME or FENBI_PASSWORD",
        )
    auth_dir = paths.root / "data" / "auth" / "fenbi"
    download_dir = paths.raw / "papers" / "fenbi" / "verification"
    auth_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    script = paths.root / "scripts" / "playwright" / "fenbi_verify.mjs"
    try:
        command = _playwright_command(paths, script)
    except RuntimeError as exc:
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason=str(exc))
    env = os.environ.copy()
    env["FENBI_AUTH_DIR"] = str(auth_dir)
    env["FENBI_DOWNLOAD_DIR"] = str(download_dir)
    if sample_url:
        env["FENBI_SAMPLE_URL"] = sample_url
    try:
        completed = subprocess.run(command, cwd=paths.root, env=env, text=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason="verification timed out")
    if completed.returncode != 0:
        reason = _sanitize_playwright_output(completed.stderr or completed.stdout)
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason=reason or "fenbi verification failed")
    path = _first_pdf(download_dir)
    if not path:
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason="login succeeded but no PDF download was captured")
    return DownloadResult(candidate_id="fenbi-login", status="downloaded", path=str(path.relative_to(paths.root)))


def auth_fenbi_login(
    paths: Paths,
    *,
    headed: bool = False,
    manual: bool = False,
    timeout_seconds: int = 180,
) -> DownloadResult:
    paths.ensure()
    if not manual and (not os.environ.get("FENBI_USERNAME") or not os.environ.get("FENBI_PASSWORD")):
        return DownloadResult(
            candidate_id="fenbi-login",
            status="blocked",
            blocked_reason="missing FENBI_USERNAME or FENBI_PASSWORD; use --manual to log in by hand",
        )

    auth_dir = paths.root / "data" / "auth" / "fenbi"
    auth_dir.mkdir(parents=True, exist_ok=True)
    script = paths.root / "scripts" / "playwright" / "fenbi_auth.mjs"
    try:
        command = _playwright_command(paths, script)
    except RuntimeError as exc:
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason=str(exc))
    env = os.environ.copy()
    env["FENBI_AUTH_DIR"] = str(auth_dir)
    env["FENBI_HEADLESS"] = "0" if headed or manual else "1"
    env["FENBI_MANUAL_LOGIN"] = "1" if manual else "0"
    env["FENBI_TIMEOUT_MS"] = str(timeout_seconds * 1000)
    try:
        completed = subprocess.run(command, cwd=paths.root, env=env, text=True, capture_output=True, timeout=timeout_seconds + 30)
    except subprocess.TimeoutExpired:
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason="login timed out")
    if completed.returncode != 0:
        reason = _sanitize_playwright_output(completed.stderr or completed.stdout)
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason=reason or "fenbi login failed")
    state = auth_dir / "storage-state.json"
    if not state.exists():
        return DownloadResult(candidate_id="fenbi-login", status="blocked", blocked_reason="login completed but storage state was not saved")
    return DownloadResult(candidate_id="fenbi-login", status="authenticated", path=str(state.relative_to(paths.root)))


def fetch_fenbi_solution(
    paths: Paths,
    *,
    paper_id: str,
    routecs: str = "xingce",
    prefix: str = "xingce",
    categories: str = "xingce",
    font_exer_id: str = "3",
    headed: bool = False,
    timeout_seconds: int = 180,
    delay_ms: int = 1500,
    paper_kind: str = "行测",
) -> FenbiFetchResult:
    paths.ensure()
    auth_state = paths.root / "data" / "auth" / "fenbi" / "storage-state.json"
    if not auth_state.exists():
        return FenbiFetchResult(
            paper_id=paper_id,
            exercise_key=None,
            paper_kind=paper_kind,
            status="blocked",
            blocked_reason="missing data/auth/fenbi/storage-state.json; run auth fenbi-login first",
        )

    output_dir = paths.raw / "papers" / "fenbi" / f"paper-{paper_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "solution.json"
    script_name = "fenbi_fetch_shenlun_solution.mjs" if paper_kind == "申论" or routecs == "shenlun" else "fenbi_fetch_solution.mjs"
    script = paths.root / "scripts" / "playwright" / script_name
    try:
        command = _playwright_command(paths, script)
    except RuntimeError as exc:
        return FenbiFetchResult(paper_id=paper_id, exercise_key=None, paper_kind=paper_kind, status="blocked", blocked_reason=str(exc))
    env = os.environ.copy()
    env["FENBI_AUTH_STATE"] = str(auth_state)
    env["FENBI_PAPER_ID"] = paper_id
    env["FENBI_ROUTECS"] = routecs
    env["FENBI_PREFIX"] = prefix
    env["FENBI_CATEGORIES"] = categories
    env["FENBI_FONT_EXER_ID"] = font_exer_id
    env["FENBI_OUTPUT_FILE"] = str(output_file)
    env["FENBI_HEADLESS"] = "0" if headed else "1"
    env["FENBI_TIMEOUT_MS"] = str(timeout_seconds * 1000)
    env["FENBI_DELAY_MS"] = str(delay_ms)
    try:
        completed = subprocess.run(command, cwd=paths.root, env=env, text=True, capture_output=True, timeout=timeout_seconds + 30)
    except subprocess.TimeoutExpired:
        return FenbiFetchResult(paper_id=paper_id, exercise_key=None, paper_kind=paper_kind, status="blocked", blocked_reason="fetch timed out")
    if completed.returncode != 0:
        reason = _sanitize_playwright_output(completed.stderr or completed.stdout)
        return FenbiFetchResult(paper_id=paper_id, exercise_key=None, paper_kind=paper_kind, status="blocked", blocked_reason=reason or "fenbi solution fetch failed")
    try:
        payload = _last_json_line(completed.stdout)
    except ValueError as exc:
        return FenbiFetchResult(paper_id=paper_id, exercise_key=None, paper_kind=paper_kind, status="blocked", blocked_reason=str(exc))
    if not output_file.exists():
        return FenbiFetchResult(paper_id=paper_id, exercise_key=payload.get("exerciseKey"), paper_kind=paper_kind, status="blocked", blocked_reason="solution file was not saved")
    return FenbiFetchResult(
        paper_id=paper_id,
        exercise_key=payload.get("exerciseKey") or payload.get("combineKey"),
        paper_kind=paper_kind,
        status="downloaded",
        path=str(output_file.relative_to(paths.root)),
        source_url=payload.get("sourceUrl"),
    )


def _playwright_command(paths: Paths, script: Path) -> list[str]:
    if not script.exists():
        raise RuntimeError(f"playwright script not found: {script.relative_to(paths.root)}")
    if (paths.root / "node_modules" / "playwright").exists():
        if shutil.which("node") is None:
            raise RuntimeError("node is not installed")
        return ["node", str(script)]
    if shutil.which("npx") is None:
        raise RuntimeError("Playwright is not installed; run npm install in the project root or install npx")
    return ["npx", "--yes", "--package", "playwright@1.61.0", "node", str(script)]


def download_pdf(url: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "ExamDB/0.1 (+public exam paper archive)"})
    with urlopen(request, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()
    if not _looks_like_pdf(url, content_type, data):
        raise ValueError("response is not a PDF")
    path.write_bytes(data)
    return path


def _discover_from_url(source_id: str, source_name: str, url: str, limit: int | None) -> list[PaperCandidate]:
    request = Request(url, headers={"User-Agent": "ExamDB/0.1 (+public exam paper archive)"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="ignore")
    links = _extract_pdf_links(html, url)
    if limit is not None:
        links = links[:limit]
    return [_candidate_from_link(source_id, source_name, page_url=url, link_text=text, download_url=href) for text, href in links]


def _extract_pdf_links(html: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    pattern = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
    for href, raw_text in pattern.findall(html):
        absolute = urljoin(base_url, href)
        text = re.sub(r"<[^>]+>", "", raw_text).strip() or Path(urlparse(absolute).path).name
        if ".pdf" in absolute.lower() or "pdf" in text.lower():
            links.append((text, absolute))
    return links


def _candidate_from_link(source_id: str, source_name: str, page_url: str, link_text: str, download_url: str) -> PaperCandidate:
    filename = Path(urlparse(download_url).path).name
    title = link_text or filename or download_url
    fake_path = Path(title)
    exam_type, region, year, exam_category, paper_kind = infer_paper_metadata(fake_path)
    candidate_id = _candidate_id(source_id, page_url, download_url)
    return PaperCandidate(
        id=candidate_id,
        source_id=source_id,
        source_name=source_name,
        title=title,
        url=page_url,
        download_url=download_url,
        exam_category=exam_category,
        exam_type=exam_type,
        region=region,
        year=year,
        paper_kind=paper_kind,
        download_status="pending",
    )


def _search_intent_candidate(source_id: str, source_name: str, query: str) -> PaperCandidate:
    now = datetime.now().isoformat(timespec="seconds")
    candidate_id = _candidate_id(source_id, f"search:{query}", "")
    return PaperCandidate(
        id=candidate_id,
        source_id=source_id,
        source_name=source_name,
        title=query,
        url=f"search:{source_id}:{query}",
        download_status="blocked",
        blocked_reason="free-text discovery requires a concrete public URL or browser search implementation",
        notes="Use a public listing URL to auto-extract PDF links.",
        created_at=now,
        updated_at=now,
    )


def _candidate_pdf_path(paths: Paths, row) -> Path:
    source = slugify(row["source_id"], fallback="source")
    title = slugify(row["title"], fallback=row["id"])
    return paths.raw / "papers" / source / row["id"] / f"{title}.pdf"


def _candidate_id(source_id: str, url: str, download_url: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{url}:{download_url}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-{digest}"


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _looks_like_pdf(url: str, content_type: str, data: bytes) -> bool:
    return data.startswith(b"%PDF") or "application/pdf" in content_type.lower() or url.lower().split("?")[0].endswith(".pdf")


def _first_pdf(directory: Path) -> Path | None:
    for path in sorted(directory.glob("*.pdf")):
        if path.stat().st_size > 0:
            return path
    return None


def _sanitize_playwright_output(output: str) -> str:
    redacted = output
    for key in ("FENBI_USERNAME", "FENBI_PASSWORD"):
        value = os.environ.get(key)
        if value:
            redacted = redacted.replace(value, "[redacted]")
    return redacted.strip()[-500:]


def _last_json_line(output: str) -> dict:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    raise ValueError("playwright script did not return JSON metadata")
