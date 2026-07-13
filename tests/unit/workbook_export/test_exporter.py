from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from loan_interest_accrual.application import calculate_submission
from loan_interest_accrual.application.results import ApplicationCheck
from loan_interest_accrual.domain import NaturalMonth
from loan_interest_accrual.workbook.export_schema import (
    CAPITALIZATION_SUMMARY_HEADERS,
    CAPITALIZATION_SUMMARY_SHEET,
    CHECK_HEADERS,
    CHECK_SHEET,
    COMPANY_SUMMARY_HEADERS,
    COMPANY_SUMMARY_SHEET,
    EXPORT_SHEET_NAMES,
    PARAMETER_HEADERS,
    PARAMETER_SHEET,
    RESULT_HEADERS,
    RESULT_SHEET,
    SEGMENT_HEADERS,
    SEGMENT_SHEET,
)
from loan_interest_accrual.workbook.exporter import (
    ExportInvariantError,
    export_calculation_workbook,
)

from tests.fixtures.export.standard_workbooks import (
    loan_row,
    movement_row,
    workbook_bytes,
)


PERIOD = NaturalMonth(2025, 6)
GENERATED_AT = datetime(2026, 7, 10, 12, 30, 0, tzinfo=timezone.utc)


def _decimal(value: object) -> Decimal:
    return value if type(value) is Decimal else Decimal(str(value))


def _money(value: object) -> Decimal:
    return _decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rows(sheet) -> list[dict[str, object]]:
    headers = [cell.value for cell in sheet[1]]
    return [
        dict(zip(headers, values, strict=True))
        for values in sheet.iter_rows(min_row=2, values_only=True)
    ]


def _calculation():
    payload = workbook_bytes(
        loans=[
            loan_row(
                "L-CAP-A",
                company="甲公司",
                contract="HT-A",
                principal=1000000,
                rate=0.0365,
                basis=365,
                capitalized="是",
            ),
            loan_row(
                "L-EXP-A",
                company="甲公司",
                contract="HT-B",
                principal=2000000,
                rate=0.036,
                basis=360,
                capitalized="否",
            ),
            loan_row(
                "L-CAP-B",
                company="乙公司",
                contract="HT-C",
                principal=500000,
                rate=0.073,
                basis=365,
                capitalized="是",
            ),
        ],
        movements=[
            movement_row("L-CAP-A", date(2025, 6, 15), "放款", 100000),
            movement_row("L-CAP-A", date(2025, 6, 20), "还本", 50000),
            movement_row("L-EXP-A", date(2025, 6, 30), "放款", 10000),
        ],
    )
    result = calculate_submission("source.xlsx", payload, PERIOD)
    assert result.errors == ()
    assert result.calculation is not None
    return payload, result.calculation


def test_export_workbook_has_exact_sheets_fixed_values_and_package_is_clean() -> None:
    source_bytes, calculation = _calculation()
    output = export_calculation_workbook(
        calculation,
        generated_at=GENERATED_AT,
    )

    assert output != source_bytes
    workbook = load_workbook(BytesIO(output), data_only=False)
    data_only_workbook = load_workbook(BytesIO(output), data_only=True)
    try:
        assert workbook.sheetnames == list(EXPORT_SHEET_NAMES)
        assert data_only_workbook.sheetnames == list(EXPORT_SHEET_NAMES)
        assert [cell.value for cell in workbook[RESULT_SHEET][1]] == list(RESULT_HEADERS)
        assert [cell.value for cell in workbook[SEGMENT_SHEET][1]] == list(SEGMENT_HEADERS)
        assert [cell.value for cell in workbook[COMPANY_SUMMARY_SHEET][1]] == list(
            COMPANY_SUMMARY_HEADERS
        )
        assert [cell.value for cell in workbook[CAPITALIZATION_SUMMARY_SHEET][1]] == list(
            CAPITALIZATION_SUMMARY_HEADERS
        )
        assert [cell.value for cell in workbook[CHECK_SHEET][1]] == list(CHECK_HEADERS)
        assert [cell.value for cell in workbook[PARAMETER_SHEET][1]] == list(
            PARAMETER_HEADERS
        )

        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    assert cell.data_type != "f"

        assert data_only_workbook[RESULT_SHEET]["A2"].value == "2025-06"
    finally:
        workbook.close()
        data_only_workbook.close()

    with ZipFile(BytesIO(output)) as package:
        names = package.namelist()
        assert not any("vbaProject" in name for name in names)
        assert not any("externalLinks" in name for name in names)
        assert not any("connections" in name for name in names)
        for name in names:
            if not (name.endswith(".xml") or name.endswith(".rels")):
                continue
            content = package.read(name).decode("utf-8", errors="ignore")
            assert "<f>" not in content
            assert "TargetMode=\"External\"" not in content
            assert "source.xlsx" not in content
            assert "贷款主表" not in content


