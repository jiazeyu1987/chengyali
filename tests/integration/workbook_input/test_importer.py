from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from itertools import permutations
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook, load_workbook

from loan_interest_accrual.domain import (
    DayCountBasis,
    DomainError,
    DomainErrorCode,
    DomainValidationError,
    MovementType,
    NaturalMonth,
)
from loan_interest_accrual.workbook import (
    LOAN_SHEET,
    LOAN_TEMPLATE_HEADERS,
    MAX_LOAN_ROWS,
    MAX_MOVEMENT_ROWS,
    MAX_UPLOAD_BYTES,
    MOVEMENT_SHEET,
    MOVEMENT_TEMPLATE_HEADERS,
    WorkbookErrorCode,
    import_workbook,
)
from loan_interest_accrual.workbook import validation as workbook_validation


PERIOD = NaturalMonth(2025, 6)


def loan_row(
    loan_id: object = "L-001",
    company: object = "甲公司",
    contract: object = "HT-001",
    bank: object = "甲银行",
    principal: object = 1000,
    rate: object = 0.025,
    basis: object = 365,
    start: object = date(2025, 1, 1),
    end: object = date(2025, 12, 31),
    capitalized: object = "否",
    note: object = None,
) -> list[object]:
    return [
        loan_id,
        company,
        contract,
        bank,
        principal,
        rate,
        basis,
        start,
        end,
        capitalized,
        note,
    ]


def movement_row(
    loan_id: object = "L-001",
    event_date: object = date(2025, 6, 15),
    movement_type: object = "放款",
    amount: object = 1,
    note: object = None,
) -> list[object]:
    return [loan_id, event_date, movement_type, amount, note]


def workbook_bytes(
    *,
    loan_headers: tuple[str, ...] = LOAN_TEMPLATE_HEADERS,
    movement_headers: tuple[str, ...] = MOVEMENT_TEMPLATE_HEADERS,
    loans: list[list[object]] | None = None,
    movements: list[list[object]] | None = None,
    include_loan_sheet: bool = True,
    include_movement_sheet: bool = True,
    extra_sheet: bool = False,
) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    if include_loan_sheet:
        sheet = workbook.create_sheet(LOAN_SHEET)
        sheet.append(list(loan_headers))
        for values in loans if loans is not None else [loan_row()]:
            sheet.append(values)
        if "年利率" in loan_headers:
            rate_column = loan_headers.index("年利率") + 1
            for row in range(2, sheet.max_row + 1):
                sheet.cell(row, rate_column).number_format = "0.00%"
        for header in ("计息开始日期", "计息结束日期"):
            if header in loan_headers:
                column = loan_headers.index(header) + 1
                for row in range(2, sheet.max_row + 1):
                    sheet.cell(row, column).number_format = "yyyy-mm-dd"
    if include_movement_sheet:
        sheet = workbook.create_sheet(MOVEMENT_SHEET)
        sheet.append(list(movement_headers))
        for values in movements or []:
            sheet.append(values)
        if "变动日期" in movement_headers:
            column = movement_headers.index("变动日期") + 1
            for row in range(2, sheet.max_row + 1):
                sheet.cell(row, column).number_format = "yyyy-mm-dd"
    if extra_sheet:
        workbook.create_sheet("其他信息")["A1"] = "不得作为输入来源"
    if not workbook.worksheets:
        workbook.create_sheet("其他信息")["A1"] = "非标准工作簿"
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def edit_workbook(payload: bytes, edit) -> bytes:
    workbook = load_workbook(BytesIO(payload))
    edit(workbook)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def rewrite_package(
    payload: bytes,
    *,
    replacements: dict[str, bytes] | None = None,
    additions: dict[str, bytes] | None = None,
) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as source, ZipFile(
        output, "w", ZIP_DEFLATED
    ) as target:
        for info in source.infolist():
            target.writestr(
                info,
                (replacements or {}).get(info.filename, source.read(info.filename)),
            )
        for name, content in (additions or {}).items():
            target.writestr(name, content)
    return output.getvalue()


def codes(result) -> list[WorkbookErrorCode]:
    return [error.error_code for error in result.errors]


