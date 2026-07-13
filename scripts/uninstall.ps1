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

$ApplicationId = "loan-interest-accrual-desktop-v1"
$HostAddress = "127.0.0.1"
$Port = 8000

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
        return $false
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
        throw "Shortcut identity is untrusted and will not be removed: $ShortcutPath"
    }

    return $true
}

if (-not (Get-Command Invoke-DesktopNetstat -CommandType Function -ErrorAction Ignore)) {
    function Invoke-DesktopNetstat {
        $netstatPath = Join-Path $env:SystemRoot "System32\netstat.exe"
        if (-not (Test-Path -LiteralPath $netstatPath -PathType Leaf)) {
            throw "Required Windows netstat executable is missing: $netstatPath"
        }
        $output = @(& $netstatPath -ano -p TCP)
        if ($LASTEXITCODE -ne 0) {
            throw "Windows netstat failed with exit code $LASTEXITCODE."
        }
        return $output
    }
}

function Get-FixedPortListeners {
    $listeners = @()
    foreach ($line in @(Invoke-DesktopNetstat)) {
        $parts = @(([string]$line).Trim() -split "\s+")
        if (
            $parts.Count -lt 5 -or
            $parts[0] -cne "TCP" -or
            $parts[3] -cne "LISTENING"
        ) {
            continue
        }
        $localEndpoint = [string]$parts[1]
        $separator = $localEndpoint.LastIndexOf(":")
        if ($separator -le 0) {
            continue
        }
        $address = $localEndpoint.Substring(0, $separator).Trim("[", "]")
        $localPort = 0
        $owningProcess = 0
        if (
            -not [int]::TryParse(
                $localEndpoint.Substring($separator + 1),
                [ref]$localPort
            ) -or
            -not [int]::TryParse([string]$parts[4], [ref]$owningProcess)
        ) {
            continue
        }
        if (
            $localPort -eq $Port -and (
                $address -eq $HostAddress -or
                $address -eq "0.0.0.0" -or
                $address -eq "::"
            )
        ) {
            $listeners += [pscustomobject]@{
                LocalAddress = $address
                LocalPort = $localPort
                OwningProcess = $owningProcess
            }
        }
    }
    return $listeners
}

function Test-OwnedProcessIdentity {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$ExpectedSourceRoot
    )

    if (
        $null -eq $Process -or
        [string]::IsNullOrWhiteSpace([string]$Process.CommandLine)
    ) {
        return $false
    }

    $commandLine = [string]$Process.CommandLine
    $requiredTokens = @(
        "-m uvicorn",
        "loan_interest_accrual.web:app",
        "--app-dir",
        (Get-NormalizedPath -Path $ExpectedSourceRoot),
        "--host $HostAddress",
        "--port $Port"
    )
    foreach ($token in $requiredTokens) {
        if ($commandLine.IndexOf($token, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            return $false
        }
    }

    return $true
}

function Get-MatchingOwnedProcesses {
    param([Parameter(Mandatory = $true)][string]$ExpectedSourceRoot)

    return @(
        Get-CimInstance -ClassName Win32_Process -ErrorAction Stop |
            Where-Object {
                Test-OwnedProcessIdentity `
                    -Process $_ `
                    -ExpectedSourceRoot $ExpectedSourceRoot
            }
    )
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "uninstall.ps1 supports Windows only."
}

$projectRoot = Get-NormalizedPath -Path (Split-Path -Parent $PSScriptRoot)
$sourceRoot = Join-Path $projectRoot "src"
$launchScript = Join-Path $PSScriptRoot "desktop-launch.ps1"
$stopScript = Join-Path $PSScriptRoot "desktop-stop.ps1"
$powershellPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$runtimeRoot = Join-Path $projectRoot ".artifacts\loan-interest-accrual-desktop-v1\runtime"
$statePath = Join-Path $runtimeRoot "app.json"
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
$desktopShortcut = Join-Path (Get-NormalizedPath -Path $DesktopDirectory) $shortcutName
$startMenuShortcut = Join-Path (Get-NormalizedPath -Path $StartMenuDirectory) $shortcutName

if (-not (Test-Path -LiteralPath $powershellPath -PathType Leaf)) {
    throw "Windows PowerShell executable is missing: $powershellPath"
}
if (-not (Test-Path -LiteralPath $stopScript -PathType Leaf)) {
    throw "Required stop script is missing: $stopScript"
}

$shell = New-Object -ComObject WScript.Shell
$desktopOwned = Assert-OwnedShortcut `
    -Shell $shell `
    -ShortcutPath $desktopShortcut `
    -ExpectedTarget $powershellPath `
    -ExpectedLaunchScript $launchScript
$startMenuOwned = Assert-OwnedShortcut `
    -Shell $shell `
    -ShortcutPath $startMenuShortcut `
    -ExpectedTarget $powershellPath `
    -ExpectedLaunchScript $launchScript
$runtimeExists = Test-Path -LiteralPath $runtimeRoot -PathType Container

if (-not $desktopOwned -and -not $startMenuOwned -and -not $runtimeExists) {
    throw "No owned desktop installation artifacts were found."
}

if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    & $powershellPath `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $stopScript
    if ($LASTEXITCODE -ne 0) {
        throw "Owned application stop failed with exit code $LASTEXITCODE; uninstall was not continued."
    }
}
else {
    $matchingProcesses = @(
        Get-MatchingOwnedProcesses -ExpectedSourceRoot $sourceRoot
    )
    $listeners = @(Get-FixedPortListeners)
    if ($matchingProcesses.Count -ne 0) {
        throw "Desktop application runtime state is missing while a matching application process still exists; uninstall was refused and installation artifacts were preserved."
    }
    if ($listeners.Count -ne 0) {
        throw "Desktop application runtime state is missing while port 8000 still has a listener; uninstall was refused and installation artifacts were preserved."
    }
}

if ($desktopOwned) {
    Remove-Item -LiteralPath $desktopShortcut -Force
}
if ($startMenuOwned) {
    Remove-Item -LiteralPath $startMenuShortcut -Force
}
if ($runtimeExists) {
    $expectedRuntimeRoot = Get-NormalizedPath -Path (
        Join-Path $projectRoot ".artifacts\loan-interest-accrual-desktop-v1\runtime"
    )
    if ((Get-NormalizedPath -Path $runtimeRoot) -cne $expectedRuntimeRoot) {
        throw "Runtime path identity is untrusted and will not be removed."
    }
    Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
}

Write-Output "Desktop shortcuts and runtime state were uninstalled successfully."
