from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from openpyxl.workbook.workbook import Workbook

from loan_interest_accrual.domain import (
    DayCountBasis,
    DomainValidationError,
    Loan,
    Movement,
    MovementType,
    NaturalMonth,
    calculate_portfolio,
)

from .limits import MAX_LOAN_ROWS, MAX_MOVEMENT_ROWS
from .schema import (
    LOAN_REQUIRED_HEADERS,
    LOAN_SHEET,
    LOAN_TEMPLATE_HEADERS,
    MOVEMENT_REQUIRED_HEADERS,
    MOVEMENT_SHEET,
    MOVEMENT_TEMPLATE_HEADERS,
    WorkbookError,
    WorkbookErrorCode,
)


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    loans: tuple[Loan, ...]
    movements: tuple[Movement, ...]
    errors: tuple[WorkbookError, ...]


def _error(
    code: WorkbookErrorCode,
    sheet: str,
    row: int | None,
    field: str,
    message: str,
) -> WorkbookError:
    return WorkbookError(code, sheet, row, field, message)


def _blank(value: object) -> bool:
    return value is None or (type(value) is str and value.strip() == "")


def _text(value: object) -> str | None:
    return value if type(value) is str and value.strip() != "" else None


def _decimal(value: object) -> Decimal | None:
    if type(value) is bool or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _date(value: object) -> date | None:
    if type(value) is datetime:
        return value.date()
    return value if type(value) is date else None


def _headers(sheet, required: tuple[str, ...]) -> tuple[dict[str, int], list[WorkbookError]]:
    values = [cell.value for cell in sheet[1]]
    positions: dict[str, list[int]] = {}
    for index, value in enumerate(values, start=1):
        if type(value) is str:
            positions.setdefault(value, []).append(index)
    errors: list[WorkbookError] = []
    mapping: dict[str, int] = {}
    for header in required:
        found = positions.get(header, [])
        if not found:
            errors.append(
                _error(
                    WorkbookErrorCode.COLUMN_MISSING,
                    sheet.title,
                    1,
                    header,
                    f"required column is missing: {header}",
                )
            )
        elif len(found) > 1:
            errors.append(
                _error(
                    WorkbookErrorCode.COLUMN_DUPLICATE,
                    sheet.title,
                    1,
                    header,
                    f"required column is duplicated: {header}",
                )
            )
        else:
            mapping[header] = found[0]
    return mapping, errors


def _data_row_numbers(sheet) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                cell.row
                for cell in sheet._cells.values()
                if cell.row >= 2 and not _blank(cell.value)
            }
        )
    )


def _formula_errors(sheet) -> list[WorkbookError]:
    errors: list[WorkbookError] = []
    headers = {
        index: value
        for index, value in enumerate(
            (cell.value for cell in sheet[1]), start=1
        )
        if type(value) is str
    }
    for cell in sorted(sheet._cells.values(), key=lambda item: (item.row, item.column)):
        if cell.data_type == "f":
            field = headers.get(cell.column, cell.coordinate)
            errors.append(
                _error(
                    WorkbookErrorCode.FORMULA_NOT_ALLOWED,
                    sheet.title,
                    cell.row,
                    field,
                    "formula cells are not allowed",
                )
            )
    return errors