def test_valid_workbook_parses_exact_ids_units_rates_and_domain_types() -> None:
    payload = workbook_bytes(
        loans=[
            loan_row("L-001", company="同公司", contract="同合同"),
            loan_row("L-002", company="同公司", contract="同合同", basis=360),
        ],
        movements=[
            movement_row("L-002", amount=1),
            movement_row("L-002", event_date=date(2025, 6, 15), amount=2),
        ],
        extra_sheet=True,
    )

    result = import_workbook("input.XLSX", payload, PERIOD)

    assert result.errors == ()
    assert result.calculable_input is not None
    assert [loan.loan_id for loan in result.calculable_input.loans] == [
        "L-001",
        "L-002",
    ]
    assert result.calculable_input.loans[0].annual_rate == Decimal("0.025")
    assert result.calculable_input.loans[1].day_count_basis is DayCountBasis.DAYS_360
    assert result.calculable_input.movements[0].amount == Decimal("1")
    assert result.calculable_input.movements[0].movement_type is MovementType.DRAWDOWN


@pytest.mark.parametrize("filename", ["input.xls", "input.xlsm", "input.csv", "input"])
def test_only_xlsx_extension_is_accepted(filename: str) -> None:
    result = import_workbook(filename, workbook_bytes(), PERIOD)
    assert codes(result) == [WorkbookErrorCode.FILE_EXTENSION_INVALID]
    assert result.calculable_input is None


def test_corrupt_xlsx_fails_structurally() -> None:
    result = import_workbook("input.xlsx", b"not-a-zip", PERIOD)
    assert codes(result) == [WorkbookErrorCode.WORKBOOK_OPEN_FAILED]


def test_file_size_limit_is_inclusive_and_exceedance_is_not_opened() -> None:
    at_limit = import_workbook("input.xlsx", b"x" * MAX_UPLOAD_BYTES, PERIOD)
    assert WorkbookErrorCode.FILE_TOO_LARGE not in codes(at_limit)
    assert WorkbookErrorCode.WORKBOOK_OPEN_FAILED in codes(at_limit)

    over_limit = import_workbook("input.xlsx", b"x" * (MAX_UPLOAD_BYTES + 1), PERIOD)
    assert codes(over_limit) == [WorkbookErrorCode.FILE_TOO_LARGE]


@pytest.mark.parametrize(
    ("addition", "expected"),
    [
        ({"xl/vbaProject.bin": b"macro"}, WorkbookErrorCode.MACRO_NOT_ALLOWED),
        (
            {"xl/externalLinks/externalLink1.xml": b"<externalLink/>"},
            WorkbookErrorCode.EXTERNAL_LINK_NOT_ALLOWED,
        ),
        ({"xl/connections.xml": b"<connections/>"}, WorkbookErrorCode.EXTERNAL_LINK_NOT_ALLOWED),
    ],
)
def test_active_and_external_package_content_is_rejected(
    addition: dict[str, bytes],
    expected: WorkbookErrorCode,
) -> None:
    payload = rewrite_package(workbook_bytes(), additions=addition)
    result = import_workbook("input.xlsx", payload, PERIOD)
    assert expected in codes(result)
    assert result.calculable_input is None


def test_duplicate_required_sheet_name_is_rejected() -> None:
    payload = workbook_bytes()
    with ZipFile(BytesIO(payload)) as package:
        root = ElementTree.fromstring(package.read("xl/workbook.xml"))
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    sheets = root.find("m:sheets", namespace)
    assert sheets is not None
    sheets[1].set("name", LOAN_SHEET)
    changed = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    payload = rewrite_package(payload, replacements={"xl/workbook.xml": changed})

    result = import_workbook("input.xlsx", payload, PERIOD)
    assert codes(result) == [WorkbookErrorCode.SHEET_DUPLICATE]


def test_missing_sheets_columns_duplicate_columns_and_aliases_are_not_inferred() -> None:
    missing_sheets = import_workbook(
        "input.xlsx",
        workbook_bytes(include_loan_sheet=False, include_movement_sheet=False),
        PERIOD,
    )
    assert codes(missing_sheets) == [
        WorkbookErrorCode.SHEET_MISSING,
        WorkbookErrorCode.SHEET_MISSING,
    ]

    alias_headers = tuple(
        "Loan ID" if header == "贷款ID" else header for header in LOAN_TEMPLATE_HEADERS
    )
    missing_column = import_workbook(
        "input.xlsx",
        workbook_bytes(loan_headers=alias_headers),
        PERIOD,
    )
    assert WorkbookErrorCode.COLUMN_MISSING in codes(missing_column)

    duplicate_headers = LOAN_TEMPLATE_HEADERS + ("贷款ID",)
    duplicate_column = import_workbook(
        "input.xlsx",
        workbook_bytes(
            loan_headers=duplicate_headers,
            loans=[loan_row() + ["ALIAS-ID"]],
        ),
        PERIOD,
    )
    assert WorkbookErrorCode.COLUMN_DUPLICATE in codes(duplicate_column)


