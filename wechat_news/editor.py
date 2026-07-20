from __future__ import annotations

import html
import json
import re
from datetime import datetime

from bs4 import BeautifulSoup

from .models import EditedArticle, NewsItem

SYSTEM_PROMPT = """你是一名谨慎、客观的中文新闻编辑。你的任务是把给定的新闻条目编辑为微信公众号每日要闻。

成功标准：
- 只依据输入材料写作，不补充无法从材料确认的事实；信息不足时使用“据相关报道”等审慎表述。
- 区分国内与国际新闻，优先呈现影响范围广、公共价值高的事件。
- 每条新闻用2至4句话说明发生了什么、为什么重要；避免情绪化、夸张和标题党。
- 不大段复制原文；保留每条新闻的媒体名称和原始链接。
- 输出适合微信公众号的简洁HTML片段，不要输出完整html/body标签，不要脚本、外链图片或CSS类。

只输出一个JSON对象，字段必须是：title、digest、content_html、source_notes。不要使用Markdown代码围栏。
"""

ALLOWED_TAGS = {"section", "h1", "h2", "h3", "p", "ul", "ol", "li", "strong", "em", "blockquote", "a", "br", "hr"}


def _clean_json_text(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    start, end = value.find("{"), value.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI 返回内容不是有效 JSON")
    return value[start : end + 1]


def sanitize_wechat_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for node in soup.find_all(["script", "style", "iframe", "object", "embed"]):
        node.decompose()
    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        attrs: dict[str, str] = {}
        if tag.name == "a":
            href = str(tag.get("href", "")).strip()
            if href.startswith(("http://", "https://")):
                attrs["href"] = href
        tag.attrs = attrs
    return str(soup).strip()


def _input_for_model(items: list[NewsItem], run_at: datetime) -> str:
    records = []
    for index, item in enumerate(items, 1):
        records.append(
            {
                "id": index,
                "region": "国内" if item.region == "domestic" else "国际",
                "category": item.category,
                "title": item.title,
                "source": item.source,
                "published_at": item.published_at.isoformat(),
                "url": item.url,
                "excerpt": item.summary,
            }
        )
    return (
        f"编辑日期：{run_at:%Y年%m月%d日}\n"
        "请生成8至12分钟可读完的每日新闻简报。国内和国际分别设置二级标题，"
        "每条新闻标题使用三级标题，文末增加‘信息来源’列表。\n"
        f"新闻材料：\n{json.dumps(records, ensure_ascii=False, indent=2)}"
    )


def _article_from_raw(raw: str, author: str) -> EditedArticle:
    data = json.loads(_clean_json_text(raw))
    title = str(data.get("title", "")).strip()[:64]
    digest = str(data.get("digest", "")).strip()[:120]
    content_html = sanitize_wechat_html(str(data.get("content_html", "")))
    source_notes = [str(item)[:200] for item in data.get("source_notes", [])]
    if not title or not digest or not content_html:
        raise ValueError("AI 返回稿件缺少 title、digest 或 content_html")
    return EditedArticle(title, digest, content_html, author, source_notes)


def _is_responses_compatibility_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()
    if status_code in {404, 405, 501}:
        return True
    return status_code in {400, 422} and any(
        marker in message for marker in ("responses", "unsupported", "not support", "unknown endpoint")
    )


def _responses_raw(client, model: str, prompt: str) -> str:
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        text={
            "verbosity": "medium",
            "format": {
                "type": "json_schema",
                "name": "wechat_daily_news",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "digest": {"type": "string"},
                        "content_html": {"type": "string"},
                        "source_notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "digest", "content_html", "source_notes"],
                    "additionalProperties": False,
                },
            },
        },
    )
    return response.output_text


def _chat_completions_raw(client, model: str, prompt: str) -> str:
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        message = str(exc).lower()
        if getattr(exc, "status_code", None) not in {400, 422} or not any(
            marker in message for marker in ("response_format", "json_object", "json mode")
        ):
            raise
        kwargs.pop("response_format")
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Chat Completions 未返回文本内容")
    return str(content)


def edit_with_openai(
    items: list[NewsItem],
    *,
    api_key: str,
    base_url: str,
    model: str,
    api_mode: str,
    author: str,
    run_at: datetime,
) -> tuple[EditedArticle, str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = _input_for_model(items, run_at)
    if api_mode == "chat_completions":
        return _article_from_raw(_chat_completions_raw(client, model, prompt), author), "chat_completions"
    if api_mode == "responses":
        return _article_from_raw(_responses_raw(client, model, prompt), author), "responses"
    try:
        return _article_from_raw(_responses_raw(client, model, prompt), author), "responses"
    except Exception as exc:
        if not _is_responses_compatibility_error(exc):
            raise
        return _article_from_raw(_chat_completions_raw(client, model, prompt), author), "chat_completions"


def edit_locally(items: list[NewsItem], *, author: str, run_at: datetime) -> EditedArticle:
    sections: list[str] = []
    for region, label in (("domestic", "国内要闻"), ("international", "国际要闻")):
        region_items = [item for item in items if item.region == region]
        if not region_items:
            continue
        sections.append(f"<h2>{label}</h2>")
        for item in region_items:
            summary = item.summary or "订阅源未提供摘要，请点击原文查看详情。"
            sections.append(f"<h3>{html.escape(item.title)}</h3>")
            sections.append(f"<p>{html.escape(summary[:360])}</p>")
            sections.append(
                f'<p><strong>来源：</strong>{html.escape(item.source)}　'
                f'<a href="{html.escape(item.url, quote=True)}">查看原文</a></p>'
            )
    sections.append("<hr><p>本文由程序根据公开新闻订阅源自动汇总，发布前请人工核对重要事实。</p>")
    title = f"{run_at:%m月%d日}每日要闻｜国内与国际重大新闻速览"
    digest = "汇总过去一天值得关注的国内与国际新闻，附原始报道链接。"
    return EditedArticle(title, digest, "\n".join(sections), author, [item.url for item in items])