def _loan_rows(
    sheet,
    period: NaturalMonth,
    mapping: dict[str, int],
    formula_errors: tuple[WorkbookError, ...],
):
    errors: list[WorkbookError] = []
    parsed: list[tuple[int, dict[str, object]]] = []
    ids: list[tuple[int, str]] = []
    formula_cells = {
        (error.row, error.column_or_field) for error in formula_errors
    }
    for row in _data_row_numbers(sheet):
        values = {
            field: sheet.cell(row, column).value for field, column in mapping.items()
        }
        valid = True
        loan_id = _text(values.get("贷款ID"))
        if (row, "贷款ID") in formula_cells:
            valid = False
        elif loan_id is None:
            errors.append(
                _error(
                    WorkbookErrorCode.LOAN_ID_REQUIRED,
                    LOAN_SHEET,
                    row,
                    "贷款ID",
                    "贷款ID must be non-empty text",
                )
            )
            valid = False
        else:
            ids.append((row, loan_id))

        for field in ("公司名称", "贷款合同号", "贷款银行"):
            if (row, field) in formula_cells:
                valid = False
            elif _text(values.get(field)) is None:
                errors.append(
                    _error(
                        WorkbookErrorCode.REQUIRED_VALUE_MISSING,
                        LOAN_SHEET,
                        row,
                        field,
                        f"{field} must be non-empty text",
                    )
                )
                valid = False

        principal = _decimal(values.get("期初本金（元）"))
        if (row, "期初本金（元）") in formula_cells:
            valid = False
        elif principal is None:
            errors.append(
                _error(
                    WorkbookErrorCode.VALUE_TYPE_INVALID,
                    LOAN_SHEET,
                    row,
                    "期初本金（元）",
                    "opening principal must be a numeric RMB amount",
                )
            )
            valid = False
        elif principal < 0:
            errors.append(
                _error(
                    WorkbookErrorCode.NEGATIVE_PRINCIPAL,
                    LOAN_SHEET,
                    row,
                    "期初本金（元）",
                    "opening principal must not be negative",
                )
            )
            valid = False

        rate_cell = sheet.cell(row, mapping.get("年利率", 1))
        rate = _decimal(values.get("年利率"))
        if (row, "年利率") in formula_cells:
            valid = False
        elif (
            rate is None
            or rate <= 0
            or rate >= 1
            or "%" not in rate_cell.number_format
        ):
            errors.append(
                _error(
                    WorkbookErrorCode.INTEREST_RATE_INVALID,
                    LOAN_SHEET,
                    row,
                    "年利率",
                    "annual rate must be an Excel percentage value greater than 0 and less than 100%",
                )
            )
            valid = False

        basis_value = values.get("计息基准")
        basis = (
            DayCountBasis(basis_value)
            if type(basis_value) is int and basis_value in (360, 365)
            else None
        )
        if (row, "计息基准") in formula_cells:
            valid = False
        elif basis is None:
            errors.append(
                _error(
                    WorkbookErrorCode.DAY_COUNT_BASIS_INVALID,
                    LOAN_SHEET,
                    row,
                    "计息基准",
                    "day-count basis must be integer 360 or 365",
                )
            )
            valid = False

        start = _date(values.get("计息开始日期"))
        end = _date(values.get("计息结束日期"))
        for field, parsed_date in (
            ("计息开始日期", start),
            ("计息结束日期", end),
        ):
            if (row, field) in formula_cells:
                valid = False
            elif parsed_date is None:
                errors.append(
                    _error(
                        WorkbookErrorCode.DATE_INVALID,
                        LOAN_SHEET,
                        row,
                        field,
                        f"{field} must be a valid Excel date",
                    )
                )
                valid = False
        if start is not None and end is not None:
            if end < start:
                errors.append(
                    _error(
                        WorkbookErrorCode.DATE_RANGE_INVALID,
                        LOAN_SHEET,
                        row,
                        "计息结束日期",
                        "accrual end must not precede accrual start",
                    )
                )
                valid = False
            elif end < period.start_date or start > period.end_date:
                errors.append(
                    _error(
                        WorkbookErrorCode.LOAN_PERIOD_OUTSIDE_MONTH,
                        LOAN_SHEET,
                        row,
                        "计息开始日期",
                        "loan accrual period does not intersect the selected month",
                    )
                )
                valid = False

        capitalized_value = values.get("是否资本化")
        capitalized = (
            capitalized_value == "是"
            if capitalized_value in ("是", "否")
            else None
        )
        if (row, "是否资本化") in formula_cells:
            valid = False
        elif capitalized is None:
            errors.append(
                _error(
                    WorkbookErrorCode.CAPITALIZATION_FLAG_INVALID,
                    LOAN_SHEET,
                    row,
                    "是否资本化",
                    "capitalization flag must be 是 or 否",
                )
            )
            valid = False
        parsed.append(
            (
                row,
                {
                    "valid": valid,
                    "loan_id": loan_id,
                    "company_name": _text(values.get("公司名称")),
                    "contract_number": _text(values.get("贷款合同号")),
                    "bank_name": _text(values.get("贷款银行")),
                    "opening_principal": principal,
                    "annual_rate": rate,
                    "day_count_basis": basis,
                    "accrual_start": start,
                    "accrual_end": end,
                    "capitalize_interest": capitalized,
                },
            )
        )
    counts = Counter(loan_id for _, loan_id in ids)
    duplicate_ids = {loan_id for loan_id, count in counts.items() if count > 1}
    for row, loan_id in ids:
        if loan_id in duplicate_ids:
            errors.append(
                _error(
                    WorkbookErrorCode.LOAN_ID_DUPLICATE,
                    LOAN_SHEET,
                    row,
                    "贷款ID",
                    f"贷款ID is duplicated: {loan_id}",
                )
            )
    loans: list[tuple[int, Loan]] = []
    for row, values in parsed:
        if not values["valid"] or values["loan_id"] in duplicate_ids:
            continue
        try:
            loans.append(
                (
                    row,
                    Loan(
                        loan_id=values["loan_id"],
                        company_name=values["company_name"],
                        contract_number=values["contract_number"],
                        bank_name=values["bank_name"],
                        opening_principal=values["opening_principal"],
                        annual_rate=values["annual_rate"],
                        day_count_basis=values["day_count_basis"],
                        accrual_start=values["accrual_start"],
                        accrual_end=values["accrual_end"],
                        capitalize_interest=values["capitalize_interest"],
                    ),
                )
            )
        except DomainValidationError:
            continue
    return loans, counts, errors


