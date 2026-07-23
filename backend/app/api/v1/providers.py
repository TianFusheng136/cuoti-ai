from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from backend.app.db.dependencies import DatabaseSession
from backend.app.db.models import ProviderConfig
from backend.app.schemas.provider import (
    ConnectionTestResponse,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
)
from backend.app.security.secrets import SecretProtectionError

router = APIRouter(prefix="/providers", tags=["模型服务"])


def get_provider(session: DatabaseSession, provider_id: str) -> ProviderConfig:
    provider = session.get(ProviderConfig, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="没有找到该模型配置。")
    return provider


def provider_response(provider: ProviderConfig) -> ProviderResponse:
    has_api_key = bool(provider.secret_ref) and not provider.secret_ref.startswith(
        "restore-missing-"
    )
    return ProviderResponse(
        id=provider.id,
        capability=provider.capability,  # type: ignore[arg-type]
        provider_type=provider.provider_type,  # type: ignore[arg-type]
        display_name=provider.display_name,
        base_url=provider.base_url,
        model_name=provider.model_name,
        timeout_seconds=provider.timeout_seconds,
        enabled=provider.enabled,
        has_api_key=has_api_key,
        api_key_masked="••••••••" if has_api_key else "",
        last_test_status=provider.last_test_status,
        last_tested_at=provider.last_tested_at,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreate, request: Request, session: DatabaseSession
) -> ProviderResponse:
    secret_ref = request.app.state.secret_store.save(payload.api_key)
    provider = ProviderConfig(
        capability=payload.capability,
        provider_type=payload.provider_type,
        display_name=payload.display_name,
        base_url=payload.base_url,
        model_name=payload.model_name,
        timeout_seconds=payload.timeout_seconds,
        secret_ref=secret_ref,
        enabled=payload.enabled,
    )
    session.add(provider)
    try:
        session.commit()
    except Exception:
        session.rollback()
        request.app.state.secret_store.delete(secret_ref)
        raise
    session.refresh(provider)
    return provider_response(provider)


@router.get("", response_model=list[ProviderResponse])
def list_providers(session: DatabaseSession) -> list[ProviderResponse]:
    providers = session.scalars(
        select(ProviderConfig).order_by(ProviderConfig.capability, ProviderConfig.created_at)
    ).all()
    return [provider_response(item) for item in providers]


@router.get("/{provider_id}", response_model=ProviderResponse)
def read_provider(provider_id: str, session: DatabaseSession) -> ProviderResponse:
    return provider_response(get_provider(session, provider_id))


@router.put("/{provider_id}", response_model=ProviderResponse)
def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    request: Request,
    session: DatabaseSession,
) -> ProviderResponse:
    provider = get_provider(session, provider_id)
    provider.display_name = payload.display_name
    provider.base_url = payload.base_url
    provider.model_name = payload.model_name
    provider.timeout_seconds = payload.timeout_seconds
    provider.enabled = payload.enabled
    if payload.api_key is not None:
        if provider.secret_ref.startswith("restore-missing-"):
            provider.secret_ref = request.app.state.secret_store.save(payload.api_key)
        else:
            request.app.state.secret_store.save(payload.api_key, provider.secret_ref)
    session.commit()
    session.refresh(provider)
    return provider_response(provider)


@router.post("/{provider_id}/test", response_model=ConnectionTestResponse)
async def test_provider(
    provider_id: str, request: Request, session: DatabaseSession
) -> ConnectionTestResponse:
    provider = get_provider(session, provider_id)
    try:
        api_key = request.app.state.secret_store.read(provider.secret_ref)
    except (OSError, UnicodeError, SecretProtectionError) as exc:
        raise HTTPException(
            status_code=500, detail="无法读取本地 API Key，请重新保存配置。"
        ) from exc

    result = await request.app.state.provider_connection_tester.test(provider, api_key)
    provider.last_test_status = "success" if result.success else "failed"
    provider.last_tested_at = datetime.now(UTC)
    session.commit()
    return ConnectionTestResponse(
        success=result.success,
        message=result.message,
        latency_ms=result.latency_ms,
    )


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id: str, request: Request, session: DatabaseSession) -> Response:
    provider = get_provider(session, provider_id)
    secret_ref = provider.secret_ref
    session.delete(provider)
    session.commit()
    request.app.state.secret_store.delete(secret_ref)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
