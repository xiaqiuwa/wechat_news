from __future__ import annotations

from typing import Any

import requests

from .config import Settings


def check_openai_connection(settings: Settings, *, show_models: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "base_url": settings.openai_base_url,
        "api_mode": settings.openai_api_mode,
        "model": settings.openai_model,
        "api_key_configured": bool(settings.openai_api_key),
        "endpoint_reachable": False,
        "authenticated": False,
        "model_available": None,
    }

    if not settings.openai_api_key:
        response = requests.get(f"{settings.openai_base_url}/models", timeout=15)
        result["http_status"] = response.status_code
        result["endpoint_reachable"] = response.status_code in {200, 401, 403}
        result["message"] = "接口路径可访问；填写 OPENAI_API_KEY 后可继续验证鉴权和模型。"
        return result

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    models = client.models.list()
    model_ids = sorted({str(model.id) for model in models.data})
    result["endpoint_reachable"] = True
    result["authenticated"] = True
    result["model_available"] = settings.openai_model in model_ids
    result["model_count"] = len(model_ids)
    if show_models:
        result["models"] = model_ids
    if result["model_available"]:
        result["message"] = "中转站鉴权成功，配置的模型存在。"
    else:
        result["message"] = "鉴权成功，但模型列表中没有当前模型；请从 models 字段选择可用模型。"
        if not show_models:
            result["available_model_examples"] = model_ids[:20]
    return result