def _movement_rows(
    sheet,
    period: NaturalMonth,
    mapping,
    loan_counts,
    formula_errors: tuple[WorkbookError, ...],
):
    errors: list[WorkbookError] = []
    movements: list[tuple[int, Movement]] = []
    invalid_loan_ids: set[str] = set()
    formula_cells = {
        (error.row, error.column_or_field) for error in formula_errors
    }
    for row in _data_row_numbers(sheet):
        values = {
            field: sheet.cell(row, column).value for field, column in mapping.items()
        }
        valid = True
        loan_id = _text(values.get("贷款ID"))
        if (row, "贷款ID") in formula_cells:
            valid = False
        elif loan_id is None:
            errors.append(
                _error(
                    WorkbookErrorCode.MOVEMENT_LOAN_ID_REQUIRED,
                    MOVEMENT_SHEET,
                    row,
                    "贷款ID",
                    "movement 贷款ID must be non-empty text",
                )
            )
            valid = False
        elif loan_counts.get(loan_id, 0) == 0:
            errors.append(
                _error(
                    WorkbookErrorCode.MOVEMENT_LOAN_ID_NOT_FOUND,
                    MOVEMENT_SHEET,
                    row,
                    "贷款ID",
                    f"movement 贷款ID was not found: {loan_id}",
                )
            )
            valid = False
        elif loan_counts[loan_id] > 1:
            errors.append(
                _error(
                    WorkbookErrorCode.MOVEMENT_LOAN_ID_AMBIGUOUS,
                    MOVEMENT_SHEET,
                    row,
                    "贷款ID",
                    f"movement 贷款ID is not unique: {loan_id}",
                )
            )
            valid = False

        event_date = _date(values.get("变动日期"))
        if (row, "变动日期") in formula_cells:
            valid = False
        elif event_date is None:
            errors.append(
                _error(
                    WorkbookErrorCode.DATE_INVALID,
                    MOVEMENT_SHEET,
                    row,
                    "变动日期",
                    "movement date must be a valid Excel date",
                )
            )
            valid = False
        elif not period.contains(event_date):
            errors.append(
                _error(
                    WorkbookErrorCode.MOVEMENT_DATE_OUTSIDE_MONTH,
                    MOVEMENT_SHEET,
                    row,
                    "变动日期",
                    "movement date must be inside the selected month",
                )
            )
            valid = False

        type_value = values.get("变动类型")
        movement_type = {
            "放款": MovementType.DRAWDOWN,
            "还本": MovementType.REPAYMENT,
        }.get(type_value)
        if (row, "变动类型") in formula_cells:
            valid = False
        elif movement_type is None:
            errors.append(
                _error(
                    WorkbookErrorCode.MOVEMENT_TYPE_INVALID,
                    MOVEMENT_SHEET,
                    row,
                    "变动类型",
                    "movement type must be 放款 or 还本",
                )
            )
            valid = False

        amount = _decimal(values.get("变动金额（元）"))
        if (row, "变动金额（元）") in formula_cells:
            valid = False
        elif amount is None or amount <= 0:
            errors.append(
                _error(
                    WorkbookErrorCode.MOVEMENT_AMOUNT_INVALID,
                    MOVEMENT_SHEET,
                    row,
                    "变动金额（元）",
                    "movement amount must be a numeric RMB amount greater than zero",
                )
            )
            valid = False
        if not valid:
            if loan_id is not None and loan_counts.get(loan_id) == 1:
                invalid_loan_ids.add(loan_id)
            continue
        movements.append(
            (
                row,
                Movement(
                    loan_id=loan_id,
                    event_date=event_date,
                    movement_type=movement_type,
                    amount=amount,
                ),
            )
        )
    return movements, invalid_loan_ids, errors


