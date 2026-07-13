[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "setup.ps1 supports Windows only."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$evidenceRoot = Join-Path $projectRoot ".artifacts\loan-interest-accrual-v1\startup"
$setupLog = Join-Path $evidenceRoot "setup.log"

New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
Set-Content -LiteralPath $setupLog -Encoding UTF8 -Value @(
    "Timestamp=$([DateTimeOffset]::Now.ToString('o'))"
    "Status=started"
)

try {
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
        throw "Pinned requirements file is missing: $requirementsPath"
    }

    try {
        $pyLauncher = Get-Command py.exe -ErrorAction Stop
    }
    catch {
        throw "Required py -3.12 launcher is unavailable."
    }
    Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "Launcher=$($pyLauncher.Source)"

    & py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    Assert-LastExitCode "py -3.12 verification"
    Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "PythonLauncher=3.12"

    Set-Location -LiteralPath $projectRoot
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        & py -3.12 -m venv .venv
        Assert-LastExitCode "Python 3.12 virtual environment creation"
    }

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Virtual environment Python is missing: $venvPython"
    }

    $venvVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Assert-LastExitCode "Virtual environment Python verification"
    if ($venvVersion.Trim() -ne "3.12") {
        throw "Project virtual environment must use Python 3.12; found $($venvVersion.Trim())."
    }
    Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "VenvPython=3.12"

    & $venvPython -m pip install --disable-pip-version-check --requirement $requirementsPath
    Assert-LastExitCode "Pinned requirements installation"
    Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "PinnedRequirements=installed"

    & $venvPython -m pip check
    Assert-LastExitCode "Installed dependency verification"

    Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "Status=passed"
    Write-Output "Windows setup completed successfully."
}
catch {
    Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value @(
        "Status=failed"
        "Error=$($_.Exception.Message)"
    )
    Write-Error "setup.ps1 failed: $($_.Exception.Message)"
    exit 1
}