def test_header_errors_do_not_hide_detectable_formula_errors() -> None:
    loan_headers = tuple(
        header for header in LOAN_TEMPLATE_HEADERS if header != "贷款银行"
    )
    payload = edit_workbook(
        workbook_bytes(
            loan_headers=loan_headers,
            loans=[loan_row()[:-1]],
            movements=[movement_row()],
        ),
        lambda workbook: setattr(workbook[MOVEMENT_SHEET]["D2"], "value", "=1+1"),
    )

    result = import_workbook("input.xlsx", payload, PERIOD)

    assert codes(result) == [
        WorkbookErrorCode.COLUMN_MISSING,
        WorkbookErrorCode.FORMULA_NOT_ALLOWED,
    ]
    assert result.errors[0].sheet == LOAN_SHEET
    assert result.errors[0].column_or_field == "贷款银行"
    assert result.errors[1].sheet == MOVEMENT_SHEET
    assert result.errors[1].row == 2
    assert result.errors[1].column_or_field == "变动金额（元）"
    assert result.calculable_input is None


def test_formula_cells_are_rejected_with_location() -> None:
    payload = edit_workbook(
        workbook_bytes(),
        lambda workbook: setattr(workbook[LOAN_SHEET]["E2"], "value", "=1+1"),
    )
    result = import_workbook("input.xlsx", payload, PERIOD)

    assert codes(result) == [WorkbookErrorCode.FORMULA_NOT_ALLOWED]
    assert result.errors[0].sheet == LOAN_SHEET
    assert result.errors[0].row == 2
    assert result.errors[0].column_or_field == "期初本金（元）"


def test_blank_and_duplicate_loan_ids_and_ambiguous_movements_fail() -> None:
    payload = workbook_bytes(
        loans=[loan_row("L-001"), loan_row("L-001"), loan_row("")],
        movements=[movement_row("L-001")],
    )
    result = import_workbook("input.xlsx", payload, PERIOD)

    assert codes(result) == [
        WorkbookErrorCode.LOAN_ID_DUPLICATE,
        WorkbookErrorCode.LOAN_ID_DUPLICATE,
        WorkbookErrorCode.LOAN_ID_REQUIRED,
        WorkbookErrorCode.MOVEMENT_LOAN_ID_AMBIGUOUS,
    ]
    assert result.calculable_input is None


def test_multiple_errors_are_collected_in_deterministic_sheet_row_field_order() -> None:
    payload = workbook_bytes(
        loans=[
            loan_row(
                "",
                company="",
                principal="1000",
                rate=2.5,
                basis=364,
                start="2025-06-01",
                capitalized="可能",
            )
        ],
        movements=[movement_row("UNKNOWN", date(2025, 7, 1), "错误", 0)],
    )
    payload = edit_workbook(
        payload,
        lambda workbook: setattr(
            workbook[LOAN_SHEET]["F2"], "number_format", "General"
        ),
    )
    result = import_workbook("input.xlsx", payload, PERIOD)

    assert [
        (error.sheet, error.row, error.column_or_field, error.error_code)
        for error in result.errors
    ] == [
        (LOAN_SHEET, 2, "贷款ID", WorkbookErrorCode.LOAN_ID_REQUIRED),
        (LOAN_SHEET, 2, "公司名称", WorkbookErrorCode.REQUIRED_VALUE_MISSING),
        (LOAN_SHEET, 2, "期初本金（元）", WorkbookErrorCode.VALUE_TYPE_INVALID),
        (LOAN_SHEET, 2, "年利率", WorkbookErrorCode.INTEREST_RATE_INVALID),
        (LOAN_SHEET, 2, "计息基准", WorkbookErrorCode.DAY_COUNT_BASIS_INVALID),
        (LOAN_SHEET, 2, "计息开始日期", WorkbookErrorCode.DATE_INVALID),
        (LOAN_SHEET, 2, "是否资本化", WorkbookErrorCode.CAPITALIZATION_FLAG_INVALID),
        (
            MOVEMENT_SHEET,
            2,
            "贷款ID",
            WorkbookErrorCode.MOVEMENT_LOAN_ID_NOT_FOUND,
        ),
        (
            MOVEMENT_SHEET,
            2,
            "变动日期",
            WorkbookErrorCode.MOVEMENT_DATE_OUTSIDE_MONTH,
        ),
        (
            MOVEMENT_SHEET,
            2,
            "变动类型",
            WorkbookErrorCode.MOVEMENT_TYPE_INVALID,
        ),
        (
            MOVEMENT_SHEET,
            2,
            "变动金额（元）",
            WorkbookErrorCode.MOVEMENT_AMOUNT_INVALID,
        ),
    ]
    assert result.calculable_input is None


