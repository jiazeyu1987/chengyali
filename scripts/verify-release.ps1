[CmdletBinding()]
param(
    [Parameter()]
    [ValidateRange(1, 300)]
    [int]$SmokeTimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Normalize-PackageName {
    param([Parameter(Mandatory = $true)][string]$Name)

    return (($Name.ToLowerInvariant() -replace "[-_.]+", "-").Trim())
}

function Invoke-PytestStage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Targets
    )

    $logPath = Join-Path $logsRoot "$Name.log"
    $junitPath = Join-Path $junitRoot "$Name.xml"
    $arguments = @(
        "-m"
        "pytest"
        "-p"
        "no:cacheprovider"
    ) + $Targets + @(
        "-q"
        "--junitxml=$junitPath"
    )
    & $venvPython @arguments *> $logPath
    $exitCode = $LASTEXITCODE
    Get-Content -LiteralPath $logPath -Encoding UTF8
    if ($exitCode -ne 0) {
        throw "$Name failed with exit code $exitCode. See $logPath"
    }
}

function Get-UnusedLoopbackPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    try {
        $listener.Start()
        return [int]$listener.LocalEndpoint.Port
    }
    finally {
        $listener.Stop()
    }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "verify-release.ps1 supports Windows only."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$releaseRoot = Join-Path $projectRoot ".artifacts\loan-interest-accrual-v1\release"
$desktopReleaseRoot = Join-Path $projectRoot (
    ".artifacts\loan-interest-accrual-desktop-v1\release"
)
$logsRoot = Join-Path $releaseRoot "logs"
$junitRoot = Join-Path $releaseRoot "junit"
$historicalSources = @(
    Get-ChildItem -LiteralPath (Join-Path $projectRoot "doc") `
        -Filter "*.xlsx" `
        -File
)

$requiredTaskFiles = @(
    "doc\tasks\loan-interest-accrual-v1\task.md"
    "doc\tasks\loan-interest-accrual-v1\execution-log.md"
    "doc\tasks\loan-interest-accrual-v1\verification-report.md"
    "doc\tasks\loan-interest-accrual-v1\task-state.json"
    "doc\tasks\loan-interest-accrual-desktop-v1\task.md"
    "doc\tasks\loan-interest-accrual-desktop-v1\execution-log.md"
    "doc\tasks\loan-interest-accrual-desktop-v1\verification-report.md"
)
foreach ($relativePath in $requiredTaskFiles) {
    $requiredPath = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required task history file is missing: $requiredPath"
    }
}

try {
    $pyLauncher = Get-Command py.exe -ErrorAction Stop
}
catch {
    throw "Required py -3.12 launcher is unavailable."
}
& $pyLauncher.Source -3.12 -c `
    "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
Assert-LastExitCode "py -3.12 verification"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "Project virtual environment Python is missing: $venvPython"
}
$venvVersion = & $venvPython -c `
    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Assert-LastExitCode "Virtual environment Python verification"
if ($venvVersion.Trim() -ne "3.12") {
    throw "Project virtual environment must use Python 3.12."
}

if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "Pinned requirements file is missing: $requirementsPath"
}
& $venvPython -m pip check
Assert-LastExitCode "Installed dependency verification"
Set-Location -LiteralPath $projectRoot
$installed = @{}
foreach ($line in @(& $venvPython -m pip freeze --local)) {
    if ($line -match "^([^=]+)==(.+)$") {
        $installed[(Normalize-PackageName -Name $Matches[1])] = $Matches[2].Trim()
    }
}
Assert-LastExitCode "Installed dependency inventory"
foreach ($line in @(Get-Content -LiteralPath $requirementsPath -Encoding UTF8)) {
    $entry = $line.Trim()
    if ($entry.Length -eq 0 -or $entry.StartsWith("#")) {
        continue
    }
    if ($entry -notmatch "^([^=]+)==(.+)$") {
        throw "Requirement is not exactly pinned: $entry"
    }
    $packageName = Normalize-PackageName -Name $Matches[1]
    $requiredVersion = $Matches[2].Trim()
    if (-not $installed.ContainsKey($packageName)) {
        throw "Required package is not installed: $packageName==$requiredVersion"
    }
    if ($installed[$packageName] -ne $requiredVersion) {
        throw (
            "Installed package version mismatch for ${packageName}: " +
            "required $requiredVersion, found $($installed[$packageName])."
        )
    }
}

