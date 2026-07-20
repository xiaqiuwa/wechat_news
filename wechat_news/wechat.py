from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path
from typing import Any

import requests

from .models import EditedArticle


class WeChatAPIError(RuntimeError):
    pass


class WeChatOfficialAccount:
    base_url = "https://api.weixin.qq.com"

    def __init__(self, app_id: str, app_secret: str, timeout: int = 30) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout = timeout
        self._access_token = ""
        self._token_expires_at = 0.0

    @staticmethod
    def _validate(data: dict[str, Any]) -> dict[str, Any]:
        error_code = int(data.get("errcode", 0) or 0)
        if error_code:
            raise WeChatAPIError(f"微信接口错误 {error_code}: {data.get('errmsg', 'unknown error')}")
        return data

    def access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 120:
            return self._access_token
        response = requests.get(
            f"{self.base_url}/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": self.app_id, "secret": self.app_secret},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = self._validate(response.json())
        self._access_token = str(data["access_token"])
        self._token_expires_at = time.time() + int(data.get("expires_in", 7200))
        return self._access_token

    def upload_thumb(self, image_path: Path) -> str:
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        with image_path.open("rb") as file_obj:
            response = requests.post(
                f"{self.base_url}/cgi-bin/material/add_material",
                params={"access_token": self.access_token(), "type": "thumb"},
                files={"media": (image_path.name, file_obj, mime_type)},
                timeout=self.timeout,
            )
        response.raise_for_status()
        data = self._validate(response.json())
        media_id = str(data.get("media_id", ""))
        if not media_id:
            raise WeChatAPIError(f"上传封面成功但未返回 media_id：{data}")
        return media_id

    def add_draft(self, article: EditedArticle, thumb_media_id: str) -> str:
        payload = {
            "articles": [
                {
                    "title": article.title,
                    "author": article.author,
                    "digest": article.digest,
                    "content": article.content_html,
                    "content_source_url": "",
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        }
        response = requests.post(
            f"{self.base_url}/cgi-bin/draft/add",
            params={"access_token": self.access_token()},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = self._validate(response.json())
        media_id = str(data.get("media_id", ""))
        if not media_id:
            raise WeChatAPIError(f"新增草稿成功但未返回 media_id：{json.dumps(data, ensure_ascii=False)}")
        return media_id

    def publish(self, draft_media_id: str) -> str:
        response = requests.post(
            f"{self.base_url}/cgi-bin/freepublish/submit",
            params={"access_token": self.access_token()},
            json={"media_id": draft_media_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = self._validate(response.json())
        publish_id = str(data.get("publish_id", ""))
        if not publish_id:
            raise WeChatAPIError(f"发布请求未返回 publish_id：{json.dumps(data, ensure_ascii=False)}")
        return publish_id

    def publish_status(self, publish_id: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/cgi-bin/freepublish/get",
            params={"access_token": self.access_token()},
            json={"publish_id": publish_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self._validate(response.json())

