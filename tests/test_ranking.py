from datetime import datetime, timedelta, timezone
import unittest

from wechat_news.models import NewsItem
from wechat_news.ranking import canonical_url, deduplicate, rank_items, select_balanced


def item(title: str, region: str, score: float = 1.0) -> NewsItem:
    return NewsItem(
        title=title,
        url=f"https://example.com/{title}?utm_source=test",
        source="测试源",
        region=region,
        category="综合",
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        summary="重大经济政策发布",
        score=score,
    )


class RankingTests(unittest.TestCase):
    def test_canonical_url_removes_tracking(self) -> None:
        self.assertEqual(canonical_url("HTTPS://EXAMPLE.COM/a/?utm_source=x&k=1#x"), "https://example.com/a?k=1")

    def test_deduplicates_similar_titles(self) -> None:
        first = item("央行发布新的金融政策", "domestic")
        second = item("央行发布新的金融政策，市场关注", "domestic")
        self.assertEqual(len(deduplicate([first, second])), 1)

    def test_balanced_selection(self) -> None:
        values = [item(f"国内新闻{i}", "domestic", 10 - i) for i in range(5)]
        values += [item(f"国际新闻{i}", "international", 5 - i) for i in range(5)]
        ranked = rank_items(values, ["重大", "政策"])
        selected = select_balanced(ranked, maximum=6, min_domestic=3, min_international=3)
        self.assertEqual(len([x for x in selected if x.region == "domestic"]), 3)
        self.assertEqual(len([x for x in selected if x.region == "international"]), 3)


if __name__ == "__main__":
    unittest.main()