def test_date_relationship_rate_basis_enum_and_amount_boundaries() -> None:
    cases = [
        (
            workbook_bytes(
                loans=[
                    loan_row(
                        start=date(2024, 1, 1),
                        end=date(2024, 12, 31),
                    )
                ]
            ),
            WorkbookErrorCode.LOAN_PERIOD_OUTSIDE_MONTH,
        ),
        (
            workbook_bytes(
                loans=[
                    loan_row(
                        start=date(2025, 6, 20),
                        end=date(2025, 6, 10),
                    )
                ]
            ),
            WorkbookErrorCode.DATE_RANGE_INVALID,
        ),
        (
            workbook_bytes(loans=[loan_row(basis="365")]),
            WorkbookErrorCode.DAY_COUNT_BASIS_INVALID,
        ),
        (
            workbook_bytes(loans=[loan_row(capitalized="Y")]),
            WorkbookErrorCode.CAPITALIZATION_FLAG_INVALID,
        ),
        (
            workbook_bytes(movements=[movement_row("", amount=1)]),
            WorkbookErrorCode.MOVEMENT_LOAN_ID_REQUIRED,
        ),
        (
            workbook_bytes(movements=[movement_row("UNKNOWN", amount=1)]),
            WorkbookErrorCode.MOVEMENT_LOAN_ID_NOT_FOUND,
        ),
        (
            workbook_bytes(movements=[movement_row(movement_type="借款")]),
            WorkbookErrorCode.MOVEMENT_TYPE_INVALID,
        ),
        (
            workbook_bytes(movements=[movement_row(amount=-1)]),
            WorkbookErrorCode.MOVEMENT_AMOUNT_INVALID,
        ),
        (
            workbook_bytes(movements=[movement_row(event_date=date(2025, 5, 31))]),
            WorkbookErrorCode.MOVEMENT_DATE_OUTSIDE_MONTH,
        ),
        (
            workbook_bytes(loans=[loan_row(rate=0)]),
            WorkbookErrorCode.INTEREST_RATE_INVALID,
        ),
        (
            workbook_bytes(loans=[loan_row(rate=1)]),
            WorkbookErrorCode.INTEREST_RATE_INVALID,
        ),
        (
            workbook_bytes(loans=[loan_row(rate=2.5)]),
            WorkbookErrorCode.INTEREST_RATE_INVALID,
        ),
    ]
    for payload, expected in cases:
        result = import_workbook("input.xlsx", payload, PERIOD)
        assert expected in codes(result)
        assert result.calculable_input is None

    non_percent = edit_workbook(
        workbook_bytes(loans=[loan_row(rate=2.5)]),
        lambda workbook: setattr(
            workbook[LOAN_SHEET]["F2"], "number_format", "General"
        ),
    )
    assert WorkbookErrorCode.INTEREST_RATE_INVALID in codes(
        import_workbook("input.xlsx", non_percent, PERIOD)
    )


def test_negative_principal_uses_domain_calculator_and_locates_movement() -> None:
    payload = workbook_bytes(
        loans=[loan_row(principal=100)],
        movements=[movement_row(movement_type="还本", amount=101)],
    )
    result = import_workbook("input.xlsx", payload, PERIOD)

    assert codes(result) == [WorkbookErrorCode.NEGATIVE_PRINCIPAL]
    assert result.errors[0].sheet == MOVEMENT_SHEET
    assert result.errors[0].row == 2
    assert result.calculable_input is None


