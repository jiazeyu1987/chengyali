from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .loan_proxy_routes import create_loan_proxy_client
from .loan_proxy_routes import router as loan_proxy_router
from .routes import router


WEB_ROOT = Path(__file__).resolve().parent


def create_app(*, loan_proxy_client: httpx.AsyncClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        client = loan_proxy_client
        owns_client = client is None
        if client is None:
            client = create_loan_proxy_client()
        application.state.loan_proxy_client = client
        try:
            yield
        finally:
            if owns_client:
                await client.aclose()

    application = FastAPI(
        title="无形资产及长摊自动计提",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )
    application.include_router(router)
    application.include_router(loan_proxy_router)
    return application


app = create_app()
