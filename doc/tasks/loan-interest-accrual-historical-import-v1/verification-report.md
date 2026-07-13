# Verification Report

## Summary
PASS. The tool now explicitly supports the known historical ledger workbook in addition to the standard template path. The screenshot failure mode no longer reports missing 贷款主表 / 资金变动 for the known historical workbook.

## Verified Behaviors
- Historical workbook doc\银行借款 利息计提明细2022-2024(计算).xlsx uploads successfully for 2024-01.
- Reference loan 历史:24全年:2 calculates 当月计提利息（元） = 10763.89.
- Exported workbook contains fixed values and 0 formulas.
- The same historical workbook for 2026-07 returns HISTORICAL_PERIOD_NOT_FOUND on sheet 历史工作簿 instead of SHEET_MISSING.
- Historical source workbook SHA-256 remained unchanged: 1340a195fe3c9d38323c7e063bbd2b09861bfb247fcc4853881f781b24628813.
- Final EXE: dist\贷款利息自动计提工具.exe, size 19221593, SHA-256 f3af3cad5fd025e16178638057fe8848307079fd8a1f271df9ed2ad9041dd3e0.

## Verification Commands
- ./.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/historical -q -> PASS, 5 passed.
- ./.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/integration/web/test_web_app.py tests/historical -q -> PASS, 16 passed.
- ./.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/unit tests/integration tests/historical -q -> PASS, 141 passed.
- ./scripts/build-exe.ps1 -> PASS.
- EXE runtime historical verification -> PASS, calculate/export validated with real historical workbook.
- ./.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/e2e/test_desktop_product.py -q -> PASS, 3 passed.
- ./scripts/verify-release.ps1 -> PASS: bootstrap 7, unit 53, integration 83, historical 5, smoke twice, E2E 5, release 6.

## Release Evidence
- Release evidence bundle: .artifacts\loan-interest-accrual-v1\release.
- Historical EXE verification evidence before cleanup: .artifacts\loan-interest-accrual-historical-import-v1\exe-runtime\historical-exe-verification.json.

## Result
completed. Required implementation, verification, EXE rebuild, and task-owned cleanup are complete.
