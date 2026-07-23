from dataclasses import dataclass
from time import perf_counter
from urllib.parse import quote

import httpx

from backend.app.db.models.provider import ProviderConfig


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    success: bool
    message: str
    latency_ms: int


class ProviderConnectionTester:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def test(self, config: ProviderConfig, api_key: str) -> ConnectionResult:
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=config.timeout_seconds,
                follow_redirects=False,
            ) as client:
                if config.provider_type == "gemini":
                    response = await self._test_gemini(client, config, api_key)
                else:
                    response = await self._test_openai_compatible(client, config, api_key)
        except httpx.TimeoutException:
            return self._result(False, "连接超时，请检查服务地址和超时时间。", started)
        except httpx.RequestError:
            return self._result(False, "无法连接模型服务，请检查 Base URL 和网络。", started)

        if response.status_code in {401, 403}:
            return self._result(False, "认证失败，请检查 API Key。", started)
        if response.status_code == 404:
            return self._result(False, "接口或模型不存在，请检查 Base URL 和模型名称。", started)
        if response.status_code == 429:
            return self._result(False, "模型服务拒绝请求，可能是额度不足或请求过于频繁。", started)
        if response.is_redirect:
            return self._result(False, "模型服务返回了重定向，请填写最终 Base URL。", started)
        if response.status_code >= 500:
            return self._result(False, "模型服务暂时不可用，请稍后重试。", started)
        if response.status_code >= 400:
            return self._result(False, f"模型服务返回错误状态 {response.status_code}。", started)

        if config.provider_type == "gemini":
            return self._result(True, "连接成功，已找到配置的模型。", started)

        try:
            payload = response.json()
            model_ids = {
                item.get("id") for item in payload.get("data", []) if isinstance(item, dict)
            }
        except (ValueError, AttributeError):
            model_ids = set()
        if model_ids and config.model_name not in model_ids:
            return self._result(False, "服务连接成功，但模型列表中未找到配置的模型。", started)
        message = (
            "连接成功，已找到配置的模型。"
            if config.model_name in model_ids
            else "服务连接成功；该兼容接口未返回可核对的模型列表。"
        )
        return self._result(True, message, started)

    @staticmethod
    async def _test_openai_compatible(
        client: httpx.AsyncClient, config: ProviderConfig, api_key: str
    ) -> httpx.Response:
        return await client.get(
            f"{config.base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )

    @staticmethod
    async def _test_gemini(
        client: httpx.AsyncClient, config: ProviderConfig, api_key: str
    ) -> httpx.Response:
        model_name = quote(config.model_name.removeprefix("models/"), safe="")
        return await client.get(
            f"{config.base_url.rstrip('/')}/models/{model_name}",
            headers={"x-goog-api-key": api_key, "Accept": "application/json"},
        )

    @staticmethod
    def _result(success: bool, message: str, started: float) -> ConnectionResult:
        return ConnectionResult(
            success=success,
            message=message,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )
