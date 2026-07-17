from __future__ import annotations

from datetime import date
from io import BytesIO
from urllib.parse import unquote

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from loan_interest_accrual.web import create_app
from loan_interest_accrual.workbook import (
    AMORTIZATION_SHEET,
    generate_amortization_template,
)


def _payload() -> bytes:
    workbook = load_workbook(BytesIO(generate_amortization_template()))
    sheet = workbook[AMORTIZATION_SHEET]
    sheet.append(
        [
            "软件",
            "测试软件",
            "管理费用",
            1200,
            0,
            date(2026, 4, 30),
            date(2026, 4, 30),
            12,
        ]
    )
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_homepage_template_calculate_and_export_flow() -> None:
    with TestClient(create_app()) as client:
        homepage = client.get("/")
        assert homepage.status_code == 200
        assert "无形资产及长摊自动计提" in homepage.text
        assert "累计摊销金额（含本期）" in homepage.text
        assert 'id="amortization-table-shell"' in homepage.text
        assert "表格右侧上下滚动，底部左右滚动" in homepage.text
        assert "styles.css?v=20260715-6" in homepage.text
        assert "app.js?v=20260715-6" in homepage.text

        template = client.get("/template")
        assert template.status_code == 200
        assert "无形资产长摊计提输入模板" in unquote(
            template.headers["content-disposition"]
        )

        files = {
            "file": (
                "摊销输入.xlsx",
                _payload(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        calculated = client.post(
            "/calculate", data={"calculation_month": "2026-06"}, files=files
        )
        assert calculated.status_code == 200
        body = calculated.json()
        assert body["success"] is True
        assert body["preview"][0]["sequence"] == 1
        assert body["preview"][0]["cumulative_months"] == 3
        assert body["preview"][0]["ending_net_value"] == "900.00"
        assert body["summary"]["original_value"] == "1200.00"

        exported = client.post(
            "/export", data={"calculation_month": "2026-06"}, files=files
        )
        assert exported.status_code == 200
        assert exported.content.startswith(b"PK")
