from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings, load_sources
from .cover import create_daily_cover
from .editor import edit_locally, edit_with_openai
from .fetcher import fetch_all
from .models import EditedArticle
from .ranking import deduplicate, rank_items, select_balanced
from .wechat import WeChatOfficialAccount

LOGGER = logging.getLogger(__name__)


def _save_results(
    settings: Settings, run_at: datetime, article: EditedArticle, selected_items: list, meta: dict
) -> Path:
    day_dir = settings.data_dir / "runs" / run_at.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "article.html").write_text(article.content_html, encoding="utf-8")
    markdown = f"# {article.title}\n\n{article.digest}\n\nHTML 正文见 article.html。\n"
    (day_dir / "article.md").write_text(markdown, encoding="utf-8")
    (day_dir / "news.json").write_text(
        json.dumps([item.to_dict() for item in selected_items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (day_dir / "result.json").write_text(
        json.dumps({"article": asdict(article), **meta}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return day_dir


def run_pipeline(
    settings: Settings,
    *,
    dry_run: bool = False,
    no_ai: bool = False,
    force_publish: bool = False,
) -> dict:
    run_at = datetime.now(ZoneInfo(settings.timezone))
    sources, keywords = load_sources(settings.sources_file)
    fetched = fetch_all(sources, lookback_hours=settings.lookback_hours, now=run_at)
    if not fetched:
        raise RuntimeError("所有新闻源均未返回最近时段的新闻，已停止生成，避免发布空文章。")

    ranked = rank_items(fetched, keywords, now=run_at)
    unique = deduplicate(ranked)
    selected = select_balanced(
        unique,
        maximum=settings.max_articles,
        min_domestic=settings.min_domestic,
        min_international=settings.min_international,
    )
    if len(selected) < 2:
        raise RuntimeError("有效新闻不足 2 条，已停止生成。")

    editor_mode = "local"
    if settings.openai_api_key and not no_ai:
        try:
            article, used_api_mode = edit_with_openai(
                selected,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                api_mode=settings.openai_api_mode,
                author=settings.wechat_author,
                run_at=run_at,
            )
            editor_mode = f"openai:{settings.openai_model}:{used_api_mode}"
        except Exception as exc:
            LOGGER.exception("AI 编辑失败，改用本地稿件：%s", exc)
            article = edit_locally(selected, author=settings.wechat_author, run_at=run_at)
    else:
        article = edit_locally(selected, author=settings.wechat_author, run_at=run_at)

    meta: dict = {
        "run_at": run_at.isoformat(),
        "fetched_count": len(fetched),
        "selected_count": len(selected),
        "editor_mode": editor_mode,
        "draft_media_id": None,
        "publish_id": None,
        "auto_publish_blocked_reasons": [],
    }
    day_dir = _save_results(settings, run_at, article, selected, meta)

    if dry_run or not settings.wechat_configured:
        LOGGER.info("仅生成本地稿件：%s", day_dir)
        meta["output_dir"] = str(day_dir)
        return meta

    cover_path = settings.wechat_cover_path
    if cover_path is None:
        cover_path = create_daily_cover(day_dir / "cover.jpg", run_at)
    if not cover_path.exists():
        raise FileNotFoundError(f"封面图不存在：{cover_path}")

    wechat = WeChatOfficialAccount(settings.wechat_app_id, settings.wechat_app_secret)
    thumb_media_id = wechat.upload_thumb(cover_path)
    draft_media_id = wechat.add_draft(article, thumb_media_id)
    meta["draft_media_id"] = draft_media_id
    LOGGER.info("已上传微信公众号草稿：%s", draft_media_id)

    domestic_count = len([item for item in selected if item.region == "domestic"])
    international_count = len([item for item in selected if item.region == "international"])
    blocked_reasons: list[str] = []
    if not editor_mode.startswith("openai:"):
        blocked_reasons.append("AI 编辑未成功，当前为本地简版稿件")
    if domestic_count < settings.min_domestic:
        blocked_reasons.append(f"国内新闻仅 {domestic_count} 条，少于要求的 {settings.min_domestic} 条")
    if international_count < settings.min_international:
        blocked_reasons.append(
            f"国际新闻仅 {international_count} 条，少于要求的 {settings.min_international} 条"
        )
    meta["auto_publish_blocked_reasons"] = blocked_reasons

    should_publish = force_publish or (settings.wechat_auto_publish and not blocked_reasons)
    if should_publish:
        publish_id = wechat.publish(draft_media_id)
        meta["publish_id"] = publish_id
        LOGGER.warning("已提交自动发布：%s", publish_id)
    elif settings.wechat_auto_publish and blocked_reasons:
        LOGGER.warning("自动发布已被质量门槛阻止：%s", "；".join(blocked_reasons))

    meta["output_dir"] = str(day_dir)
    _save_results(settings, run_at, article, selected, meta)
    return meta
