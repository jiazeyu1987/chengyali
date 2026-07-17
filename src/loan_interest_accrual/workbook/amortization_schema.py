from __future__ import annotations

from dataclasses import dataclass

from loan_interest_accrual.domain import AmortizationAsset, NaturalMonth

from .schema import WorkbookError


AMORTIZATION_SHEET = "摊销输入"
AMORTIZATION_HEADERS = (
    "一级分类",
    "名称",
    "对应费用",
    "原值",
    "残值",
    "开始摊销月",
    "入账月",
    "摊销期限/月",
)
AMORTIZATION_RESULT_HEADERS = (
    "计提月份",
    "序号",
    *AMORTIZATION_HEADERS,
    "月摊销额",
    "累计摊销月数（含本期）",
    "累计摊销金额（含本期）",
    "当期应摊销金额",
    "本期实际摊销金额",
    "差异",
    "期末净值",
)
AMOUNT_NUMBER_FORMAT = '#,##0.00;[Red](#,##0.00);-'
DATE_NUMBER_FORMAT = "yyyy-mm-dd"
MONTH_COUNT_NUMBER_FORMAT = '#,##0;[Red](#,##0);-'
MAX_AMORTIZATION_ROWS = 10_000


@dataclass(frozen=True, slots=True)
class AmortizationWorkbookInput:
    period: NaturalMonth
    assets: tuple[AmortizationAsset, ...]


@dataclass(frozen=True, slots=True)
class AmortizationWorkbookImportResult:
    source_bytes: bytes
    source_sha256: str
    calculable_input: AmortizationWorkbookInput | None
    errors: tuple[WorkbookError, ...]
