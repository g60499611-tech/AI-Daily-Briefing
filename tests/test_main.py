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
    @staticmethod
    def scored_item(title, total=80, credibility=16):
        scores = {
            "impact": min(25, total),
            "novelty": 15,
            "credibility": credibility,
            "relevance": 15,
            "timeliness": 9,
        }
        penalty = max(0, sum(scores.values()) - total)
        return {"title": title, "scores": scores, "penalty": penalty}

    def test_order_and_three_item_limit(self):
        data = {
            "categories": [
                {"name": "模型与算法", "items": [self.scored_item(str(i), 80 - i) for i in range(5)]},
                {"name": "政策与治理", "items": []},
                {"name": "产品与商业", "items": [self.scored_item("A")]},
            ]
        }
        normalized = main._normalize_processed_data(data)
        self.assertEqual(
            [category["name"] for category in normalized["categories"]],
            ["产品与商业", "政策与治理", "模型与算法"],
        )
        self.assertEqual(len(normalized["categories"][2]["items"]), 3)

    def test_total_is_recalculated_and_items_are_sorted(self):
        high = self.scored_item("高分", 80)
        high["total_score"] = 1
        low = self.scored_item("低分", 60)
        data = {"categories": [{"name": "产品与商业", "items": [low, high]}]}
        normalized = main._normalize_processed_data(data)
        items = normalized["categories"][0]["items"]
        self.assertEqual([item["title"] for item in items], ["高分", "低分"])
        self.assertNotEqual(items[0]["total_score"], 1)

    def test_low_score_or_low_credibility_is_rejected(self):
        low_total = self.scored_item("低总分", 40)
        low_credibility = self.scored_item("低可信度", 70, credibility=5)
        data = {"categories": [{"name": "产品与商业", "items": [low_total, low_credibility]}]}
        normalized = main._normalize_processed_data(data)
        self.assertEqual(normalized["categories"][0]["items"], [])

    def test_signal_is_removed_without_qualified_event(self):
        data = {
            "signal": "不应保留",
            "categories": [{"name": "产品与商业", "items": [self.scored_item("普通新闻", 70)]}],
        }
        normalized = main._normalize_processed_data(data)
        self.assertEqual(normalized["signal"], "")


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
                    "scores": {
                        "impact": 25,
                        "novelty": 15,
                        "credibility": 16,
                        "relevance": 15,
                        "timeliness": 9,
                    },
                    "penalty": 0,
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
