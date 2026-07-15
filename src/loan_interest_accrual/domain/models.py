from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import IntEnum, StrEnum

from .errors import DomainError, DomainErrorCode, DomainValidationError
from .period import NaturalMonth


class DayCountBasis(IntEnum):
    DAYS_360 = 360
    DAYS_365 = 365


class MovementType(StrEnum):
    DRAWDOWN = "drawdown"
    REPAYMENT = "repayment"


def _required_text(value: object, field: str, code: DomainErrorCode) -> None:
    if type(value) is not str or value == "" or value.isspace():
        raise DomainValidationError(
            DomainError(
                error_code=code,
                column_or_field=field,
                message=f"{field} must be non-empty text",
                loan_id=value if type(value) is str and value != "" else None,
            )
        )


def _required_decimal(value: object, field: str, loan_id: str | None) -> None:
    if type(value) is not Decimal:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.DECIMAL_REQUIRED,
                column_or_field=field,
                message=f"{field} must be Decimal",
                loan_id=loan_id,
            )
        )
    if not value.is_finite():
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                column_or_field=field,
                message=f"{field} must be a finite Decimal",
                loan_id=loan_id,
            )
        )


def _required_date(value: object, field: str, loan_id: str | None) -> None:
    if type(value) is not date:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.DATE_INVALID,
                column_or_field=field,
                message=f"{field} must be a date",
                loan_id=loan_id,
            )
        )


@dataclass(frozen=True, slots=True)
class Loan:
    loan_id: str
    company_name: str
    contract_number: str
    bank_name: str
    opening_principal: Decimal
    annual_rate: Decimal
    day_count_basis: DayCountBasis
    accrual_start: date
    accrual_end: date
    capitalize_interest: bool

    def __post_init__(self) -> None:
        _required_text(self.loan_id, "loan_id", DomainErrorCode.LOAN_ID_REQUIRED)
        if type(self.company_name) is not str:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="company_name",
                    message="company_name must be text when provided",
                    loan_id=self.loan_id,
                )
            )
        if type(self.contract_number) is not str:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="contract_number",
                    message="contract_number must be text when provided",
                    loan_id=self.loan_id,
                )
            )
        if type(self.bank_name) is not str:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="bank_name",
                    message="bank_name must be text when provided",
                    loan_id=self.loan_id,
                )
            )
        _required_decimal(self.opening_principal, "opening_principal", self.loan_id)
        _required_decimal(self.annual_rate, "annual_rate", self.loan_id)
        if self.opening_principal < Decimal("0"):
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.NEGATIVE_PRINCIPAL,
                    column_or_field="opening_principal",
                    message="opening principal must not be negative",
                    loan_id=self.loan_id,
                )
            )
        if self.annual_rate < Decimal("0"):
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.INTEREST_RATE_INVALID,
                    column_or_field="annual_rate",
                    message="annual rate must not be negative",
                    loan_id=self.loan_id,
                )
            )
        if type(self.day_count_basis) is not DayCountBasis:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.DAY_COUNT_BASIS_INVALID,
                    column_or_field="day_count_basis",
                    message="day-count basis must be DayCountBasis.DAYS_360 or DAYS_365",
                    loan_id=self.loan_id,
                )
            )
        _required_date(self.accrual_start, "accrual_start", self.loan_id)
        _required_date(self.accrual_end, "accrual_end", self.loan_id)
        if self.accrual_end < self.accrual_start:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.DATE_RANGE_INVALID,
                    column_or_field="accrual_end",
                    message="accrual end must not precede accrual start",
                    loan_id=self.loan_id,
                )
            )
        if type(self.capitalize_interest) is not bool:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="capitalize_interest",
                    message="capitalize_interest must be bool",
                    loan_id=self.loan_id,
                )
            )


@dataclass(frozen=True, slots=True)
class Movement:
    loan_id: str
    event_date: date
    movement_type: MovementType
    amount: Decimal

    def __post_init__(self) -> None:
        _required_text(
            self.loan_id,
            "loan_id",
            DomainErrorCode.MOVEMENT_LOAN_ID_REQUIRED,
        )
        _required_date(self.event_date, "event_date", self.loan_id)
        if type(self.movement_type) is not MovementType:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.MOVEMENT_TYPE_INVALID,
                    column_or_field="movement_type",
                    message="movement type must be drawdown or repayment",
                    loan_id=self.loan_id,
                    event_date=self.event_date,
                )
            )
        _required_decimal(self.amount, "amount", self.loan_id)
        if self.amount <= Decimal("0"):
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.MOVEMENT_AMOUNT_INVALID,
                    column_or_field="amount",
                    message="movement amount must be greater than zero",
                    loan_id=self.loan_id,
                    event_date=self.event_date,
                )
            )


@dataclass(frozen=True, slots=True)
class InterestSegment:
    sequence: int
    loan_id: str
    start_date: date
    end_date: date
    days: int
    principal: Decimal
    annual_rate: Decimal
    day_count_basis: DayCountBasis
    unrounded_interest: Decimal
    ending_principal: Decimal
    trigger_date: date | None


@dataclass(frozen=True, slots=True)
class LoanResult:
    period: NaturalMonth
    loan: Loan
    actual_start: date
    actual_end: date
    interest_days: int
    segments: tuple[InterestSegment, ...]
    total_drawdowns: Decimal
    total_repayments: Decimal
    ending_principal: Decimal
    unrounded_interest: Decimal
    accrued_interest: Decimal
    capitalized_interest: Decimal
    expensed_interest: Decimal


@dataclass(frozen=True, slots=True)
class CompanySummary:
    company_name: str
    loan_count: int
    opening_principal: Decimal
    total_drawdowns: Decimal
    total_repayments: Decimal
    ending_principal: Decimal
    accrued_interest: Decimal
    capitalized_interest: Decimal
    expensed_interest: Decimal


@dataclass(frozen=True, slots=True)
class CapitalizationSummary:
    company_name: str
    capitalized_loan_count: int
    ending_principal: Decimal
    capitalized_interest: Decimal


@dataclass(frozen=True, slots=True)
class ReconciliationCheck:
    name: str
    passed: bool
    expected: Decimal
    actual: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    period: NaturalMonth
    loan_results: tuple[LoanResult, ...]
    company_summaries: tuple[CompanySummary, ...]
    capitalization_summaries: tuple[CapitalizationSummary, ...]
    total_capitalized_interest: Decimal
    checks: tuple[ReconciliationCheck, ...]