def _sort_key(error: WorkbookError):
    sheet_rank = {None: -1, LOAN_SHEET: 0, MOVEMENT_SHEET: 1}
    field_orders = {
        LOAN_SHEET: {name: index for index, name in enumerate(LOAN_TEMPLATE_HEADERS)},
        MOVEMENT_SHEET: {
            name: index for index, name in enumerate(MOVEMENT_TEMPLATE_HEADERS)
        },
    }
    return (
        sheet_rank.get(error.sheet, 2),
        error.row if error.row is not None else 0,
        field_orders.get(error.sheet, {}).get(error.column_or_field, 999),
        error.column_or_field,
        error.error_code.value,
    )


def sort_errors(errors) -> tuple[WorkbookError, ...]:
    return tuple(sorted(errors, key=_sort_key))


def _business_validation_errors(
    period: NaturalMonth,
    loans_with_rows: tuple[tuple[int, Loan], ...],
    movements_with_rows: tuple[tuple[int, Movement], ...],
    invalid_movement_ids: set[str],
) -> tuple[WorkbookError, ...]:
    loans = tuple(
        loan for _, loan in loans_with_rows if loan.loan_id not in invalid_movement_ids
    )
    loan_ids = {loan.loan_id for loan in loans}
    movements = tuple(
        movement
        for _, movement in movements_with_rows
        if movement.loan_id in loan_ids
    )
    if not loans:
        return ()

    loan_rows = {loan.loan_id: row for row, loan in loans_with_rows}
    movement_rows: dict[tuple[str, date], int] = {}
    for row, movement in movements_with_rows:
        movement_rows.setdefault((movement.loan_id, movement.event_date), row)

    try:
        calculate_portfolio(period, loans, movements)
    except DomainValidationError as caught:
        errors: list[WorkbookError] = []
        for domain_error in caught.errors:
            if domain_error.error_code.value == WorkbookErrorCode.NEGATIVE_PRINCIPAL:
                errors.append(
                    _error(
                        WorkbookErrorCode.NEGATIVE_PRINCIPAL,
                        MOVEMENT_SHEET,
                        movement_rows.get(
                            (domain_error.loan_id, domain_error.event_date)
                        ),
                        "变动金额（元）",
                        domain_error.message,
                    )
                )
                continue
            workbook_code = (
                WorkbookErrorCode(domain_error.error_code.value)
                if domain_error.error_code.value in WorkbookErrorCode._value2member_map_
                else WorkbookErrorCode.VALUE_TYPE_INVALID
            )
            errors.append(
                _error(
                    workbook_code,
                    LOAN_SHEET,
                    loan_rows.get(domain_error.loan_id),
                    domain_error.column_or_field,
                    domain_error.message,
                )
            )
        return tuple(errors)
    return ()


