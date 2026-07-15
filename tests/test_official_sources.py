import unittest
from datetime import date
from pathlib import Path

from examdb.ingest.official import CcdiGovSource, MohrssGovSource, MostGovSource, NeacGovSource, StatsGovSource


class OfficialSourceTests(unittest.TestCase):
    def test_neac_discovers_recent_articles(self):
        html = Path("tests/fixtures/official_neac_index.html").read_text(encoding="utf-8")
        source = NeacGovSource()
        urls = []
        for url in source._extract_candidate_links_for_test(html, "https://www.neac.gov.cn/seac/xwzx/index.shtml"):
            if source._is_article_url(url):
                url_date = source._date_from_url(url)
                if url_date and date.fromisoformat(url_date) >= date(2025, 6, 17):
                    urls.append(url)
        self.assertEqual(urls, ["https://www.neac.gov.cn/seac/xwzx/202609/abc123.shtml"])

    def test_neac_parses_article_with_body_image(self):
        html = Path("tests/fixtures/official_neac_article.html").read_text(encoding="utf-8")
        article = NeacGovSource().parse_article_html(html, "https://www.neac.gov.cn/seac/xwzx/202609/abc123.shtml")
        self.assertEqual(article.title, "不断推进中华民族共同体建设")
        self.assertEqual(article.published_at, "2026-09-27")
        self.assertEqual(article.source, "国家民委-国家民委网站")
        self.assertIn("中华民族共同体建设", article.content)
        self.assertNotIn("qrcode", article.image_urls)

    def test_most_discovers_and_parses_article(self):
        html = Path("tests/fixtures/official_most_index.html").read_text(encoding="utf-8")
        source = MostGovSource()
        links = source._extract_candidate_links_for_test(html, "https://www.most.gov.cn/kjbgz/")
        self.assertEqual(links, ["https://www.most.gov.cn/kjbgz/202406/t20240624_191111.html"])
        article_html = Path("tests/fixtures/official_most_article.html").read_text(encoding="utf-8")
        article = source.parse_article_html(article_html, links[0])
        self.assertEqual(article.title, "加快实现高水平科技自立自强")
        self.assertEqual(article.published_at, "2026-06-24")
        self.assertIn("科技资源配置", article.content)

    def test_mohrss_parses_article(self):
        html = Path("tests/fixtures/official_mohrss_article.html").read_text(encoding="utf-8")
        article = MohrssGovSource().parse_article_html(
            html,
            "https://www.mohrss.gov.cn/SYrlzyhshbzb/zwgk/zcwj/202410/t20241031_527001.html",
        )
        self.assertEqual(article.title, "促进高质量充分就业")
        self.assertIn("扩大就业容量", article.content)

    def test_ccdi_parses_article(self):
        html = Path("tests/fixtures/official_ccdi_article.html").read_text(encoding="utf-8")
        article = CcdiGovSource().parse_article_html(html, "https://www.ccdi.gov.cn/llxx/202412/t20241216_398181.html")
        self.assertEqual(article.title, "深入推进党的自我革命")
        self.assertIn("党的自我革命", article.content)

    def test_stats_parses_article(self):
        html = Path("tests/fixtures/official_stats_article.html").read_text(encoding="utf-8")
        article = StatsGovSource().parse_article_html(html, "https://www.stats.gov.cn/sj/sjjd/202409/t20240930_1956789.html")
        self.assertEqual(article.title, "区域协调发展迈向高水平")
        self.assertIn("区域发展协调性", article.content)


if __name__ == "__main__":
    unittest.main()
