from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from loan_interest_accrual.domain import (
    DomainError,
    DomainValidationError,
    NaturalMonth,
    calculate_amortization_portfolio,
)
from loan_interest_accrual.workbook.amortization_exporter import (
    AmortizationExportInvariantError,
    export_amortization_workbook,
)
from loan_interest_accrual.workbook.amortization_importer import (
    import_amortization_workbook,
)
from loan_interest_accrual.workbook.schema import WorkbookError

from .amortization_results import (
    AmortizationCalculationServiceResult,
    AmortizationExportedWorkbook,
    AmortizationExportServiceResult,
    build_amortization_calculation_result,
)
from .results import ApplicationError


EXPORT_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


def calculate_amortization_submission(
    filename: str,
    source_bytes: bytes,
    period: NaturalMonth,
) -> AmortizationCalculationServiceResult:
    source_hash = sha256(source_bytes).hexdigest()
    imported = import_amortization_workbook(filename, source_bytes, period)
    if imported.errors:
        return AmortizationCalculationServiceResult(
            source_sha256=imported.source_sha256,
            errors=tuple(_workbook_error(error) for error in imported.errors),
            calculation=None,
        )
    if imported.calculable_input is None:
        return AmortizationCalculationServiceResult(
            source_sha256=source_hash,
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
        portfolio = calculate_amortization_portfolio(
            imported.calculable_input.period,
            imported.calculable_input.assets,
        )
    except DomainValidationError as caught:
        return AmortizationCalculationServiceResult(
            source_sha256=source_hash,
            errors=tuple(_domain_error(error) for error in caught.errors),
            calculation=None,
        )
    return AmortizationCalculationServiceResult(
        source_sha256=source_hash,
        errors=(),
        calculation=build_amortization_calculation_result(
            source_filename=filename,
            source_bytes=source_bytes,
            source_sha256=source_hash,
            portfolio=portfolio,
        ),
    )


def export_amortization_submission(
    filename: str,
    source_bytes: bytes,
    period: NaturalMonth,
    *,
    generated_at: datetime | None = None,
) -> AmortizationExportServiceResult:
    calculated = calculate_amortization_submission(filename, source_bytes, period)
    if calculated.errors or calculated.calculation is None:
        return AmortizationExportServiceResult(
            source_sha256=calculated.source_sha256,
            errors=calculated.errors,
            output=None,
        )
    try:
        workbook_bytes = export_amortization_workbook(
            calculated.calculation,
            generated_at=generated_at,
        )
    except AmortizationExportInvariantError as caught:
        return AmortizationExportServiceResult(
            source_sha256=calculated.source_sha256,
            errors=(
                ApplicationError(
                    error_code="EXPORT_CHECK_FAILED",
                    sheet="摊销明细",
                    row=None,
                    column_or_field="status",
                    message=str(caught),
                ),
            ),
            output=None,
        )
    month = f"{period.year:04d}-{period.month:02d}"
    return AmortizationExportServiceResult(
        source_sha256=calculated.source_sha256,
        errors=(),
        output=AmortizationExportedWorkbook(
            filename=f"摊销结果_{month}.xlsx",
            media_type=EXPORT_MEDIA_TYPE,
            workbook_bytes=workbook_bytes,
            calculation=calculated.calculation,
        ),
    )
