from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import NewsSource


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_openai_base_url(value: str | None) -> str:
    base_url = (value or "https://api.openai.com/v1").strip().rstrip("/")
    if not base_url:
        return "https://api.openai.com/v1"
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    return base_url


@dataclass(slots=True)
class Settings:
    project_dir: Path
    data_dir: Path
    sources_file: Path
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    openai_api_mode: str
    wechat_app_id: str
    wechat_app_secret: str
    wechat_author: str
    wechat_auto_publish: bool
    wechat_cover_path: Path | None
    run_time: str
    timezone: str
    lookback_hours: int
    max_articles: int
    min_domestic: int
    min_international: int

    @property
    def wechat_configured(self) -> bool:
        return bool(self.wechat_app_id and self.wechat_app_secret)


def load_settings(project_dir: Path | None = None) -> Settings:
    project_dir = (project_dir or Path.cwd()).resolve()
    load_dotenv(project_dir / ".env")

    data_dir_value = os.getenv("DATA_DIR", "./data")
    data_dir = Path(data_dir_value)
    if not data_dir.is_absolute():
        data_dir = project_dir / data_dir

    cover_value = os.getenv("WECHAT_COVER_PATH", "").strip()
    cover_path: Path | None = None
    if cover_value:
        cover_path = Path(cover_value)
        if not cover_path.is_absolute():
            cover_path = project_dir / cover_path

    api_mode = os.getenv("OPENAI_API_MODE", "auto").strip().lower()
    if api_mode not in {"auto", "responses", "chat_completions"}:
        raise ValueError("OPENAI_API_MODE 必须是 auto、responses 或 chat_completions")

    return Settings(
        project_dir=project_dir,
        data_dir=data_dir.resolve(),
        sources_file=project_dir / "config" / "sources.yml",
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=normalize_openai_base_url(os.getenv("OPENAI_BASE_URL")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip(),
        openai_api_mode=api_mode,
        wechat_app_id=os.getenv("WECHAT_APP_ID", "").strip(),
        wechat_app_secret=os.getenv("WECHAT_APP_SECRET", "").strip(),
        wechat_author=os.getenv("WECHAT_AUTHOR", "每日要闻编辑部").strip(),
        wechat_auto_publish=_as_bool(os.getenv("WECHAT_AUTO_PUBLISH")),
        wechat_cover_path=cover_path,
        run_time=os.getenv("RUN_TIME", "07:30").strip(),
        timezone=os.getenv("TIMEZONE", "Asia/Shanghai").strip(),
        lookback_hours=max(1, int(os.getenv("LOOKBACK_HOURS", "30"))),
        max_articles=max(2, int(os.getenv("MAX_ARTICLES", "12"))),
        min_domestic=max(0, int(os.getenv("MIN_DOMESTIC", "5"))),
        min_international=max(0, int(os.getenv("MIN_INTERNATIONAL", "5"))),
    )


def load_sources(path: Path) -> tuple[list[NewsSource], list[str]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = [NewsSource(**item) for item in raw.get("sources", [])]
    keywords = [str(value).lower() for value in raw.get("important_keywords", [])]
    if not sources:
        raise ValueError(f"没有配置新闻源：{path}")
    return sources, keywords
