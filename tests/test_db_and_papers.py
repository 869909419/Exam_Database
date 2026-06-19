import sqlite3
import tempfile
import unittest
from datetime import date
import json
from pathlib import Path

from examdb import db
from examdb.config import Paths
from examdb.enrichment import enrich_explanations
from examdb.fenbi import import_fenbi_solution, parse_fenbi_solution
from examdb.models import ArticleRecord, PaperCandidate
from examdb.ingest.pipeline import SOURCES, article_discovery_limit, article_image_dir, article_vault_path, ingest_articles
from examdb.ingest.qstheory import QSTheorySource
from examdb.markdown import article_markdown
from examdb.papers import import_paper


class DatabaseAndPaperTests(unittest.TestCase):
    def test_article_upsert_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "examdb.sqlite")
            db.init_schema(conn)
            html = Path("tests/fixtures/qstheory_article.html").read_text(encoding="utf-8")
            article = QSTheorySource().parse_article_html(html, "https://www.qstheory.cn/20260615/test/c.html")
            db.upsert_article(conn, article)
            db.upsert_article(conn, article)
            count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            self.assertEqual(count, 1)
            self.assertIn("tags:", article_markdown(article))
            self.assertIn("images:", article_markdown(article))

    def test_ingest_skips_existing_urls_unless_refreshing(self):
        class FakeSource:
            fetch_count = 0

            def list_article_urls(self, since, limit=None):
                return ["https://example.gov/a"]

            def fetch_article_html(self, url):
                FakeSource.fetch_count += 1
                return "<html><h1>测试文章</h1><p>正文</p></html>"

            def parse_article_html(self, html, url):
                return ArticleRecord(
                    id="fake-article",
                    title="测试文章",
                    source="测试来源",
                    url=url,
                    published_at="2026-06-17",
                    content="正文",
                    content_hash="fake-hash",
                )

        original = SOURCES.get("fake-source")
        SOURCES["fake-source"] = FakeSource
        try:
            with tempfile.TemporaryDirectory() as tmp:
                paths = Paths.from_root(tmp)
                first = ingest_articles("fake-source", since=date(2026, 1, 1), paths=paths)
                second = ingest_articles("fake-source", since=date(2026, 1, 1), paths=paths)
                refreshed = ingest_articles(
                    "fake-source",
                    since=date(2026, 1, 1),
                    paths=paths,
                    refresh=True,
                )
                self.assertEqual(len(first.written), 1)
                self.assertEqual(len(second.written), 0)
                self.assertEqual(second.skipped_existing, 1)
                self.assertEqual(len(refreshed.written), 1)
                self.assertEqual(FakeSource.fetch_count, 2)
        finally:
            if original is None:
                SOURCES.pop("fake-source", None)
            else:
                SOURCES["fake-source"] = original

    def test_article_discovery_limit_overfetches_small_limited_runs(self):
        self.assertEqual(article_discovery_limit(1, refresh=False), 51)
        self.assertEqual(article_discovery_limit(10, refresh=False), 60)
        self.assertIsNone(article_discovery_limit(None, refresh=False))
        self.assertEqual(article_discovery_limit(5, refresh=True), 5)

    def test_qstheory_article_path_groups_by_issue_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = Paths.from_root(tmp)
            html = Path("tests/fixtures/qstheory_article.html").read_text(encoding="utf-8")
            article = QSTheorySource().parse_article_html(html, "https://www.qstheory.cn/20260615/test/c.html")
            article.source = "《求是》2026/12"
            path = article_vault_path(paths, "qstheory", article)
            self.assertEqual(path.name, "以高质量发展推进中国式现代化.md")
            self.assertIn("qstheory/2026/2026年第12期", path.as_posix())
            self.assertNotIn("2026-06-15-以高质量发展", path.name)
            image_dir = article_image_dir(path, article)
            self.assertIn("qstheory/2026/2026年第12期/附件/以高质量发展推进中国式现代化", image_dir.as_posix())

    def test_article_path_falls_back_to_date_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = Paths.from_root(tmp)
            article = ArticleRecord(
                id="article-test",
                title="普通政府文章",
                source="政府网站",
                url="https://example.gov/article",
                published_at="2026-06-15",
            )
            path = article_vault_path(paths, "gov", article)
            self.assertIn("gov/2026/06-15", path.as_posix())

    def test_import_markdown_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "2025四川省考行测.md"
            source.write_text(
                "1. 下列说法正确的是？\nA. 选项一\nB. 选项二\nC. 选项三\nD. 选项四\n\n"
                "2. 根据材料，以下正确的是？\nA. 甲\nB. 乙\n",
                encoding="utf-8",
            )
            paths = Paths.from_root(root)
            paper = import_paper(source, paths)
            self.assertEqual(paper.region, "四川")
            self.assertEqual(paper.exam_type, "省考")
            self.assertEqual(paper.exam_category, "公务员")
            self.assertEqual(paper.paper_kind, "行测")
            self.assertEqual(paper.question_count, 2)
            self.assertTrue((root / paper.markdown_path).exists())
            self.assertTrue((root / "data" / "processed" / "papers" / f"{paper.id}.md").exists())

    def test_paper_candidate_upsert_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "examdb.sqlite")
            conn.row_factory = sqlite3.Row
            db.init_schema(conn)
            candidate = PaperCandidate(
                id="candidate-test",
                source_id="fenbi",
                source_name="粉笔",
                title="2025国考行测真题.pdf",
                url="https://example.com/list",
                download_url="https://example.com/2025.pdf",
                exam_type="国考",
                region="全国",
                year=2025,
                paper_kind="行测",
            )
            db.upsert_paper_candidate(conn, candidate)
            db.upsert_paper_candidate(conn, candidate)
            rows = db.list_paper_candidates(conn, source_id="fenbi")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["download_status"], "pending")

    def test_import_extracts_answers_and_review_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "2025事业单位公基.md"
            source.write_text(
                "1. 下列属于法律常识的是？\nA. 宪法\nB. 诗歌\nC. 物理\nD. 音乐\n\n"
                "答案\n1 A\n\n解析\n1. 宪法属于法律知识。\n",
                encoding="utf-8",
            )
            paths = Paths.from_root(root)
            paper = import_paper(source, paths)
            conn = db.connect(paths.db)
            rows = db.question_rows_for_paper(conn, paper.id)
            self.assertEqual(paper.exam_category, "事业编")
            self.assertEqual(paper.paper_kind, "公基")
            self.assertEqual(rows[0]["answer"], "A")
            self.assertEqual(rows[0]["explanation_status"], "fetched")
            self.assertEqual(rows[0]["explanation_source"], "source_file")
            self.assertEqual(rows[0]["question_type"], "公共基础知识")
            self.assertEqual(rows[0]["question_format"], "单选")
            self.assertEqual(rows[0]["review_status"], "needs_review")

    def test_enrich_explanations_queues_missing_source_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "2025四川省考行测.md"
            source.write_text(
                "1. 下列说法正确的是？\nA. 选项一\nB. 选项二\nC. 选项三\nD. 选项四\n",
                encoding="utf-8",
            )
            paths = Paths.from_root(root)
            paper = import_paper(source, paths)
            result = enrich_explanations(paths, paper.id, source_name="fenbi")
            conn = db.connect(paths.db)
            sources = db.list_question_sources(conn, source_name="fenbi")
            self.assertEqual(result.queued, 1)
            self.assertEqual(sources[0]["status"], "needs_lookup")

    def test_enrich_explanations_applies_high_confidence_external_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "2025四川省考行测.md"
            stem = "下列属于法律常识的是？"
            source.write_text(f"1. {stem}\nA. 宪法\nB. 诗歌\nC. 物理\nD. 音乐\n", encoding="utf-8")
            match_file = root / "fenbi_matches.jsonl"
            match_file.write_text(
                '{"number":"1","stem":"下列属于法律常识的是？","answer":"A","explanation":"宪法属于法律知识。","source_url":"https://fenbi.example/q/1"}\n',
                encoding="utf-8",
            )
            paths = Paths.from_root(root)
            paper = import_paper(source, paths)
            result = enrich_explanations(paths, paper.id, source_name="fenbi", source_file=match_file, apply=True)
            conn = db.connect(paths.db)
            rows = db.question_rows_for_paper(conn, paper.id)
            self.assertEqual(result.matched, 1)
            self.assertEqual(result.applied, 1)
            self.assertEqual(rows[0]["answer"], "A")
            self.assertEqual(rows[0]["explanation"], "宪法属于法律知识。")
            self.assertEqual(rows[0]["explanation_source"], "https://fenbi.example/q/1")
            self.assertEqual(rows[0]["explanation_status"], "fetched")

    def test_parse_fenbi_solution_maps_answers_explanations_and_sections(self):
        payload = _fenbi_solution_fixture()
        questions = parse_fenbi_solution(payload, paper_id="fenbi-test", paper_kind="行测")
        self.assertEqual(len(questions), 3)
        self.assertEqual(questions[0].answer, "D")
        self.assertEqual(questions[0].question_type, "常识判断")
        self.assertEqual(questions[0].question_format, "单选")
        self.assertIn("政治理论", questions[0].knowledge_points)
        self.assertIn("故正确答案为D。", questions[0].explanation)
        self.assertEqual(questions[1].question_type, "资料分析")
        self.assertIn("【材料】", questions[1].stem)
        self.assertIn("materials:4_1_material", questions[1].source_span)
        self.assertEqual(questions[1].answer, "B")

    def test_import_fenbi_solution_writes_sqlite_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            solution_file = root / "solution.json"
            solution_file.write_text(json.dumps(_fenbi_solution_fixture(), ensure_ascii=False), encoding="utf-8")
            paths = Paths.from_root(root)
            paper = import_fenbi_solution(solution_file, paths, source_url="https://spa.fenbi.com/ti/exam/solution/test")
            conn = db.connect(paths.db)
            rows = db.question_rows_for_paper(conn, paper.id)
            self.assertEqual(paper.source_name, "粉笔")
            self.assertEqual(paper.question_count, 3)
            self.assertTrue((root / paper.markdown_path).exists())
            self.assertTrue((root / paper.source_file).exists())
            self.assertEqual(rows[0]["answer"], "D")
            self.assertEqual(rows[0]["explanation_status"], "fetched")
            self.assertEqual(rows[1]["question_type"], "资料分析")
            group_cards = list((root / "vault" / "题库" / "题目卡片" / paper.id).glob("**/*材料题组.md"))
            self.assertEqual(len(group_cards), 1)
            group_text = group_cards[0].read_text(encoding="utf-8")
            self.assertIn("# 第 2-3 题 材料题组", group_text)
            self.assertEqual(group_text.count("2025年A省接待游客100万人次"), 1)
            self.assertIn("## 第 2 题", group_text)
            self.assertIn("## 第 3 题", group_text)
            self.assertFalse((root / "vault" / "题库" / "题目卡片" / f"{paper.id}-2.md").exists())


