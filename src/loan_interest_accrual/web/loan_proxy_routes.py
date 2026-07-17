from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from .routes import WEB_ROOT


REMOTE_BASE_URL = "http://172.30.30.58:18082"
REMOTE_TIMEOUT = httpx.Timeout(120.0, connect=10.0)

router = APIRouter(prefix="/loan-interest")
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def homepage(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="loan_interest.html",
    )


@router.get("/health")
async def remote_health() -> Response:
    return await _proxy_get("/health")


@router.get("/template")
async def download_template() -> Response:
    return await _proxy_get("/template")


@router.post("/calculate")
async def calculate(
    calculation_start_date: Annotated[str | None, Form()] = None,
    calculation_end_date: Annotated[str | None, Form()] = None,
    calculation_start_month: Annotated[str | None, Form()] = None,
    calculation_end_month: Annotated[str | None, Form()] = None,
    calculation_month: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> Response:
    return await _proxy_submission(
        "/calculate",
        calculation_start_date=calculation_start_date,
        calculation_end_date=calculation_end_date,
        calculation_start_month=calculation_start_month,
        calculation_end_month=calculation_end_month,
        calculation_month=calculation_month,
        file=file,
    )


@router.post("/export")
async def export(
    calculation_start_date: Annotated[str | None, Form()] = None,
    calculation_end_date: Annotated[str | None, Form()] = None,
    calculation_start_month: Annotated[str | None, Form()] = None,
    calculation_end_month: Annotated[str | None, Form()] = None,
    calculation_month: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> Response:
    return await _proxy_submission(
        "/export",
        calculation_start_date=calculation_start_date,
        calculation_end_date=calculation_end_date,
        calculation_start_month=calculation_start_month,
        calculation_end_month=calculation_end_month,
        calculation_month=calculation_month,
        file=file,
    )


async def _proxy_get(path: str) -> Response:
    try:
        async with httpx.AsyncClient(timeout=REMOTE_TIMEOUT) as client:
            remote = await client.get(f"{REMOTE_BASE_URL}{path}")
    except httpx.HTTPError:
        return _unavailable_response()
    return _remote_response(remote)


async def _proxy_submission(
    path: str,
    *,
    calculation_start_date: str | None,
    calculation_end_date: str | None,
    calculation_start_month: str | None,
    calculation_end_month: str | None,
    calculation_month: str | None,
    file: UploadFile | None,
) -> Response:
    data = {
        key: value
        for key, value in {
            "calculation_start_date": calculation_start_date,
            "calculation_end_date": calculation_end_date,
            "calculation_start_month": calculation_start_month,
            "calculation_end_month": calculation_end_month,
            "calculation_month": calculation_month,
        }.items()
        if value is not None
    }
    files = None
    if file is not None:
        try:
            contents = await file.read()
        finally:
            await file.close()
        files = {
            "file": (
                file.filename or "upload.xlsx",
                contents,
                file.content_type or "application/octet-stream",
            )
        }

    try:
        async with httpx.AsyncClient(timeout=REMOTE_TIMEOUT) as client:
            remote = await client.post(
                f"{REMOTE_BASE_URL}{path}",
                data=data,
                files=files,
            )
    except httpx.HTTPError:
        return _unavailable_response()
    return _remote_response(remote)


def _remote_response(remote: httpx.Response) -> Response:
    headers = {
        name: value
        for name in ("content-type", "content-disposition")
        if (value := remote.headers.get(name)) is not None
    }
    return Response(
        content=remote.content,
        status_code=remote.status_code,
        headers=headers,
    )


def _unavailable_response() -> JSONResponse:
    return JSONResponse(
        {
            "success": False,
            "errors": [
                {
                    "error_code": "REMOTE_SERVICE_UNAVAILABLE",
                    "sheet": None,
                    "row": None,
                    "column_or_field": "remote_service",
                    "message": "无法连接贷款利息最终版服务 172.30.30.58:18082。",
                }
            ],
        },
        status_code=502,
    )