def test_portfolio_business_validation_errors_are_mapped_to_source_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_portfolio(period, loans, movements):
        assert period is PERIOD
        assert tuple(loan.loan_id for loan in loans) == ("L-001",)
        assert tuple(movement.loan_id for movement in movements) == ("L-001",)
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.NEGATIVE_PRINCIPAL,
                column_or_field="principal",
                message="principal becomes negative at an effective event boundary",
                loan_id="L-001",
                event_date=date(2025, 6, 15),
            )
        )

    monkeypatch.setattr(workbook_validation, "calculate_portfolio", fail_portfolio)
    payload = workbook_bytes(movements=[movement_row(movement_type="还本")])

    result = import_workbook("input.xlsx", payload, PERIOD)

    assert codes(result) == [WorkbookErrorCode.NEGATIVE_PRINCIPAL]
    assert result.errors[0].sheet == MOVEMENT_SHEET
    assert result.errors[0].row == 2
    assert result.errors[0].column_or_field == "变动金额（元）"
    assert result.calculable_input is None


def test_same_day_movement_order_is_preserved_as_input_but_calculates_by_loan_id() -> None:
    rows = [
        movement_row(amount=10),
        movement_row(movement_type="还本", amount=3),
        movement_row(amount=2),
    ]
    endings = set()
    for ordering in permutations(rows):
        result = import_workbook(
            "input.xlsx",
            workbook_bytes(movements=list(ordering)),
            PERIOD,
        )
        assert result.errors == ()
        assert result.calculable_input is not None
        endings.add(
            tuple(
                (movement.movement_type, movement.amount)
                for movement in result.calculable_input.movements
            )
        )
    assert len(endings) == 6


def test_row_limits_allow_boundary_and_reject_exceedance_without_truncation() -> None:
    boundary = load_workbook(BytesIO(workbook_bytes()))
    boundary[LOAN_SHEET].cell(MAX_LOAN_ROWS + 1, 1, "L-LAST")
    for column, value in enumerate(loan_row("L-LAST"), start=1):
        boundary[LOAN_SHEET].cell(MAX_LOAN_ROWS + 1, column, value)
    boundary[LOAN_SHEET].cell(MAX_LOAN_ROWS + 1, 6).number_format = "0.00%"
    for column, value in enumerate(movement_row(), start=1):
        boundary[MOVEMENT_SHEET].cell(MAX_MOVEMENT_ROWS + 1, column, value)
    stream = BytesIO()
    boundary.save(stream)
    boundary_result = import_workbook("input.xlsx", stream.getvalue(), PERIOD)
    assert WorkbookErrorCode.LOAN_ROW_LIMIT_EXCEEDED not in codes(boundary_result)
    assert WorkbookErrorCode.MOVEMENT_ROW_LIMIT_EXCEEDED not in codes(boundary_result)

    loan_over = edit_workbook(
        workbook_bytes(),
        lambda workbook: workbook[LOAN_SHEET].cell(
            MAX_LOAN_ROWS + 2, 1, "OVER"
        ),
    )
    assert codes(import_workbook("input.xlsx", loan_over, PERIOD)) == [
        WorkbookErrorCode.LOAN_ROW_LIMIT_EXCEEDED
    ]

    movement_over = edit_workbook(
        workbook_bytes(),
        lambda workbook: workbook[MOVEMENT_SHEET].cell(
            MAX_MOVEMENT_ROWS + 2, 1, "OVER"
        ),
    )
    assert codes(import_workbook("input.xlsx", movement_over, PERIOD)) == [
        WorkbookErrorCode.MOVEMENT_ROW_LIMIT_EXCEEDED
    ]


def test_source_file_bytes_and_hash_are_never_modified(tmp_path) -> None:
    payload = workbook_bytes(movements=[movement_row()])
    source_path = tmp_path / "source.xlsx"
    source_path.write_bytes(payload)
    before = sha256(source_path.read_bytes()).hexdigest()

    result = import_workbook(source_path.name, source_path.read_bytes(), PERIOD)

    assert result.errors == ()
    assert result.source_bytes == payload
    assert result.source_sha256 == before
    assert source_path.read_bytes() == payload
    assert sha256(source_path.read_bytes()).hexdigest() == before
