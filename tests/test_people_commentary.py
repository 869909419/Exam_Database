import unittest
from datetime import date
from pathlib import Path

from examdb.ingest.people_commentary import PeopleCommentarySource


class PeopleCommentaryTests(unittest.TestCase):
    def test_discovers_recent_same_domain_articles(self):
        html = Path("tests/fixtures/people_commentary_index.html").read_text(encoding="utf-8")
        source = PeopleCommentarySource()
        urls = source._extract_links(html, "http://opinion.people.com.cn/", since=date(2025, 6, 17))
        self.assertIn("http://opinion.people.com.cn/n1/2026/0617/c1003-12345678.html", urls)
        self.assertNotIn("http://opinion.people.com.cn/n1/2024/0101/c1003-11111111.html", urls)
        self.assertNotIn("http://politics.people.com.cn/n1/2026/0617/c1001-22222222.html", urls)
        self.assertNotIn("http://opinion.people.com.cn/static/logo.png", urls)

    def test_parses_article_with_body_image(self):
        html = Path("tests/fixtures/people_commentary_article.html").read_text(encoding="utf-8")
        url = "http://opinion.people.com.cn/n1/2026/0617/c1003-12345678.html"
        article = PeopleCommentarySource().parse_article_html(html, url)
        self.assertEqual(article.title, "人民网评：以实干绘就民生新图景")
        self.assertEqual(article.published_at, "2026-06-17")
        self.assertEqual(article.source, "人民网-观点频道")
        self.assertIn("李明", article.authors)
        self.assertIn("基层治理", article.tags)
        self.assertEqual(article.image_urls, ["http://opinion.people.com.cn/NMediaFile/2026/0617/MAIN123456789.jpg"])
        self.assertIn("![基层治理现场](http://opinion.people.com.cn/NMediaFile/2026/0617/MAIN123456789.jpg)", article.content)
        self.assertNotIn("责任编辑", article.content)
        self.assertNotIn("推荐阅读", article.content)
        self.assertNotIn("观点首页", article.content)


if __name__ == "__main__":
    unittest.main()
