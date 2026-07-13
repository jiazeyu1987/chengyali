[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$HostAddress = "127.0.0.1",

    [Parameter()]
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "start.ps1 supports Windows only."
}

if ($HostAddress -cne "127.0.0.1") {
    throw "HostAddress must be exactly 127.0.0.1."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$sourceRoot = Join-Path $projectRoot "src"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "Project virtual environment Python is missing: $venvPython"
}

$venvVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Assert-LastExitCode "Virtual environment Python verification"
if ($venvVersion.Trim() -ne "3.12") {
    throw "Project virtual environment must use Python 3.12; found $($venvVersion.Trim())."
}

$existingListeners = @(
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
)
if ($existingListeners.Count -ne 0) {
    throw "Port $Port is already in use."
}

Set-Location -LiteralPath $projectRoot
& $venvPython -m uvicorn loan_interest_accrual.web:app --app-dir $sourceRoot --host $HostAddress --port $Port
Assert-LastExitCode "Uvicorn startup"
