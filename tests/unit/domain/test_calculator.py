import ast
from datetime import date, timedelta
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import pytest

from loan_interest_accrual.domain import (
    DayCountBasis,
    DomainErrorCode,
    DomainValidationError,
    Loan,
    Movement,
    MovementType,
    NaturalMonth,
    calculate_loan,
)


def make_loan(
    *,
    loan_id: str = "L-001",
    principal: str = "1000",
    rate: str = "0.0365",
    basis: DayCountBasis = DayCountBasis.DAYS_365,
    accrual_start: date = date(2025, 1, 1),
    accrual_end: date = date(2025, 12, 31),
    capitalized: bool = False,
) -> Loan:
    return Loan(
        loan_id=loan_id,
        company_name="Company A",
        contract_number="C-001",
        bank_name="Bank A",
        opening_principal=Decimal(principal),
        annual_rate=Decimal(rate),
        day_count_basis=basis,
        accrual_start=accrual_start,
        accrual_end=accrual_end,
        capitalize_interest=capitalized,
    )


def movement(
    event_date: date,
    movement_type: MovementType,
    amount: str,
    *,
    loan_id: str = "L-001",
) -> Movement:
    return Movement(
        loan_id=loan_id,
        event_date=event_date,
        movement_type=movement_type,
        amount=Decimal(amount),
    )


@pytest.mark.parametrize(
    ("basis", "expected_interest"),
    [
        (DayCountBasis.DAYS_360, Decimal("3.04")),
        (DayCountBasis.DAYS_365, Decimal("3.00")),
    ],
)
def test_june_whole_month_uses_loan_day_count_basis(
    basis: DayCountBasis,
    expected_interest: Decimal,
) -> None:
    result = calculate_loan(NaturalMonth(2025, 6), make_loan(basis=basis), ())

    assert result.actual_start == date(2025, 6, 1)
    assert result.actual_end == date(2025, 6, 30)
    assert result.interest_days == 30
    assert result.accrued_interest == expected_interest


@pytest.mark.parametrize(
    ("start", "end", "actual_start", "actual_end", "days"),
    [
        (
            date(2025, 1, 1),
            date(2025, 6, 15),
            date(2025, 6, 1),
            date(2025, 6, 15),
            15,
        ),
        (
            date(2025, 6, 10),
            date(2025, 12, 31),
            date(2025, 6, 11),
            date(2025, 6, 30),
            20,
        ),
        (
            date(2025, 6, 10),
            date(2025, 6, 20),
            date(2025, 6, 11),
            date(2025, 6, 20),
            10,
        ),
    ],
)
def test_start_date_is_exclusive_and_end_date_is_inclusive(
    start: date,
    end: date,
    actual_start: date,
    actual_end: date,
    days: int,
) -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(accrual_start=start, accrual_end=end),
        (),
    )

    assert result.actual_start == actual_start
    assert result.actual_end == actual_end
    assert result.interest_days == days
    assert sum(segment.days for segment in result.segments) == days


def test_non_intersecting_loan_period_is_rejected() -> None:
    with pytest.raises(DomainValidationError) as caught:
        calculate_loan(
            NaturalMonth(2025, 6),
            make_loan(
                accrual_start=date(2025, 7, 1),
                accrual_end=date(2025, 7, 31),
            ),
            (),
        )

    assert caught.value.errors[0].error_code is DomainErrorCode.LOAN_PERIOD_OUTSIDE_MONTH


def test_leap_february_accrues_all_29_days() -> None:
    result = calculate_loan(
        NaturalMonth(2024, 2),
        make_loan(
            accrual_start=date(2024, 1, 1),
            accrual_end=date(2024, 12, 31),
        ),
        (),
    )

    assert result.interest_days == 29
    assert result.segments[0].days == 29


