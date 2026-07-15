from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Iterable


class DomainErrorCode(StrEnum):
    PERIOD_INVALID = "PERIOD_INVALID"
    LOAN_ID_REQUIRED = "LOAN_ID_REQUIRED"
    LOAN_ID_DUPLICATE = "LOAN_ID_DUPLICATE"
    REQUIRED_VALUE_MISSING = "REQUIRED_VALUE_MISSING"
    VALUE_TYPE_INVALID = "VALUE_TYPE_INVALID"
    DECIMAL_REQUIRED = "DECIMAL_REQUIRED"
    INTEREST_RATE_INVALID = "INTEREST_RATE_INVALID"
    DAY_COUNT_BASIS_INVALID = "DAY_COUNT_BASIS_INVALID"
    DATE_INVALID = "DATE_INVALID"
    DATE_RANGE_INVALID = "DATE_RANGE_INVALID"
    LOAN_PERIOD_OUTSIDE_MONTH = "LOAN_PERIOD_OUTSIDE_MONTH"
    MOVEMENT_LOAN_ID_REQUIRED = "MOVEMENT_LOAN_ID_REQUIRED"
    MOVEMENT_LOAN_ID_NOT_FOUND = "MOVEMENT_LOAN_ID_NOT_FOUND"
    MOVEMENT_LOAN_MISMATCH = "MOVEMENT_LOAN_MISMATCH"
    MOVEMENT_TYPE_INVALID = "MOVEMENT_TYPE_INVALID"
    MOVEMENT_AMOUNT_INVALID = "MOVEMENT_AMOUNT_INVALID"
    MOVEMENT_DATE_OUTSIDE_MONTH = "MOVEMENT_DATE_OUTSIDE_MONTH"
    NEGATIVE_PRINCIPAL = "NEGATIVE_PRINCIPAL"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    ORIGINAL_VALUE_INVALID = "ORIGINAL_VALUE_INVALID"
    RESIDUAL_VALUE_INVALID = "RESIDUAL_VALUE_INVALID"
    AMORTIZATION_TERM_INVALID = "AMORTIZATION_TERM_INVALID"
    START_MONTH_AFTER_CALCULATION = "START_MONTH_AFTER_CALCULATION"


@dataclass(frozen=True, slots=True)
class DomainError:
    error_code: DomainErrorCode
    column_or_field: str
    message: str
    loan_id: str | None = None
    event_date: date | None = None
    sheet: str | None = None
    row: int | None = None


class DomainValidationError(ValueError):
    def __init__(self, errors: DomainError | Iterable[DomainError]) -> None:
        if isinstance(errors, DomainError):
            normalized = (errors,)
        else:
            normalized = tuple(errors)
        if not normalized:
            raise ValueError("DomainValidationError requires at least one error")
        self.errors = normalized
        super().__init__("; ".join(error.message for error in normalized))
