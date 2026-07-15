import unittest

from examdb.collection_profiles import article_matches_keywords, keywords_for_profile, parse_keywords


class CollectionProfileTests(unittest.TestCase):
    def test_politics_theory_profile_matches_similar_material(self):
        keywords = keywords_for_profile("politics-theory")
        self.assertTrue(article_matches_keywords("加快建设教育强国", "正确处理支撑国家战略和满足民生需求的关系。", keywords))
        self.assertTrue(article_matches_keywords("全国民族团结进步表彰大会举行", "铸牢中华民族共同体意识。", keywords))
        self.assertFalse(article_matches_keywords("铁路调图公告", "旅客列车运行图调整。", keywords))

    def test_parse_custom_keywords(self):
        self.assertEqual(parse_keywords("数字政府,质量强国\n绿色低碳"), ["数字政府", "质量强国", "绿色低碳"])


if __name__ == "__main__":
    unittest.main()
