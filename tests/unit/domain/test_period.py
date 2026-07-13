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
