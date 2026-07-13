from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .limits import MAX_LOAN_ROWS, MAX_MOVEMENT_ROWS
from .schema import (
    CURRENCY_NUMBER_FORMAT,
    DATE_NUMBER_FORMAT,
    LOAN_SHEET,
    LOAN_TEMPLATE_HEADERS,
    MOVEMENT_SHEET,
    MOVEMENT_TEMPLATE_HEADERS,
    PERCENT_NUMBER_FORMAT,
)


_LOAN_INSTRUCTIONS = (
    "填写唯一且非空的贷款ID。",
    "填写非空公司名称。",
    "填写非空贷款合同号；不得作为关联键。",
    "填写非空贷款银行。",
    "填写人民币元金额，必须大于或等于0。",
    "使用Excel百分比格式填写，例如2.50%。",
    "仅填写整数360或365。",
    "填写有效日期，该日计息。",
    "填写有效日期，该日计息且不得早于开始日期。",
    "仅填写是或否。",
    "可选备注，不参与计算。",
)
_MOVEMENT_INSTRUCTIONS = (
    "填写贷款主表中唯一存在的贷款ID。",
    "填写所选自然月内的有效日期。",
    "仅填写放款或还本。",
    "填写人民币元金额，必须大于0。",
    "可选备注，不参与计算。",
)


def _configure_sheet(sheet, headers, instructions, max_rows: int) -> None:
    sheet.append(headers)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(headers)).column_letter}1"
    fill = PatternFill("solid", fgColor="1D2330")
    for column, (header, instruction) in enumerate(
        zip(headers, instructions, strict=True), start=1
    ):
        cell = sheet.cell(1, column)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = fill
        cell.comment = Comment(f"填写说明：{instruction}", "本地应用")
        sheet.column_dimensions[cell.column_letter].width = max(14, len(header) * 2 + 2)
    for row in range(2, 3):
        for column in range(1, len(headers) + 1):
            sheet.cell(row, column)
    sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(headers)).column_letter}{max_rows + 1}"


def generate_standard_template() -> bytes:
    workbook = Workbook()
    loan_sheet = workbook.active
    loan_sheet.title = LOAN_SHEET
    movement_sheet = workbook.create_sheet(MOVEMENT_SHEET)
    _configure_sheet(
        loan_sheet, LOAN_TEMPLATE_HEADERS, _LOAN_INSTRUCTIONS, MAX_LOAN_ROWS
    )
    _configure_sheet(
        movement_sheet,
        MOVEMENT_TEMPLATE_HEADERS,
        _MOVEMENT_INSTRUCTIONS,
        MAX_MOVEMENT_ROWS,
    )

    loan_sheet["E2"].number_format = CURRENCY_NUMBER_FORMAT
    loan_sheet["F2"].number_format = PERCENT_NUMBER_FORMAT
    loan_sheet["H2"].number_format = DATE_NUMBER_FORMAT
    loan_sheet["I2"].number_format = DATE_NUMBER_FORMAT
    movement_sheet["B2"].number_format = DATE_NUMBER_FORMAT
    movement_sheet["D2"].number_format = CURRENCY_NUMBER_FORMAT

    basis = DataValidation(type="list", formula1='"360,365"', allow_blank=False)
    capitalized = DataValidation(type="list", formula1='"是,否"', allow_blank=False)
    movement_type = DataValidation(
        type="list", formula1='"放款,还本"', allow_blank=False
    )
    loan_sheet.add_data_validation(basis)
    loan_sheet.add_data_validation(capitalized)
    movement_sheet.add_data_validation(movement_type)
    basis.add(f"G2:G{MAX_LOAN_ROWS + 1}")
    capitalized.add(f"J2:J{MAX_LOAN_ROWS + 1}")
    movement_type.add(f"C2:C{MAX_MOVEMENT_ROWS + 1}")

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()
