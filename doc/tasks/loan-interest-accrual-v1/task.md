# 贷款利息自动计提工具

## Task Goal

构建一个仅在当前 Windows 电脑运行的本地网页应用，完成标准 Excel 模板下载、自然月选择、输入校验、贷款分段计息、资本化与费用化拆分、汇总校验、结果预览和 Excel 导出。

## Milestones

- [x] M1: 完成需求分析、PRD 与可测试验收标准
- [x] M2: 完成依赖图、BDD/TDD 测试计划与实施分工
- [x] M3: 完成项目基线和分段计息核心
- [x] M4: 完成标准 Excel 输入、结果导出与历史差异验证
- [x] M5: 完成本地网页界面、接口和真实用户路径
- [x] M6: 完成独立测试、评审修复循环和最终放行
- [x] M7: 完成任务清理、最终验证和收尾记录

## Expected Verification

- pytest 单元测试和集成测试全部通过
- Playwright 真实页面端到端测试全部通过
- 标准模板可下载、回读、校验、计算和导出
- 历史 Excel 可比样本形成可解释的差异报告
- 计算结果满足本金滚动、利息拆分和汇总勾稽
- 独立 reviewer 的最终结论为 `pass`
- 启动脚本在当前 Windows 电脑完成烟雾验证

## Current Status

completed

## Constraints

- 遵循 BDD + 严格 TDD，生产代码必须有对应测试
- 不增加需求之外的 fallback、静默降级或兼容分支
- 不修改 `doc` 目录中的原始需求文档、图片和历史 Excel
- 使用 PowerShell 时不得使用 `&&`
- 仅处理当前任务拥有的文件和进程

## Cleanup Keep

- doc/tasks/loan-interest-accrual-v1/task-state.json

## Cleanup Candidates

- .artifacts/loan-interest-accrual-v1/browser-install/
