# Verification Report

## Status
completed

## Evidence
- Local source state confirmed at `7d47099`.
- CI/CD evidence contract loaded.
- Reference deployment materials located.
- Deployment script and contract tests added.
- Test server target and runtime route identified: `172.30.30.58`, `/opt/loan-interest-accrual`, service `loan-interest-accrual-test`, port `18082`.
- Docker image route is blocked by Docker Hub access; task uses an explicit Linux wheelhouse and independent Python 3.12 venv.
- Final deployed release: `chenyali-a02c95a-r202607151435`.
- Deployed commit: `a02c95acea2d7eec78da5a85dcea729a36e6430f`.
- Test server service: `loan-interest-accrual-test.service` active.
- Test server URL: `http://172.30.30.58:18082/`.
- Health verification: remote and local HTTP checks returned `{"status":"ok"}`.
- Template verification: `GET /template` returned the expected xlsx media type.
- Calculation verification: real workbook upload to `/calculate` returned HTTP 200 with accrued interest `3.00`.
- Browser verification: Playwright opened the deployed page with HTTP 200, title `贷款利息自动计提`, zero console errors, and zero failed requests.
- CI/CD evidence validation passed.
- Cleanup preview/apply passed and removed task-owned local artifacts.
- Final remote health recheck passed after cleanup.

## Pending
- None.
