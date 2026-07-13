# Execution Log

## BDD Scenarios

BDD: 财务人员一键启动 -> Given 已完成本机安装且桌面快捷方式存在, When 用户双击“贷款利息自动计提工具”, Then 工具隐藏启动或复用健康实例，确认仅监听 127.0.0.1 后自动打开默认浏览器首页。

BDD: 缺少运行前提时快速失败 -> Given Python 3.12、虚拟环境或固定依赖缺失, When 用户安装或启动工具, Then 脚本明确报告缺失前提且不创建伪成功快捷方式。

BDD: 端口被其他程序占用 -> Given 8000 端口由非任务进程监听, When 用户启动工具, Then 启动失败并明确提示端口冲突，不扫描或静默切换其他端口。

BDD: 已有健康实例复用 -> Given 运行状态文件和进程身份匹配且健康检查通过, When 用户再次双击启动快捷方式, Then 不创建第二个服务实例，只重新打开页面。

BDD: 安全停止工具 -> Given 运行状态文件记录任务自有进程及命令行身份, When 用户使用退出入口, Then 仅终止该任务进程树、释放端口并删除运行状态文件。

BDD: 拒绝不可信 PID -> Given 运行状态文件中的 PID 不存在或进程命令行与本工具不匹配, When 执行停止, Then 脚本快速失败且不终止任何进程。

BDD: 财务页面自助操作 -> Given 用户打开首页, When 查看顶部和辅助操作, Then 页面明确说明数据仅在本机处理，并提供使用说明、打开下载目录和退出工具入口。

BDD: 原有 Excel 路径保持不变 -> Given 合法标准模板, When 选择月份、上传、计算并导出, Then 预览和导出数值与既有规则一致，新增桌面化功能不改变工作簿契约。

## RED/GREEN Evidence

待实现子任务按场景追加精确的 `RED:`、`GREEN:`、修改摘要和验证结果。

## Baseline Verification

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, `108 passed in 30.94s` before desktop-product production changes.

Implementation coordination: the first broad implementation subtask completed analysis only and made no code changes. Work was repartitioned into mutually exclusive Windows lifecycle and finance-user web slices so each worker owns a concrete production and test write set.

## 2026-07-10 收敛记录

- 已完整核对任务目标、BDD 场景、前端证据契约、测试计划，以及现有 Windows、Web、E2E、发布和贷款计算/Excel 契约。
- 本轮在进入测试写入前由用户要求立即收敛，因此尚未产生可记录的 `RED:` 或 `GREEN:` 命令结果。
- 未修改生产代码、测试代码、依赖、计算规则或 Excel 输入输出契约。
- 已检查当前工作区进程；没有本轮遗留的测试、构建或子任务命令。`127.0.0.1:8000` 的既有应用实例继续保留，未被本轮终止。
- 后续恢复时必须从新增失败测试开始，不得将本次审阅记录视为实现完成或放行证据。

## Windows Desktop Lifecycle

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_product.py -q` -> FAIL, `10 failed in 0.34s` because the required install, launch, stop, and uninstall scripts did not exist.

Implemented: desktop and Start Menu shortcut installation, hidden fixed-port launch, healthy owned-instance reuse, explicit port-conflict failure, runtime identity state, safe owned-tree stop, and owned-artifact uninstall.

## Finance User Web Slice

RED: `.\.venv\Scripts\python.exe -m pytest tests\integration\web\test_desktop_product.py -q` -> FAIL during collection because `loan_interest_accrual.web.desktop_actions` did not exist.

Implemented: prominent local-only data notice, accessible usage dialog, open-downloads action, delayed safe-exit action, Chinese busy/success/failure states, and responsive layout.

## Main Review Fixes

RED: local-action and hidden-launch tests -> FAIL, `2 failed`; auxiliary actions accepted requests without the local-action header and hidden launch had no user-visible failure report.

GREEN: targeted Web and Windows suites -> PASS, `43 passed`, after requiring `X-Local-Tool-Action`, adding launcher error logging and a Chinese Windows popup, and preserving fixed-port fail-fast behavior.

RED: delayed-exit and sanitized-error tests -> FAIL, `4 failed`; exit process creation failure occurred after the response, stop had no bounded response delay, and raw OS errors leaked into user-visible messages.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web\test_desktop_actions.py tests\integration\web\test_web_app.py tests\integration\windows\test_desktop_lifecycle.py tests\integration\windows\test_windows_scripts.py -q` -> PASS, `44 passed in 24.58s`.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, `132 passed in 31.55s`.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\e2e tests\release -q` -> PASS, `8 passed in 13.56s`.

Verification: real Chromium confirmed the local-only notice, accessible help dialog, protected local action requests, existing Excel workflow, Chinese validation errors, and stable layouts at 1366x768, 1536x864, and 1920x1080.

Remaining blockers: complete release script, installed shortcut handoff, independent reviewer, and closeout.

## Review Round 1 Blocking Fix BDD

BDD: Restart after dead owned runtime state -> Given a valid task-owned runtime state records a PID that no longer exists and fixed port 8000 has no listener, When the finance user launches the desktop shortcut, Then only the stale task-owned state is removed and a fresh fixed-port owned instance starts.
BDD: Uninstall after dead owned runtime state -> Given owned shortcuts and a valid task-owned runtime state record a PID that no longer exists while fixed port 8000 has no listener, When the finance user uninstalls the desktop tool, Then stale runtime state and owned shortcuts are removed without touching unrelated files.
BDD: Stop helper failure remains retryable -> Given the safe-stop helper starts but exits nonzero while the web service remains healthy, When the finance user requests exit, Then the page reports a clear Chinese failure and re-enables actions instead of retaining a success state.
BDD: Real desktop exit lifecycle -> Given the application was started by desktop-launch.ps1 on fixed loopback port 8000, When the finance user confirms the real /desktop/exit action in Chromium, Then the response is acknowledged before shutdown and the page observes the owned service and fixed-port listener terminate.

## Review Round 1 Fix Evidence

BDD: Fast fixed-port ownership inspection -> Given the desktop lifecycle scripts must inspect fixed port 8000, When launch or stop validates the listener, Then native Windows `netstat.exe` is used and the operation completes without the observed `Get-NetTCPConnection` delay.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py::test_ac_d04_stop_terminates_only_validated_owned_tree -q` -> FAIL because the stop helper was included in the owned application tree and would terminate itself before removing runtime state.

