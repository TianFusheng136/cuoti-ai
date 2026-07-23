from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import API_VERSION, APP_NAME

router = APIRouter(tags=["系统"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    api_version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app_name=APP_NAME, api_version=API_VERSION)
