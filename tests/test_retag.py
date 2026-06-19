import json
import tempfile
import unittest
from pathlib import Path

from examdb import db
from examdb.config import Paths
from examdb.models import ArticleRecord
from examdb.retag import parse_markdown_note, retag_articles


class FakeDeepSeekClient:
    enabled = True

    def __init__(self, response: dict):
        self.response = response

    def chat_json(self, system: str, user: str) -> dict:
        return self.response


class DisabledClient:
    enabled = False


class RetagTests(unittest.TestCase):
    def test_dry_run_does_not_modify_markdown_or_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, note_path = self._setup_article(tmp)
            before_note = note_path.read_text(encoding="utf-8")
            before_db = self._db_tags(paths)

            result = retag_articles(
                paths,
                client=FakeDeepSeekClient({"tags": ["民生"], "topics": ["就业"], "confidence": "high"}),
            )

            self.assertEqual(result.scanned, 1)
            self.assertTrue(result.changes[0].out_of_sync)
            self.assertEqual(note_path.read_text(encoding="utf-8"), before_note)
            self.assertEqual(self._db_tags(paths), before_db)

    def test_apply_updates_markdown_and_sqlite_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, note_path = self._setup_article(tmp)

            result = retag_articles(
                paths,
                apply=True,
                client=FakeDeepSeekClient({"tags": ["民生"], "topics": ["就业"], "confidence": "high"}),
            )

            self.assertTrue(result.changes[0].applied)
            metadata, _body = parse_markdown_note(note_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["tags"], ["民生"])
            self.assertEqual(metadata["topics"], ["就业"])
            self.assertEqual(metadata["status"], "ai-retagged")
            self.assertEqual(self._db_tags(paths), (["民生"], ["就业"], "ai-retagged"))

    def test_illegal_deepseek_tags_are_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, note_path = self._setup_article(tmp)

            retag_articles(
                paths,
                apply=True,
                client=FakeDeepSeekClient({"tags": ["就业", "民生"], "topics": ["就业"], "confidence": "high"}),
            )

            metadata, _body = parse_markdown_note(note_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["tags"], ["民生"])
            self.assertNotIn("就业", metadata["tags"])
            self.assertEqual(metadata["topics"], ["就业"])

    def test_missing_api_key_exits_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, note_path = self._setup_article(tmp)
            before_note = note_path.read_text(encoding="utf-8")

            result = retag_articles(paths, apply=True, client=DisabledClient())

            self.assertTrue(result.missing_api_key)
            self.assertEqual(note_path.read_text(encoding="utf-8"), before_note)

    def _setup_article(self, tmp: str) -> tuple[Paths, Path]:
        paths = Paths.from_root(tmp)
        paths.ensure()
        note_path = paths.vault / "资料库" / "政策理论" / "gov-policy" / "2026" / "06-17" / "就业.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            """---
title: "就业政策"
source: "中国政府网"
url: "https://example.com/job"
published_at: "2026-06-17"
authors:
tags:
  - "民生"
  - "就业"
topics:
  - "申论素材"
images:
hash: "hash-job"
raw_path: "data/raw/articles/gov-policy/job.html"
ingested_at: "2026-06-17T12:00:00"
status: "parsed"
---

# 就业政策

就业是最基本的民生。要促进高质量充分就业。
""",
            encoding="utf-8",
        )
        conn = db.connect(paths.db)
        db.init_schema(conn)
        db.upsert_article(
            conn,
            ArticleRecord(
                id="article-job",
                title="就业政策",
                source="中国政府网",
                url="https://example.com/job",
                published_at="2026-06-17",
                tags=["民生"],
                topics=["申论素材"],
                content_hash="hash-job",
                markdown_path=str(note_path.relative_to(paths.root)),
            ),
        )
        return paths, note_path

    def _db_tags(self, paths: Paths) -> tuple[list[str], list[str], str]:
        conn = db.connect(paths.db)
        row = conn.execute("SELECT tags_json, topics_json, status FROM articles WHERE id = ?", ("article-job",)).fetchone()
        return json.loads(row["tags_json"]), json.loads(row["topics_json"]), row["status"]


if __name__ == "__main__":
    unittest.main()
