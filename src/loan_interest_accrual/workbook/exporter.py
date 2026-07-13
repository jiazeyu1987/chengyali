from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell

from loan_interest_accrual.application.results import CalculationResult
from loan_interest_accrual.domain.decimal_math import exact_sum
from loan_interest_accrual.version import __version__

from .export_schema import (
    CAPITALIZATION_SUMMARY_HEADERS,
    CAPITALIZATION_SUMMARY_SHEET,
    CHECK_HEADERS,
    CHECK_SHEET,
    COMPANY_SUMMARY_HEADERS,
    COMPANY_SUMMARY_SHEET,
    EXPORT_SHEET_NAMES,
    PARAMETER_HEADERS,
    PARAMETER_SHEET,
    RESULT_HEADERS,
    RESULT_SHEET,
    SEGMENT_HEADERS,
    SEGMENT_SHEET,
)


class ExportInvariantError(ValueError):
    pass


def _set_cell(cell: Cell, value: object) -> None:
    cell.value = value
    if type(value) is str:
        cell.data_type = "s"


def _append_row(sheet, values: tuple[object, ...] | list[object]) -> None:
    row_number = sheet.max_row + 1
    for column, value in enumerate(values, start=1):
        _set_cell(sheet.cell(row_number, column), value)


def _write_sheet(sheet, headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    for column, header in enumerate(headers, start=1):
        _set_cell(sheet.cell(1, column), header)
    for row in rows:
        _append_row(sheet, row)
    _format_sheet(sheet, headers)


def _format_sheet(sheet, headers: tuple[str, ...]) -> None:
    for index, header in enumerate(headers, start=1):
        column_letter = sheet.cell(1, index).column_letter
        if "日期" in header:
            number_format = "yyyy-mm-dd"
        elif header == "年利率":
            number_format = "0.000000%"
        elif header == "未舍入分段利息（元）":
            number_format = "0.000000000000"
        elif "（元）" in header:
            number_format = '#,##0.00'
        else:
            number_format = None
        if number_format is not None:
            for cell in sheet[column_letter][1:]:
                cell.number_format = number_format
        sheet.column_dimensions[column_letter].width = max(12, min(len(header) + 4, 32))


def _result_rows(calculation: CalculationResult) -> list[tuple[object, ...]]:
    return [
        (
            row.calculation_month,
            row.loan_id,
            row.company_name,
            row.contract_number,
            row.bank_name,
            "是" if row.capitalize_interest else "否",
            row.opening_principal,
            row.total_drawdowns,
            row.total_repayments,
            row.ending_principal,
            row.interest_days,
            row.accrued_interest,
            row.capitalized_interest,
            row.expensed_interest,
        )
        for row in calculation.loan_rows
    ]


def _segment_rows(calculation: CalculationResult) -> list[tuple[object, ...]]:
    return [
        (
            row.calculation_month,
            row.loan_id,
            row.sequence,
            row.start_date,
            row.end_date,
            row.days,
            row.principal,
            row.annual_rate,
            row.day_count_basis,
            row.unrounded_interest,
            row.ending_principal,
            row.trigger_note,
        )
        for row in calculation.segment_rows
    ]


def _company_rows(calculation: CalculationResult) -> list[tuple[object, ...]]:
    return [
        (
            row.company_name,
            row.loan_count,
            row.opening_principal,
            row.total_drawdowns,
            row.total_repayments,
            row.ending_principal,
            row.accrued_interest,
            row.capitalized_interest,
            row.expensed_interest,
        )
        for row in calculation.company_summary_rows
    ]


def _capitalization_rows(calculation: CalculationResult) -> list[tuple[object, ...]]:
    rows = [
        (
            row.company_name,
            row.capitalized_loan_count,
            row.ending_principal,
            row.capitalized_interest,
        )
        for row in calculation.capitalization_summary_rows
    ]
    rows.append(
        (
            "合计",
            sum(row.capitalized_loan_count for row in calculation.capitalization_summary_rows),
            exact_sum(row.ending_principal for row in calculation.capitalization_summary_rows),
            calculation.portfolio_result.total_capitalized_interest,
        )
    )
    return rows


def _check_rows(calculation: CalculationResult) -> list[tuple[object, ...]]:
    return [
        (
            check.display_name,
            check.status,
            check.expected,
            check.actual,
        )
        for check in calculation.checks
    ]


def _parameter_rows(
    calculation: CalculationResult,
    generated_at: datetime,
) -> list[tuple[object, ...]]:
    period = calculation.period
    return [
        ("计算月份", f"{period.year:04d}-{period.month:02d}"),
        ("期间开始日期", period.start_date.isoformat()),
        ("期间结束日期", period.end_date.isoformat()),
        ("金额单位", "人民币元"),
        ("利率输入格式", "Excel 百分比"),
        ("放款生效规则", "次日起息"),
        ("还本生效规则", "计息至还本当日"),
        ("贷款日期规则", "开始日和结束日均计息"),
        ("舍入规则", "逐笔最终 ROUND_HALF_UP 到 0.01"),
        ("应用版本", __version__),
        ("生成时间", generated_at.isoformat()),
    ]


def _assert_checks_pass(calculation: CalculationResult) -> None:
    failed = tuple(check.display_name for check in calculation.checks if not check.passed)
    if failed:
        raise ExportInvariantError(
            "export requires all checks to pass: " + ", ".join(failed)
        )


def inspect_export_package(workbook_bytes: bytes) -> tuple[str, ...]:
    problems: list[str] = []
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False, keep_links=False)
    try:
        if tuple(workbook.sheetnames) != EXPORT_SHEET_NAMES:
            problems.append("worksheet names do not match export schema")
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        problems.append(
                            f"formula cell is present: {sheet.title}!{cell.coordinate}"
                        )
    finally:
        workbook.close()

    with ZipFile(BytesIO(workbook_bytes)) as package:
        for name in package.namelist():
            lowered = name.lower()
            if "vbaproject" in lowered:
                problems.append(f"VBA part is present: {name}")
            if "externallinks" in lowered:
                problems.append(f"external link part is present: {name}")
            if "connections" in lowered:
                problems.append(f"connection part is present: {name}")
            if not (lowered.endswith(".xml") or lowered.endswith(".rels")):
                continue
            content = package.read(name).decode("utf-8", errors="ignore")
            if "<f>" in content:
                problems.append(f"formula element is present: {name}")
            if 'TargetMode="External"' in content:
                problems.append(f"external relationship is present: {name}")
    return tuple(problems)


