from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from loan_interest_accrual.domain import PortfolioResult


PASS_STATUS = "通过"
FAIL_STATUS = "失败"


@dataclass(frozen=True, slots=True)
class ApplicationError:
    error_code: str
    sheet: str | None
    row: int | None
    column_or_field: str
    message: str


@dataclass(frozen=True, slots=True)
class LoanPreviewRow:
    calculation_month: str
    loan_id: str
    company_name: str
    contract_number: str
    bank_name: str
    capitalize_interest: bool
    opening_principal: Decimal
    total_drawdowns: Decimal
    total_repayments: Decimal
    ending_principal: Decimal
    interest_days: int
    accrued_interest: Decimal
    capitalized_interest: Decimal
    expensed_interest: Decimal


@dataclass(frozen=True, slots=True)
class SegmentDetailRow:
    calculation_month: str
    loan_id: str
    sequence: int
    start_date: date
    end_date: date
    days: int
    principal: Decimal
    annual_rate: Decimal
    day_count_basis: int
    unrounded_interest: Decimal
    ending_principal: Decimal
    trigger_note: str


@dataclass(frozen=True, slots=True)
class CompanySummaryRow:
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
class CapitalizationSummaryRow:
    company_name: str
    capitalized_loan_count: int
    ending_principal: Decimal
    capitalized_interest: Decimal


@dataclass(frozen=True, slots=True)
class ApplicationCheck:
    name: str
    display_name: str
    passed: bool
    expected: Decimal | str
    actual: Decimal | str

    @property
    def status(self) -> str:
        return PASS_STATUS if self.passed else FAIL_STATUS


@dataclass(frozen=True, slots=True)
class CalculationResult:
    source_filename: str
    source_bytes: bytes
    source_sha256: str
    source_size_bytes: int
    period: object
    portfolio_result: PortfolioResult
    loan_rows: tuple[LoanPreviewRow, ...]
    segment_rows: tuple[SegmentDetailRow, ...]
    company_summary_rows: tuple[CompanySummaryRow, ...]
    capitalization_summary_rows: tuple[CapitalizationSummaryRow, ...]
    checks: tuple[ApplicationCheck, ...]


@dataclass(frozen=True, slots=True)
class CalculationServiceResult:
    source_sha256: str
    errors: tuple[ApplicationError, ...]
    calculation: CalculationResult | None


@dataclass(frozen=True, slots=True)
class ExportedWorkbook:
    filename: str
    media_type: str
    workbook_bytes: bytes
    calculation: CalculationResult


@dataclass(frozen=True, slots=True)
class ExportServiceResult:
    source_sha256: str
    errors: tuple[ApplicationError, ...]
    output: ExportedWorkbook | None


def calculation_month(period: object) -> str:
    return f"{period.year:04d}-{period.month:02d}"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _segment_trigger_note(trigger_date: date | None) -> str:
    if trigger_date is None:
        return "自然期间结束"
    return f"事件日 {trigger_date.isoformat()}，次日生效"


def _base_passed_checks() -> tuple[ApplicationCheck, ...]:
    return (
        ApplicationCheck(
            "input_workbook_structure",
            "输入工作表结构校验",
            True,
            PASS_STATUS,
            PASS_STATUS,
        ),
        ApplicationCheck(
            "loan_id_and_movement_linkage",
            "主键唯一性和资金变动关联校验",
            True,
            PASS_STATUS,
            PASS_STATUS,
        ),
        ApplicationCheck(
            "field_type_and_enum",
            "字段类型和枚举校验",
            True,
            PASS_STATUS,
            PASS_STATUS,
        ),
        ApplicationCheck(
            "date_range",
            "日期区间校验",
            True,
            PASS_STATUS,
            PASS_STATUS,
        ),
        ApplicationCheck(
            "non_negative_principal",
            "本金非负校验",
            True,
            PASS_STATUS,
            PASS_STATUS,
        ),
    )


def _domain_check_display_name(name: str) -> str:
    names = {
        "loan_principal_rollforward": "逐笔本金滚动校验",
        "loan_interest_classification": "资本化加费用化与计提利息勾稽",
        "company_interest_summary": "公司汇总与逐笔结果勾稽",
        "capitalization_interest_summary": "资本化汇总与逐笔结果勾稽",
    }
    return names.get(name, name)


