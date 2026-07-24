from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import API_VERSION, APP_NAME, PROJECT_ROOT, AppPaths
from backend.app.db import models as database_models  # noqa: F401
from backend.app.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from backend.app.providers import (
    ProviderConnectionTester,
    TextProviderFactory,
    VariationProviderFactory,
    VisionProviderFactory,
)
from backend.app.security import SecretProtector, SecretStore, default_secret_protector
from backend.app.security.local_access import LocalOriginMiddleware
from backend.app.services.backup import apply_pending_restore


def create_app(
    *,
    data_dir: Path | None = None,
    frontend_dist: Path | None = None,
    secret_protector: SecretProtector | None = None,
    provider_transport: httpx.AsyncBaseTransport | None = None,
    expose_api_docs: bool = True,
) -> FastAPI:
    paths = AppPaths.from_data_dir(data_dir or PROJECT_ROOT / "data")
    web_root = (frontend_dist or PROJECT_ROOT / "frontend" / "dist").resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        paths.initialize()
        apply_pending_restore(paths)
        engine = create_sqlite_engine(paths.database)
        initialize_database(engine)
        app.state.paths = paths
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.secret_store = SecretStore(
            paths.secrets, secret_protector or default_secret_protector()
        )
        app.state.provider_connection_tester = ProviderConnectionTester(provider_transport)
        app.state.vision_provider_factory = VisionProviderFactory(provider_transport)
        app.state.text_provider_factory = TextProviderFactory(provider_transport)
        app.state.variation_provider_factory = VariationProviderFactory(provider_transport)
        app.state.active_model_operations: set[tuple[str, str]] = set()
        yield
        engine.dispose()

    app = FastAPI(
        title=APP_NAME,
        version="0.1.1",
        docs_url="/api/docs" if expose_api_docs else None,
        openapi_url="/api/openapi.json" if expose_api_docs else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.add_middleware(LocalOriginMiddleware)
    app.include_router(api_router, prefix=f"/api/{API_VERSION}")

    assets = web_root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.get("/", include_in_schema=False, response_model=None)
    def frontend_index() -> Response:
        index = web_root / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {
                "message": "前端尚未构建，请在开发模式下启动 Vite。",
                "api_docs": "/api/docs",
            }
        )

    @app.get("/{route:path}", include_in_schema=False, response_model=None)
    def frontend_fallback(route: str) -> Response:
        index = web_root / "index.html"
        if not route.startswith("api/") and index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "页面不存在"}, status_code=404)

    return app


app = create_app()
