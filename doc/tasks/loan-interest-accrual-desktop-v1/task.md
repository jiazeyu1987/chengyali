# 贷款利息自动计提工具桌面化交付

## Task Goal

将现有本地网页应用产品化为财务人员可直接使用的 Windows 工具：首次安装后通过桌面快捷方式一键启动，后台窗口隐藏，自动打开默认浏览器，保持仅监听 `127.0.0.1`，提供清晰的本机处理提示、使用说明、下载目录入口和安全退出方式。

## Scope

- 新增面向最终用户的一键安装、启动、停止和卸载脚本。
- 安装时创建桌面及开始菜单快捷方式，不要求用户手工运行 Python 或 PowerShell。
- 启动时复用健康的任务自有实例；不存在时隐藏启动，健康检查通过后自动打开默认浏览器。
- 停止时只终止运行状态文件记录且身份匹配的任务自有进程树，拒绝处理不匹配或不可信 PID。
- 页面增加本机数据说明、简明使用说明、打开下载目录和退出工具入口。
- 保持现有模板、计算、校验和 Excel 导出契约不变。
- 上传内容继续仅在请求内存中处理，不新增数据库或持久化原始文件。

## Non-Goals

- 不制作跨电脑安装包、MSI、Electron、VBA 或公网服务。
- 不增加账号、多用户、数据库、云同步或自动更新。
- 不猜测或扫描任意端口，不终止非任务自有进程。

## Milestones

- [x] M1: 建立桌面化产品 BDD、TDD 和验收证据
- [x] M2: 完成一键安装、启动、停止、卸载和快捷方式
- [x] M3: 完成财务用户页面入口及本机运行交互
- [x] M4: 完成 Windows 集成、真实页面 E2E 和回归验证
- [x] M5: 完成独立 reviewer 放行、清理和最终交付

## Expected Verification

- Windows 脚本测试覆盖安装、快捷方式、隐藏启动、健康复用、端口冲突、PID 身份校验、停止和卸载。
- Web 集成测试覆盖帮助内容、下载目录、退出请求和原有 API 契约。
- Playwright 使用真实页面完成启动后的核心财务路径及新增产品入口。
- 现有计算、Excel 导入导出、历史差异和发布测试全部回归通过。
- 独立 reviewer 的逻辑、易用性和 UI 三层均为 `pass`。

## Current Status

completed

## Closeout

- Final independent review: pass in round 4.
- Finance-user desktop and Start Menu shortcuts are installed.
- Task cleanup preview and apply completed without blocked paths or warnings.
- Retained records: `task.md`, `execution-log.md`, and `verification-report.md`.

## Constraints

- BDD + strict TDD；生产行为必须先有失败测试。
- 不增加 fallback、静默降级、端口扫描或身份不明的进程终止。
- 仅监听 `127.0.0.1`，不访问外部网络。
- PowerShell 命令不得使用 `&&`。
- 不修改原始需求文档和历史 Excel。
