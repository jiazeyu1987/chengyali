# CI/CD Evidence: deploy current code to test server

## Environments And Deployment Targets
- Local repository: `E:\ProjectPackage\chenyali`
- Test server: `172.30.30.58`
- Test server URL: `http://172.30.30.58:18082/`
- Test server health: `http://172.30.30.58:18082/health`
- Remote runtime root: `/opt/loan-interest-accrual`
- Remote service: `loan-interest-accrual-test.service`

## Commands
- Local validation: `.\.venv\Scripts\python.exe -m pytest tests\deploy\test_test_server_deploy_contract.py tests\bootstrap -q`
- Deployment: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-test-server.ps1 -ReleaseTag chenyali-a02c95a-r202607151435`
- Remote service status: `systemctl is-active loan-interest-accrual-test.service`
- Remote health: `curl -fsS http://127.0.0.1:18082/health`

## Pipeline
- Preflight: read reference server/release documents, confirm SSH, disk capacity, port availability, and Python 3.12.
- Package: create `git archive` from committed `HEAD`.
- Dependency artifact: build Linux CPython 3.12 wheelhouse from pinned `requirements.txt`.
- Deploy: upload source archive, wheelhouse, and UTF-8 no-BOM remote deploy script; create independent release venv; install dependencies offline; write systemd service; restart service.
- Verify: check systemd, port listener, health, homepage, template download, real calculation upload, and Playwright browser entry.

## Required Secrets And Owners
- Existing SSH access to `root@172.30.30.58` was used.
- No passwords, tokens, private keys, or connection secrets were committed or recorded.
- Deployment owner: current task requester.

## Artifacts And Release Output
- Implementation commit: `d28158940e123757e0f44fe859e7f906a20ad232`
- Final deployed commit: `a02c95acea2d7eec78da5a85dcea729a36e6430f`
- Release tag: `chenyali-a02c95a-r202607151435`
- Remote release directory: `/opt/loan-interest-accrual/releases/chenyali-a02c95a-r202607151435`
- Remote release manifest: `/opt/loan-interest-accrual/current-release.json`
- Service: `loan-interest-accrual-test.service`

## RED Evidence
- Docker route failed because both local and remote Docker could not pull `python:3.12-slim` from Docker Hub due connection reset/timeout.
- Remote direct `pip download` exceeded three minutes and the task-owned hanging process was stopped.
- First script run deployed `d281589` but returned non-zero because piped remote script text included a BOM; fixed by uploading a UTF-8 no-BOM script file and redeploying `a02c95a`.

## GREEN Verification Evidence
- Contract tests and bootstrap tests: `9 passed`.
- Final deployment command returned status `pass`.
- Remote `/opt/loan-interest-accrual/current-release.json` records release tag `chenyali-a02c95a-r202607151435` and commit `a02c95acea2d7eec78da5a85dcea729a36e6430f`.
- `systemctl is-active loan-interest-accrual-test.service` returned `active`.
- Remote `ss` shows Python listening on `0.0.0.0:18082`.
- Remote and local health checks returned `{"status":"ok"}`.
- Homepage returned HTTP 200.
- Template download returned `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Real workbook upload to `/calculate` returned HTTP 200 and accrued interest `3.00`.
- Playwright opened the deployed page with HTTP 200, title `贷款利息自动计提`, console errors `0`, failed requests `0`.

## Manual Approvals And Blockers
- User explicitly requested deployment to the test server.
- No approval was granted for production, backup, restore, rollback, database sync, or object storage sync.
- Docker Hub access remains unavailable for this project; the deployed path uses a pinned Linux wheelhouse and independent Python 3.12 venv.

## Rollback Procedure And Validation
- If rollback is needed, perform it as a separate explicitly authorized task.
- Minimal rollback target is a prior release under `/opt/loan-interest-accrual/releases/<releaseTag>` by updating `/etc/systemd/system/loan-interest-accrual-test.service` to the prior release venv/source path, running `systemctl daemon-reload`, restarting the service, and rechecking `http://127.0.0.1:18082/health`.