def _fenbi_solution_fixture():
    return {
        "name": "2026年国家公务员录用考试《行测》题（行政执法卷网友回忆版）",
        "materials": [
            {
                "globalId": "4_1_material",
                "content": "<p>2025年A省接待游客100万人次，同比增长10%。</p>",
            }
        ],
        "solutions": [
            {
                "id": 19526238,
                "globalId": "3_1_q1",
                "content": "<p>关于坚持自信自立，下列表述正确的有几项？</p>",
                "type": 1,
                "accessories": [{"options": ["1项", "2项", "3项", "4项"], "type": 101}],
                "solution": "<p>本题考查理论与政策。</p><p>故正确答案为D。</p>",
                "keypoints": [{"id": 1, "name": "其他建设"}],
                "correctAnswer": {"choice": "3", "type": 201},
            },
            {
                "id": 19526239,
                "globalId": "3_1_q2",
                "content": "<p>A省游客增长量约为：</p>",
                "type": 1,
                "accessories": [{"options": ["8万人", "9万人", "10万人", "11万人"], "type": 101}],
                "solution": "<p>根据增长率计算，约为9万人。</p>",
                "keypoints": [{"id": 2, "name": "增长量"}],
                "correctAnswer": {"choice": "1", "type": 201},
            },
            {
                "id": 19526240,
                "globalId": "3_1_q3",
                "content": "<p>A省游客基期量约为：</p>",
                "type": 1,
                "accessories": [{"options": ["80万人", "90万人", "100万人", "110万人"], "type": 101}],
                "solution": "<p>基期量约为90万人。</p>",
                "keypoints": [{"id": 3, "name": "基期量"}],
                "correctAnswer": {"choice": "1", "type": 201},
            },
        ],
        "card": {
            "nodeType": 0,
            "children": [
                {
                    "name": "政治理论",
                    "nodeType": 1,
                    "children": [{"key": "3_1_q1", "nodeType": 2}],
                },
                {
                    "name": "资料分析",
                    "nodeType": 1,
                    "children": [
                        {"key": "3_1_q2", "nodeType": 2, "materialKeys": ["4_1_material"]},
                        {"key": "3_1_q3", "nodeType": 2, "materialKeys": ["4_1_material"]},
                    ],
                },
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
