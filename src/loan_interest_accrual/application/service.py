from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from loan_interest_accrual.domain import (
    DomainError,
    DomainValidationError,
    NaturalMonth,
    calculate_portfolio,
)
from loan_interest_accrual.workbook import WorkbookError, import_workbook
from loan_interest_accrual.workbook.exporter import (
    ExportInvariantError,
    export_calculation_workbook,
)

from .results import (
    ApplicationError,
    CalculationServiceResult,
    ExportedWorkbook,
    ExportServiceResult,
    build_calculation_result,
    calculation_month,
)


EXPORT_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _workbook_error(error: WorkbookError) -> ApplicationError:
    return ApplicationError(
        error_code=error.error_code.value,
        sheet=error.sheet,
        row=error.row,
        column_or_field=error.column_or_field,
        message=error.message,
    )


def _domain_error(error: DomainError) -> ApplicationError:
    return ApplicationError(
        error_code=error.error_code.value,
        sheet=error.sheet,
        row=error.row,
        column_or_field=error.column_or_field,
        message=error.message,
    )


def _export_error(error: ExportInvariantError) -> ApplicationError:
    return ApplicationError(
        error_code="EXPORT_CHECK_FAILED",
        sheet="校验结果",
        row=None,
        column_or_field="status",
        message=str(error),
    )


def calculate_submission(
    filename: str,
    source_bytes: bytes,
    period: NaturalMonth,
) -> CalculationServiceResult:
    source_hash = sha256(source_bytes).hexdigest()
    try:
        imported = import_workbook(filename, source_bytes, period)
    except DomainValidationError as caught:
        return CalculationServiceResult(
            source_sha256=source_hash,
            errors=tuple(_domain_error(error) for error in caught.errors),
            calculation=None,
        )

    if imported.errors:
        return CalculationServiceResult(
            source_sha256=imported.source_sha256,
            errors=tuple(_workbook_error(error) for error in imported.errors),
            calculation=None,
        )
    if imported.calculable_input is None:
        return CalculationServiceResult(
            source_sha256=imported.source_sha256,
            errors=(
                ApplicationError(
                    error_code="CALCULABLE_INPUT_MISSING",
                    sheet=None,
                    row=None,
                    column_or_field="workbook",
                    message="workbook import produced no calculable input",
                ),
            ),
            calculation=None,
        )

    try:
        portfolio_result = calculate_portfolio(
            imported.calculable_input.period,
            imported.calculable_input.loans,
            imported.calculable_input.movements,
        )
    except DomainValidationError as caught:
        return CalculationServiceResult(
            source_sha256=imported.source_sha256,
            errors=tuple(_domain_error(error) for error in caught.errors),
            calculation=None,
        )

    return CalculationServiceResult(
        source_sha256=imported.source_sha256,
        errors=(),
        calculation=build_calculation_result(
            source_filename=filename,
            source_bytes=imported.source_bytes,
            source_sha256=imported.source_sha256,
            portfolio_result=portfolio_result,
        ),
    )


def export_submission(
    filename: str,
    source_bytes: bytes,
    period: NaturalMonth,
    *,
    generated_at: datetime | None = None,
) -> ExportServiceResult:
    calculated = calculate_submission(filename, source_bytes, period)
    if calculated.errors or calculated.calculation is None:
        return ExportServiceResult(
            source_sha256=calculated.source_sha256,
            errors=calculated.errors,
            output=None,
        )

    try:
        workbook_bytes = export_calculation_workbook(
            calculated.calculation,
            generated_at=generated_at,
        )
    except ExportInvariantError as caught:
        return ExportServiceResult(
            source_sha256=calculated.source_sha256,
            errors=(_export_error(caught),),
            output=None,
        )

    output_filename = f"计提结果_{calculation_month(period)}.xlsx"
    return ExportServiceResult(
        source_sha256=calculated.source_sha256,
        errors=(),
        output=ExportedWorkbook(
            filename=output_filename,
            media_type=EXPORT_MEDIA_TYPE,
            workbook_bytes=workbook_bytes,
            calculation=calculated.calculation,
        ),
    )
