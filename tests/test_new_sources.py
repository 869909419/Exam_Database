import unittest
from datetime import date
from pathlib import Path

from examdb.ingest.local_gov import ChongqingGovSource, SichuanGovSource
from examdb.ingest.xinhua_politics import XinhuaPoliticsSource


class XinhuaPoliticsTests(unittest.TestCase):
    def test_discovers_recent_politics_articles(self):
        html = Path("tests/fixtures/xinhua_politics_index.html").read_text(encoding="utf-8")
        source = XinhuaPoliticsSource()
        urls = []
        for url in source._extract_links(html, "https://www.news.cn/politics/"):
            if source._is_article_url(url):
                url_date = source._date_from_url(url)
                if url_date and date.fromisoformat(url_date) >= date(2025, 6, 17):
                    urls.append(url)
        self.assertEqual(urls, ["https://www.news.cn/politics/20260617/3cfa4154be374d9581b6815a24278e31/c.html"])

    def test_parses_xinhua_article_with_body_image(self):
        html = Path("tests/fixtures/xinhua_politics_article.html").read_text(encoding="utf-8")
        url = "https://www.news.cn/politics/20260617/3cfa4154be374d9581b6815a24278e31/c.html"
        article = XinhuaPoliticsSource().parse_article_html(html, url)
        self.assertEqual(article.title, "全国铁路7月1日起实行新的列车运行图")
        self.assertEqual(article.published_at, "2026-06-17")
        self.assertEqual(article.source, "中国铁路微信公众号")
        self.assertEqual(article.image_urls, ["https://www.news.cn/politics/20260617/3cfa4154be374d9581b6815a24278e31/train.jpeg"])
        self.assertIn("全国铁路将实行新的列车运行图", article.content)
        self.assertNotIn("责任编辑", article.content)
        self.assertNotIn("zxcode", article.content)


class LocalGovTests(unittest.TestCase):
    def test_parses_sichuan_policy_article(self):
        html = Path("tests/fixtures/sichuan_gov_article.html").read_text(encoding="utf-8")
        url = "https://www.sc.gov.cn/10462/zfwjts/2026/6/17/446ac7824cdd41c7a9e0490a93d7ae13.shtml"
        article = SichuanGovSource().parse_article_html(html, url)
        self.assertEqual(article.title, "四川省人民政府关于任免李文双等职务的通知")
        self.assertEqual(article.published_at, "2026-06-17")
        self.assertEqual(article.source, "四川省政府-四川省人民政府")
        self.assertIn("四川省人民政府决定", article.content)

    def test_parses_sichuan_report_from_cms_article_content(self):
        html = Path("tests/fixtures/sichuan_gov_report.html").read_text(encoding="utf-8")
        url = "https://www.sc.gov.cn/10462/c105962s/2026/2/10/c3064029fbc341e99c8ce71ce3aec20c.shtml"
        article = SichuanGovSource().parse_article_html(html, url)
        self.assertEqual(article.title, "2026年四川省人民政府工作报告")
        self.assertIn("一、2025年工作回顾和“十四五”发展主要成绩", article.content)
        self.assertIn("二、“十五五”发展的主要考虑", article.content)
        self.assertIn("成渝地区双城经济圈建设", article.content)
        self.assertNotIn("责任编辑", article.content)

    def test_parses_chongqing_policy_article(self):
        html = Path("tests/fixtures/chongqing_gov_article.html").read_text(encoding="utf-8")
        url = "https://www.cq.gov.cn/zwgk/zfxxgkml/szfwj/xzgfxwj/szfbgt/202606/t20260616_15758457.html"
        self.assertTrue(ChongqingGovSource()._is_article_url(url))
        article = ChongqingGovSource().parse_article_html(html, url)
        self.assertEqual(article.title, "重庆市人民政府办公厅关于印发《重庆市建设新型能源算力枢纽实施方案》的通知")
        self.assertEqual(article.published_at, "2026-06-16")
        self.assertEqual(article.source, "重庆市政府-市政府办公厅")
        self.assertEqual(article.authors, ["市政府办公厅"])
        self.assertIn("新型能源算力枢纽实施方案", article.content)
        self.assertEqual(article.image_urls, [])


if __name__ == "__main__":
    unittest.main()