GREEN: the stop script now separates the validated owned tree from termination IDs and never terminates its current helper process.

RED: real Playwright desktop lifecycle -> FAIL because a stop helper launched as a child of the application was terminated with the application process tree, leaving `app.json` behind.

GREEN: the web action now starts a short broker process; `desktop-stop.ps1 -Detach` uses Windows CIM to create an independent hidden worker, and status polling treats successful broker acceptance as pending until the service actually stops.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py tests\integration\web\test_desktop_actions.py -q` -> PASS, `28 passed in 8.98s`.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\e2e tests\release -q` -> PASS, `10 passed in 29.03s`.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, `136 passed in 38.23s`.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-release.ps1` -> PASS: bootstrap `7`, unit `53`, integration `73`, historical `3`, E2E `5`, release `5`; Windows startup smoke passed twice and the release verifier reported no broken requirements.

Verification: real Chromium launched the fixed-port desktop application through `desktop-launch.ps1`, invoked the real `/desktop/exit` route, observed service shutdown, confirmed port release and confirmed runtime state removal.

## Review Round 2 Fix Evidence

BDD: Concurrent desktop launch ownership -> Given two shortcut launches overlap before state and port decisions finish, When both launchers execute, Then a machine-wide project-scoped mutex serializes them and exactly one healthy owned service plus one valid runtime state remain.

BDD: Failed competing launch preserves winning state -> Given a launch attempt owns a unique generation token and another valid state replaces it, When the first attempt fails cleanup, Then it may stop only its own process and must not remove the replacement state.

BDD: Missing-state uninstall fails closed -> Given runtime state is absent while a matching project process or any fixed-port listener remains, When uninstall runs, Then it preserves shortcuts/runtime artifacts and reports a recovery error.

RED: the new concurrency, ownership-cleanup and missing-state uninstall tests failed before implementation: `5 failed in 5.33s`.

GREEN: launch now uses a deterministic machine-wide mutex, runtime schema version 2 includes a unique `launch_token`, atomic writes use token-specific temporary/backup paths, failed startup removes state only after exact PID/listener/token ownership validation, and uninstall refuses missing-state live-service conditions.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py tests\integration\web\test_desktop_actions.py -q` -> PASS, `32 passed in 15.93s`.

BDD: Reused parent PID must not imply ownership -> Given an unrelated older process retains a parent PID value later reused by the application root, When the application validates or stops its process tree, Then the older process is excluded by creation-time ordering and is never terminated.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py::test_ac_d04_stop_terminates_only_validated_owned_tree -q` -> FAIL because the tree scan included unrelated older PID `6000` solely from a stale `ParentProcessId`.

GREEN: both launch and stop process-tree validation now require trustworthy creation times and accept a child relation only when the candidate process was created no earlier than its validated parent.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py -q` -> PASS, `18 passed in 14.92s`.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, `140 passed in 40.33s`.

GREEN: fresh release verification from a free fixed port -> PASS: bootstrap `7`, unit `53`, integration `77`, historical `3`, E2E `5`, release `6`; startup smoke passed twice and the verifier reported no broken requirements.

Cleanup evidence: a timed-out verifier tree and its task-owned random-port startup process were explicitly identity-checked and stopped. Unrelated older `winrdlv3.exe` processes exposed by stale parent PID reuse were not terminated and motivated the creation-time ownership fix. Final runtime state is absent and port `8000` is free.

## Final Installation Evidence

