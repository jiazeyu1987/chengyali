from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router


WEB_ROOT = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    application = FastAPI(
        title="贷款利息自动计提",
        docs_url=None,
        redoc_url=None,
    )
    application.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )
    application.include_router(router)
    return application


app = create_app()
