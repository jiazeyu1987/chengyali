from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from loan_interest_accrual.domain import AmortizationPortfolio
from loan_interest_accrual.domain.decimal_math import exact_sum

from .results import ApplicationError


@dataclass(frozen=True, slots=True)
class AmortizationPreviewRow:
    sequence: int
    primary_category: str
    name: str
    expense_category: str
    original_value: Decimal
    residual_value: Decimal
    amortization_start: date
    booking_month: date
    amortization_term_months: int
    monthly_amortization: Decimal
    cumulative_months: int
    cumulative_amortization: Decimal
    current_required_amortization: Decimal | None
    current_actual_amortization: Decimal | None
    difference: Decimal | None
    ending_net_value: Decimal | None
    fully_amortized: bool


@dataclass(frozen=True, slots=True)
class AmortizationCheck:
    name: str
    display_name: str
    passed: bool
    expected: Decimal | str
    actual: Decimal | str

    @property
    def status(self) -> str:
        return "通过" if self.passed else "失败"


@dataclass(frozen=True, slots=True)
class AmortizationSummary:
    asset_count: int
    original_value: Decimal
    monthly_amortization: Decimal
    cumulative_amortization: Decimal
    current_required_amortization: Decimal
    current_actual_amortization: Decimal
    ending_net_value: Decimal


@dataclass(frozen=True, slots=True)
class AmortizationCalculationResult:
    source_filename: str
    source_bytes: bytes
    source_sha256: str
    source_size_bytes: int
    period: object
    portfolio: AmortizationPortfolio
    rows: tuple[AmortizationPreviewRow, ...]
    summary: AmortizationSummary
    checks: tuple[AmortizationCheck, ...]


@dataclass(frozen=True, slots=True)
class AmortizationCalculationServiceResult:
    source_sha256: str
    errors: tuple[ApplicationError, ...]
    calculation: AmortizationCalculationResult | None


@dataclass(frozen=True, slots=True)
class AmortizationExportedWorkbook:
    filename: str
    media_type: str
    workbook_bytes: bytes
    calculation: AmortizationCalculationResult


@dataclass(frozen=True, slots=True)
class AmortizationExportServiceResult:
    source_sha256: str
    errors: tuple[ApplicationError, ...]
    output: AmortizationExportedWorkbook | None


def build_amortization_calculation_result(
    *,
    source_filename: str,
    source_bytes: bytes,
    source_sha256: str,
    portfolio: AmortizationPortfolio,
) -> AmortizationCalculationResult:
    rows = tuple(
        AmortizationPreviewRow(
            sequence=result.sequence,
            primary_category=result.asset.primary_category,
            name=result.asset.name,
            expense_category=result.asset.expense_category,
            original_value=result.asset.original_value,
            residual_value=result.asset.residual_value,
            amortization_start=result.asset.amortization_start,
            booking_month=result.asset.booking_month,
            amortization_term_months=result.asset.amortization_term_months,
            monthly_amortization=result.monthly_amortization,
            cumulative_months=result.cumulative_months,
            cumulative_amortization=result.cumulative_amortization,
            current_required_amortization=result.current_required_amortization,
            current_actual_amortization=result.current_actual_amortization,
            difference=result.difference,
            ending_net_value=result.ending_net_value,
            fully_amortized=result.fully_amortized,
        )
        for result in portfolio.results
    )
    summary = AmortizationSummary(
        asset_count=len(rows),
        original_value=exact_sum(row.original_value for row in rows),
        monthly_amortization=exact_sum(row.monthly_amortization for row in rows),
        cumulative_amortization=exact_sum(row.cumulative_amortization for row in rows),
        current_required_amortization=exact_sum(
            row.current_required_amortization
            for row in rows
            if row.current_required_amortization is not None
        ),
        current_actual_amortization=exact_sum(
            row.current_actual_amortization
            for row in rows
            if row.current_actual_amortization is not None
        ),
        ending_net_value=exact_sum(
            row.ending_net_value for row in rows if row.ending_net_value is not None
        ),
    )
    months_ok = all(
        1 <= row.cumulative_months <= row.amortization_term_months for row in rows
    )
    completed_ok = all(
        not row.fully_amortized or row.cumulative_amortization == row.original_value
        for row in rows
    )
    incomplete_ok = all(
        row.fully_amortized
        or row.cumulative_amortization
        == row.monthly_amortization * Decimal(row.cumulative_months)
        for row in rows
    )
    checks = (
        AmortizationCheck(
            "cumulative_month_cap",
            "累计摊销月数不超过摊销期限",
            months_ok,
            "全部不超过期限",
            "全部不超过期限" if months_ok else "存在超期记录",
        ),
        AmortizationCheck(
            "fully_amortized_to_original_value",
            "已摊满资产累计金额等于原值",
            completed_ok,
            "已摊满累计金额=原值",
            "通过" if completed_ok else "不一致",
        ),
        AmortizationCheck(
            "active_asset_formula",
            "未摊满资产累计金额公式勾稽",
            incomplete_ok,
            "月摊销额×累计月数",
            "通过" if incomplete_ok else "不一致",
        ),
    )
    return AmortizationCalculationResult(
        source_filename=source_filename,
        source_bytes=source_bytes,
        source_sha256=source_sha256,
        source_size_bytes=len(source_bytes),
        period=portfolio.period,
        portfolio=portfolio,
        rows=rows,
        summary=summary,
        checks=checks,
    )
