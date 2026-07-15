from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from pydantic import BaseModel

from loan_interest_accrual.application import ApplicationError, CalculationResult
from loan_interest_accrual.domain.decimal_math import exact_sum, quantize_money


PASS_STATUS = "通过"
FAIL_STATUS = "失败"
ERROR_MESSAGE_BY_CODE: dict[str, str] = {
    "PERIOD_REQUIRED": "请选择开始日期和结束日期",
    "PERIOD_INVALID": "日期区间必须使用有效的 YYYY-MM-DD 格式，且结束日期不得早于开始日期",
    "FILE_REQUIRED": "请选择一个 .xlsx 文件",
    "FILE_EXTENSION_INVALID": "文件扩展名必须为 .xlsx",
    "FILE_TOO_LARGE": "上传文件超过允许的大小限制",
    "WORKBOOK_OPEN_FAILED": "无法打开工作簿，请确认文件是有效的 .xlsx 文件",
    "MACRO_NOT_ALLOWED": "工作簿不得包含宏",
    "EXTERNAL_LINK_NOT_ALLOWED": "工作簿不得包含外部链接",
    "EMBEDDED_OBJECT_NOT_ALLOWED": "工作簿不得包含嵌入对象",
    "FORMULA_NOT_ALLOWED": "输入区域不得包含公式，请填写固定值",
    "SHEET_MISSING": "缺少必需工作表",
    "SHEET_DUPLICATE": "工作簿中存在重复的工作表",
    "COLUMN_MISSING": "缺少必需列",
    "COLUMN_DUPLICATE": "工作表中存在重复列",
    "LOAN_ID_REQUIRED": "贷款ID为必填项",
    "LOAN_ID_DUPLICATE": "贷款ID必须唯一，不能重复",
    "REQUIRED_VALUE_MISSING": "该必填项不能为空",
    "VALUE_TYPE_INVALID": "字段值类型不正确",
    "DECIMAL_REQUIRED": "该字段必须为有效数值",
    "INTEREST_RATE_INVALID": "年利率必须大于0且小于100%",
    "DAY_COUNT_BASIS_INVALID": "计息基准必须为360或365",
    "DATE_INVALID": "日期格式或日期值无效",
    "DATE_RANGE_INVALID": "备注中的还本日期不得早于借款时间",
    "LOAN_PERIOD_OUTSIDE_MONTH": "贷款计息期间必须与所选月份有交集",
    "HISTORICAL_PERIOD_NOT_FOUND": "历史工作簿中未找到所选月份的可计算数据",
    "CAPITALIZATION_FLAG_INVALID": "是否资本化必须填写“是”或“否”",
    "MOVEMENT_LOAN_ID_REQUIRED": "资金变动的贷款ID为必填项",
    "MOVEMENT_LOAN_ID_NOT_FOUND": "资金变动引用的贷款ID不存在",
    "MOVEMENT_LOAN_ID_AMBIGUOUS": "资金变动引用的贷款ID对应多条贷款记录",
    "MOVEMENT_LOAN_MISMATCH": "资金变动的贷款ID与当前贷款不一致",
    "MOVEMENT_TYPE_INVALID": "变动类型必须为“放款”或“还本”",
    "MOVEMENT_AMOUNT_INVALID": "变动金额必须为大于0的人民币数值",
    "MOVEMENT_DATE_OUTSIDE_MONTH": "变动日期必须位于所选月份内",
    "NEGATIVE_PRINCIPAL": "本金不得为负数，且还本后本金不能小于0",
    "RECONCILIATION_FAILED": "计算结果勾稽校验未通过",
    "LOAN_ROW_LIMIT_EXCEEDED": "贷款主表的数据行数超过允许上限",
    "MOVEMENT_ROW_LIMIT_EXCEEDED": "资金变动表的数据行数超过允许上限",
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
    try:
        return ERROR_MESSAGE_BY_CODE[error_code]
    except KeyError as caught:
        raise ValueError(
            f"Unsupported HTTP error code: {error_code}"
        ) from caught


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
    company_name: str
    bank_name: str
    opening_principal: str
    annual_rate: str
    borrowing_time: str
    accrued_interest: str
    interest_days: int


class CheckRow(BaseModel):
    name: str
    display_name: str
    status: str
    expected: str
    actual: str


class PreviewSummary(BaseModel):
    loan_count: int
    opening_principal: str
    total_drawdowns: str
    total_repayments: str
    ending_principal: str
    accrued_interest: str
    capitalized_interest: str
    expensed_interest: str


class CompanyPreviewSummary(BaseModel):
    company_name: str
    opening_principal: str
    accrued_interest: str


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
    company_summaries: list[CompanyPreviewSummary]
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
        company_summaries=[],
        checks=[],
        summary=None,
    )