$browserExecutable = [Environment]::GetEnvironmentVariable(
    "LIA_PLAYWRIGHT_EXECUTABLE",
    "Process"
)
if ([string]::IsNullOrWhiteSpace($browserExecutable)) {
    throw "LIA_PLAYWRIGHT_EXECUTABLE must explicitly point to Chromium."
}
if (-not (Test-Path -LiteralPath $browserExecutable -PathType Leaf)) {
    throw "LIA_PLAYWRIGHT_EXECUTABLE does not exist: $browserExecutable"
}

if ($historicalSources.Count -eq 0) {
    throw "Required historical source workbook is missing under doc."
}
$historicalBefore = @{}
foreach ($source in $historicalSources) {
    $historicalBefore[$source.FullName] = (
        Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}

if (Test-Path -LiteralPath $releaseRoot) {
    Remove-Item -LiteralPath $releaseRoot -Recurse -Force
}
if (Test-Path -LiteralPath $desktopReleaseRoot) {
    Remove-Item -LiteralPath $desktopReleaseRoot -Recurse -Force
}
foreach ($directory in @(
    $releaseRoot
    $logsRoot
    $junitRoot
    (Join-Path $releaseRoot "downloads")
    (Join-Path $releaseRoot "screenshots")
    (Join-Path $releaseRoot "traces")
    $desktopReleaseRoot
    (Join-Path $desktopReleaseRoot "screenshots")
)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$env:PYTHONDONTWRITEBYTECODE = "1"

Invoke-PytestStage -Name "bootstrap" -Targets @("tests\bootstrap")
Invoke-PytestStage -Name "unit" -Targets @("tests\unit")
Invoke-PytestStage -Name "integration" -Targets @("tests\integration")
Invoke-PytestStage -Name "historical" -Targets @("tests\historical")

$historicalEvidence = @()
foreach ($source in $historicalSources) {
    $after = (
        Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $before = $historicalBefore[$source.FullName]
    if ($after -ne $before) {
        throw "Historical source workbook hash changed: $($source.FullName)"
    }
    $historicalEvidence += [pscustomobject]@{
        path = $source.FullName
        before = $before
        after = $after
        unchanged = $true
    }
}
[pscustomobject]@{
    historical_source = $historicalEvidence
} |
    ConvertTo-Json -Depth 10 |
    Set-Content `
        -LiteralPath (Join-Path $releaseRoot "source-hashes.json") `
        -Encoding UTF8

$smokePort = Get-UnusedLoopbackPort
$smokeLog = Join-Path $logsRoot "smoke.log"
& powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File (Join-Path $projectRoot "scripts\smoke.ps1") `
    -Port $smokePort `
    -TimeoutSeconds $SmokeTimeoutSeconds *> $smokeLog
$smokeExitCode = $LASTEXITCODE
Get-Content -LiteralPath $smokeLog -Encoding UTF8
if ($smokeExitCode -ne 0) {
    throw "Windows smoke failed with exit code $smokeExitCode. See $smokeLog"
}

Invoke-PytestStage -Name "e2e" -Targets @("tests\e2e")

$sourceHashesPath = Join-Path $releaseRoot "source-hashes.json"
if (-not (Test-Path -LiteralPath $sourceHashesPath -PathType Leaf)) {
    throw "E2E source hash evidence is missing: $sourceHashesPath"
}
$sourceHashes = Get-Content -LiteralPath $sourceHashesPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$historicalEvidence = @()
foreach ($source in $historicalSources) {
    $after = (
        Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $before = $historicalBefore[$source.FullName]
    if ($after -ne $before) {
        throw "Historical source workbook hash changed: $($source.FullName)"
    }
    $historicalEvidence += [pscustomobject]@{
        path = $source.FullName
        before = $before
        after = $after
        unchanged = $true
    }
}
$sourceHashes | Add-Member `
    -NotePropertyName "historical_source" `
    -NotePropertyValue $historicalEvidence `
    -Force
$sourceHashes |
    ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath $sourceHashesPath -Encoding UTF8

Invoke-PytestStage -Name "release" -Targets @("tests\release")

$summary = [pscustomobject]@{
    status = "pass"
    completed_at = [DateTimeOffset]::Now.ToString("o")
    python = $venvVersion.Trim()
    browser_executable = $browserExecutable
    smoke_port = $smokePort
    stages = @(
        "bootstrap"
        "unit"
        "integration"
        "historical"
        "smoke"
        "e2e"
        "release"
    )
}
$summary |
    ConvertTo-Json -Depth 5 |
    Set-Content `
        -LiteralPath (Join-Path $releaseRoot "release-summary.json") `
        -Encoding UTF8

Write-Output "Release verification passed. Evidence: $releaseRoot"
