from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .amortization_schema import (
    AMORTIZATION_RESULT_HEADERS,
    AMOUNT_NUMBER_FORMAT,
    DATE_NUMBER_FORMAT,
    MONTH_COUNT_NUMBER_FORMAT,
)

if TYPE_CHECKING:
    from loan_interest_accrual.application.amortization_results import (
        AmortizationCalculationResult,
    )


RESULT_SHEET = "摊销明细"


class AmortizationExportInvariantError(ValueError):
    pass


def _set_value(cell, value: object) -> None:
    cell.value = value
    if type(value) is str and not value.startswith("="):
        cell.data_type = "s"


def export_amortization_workbook(
    calculation: "AmortizationCalculationResult",
    *,
    generated_at: datetime | None = None,
) -> bytes:
    if any(not check.passed for check in calculation.checks):
        raise AmortizationExportInvariantError(
            "amortization checks failed; export was blocked"
        )
    if not calculation.rows:
        raise AmortizationExportInvariantError("no amortization rows to export")

    generated_at = generated_at or datetime.now(timezone.utc)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = RESULT_SHEET
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A3"
    sheet.auto_filter.ref = f"A2:P{len(calculation.rows) + 3}"

    period = calculation.period
    title = f"无形资产、长期待摊费用摊销明细  {period.year}年{period.month}月"
    sheet.merge_cells("A1:P1")
    _set_value(sheet["A1"], title)
    sheet["A1"].font = Font(name="Microsoft YaHei", size=14, bold=True)
    sheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
    sheet["A1"].fill = PatternFill("solid", fgColor="C6E0B4")
    sheet.row_dimensions[1].height = 28

    input_fill = PatternFill("solid", fgColor="FFF200")
    formula_fill = PatternFill("solid", fgColor="C6E0B4")
    border = Border(
        left=Side(style="thin", color="548235"),
        right=Side(style="thin", color="548235"),
        top=Side(style="thin", color="548235"),
        bottom=Side(style="thin", color="548235"),
    )
    for column, header in enumerate(AMORTIZATION_RESULT_HEADERS, start=1):
        cell = sheet.cell(2, column, header)
        cell.fill = input_fill if column <= 9 else formula_fill
        cell.font = Font(name="Microsoft YaHei", size=10, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    sheet.row_dimensions[2].height = 34

    sheet["Q1"] = "计提月份"
    sheet["R1"] = period.start_date
    sheet["R1"].number_format = DATE_NUMBER_FORMAT
    sheet["Q2"] = "生成时间"
    sheet["R2"] = generated_at.replace(tzinfo=None)
    sheet["R2"].number_format = "yyyy-mm-dd hh:mm:ss"
    sheet.column_dimensions["Q"].hidden = True
    sheet.column_dimensions["R"].hidden = True

    first_data_row = 3
    for offset, row in enumerate(calculation.rows):
        excel_row = first_data_row + offset
        values = (
            row.sequence,
            row.primary_category,
            row.name,
            row.expense_category,
            row.original_value,
            row.residual_value,
            row.amortization_start,
            row.booking_month,
            row.amortization_term_months,
        )
        for column, value in enumerate(values, start=1):
            _set_value(sheet.cell(excel_row, column), value)
        sheet.cell(excel_row, 10, f"=ROUND((E{excel_row}-F{excel_row})/I{excel_row},2)")
        sheet.cell(
            excel_row,
            11,
            f"=MIN(I{excel_row},MAX(0,(YEAR($R$1)-YEAR(G{excel_row}))*12+MONTH($R$1)-MONTH(G{excel_row})+1))",
        )
        sheet.cell(
            excel_row,
            12,
            f"=IF(K{excel_row}>=I{excel_row},E{excel_row},J{excel_row}*K{excel_row})",
        )
        sheet.cell(excel_row, 13, f'=IF(K{excel_row}>=I{excel_row},"",J{excel_row})')
        sheet.cell(excel_row, 14, f'=IF(K{excel_row}>=I{excel_row},"",J{excel_row})')
        sheet.cell(excel_row, 15, None)
        sheet.cell(excel_row, 16, f'=IF(K{excel_row}>=I{excel_row},"",E{excel_row}-L{excel_row})')
        for column in range(1, 17):
            cell = sheet.cell(excel_row, column)
            cell.border = border
            cell.alignment = Alignment(
                horizontal="left" if column in (2, 3, 4) else "right",
                vertical="center",
            )
            if column >= 10:
                cell.fill = PatternFill("solid", fgColor="E2F0D9")

    last_data_row = first_data_row + len(calculation.rows) - 1
    total_row = last_data_row + 1
    sheet.cell(total_row, 2, "合计")
    for column in (5, 10, 12, 13, 14, 16):
        letter = get_column_letter(column)
        sheet.cell(total_row, column, f"=SUM({letter}{first_data_row}:{letter}{last_data_row})")
    for column in (7, 8, 9, 11):
        sheet.cell(total_row, column, "/")
    for column in range(1, 17):
        cell = sheet.cell(total_row, column)
        cell.fill = PatternFill("solid", fgColor="C6E0B4")
        cell.font = Font(name="Microsoft YaHei", size=10, bold=True)
        cell.border = border
        cell.alignment = Alignment(
            horizontal="center" if column in (1, 2, 7, 8, 9, 11, 15) else "right",
            vertical="center",
        )

    for row in range(first_data_row, total_row + 1):
        for column in (5, 6, 10, 12, 13, 14, 15, 16):
            sheet.cell(row, column).number_format = AMOUNT_NUMBER_FORMAT
        for column in (7, 8):
            sheet.cell(row, column).number_format = DATE_NUMBER_FORMAT
        for column in (1, 9, 11):
            sheet.cell(row, column).number_format = MONTH_COUNT_NUMBER_FORMAT

    widths = (8, 20, 42, 16, 16, 13, 17, 17, 17, 15, 22, 23, 19, 21, 12, 16)
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = "1:2"
    sheet.print_area = f"A1:P{total_row}"

    workbook.calculation.calcMode = "auto"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()
