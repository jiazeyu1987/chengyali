from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Iterable

from .decimal_math import (
    ZERO,
    configure_context,
    exact_difference,
    exact_sum,
    quantize_money,
    working_precision,
)
from .errors import DomainError, DomainErrorCode, DomainValidationError
from .models import (
    DayCountBasis,
    InterestSegment,
    Loan,
    LoanResult,
    Movement,
    MovementType,
    PortfolioResult,
)
from .period import NaturalMonth
from .reconciliation import (
    build_reconciliation_checks,
    summarize_capitalization,
    summarize_companies,
)


@dataclass(frozen=True, slots=True)
class _DailyMovement:
    event_date: date
    drawdowns: Decimal
    repayments: Decimal

    @property
    def net_change(self) -> Decimal:
        return exact_difference(self.drawdowns, self.repayments)


def _aggregate_movements(
    period: NaturalMonth,
    loan: Loan,
    movements: Iterable[Movement],
) -> tuple[_DailyMovement, ...]:
    by_date: dict[date, list[list[Decimal]]] = defaultdict(
        lambda: [[], []]
    )
    for item in movements:
        if type(item) is not Movement:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="movements",
                    message="movements must contain Movement values",
                    loan_id=loan.loan_id,
                )
            )
        if item.loan_id != loan.loan_id:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.MOVEMENT_LOAN_MISMATCH,
                    column_or_field="loan_id",
                    message="movement loan ID does not match the calculated loan",
                    loan_id=item.loan_id,
                    event_date=item.event_date,
                )
            )
        if not period.contains(item.event_date):
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.MOVEMENT_DATE_OUTSIDE_MONTH,
                    column_or_field="event_date",
                    message="movement date is outside the selected month",
                    loan_id=item.loan_id,
                    event_date=item.event_date,
                )
            )
        bucket = by_date[item.event_date]
        if item.movement_type is MovementType.DRAWDOWN:
            bucket[0].append(item.amount)
        else:
            bucket[1].append(item.amount)

    return tuple(
        _DailyMovement(
            event_date=event_date,
            drawdowns=exact_sum(amounts[0]),
            repayments=exact_sum(amounts[1]),
        )
        for event_date, amounts in sorted(by_date.items())
    )


def _roll_principal(
    loan: Loan,
    daily_movements: tuple[_DailyMovement, ...],
) -> tuple[dict[date, Decimal], Decimal, Decimal, Decimal]:
    principal = loan.opening_principal
    principal_after_event: dict[date, Decimal] = {}

    for daily in daily_movements:
        principal = exact_sum((principal, daily.net_change))
        if principal < ZERO:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.NEGATIVE_PRINCIPAL,
                    column_or_field="principal",
                    message="principal becomes negative at an effective event boundary",
                    loan_id=loan.loan_id,
                    event_date=daily.event_date,
                )
            )
        principal_after_event[daily.event_date] = principal

    total_drawdowns = exact_sum(
        daily.drawdowns for daily in daily_movements
    )
    total_repayments = exact_sum(
        daily.repayments for daily in daily_movements
    )
    return (
        principal_after_event,
        total_drawdowns,
        total_repayments,
        principal,
    )


def _segment_interest(
    principal: Decimal,
    annual_rate: Decimal,
    basis: DayCountBasis,
    days: int,
) -> Decimal:
    with localcontext() as context:
        values = (
            principal,
            annual_rate,
            Decimal(days),
            Decimal(basis.value),
        )
        configure_context(context, working_precision(values))
        return (
            principal
            * annual_rate
            * Decimal(days)
            / Decimal(basis.value)
        )


def _build_segments(
    loan: Loan,
    actual_start: date,
    actual_end: date,
    daily_movements: tuple[_DailyMovement, ...],
    principal_after_event: dict[date, Decimal],
) -> tuple[InterestSegment, ...]:
    current_principal = loan.opening_principal
    for daily in daily_movements:
        if daily.event_date < actual_start:
            current_principal = principal_after_event[daily.event_date]

    segments: list[InterestSegment] = []
    current_start = actual_start
    sequence = 1

    for daily in daily_movements:
        if daily.event_date < actual_start or daily.event_date > actual_end:
            continue
        segment_end = daily.event_date
        days = (segment_end - current_start).days + 1
        segments.append(
            InterestSegment(
                sequence=sequence,
                loan_id=loan.loan_id,
                start_date=current_start,
                end_date=segment_end,
                days=days,
                principal=current_principal,
                annual_rate=loan.annual_rate,
                day_count_basis=loan.day_count_basis,
                unrounded_interest=_segment_interest(
                    current_principal,
                    loan.annual_rate,
                    loan.day_count_basis,
                    days,
                ),
                ending_principal=principal_after_event[daily.event_date],
                trigger_date=daily.event_date,
            )
        )
        sequence += 1
        current_principal = principal_after_event[daily.event_date]
        current_start = daily.event_date + timedelta(days=1)

    if current_start <= actual_end:
        days = (actual_end - current_start).days + 1
        segments.append(
            InterestSegment(
                sequence=sequence,
                loan_id=loan.loan_id,
                start_date=current_start,
                end_date=actual_end,
                days=days,
                principal=current_principal,
                annual_rate=loan.annual_rate,
                day_count_basis=loan.day_count_basis,
                unrounded_interest=_segment_interest(
                    current_principal,
                    loan.annual_rate,
                    loan.day_count_basis,
                    days,
                ),
                ending_principal=current_principal,
                trigger_date=None,
            )
        )

    return tuple(segments)