BDD: End-user installation does not download a test browser -> Given the finance user runs the final installer on the current Windows computer, When runtime dependencies are already present or installed, Then setup verifies Python packages and creates shortcuts without invoking a Playwright Chromium download.

RED: the first real `scripts\install.ps1` run exceeded `600` seconds and remained blocked in `python -m playwright install chromium`; shortcuts were not created.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_windows_scripts.py::test_setup_requires_exact_python_pins_without_browser_download -q` -> FAIL because `setup.ps1` still invoked the browser download.

GREEN: `setup.ps1` now installs pinned Python requirements, runs `pip check`, and does not download an E2E browser during finance-user installation. Playwright browser provisioning remains a development/release-verification concern, not an end-user runtime prerequisite.

GREEN: real `scripts\install.ps1` -> PASS in `6.5s`; Windows setup completed and desktop plus Start Menu shortcuts were created.

GREEN: installed-shortcut smoke -> PASS. Both shortcuts target Windows PowerShell with the exact hidden `desktop-launch.ps1` command, the desktop shortcut started a healthy schema-v2 owned service, and `desktop-stop.ps1` removed state and released port `8000`.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, `140 passed in 39.60s`.

GREEN: final release verification after the installer change -> PASS: bootstrap `7`, unit `53`, integration `77`, historical `3`, E2E `5`, release `6`; no broken requirements.

## Closeout

GREEN: final independent review round 4 -> PASS across logic, usability, and UI; `required_changes: []`, `final_decision: pass`.

GREEN: task-closeout-cleanup preview -> READY with no blocked paths or warnings.

GREEN: task-closeout-cleanup apply -> APPLIED. Removed `frontend-feature-evidence.md`, `task-state.json`, and `test-plan.md`; retained `task.md`, `execution-log.md`, and `verification-report.md`.

Final status: completed.

## Review Round 2 Blocking Fix BDD

BDD: Concurrent desktop launch serialization -> Given port 8000 is initially free and two finance users launch the same project shortcut concurrently, When both launchers evaluate shared runtime state and fixed-port ownership, Then one launcher starts exactly one owned service while the waiting launcher reuses the verified healthy instance and one valid atomic state file remains.
BDD: Failed startup cleanup ownership -> Given one launch attempt has written its per-launch ownership token and a competing owner replaces runtime state, When the first attempt fails startup cleanup, Then it stops only its own validated process and preserves the state belonging to the other PID, listener, and token.
BDD: Missing-state live-service uninstall -> Given owned shortcuts and runtime artifacts exist but `app.json` is missing while either a matching project process or any fixed-port listener exists, When uninstall runs, Then it fails closed and preserves the shortcuts and runtime artifacts without terminating any process.

## Review Round 2 RED Evidence

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py::test_ac_d01_launch_is_hidden_fixed_loopback_and_opens_after_health tests\integration\windows\test_desktop_lifecycle.py::test_ac_d02_concurrent_launches_serialize_and_reuse_single_owned_instance tests\integration\windows\test_desktop_lifecycle.py::test_ac_d03_failed_launch_cleanup_preserves_replaced_state tests\integration\windows\test_desktop_lifecycle.py::test_ac_d05_uninstall_missing_state_fails_closed -q` -> FAIL, `5 failed in 5.33s`; the launcher had no Windows mutex or ownership token, both concurrent launchers started, failed startup cleanup removed shared state unconditionally, and missing-state uninstall removed shortcuts/runtime artifacts despite simulated matching processes or fixed-port listeners.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py::test_ac_d01_launch_is_hidden_fixed_loopback_and_opens_after_health -q` -> FAIL, `1 failed in 0.12s`; the first mutex implementation used the session-local namespace instead of the required machine-wide application/project-scoped `Global\` namespace.

## Review Round 2 GREEN Evidence

Implemented: `desktop-launch.ps1` now acquires a deterministic machine-wide named mutex before runtime-state, fixed-port, process-start, and state-write decisions; a waiting launcher re-evaluates state after acquisition and reuses only the verified healthy owned instance.

Implemented: runtime state is schema version 2 with a per-launch 32-character ownership token, unique temporary/backup paths, atomic `File.Replace` updates, and failed-startup deletion only when PID, listener PID, and token still match the exact launch attempt.

Implemented: `uninstall.ps1` uses native `netstat.exe` and project command-line identity checks when `app.json` is missing; any matching project process or fixed-port listener aborts uninstall before shortcuts or runtime artifacts are removed.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_desktop_lifecycle.py -q` -> PASS, `18 passed in 17.25s`.

GREEN: main verification of PowerShell parsing and the focused Windows/Web suites -> PASS, `32 passed in 15.93s`.

Cleanup verification: task-owned process count `0`, runtime state absent, and fixed-port listener count `0`. No unrelated process was terminated.

Release note: no final release decision is recorded here. Full release verification was not used as final round-2 evidence after the last mutex namespace change.
