import json
import tempfile
import unittest

from examdb import db
from examdb.config import Paths
from examdb.models import ArticleRecord
from examdb.sync import sync_article_metadata_from_markdown


class SyncTests(unittest.TestCase):
    def test_dry_run_does_not_modify_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_article(tmp)
            before = self._db_metadata(paths)

            result = sync_article_metadata_from_markdown(paths)

            self.assertEqual(result.scanned, 1)
            self.assertEqual(len(result.changes), 1)
            self.assertEqual(self._db_metadata(paths), before)

    def test_apply_overwrites_sqlite_from_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_article(tmp)

            result = sync_article_metadata_from_markdown(paths, apply=True)

            self.assertTrue(result.changes[0].applied)
            self.assertEqual(self._db_metadata(paths), (["民生", "就业"], ["就业", "申论素材"], "manual-reviewed"))

    def _setup_article(self, tmp: str) -> Paths:
        paths = Paths.from_root(tmp)
        paths.ensure()
        note_path = paths.vault / "资料库" / "政策理论" / "gov-policy" / "2026" / "06-17" / "就业.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(
            """---
title: "就业政策"
source: "中国政府网"
url: "https://example.com/job-sync"
published_at: "2026-06-17"
authors:
tags:
  - "民生"
  - "就业"
topics:
  - "就业"
  - "申论素材"
images:
hash: "hash-job-sync"
raw_path: "data/raw/articles/gov-policy/job-sync.html"
ingested_at: "2026-06-17T12:00:00"
status: "manual-reviewed"
---

# 就业政策

就业是最基本的民生。
""",
            encoding="utf-8",
        )
        conn = db.connect(paths.db)
        db.init_schema(conn)
        db.upsert_article(
            conn,
            ArticleRecord(
                id="article-job-sync",
                title="就业政策",
                source="中国政府网",
                url="https://example.com/job-sync",
                published_at="2026-06-17",
                tags=["民生"],
                topics=["申论素材"],
                content_hash="hash-job-sync",
                markdown_path=str(note_path.relative_to(paths.root)),
            ),
        )
        return paths

    def _db_metadata(self, paths: Paths) -> tuple[list[str], list[str], str]:
        conn = db.connect(paths.db)
        row = conn.execute(
            "SELECT tags_json, topics_json, status FROM articles WHERE id = ?",
            ("article-job-sync",),
        ).fetchone()
        return json.loads(row["tags_json"]), json.loads(row["topics_json"]), row["status"]


if __name__ == "__main__":
    unittest.main()
