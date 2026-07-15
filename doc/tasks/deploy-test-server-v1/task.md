# Deploy current code to test server

## Task Goal
Publish the current `chenyali` code to the test server using a deployment approach derived from `D:\ProjectPackage\Int\IntRuoyiMaintance`, while failing fast if required deployment prerequisites are missing.

## Milestones
- [x] M1: Confirm local branch and commit state.
- [x] M2: Read CI/CD delivery guidance and locate reference deployment materials.
- [x] M3: Identify test server target, deployment command, artifact format, and verification gates.
- [x] M4: Build/package the current code for the test server.
- [x] M5: Deploy to the test server and verify real runtime state.
- [x] M6: Record release evidence, blockers, and closeout status.

## Expected Verification
- Current source commit is recorded before deployment.
- Reference deployment method is mapped to this project without inventing credentials or targets.
- Deployment target, artifact path, rollback path, and required secrets are explicitly identified.
- Test server runtime verification proves the deployed version is active.
- No production, backup, restore, or rollback actions are performed unless separately authorized.

## 设计约束检查
- 是否引入 fallback/降级/吞异常：否。
- 是否从根因和长期维护角度解决：是，先识别正式发布契约和目标环境，再执行发布。
- 是否存在临时补丁或绕过：否；缺少发布前置条件时阻塞，不用手工拼接未定义流程。

## Current Status
completed

## Preflight Gates
- Test server: `172.30.30.58`.
- Deployment boundary: test server only; no production, backup, restore, rollback, database sync, or object storage sync.
- Remote target port: `18082`, selected because `8000` is owned by `/opt/intpp-backend`, `18080` and `18081` are already used, and `18082` is free.
- Remote runtime root: `/opt/loan-interest-accrual`.
- Remote runtime method: independent Python 3.12 virtual environment under the release directory, installed from a task-built Linux wheelhouse.
- Docker route: blocked because local and remote Docker Hub access could not pull `python:3.12-slim`; no Docker fallback was used.
- Required remote Python: `/opt/intpp-backend/venv/bin/python`, verified as Python 3.12.7; it is used only to create an independent venv for this app.

## Deployment Evidence
- Implementation commit: `d281589` added the test-server deployment script and contract tests.
- Script fix commit: `a02c95a` fixed remote script encoding and status output.
- Final release tag: `chenyali-a02c95a-r202607151435`.
- Final commit deployed: `a02c95acea2d7eec78da5a85dcea729a36e6430f`.
- Service: `loan-interest-accrual-test.service`.
- Test URL: `http://172.30.30.58:18082/`.
- Health URL: `http://172.30.30.58:18082/health`.
- Remote release root: `/opt/loan-interest-accrual/releases/chenyali-a02c95a-r202607151435`.
- Verification: remote systemd active, remote/local health HTTP 200, homepage HTTP 200, template download content type xlsx, real `/calculate` upload returned HTTP 200, Playwright browser entry returned HTTP 200 with zero console errors and zero failed requests.
- CI/CD evidence validation passed.
- Task cleanup preview/apply passed and deleted `.artifacts/deploy-test-server-v1`.
- Final remote recheck remained healthy after cleanup.

## Cleanup Keep
- doc/tasks/deploy-test-server-v1/ci-cd-evidence.md
- docs/environments/ci-cd-evidence.md

## Cleanup Candidates
- .artifacts/deploy-test-server-v1/
