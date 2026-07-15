import sqlite3
import unittest

from examdb.source_analysis import analyze_politics_sources, apply_politics_sources, infer_politics_source


class PoliticsSourceInferenceTests(unittest.TestCase):
    def test_infers_central_document(self):
        result = infer_politics_source(
            "党的二十届三中全会提出，健全因地制宜发展新质生产力体制机制。",
            "《中共中央关于进一步全面深化改革 推进中国式现代化的决定》指出，加强新领域新赛道制度供给。",
        )
        self.assertEqual(result[0], "central_document")
        self.assertIn("进一步全面深化改革", result[1])
        self.assertEqual(result[4], "high")

    def test_infers_fifteen_five_suggestion(self):
        result = infer_politics_source(
            "《中共中央关于制定国民经济和社会发展第十五个五年规划的建议》提出。",
            "2025年10月23日，中国共产党第二十届中央委员会第四次全体会议通过《中共中央关于制定国民经济和社会发展第十五个五年规划的建议》。",
        )
        self.assertEqual(result[0], "central_document")
        self.assertEqual(result[2], "2025-10-23")

    def test_infers_qstheory_article(self):
        result = infer_politics_source(
            "建设教育强国是一项复杂的系统工程。",
            "2025年6月1日，《求是》杂志发表习近平总书记的重要文章《加快建设教育强国》。",
        )
        self.assertEqual(result[0], "qstheory_article")
        self.assertEqual(result[1], "《加快建设教育强国》")

    def test_infers_speech_or_meeting(self):
        result = infer_politics_source(
            "关于建成科技强国的举措。",
            "2024年6月24日，习近平总书记在全国科技大会、国家科学技术奖励大会、两院院士大会上发表重要讲话。",
        )
        self.assertEqual(result[0], "leader_speech_or_meeting")
        self.assertEqual(result[2], "2024-06-24")

    def test_infers_local_policy(self):
        result = infer_politics_source(
            "全力打造锦绣天府安逸四川文旅品牌。",
            "《中共四川省委关于推进文化和旅游深度融合发展 做大做强文化旅游业的决定》指出，深化成都、自贡国家文化出口基地建设。",
        )
        self.assertEqual(result[0], "local_policy")

    def test_infers_textbook_marxism(self):
        result = infer_politics_source(
            "关于马克思主义政治经济学，下列说法正确的是。",
            "商品的价值量由生产商品的社会必要劳动时间决定。",
        )
        self.assertEqual(result[0], "textbook_marxism")


class PoliticsSourceApplyTests(unittest.TestCase):
    def test_applies_to_duplicate_stems(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        from examdb import db

        db.init_schema(conn)
        conn.execute(
            "INSERT INTO exam_papers (id, exam_type, region, year, paper_kind, source_file, markdown_path, question_count, import_status) VALUES "
            "('p1','国考','全国',2026,'行测','raw','md',1,'imported'),"
            "('p2','国考','全国',2026,'行测','raw','md',1,'imported')"
        )
        for qid, pid in [("q1", "p1"), ("q2", "p2")]:
            conn.execute(
                """
                INSERT INTO questions (
                    id, paper_id, number, stem, options_json, answer, explanation,
                    question_type, knowledge_points_json, difficulty
                ) VALUES (?, ?, '1', '同一道政治理论题', '{}', 'A',
                    '《中共中央关于制定国民经济和社会发展第十五个五年规划的建议》提出相关要求。',
                    '常识判断', '["政治理论"]', 'medium')
                """,
                (qid, pid),
            )
        conn.commit()

        evidences = analyze_politics_sources(
            conn,
            years=[2026],
            paper_kind="行测",
            knowledge_point="政治理论",
            dedupe="stem",
        )
        self.assertEqual(len(evidences), 1)
        written = apply_politics_sources(
            conn,
            evidences,
            years=[2026],
            paper_kind="行测",
            knowledge_point="政治理论",
            dedupe="stem",
        )
        self.assertEqual(written, 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM question_sources").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
