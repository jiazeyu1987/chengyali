from collections import defaultdict
from typing import Iterable

from .decimal_math import ZERO, exact_difference, exact_sum
from .models import (
    CapitalizationSummary,
    CompanySummary,
    LoanResult,
    ReconciliationCheck,
)

def summarize_companies(
    loan_results: Iterable[LoanResult],
) -> tuple[CompanySummary, ...]:
    grouped: dict[str, list[LoanResult]] = defaultdict(list)
    for result in loan_results:
        grouped[result.loan.company_name].append(result)

    summaries = []
    for company_name in sorted(grouped):
        results = grouped[company_name]
        summaries.append(
            CompanySummary(
                company_name=company_name,
                loan_count=len(results),
                opening_principal=exact_sum(
                    result.loan.opening_principal for result in results
                ),
                total_drawdowns=exact_sum(
                    result.total_drawdowns for result in results
                ),
                total_repayments=exact_sum(
                    result.total_repayments for result in results
                ),
                ending_principal=exact_sum(
                    result.ending_principal for result in results
                ),
                accrued_interest=exact_sum(
                    result.accrued_interest for result in results
                ),
                capitalized_interest=exact_sum(
                    result.capitalized_interest for result in results
                ),
                expensed_interest=exact_sum(
                    result.expensed_interest for result in results
                ),
            )
        )
    return tuple(summaries)


def summarize_capitalization(
    loan_results: Iterable[LoanResult],
) -> tuple[CapitalizationSummary, ...]:
    grouped: dict[str, list[LoanResult]] = defaultdict(list)
    for result in loan_results:
        if result.loan.capitalize_interest:
            grouped[result.loan.company_name].append(result)

    summaries = []
    for company_name in sorted(grouped):
        results = grouped[company_name]
        summaries.append(
            CapitalizationSummary(
                company_name=company_name,
                capitalized_loan_count=len(results),
                ending_principal=exact_sum(
                    result.ending_principal for result in results
                ),
                capitalized_interest=exact_sum(
                    result.capitalized_interest for result in results
                ),
            )
        )
    return tuple(summaries)


def build_reconciliation_checks(
    loan_results: tuple[LoanResult, ...],
    company_summaries: tuple[CompanySummary, ...],
    capitalization_summaries: tuple[CapitalizationSummary, ...],
) -> tuple[ReconciliationCheck, ...]:
    principal_difference = exact_sum(
        exact_difference(
            exact_difference(
                exact_sum(
                    (
                        result.loan.opening_principal,
                        result.total_drawdowns,
                    )
                ),
                result.total_repayments,
            ),
            result.ending_principal,
        ).copy_abs()
        for result in loan_results
    )
    classification_difference = exact_sum(
        exact_difference(
            exact_sum(
                (
                    result.capitalized_interest,
                    result.expensed_interest,
                )
            ),
            result.accrued_interest,
        ).copy_abs()
        for result in loan_results
    )
    company_summary_interest = exact_sum(
        summary.accrued_interest for summary in company_summaries
    )
    loan_interest = exact_sum(
        result.accrued_interest for result in loan_results
    )
    capitalization_summary_interest = exact_sum(
        summary.capitalized_interest
        for summary in capitalization_summaries
    )
    capitalized_loan_interest = exact_sum(
        result.capitalized_interest
        for result in loan_results
        if result.loan.capitalize_interest
    )

    return (
        ReconciliationCheck(
            name="loan_principal_rollforward",
            passed=principal_difference == ZERO,
            expected=ZERO,
            actual=principal_difference,
        ),
        ReconciliationCheck(
            name="loan_interest_classification",
            passed=classification_difference == ZERO,
            expected=ZERO,
            actual=classification_difference,
        ),
        ReconciliationCheck(
            name="company_interest_summary",
            passed=company_summary_interest == loan_interest,
            expected=loan_interest,
            actual=company_summary_interest,
        ),
        ReconciliationCheck(
            name="capitalization_interest_summary",
            passed=capitalization_summary_interest == capitalized_loan_interest,
            expected=capitalized_loan_interest,
            actual=capitalization_summary_interest,
        ),
    )
