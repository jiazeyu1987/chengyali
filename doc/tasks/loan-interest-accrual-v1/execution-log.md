# Execution Log

## Initialization

- Task directory and supervisor-owned state initialized.
- Product implementation has not started.

## LIA-T01 Project Bootstrap

BDD: Exact Python 3.12 bootstrap with local-only configuration -> Given a Windows checkout with Python 3.12, When the bootstrap test suite inspects project metadata, package imports, settings, and direct dependencies, Then the package imports from the src layout, exposes its version, defaults to loopback only, declares only pinned approved dependencies, and rejects database, authentication, telemetry, and external-service dependencies.

RED: py -3.12 -m pytest tests/bootstrap -q -> FAIL, package bootstrap is absent and test collection raises ModuleNotFoundError for loan_interest_accrual.

GREEN: .\.venv\Scripts\python.exe -m pytest tests/bootstrap -q -> PASS, 7 passed.

### Completed Work

- Added exact Python 3.12 project metadata and src-layout package discovery.
- Added pinned approved runtime and test dependencies.
- Added immutable loopback-only default settings and application version exposure.
- Added bootstrap coverage for runtime, package imports, src layout, dependency pins, forbidden dependency classes, and generated-file ignores.

### Changed Paths

- `.gitignore`
- `pyproject.toml`
- `requirements.txt`
- `src/loan_interest_accrual/__init__.py`
- `src/loan_interest_accrual/settings.py`
- `src/loan_interest_accrual/version.py`
- `tests/conftest.py`
- `tests/bootstrap/test_package.py`
- `tests/bootstrap/test_project_metadata.py`
- `tests/bootstrap/test_repository_hygiene.py`
- `tests/bootstrap/test_runtime.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

Generated environment evidence: `.venv/` was created for Python 3.12 dependency installation and verification and is ignored by `.gitignore`.

### Verification and Scope

- The task-owned virtual environment has no broken requirements.
- The installed package imports outside the repository and exposes version `0.1.0` with host `127.0.0.1` and port `8000`.
- Generated caches and package build metadata outside `.venv/` were removed.
- No out-of-scope project file was created or modified; `task-state.json` and all other task documents remain untouched.

## LIA-T02 Domain Models and Calculation Engine

BDD: Natural-month bounds and inclusive loan-date intersection -> Given a selected natural month and loans with full or partial date coverage, When the domain period and accrual ranges are calculated, Then true month boundaries including leap February are used and each loan accrues over the inclusive closed intersection only.

BDD: Next-day drawdown and repayment effectiveness -> Given a loan with month-start, month-middle, or month-end principal movements, When interest segments are generated, Then the movement day accrues on pre-movement principal, the aggregate movement changes principal on the next day, and segments remain continuous, gap-free, and non-overlapping.

BDD: Same-day movement ordering and loan-ID identity -> Given multiple same-day drawdowns and repayments plus loans sharing display attributes, When inputs are supplied in different orders, Then same-day movements are aggregated deterministically and every result remains isolated by unique loan ID.

BDD: Negative-principal boundary rejection -> Given principal movements whose aggregate effective balance becomes negative at an event boundary, When the loan is calculated, Then calculation fails with a structured `NEGATIVE_PRINCIPAL` domain error identifying the loan and boundary.

BDD: Decimal rounding, classification, and summaries -> Given precision-sensitive capitalized and expensed loans, When interest and reconciliation summaries are calculated, Then all arithmetic remains Decimal-only, segment interest stays unrounded, each loan is rounded once with ROUND_HALF_UP to 0.01, and summaries add the rounded loan results.

RED: .\.venv\Scripts\python.exe -m pytest tests\unit\domain -q -> FAIL, the approved domain package and calculation behavior do not exist, so test collection raises ModuleNotFoundError for loan_interest_accrual.domain.

GREEN: .\.venv\Scripts\python.exe -m pytest tests\unit\domain -q -> PASS, 43 passed.

### Completed Work

- Added immutable typed models for natural months, loans, movements, interest segments, loan results, company summaries, capitalization summaries, reconciliation checks, and structured domain errors.
- Added deterministic natural-month bounds, leap-year handling, inclusive loan-period intersection, unique loan-ID enforcement, and strict 360/365 day-count selection.
- Added next-day principal effectiveness for drawdowns and repayments, same-day aggregation independent of input order, continuous segment generation, and negative-principal rejection at each effective event boundary.
- Added Decimal-only interest arithmetic, unrounded segment interest, one per-loan `ROUND_HALF_UP` rounding operation to `0.01`, capitalization/expense classification, and summaries based on rounded loan results.
- Added explicit boundary coverage for June, leap February, partial loan dates, month-start/month-end events, multiple movements, same-day permutations, intermediate negative principal, and segment-versus-loan rounding divergence.

### Changed Paths

- `src/loan_interest_accrual/domain/__init__.py`
- `src/loan_interest_accrual/domain/calculator.py`
- `src/loan_interest_accrual/domain/errors.py`
- `src/loan_interest_accrual/domain/models.py`
- `src/loan_interest_accrual/domain/period.py`
- `src/loan_interest_accrual/domain/reconciliation.py`
- `tests/unit/domain/test_calculator.py`
- `tests/unit/domain/test_models.py`
- `tests/unit/domain/test_period.py`
- `tests/unit/domain/test_reconciliation.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Acceptance Coverage

