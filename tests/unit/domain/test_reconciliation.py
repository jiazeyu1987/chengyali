from datetime import date
from decimal import Decimal

from loan_interest_accrual.domain import (
    DayCountBasis,
    Loan,
    NaturalMonth,
    calculate_portfolio,
)


def make_precision_loan(
    loan_id: str,
    company_name: str,
    *,
    capitalized: bool,
    principal: str = "6",
) -> Loan:
    return Loan(
        loan_id=loan_id,
        company_name=company_name,
        contract_number=f"C-{loan_id}",
        bank_name="Bank A",
        opening_principal=Decimal(principal),
        annual_rate=Decimal("0.365"),
        day_count_basis=DayCountBasis.DAYS_365,
        accrual_start=date(2025, 5, 31),
        accrual_end=date(2025, 6, 1),
        capitalize_interest=capitalized,
    )


def test_company_and_capitalization_summaries_use_rounded_loan_results() -> None:
    portfolio = calculate_portfolio(
        NaturalMonth(2025, 6),
        (
            make_precision_loan("L-001", "Company A", capitalized=True),
            make_precision_loan("L-002", "Company A", capitalized=False),
            make_precision_loan("L-003", "Company B", capitalized=True),
        ),
        (),
    )

    result_by_id = {
        result.loan.loan_id: result for result in portfolio.loan_results
    }
    assert result_by_id["L-001"].unrounded_interest == Decimal("0.006")
    assert result_by_id["L-001"].accrued_interest == Decimal("0.01")
    assert result_by_id["L-002"].accrued_interest == Decimal("0.01")

    company_by_name = {
        summary.company_name: summary for summary in portfolio.company_summaries
    }
    company_a = company_by_name["Company A"]
    assert company_a.loan_count == 2
    assert company_a.accrued_interest == Decimal("0.02")
    assert company_a.capitalized_interest == Decimal("0.01")
    assert company_a.expensed_interest == Decimal("0.01")
    assert (
        company_a.capitalized_interest + company_a.expensed_interest
        == company_a.accrued_interest
    )

    capitalization_by_name = {
        summary.company_name: summary
        for summary in portfolio.capitalization_summaries
    }
    assert capitalization_by_name["Company A"].capitalized_loan_count == 1
    assert capitalization_by_name["Company A"].capitalized_interest == Decimal(
        "0.01"
    )
    assert capitalization_by_name["Company B"].capitalized_interest == Decimal(
        "0.01"
    )
    assert portfolio.total_capitalized_interest == Decimal("0.02")


def test_portfolio_reconciliation_checks_are_explicit_and_passing() -> None:
    portfolio = calculate_portfolio(
        NaturalMonth(2025, 6),
        (
            make_precision_loan("L-001", "Company A", capitalized=True),
            make_precision_loan("L-002", "Company A", capitalized=False),
        ),
        (),
    )

    assert portfolio.checks
    assert all(check.passed for check in portfolio.checks)
    assert {check.name for check in portfolio.checks} == {
        "loan_principal_rollforward",
        "loan_interest_classification",
        "company_interest_summary",
        "capitalization_interest_summary",
    }


def test_high_precision_summaries_and_checks_preserve_exact_totals() -> None:
    portfolio = calculate_portfolio(
        NaturalMonth(2025, 6),
        (
            make_precision_loan(
                "L-001",
                "Company A",
                capitalized=True,
                principal="1E+28",
            ),
            make_precision_loan(
                "L-002",
                "Company A",
                capitalized=True,
                principal="6",
            ),
        ),
        (),
    )

    company = portfolio.company_summaries[0]
    capitalization = portfolio.capitalization_summaries[0]
    assert company.opening_principal == Decimal(
        "10000000000000000000000000006"
    )
    assert company.ending_principal == Decimal(
        "10000000000000000000000000006"
    )
    assert company.accrued_interest == Decimal(
        "10000000000000000000000000.01"
    )
    assert capitalization.ending_principal == Decimal(
        "10000000000000000000000000006"
    )
    assert capitalization.capitalized_interest == Decimal(
        "10000000000000000000000000.01"
    )
    assert portfolio.total_capitalized_interest == Decimal(
        "10000000000000000000000000.01"
    )
    assert all(check.passed for check in portfolio.checks)
