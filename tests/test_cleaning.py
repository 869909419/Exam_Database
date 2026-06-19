import unittest
from datetime import date
from pathlib import Path

from examdb.cleaning import clean_article_text, html_to_text
from examdb.ingest.qstheory import QSTheorySource
from examdb.taxonomy import suggest_policy_metadata


class CleaningTests(unittest.TestCase):
    def test_clean_article_text_removes_noise(self):
        text = "正文第一段\n责任编辑：某某\n推荐阅读\n正文第二段\n正文第二段"
        self.assertEqual(clean_article_text(text), "正文第一段\n\n正文第二段")

    def test_qstheory_parse_fixture(self):
        html = Path("tests/fixtures/qstheory_article.html").read_text(encoding="utf-8")
        article = QSTheorySource().parse_article_html(html, "https://www.qstheory.cn/20260615/test/c.html")
        self.assertEqual(article.title, "以高质量发展推进中国式现代化")
        self.assertEqual(article.source, "求是网")
        self.assertEqual(article.published_at, "2026-06-15")
        self.assertIn("经济", article.tags)
        self.assertEqual(article.image_urls, ["https://www.qstheory.cn/20260615/test/example-image.jpg"])
        self.assertIn("![示例图.jpg](https://www.qstheory.cn/20260615/test/example-image.jpg)", article.content)
        self.assertNotIn("责任编辑", article.content)
        self.assertNotIn("推荐阅读", article.content)

    def test_html_to_text_keeps_body_text(self):
        html = "<html><script>bad()</script><body><h1>标题</h1><p>正文</p></body></html>"
        self.assertNotIn("bad", html_to_text(html))
        self.assertIn("标题", html_to_text(html))

    def test_policy_tags_are_selective(self):
        suggestion = suggest_policy_metadata(
            "本期导读",
            (
                "教育、科技、人才是全面建设社会主义现代化国家的基础性、战略性支撑。"
                "习近平党建思想具有里程碑意义。"
                "文章探讨如何破解生活性服务业的卡点堵点。"
            ),
        )
        self.assertLessEqual(len(suggestion.tags), 3)
        self.assertIn("科技教育人才", suggestion.tags)
        self.assertNotIn("申论素材", suggestion.tags)
        self.assertNotIn("规范表述", suggestion.tags)

    def test_listing_page_before_since_still_expands_recent_children(self):
        class FakeQSTheorySource(QSTheorySource):
            def __init__(self):
                super().__init__("https://www.qstheory.cn/qs/mulu.htm")
                self.pages = {
                    "https://www.qstheory.cn/qs/mulu.htm": (
                        '<a href="https://www.qstheory.cn/20250101/year/c.html">2025年</a>'
                    ),
                    "https://www.qstheory.cn/20250101/year/c.html": (
                        "<h1>《求是》2025年</h1>"
                        "<p>2025-01-01</p>"
                        '<a href="https://www.qstheory.cn/20250701/issue/c.html">第13期目录</a>'
                    ),
                    "https://www.qstheory.cn/20250701/issue/c.html": (
                        "<h1>2025年第13期《求是》目录</h1>"
                        "<p>2025-07-01</p>"
                        '<a href="https://www.qstheory.cn/20250701/article/c.html">正文</a>'
                    ),
                }

            def fetch_article_html(self, url: str) -> str:
                return self.pages[url]

        urls = FakeQSTheorySource().list_article_urls(date(2025, 6, 17))
        self.assertEqual(urls, ["https://www.qstheory.cn/20250701/article/c.html"])

if __name__ == "__main__":
    unittest.main()
