from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Iterable

from .decimal_math import configure_context, working_precision
from .errors import DomainError, DomainErrorCode, DomainValidationError
from .period import NaturalMonth


MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _required_text(value: object, field: str) -> None:
    if type(value) is not str or not value.strip():
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.REQUIRED_VALUE_MISSING,
                column_or_field=field,
                message=f"{field} must be non-empty text",
            )
        )


@dataclass(frozen=True, slots=True)
class AmortizationAsset:
    primary_category: str
    name: str
    expense_category: str
    original_value: Decimal
    residual_value: Decimal
    amortization_start: date
    booking_month: date
    amortization_term_months: int

    def __post_init__(self) -> None:
        _required_text(self.primary_category, "primary_category")
        _required_text(self.name, "name")
        _required_text(self.expense_category, "expense_category")
        for field, value in (
            ("original_value", self.original_value),
            ("residual_value", self.residual_value),
        ):
            if type(value) is not Decimal or not value.is_finite():
                raise DomainValidationError(
                    DomainError(
                        error_code=DomainErrorCode.DECIMAL_REQUIRED,
                        column_or_field=field,
                        message=f"{field} must be a finite Decimal",
                    )
                )
        residual_has_wrong_direction = (
            self.original_value >= Decimal("0")
            and not (Decimal("0") <= self.residual_value <= self.original_value)
        ) or (
            self.original_value < Decimal("0")
            and not (self.original_value <= self.residual_value <= Decimal("0"))
        )
        if residual_has_wrong_direction:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.RESIDUAL_VALUE_INVALID,
                    column_or_field="residual_value",
                    message="residual value must use the original value's sign direction",
                )
            )
        if type(self.amortization_start) is not date:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.DATE_INVALID,
                    column_or_field="amortization_start",
                    message="amortization start must be a date",
                )
            )
        if type(self.booking_month) is not date:
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.DATE_INVALID,
                    column_or_field="booking_month",
                    message="booking month must be a date",
                )
            )
        if (
            type(self.amortization_term_months) is not int
            or self.amortization_term_months <= 0
        ):
            raise DomainValidationError(
                DomainError(
                    error_code=DomainErrorCode.AMORTIZATION_TERM_INVALID,
                    column_or_field="amortization_term_months",
                    message="amortization term must be a positive integer",
                )
            )


@dataclass(frozen=True, slots=True)
class AmortizationResult:
    sequence: int
    asset: AmortizationAsset
    monthly_amortization: Decimal
    cumulative_months: int
    cumulative_amortization: Decimal
    current_required_amortization: Decimal | None
    current_actual_amortization: Decimal | None
    difference: Decimal | None
    ending_net_value: Decimal | None
    fully_amortized: bool


@dataclass(frozen=True, slots=True)
class AmortizationPortfolio:
    period: NaturalMonth
    results: tuple[AmortizationResult, ...]


def elapsed_months_inclusive(period: NaturalMonth, start: date) -> int:
    return (period.year - start.year) * 12 + period.month - start.month + 1


def calculate_asset(
    period: NaturalMonth,
    asset: AmortizationAsset,
    *,
    sequence: int = 1,
) -> AmortizationResult:
    if type(period) is not NaturalMonth:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                column_or_field="period",
                message="period must be a NaturalMonth",
            )
        )
    if type(asset) is not AmortizationAsset:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.VALUE_TYPE_INVALID,
                column_or_field="asset",
                message="asset must be an AmortizationAsset",
            )
        )
    elapsed = elapsed_months_inclusive(period, asset.amortization_start)
    if elapsed <= 0:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.START_MONTH_AFTER_CALCULATION,
                column_or_field="amortization_start",
                message="amortization start month must not be after calculation month",
            )
        )

    with localcontext() as context:
        values = (
            asset.original_value,
            asset.residual_value,
            Decimal(asset.amortization_term_months),
        )
        configure_context(context, working_precision(values))
        monthly = _money(
            (asset.original_value - asset.residual_value)
            / Decimal(asset.amortization_term_months)
        )

    cumulative_months = min(elapsed, asset.amortization_term_months)
    fully_amortized = elapsed >= asset.amortization_term_months
    if fully_amortized:
        cumulative = _money(asset.original_value)
        current_required = None
        current_actual = None
        difference = None
        ending_net = None
    else:
        cumulative = _money(monthly * Decimal(cumulative_months))
        current_required = monthly
        current_actual = monthly
        difference = None
        ending_net = _money(asset.original_value - cumulative)

    return AmortizationResult(
        sequence=sequence,
        asset=asset,
        monthly_amortization=monthly,
        cumulative_months=cumulative_months,
        cumulative_amortization=cumulative,
        current_required_amortization=current_required,
        current_actual_amortization=current_actual,
        difference=difference,
        ending_net_value=ending_net,
        fully_amortized=fully_amortized,
    )


def calculate_amortization_portfolio(
    period: NaturalMonth,
    assets: Iterable[AmortizationAsset],
) -> AmortizationPortfolio:
    normalized = tuple(assets)
    if not normalized:
        raise DomainValidationError(
            DomainError(
                error_code=DomainErrorCode.REQUIRED_VALUE_MISSING,
                column_or_field="assets",
                message="at least one asset is required",
            )
        )
    results = tuple(
        calculate_asset(period, asset, sequence=index)
        for index, asset in enumerate(normalized, start=1)
    )
    return AmortizationPortfolio(period=period, results=results)