- Covered: `AC-04`, `AC-08`, `AC-09`, `AC-10`, `AC-11`, `AC-12`, `AC-13`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-18`.
- Regression verification: `.\.venv\Scripts\python.exe -m pytest tests\bootstrap tests\unit\domain -q` -> PASS, 50 passed.

### Scope Confirmation

- Modified only `src/loan_interest_accrual/domain/**`, `tests/unit/domain/**`, and this execution log.
- Did not modify `task-state.json`, planning files, workbook modules, web modules, scripts, or bootstrap files.
- Removed task-owned generated `__pycache__` directories under the domain source and unit-test paths.
- LIA-T02 is complete with no remaining implementation or verification blockers.

## LIA-T02 Fix Round 1 - Decimal Context Independence

BDD: High-precision same-day movement determinism -> Given same-day drawdowns of `1E+28`, `6`, and `6` and repayments of `1` and `1`, When every input permutation is calculated under the process default Decimal context, Then every order produces the exact ending principal `10000000000000000000000000010`.

BDD: High-precision final-only interest rounding -> Given two unrounded segment interests of `1E+25` and `0.005`, When segment interest is accumulated and the loan result is finalized, Then the exact unrounded sum is preserved and one final `ROUND_HALF_UP` produces `10000000000000000000000000.01`.

BDD: High-precision portfolio summaries and empty-period validation -> Given rounded loan results whose totals exceed the default Decimal precision or an empty portfolio with an invalid period value, When portfolio calculation and reconciliation run, Then summaries remain exact and deterministic while invalid periods fail before loan iteration.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\domain -q -> FAIL, 4 failed and 43 passed because default-context accumulation rounds high-precision movements, segment totals, and summaries, while an empty portfolio bypasses period type validation.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\domain -q -> PASS, 47 passed.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap -q -> PASS, 7 passed.

### Root Cause and Fix

- Same-day movement buckets, principal roll-forward, segment totals, summaries, and reconciliation checks accumulated `Decimal` values under the process default precision, allowing valid high-precision values to round before the approved final loan quantization.
- Added deterministic operand-derived Decimal precision for exact additions and differences, sufficient working precision for segment calculations, and context-independent `ROUND_HALF_UP` money quantization.
- Aggregated same-day movement values as complete collections before exact summation, preserving accepted Decimal inputs and making every permutation produce the same exact principal.
- Added upfront portfolio period validation so invalid periods fail even when no loans are supplied.
- Corrected only the regression test's erroneous summary expectation: `1E+28 * 0.365 / 365` for one day equals `1E+25`, and the second loan rounds from `0.006` to `0.01`, yielding `10000000000000000000000000.01`.

### Fix-Round Changed Paths

- `src/loan_interest_accrual/domain/calculator.py`
- `src/loan_interest_accrual/domain/decimal_math.py`
- `src/loan_interest_accrual/domain/reconciliation.py`
- `tests/unit/domain/test_calculator.py`
- `tests/unit/domain/test_models.py`
- `tests/unit/domain/test_reconciliation.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Fix-Round Verification and Scope

- High-precision same-day drawdown and repayment permutations all produce exact ending principal `10000000000000000000000000010`.
- Segment interests `1E+25` and `0.005` sum exactly before final rounding to `10000000000000000000000000.01`.
- Company summaries, capitalization summaries, total capitalization interest, and reconciliation accumulation preserve high-precision totals.
- Existing business rules remain unchanged; no amount cap, fallback, silent coercion, or float arithmetic was added.
- Modified only the approved LIA-T02 domain, unit-test, and execution-log paths.
- Removed task-owned generated `__pycache__` directories after verification.
- No implementation or test blocker remains for this fix round.

## LIA-T03 Standard Excel Template and Input Adapter

BDD: Exact standard workbook template -> Given a user requests the approved input template, When the template is generated, Then it contains exactly `贷款主表` and `资金变动`, the approved required columns plus optional `备注`, local header instructions, and percentage/date/currency formats without formulas, macros, or external links.

BDD: Strict standard-schema import -> Given uploaded bytes and a selected natural month, When production input is imported, Then only `.xlsx` files using the exact required sheets, columns, percentage rates, units, enums, dates, and `贷款ID` relationships are accepted without aliases or historical-layout inference.

BDD: Atomic deterministic workbook failure -> Given a workbook contains structural, cell, relationship, resource, or business errors, When it is imported, Then every detectable error is returned in deterministic sheet, row, field, and code order and no calculable input is exposed.

BDD: Principal-boundary validation -> Given valid typed workbook rows whose repayments make principal negative at an effective boundary, When the workbook adapter validates them through the existing domain calculator, Then the whole workbook fails with a located `NEGATIVE_PRINCIPAL` error.

BDD: Source immutability and hard limits -> Given source bytes with a recorded SHA-256 and files at or beyond the approved 20 MiB, 10,000-loan-row, and 100,000-movement-row limits, When import runs, Then the original bytes and hash remain unchanged, boundary inputs are not truncated, and exceedances fail structurally.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\workbook_input tests\integration\workbook_input -q -> FAIL, test collection raises ModuleNotFoundError because the approved `loan_interest_accrual.workbook` template and input adapter package does not exist.

### LIA-T03 Implementation Round 1

BDD: Structural errors do not hide formula errors -> Given a workbook with a missing required loan column and a formula in a detectable movement cell, When the workbook is imported, Then both structured errors are returned in deterministic order and no calculable input is exposed.

BDD: Portfolio business validation locates upload rows -> Given parsed workbook rows that domain portfolio validation rejects at a principal boundary, When the workbook is imported, Then the adapter maps the domain `NEGATIVE_PRINCIPAL` error back to the uploaded movement amount row and exposes no calculable input.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\workbook_input\test_importer.py::test_header_errors_do_not_hide_detectable_formula_errors tests\integration\workbook_input\test_importer.py::test_portfolio_business_validation_errors_are_mapped_to_source_rows -q -> FAIL, 2 failed because formula scanning stops after header errors and `loan_interest_accrual.workbook.validation` has no `calculate_portfolio` validation hook.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\workbook_input tests\integration\workbook_input -q -> PASS, 25 passed in 0.91s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit\domain tests\unit\workbook_input tests\integration\workbook_input -q -> PASS, 79 passed in 1.56s.

### Completed Work

- Added the standard workbook template contract for exactly `贷款主表` and `资金变动`, with approved required columns, optional `备注`, local instructions, and percentage/date/currency formatting.
- Added safe `.xlsx` import handling that preserves source bytes and SHA-256, rejects unsupported file extensions, corrupt packages, macros, external links, embedded objects, formulas, missing/duplicate sheets, missing/duplicate required columns, and conservative file/row-limit exceedances.
- Added strict standard-schema validation for blank/duplicate loan IDs, orphan or ambiguous movement IDs, invalid text/number/date/month/rate/basis/enum/amount values, loan date ranges without selected-month intersection, and no alias, historical-layout, unit, or non-percent-rate inference.
- Added atomic deterministic error collection: detectable errors are sorted by workbook, sheet, row, field, and code, and any error prevents exposing calculable loans or movements.
- Added domain-backed business validation through `Loan`, `Movement`, `NaturalMonth`, and `calculate_portfolio`, including located `NEGATIVE_PRINCIPAL` workbook errors for principal-boundary failures.
- Optimized validation to inspect populated workbook cells directly so sparse high-row limit fixtures are validated without truncating or timing out.

### Changed Paths

- `src/loan_interest_accrual/workbook/__init__.py`
- `src/loan_interest_accrual/workbook/schema.py`
- `src/loan_interest_accrual/workbook/limits.py`
- `src/loan_interest_accrual/workbook/template.py`
- `src/loan_interest_accrual/workbook/safe_reader.py`
- `src/loan_interest_accrual/workbook/importer.py`
- `src/loan_interest_accrual/workbook/validation.py`
- `tests/unit/workbook_input/test_template_and_limits.py`
- `tests/integration/workbook_input/test_importer.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Acceptance Coverage

- Covered mapped LIA-T03 acceptance IDs: `AC-03`, `AC-05`, `AC-06`, `AC-07`, `AC-08`, `AC-19`, `AC-20`, `AC-29`.
- Regression coverage also exercised the LIA-T02 domain contract used by workbook business validation, including negative-principal rejection and Decimal/domain type behavior.

### Scope Confirmation

- Modified only the approved LIA-T03 workbook input/template modules, workbook input tests, and this execution log.
- No `tests/fixtures/input/**` files were needed or created.
- Removed task-owned generated `__pycache__` directories under `src/loan_interest_accrual/workbook`, `tests/unit/workbook_input`, and `tests/integration/workbook_input`.
- No historical workbook compatibility parsing, aliases, fallback behavior, alternate units, non-percent rate parsing, upload saving, external service, database, authentication, or out-of-scope feature behavior was added.
- LIA-T03 is complete with no remaining implementation or verification blockers.

## LIA-T03 Fix Round 1 - Strict Interest Rate Bounds

BDD: Strict percentage-rate bounds -> Given a standard workbook whose `年利率` cell is formatted as an Excel percentage but has a value of `0`, `1`, or `2.5`, When the workbook is imported, Then the whole workbook fails with `INTEREST_RATE_INVALID` and no calculable input is exposed because approved rates must satisfy `0 < 年利率 < 1`.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\workbook_input\test_importer.py::test_date_relationship_rate_basis_enum_and_amount_boundaries -q -> FAIL, `0` formatted as a percentage was accepted and produced a calculable input.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\workbook_input tests\integration\workbook_input -q -> PASS, 25 passed in 1.35s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit\domain tests\unit\workbook_input tests\integration\workbook_input -q -> PASS, 79 passed in 1.14s.

### Fix-Round Changed Paths

- `src/loan_interest_accrual/workbook/validation.py`
- `tests/integration/workbook_input/test_importer.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Fix-Round Scope

- Tightened only the approved interest-rate rule to reject `rate <= 0` and `rate >= 1`.
- Added no unit conversion, fallback, alias parsing, historical compatibility, or partial-success behavior.

## LIA-T05 Historical Workbook Read-Only Differential Validator

BDD: Historical read-only differential validation -> Given two explicitly selected historical rows and a recorded source-workbook SHA-256, When the isolated historical validator reads only manifest-listed cells and calculates canonical PRD results, Then the deterministic report contains source evidence, canonical result, historical value, delta, and reason code, while the historical source hash remains unchanged.

BDD: Historical workbook is not a production input -> Given the historical workbook bytes, When they are submitted to the production workbook importer, Then the standard-schema importer rejects the historical layout and exposes no calculable input.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\historical -q -> FAIL, test collection raised ModuleNotFoundError because `tools.historical_validation.validator` did not exist.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\historical -q -> PASS, 3 passed in 3.94s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit\domain tests\unit\workbook_input tests\integration\workbook_input tests\historical -q -> PASS, 82 passed in 4.57s.

### Completed Work

- Added the isolated test-only historical validator module/CLI with an explicit manifest of selected workbook cells from `24全年` and `子公司借款利息（农商）`.
- The validator opens the historical workbook read-only, records source SHA-256 before and after, fails if the workbook changes, calculates canonical domain results, classifies deltas with allowed reason codes, and writes deterministic historical artifacts.
- Historical tests also assert the production standard-schema importer rejects the historical workbook layout without adding production compatibility.

### Changed Paths

- `tools/historical_validation/validator.py`
- `.artifacts/loan-interest-accrual-v1/historical/differential-report.json`
- `.artifacts/loan-interest-accrual-v1/historical/source-hash-before.txt`
- `.artifacts/loan-interest-accrual-v1/historical/source-hash-after.txt`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Scope Confirmation

- Did not modify production source code or `doc/银行借款 利息计提明细2022-2024(计算).xlsx`.
- Removed task-owned `__pycache__` directories under `tools/historical_validation` and `tests/historical` after verification.
- Release status was not decided.

## LIA-T04 Atomic Pipeline and Fixed-Value Excel Export

BDD: Atomic calculation service failure -> Given a submitted filename, workbook bytes, and NaturalMonth where the workbook contains any structured input error, When the application service processes the submission, Then it returns the complete structured error list with no preview, no domain result, and no export bytes.

BDD: Complete preview from current submission -> Given a valid standard workbook and NaturalMonth, When the application service calculates it, Then the response contains one complete per-loan preview row for every valid loan ID, all reconciliation checks are `通过`, and the original source bytes and SHA-256 are preserved.

BDD: Stateless export recomputation -> Given one workbook was previously calculated and a different workbook is later submitted for export, When export is requested, Then the export call reimports and recalculates the current submitted bytes/month and does not reuse prior calculated business state.

BDD: Six-sheet fixed-value export reconciliation -> Given a valid multi-loan workbook whose checks pass, When the result workbook is exported, Then it contains exactly `计提结果`, `分段明细`, `公司汇总`, `资本化汇总`, `校验结果`, and `计算参数`, with fixed values, no formulas/macros/external links/data connections/source workbook references, unrounded segment detail that ties to rounded loan results, summaries from rounded loan results, all checks `通过`, and complete parameter records.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\workbook_export tests\integration\pipeline -q -> FAIL, test collection raises ModuleNotFoundError because the approved `loan_interest_accrual.application` pipeline and workbook export modules do not exist.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\unit\workbook_export tests\integration\pipeline -q -> PASS, 6 passed in 0.50s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit\domain tests\unit\workbook_input tests\integration\workbook_input tests\unit\workbook_export tests\integration\pipeline -q -> PASS, 85 passed in 1.18s.

### Completed Work

- Added the stateless application service entry points `calculate_submission` and `export_submission`; both accept filename, source bytes, and `NaturalMonth`, and export internally recalculates from the current submitted bytes/month.
- Added structured application errors, complete calculated result rows, per-loan preview rows, segment detail rows, company summaries, capitalization summaries, and check records without returning partial success.
- Added the fixed export schema for exactly `计提结果`, `分段明细`, `公司汇总`, `资本化汇总`, `校验结果`, and `计算参数`.
- Added fixed-value `.xlsx` export with one result row per valid loan ID, unrounded segment interest rows, summaries derived from rounded per-loan results, all-success check rows, parameter records for period/rules/version/generation time, and package inspection for formulas, VBA, external links, and data connections.
- Added unit and integration coverage for atomic invalid processing, complete preview fields, source hash preservation, stateless export recomputation, six-sheet export structure, fixed-value package inspection, result/detail/summary tie-outs, check/parameter records, and blocked export on failed checks.

### Changed Paths

- `src/loan_interest_accrual/application/__init__.py`
- `src/loan_interest_accrual/application/service.py`
- `src/loan_interest_accrual/application/results.py`
- `src/loan_interest_accrual/workbook/export_schema.py`
- `src/loan_interest_accrual/workbook/exporter.py`
- `tests/fixtures/export/standard_workbooks.py`
- `tests/integration/pipeline/test_atomic_service.py`
- `tests/unit/workbook_export/test_exporter.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Acceptance Coverage

- Covered mapped LIA-T04 acceptance IDs: `AC-19`, `AC-21`, `AC-22`, `AC-23`, `AC-24`, `AC-25`, `AC-26`, `AC-27`, `AC-28`, `AC-29`.
- Export package inspection confirms no formula cells, VBA parts, external-link parts, connection parts, or external relationships in generated output.
- Source workbook bytes are never written back or mutated; source SHA-256 is preserved on calculation/export results, and output bytes are distinct from source bytes.

### Scope Confirmation

- Modified only the approved LIA-T04 application, workbook export, export fixture/test, pipeline test, and execution-log paths.
- Did not modify domain calculations, workbook input modules, web routes, historical tools/tests, scripts, `task-state.json`, or planning files.
- Removed task-owned generated `__pycache__` directories/files under the LIA-T04 application/export test paths and the two new workbook export modules.
- LIA-T04 implementation and required verification are complete with no remaining blockers; release status was not decided.

## LIA-T06 FastAPI APIs and Jinja2 Browser Interface

BDD: Local browser workflow and template download -> Given the local FastAPI application is running, When a user opens `/`, checks `/health`, loads local static assets, or downloads `/template`, Then the Chinese Jinja2 page exposes month selection, `.xlsx` upload, calculation, preview, error, and export controls, health reports success, all assets remain local, and the template downloads with the approved filename, media type, and worksheets.

BDD: Atomic calculation preview or structured failure -> Given a submitted `YYYY-MM` month and `.xlsx` workbook, When the user posts `/calculate`, Then a valid workbook returns the complete per-loan preview and passing checks, while any invalid workbook or request returns only structured errors containing `error_code`, `sheet`, `row`, `column_or_field`, and `message` with no partial preview.

BDD: Stateless export recomputation -> Given a prior calculation and a newly submitted workbook and month, When the user posts `/export`, Then the service independently revalidates and recalculates the current submission, streams the six-sheet fixed-value workbook with the approved filename and media type, and never reuses server-side business state.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web -q -> FAIL, test collection raises ModuleNotFoundError because `loan_interest_accrual.web` and the required FastAPI/Jinja2 routes do not exist.

### LIA-T06 Template and Static Asset Wiring Fix

BDD: Real template and mounted local assets -> Given the completed Chinese interface exists in `templates/index.html` with local CSS and JavaScript files, When the FastAPI application serves `/` and `/static/*`, Then the homepage is rendered through `Jinja2Templates`, static files are served through one named `StaticFiles` mount, and the inline duplicate interface is not used.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web\test_web_app.py::test_homepage_uses_the_jinja_template_and_mounted_static_files -q -> FAIL, 1 failed because `/` still returned the inline HTML from `routes.py` instead of `templates/index.html`.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web\test_web_app.py::test_homepage_uses_the_jinja_template_and_mounted_static_files -q -> PASS, 1 passed in 0.63s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web -q -> PASS, 8 passed in 1.11s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit\domain tests\unit\workbook_input tests\integration\workbook_input tests\unit\workbook_export tests\integration\pipeline tests\historical tests\integration\web -q -> PASS, 96 passed in 7.61s.

### Completed Work

- Added the FastAPI application factory and stateless HTTP routes for health, standard-template download, calculation preview, structured whole-request failure, and fixed-value workbook export.
- Added typed HTTP response models with located errors, per-loan preview rows, passing checks, deterministic calculation numbers, and preview summary totals.
- Rendered the existing complete Chinese interface through `Jinja2Templates` and mounted the existing local `static` directory through `StaticFiles`.
- Removed the duplicate inline HTML, CSS, JavaScript, and explicit static-content routes from `routes.py`.
- Preserved stateless request processing: calculation and export independently process the currently uploaded workbook and month without database, authentication, external URL, server-side business-result cache, or fallback behavior.

### Changed Paths

- `src/loan_interest_accrual/web/__init__.py`
- `src/loan_interest_accrual/web/app.py`
- `src/loan_interest_accrual/web/routes.py`
- `src/loan_interest_accrual/web/http_models.py`
- `tests/integration/web/test_web_app.py`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Scope Confirmation

- Reused the existing application service, workbook template generator, and workbook exporter without modifying their modules.
- Kept all API success, structured error, MIME type, attachment filename, source hash, preview, check, and stateless export contracts passing.
- Ran the related implemented non-E2E regression suites; no blocker remains for this LIA-T06 narrow slice.

## LIA-T07 Windows Setup, Startup, Smoke, and Runtime Integration

BDD: Exact Windows setup prerequisites -> Given the repository is on Windows with the `py` launcher, When `setup.ps1` runs, Then it requires `py -3.12`, creates or verifies the project `.venv`, installs only the exact pins from `requirements.txt`, explicitly runs `.venv\Scripts\python.exe -m playwright install chromium`, and exits immediately on any failed prerequisite or command.

BDD: Loopback-only startup -> Given the project `.venv` exists with Python 3.12 and the requested port is valid and unused, When `start.ps1` runs, Then it starts `loan_interest_accrual.web:app` with the project virtual-environment Python on `127.0.0.1` only; non-loopback addresses, invalid ports, occupied ports, or a missing `.venv` fail before startup.

BDD: Owned two-run smoke lifecycle -> Given a task-owned unused loopback port, When `smoke.ps1` runs, Then it uses hidden `Start-Process` execution of `start.ps1`, polls `/health` and `/static/styles.css`, proves the listener address is only `127.0.0.1` and belongs to the created process tree, writes setup/startup/listener/shutdown evidence, stops only that process tree, verifies the port is released, and repeats the lifecycle a second time on the same port.

RED: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows -q -> FAIL, 10 failed because `scripts/setup.ps1`, `scripts/start.ps1`, and `scripts/smoke.ps1` did not exist; the failures covered static setup/start/smoke contracts, exact Python prerequisite failure, loopback and port rejection, missing `.venv`, occupied-port rejection, startup response, evidence, listener ownership, and two-run cleanup.

### LIA-T07 GREEN and Runtime Fixes

- Fixed the missing-launcher failure message so the fail-fast output contains the exact required `py -3.12` prerequisite.
- Fixed the PowerShell parser failure caused by `$packageName:` by using `${packageName}:`.
- Replaced Windows PowerShell 5-incompatible generic-list serialization with native PowerShell arrays and pipeline JSON serialization.
- Hardened owned-process shutdown against the verified race where a task-owned child or root process exits between discovery and `Stop-Process`; the script rechecks the exact PID, records the already-exited state, and still fails if that PID remains alive.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows -q -> PASS, 10 passed in 15.02s.

GREEN: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q -> PASS, 106 passed in 19.01s.

### Completed Work

- Added Windows-only `setup.ps1` with exact `py -3.12` validation, project `.venv` creation or verification, pinned `requirements.txt` installation, explicit `.venv\Scripts\python.exe -m playwright install chromium`, `pip check`, fail-fast behavior, and setup evidence.
- Added loopback-only `start.ps1` with validated port range, occupied-port rejection, exact project `.venv` Python 3.12 enforcement, and Uvicorn startup for `loan_interest_accrual.web:app` on `127.0.0.1`.
- Added `smoke.ps1` with hidden background startup through `start.ps1`, `/health`, homepage, and local static-resource polling, `Get-NetTCPConnection` listener ownership verification, task-owned process-tree shutdown, port-release verification, and two consecutive runs on the same port.
- Added Windows integration coverage for missing `py -3.12`, missing `.venv`, non-loopback bind rejection, invalid and occupied ports, exact setup/start commands, hidden smoke startup, listener ownership, evidence generation, two-run lifecycle, and final port release.
- Generated `setup.log`, `startup.log`, `listener.json`, and `shutdown.log`; the final evidence contains two `127.0.0.1` listener records on the same task-owned port and confirms both shutdowns released the port.
- Verified no task-owned startup, smoke, or Uvicorn process remained after the completed test runs.
- Playwright Chromium installation is an explicit non-skippable setup step and is statically covered here; actual browser installation and E2E execution remain assigned to LIA-T08 as directed.

### Changed Paths

- `scripts/setup.ps1`
- `scripts/start.ps1`
- `scripts/smoke.ps1`
- `tests/integration/windows/test_windows_scripts.py`
- `.artifacts/loan-interest-accrual-v1/startup/setup.log`
- `.artifacts/loan-interest-accrual-v1/startup/startup.log`
- `.artifacts/loan-interest-accrual-v1/startup/listener.json`
- `.artifacts/loan-interest-accrual-v1/startup/shutdown.log`
- `doc/tasks/loan-interest-accrual-v1/execution-log.md`

### Scope and Blockers

- Modified only the explicitly approved LIA-T07 script, Windows integration-test, startup-evidence, and execution-log paths.
- No application, settings, web, dependency, planning, or task-state file was modified.
- LIA-T07 implementation and required non-E2E verification are complete with no remaining blocker.

## LIA-T07 Fix Round 1 - Redirected Log Handle Release

BDD: Redirected startup logs are released before cleanup -> Given `smoke.ps1` starts the owned root process with redirected stdout and stderr, When the owned process tree is stopped, Then the script explicitly waits for the `Start-Process` root process to exit, disposes its process handle, verifies exclusive access to both redirected files, and only then reads and deletes those files.

BDD: Current listener evidence is atomic and failure-safe -> Given a prior `listener.json` exists or a current smoke run fails during cleanup, When a new smoke starts, Then stale listener evidence is removed before execution and the current run's two listener records are published atomically only after both port-release markers have been persisted.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_windows_scripts.py::test_smoke_waits_for_redirect_handle_release_before_log_cleanup -q` -> FAIL, 1 failed because `smoke.ps1` stops the owned process tree and immediately reads/removes redirected logs without an explicit root-process `WaitForExit`, process disposal, or exclusive-file-access barrier.

GREEN: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke.ps1 -Port 57497 -TimeoutSeconds 30` -> PASS, exit code `0`; `listener.json` contains exactly two current-run records for `127.0.0.1:57497`, `shutdown.log` contains both `[run 1] port released` and `[run 2] port released`, and the post-run listener count is `0`.

### Fix-Round Result

- Fix Round 1 did not close the LIA-T07 independent-verification blocker: the manual smoke passed, but the required redirect-handle-release function was not implemented and the source-contract test still failed.
- The blocker remained open until the code change and complete GREEN verification recorded in Fix Round 2 below.

## LIA-T07 Fix Round 2 - Redirected Process and File Handle Barrier

BDD: Redirected startup logs are released before cleanup -> Given `smoke.ps1` starts the task-owned root process with redirected stdout and stderr, When the owned process tree is stopped, Then `Wait-For-RootProcessExitAndRedirectRelease` waits for the original `Start-Process` process object to exit, calls `WaitForExit` and `Dispose`, verifies each redirected file can be opened with `[System.IO.FileShare]::None` within a fixed timeout, and only then reads and deletes the logs.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_windows_scripts.py::test_smoke_waits_for_redirect_handle_release_before_log_cleanup -q` -> FAIL, 1 failed because `Wait-For-RootProcessExitAndRedirectRelease` was absent.

### Implemented Work

- Added `Wait-For-RootProcessExitAndRedirectRelease` to `scripts/smoke.ps1` and invoked it immediately after `Stop-OwnedProcessTree`.
- The function waits on the original root `System.Diagnostics.Process`, performs the parameterized and parameterless `WaitForExit` calls, and disposes the process object.
- The function validates stdout and stderr separately by opening each file with `[System.IO.FileShare]::None`; lock contention is retried only until the fixed timeout, after which cleanup fails with the last open error.
- Redirected logs are not read or deleted until the exclusive-open checks succeed. No process-selection fallback, exception swallowing, or cleanup of non-owned processes was added.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows\test_windows_scripts.py::test_smoke_waits_for_redirect_handle_release_before_log_cleanup -q` -> PASS, 1 passed.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\windows -q` -> PASS, 11 passed.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, 107 passed.

GREEN: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke.ps1 -Port 49879 -TimeoutSeconds 30` -> PASS, exit code `0`; `listener.json` contains exactly two current-run records for `127.0.0.1:49879`, both shutdown port-release markers are present, no task-owned process or listener remains, and the port is reusable.

### Fix-Round Result

- The LIA-T07 redirect-handle-release blocker is closed only after the implemented code change and all targeted, Windows-suite, complete non-E2E, and fresh-port smoke checks exited `0`.
- Changed paths remained within `scripts/smoke.ps1`, `doc/tasks/loan-interest-accrual-v1/execution-log.md`, and `.artifacts/loan-interest-accrual-v1/startup/**`; tests were not modified.
## LIA-T08 Browser And Release Verification

BDD: Complete real-browser user journey -> Given the application is started through `scripts/start.ps1` on a task-owned unused `127.0.0.1` port with an explicitly configured existing Chromium executable, When a user downloads the template, selects a month, uploads a real valid workbook, previews and exports results, uploads a real invalid workbook, and refreshes the page, Then template and six-sheet workbook contracts pass, invalid input exposes complete errors without preview or export, refresh retains no business state, all browser requests remain loopback-only, the console has no errors, and source workbook hashes remain unchanged.

BDD: Desktop viewport release evidence -> Given Chromium renders the homepage at 1366x768, 1536x864, and 1920x1080, When release visual checks run, Then the document has no horizontal page overflow, controls and text remain unobscured, and screenshots are stored in the release evidence bundle.

BDD: Fail-fast release verification -> Given Python 3.12, pinned dependencies, the explicit `LIA_PLAYWRIGHT_EXECUTABLE`, historical source data, and prior task suites are required release prerequisites, When `scripts/verify-release.ps1` runs, Then it stops at the first missing prerequisite or failed bootstrap, unit, integration, historical, smoke, E2E, or release stage and produces the required acceptance, network, workbook, source-hash, screenshot, trace, and download evidence without converting failure to warning.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\release -q` -> FAIL, 2 failed as expected because `scripts/verify-release.ps1` and `.artifacts/loan-interest-accrual-v1/release/acceptance-matrix.json` do not yet exist.

RED: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\e2e tests\release -q` -> FAIL, 3 failed and 1 passed. The valid February fixture and complete preview/export path passed after aligning the loan dates and movement date with `2024-02`; remaining failures were the real `/favicon.ico` HTTP 404 browser-console error, a vertical line-height rounding false positive in the visual text check, and the acceptance matrix not being emitted after the visual failure.

Required production change: the homepage must serve and locally reference `/favicon.ico` so the real Chromium journey has no unexpected console errors. This is a production web-file change outside the LIA-T08 write scope; the expected local `POST /calculate` HTTP 422 for an intentionally invalid workbook is classified separately as an expected validation response and is not treated as an unhandled console failure.

## LIA-T08 Production Blocker Fix - Local Favicon

Bug: real Chromium requested `/favicon.ico`, received HTTP 404, and reported a console error that blocked LIA-T08 release verification.

Expected: the homepage declares a local favicon, the referenced static asset returns HTTP 200, and no remote or data URL is required.

Reproduction: load `/` in real Chromium without an explicit favicon declaration and observe the fallback `/favicon.ico` request returning HTTP 404.

BDD: Local favicon without remote dependencies -> Given the FastAPI homepage and mounted local static directory, When a browser loads `/` and resolves the declared favicon, Then the homepage references `/static/favicon.svg`, the local SVG request returns HTTP 200 with an SVG media type, and the homepage contains no remote HTTP or HTTPS URL.

RED: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web\test_web_app.py::test_homepage_health_and_local_assets_expose_the_browser_workflow -q` -> FAIL, 1 failed because the homepage did not declare `rel="icon"` and `/static/favicon.svg` did not exist.

Root Cause: the homepage had no explicit favicon declaration, so real Chromium fell back to requesting `/favicon.ico`, which was not served and produced the release-blocking HTTP 404 console error.

Regression test: extended `test_homepage_health_and_local_assets_expose_the_browser_workflow` to require the local favicon link, prohibit remote homepage URLs, request `/static/favicon.svg`, and verify HTTP 200 with an SVG media type.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web\test_web_app.py::test_homepage_health_and_local_assets_expose_the_browser_workflow -q` -> PASS, 1 passed in 0.61s.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\integration\web -q` -> PASS, 8 passed in 0.80s.

GREEN: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\bootstrap tests\unit tests\integration tests\historical -q` -> PASS, 107 passed in 21.29s.

Implemented work: added a compact dependency-free SVG favicon under the existing mounted static directory and declared it in the homepage head with a local `/static/favicon.svg` link. The existing `StaticFiles` mount serves the asset, so no application route or API contract changed.

Risk and regression scope: the change is limited to homepage metadata and one static image. Regression verification covered the favicon behavior, the complete web integration suite, and all implemented non-E2E bootstrap, unit, integration, and historical tests.

Verification: the targeted regression test, complete web integration suite, and complete non-E2E regression all passed after the production change.

Blockers: none for this production fix. LIA-T08 can rerun the real Chromium release journey to confirm the browser no longer falls back to `/favicon.ico`.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\e2e tests\release -q` -> PARTIAL PASS, 3 passed and 1 failed. The complete valid/invalid workbook journey, template and six-sheet inspections, source hash checks, refresh statelessness, loopback request capture, all three desktop viewport overflow/overlap checks, screenshots, traces, downloads, acceptance evidence, and release contract tests completed; the only failing assertion is the unexpected real `/favicon.ico` HTTP 404 console error.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\release -q` -> PASS, 3 passed. Release tests confirm fail-fast script structure, explicit existing-browser-path enforcement with no search or fallback, loopback-only request evidence, exact template/export workbook contracts, immutable source hashes, and non-empty screenshots/traces/downloads.

GREEN: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-release.ps1` reached the intended E2E gate after `7` bootstrap, `53` unit, `44` integration, and `3` historical tests passed and the two-run Windows smoke passed on task-owned port `53425`. The script then failed fast at E2E with `1 failed, 1 passed` because of `/favicon.ico` HTTP 404; it did not downgrade the failure or run the final release stage.

Evidence: `.artifacts/loan-interest-accrual-v1/release/acceptance-matrix.json` reports `29` pass and `3` blocked criteria (`AC-01`, `AC-31`, `AC-32`). The bundle includes `network-requests.json`, `console-errors.json`, `workbook-inspection.json`, `source-hashes.json`, `required-changes.json`, two downloaded `.xlsx` files, six screenshots, four Playwright traces, per-stage logs, and JUnit reports.

Current status: BLOCKED on a required production web change. LIA-T08 test, release-verifier, fixture, and evidence implementation is complete within its write scope, but final GREEN and release acceptance cannot be claimed until the owning production task provides and locally references `/favicon.ico`, after which the target E2E/release command and `scripts/verify-release.ps1` must be rerun.

## Final Release Review Fix Round 1 - Structured Error Chinese Localization

BDD: Web structured errors use stable codes and clear Chinese descriptions -> Given any existing request, workbook, domain, application, or export validation failure reaches the HTTP boundary, When the API returns its structured error list and the browser renders the error table, Then `sheet`, `row`, `column_or_field`, and stable English `error_code` remain unchanged, every user-visible `message` contains clear Simplified Chinese, current English diagnostic phrases such as `must be`, `not found`, `greater than`, and `inside the selected month` are absent, and an unknown error code fails fast instead of exposing the original English message.

RED: `.\.venv\Scripts\python.exe -m pytest tests\integration\web\test_web_app.py::test_calculate_returns_atomic_structured_errors_without_preview tests\integration\web\test_web_app.py::test_export_failure_returns_json_errors_and_no_download -q` -> FAIL, 2 failed. API responses still exposed English source diagnostics including `贷款ID must be non-empty text` and `uploaded bytes are not a readable .xlsx package`.

RED: `.\.venv\Scripts\python.exe -m pytest tests\integration\web\test_web_app.py::test_http_error_catalog_covers_all_production_codes_and_rejects_unknown -q` -> FAIL during collection because `ERROR_MESSAGE_BY_CODE` did not exist in `web/http_models.py`, proving that the HTTP boundary had no explicit complete catalog.

RED: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest tests\e2e\test_user_journey.py::test_complete_real_browser_user_journey -q` -> FAIL, 1 failed. The first E2E assertion revision selected the stable error-code column rather than the adjacent user-visible message column; the selector was corrected to the “错误说明” column before GREEN verification. The API RED cases above are the behavior-level pre-fix evidence for the English-message defect.

### Root Cause

- `application_error_to_http` copied `ApplicationError.message` directly into the HTTP response, so English diagnostics from workbook, domain, application, and export layers leaked into the Chinese web interface.
- Request validation messages were constructed separately in `routes.py`, and no single explicit catalog enforced complete production-code coverage.
- Unknown application error codes had no fail-fast HTTP-boundary guard and could silently expose an unreviewed source message.

### Implemented Work

- Added one explicit `ERROR_MESSAGE_BY_CODE` catalog in `src/loan_interest_accrual/web/http_models.py`.
- Changed `application_error_to_http` to resolve the user-visible message only from the stable `error_code`; the original application-layer English message is no longer used as a fallback.
- Added `error_message_for_code` and `http_error`; unknown codes raise `ValueError` immediately.
- Routed request errors in `routes.py` through the same catalog while preserving the existing HTTP 422 semantics and all structured location fields.
- Added integration coverage for complete production-code equality, Simplified Chinese content, forbidden English diagnostic phrases, unknown-code failure, invalid workbook API responses, and export failure responses.
- Added real-browser coverage for the rendered “错误说明” column.

### Complete Error-Code Catalog

The HTTP boundary explicitly covers all 38 current production codes:

`CALCULABLE_INPUT_MISSING`, `CAPITALIZATION_FLAG_INVALID`, `COLUMN_DUPLICATE`, `COLUMN_MISSING`, `DATE_INVALID`, `DATE_RANGE_INVALID`, `DAY_COUNT_BASIS_INVALID`, `DECIMAL_REQUIRED`, `EMBEDDED_OBJECT_NOT_ALLOWED`, `EXPORT_CHECK_FAILED`, `EXTERNAL_LINK_NOT_ALLOWED`, `FILE_EXTENSION_INVALID`, `FILE_REQUIRED`, `FILE_TOO_LARGE`, `FORMULA_NOT_ALLOWED`, `INTEREST_RATE_INVALID`, `LOAN_ID_DUPLICATE`, `LOAN_ID_REQUIRED`, `LOAN_PERIOD_OUTSIDE_MONTH`, `LOAN_ROW_LIMIT_EXCEEDED`, `MACRO_NOT_ALLOWED`, `MOVEMENT_AMOUNT_INVALID`, `MOVEMENT_DATE_OUTSIDE_MONTH`, `MOVEMENT_LOAN_ID_AMBIGUOUS`, `MOVEMENT_LOAN_ID_NOT_FOUND`, `MOVEMENT_LOAN_ID_REQUIRED`, `MOVEMENT_LOAN_MISMATCH`, `MOVEMENT_ROW_LIMIT_EXCEEDED`, `MOVEMENT_TYPE_INVALID`, `NEGATIVE_PRINCIPAL`, `PERIOD_INVALID`, `PERIOD_REQUIRED`, `RECONCILIATION_FAILED`, `REQUIRED_VALUE_MISSING`, `SHEET_DUPLICATE`, `SHEET_MISSING`, `VALUE_TYPE_INVALID`, `WORKBOOK_OPEN_FAILED`.

GREEN: `.\.venv\Scripts\python.exe -m pytest tests\integration\web -q` -> PASS, 9 passed.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\.venv\Scripts\python.exe -m pytest tests\e2e tests\release -q` -> PASS, 5 passed.

GREEN: `$env:LIA_PLAYWRIGHT_EXECUTABLE='C:\Users\BJB110\AppData\Local\ms-playwright\chromium-1224\chrome-win64\chrome.exe'; .\scripts\verify-release.ps1` -> PASS. Bootstrap `7 passed`, unit `53 passed`, integration `45 passed`, historical `3 passed`, Windows startup smoke passed twice, E2E `2 passed`, and release `3 passed`.

### Release Evidence

- Regenerated `.artifacts/loan-interest-accrual-v1/release/screenshots/invalid-errors.png`; direct visual inspection confirms all 14 displayed error descriptions are clear Simplified Chinese while the stable English error codes remain visible.
- Regenerated `.artifacts/loan-interest-accrual-v1/release/traces/complete-user-journey.zip`.
- Regenerated `.artifacts/loan-interest-accrual-v1/release/acceptance-matrix.json` and the complete release evidence bundle through `scripts/verify-release.ps1`.

### Fix-Round Result

- The structured-error localization blocker is closed.
- No calculation, validation, export, structured location field, error code, or HTTP status behavior changed.
- Remaining blockers: none for Fix Round 1 implementation and verification.

## Final Closeout

- CLEANUP PREVIEW: confirmed preservation of `task.md`, `execution-log.md`, `verification-report.md`, and `task-state.json`; identified only task-owned planning intermediates and temporary browser-install artifacts for removal.
- CLEANUP APPLY: removed `dev-plan.md`, `prd.md`, `request-analysis.md`, `test-plan.md`, `test-report.md`, and `.artifacts/loan-interest-accrual-v1/browser-install/`.
- CLEANUP APPLY: removed generated `__pycache__` directories; no source, test, historical input, release evidence, dependency package, or unrelated user file was removed.
- FINAL VERIFICATION: full release verification passed with bootstrap `7`, unit `53`, integration `45`, historical `3`, E2E `2`, release `3`, and two successful loopback-only Windows startup smoke runs.
- FINAL REVIEW: isolated reviewer Round 2 returned logic, usability, and UI decisions `pass`, `required_changes: []`, and `final_decision: pass`.
- CLOSEOUT: task state advanced from `ready_for_closeout` to `completed`; no Git repository or task-owned worktree required commit, merge, or removal.
- LIVE SMOKE: started the completed application through `scripts/start.ps1` on `127.0.0.1:8000`; both `/health` and `/` returned HTTP `200`, and runtime process details were recorded in `.artifacts/loan-interest-accrual-v1/runtime/app.json`.
