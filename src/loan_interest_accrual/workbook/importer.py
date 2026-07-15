from hashlib import sha256

from loan_interest_accrual.domain import NaturalMonth

from .historical_importer import is_historical_workbook, validate_historical_workbook
from .safe_reader import read_workbook
from .schema import CalculableWorkbookInput, WorkbookImportResult
from .validation import sort_errors, validate_workbook


def import_workbook(
    filename: str,
    source_bytes: bytes,
    period: NaturalMonth,
) -> WorkbookImportResult:
    source_hash = sha256(source_bytes).hexdigest()
    safe_result = read_workbook(filename, source_bytes)
    if safe_result.workbook is None:
        return WorkbookImportResult(
            source_bytes=source_bytes,
            source_sha256=source_hash,
            calculable_input=None,
            errors=sort_errors(safe_result.errors),
        )

    workbook = safe_result.workbook
    try:
        outcome = validate_workbook(workbook, period)
        if outcome.errors and period.is_single_month and is_historical_workbook(workbook):
            outcome = validate_historical_workbook(workbook, period)
    finally:
        workbook.close()
    errors = sort_errors(safe_result.errors + outcome.errors)
    calculable_input = None
    if not errors:
        calculable_input = CalculableWorkbookInput(
            period=period,
            loans=outcome.loans,
            movements=outcome.movements,
        )
    return WorkbookImportResult(
        source_bytes=source_bytes,
        source_sha256=source_hash,
        calculable_input=calculable_input,
        errors=errors,
    )
