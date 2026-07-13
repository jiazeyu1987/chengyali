# Loan Interest Accrual

Local Windows tool for loan interest accrual calculation, Excel template import, preview, and export.

## Prerequisites
- Windows.
- Python 3.12 available through the Windows Python launcher as `py -3.12`.
- PowerShell 5+.

## Setup
From the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The setup script creates `.venv` and installs the pinned dependencies from `requirements.txt`.

## Run
Start the local web app on `127.0.0.1:8000`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Install desktop and Start Menu shortcuts:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

## Test
Run the automated test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Some E2E/release checks require Playwright Chromium to be installed and may require `LIA_PLAYWRIGHT_EXECUTABLE` to point to the Chromium executable.

## Package
Build the Windows single-file executable:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1
```

The packaged `.exe` is written to `dist\`. Build intermediates and generated release evidence are local artifacts and are not committed.
