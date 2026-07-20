from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

from .models import NewsItem, NewsSource

LOGGER = logging.getLogger(__name__)
USER_AGENT = "DailyNewsPublisher/1.0 (+RSS aggregation; contact: account owner)"


def _plain_text(value: str, limit: int = 700) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _date_from_url(url: str) -> datetime | None:
    patterns = (
        r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)",
        r"(?<!\d)(20\d{2})/(\d{2})(\d{2})(?!\d)",
        r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)",
    )
    for pattern in patterns:
        match = re.search(pattern, url)
        if not match:
            continue
        try:
            local_date = datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                12,
                tzinfo=ZoneInfo("Asia/Shanghai"),
            )
            return local_date.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _entry_datetime(entry: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(field)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    for field in ("published", "updated", "created"):
        value = entry.get(field)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
    # 没有发布时间时，只接受能从链接中明确识别出的日期；绝不把旧条目当成“今天”。
    return _date_from_url(str(entry.get("link", "")))


def fetch_source(
    source: NewsSource,
    *,
    now: datetime | None = None,
    lookback_hours: int = 30,
    timeout: int = 20,
) -> list[NewsItem]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    response = requests.get(
        source.url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"},
    )
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"无法解析订阅源：{feed.bozo_exception}")

    results: list[NewsItem] = []
    for entry in feed.entries:
        title = _plain_text(entry.get("title", ""), limit=180)
        url = str(entry.get("link", "")).strip()
        if not title or not url:
            continue
        published_at = _entry_datetime(entry)
        if published_at is None or published_at < cutoff or published_at > now + timedelta(hours=2):
            continue
        results.append(
            NewsItem(
                title=title,
                url=url,
                source=source.name,
                region=source.region,
                category=source.category,
                published_at=published_at,
                summary=_plain_text(entry.get("summary", entry.get("description", ""))),
                score=source.weight,
            )
        )
    return results


def fetch_all(
    sources: list[NewsSource], *, lookback_hours: int, now: datetime | None = None
) -> list[NewsItem]:
    results: list[NewsItem] = []
    for source in sources:
        try:
            items = fetch_source(source, now=now, lookback_hours=lookback_hours)
            LOGGER.info("新闻源 %-20s 获取 %d 条", source.name, len(items))
            results.extend(items)
        except (requests.RequestException, ValueError, OSError) as exc:
            LOGGER.warning("跳过新闻源 %s：%s", source.name, exc)
    return results
