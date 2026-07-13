# Execution Log

BDD: 历史 Excel 上传提示可操作结果 -> Given 用户上传 doc 下历史银行借款工作簿, When 选择可计算自然月并点击计算, Then 系统不应仅因缺少标准模板工作表而失败, 应识别历史格式并给出计算结果或字段级可定位错误。
BDD: 当前月份超出历史数据范围 -> Given 用户上传历史工作簿, When 选择文件不覆盖的自然月, Then 系统应明确提示该月份缺少可计算数据, 不生成部分结果。

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\historical -q -> FAIL, 历史导入错误纳入了所选月份之后才发生的借款行，触发 DATE_RANGE_INVALID。
RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\historical -q -> FAIL, 历史银行表标题月份与列头月份不一致时，解析器错误使用列头月份，导致非所选月份数据进入 2024-01。
RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\historical -q -> FAIL, 无标题行的历史工作表（如 24全年 第1行即表头）触发 title_row=None 的 TypeError。
GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\historical -q -> PASS, 5 passed；历史 Excel 2024-01 可直传计算并导出，2026-07 明确提示历史月份无数据，不再报缺少标准模板工作表。

BLOCKER CLEARED: 端口 8000 被任务生成的 dist\贷款利息自动计提工具.exe 残留进程占用；已确认路径后停止该任务自有进程，再继续回归验证。
GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web\test_web_app.py tests\historical -q -> PASS, 16 passed；Web API 已覆盖历史 Excel 成功月份和无数据月份提示。
GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit tests\integration tests\historical -q -> PASS, 141 passed；标准模板、历史导入、Web、导出和 Windows 集成回归通过。
GREEN: EXE runtime historical verification -> PASS, dist\贷款利息自动计提工具.exe 可启动；历史 Excel 2024-01 计算/导出通过，历史:24全年:2 利息 10763.89，导出无公式；2026-07 返回 HISTORICAL_PERIOD_NOT_FOUND；源文件哈希未变。EXE size=19221593 sha256=f3af3cad5fd025e16178638057fe8848307079fd8a1f271df9ed2ad9041dd3e0
RED: .\scripts\verify-release.ps1 -> FAIL, 发布脚本仍要求桌面化任务已按 closeout 清理掉的 frontend-feature-evidence.md、test-plan.md、task-state.json 中间产物。
GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\release -q -> PASS, release contract now requires only retained desktop task closeout records.
RED: .\scripts\verify-release.ps1 -> FAIL, E2E 使用说明仍按旧版 4 步断言；产品文案新增历史台账说明后实际为 5 步。
GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\e2e\test_desktop_product.py -q -> PASS, 桌面产品 E2E 已更新为 5 步使用说明并验证历史台账说明文案。
GREEN: .\scripts\verify-release.ps1 -> PASS, bootstrap 7, unit 53, integration 83, historical 5, Windows smoke twice, E2E 5, release 6. Release evidence: .artifacts\loan-interest-accrual-v1\release.
CLOSEOUT READY: task.md marked ready_for_closeout; verification-report.md created with final evidence summary. Cleanup candidate: .artifacts\loan-interest-accrual-historical-import-v1/.
CLOSEOUT FIX: verification-report.md rewritten with concrete EXE hash, source hash, and formula count after PowerShell interpolation produced literal placeholders.
CLEANUP APPLY: task-closeout-cleanup apply -> APPLIED. Removed .artifacts/loan-interest-accrual-historical-import-v1 and retained task.md, execution-log.md, verification-report.md.
COMPLETED: task.md marked completed after cleanup apply and final verification evidence was retained.
CLOSEOUT FIX: verification-report.md placeholders replaced with final concrete source hash, EXE hash, EXE size, formula count, and completed status.