def _segment_interest_check(portfolio_result: PortfolioResult) -> ApplicationCheck:
    differences = []
    for result in portfolio_result.loan_results:
        segment_total = sum(
            (segment.unrounded_interest for segment in result.segments),
            Decimal("0"),
        )
        differences.append((_money(segment_total) - result.accrued_interest).copy_abs())
    difference = sum(differences, Decimal("0"))
    return ApplicationCheck(
        "segment_interest_to_loan_result",
        "分段利息与逐笔结果勾稽",
        difference == Decimal("0"),
        Decimal("0"),
        difference,
    )


def _application_checks(
    portfolio_result: PortfolioResult,
) -> tuple[ApplicationCheck, ...]:
    domain_checks = tuple(
        ApplicationCheck(
            check.name,
            _domain_check_display_name(check.name),
            check.passed,
            check.expected,
            check.actual,
        )
        for check in portfolio_result.checks
    )
    return (
        _base_passed_checks()
        + (_segment_interest_check(portfolio_result),)
        + domain_checks
    )


def build_calculation_result(
    *,
    source_filename: str,
    source_bytes: bytes,
    source_sha256: str,
    portfolio_result: PortfolioResult,
) -> CalculationResult:
    month = calculation_month(portfolio_result.period)
    loan_rows = tuple(
        LoanPreviewRow(
            calculation_month=month,
            loan_id=result.loan.loan_id,
            company_name=result.loan.company_name,
            contract_number=result.loan.contract_number,
            bank_name=result.loan.bank_name,
            capitalize_interest=result.loan.capitalize_interest,
            opening_principal=result.loan.opening_principal,
            total_drawdowns=result.total_drawdowns,
            total_repayments=result.total_repayments,
            ending_principal=result.ending_principal,
            interest_days=result.interest_days,
            accrued_interest=result.accrued_interest,
            capitalized_interest=result.capitalized_interest,
            expensed_interest=result.expensed_interest,
        )
        for result in portfolio_result.loan_results
    )
    segment_rows = tuple(
        SegmentDetailRow(
            calculation_month=month,
            loan_id=segment.loan_id,
            sequence=segment.sequence,
            start_date=segment.start_date,
            end_date=segment.end_date,
            days=segment.days,
            principal=segment.principal,
            annual_rate=segment.annual_rate,
            day_count_basis=segment.day_count_basis.value,
            unrounded_interest=segment.unrounded_interest,
            ending_principal=segment.ending_principal,
            trigger_note=_segment_trigger_note(segment.trigger_date),
        )
        for result in portfolio_result.loan_results
        for segment in result.segments
    )
    company_rows = tuple(
        CompanySummaryRow(
            company_name=summary.company_name,
            loan_count=summary.loan_count,
            opening_principal=summary.opening_principal,
            total_drawdowns=summary.total_drawdowns,
            total_repayments=summary.total_repayments,
            ending_principal=summary.ending_principal,
            accrued_interest=summary.accrued_interest,
            capitalized_interest=summary.capitalized_interest,
            expensed_interest=summary.expensed_interest,
        )
        for summary in portfolio_result.company_summaries
    )
    capitalization_rows = tuple(
        CapitalizationSummaryRow(
            company_name=summary.company_name,
            capitalized_loan_count=summary.capitalized_loan_count,
            ending_principal=summary.ending_principal,
            capitalized_interest=summary.capitalized_interest,
        )
        for summary in portfolio_result.capitalization_summaries
    )
    return CalculationResult(
        source_filename=source_filename,
        source_bytes=source_bytes,
        source_sha256=source_sha256,
        source_size_bytes=len(source_bytes),
        period=portfolio_result.period,
        portfolio_result=portfolio_result,
        loan_rows=loan_rows,
        segment_rows=segment_rows,
        company_summary_rows=company_rows,
        capitalization_summary_rows=capitalization_rows,
        checks=_application_checks(portfolio_result),
    )