@pytest.mark.parametrize(
    ("event_date", "expected_segments"),
    [
        (
            date(2025, 6, 1),
            [
                (date(2025, 6, 1), date(2025, 6, 1), Decimal("1000")),
                (date(2025, 6, 2), date(2025, 6, 30), Decimal("1500")),
            ],
        ),
        (
            date(2025, 6, 15),
            [
                (date(2025, 6, 1), date(2025, 6, 15), Decimal("1000")),
                (date(2025, 6, 16), date(2025, 6, 30), Decimal("1500")),
            ],
        ),
        (
            date(2025, 6, 30),
            [
                (date(2025, 6, 1), date(2025, 6, 30), Decimal("1000")),
            ],
        ),
    ],
)
def test_drawdown_changes_interest_principal_on_next_day(
    event_date: date,
    expected_segments: list[tuple[date, date, Decimal]],
) -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(),
        (movement(event_date, MovementType.DRAWDOWN, "500"),),
    )

    assert [
        (segment.start_date, segment.end_date, segment.principal)
        for segment in result.segments
    ] == expected_segments
    assert result.ending_principal == Decimal("1500")


@pytest.mark.parametrize(
    ("event_date", "expected_segments"),
    [
        (
            date(2025, 6, 1),
            [
                (date(2025, 6, 1), date(2025, 6, 1), Decimal("1000")),
                (date(2025, 6, 2), date(2025, 6, 30), Decimal("600")),
            ],
        ),
        (
            date(2025, 6, 15),
            [
                (date(2025, 6, 1), date(2025, 6, 15), Decimal("1000")),
                (date(2025, 6, 16), date(2025, 6, 30), Decimal("600")),
            ],
        ),
        (
            date(2025, 6, 30),
            [
                (date(2025, 6, 1), date(2025, 6, 30), Decimal("1000")),
            ],
        ),
    ],
)
def test_repayment_day_accrues_on_pre_repayment_principal(
    event_date: date,
    expected_segments: list[tuple[date, date, Decimal]],
) -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(),
        (movement(event_date, MovementType.REPAYMENT, "400"),),
    )

    assert [
        (segment.start_date, segment.end_date, segment.principal)
        for segment in result.segments
    ] == expected_segments
    assert result.ending_principal == Decimal("600")


def test_movements_before_and_after_partial_accrual_affect_only_relevant_values() -> None:
    loan = make_loan(
        accrual_start=date(2025, 6, 10),
        accrual_end=date(2025, 6, 20),
    )
    result = calculate_loan(
        NaturalMonth(2025, 6),
        loan,
        (
            movement(date(2025, 6, 5), MovementType.DRAWDOWN, "500"),
            movement(date(2025, 6, 25), MovementType.REPAYMENT, "200"),
        ),
    )

    assert len(result.segments) == 1
    assert result.segments[0].principal == Decimal("1500")
    assert result.segments[0].days == 10
    assert result.ending_principal == Decimal("1300")


def test_multiple_movement_dates_create_continuous_segments() -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(),
        (
            movement(date(2025, 6, 5), MovementType.DRAWDOWN, "100"),
            movement(date(2025, 6, 10), MovementType.REPAYMENT, "50"),
            movement(date(2025, 6, 20), MovementType.DRAWDOWN, "200"),
        ),
    )

    assert [
        (segment.start_date, segment.end_date, segment.principal)
        for segment in result.segments
    ] == [
        (date(2025, 6, 1), date(2025, 6, 5), Decimal("1000")),
        (date(2025, 6, 6), date(2025, 6, 10), Decimal("1100")),
        (date(2025, 6, 11), date(2025, 6, 20), Decimal("1050")),
        (date(2025, 6, 21), date(2025, 6, 30), Decimal("1250")),
    ]
    assert sum(segment.days for segment in result.segments) == result.interest_days
    for previous, current in zip(result.segments, result.segments[1:]):
        assert current.start_date == previous.end_date + timedelta(days=1)


def test_same_day_events_are_aggregated_and_input_order_independent() -> None:
    same_day_events = (
        movement(date(2025, 6, 15), MovementType.DRAWDOWN, "200"),
        movement(date(2025, 6, 15), MovementType.REPAYMENT, "50"),
        movement(date(2025, 6, 15), MovementType.DRAWDOWN, "25"),
        movement(date(2025, 6, 15), MovementType.REPAYMENT, "75"),
    )

    results = {
        calculate_loan(NaturalMonth(2025, 6), make_loan(), ordering)
        for ordering in permutations(same_day_events)
    }

    assert len(results) == 1
    only_result = results.pop()
    assert only_result.ending_principal == Decimal("1100")
    assert only_result.segments[0].ending_principal == Decimal("1100")


