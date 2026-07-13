from __future__ import annotations

from datetime import date
from pathlib import Path

from tests.fixtures.web.workbooks import (
    loan_row,
    movement_row,
    workbook_bytes,
)


def write_valid_workbook(path: Path) -> Path:
    path.write_bytes(
        workbook_bytes(
            loans=[
                loan_row(
                    loan_id="L-E2E-001",
                    company="端到端测试公司",
                    contract="E2E-HT-001",
                    bank="端到端测试银行",
                    principal=1_000_000,
                    rate=0.0365,
                    basis=365,
                    start=date(2024, 2, 1),
                    end=date(2024, 2, 29),
                    capitalized="否",
                )
            ],
            movements=[
                movement_row(
                    loan_id="L-E2E-001",
                    event_date=date(2024, 2, 15),
                    movement_type="放款",
                    amount=100_000,
                )
            ],
        )
    )
    return path


def write_invalid_workbook(path: Path) -> Path:
    path.write_bytes(
        workbook_bytes(
            loans=[
                loan_row(
                    loan_id="",
                    company="",
                    contract="",
                    bank="",
                    principal=-1,
                    rate="not-a-rate",
                    basis=999,
                    start="not-a-date",
                    end=None,
                    capitalized="invalid",
                )
            ],
            movements=[
                movement_row(
                    loan_id="MISSING-LOAN",
                    event_date=date(2024, 3, 1),
                    movement_type="invalid",
                    amount=-5,
                )
            ],
        )
    )
    return path
