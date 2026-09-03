import datetime
import json
import unittest

import main


class ReportContextTests(unittest.TestCase):
    def test_wednesday_window_starts_on_monday(self):
        now = datetime.datetime(2026, 9, 2, 20, 0, tzinfo=main.BEIJING_TZ)
        context = main.get_report_context("auto", now)
        self.assertEqual(context["type"], "midweek")
        self.assertEqual(context["start_date"], "2026-08-31")
        self.assertEqual(context["end_date"], "2026-09-03")

    def test_sunday_window_covers_the_week(self):
        now = datetime.datetime(2026, 9, 6, 20, 0, tzinfo=main.BEIJING_TZ)
        context = main.get_report_context("auto", now)
        self.assertEqual(context["type"], "weekly")
        self.assertEqual(context["start_date"], "2026-08-31")
        self.assertEqual(context["end_date"], "2026-09-07")


class NewsNormalizationTests(unittest.TestCase):
    def test_order_and_three_item_limit(self):
        data = {
            "categories": [
                {"name": "模型与算法", "items": [{"title": str(i)} for i in range(5)]},
                {"name": "政策与治理", "items": []},
                {"name": "产品与商业", "items": [{"title": "A"}]},
            ]
        }
        normalized = main._normalize_processed_data(data)
        self.assertEqual(
            [category["name"] for category in normalized["categories"]],
            ["产品与商业", "政策与治理", "模型与算法"],
        )
        self.assertEqual(len(normalized["categories"][2]["items"]), 3)


class HtmlSafetyTests(unittest.TestCase):
    def test_external_text_is_escaped(self):
        context = main.get_report_context(
            "midweek",
            datetime.datetime(2026, 9, 2, 20, 0, tzinfo=main.BEIJING_TZ),
        )
        data = {
            "categories": [{
                "name": "产品与商业",
                "trend": "趋势 <script>alert(1)</script>",
                "items": [{
                    "title": "A < B",
                    "source": "媒体 & 来源",
                    "summary": "<img src=x onerror=alert(1)>",
                    "link": "javascript:alert(1)",
                }],
            }],
            "overview": "总览 <b>不可执行</b>",
        }
        rendered = main.generate_html(json.dumps(data), context)
        self.assertIn("A &lt; B", rendered)
        self.assertIn("媒体 &amp; 来源", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img src=x", rendered)
        self.assertIn('href="#"', rendered)

    def test_https_link_is_retained_and_quotes_are_escaped(self):
        safe = main._safe_url('https://example.com/news?q="ai"&lang=zh')
        self.assertEqual(safe, "https://example.com/news?q=&quot;ai&quot;&amp;lang=zh")


if __name__ == "__main__":
    unittest.main()