def test_high_precision_same_day_events_are_exact_for_every_permutation() -> None:
    same_day_events = (
        movement(date(2025, 6, 15), MovementType.DRAWDOWN, "1E+28"),
        movement(date(2025, 6, 15), MovementType.DRAWDOWN, "6"),
        movement(date(2025, 6, 15), MovementType.DRAWDOWN, "6"),
        movement(date(2025, 6, 15), MovementType.REPAYMENT, "1"),
        movement(date(2025, 6, 15), MovementType.REPAYMENT, "1"),
    )
    expected_principal = Decimal("10000000000000000000000000010")

    results = [
        calculate_loan(
            NaturalMonth(2025, 6),
            make_loan(principal="0", rate="0"),
            ordering,
        )
        for ordering in permutations(same_day_events)
    ]

    assert {result.ending_principal for result in results} == {
        expected_principal
    }
    assert {result.total_drawdowns for result in results} == {
        Decimal("10000000000000000000000000012")
    }
    assert {result.total_repayments for result in results} == {Decimal("2")}


def test_negative_principal_is_rejected_at_effective_event_boundary() -> None:
    with pytest.raises(DomainValidationError) as caught:
        calculate_loan(
            NaturalMonth(2025, 6),
            make_loan(),
            (movement(date(2025, 6, 10), MovementType.REPAYMENT, "1000.01"),),
        )

    error = caught.value.errors[0]
    assert error.error_code is DomainErrorCode.NEGATIVE_PRINCIPAL
    assert error.loan_id == "L-001"
    assert error.event_date == date(2025, 6, 10)


def test_rounding_occurs_once_after_unrounded_segment_sum() -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(
            principal="4",
            rate="0.365",
            accrual_start=date(2025, 6, 1),
            accrual_end=date(2025, 6, 2),
        ),
        (movement(date(2025, 6, 1), MovementType.REPAYMENT, "1"),),
    )

    assert [segment.unrounded_interest for segment in result.segments] == [
        Decimal("0.003"),
    ]
    assert result.unrounded_interest == Decimal("0.003")
    assert result.accrued_interest == Decimal("0.00")
    assert sum(
        segment.unrounded_interest.quantize(Decimal("0.01"))
        for segment in result.segments
    ) == Decimal("0.00")


def test_high_precision_segment_sum_is_exact_before_final_rounding() -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(
            principal="1E+25",
            rate="360",
            basis=DayCountBasis.DAYS_360,
            accrual_start=date(2025, 6, 1),
            accrual_end=date(2025, 6, 2),
        ),
        (
            movement(
                date(2025, 6, 1),
                MovementType.REPAYMENT,
                "9999999999999999999999999.995",
            ),
        ),
    )

    assert [segment.unrounded_interest for segment in result.segments] == [
        Decimal("0.005"),
    ]
    assert result.unrounded_interest == Decimal("0.005")
    assert result.accrued_interest == Decimal("0.01")


@pytest.mark.parametrize(
    ("capitalized", "expected_capitalized", "expected_expensed"),
    [
        (True, Decimal("3.00"), Decimal("0.00")),
        (False, Decimal("0.00"), Decimal("3.00")),
    ],
)
def test_rounded_interest_is_classified_without_residual(
    capitalized: bool,
    expected_capitalized: Decimal,
    expected_expensed: Decimal,
) -> None:
    result = calculate_loan(
        NaturalMonth(2025, 6),
        make_loan(capitalized=capitalized),
        (),
    )

    assert result.capitalized_interest == expected_capitalized
    assert result.expensed_interest == expected_expensed
    assert (
        result.capitalized_interest + result.expensed_interest
        == result.accrued_interest
    )


def test_calculation_modules_contain_no_float_literals_or_conversions() -> None:
    domain_root = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "loan_interest_accrual"
        / "domain"
    )

    for module_name in ("calculator.py", "reconciliation.py"):
        tree = ast.parse((domain_root / module_name).read_text(encoding="utf-8"))
        float_literals = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, float)
        ]
        float_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "float"
        ]

        assert float_literals == []
        assert float_calls == []