def success_response(calculation: CalculationResult) -> CalculationHttpResponse:
    if calculation.period.is_exact_date_range:
        month = (
            f"{calculation.period.start_date.isoformat()}至"
            f"{calculation.period.end_date.isoformat()}"
        )
    else:
        start = f"{calculation.period.year:04d}-{calculation.period.month:02d}"
        end_date = calculation.period.end_date
        end = f"{end_date.year:04d}-{end_date.month:02d}"
        month = start if start == end else f"{start}至{end}"
    calculation_number = (
        f"LIA-{month}-{calculation.source_sha256[:12].upper()}"
    )
    preview: list[PreviewRow] = []
    for result in calculation.portfolio_result.loan_results:
        if len(result.segments) <= 1:
            display_rows = (
                (
                    result.loan.opening_principal,
                    result.interest_days,
                    result.accrued_interest,
                ),
            )
        else:
            rounded_interest = [
                quantize_money(segment.unrounded_interest)
                for segment in result.segments
            ]
            rounded_interest[-1] += result.accrued_interest - exact_sum(
                rounded_interest
            )
            display_rows = tuple(
                (segment.principal, segment.days, interest)
                for segment, interest in zip(
                    result.segments, rounded_interest, strict=True
                )
            )
        for principal, days, interest in display_rows:
            preview.append(
                PreviewRow(
                    sequence=len(preview) + 1,
                    company_name=result.loan.company_name,
                    bank_name=result.loan.bank_name,
                    opening_principal=_money(principal),
                    annual_rate=_rate(result.loan.annual_rate),
                    borrowing_time=result.loan.accrual_start.isoformat(),
                    accrued_interest=_money(interest),
                    interest_days=days,
                )
            )
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
    summary_by_company = {
        row.company_name: row for row in calculation.company_summary_rows
    }
    company_summaries = [
        CompanyPreviewSummary(
            company_name=company_name,
            opening_principal=_money(
                summary_by_company[company_name].opening_principal
            ),
            accrued_interest=_money(
                summary_by_company[company_name].accrued_interest
            ),
        )
        for company_name in dict.fromkeys(
            row.company_name for row in calculation.loan_rows
        )
    ]
    summary = PreviewSummary(
        loan_count=len(calculation.loan_rows),
        opening_principal=_money(
            exact_sum(row.opening_principal for row in calculation.loan_rows)
        ),
        total_drawdowns=_money(
            exact_sum(row.total_drawdowns for row in calculation.loan_rows)
        ),
        total_repayments=_money(
            exact_sum(row.total_repayments for row in calculation.loan_rows)
        ),
        ending_principal=_money(
            exact_sum(row.ending_principal for row in calculation.loan_rows)
        ),
        accrued_interest=_money(
            exact_sum(row.accrued_interest for row in calculation.loan_rows)
        ),
        capitalized_interest=_money(
            exact_sum(row.capitalized_interest for row in calculation.loan_rows)
        ),
        expensed_interest=_money(
            exact_sum(row.expensed_interest for row in calculation.loan_rows)
        ),
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
        company_summaries=company_summaries,
        checks=checks,
        summary=summary,
    )


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _rate(value: Decimal) -> str:
    return f"{value * Decimal('100'):.4f}%"


def _scalar(value: Decimal | str) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value
