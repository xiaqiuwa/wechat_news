from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class NewsSource:
    name: str
    url: str
    region: str
    category: str = "综合"
    weight: float = 1.0


@dataclass(slots=True)
class NewsItem:
    title: str
    url: str
    source: str
    region: str
    category: str
    published_at: datetime
    summary: str = ""
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["published_at"] = self.published_at.isoformat()
        return result


@dataclass(slots=True)
class EditedArticle:
    title: str
    digest: str
    content_html: str
    author: str
    source_notes: list[str] = field(default_factory=list)