def test_export_rows_summaries_checks_and_parameters_reconcile() -> None:
    _, calculation = _calculation()
    output = export_calculation_workbook(
        calculation,
        generated_at=GENERATED_AT,
    )

    workbook = load_workbook(BytesIO(output), data_only=True)
    try:
        result_rows = _rows(workbook[RESULT_SHEET])
        segment_rows = _rows(workbook[SEGMENT_SHEET])
        company_rows = _rows(workbook[COMPANY_SUMMARY_SHEET])
        capitalization_rows = _rows(workbook[CAPITALIZATION_SUMMARY_SHEET])
        check_rows = _rows(workbook[CHECK_SHEET])
        parameter_rows = _rows(workbook[PARAMETER_SHEET])
    finally:
        workbook.close()

    assert {row["贷款ID"] for row in result_rows} == {
        "L-CAP-A",
        "L-EXP-A",
        "L-CAP-B",
    }
    assert len(result_rows) == 3

    segment_interest_by_loan: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in segment_rows:
        segment_interest_by_loan[row["贷款ID"]] += _decimal(
            row["未舍入分段利息（元）"]
        )
    for row in result_rows:
        assert _money(segment_interest_by_loan[row["贷款ID"]]) == _money(
            row["当月计提利息（元）"]
        )

    result_by_company: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in result_rows:
        result_by_company[row["公司名称"]].append(row)
    for row in company_rows:
        expected_rows = result_by_company[row["公司名称"]]
        assert row["贷款笔数"] == len(expected_rows)
        assert _money(row["期初本金合计（元）"]) == sum(
            _money(item["期初本金（元）"]) for item in expected_rows
        )
        assert _money(row["当月放款合计（元）"]) == sum(
            _money(item["当月放款合计（元）"]) for item in expected_rows
        )
        assert _money(row["当月还本合计（元）"]) == sum(
            _money(item["当月还本合计（元）"]) for item in expected_rows
        )
        assert _money(row["月末本金合计（元）"]) == sum(
            _money(item["月末本金（元）"]) for item in expected_rows
        )
        assert _money(row["当月计提利息合计（元）"]) == sum(
            _money(item["当月计提利息（元）"]) for item in expected_rows
        )
        assert _money(row["资本化利息合计（元）"]) == sum(
            _money(item["资本化利息（元）"]) for item in expected_rows
        )
        assert _money(row["费用化利息合计（元）"]) == sum(
            _money(item["费用化利息（元）"]) for item in expected_rows
        )

    capitalized_rows = [
        row for row in result_rows if row["是否资本化"] == "是"
    ]
    capitalized_by_company: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in capitalized_rows:
        capitalized_by_company[row["公司名称"]].append(row)
    total_row = next(row for row in capitalization_rows if row["公司名称"] == "合计")
    company_cap_rows = [
        row for row in capitalization_rows if row["公司名称"] != "合计"
    ]
    for row in company_cap_rows:
        expected_rows = capitalized_by_company[row["公司名称"]]
        assert row["资本化贷款笔数"] == len(expected_rows)
        assert _money(row["资本化计息本金或月末本金汇总（元）"]) == sum(
            _money(item["月末本金（元）"]) for item in expected_rows
        )
        assert _money(row["资本化利息合计（元）"]) == sum(
            _money(item["资本化利息（元）"]) for item in expected_rows
        )
    assert _money(total_row["资本化利息合计（元）"]) == sum(
        _money(row["资本化利息（元）"]) for row in capitalized_rows
    )

    assert all(row["状态"] == "通过" for row in check_rows)
    assert {
        "输入工作表结构校验",
        "分段利息与逐笔结果勾稽",
        "公司汇总与逐笔结果勾稽",
    } <= {row["校验项"] for row in check_rows}

    parameters = {row["参数"]: row["值"] for row in parameter_rows}
    assert parameters["计算月份"] == "2025-06"
    assert parameters["期间开始日期"] == "2025-06-01"
    assert parameters["期间结束日期"] == "2025-06-30"
    assert parameters["金额单位"] == "人民币元"
    assert parameters["利率输入格式"] == "Excel 百分比"
    assert parameters["放款生效规则"] == "次日起息"
    assert parameters["还本生效规则"] == "计息至还本当日"
    assert parameters["舍入规则"] == "逐笔最终 ROUND_HALF_UP 到 0.01"
    assert parameters["应用版本"] == "0.1.0"
    assert parameters["生成时间"] == "2026-07-10T12:30:00+00:00"


def test_export_is_blocked_when_any_check_has_failed() -> None:
    _, calculation = _calculation()
    failed_calculation = replace(
        calculation,
        checks=calculation.checks
        + (
            ApplicationCheck(
                name="forced_failure",
                display_name="强制失败",
                passed=False,
                expected=Decimal("0"),
                actual=Decimal("1"),
            ),
        ),
    )

    with pytest.raises(ExportInvariantError):
        export_calculation_workbook(failed_calculation, generated_at=GENERATED_AT)
