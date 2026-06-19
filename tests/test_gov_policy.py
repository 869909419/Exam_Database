import json
import unittest
from datetime import date
from pathlib import Path

from examdb.ingest.gov_policy import GovPolicySource


class GovPolicyTests(unittest.TestCase):
    def test_records_filter_recent_article_urls(self):
        records = json.loads(Path("tests/fixtures/gov_policy_records.json").read_text(encoding="utf-8"))
        urls = GovPolicySource()._records_to_urls(records, since=date(2025, 6, 17))
        self.assertIn("https://www.gov.cn/zhengce/content/202606/content_7072481.htm", urls)
        self.assertIn("https://www.gov.cn/zhengce/202606/content_7072156.htm", urls)
        self.assertNotIn("https://www.gov.cn/zhengce/content/202401/content_7000000.htm", urls)
        self.assertNotIn("https://www.gov.cn/zhengce/jiedu/tzxfzxxd/index.htm", urls)

    def test_parses_policy_document(self):
        html = Path("tests/fixtures/gov_policy_document.html").read_text(encoding="utf-8")
        url = "https://www.gov.cn/zhengce/content/202606/content_7072481.htm"
        article = GovPolicySource().parse_article_html(html, url)
        self.assertEqual(article.title, "国务院关于印发《实施就业优先战略“十五五”规划》的通知")
        self.assertEqual(article.published_at, "2026-06-17")
        self.assertEqual(article.source, "中国政府网-国务院")
        self.assertEqual(article.authors, ["李自可"])
        self.assertNotIn("待复核", article.tags)
        self.assertIn("现将《实施就业优先战略“十五五”规划》印发给你们", article.content)
        self.assertNotIn("责任编辑", article.content)

    def test_parses_interpretation_with_body_image(self):
        html = Path("tests/fixtures/gov_policy_interpretation.html").read_text(encoding="utf-8")
        url = "https://www.gov.cn/zhengce/202606/content_7072197.htm"
        article = GovPolicySource().parse_article_html(html, url)
        self.assertEqual(article.title, "数万亿元将投向这里！国家重要部署")
        self.assertEqual(article.published_at, "2026-06-15")
        self.assertEqual(article.source, "中国政府网")
        self.assertEqual(article.image_urls, ["https://www.gov.cn/zhengce/202606/W020260615785703777990_ORIGIN.png"])
        self.assertIn("![六张网图解](https://www.gov.cn/zhengce/202606/W020260615785703777990_ORIGIN.png)", article.content)
        self.assertNotIn("/images/150.jpg", article.content)


if __name__ == "__main__":
    unittest.main()