def export_calculation_workbook(
    calculation: CalculationResult,
    *,
    generated_at: datetime | None = None,
) -> bytes:
    _assert_checks_pass(calculation)
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0)

    workbook = Workbook()
    workbook.active.title = RESULT_SHEET
    for sheet_name in EXPORT_SHEET_NAMES[1:]:
        workbook.create_sheet(sheet_name)

    _write_sheet(workbook[RESULT_SHEET], RESULT_HEADERS, _result_rows(calculation))
    _write_sheet(workbook[SEGMENT_SHEET], SEGMENT_HEADERS, _segment_rows(calculation))
    _write_sheet(
        workbook[COMPANY_SUMMARY_SHEET],
        COMPANY_SUMMARY_HEADERS,
        _company_rows(calculation),
    )
    _write_sheet(
        workbook[CAPITALIZATION_SUMMARY_SHEET],
        CAPITALIZATION_SUMMARY_HEADERS,
        _capitalization_rows(calculation),
    )
    _write_sheet(workbook[CHECK_SHEET], CHECK_HEADERS, _check_rows(calculation))
    _write_sheet(
        workbook[PARAMETER_SHEET],
        PARAMETER_HEADERS,
        _parameter_rows(calculation, timestamp),
    )

    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    output = stream.getvalue()
    problems = inspect_export_package(output)
    if problems:
        raise ExportInvariantError("; ".join(problems))
    return output
