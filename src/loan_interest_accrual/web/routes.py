from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from loan_interest_accrual.application import (
    calculate_submission,
    export_submission,
)
from loan_interest_accrual.domain import DomainValidationError, NaturalMonth
from loan_interest_accrual.workbook import generate_standard_template

from .desktop_actions import (
    DesktopActionError,
    DesktopActions,
    get_desktop_actions,
)
from .http_models import (
    CalculationHttpResponse,
    HttpError,
    application_error_to_http,
    failure_response,
    http_error,
    success_response,
)


XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
TEMPLATE_FILENAME = "贷款利息计提输入模板.xlsx"
MONTH_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
WEB_ROOT = Path(__file__).resolve().parent
LOCAL_ACTION_TOKEN = "loan-interest-accrual"

router = APIRouter()
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


@router.get("/", response_class=HTMLResponse)
def homepage(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/template")
def download_template() -> Response:
    return Response(
        generate_standard_template(),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": _attachment_disposition(TEMPLATE_FILENAME)
        },
    )


@router.post("/desktop/open-downloads")
def open_downloads(
    actions: Annotated[DesktopActions, Depends(get_desktop_actions)],
    local_action: Annotated[
        str | None,
        Header(alias="X-Local-Tool-Action"),
    ] = None,
) -> JSONResponse:
    forbidden = _local_action_forbidden("open_downloads", local_action)
    if forbidden is not None:
        return forbidden
    try:
        actions.open_downloads()
    except DesktopActionError as error:
        return _desktop_failure("open_downloads", error)
    return JSONResponse(
        {
            "success": True,
            "action": "open_downloads",
            "state": "success",
            "message": "已打开当前用户的下载目录。",
        }
    )


@router.post("/desktop/exit", status_code=202)
def exit_desktop(
    actions: Annotated[DesktopActions, Depends(get_desktop_actions)],
    local_action: Annotated[
        str | None,
        Header(alias="X-Local-Tool-Action"),
    ] = None,
) -> JSONResponse:
    forbidden = _local_action_forbidden("exit", local_action)
    if forbidden is not None:
        return forbidden
    try:
        request_id = actions.exit()
    except DesktopActionError as error:
        return _desktop_failure("exit", error)
    return JSONResponse(
        {
            "success": True,
            "action": "exit",
            "state": "shutdown_requested",
            "request_id": request_id,
            "status_url": f"/desktop/exit-status/{request_id}",
            "message": "退出请求已提交，工具即将关闭。",
        },
        status_code=202,
    )


@router.get("/desktop/exit-status/{request_id}")
def exit_desktop_status(
    request_id: str,
    actions: Annotated[DesktopActions, Depends(get_desktop_actions)],
    local_action: Annotated[
        str | None,
        Header(alias="X-Local-Tool-Action"),
    ] = None,
) -> JSONResponse:
    forbidden = _local_action_forbidden("exit", local_action)
    if forbidden is not None:
        return forbidden
    try:
        status = actions.exit_status(request_id)
    except DesktopActionError as error:
        return _desktop_failure("exit", error)
    return JSONResponse(
        {
            "success": True,
            "action": "exit",
            "state": status.state,
            "message": status.message,
        },
        status_code=202,
    )


@router.post("/calculate")
async def calculate(
    calculation_month: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> Response:
    validated = _validate_request(calculation_month, file)
    if isinstance(validated, CalculationHttpResponse):
        return _json(validated, 422)
    period, upload = validated
    source_bytes = await _read_upload(upload)
    result = calculate_submission(upload.filename or "", source_bytes, period)
    if result.errors or result.calculation is None:
        response = failure_response(
            (application_error_to_http(error) for error in result.errors),
            calculation_month=_month_text(period),
            source_filename=upload.filename,
            source_sha256=result.source_sha256,
        )
        return _json(response, 422)
    return _json(success_response(result.calculation), 200)


@router.post("/export")
async def export(
    calculation_month: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> Response:
    validated = _validate_request(calculation_month, file)
    if isinstance(validated, CalculationHttpResponse):
        return _json(validated, 422)
    period, upload = validated
    source_bytes = await _read_upload(upload)
    result = export_submission(upload.filename or "", source_bytes, period)
    if result.errors or result.output is None:
        response = failure_response(
            (application_error_to_http(error) for error in result.errors),
            calculation_month=_month_text(period),
            source_filename=upload.filename,
            source_sha256=result.source_sha256,
        )
        return _json(response, 422)
    return Response(
        result.output.workbook_bytes,
        media_type=result.output.media_type,
        headers={
            "Content-Disposition": _attachment_disposition(
                result.output.filename
            )
        },
    )


def _validate_request(
    calculation_month: str | None,
    file: UploadFile | None,
) -> tuple[NaturalMonth, UploadFile] | CalculationHttpResponse:
    errors: list[HttpError] = []
    period: NaturalMonth | None = None
    if calculation_month is None or calculation_month == "":
        errors.append(
            http_error(
                error_code="PERIOD_REQUIRED",
                sheet=None,
                row=None,
                column_or_field="calculation_month",
            )
        )
    elif not MONTH_PATTERN.fullmatch(calculation_month):
        errors.append(_invalid_period_error())
    else:
        year, month = calculation_month.split("-", 1)
        try:
            period = NaturalMonth(int(year), int(month))
        except DomainValidationError:
            errors.append(_invalid_period_error())

    if file is None or not file.filename:
        errors.append(
            http_error(
                error_code="FILE_REQUIRED",
                sheet=None,
                row=None,
                column_or_field="file",
            )
        )

    if errors:
        return failure_response(
            errors,
            calculation_month=calculation_month,
            source_filename=file.filename if file is not None else None,
        )
    if period is None or file is None:
        raise RuntimeError("validated request is missing required values")
    return period, file


def _invalid_period_error() -> HttpError:
    return http_error(
        error_code="PERIOD_INVALID",
        sheet=None,
        row=None,
        column_or_field="calculation_month",
    )


async def _read_upload(file: UploadFile) -> bytes:
    try:
        return await file.read()
    finally:
        await file.close()


def _month_text(period: NaturalMonth) -> str:
    return f"{period.year:04d}-{period.month:02d}"


def _attachment_disposition(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename)}"


def _json(payload: CalculationHttpResponse, status_code: int) -> JSONResponse:
    return JSONResponse(
        payload.model_dump(mode="json"),
        status_code=status_code,
    )


def _desktop_failure(
    action: str,
    error: DesktopActionError,
) -> JSONResponse:
    return JSONResponse(
        {
            "success": False,
            "action": action,
            "state": "failure",
            "error_code": error.error_code,
            "message": error.message,
        },
        status_code=503,
    )


def _local_action_forbidden(
    action: str,
    supplied_token: str | None,
) -> JSONResponse | None:
    if supplied_token == LOCAL_ACTION_TOKEN:
        return None
    return JSONResponse(
        {
            "success": False,
            "action": action,
            "state": "failure",
            "error_code": "LOCAL_ACTION_FORBIDDEN",
            "message": "本机辅助操作请求未通过来源校验。",
        },
        status_code=403,
    )
