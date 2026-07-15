from datetime import date

import pytest

from loan_interest_accrual.domain import (
    DomainErrorCode,
    DomainValidationError,
    NaturalMonth,
)


@pytest.mark.parametrize(
    ("year", "month", "expected_start", "expected_end"),
    [
        (2023, 2, date(2023, 2, 1), date(2023, 2, 28)),
        (2024, 2, date(2024, 2, 1), date(2024, 2, 29)),
        (2025, 6, date(2025, 6, 1), date(2025, 6, 30)),
        (2025, 7, date(2025, 7, 1), date(2025, 7, 31)),
    ],
)
def test_natural_month_uses_true_calendar_bounds(
    year: int,
    month: int,
    expected_start: date,
    expected_end: date,
) -> None:
    period = NaturalMonth(year=year, month=month)

    assert period.start_date == expected_start
    assert period.end_date == expected_end
    assert period.day_count == (expected_end - expected_start).days + 1


def test_month_range_uses_first_day_through_last_day() -> None:
    period = NaturalMonth(2025, 6, 2025, 8)

    assert period.start_date == date(2025, 6, 1)
    assert period.end_date == date(2025, 8, 31)
    assert period.day_count == 92
    assert period.is_single_month is False


def test_exact_date_range_uses_selected_calendar_days() -> None:
    period = NaturalMonth(2025, 6, 2025, 8, 10, 20)

    assert period.start_date == date(2025, 6, 10)
    assert period.end_date == date(2025, 8, 20)
    assert period.day_count == 72
    assert period.is_exact_date_range is True


def test_exact_date_range_rejects_invalid_day_or_reverse_order() -> None:
    with pytest.raises(DomainValidationError):
        NaturalMonth(2025, 2, 2025, 3, 30, 1)
    with pytest.raises(DomainValidationError):
        NaturalMonth(2025, 6, 2025, 6, 20, 10)


def test_month_range_rejects_end_before_start() -> None:
    with pytest.raises(DomainValidationError) as caught:
        NaturalMonth(2025, 8, 2025, 6)

    assert caught.value.errors[0].error_code is DomainErrorCode.PERIOD_INVALID


@pytest.mark.parametrize(
    ("year", "month"),
    [(2025, 0), (2025, 13), (True, 6), (2025, False)],
)
def test_natural_month_rejects_invalid_or_coerced_values(
    year: object,
    month: object,
) -> None:
    with pytest.raises(DomainValidationError) as caught:
        NaturalMonth(year=year, month=month)  # type: ignore[arg-type]

    assert caught.value.errors[0].error_code is DomainErrorCode.PERIOD_INVALID
