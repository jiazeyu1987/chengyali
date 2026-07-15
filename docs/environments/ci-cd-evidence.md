# CI/CD Evidence: test server deployment

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
- Preflight confirms SSH, capacity, port availability, remote Python 3.12, and test-only boundary.
- Package uses `git archive` from committed `HEAD`.
- Dependency artifact uses a Linux CPython 3.12 wheelhouse from pinned `requirements.txt`.
- Deploy creates an independent release venv, installs dependencies offline, writes a systemd service, and restarts it.
- Verification checks service state, port listener, health, homepage, template download, real calculation upload, and Playwright browser entry.

## Required Secrets And Owners
- Existing SSH access to `root@172.30.30.58` was used.
- No secrets are committed or recorded.
- Deployment owner: current task requester.

## Artifacts And Release Output
- Final deployed commit: `a02c95acea2d7eec78da5a85dcea729a36e6430f`
- Release tag: `chenyali-a02c95a-r202607151435`
- Remote release directory: `/opt/loan-interest-accrual/releases/chenyali-a02c95a-r202607151435`
- Remote release manifest: `/opt/loan-interest-accrual/current-release.json`

## RED Evidence
- Docker route failed because `python:3.12-slim` could not be pulled from Docker Hub.
- Remote direct dependency download exceeded three minutes and the task-owned process was stopped.
- First remote script transport included a BOM and was fixed before final deployment.

## GREEN Verification Evidence
- Contract/bootstrap tests passed: `9 passed`.
- Final deployment command returned status `pass`.
- Remote release manifest records release tag `chenyali-a02c95a-r202607151435` and commit `a02c95acea2d7eec78da5a85dcea729a36e6430f`.
- Systemd service is active and Python listens on `0.0.0.0:18082`.
- Health checks returned `{"status":"ok"}`.
- Homepage and template endpoints returned HTTP 200 / expected media type.
- Real workbook upload to `/calculate` returned HTTP 200 and accrued interest `3.00`.
- Playwright page load returned HTTP 200 with zero console errors and zero failed requests.

## Manual Approvals And Blockers
- User authorized deployment to the test server in this task.
- Production, backup, restore, rollback, database sync, and object storage sync were not authorized and were not performed.
- Docker Hub access remains a blocker for Docker-image deployment.

## Rollback Procedure And Validation
- Rollback requires a separate explicit rollback authorization.
- To roll back, point the systemd service to a prior release directory under `/opt/loan-interest-accrual/releases`, run `systemctl daemon-reload`, restart `loan-interest-accrual-test.service`, and verify `http://127.0.0.1:18082/health`.
