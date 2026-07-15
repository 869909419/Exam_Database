import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from examdb import db
from examdb.config import Paths
from examdb.models import ExamPaper, Question
from examdb.practice import analyze_session_with_ai, create_session, finish_session, save_review, submit_answer
from examdb.reviews import sync_reviews_from_markdown, write_question_review_cards


class PracticeSystemTests(unittest.TestCase):
    def test_schema_adds_practice_tables_and_attempt_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "examdb.sqlite")
            conn.row_factory = sqlite3.Row
            db.init_schema(conn)
            tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertIn("practice_sessions", tables)
            self.assertIn("practice_session_items", tables)
            self.assertIn("question_reviews", tables)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(practice_attempts)")}
            self.assertIn("session_id", columns)
            self.assertIn("review_note", columns)
            conn.close()

    def test_section_session_keeps_material_group_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "section", "question_type": "资料分析", "count": 5})
            self.assertEqual(session["progress"]["total"], 5)
            self.assertEqual(len(session["cards"]), 1)
            self.assertEqual(session["cards"][0]["kind"], "material_group")
            numbers = [int(item["number"]) for item in session["cards"][0]["items"]]
            self.assertEqual(numbers, list(range(numbers[0], numbers[0] + 5)))
            conn.close()

    def test_mock_session_uses_guokao_template_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "mock", "template": "guokao-xingzheng"})
            self.assertEqual(session["progress"]["total"], 130)
            counts = {}
            for card in session["cards"]:
                for item in card["items"]:
                    counts[item["question_type"]] = counts.get(item["question_type"], 0) + 1
            self.assertEqual(counts["常识判断"], 35)
            self.assertEqual(counts["言语理解"], 30)
            self.assertEqual(counts["数量关系"], 10)
            self.assertEqual(counts["判断推理"], 35)
            self.assertEqual(counts["资料分析"], 20)
            conn.close()

    def test_answer_writes_item_attempt_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "section", "question_type": "常识判断", "count": 1})
            item_id = session["cards"][0]["items"][0]["id"]
            result = submit_answer(
                conn,
                session["session"]["id"],
                item_id,
                {"selected_answer": "A", "duration_seconds": 12, "confidence": 4},
            )
            self.assertTrue(result["item"]["is_correct"])
            attempt_count = conn.execute("SELECT COUNT(*) AS total FROM practice_attempts").fetchone()["total"]
            self.assertEqual(attempt_count, 1)
            review = conn.execute("SELECT * FROM question_reviews WHERE question_id = ?", (result["item"]["question_id"],)).fetchone()
            self.assertEqual(review["confidence"], 4)
            conn.close()

    def test_answers_are_revealed_only_after_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "section", "question_type": "常识判断", "count": 1})
            item_id = session["cards"][0]["items"][0]["id"]
            result = submit_answer(conn, session["session"]["id"], item_id, {"selected_answer": "A", "duration_seconds": 12})
            self.assertIsNone(result["item"]["answer"])
            self.assertIsNone(result["item"]["explanation"])

            finished = finish_session(conn, session["session"]["id"])
            item = finished["cards"][0]["items"][0]
            self.assertEqual(item["answer"], "A")
            self.assertEqual(item["explanation"], "解析内容")
            self.assertEqual(finished["session"]["status"], "finished")
            self.assertGreaterEqual(finished["session"]["duration_seconds"], 12)
            conn.close()

    def test_review_cards_sync_only_learning_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "section", "question_type": "常识判断", "count": 1})
            item_id = session["cards"][0]["items"][0]["id"]
            submit_answer(conn, session["session"]["id"], item_id, {"selected_answer": "B", "duration_seconds": 10})
            save_review(
                conn,
                session["session"]["id"],
                item_id,
                {"mistake_reason": "审题粗心", "review_note": "重新整理关键词", "confidence": 2},
            )
            written = write_question_review_cards(conn, paths.vault)
            self.assertEqual(len(written), 1)
            note = written[0].read_text(encoding="utf-8").replace("重新整理关键词", "画出否定词")
            written[0].write_text(note, encoding="utf-8")

            dry_run = sync_reviews_from_markdown(paths)
            self.assertEqual(len(dry_run.changes), 1)
            sync_reviews_from_markdown(paths, apply=True)
            row = conn.execute("SELECT review_note FROM question_reviews WHERE question_id = ?", (session["cards"][0]["items"][0]["question_id"],)).fetchone()
            self.assertEqual(row["review_note"], "画出否定词")
            conn.close()

    def test_ai_analysis_without_key_is_safe(self):
        class DisabledClient:
            enabled = False

        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "section", "question_type": "常识判断", "count": 1})
            result = analyze_session_with_ai(conn, session["session"]["id"], client=DisabledClient())
            self.assertEqual(result["status"], "missing_api_key")
            conn.close()

    def test_recent_favorite_is_not_immediately_repeated_in_normal_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            recent_question_id = "paper-xingce-q001"
            conn.execute(
                """
                INSERT INTO question_reviews (
                    question_id, favorite, last_attempted_at, updated_at
                ) VALUES (?, 1, ?, ?)
                """,
                (
                    recent_question_id,
                    datetime.now().isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()

            normal = create_session(conn, {"mode": "section", "question_type": "常识判断", "count": 1})
            self.assertNotEqual(normal["cards"][0]["items"][0]["question_id"], recent_question_id)

            favorites = create_session(conn, {"mode": "favorites", "count": 1})
            self.assertEqual(favorites["cards"][0]["items"][0]["question_id"], recent_question_id)
            conn.close()

    def test_mistake_mode_uses_latest_wrong_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._setup_paths(tmp)
            conn = db.connect(paths.db)
            session = create_session(conn, {"mode": "section", "question_type": "常识判断", "count": 1})
            item = session["cards"][0]["items"][0]
            submit_answer(conn, session["session"]["id"], item["id"], {"selected_answer": "B", "duration_seconds": 9})

            mistake = create_session(conn, {"mode": "mistakes", "count": 1})
            self.assertEqual(mistake["cards"][0]["items"][0]["question_id"], item["question_id"])

            submit_answer(conn, session["session"]["id"], item["id"], {"selected_answer": "A", "duration_seconds": 8})
            empty = create_session(conn, {"mode": "mistakes", "count": 1})
            self.assertEqual(empty["progress"]["total"], 0)
            conn.close()

    def _setup_paths(self, tmp: str) -> Paths:
        paths = Paths.from_root(tmp)
        paths.ensure()
        conn = db.connect(paths.db)
        db.init_schema(conn)
        paper = ExamPaper(
            id="paper-xingce",
            exam_type="国考",
            region="全国",
            year=2026,
            source_url=None,
            source_file="fixture.json",
            markdown_path="vault/题库/真题套卷/fixture.md",
            question_count=140,
            paper_kind="行测",
            source_name="fixture",
        )
        db.upsert_paper(conn, paper)
        numbers = {
            "常识判断": 35,
            "言语理解": 30,
            "数量关系": 15,
            "判断推理": 35,
        }
        number = 1
        for question_type, count in numbers.items():
            for _ in range(count):
                self._upsert_question(conn, paper.id, number, question_type)
                number += 1
        for group_index in range(1, 6):
            for offset in range(5):
                self._upsert_question(
                    conn,
                    paper.id,
                    115 + (group_index - 1) * 5 + offset + 1,
                    "资料分析",
                    stem=f"【材料】\n\n材料{group_index}\n\n资料题{offset + 1}",
                    source_span=f"fenbi:data;materials:group-{group_index}",
                    knowledge_points=["资料分析", "统计表"],
                )
        conn.close()
        return paths

    def _upsert_question(
        self,
        conn,
        paper_id: str,
        number: int,
        question_type: str,
        stem: str | None = None,
        source_span: str | None = None,
        knowledge_points: list[str] | None = None,
    ) -> None:
        db.upsert_question(
            conn,
            Question(
                id=f"{paper_id}-q{number:03d}",
                paper_id=paper_id,
                number=str(number),
                stem=stem or f"{question_type} 第{number}题",
                options={"A": "正确项", "B": "干扰项", "C": "干扰项", "D": "干扰项"},
                answer="A",
                explanation="解析内容",
                explanation_source="fixture",
                explanation_status="fetched",
                question_type=question_type,
                question_format="单选",
                knowledge_points=knowledge_points or [question_type],
                source_span=source_span,
            ),
        )


if __name__ == "__main__":
    unittest.main()
