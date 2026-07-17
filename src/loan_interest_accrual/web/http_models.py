from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from pydantic import BaseModel

from loan_interest_accrual.application import (
    AmortizationCalculationResult,
    ApplicationError,
)


PASS_STATUS = "通过"
FAIL_STATUS = "失败"
ERROR_MESSAGE_BY_CODE: dict[str, str] = {
    "PERIOD_REQUIRED": "请选择计提月份",
    "PERIOD_INVALID": "计提月份必须使用 YYYY-MM 格式",
    "FILE_REQUIRED": "请选择一个 .xlsx 文件",
    "FILE_EXTENSION_INVALID": "文件扩展名必须为 .xlsx",
    "FILE_TOO_LARGE": "上传文件超过允许的大小限制",
    "WORKBOOK_OPEN_FAILED": "无法打开工作簿，请确认文件是有效的 .xlsx 文件",
    "MACRO_NOT_ALLOWED": "工作簿不得包含宏",
    "EXTERNAL_LINK_NOT_ALLOWED": "工作簿不得包含外部链接",
    "EMBEDDED_OBJECT_NOT_ALLOWED": "工作簿不得包含嵌入对象",
    "FORMULA_NOT_ALLOWED": "输入区域不得包含公式，请填写固定值",
    "SHEET_MISSING": "缺少“摊销输入”工作表",
    "SHEET_DUPLICATE": "工作簿中存在重复工作表",
    "COLUMN_MISSING": "缺少必需列",
    "COLUMN_DUPLICATE": "工作表中存在重复列",
    "REQUIRED_VALUE_MISSING": "该必填项不能为空",
    "VALUE_TYPE_INVALID": "字段值类型不正确",
    "DECIMAL_REQUIRED": "该字段必须为有效数值",
    "DATE_INVALID": "日期格式或日期值无效",
    "ORIGINAL_VALUE_INVALID": "原值必须为有效数值；冲销或更正记录可使用负数",
    "RESIDUAL_VALUE_INVALID": "残值必须与原值方向一致且绝对值不得超过原值",
    "AMORTIZATION_TERM_INVALID": "摊销期限/月必须为正整数",
    "START_MONTH_AFTER_CALCULATION": "开始摊销月不得晚于计提月份",
    "ASSET_ROW_LIMIT_EXCEEDED": "摊销输入的数据行数超过允许上限",
    "CALCULABLE_INPUT_MISSING": "工作簿未生成可计算的有效输入",
    "EXPORT_CHECK_FAILED": "导出前校验未通过，未生成结果文件",
}


class HttpError(BaseModel):
    error_code: str
    sheet: str | None
    row: int | None
    column_or_field: str
    message: str


def error_message_for_code(error_code: str) -> str:
    return ERROR_MESSAGE_BY_CODE.get(error_code, "数据校验未通过")


def http_error(
    *,
    error_code: str,
    sheet: str | None,
    row: int | None,
    column_or_field: str,
) -> HttpError:
    return HttpError(
        error_code=error_code,
        sheet=sheet,
        row=row,
        column_or_field=column_or_field,
        message=error_message_for_code(error_code),
    )


class PreviewRow(BaseModel):
    sequence: int
    primary_category: str
    name: str
    expense_category: str
    original_value: str
    residual_value: str
    amortization_start: str
    booking_month: str
    amortization_term_months: int
    monthly_amortization: str
    cumulative_months: int
    cumulative_amortization: str
    current_required_amortization: str | None
    current_actual_amortization: str | None
    difference: str | None
    ending_net_value: str | None
    fully_amortized: bool


class CheckRow(BaseModel):
    name: str
    display_name: str
    status: str
    expected: str
    actual: str


class PreviewSummary(BaseModel):
    asset_count: int
    original_value: str
    monthly_amortization: str
    cumulative_amortization: str
    current_required_amortization: str
    current_actual_amortization: str
    ending_net_value: str


class CalculationHttpResponse(BaseModel):
    success: bool
    calculation_id: str | None
    calculation_number: str | None
    calculation_month: str | None
    validation_status: str
    source_filename: str | None
    source_sha256: str
    errors: list[HttpError]
    preview: list[PreviewRow]
    checks: list[CheckRow]
    summary: PreviewSummary | None


def application_error_to_http(error: ApplicationError) -> HttpError:
    return http_error(
        error_code=error.error_code,
        sheet=error.sheet,
        row=error.row,
        column_or_field=error.column_or_field,
    )


def failure_response(
    errors: Iterable[HttpError],
    *,
    calculation_month: str | None,
    source_filename: str | None,
    source_sha256: str = "",
) -> CalculationHttpResponse:
    return CalculationHttpResponse(
        success=False,
        calculation_id=None,
        calculation_number=None,
        calculation_month=calculation_month,
        validation_status=FAIL_STATUS,
        source_filename=source_filename,
        source_sha256=source_sha256,
        errors=list(errors),
        preview=[],
        checks=[],
        summary=None,
    )


def success_response(
    calculation: AmortizationCalculationResult,
) -> CalculationHttpResponse:
    month = f"{calculation.period.year:04d}-{calculation.period.month:02d}"
    calculation_number = f"AMO-{month}-{calculation.source_sha256[:12].upper()}"
    preview = [
        PreviewRow(
            sequence=row.sequence,
            primary_category=row.primary_category,
            name=row.name,
            expense_category=row.expense_category,
            original_value=_money(row.original_value),
            residual_value=_money(row.residual_value),
            amortization_start=row.amortization_start.isoformat(),
            booking_month=row.booking_month.isoformat(),
            amortization_term_months=row.amortization_term_months,
            monthly_amortization=_money(row.monthly_amortization),
            cumulative_months=row.cumulative_months,
            cumulative_amortization=_money(row.cumulative_amortization),
            current_required_amortization=_optional_money(
                row.current_required_amortization
            ),
            current_actual_amortization=_optional_money(
                row.current_actual_amortization
            ),
            difference=_optional_money(row.difference),
            ending_net_value=_optional_money(row.ending_net_value),
            fully_amortized=row.fully_amortized,
        )
        for row in calculation.rows
    ]
    checks = [
        CheckRow(
            name=check.name,
            display_name=check.display_name,
            status=check.status,
            expected=_scalar(check.expected),
            actual=_scalar(check.actual),
        )
        for check in calculation.checks
    ]
    summary = PreviewSummary(
        asset_count=calculation.summary.asset_count,
        original_value=_money(calculation.summary.original_value),
        monthly_amortization=_money(calculation.summary.monthly_amortization),
        cumulative_amortization=_money(
            calculation.summary.cumulative_amortization
        ),
        current_required_amortization=_money(
            calculation.summary.current_required_amortization
        ),
        current_actual_amortization=_money(
            calculation.summary.current_actual_amortization
        ),
        ending_net_value=_money(calculation.summary.ending_net_value),
    )
    return CalculationHttpResponse(
        success=True,
        calculation_id=calculation_number,
        calculation_number=calculation_number,
        calculation_month=month,
        validation_status=PASS_STATUS,
        source_filename=calculation.source_filename,
        source_sha256=calculation.source_sha256,
        errors=[],
        preview=preview,
        checks=checks,
        summary=summary,
    )


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _optional_money(value: Decimal | None) -> str | None:
    return None if value is None else _money(value)


def _scalar(value: Decimal | str) -> str:
    return format(value, "f") if isinstance(value, Decimal) else value
