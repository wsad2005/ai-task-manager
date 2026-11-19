"""OpenAI 兼容对话客户端（AI 功能专用，与 01/03 项目同一模式）。

所有异常映射为 app.core.errors 中的 AIError 家族；
异常消息不含 API Key；transport 仅供测试注入。
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.errors import AIError, AIQuotaError, AIResponseError, AITimeoutError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AIClient:
    """最小 OpenAI 兼容客户端：只暴露 chat(messages) -> str。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport

    def chat(self, messages: list[dict[str, str]]) -> str:
        """发送对话请求并返回文本回复。"""
        logger.info("AI 请求开始：model=%s timeout=%ss", self._model, self._timeout)
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            try:
                response = client.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": messages,
                        "temperature": 0.3,
                    },
                )
            except httpx.TimeoutException as exc:
                raise AITimeoutError(f"AI 服务响应超时（>{self._timeout:g}s）") from exc
            except httpx.HTTPError as exc:
                raise AIError(f"无法连接 AI 服务：{exc}") from exc

        logger.info("AI 请求结束：HTTP %d", response.status_code)
        if response.status_code == 429:
            raise AIQuotaError("AI 服务额度不足或限流（429），请稍后重试")
        if response.status_code in (401, 403):
            raise AIError("AI 鉴权失败：请检查 AI_API_KEY")
        if response.status_code >= 400:
            raise AIError(f"AI 服务返回 HTTP {response.status_code}")

        try:
            data: dict[str, Any] = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIResponseError("AI 响应缺少内容") from exc
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError("AI 返回了空内容")
        return content