def calculate_loan(
    period: NaturalMonth,
    loan: Loan,
    movements: Iterable[Movement],
) -> LoanResult:
    if type(period) is not NaturalMonth:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                column_or_field="period",
                message="period must be a NaturalMonth value",
            )
        )
    if type(loan) is not Loan:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                column_or_field="loan",
                message="loan must be a Loan value",
            )
        )

    raw_actual_start = max(period.start_date, loan.accrual_start)
    actual_end = min(period.end_date, loan.accrual_end)
    if raw_actual_start > actual_end:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.LOAN_PERIOD_OUTSIDE_MONTH,
                column_or_field="accrual_period",
                message="loan accrual period does not intersect the selected month",
                loan_id=loan.loan_id,
            )
        )

    # The loan's accrual-start date is the value date. Interest begins on the
    # following day; loans that started before the selected month still begin
    # at the first calendar day of that month.
    actual_start = max(
        period.start_date,
        loan.accrual_start + timedelta(days=1),
    )

    daily_movements = _aggregate_movements(period, loan, movements)
    (
        principal_after_event,
        total_drawdowns,
        total_repayments,
        ending_principal,
    ) = _roll_principal(loan, daily_movements)
    segments = _build_segments(
        loan,
        actual_start,
        actual_end,
        daily_movements,
        principal_after_event,
    )
    interest_days = (actual_end - actual_start).days + 1
    if sum(segment.days for segment in segments) != interest_days:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.RECONCILIATION_FAILED,
                column_or_field="segments",
                message="segment days do not reconcile to loan interest days",
                loan_id=loan.loan_id,
            )
        )

    unrounded_interest = exact_sum(
        segment.unrounded_interest for segment in segments
    )
    accrued_interest = quantize_money(unrounded_interest)
    if loan.capitalize_interest:
        capitalized_interest = accrued_interest
        expensed_interest = Decimal("0.00")
    else:
        capitalized_interest = Decimal("0.00")
        expensed_interest = accrued_interest

    return LoanResult(
        period=period,
        loan=loan,
        actual_start=actual_start,
        actual_end=actual_end,
        interest_days=interest_days,
        segments=segments,
        total_drawdowns=total_drawdowns,
        total_repayments=total_repayments,
        ending_principal=ending_principal,
        unrounded_interest=unrounded_interest,
        accrued_interest=accrued_interest,
        capitalized_interest=capitalized_interest,
        expensed_interest=expensed_interest,
    )


def calculate_portfolio(
    period: NaturalMonth,
    loans: Iterable[Loan],
    movements: Iterable[Movement],
) -> PortfolioResult:
    if type(period) is not NaturalMonth:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                column_or_field="period",
                message="period must be a NaturalMonth value",
            )
        )

    loan_values = tuple(loans)
    movement_values = tuple(movements)
    loan_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    for loan in loan_values:
        if type(loan) is not Loan:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="loans",
                    message="loans must contain Loan values",
                )
            )
        if loan.loan_id in loan_ids:
            duplicate_ids.add(loan.loan_id)
        loan_ids.add(loan.loan_id)

    if duplicate_ids:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.LOAN_ID_DUPLICATE,
                column_or_field="loan_id",
                message="loan ID must be unique",
                loan_id=loan_id,
            )
            for loan_id in sorted(duplicate_ids)
        )

    movements_by_loan: dict[str, list[Movement]] = defaultdict(list)
    unknown_errors = []
    for movement in movement_values:
        if type(movement) is not Movement:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                    column_or_field="movements",
                    message="movements must contain Movement values",
                )
            )
        if movement.loan_id not in loan_ids:
            unknown_errors.append(
                DomainError(
                    error_code=DomainErrorCode.MOVEMENT_LOAN_ID_NOT_FOUND,
                    column_or_field="loan_id",
                    message="movement references an unknown loan ID",
                    loan_id=movement.loan_id,
                    event_date=movement.event_date,
                )
            )
        else:
            movements_by_loan[movement.loan_id].append(movement)
    if unknown_errors:
        raise DomainValidationError(
            sorted(
                unknown_errors,
                key=lambda error: (
                    error.loan_id or "",
                    error.event_date or date.min,
                ),
            )
        )

    loan_results = tuple(
        calculate_loan(
            period,
            loan,
            movements_by_loan.get(loan.loan_id, ()),
        )
        for loan in sorted(loan_values, key=lambda value: value.loan_id)
    )
    company_summaries = summarize_companies(loan_results)
    capitalization_summaries = summarize_capitalization(loan_results)
    checks = build_reconciliation_checks(
        loan_results,
        company_summaries,
        capitalization_summaries,
    )
    failed_checks = tuple(check for check in checks if not check.passed)
    if failed_checks:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.RECONCILIATION_FAILED,
                column_or_field=check.name,
                message=f"reconciliation failed: {check.name}",
            )
            for check in failed_checks
        )

    total_capitalized_interest = exact_sum(
        summary.capitalized_interest
        for summary in capitalization_summaries
    )
    return PortfolioResult(
        period=period,
        loan_results=loan_results,
        company_summaries=company_summaries,
        capitalization_summaries=capitalization_summaries,
        total_capitalized_interest=total_capitalized_interest,
        checks=checks,
    )
