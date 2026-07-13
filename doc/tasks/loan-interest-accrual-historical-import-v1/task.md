# 历史 Excel 直接导入支持任务

## Task Goal
让本地贷款利息自动计提工具能够明确识别并处理用户现有历史 Excel 文件，避免只提示缺少标准模板工作表；在可计算时生成与规则一致的计提结果，在不可计算时给出可定位的错误。

## Milestones
- [x] 核对历史工作簿结构与当前导入器失败原因
- [x] 编写历史 Excel 导入 BDD/TDD 用例并记录 RED/GREEN 证据
- [x] 实现显式历史文件导入、校验、预览与导出路径
- [x] 重建 EXE 并用真实工作簿验证数值与界面路径
- [x] 发布级验证通过并准备 closeout 清理

## Expected Verification
- pytest 单元与集成测试通过
- 使用 doc 下历史 Excel 走真实上传计算路径
- 导出结果工作簿的关键数值与可解释预期一致
- EXE 双击启动路径可用

## Cleanup Candidates
- .artifacts/loan-interest-accrual-historical-import-v1/

## Cleanup Keep
- doc/tasks/loan-interest-accrual-historical-import-v1/task.md
- doc/tasks/loan-interest-accrual-historical-import-v1/execution-log.md
- doc/tasks/loan-interest-accrual-historical-import-v1/verification-report.md

## Current Status
completed

