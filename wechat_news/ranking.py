from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import NewsItem


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ocid", "cmpid"}
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def normalized_title(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", title.lower())


def is_duplicate(left: NewsItem, right: NewsItem, threshold: float = 0.82) -> bool:
    if canonical_url(left.url) == canonical_url(right.url):
        return True
    a, b = normalized_title(left.title), normalized_title(right.title)
    if not a or not b:
        return False
    if a in b or b in a:
        # 中文标题通常比英文短，8 个有效字符已经足以识别“原标题 + 补充说明”。
        return min(len(a), len(b)) >= 8
    return SequenceMatcher(None, a, b).ratio() >= threshold


def rank_items(
    items: list[NewsItem], keywords: list[str], now: datetime | None = None
) -> list[NewsItem]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for item in items:
        age_hours = max(0.0, (now - item.published_at.astimezone(timezone.utc)).total_seconds() / 3600)
        freshness = max(0.0, 2.2 - age_hours / 18)
        haystack = f"{item.title} {item.summary}".lower()
        keyword_score = min(3.0, sum(0.45 for keyword in keywords if keyword and keyword in haystack))
        title_bonus = min(0.8, len(item.title) / 120)
        item.score = round(item.score + freshness + keyword_score + title_bonus, 4)
    return sorted(items, key=lambda item: (item.score, item.published_at), reverse=True)


def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    unique: list[NewsItem] = []
    for item in items:
        if any(is_duplicate(item, existing) for existing in unique):
            continue
        unique.append(item)
    return unique


def select_balanced(
    items: list[NewsItem], *, maximum: int, min_domestic: int, min_international: int
) -> list[NewsItem]:
    selected: list[NewsItem] = []
    selected_urls: set[str] = set()

    def take(region: str, limit: int) -> None:
        for item in items:
            if len([x for x in selected if x.region == region]) >= limit:
                break
            key = canonical_url(item.url)
            if item.region == region and key not in selected_urls:
                selected.append(item)
                selected_urls.add(key)

    take("domestic", min(min_domestic, maximum))
    take("international", min(min_international, maximum - len(selected)))
    for item in items:
        if len(selected) >= maximum:
            break
        key = canonical_url(item.url)
        if key not in selected_urls:
            selected.append(item)
            selected_urls.add(key)
    return sorted(selected, key=lambda item: (item.region != "domestic", -item.score))
