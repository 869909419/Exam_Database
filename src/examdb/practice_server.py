from __future__ import annotations

import json
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db
from .config import Paths
from .practice import (
    analyze_session_with_ai,
    create_session,
    finish_session,
    metadata,
    recent_sessions,
    save_review,
    session_payload,
    stats,
    submit_answer,
)
from .reviews import write_question_review_cards


WEB_ROOT = Path(__file__).with_name("web")


def serve_practice_app(paths: Paths, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = _handler(paths)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"ExamDB practice server: http://{host}:{port}")
    server.serve_forever()


def _handler(paths: Paths):
    class PracticeHandler(SimpleHTTPRequestHandler):
        server_version = "ExamDBPractice/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/metadata":
                    self._send_json(metadata(self._conn()))
                    return
                if parsed.path == "/api/stats":
                    query = parse_qs(parsed.query)
                    days = int((query.get("days") or ["30"])[0])
                    self._send_json(stats(self._conn(), days=days))
                    return
                if parsed.path == "/api/sessions":
                    self._send_json({"sessions": recent_sessions(self._conn())})
                    return
                if parsed.path.startswith("/api/sessions/"):
                    parts = _parts(parsed.path)
                    if len(parts) == 3:
                        self._send_json(session_payload(self._conn(), parts[2]))
                        return
                self._serve_static(parsed.path)
            except Exception as exc:
                self._send_error(exc)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
                parts = _parts(parsed.path)
                conn = self._conn()
                if parsed.path == "/api/sessions":
                    self._send_json(create_session(conn, payload), status=HTTPStatus.CREATED)
                    return
                if len(parts) == 4 and parts[0:2] == ["api", "sessions"] and parts[3] == "finish":
                    self._send_json(finish_session(conn, parts[2]))
                    return
                if len(parts) == 4 and parts[0:2] == ["api", "sessions"] and parts[3] == "ai-analysis":
                    self._send_json(analyze_session_with_ai(conn, parts[2]))
                    return
                if len(parts) == 6 and parts[0:2] == ["api", "sessions"] and parts[3] == "items" and parts[5] == "answer":
                    result = submit_answer(conn, parts[2], parts[4], payload)
                    write_question_review_cards(conn, paths.vault)
                    self._send_json(result)
                    return
                if len(parts) == 6 and parts[0:2] == ["api", "sessions"] and parts[3] == "items" and parts[5] == "review":
                    result = save_review(conn, parts[2], parts[4], payload)
                    write_question_review_cards(conn, paths.vault)
                    self._send_json(result)
                    return
                self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self._send_error(exc)

        def _conn(self):
            conn = db.connect(paths.db)
            db.init_schema(conn)
            return conn

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or "0")
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw) if raw else {}

        def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, exc: Exception) -> None:
            status = HTTPStatus.NOT_FOUND if isinstance(exc, KeyError) else HTTPStatus.BAD_REQUEST
            self._send_json({"error": type(exc).__name__, "message": str(exc)}, status=status)

        def _serve_static(self, path: str) -> None:
            target = "index.html" if path in {"", "/"} else path.removeprefix("/")
            file_path = (WEB_ROOT / target).resolve()
            if WEB_ROOT.resolve() not in file_path.parents and file_path != WEB_ROOT.resolve():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", _content_type(file_path))
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args) -> None:
            print(f"{self.address_string()} - {format % args}")

    return PracticeHandler


def _parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _content_type(path: Path) -> str:
    if path.suffix == ".html":
        return "text/html; charset=utf-8"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "text/javascript; charset=utf-8"
    return "application/octet-stream"