def validate_workbook(workbook: Workbook, period: NaturalMonth) -> ValidationOutcome:
    errors: list[WorkbookError] = []
    for sheet_name in (LOAN_SHEET, MOVEMENT_SHEET):
        if sheet_name not in workbook.sheetnames:
            errors.append(
                _error(
                    WorkbookErrorCode.SHEET_MISSING,
                    sheet_name,
                    None,
                    sheet_name,
                    f"required worksheet is missing: {sheet_name}",
                )
            )
    for sheet_name in (LOAN_SHEET, MOVEMENT_SHEET):
        if sheet_name in workbook.sheetnames:
            errors.extend(_formula_errors(workbook[sheet_name]))
    if LOAN_SHEET not in workbook.sheetnames or MOVEMENT_SHEET not in workbook.sheetnames:
        return ValidationOutcome((), (), sort_errors(errors))

    loan_sheet = workbook[LOAN_SHEET]
    movement_sheet = workbook[MOVEMENT_SHEET]
    loan_formula_errors = tuple(
        error for error in errors if error.sheet == LOAN_SHEET
    )
    movement_formula_errors = tuple(
        error for error in errors if error.sheet == MOVEMENT_SHEET
    )
    loan_mapping, loan_header_errors = _headers(
        loan_sheet, LOAN_REQUIRED_HEADERS
    )
    movement_mapping, movement_header_errors = _headers(
        movement_sheet, MOVEMENT_REQUIRED_HEADERS
    )
    errors.extend(loan_header_errors)
    errors.extend(movement_header_errors)

    loan_over = loan_sheet.max_row - 1 > MAX_LOAN_ROWS
    movement_over = movement_sheet.max_row - 1 > MAX_MOVEMENT_ROWS
    if loan_over:
        errors.append(
            _error(
                WorkbookErrorCode.LOAN_ROW_LIMIT_EXCEEDED,
                LOAN_SHEET,
                None,
                "rows",
                f"贷款主表 exceeds {MAX_LOAN_ROWS} data rows",
            )
        )
    if movement_over:
        errors.append(
            _error(
                WorkbookErrorCode.MOVEMENT_ROW_LIMIT_EXCEEDED,
                MOVEMENT_SHEET,
                None,
                "rows",
                f"资金变动 exceeds {MAX_MOVEMENT_ROWS} data rows",
            )
        )
    if loan_header_errors or movement_header_errors or loan_over or movement_over:
        return ValidationOutcome((), (), sort_errors(errors))

    loans_with_rows, loan_counts, loan_errors = _loan_rows(
        loan_sheet, period, loan_mapping, loan_formula_errors
    )
    movements_with_rows, invalid_movement_ids, movement_errors = _movement_rows(
        movement_sheet,
        period,
        movement_mapping,
        loan_counts,
        movement_formula_errors,
    )
    errors.extend(loan_errors)
    errors.extend(movement_errors)
    errors.extend(
        _business_validation_errors(
            period,
            tuple(loans_with_rows),
            tuple(movements_with_rows),
            invalid_movement_ids,
        )
    )
    movements = tuple(movement for _, movement in movements_with_rows)

    return ValidationOutcome(
        tuple(loan for _, loan in loans_with_rows),
        movements,
        sort_errors(errors),
    )
