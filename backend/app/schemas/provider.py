from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

Capability = Literal["vision", "text"]
ProviderType = Literal["openai_compatible", "gemini"]


def normalize_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("该字段不能为空")
    return normalized


def normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL 必须是有效的 HTTP 或 HTTPS 地址")
    if parsed.username or parsed.password:
        raise ValueError("Base URL 不能包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL 不能包含查询参数或锚点")
    return normalized


class ProviderCreate(BaseModel):
    capability: Capability
    provider_type: ProviderType
    display_name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=10_000)
    model_name: str = Field(min_length=1, max_length=200)
    timeout_seconds: int = Field(default=600, ge=5, le=600)
    enabled: bool = True

    _normalize_display_name = field_validator("display_name")(normalize_text)
    _normalize_model_name = field_validator("model_name")(normalize_text)
    _normalize_api_key = field_validator("api_key")(normalize_text)
    _normalize_base_url = field_validator("base_url")(normalize_base_url)


class ProviderUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, min_length=1, max_length=10_000)
    model_name: str = Field(min_length=1, max_length=200)
    timeout_seconds: int = Field(default=600, ge=5, le=600)
    enabled: bool = True

    _normalize_display_name = field_validator("display_name")(normalize_text)
    _normalize_model_name = field_validator("model_name")(normalize_text)
    _normalize_api_key = field_validator("api_key")(normalize_text)
    _normalize_base_url = field_validator("base_url")(normalize_base_url)


class ProviderResponse(BaseModel):
    id: str
    capability: Capability
    provider_type: ProviderType
    display_name: str
    base_url: str
    model_name: str
    timeout_seconds: int
    enabled: bool
    has_api_key: bool
    api_key_masked: str
    last_test_status: str | None
    last_tested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int
