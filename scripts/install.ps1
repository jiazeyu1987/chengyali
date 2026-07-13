[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$DesktopDirectory = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::DesktopDirectory
    ),

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$StartMenuDirectory = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::Programs
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Assert-OwnedShortcut {
    param(
        [Parameter(Mandatory = $true)]$Shell,
        [Parameter(Mandatory = $true)][string]$ShortcutPath,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget,
        [Parameter(Mandatory = $true)][string]$ExpectedLaunchScript
    )

    if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) {
        return
    }

    $shortcut = $Shell.CreateShortcut($ShortcutPath)
    $target = Get-NormalizedPath -Path ([string]$shortcut.TargetPath)
    $expectedTargetPath = Get-NormalizedPath -Path $ExpectedTarget
    $expectedFileArgument = '-File "{0}"' -f $ExpectedLaunchScript
    if (
        $target -ine $expectedTargetPath -or
        ([string]$shortcut.Arguments).IndexOf(
            $expectedFileArgument,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -lt 0
    ) {
        throw "Existing shortcut is not owned by this application: $ShortcutPath"
    }
}

function Save-ApplicationShortcut {
    param(
        [Parameter(Mandatory = $true)]$Shell,
        [Parameter(Mandatory = $true)][string]$ShortcutPath,
        [Parameter(Mandatory = $true)][string]$PowerShellPath,
        [Parameter(Mandatory = $true)][string]$LaunchScript,
        [Parameter(Mandatory = $true)][string]$ProjectRoot
    )

    $shortcut = $Shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $PowerShellPath
    $shortcut.Arguments = (
        '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f
        $LaunchScript
    )
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Loan Interest Accrual"
    $shortcut.Save()
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "install.ps1 supports Windows only."
}

$projectRoot = Get-NormalizedPath -Path (Split-Path -Parent $PSScriptRoot)
$setupScript = Join-Path $PSScriptRoot "setup.ps1"
$launchScript = Join-Path $PSScriptRoot "desktop-launch.ps1"
$stopScript = Join-Path $PSScriptRoot "desktop-stop.ps1"
$uninstallScript = Join-Path $PSScriptRoot "uninstall.ps1"
$powershellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcutBaseName = -join @(
    [char]0x8D37,
    [char]0x6B3E,
    [char]0x5229,
    [char]0x606F,
    [char]0x81EA,
    [char]0x52A8,
    [char]0x8BA1,
    [char]0x63D0,
    [char]0x5DE5,
    [char]0x5177
)
$shortcutName = "$shortcutBaseName.lnk"

foreach ($requiredScript in @(
    $setupScript,
    $launchScript,
    $stopScript,
    $uninstallScript
)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required installation script is missing: $requiredScript"
    }
}
if (-not (Test-Path -LiteralPath $powershellPath -PathType Leaf)) {
    throw "Windows PowerShell executable is missing: $powershellPath"
}

$desktopDirectoryPath = Get-NormalizedPath -Path $DesktopDirectory
$startMenuDirectoryPath = Get-NormalizedPath -Path $StartMenuDirectory
$desktopShortcut = Join-Path $desktopDirectoryPath $shortcutName
$startMenuShortcut = Join-Path $startMenuDirectoryPath $shortcutName
$shell = New-Object -ComObject WScript.Shell

Assert-OwnedShortcut `
    -Shell $shell `
    -ShortcutPath $desktopShortcut `
    -ExpectedTarget $powershellPath `
    -ExpectedLaunchScript $launchScript
Assert-OwnedShortcut `
    -Shell $shell `
    -ShortcutPath $startMenuShortcut `
    -ExpectedTarget $powershellPath `
    -ExpectedLaunchScript $launchScript

& $powershellPath `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File $setupScript
if ($LASTEXITCODE -ne 0) {
    throw "Required setup failed with exit code $LASTEXITCODE; shortcuts were not created."
}

New-Item -ItemType Directory -Path $desktopDirectoryPath -Force | Out-Null
New-Item -ItemType Directory -Path $startMenuDirectoryPath -Force | Out-Null

$desktopExisted = Test-Path -LiteralPath $desktopShortcut -PathType Leaf
$startMenuExisted = Test-Path -LiteralPath $startMenuShortcut -PathType Leaf
try {
    Save-ApplicationShortcut `
        -Shell $shell `
        -ShortcutPath $desktopShortcut `
        -PowerShellPath $powershellPath `
        -LaunchScript $launchScript `
        -ProjectRoot $projectRoot
    Save-ApplicationShortcut `
        -Shell $shell `
        -ShortcutPath $startMenuShortcut `
        -PowerShellPath $powershellPath `
        -LaunchScript $launchScript `
        -ProjectRoot $projectRoot
}
catch {
    if (-not $desktopExisted -and (Test-Path -LiteralPath $desktopShortcut)) {
        Remove-Item -LiteralPath $desktopShortcut -Force
    }
    if (-not $startMenuExisted -and (Test-Path -LiteralPath $startMenuShortcut)) {
        Remove-Item -LiteralPath $startMenuShortcut -Force
    }
    throw
}

Write-Output "Desktop and Start Menu shortcuts were installed successfully."
