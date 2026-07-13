from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from loan_interest_accrual.domain import (
    DayCountBasis,
    DomainErrorCode,
    DomainValidationError,
    Loan,
    Movement,
    MovementType,
    NaturalMonth,
    calculate_portfolio,
)


def make_loan(
    loan_id: str = "L-001",
    *,
    company_name: str = "Company A",
    contract_number: str = "C-001",
    day_count_basis: DayCountBasis = DayCountBasis.DAYS_365,
) -> Loan:
    return Loan(
        loan_id=loan_id,
        company_name=company_name,
        contract_number=contract_number,
        bank_name="Bank A",
        opening_principal=Decimal("1000"),
        annual_rate=Decimal("0.0365"),
        day_count_basis=day_count_basis,
        accrual_start=date(2025, 1, 1),
        accrual_end=date(2025, 12, 31),
        capitalize_interest=False,
    )


def test_domain_inputs_are_immutable() -> None:
    loan = make_loan()
    movement = Movement(
        loan_id=loan.loan_id,
        event_date=date(2025, 6, 15),
        movement_type=MovementType.DRAWDOWN,
        amount=Decimal("100"),
    )

    with pytest.raises(FrozenInstanceError):
        loan.opening_principal = Decimal("2000")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        movement.amount = Decimal("200")  # type: ignore[misc]


@pytest.mark.parametrize("basis", [360, 365, 364, "365", Decimal("365")])
def test_day_count_basis_requires_approved_enum_without_coercion(
    basis: object,
) -> None:
    with pytest.raises(DomainValidationError) as caught:
        Loan(
            loan_id="L-001",
            company_name="Company A",
            contract_number="C-001",
            bank_name="Bank A",
            opening_principal=Decimal("1000"),
            annual_rate=Decimal("0.0365"),
            day_count_basis=basis,  # type: ignore[arg-type]
            accrual_start=date(2025, 1, 1),
            accrual_end=date(2025, 12, 31),
            capitalize_interest=False,
        )

    assert caught.value.errors[0].error_code is DomainErrorCode.DAY_COUNT_BASIS_INVALID


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("opening_principal", 1000),
        ("opening_principal", 1000.0),
        ("annual_rate", 0.0365),
        ("annual_rate", "0.0365"),
    ],
)
def test_money_and_rate_fields_require_decimal(
    field: str,
    value: object,
) -> None:
    arguments = {
        "loan_id": "L-001",
        "company_name": "Company A",
        "contract_number": "C-001",
        "bank_name": "Bank A",
        "opening_principal": Decimal("1000"),
        "annual_rate": Decimal("0.0365"),
        "day_count_basis": DayCountBasis.DAYS_365,
        "accrual_start": date(2025, 1, 1),
        "accrual_end": date(2025, 12, 31),
        "capitalize_interest": False,
    }
    arguments[field] = value

    with pytest.raises(DomainValidationError) as caught:
        Loan(**arguments)  # type: ignore[arg-type]

    assert caught.value.errors[0].error_code is DomainErrorCode.DECIMAL_REQUIRED


def test_portfolio_rejects_duplicate_loan_identity() -> None:
    period = NaturalMonth(2025, 6)
    loans = (
        make_loan("L-001", company_name="Company A", contract_number="C-001"),
        make_loan("L-001", company_name="Company B", contract_number="C-999"),
    )

    with pytest.raises(DomainValidationError) as caught:
        calculate_portfolio(period, loans, ())

    assert caught.value.errors[0].error_code is DomainErrorCode.LOAN_ID_DUPLICATE
    assert caught.value.errors[0].loan_id == "L-001"


def test_loans_with_matching_display_fields_remain_isolated_by_id() -> None:
    period = NaturalMonth(2025, 6)
    loans = (
        make_loan("L-001", company_name="Same Company", contract_number="Same Contract"),
        make_loan("L-002", company_name="Same Company", contract_number="Same Contract"),
    )
    movements = (
        Movement(
            loan_id="L-002",
            event_date=date(2025, 6, 1),
            movement_type=MovementType.DRAWDOWN,
            amount=Decimal("500"),
        ),
    )

    result = calculate_portfolio(period, loans, movements)

    by_id = {loan_result.loan.loan_id: loan_result for loan_result in result.loan_results}
    assert by_id["L-001"].ending_principal == Decimal("1000")
    assert by_id["L-002"].ending_principal == Decimal("1500")


def test_empty_portfolio_still_rejects_invalid_period_type() -> None:
    with pytest.raises(DomainValidationError) as caught:
        calculate_portfolio("2025-06", (), ())  # type: ignore[arg-type]

    assert caught.value.errors[0].error_code is DomainErrorCode.VALUE_TYPE_INVALID
    assert caught.value.errors[0].column_or_field == "period"
