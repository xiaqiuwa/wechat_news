from datetime import datetime, timezone
import unittest

from wechat_news.fetcher import _date_from_url, _entry_datetime


class FetcherDateTests(unittest.TestCase):
    def test_extracts_common_news_url_dates(self) -> None:
        values = [
            "https://example.com/gn/2026/07-20/123.shtml",
            "https://example.com/n1/2026/0720/c1.html",
            "https://example.com/2026-07/20/story.html",
        ]
        for value in values:
            with self.subTest(value=value):
                parsed = _date_from_url(value)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.astimezone(timezone.utc).date(), datetime(2026, 7, 20).date())

    def test_missing_date_is_not_treated_as_current(self) -> None:
        self.assertIsNone(_entry_datetime({"link": "https://example.com/story"}))


if __name__ == "__main__":
    unittest.main()

