param(
    [string]$ExeName = (
        -join ([int[]](
            26080,
            24418,
            36164,
            20135,
            38271,
            25674,
            33258,
            21160,
            35745,
            25552,
            24037,
            20855
        ) | ForEach-Object { [char]$_ })
    )
)

$ErrorActionPreference = "Stop"

# Default EXE display name: 无形资产长摊自动计提工具
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$buildRequirements = Join-Path $projectRoot "requirements-build.txt"
$entrypoint = Join-Path $projectRoot "src\loan_interest_accrual\desktop_exe.py"
$templatesSource = Join-Path $projectRoot "src\loan_interest_accrual\web\templates"
$staticSource = Join-Path $projectRoot "src\loan_interest_accrual\web\static"
$distRoot = Join-Path $projectRoot "dist"
$artifactRoot = Join-Path $projectRoot ".artifacts\amortization-exe-v1"
$workRoot = Join-Path $artifactRoot "pyinstaller-build"
$specRoot = Join-Path $artifactRoot "pyinstaller-spec"
$outputExe = Join-Path $distRoot "$ExeName.exe"

function Assert-RequiredFile {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description is required: $Path"
    }
}

function Assert-RequiredDirectory {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Description is required: $Path"
    }
}

function Assert-UnderProject {
    param([string]$Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside project: $resolved"
    }
}

Assert-RequiredFile -Path $venvPython -Description "Project virtual environment Python"
Assert-RequiredFile -Path $buildRequirements -Description "Pinned build requirements"
Assert-RequiredFile -Path $entrypoint -Description "Standalone EXE entrypoint"
Assert-RequiredDirectory -Path $templatesSource -Description "Web templates directory"
Assert-RequiredDirectory -Path $staticSource -Description "Web static directory"

New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null

Get-ChildItem -LiteralPath $distRoot -Filter "*.exe" -File |
    ForEach-Object {
        Assert-UnderProject -Path $_.FullName
        Remove-Item -LiteralPath $_.FullName -Force
    }

foreach ($path in @($workRoot, $specRoot)) {
    Assert-UnderProject -Path $path
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

Assert-UnderProject -Path $outputExe
if (Test-Path -LiteralPath $outputExe) {
    Remove-Item -LiteralPath $outputExe -Force
}

& $venvPython -m pip install --requirement $buildRequirements
if ($LASTEXITCODE -ne 0) {
    throw "Build dependency installation failed."
}

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $ExeName `
    --paths (Join-Path $projectRoot "src") `
    --distpath $distRoot `
    --workpath $workRoot `
    --specpath $specRoot `
    --add-data "$templatesSource;loan_interest_accrual\web\templates" `
    --add-data "$staticSource;loan_interest_accrual\web\static" `
    $entrypoint
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Assert-RequiredFile -Path $outputExe -Description "Built EXE"

$file = Get-Item -LiteralPath $outputExe
[pscustomobject]@{
    status = "pass"
    exe = $file.FullName
    size_bytes = $file.Length
    runtime_dependency = "self-contained PyInstaller onefile"
} | ConvertTo-Json -Depth 3
