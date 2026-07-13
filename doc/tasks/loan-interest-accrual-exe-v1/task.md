# 贷款利息自动计提工具 EXE 打包任务

## Task Goal
将现有本地网页应用打包成 Windows 单文件可执行程序，财务用户双击 exe 即可启动并打开工具页面，运行时不要求用户安装 Python、虚拟环境或依赖包。

## Milestones
- [x] M1: 明确当前启动方式、静态资源、依赖和打包约束。
- [x] M2: 先补充 EXE 打包与双击启动相关失败测试。
- [x] M3: 实现 PyInstaller 单文件入口、资源定位和构建脚本。
- [x] M4: 构建 EXE 并验证双击式启动、页面访问和 Excel 导入导出。
- [x] M5: 完成清理与放行记录。

## Expected Verification
- pytest 覆盖新增打包入口与资源定位行为。
- 构建产物为单个 `.exe`，不依赖系统 Python 或项目 `.venv`。
- 启动后仅监听 `127.0.0.1`，自动打开浏览器页面。
- 通过真实 HTTP 路径验证模板下载、有效 Excel 计算和结果导出。
- 任务文档记录 BDD、RED、GREEN 和最终验证证据。

## Current Status
completed

## Verification Evidence
- Built single-file Windows executable: `dist/贷款利息自动计提工具.exe`.
- Verified executable from an isolated temp copy, not from the project tree.
- Verified local-only runtime on `127.0.0.1:8000`.
- Verified template download, valid Excel calculation, result workbook export, zero formulas in export, embedded exit, and port release.
- Runtime verification evidence: `.artifacts/loan-interest-accrual-exe-v1/release/exe-runtime-verification.json`.

## Cleanup Plan
- Keep the final executable and release verification evidence.
- Remove PyInstaller intermediate build/spec folders under `.artifacts/loan-interest-accrual-exe-v1/`.
- Keep `task.md`, `execution-log.md`, and `verification-report.md`.

## Cleanup Evidence
- Cleanup applied: removed `.artifacts/loan-interest-accrual-exe-v1/pyinstaller-build`.
- Cleanup applied: removed `.artifacts/loan-interest-accrual-exe-v1/pyinstaller-spec`.
- Preserved release evidence under `.artifacts/loan-interest-accrual-exe-v1/release`.
- Preserved final executable under `dist/贷款利息自动计提工具.exe`.
