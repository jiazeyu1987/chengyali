[CmdletBinding()]
param(
    [Parameter()]
    [ValidateRange(1, 60)]
    [int]$TimeoutSeconds = 10,

    [Parameter()]
    [ValidateRange(0, 5000)]
    [int]$DelayMilliseconds = 0,

    [Parameter()]
    [switch]$Detach,

    [Parameter()]
    [switch]$DetachedWorker
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

function Get-ProcessById {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    return Get-CimInstance `
        -ClassName Win32_Process `
        -Filter "ProcessId = $ProcessId" `
        -ErrorAction Stop
}

function Get-RequiredProcessCreationTime {
    param([Parameter(Mandatory = $true)]$Process)

    if (
        $Process.PSObject.Properties.Name -notcontains "CreationDate" -or
        $null -eq $Process.CreationDate
    ) {
        throw "Runtime process identity is untrusted: creation time is unavailable."
    }
    try {
        return [DateTimeOffset]$Process.CreationDate
    }
    catch {
        throw "Runtime process identity is untrusted: creation time is invalid."
    }
}

function Get-ProcessTreeIds {
    param([Parameter(Mandatory = $true)][int]$RootProcessId)

    $processes = @(
        Get-CimInstance -ClassName Win32_Process -ErrorAction Stop
    )
    $processById = @{}
    foreach ($process in $processes) {
        $processById[[int]$process.ProcessId] = $process
    }
    if (-not $processById.ContainsKey($RootProcessId)) {
        throw "Runtime process identity is untrusted: root process is unavailable."
    }
    $owned = New-Object "System.Collections.Generic.HashSet[int]"
    [void]$owned.Add($RootProcessId)

    do {
        $added = $false
        foreach ($process in $processes) {
            $processId = [int]$process.ProcessId
            $parentProcessId = [int]$process.ParentProcessId
            if ($owned.Contains($parentProcessId) -and -not $owned.Contains($processId)) {
                $parentProcess = $processById[$parentProcessId]
                $parentCreated = Get-RequiredProcessCreationTime -Process $parentProcess
                $processCreated = Get-RequiredProcessCreationTime -Process $process
                if ($processCreated -lt $parentCreated) {
                    continue
                }
                [void]$owned.Add($processId)
                $added = $true
            }
        }
    } while ($added)

    return @($owned | ForEach-Object { [int]$_ })
}

function Assert-OwnedProcessIdentity {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$ExpectedSourceRoot
    )

    if ($null -eq $Process) {
        throw "Runtime state is stale: the recorded process does not exist."
    }
    if ([string]::IsNullOrWhiteSpace([string]$Process.CommandLine)) {
        throw "Runtime process identity is untrusted: command line is unavailable."
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
            throw "Runtime process identity is untrusted: command line does not match this project."
        }
    }
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

function Read-RuntimeState {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)][string]$ExpectedProjectRoot
    )

    try {
        $state = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
        $requiredProperties = @(
            "schema_version",
            "application_id",
            "project_root",
            "host",
            "port",
            "pid",
            "listener_pid",
            "launch_token"
        )
        foreach ($property in $requiredProperties) {
            if ($state.PSObject.Properties.Name -notcontains $property) {
                throw "Missing runtime state property: $property"
            }
        }

        if (
            [int]$state.schema_version -ne 2 -or
            [string]$state.application_id -cne $ApplicationId -or
            (Get-NormalizedPath -Path ([string]$state.project_root)) -ine $ExpectedProjectRoot -or
            [string]$state.host -cne $HostAddress -or
            [int]$state.port -ne $Port -or
            [int]$state.pid -le 0 -or
            [int]$state.listener_pid -le 0 -or
            [string]$state.launch_token -notmatch "^[0-9a-f]{32}$"
        ) {
            throw "Runtime state values do not match this application."
        }
    }
    catch {
        throw "Runtime state identity is untrusted: $($_.Exception.Message)"
    }

    return $state
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "desktop-stop.ps1 supports Windows only."
}

$projectRoot = Get-NormalizedPath -Path (Split-Path -Parent $PSScriptRoot)
$sourceRoot = Join-Path $projectRoot "src"
$runtimeRoot = Join-Path $projectRoot ".artifacts\loan-interest-accrual-desktop-v1\runtime"
$statePath = Join-Path $runtimeRoot "app.json"

if ($Detach) {
    if ($DetachedWorker) {
        throw "Detached worker mode cannot request another detach."
    }
    $escapedScriptPath = $PSCommandPath.Replace("'", "''")
    $workerExpression = (
        "& '{0}' -TimeoutSeconds {1} -DelayMilliseconds {2} -DetachedWorker" -f
        $escapedScriptPath,
        $TimeoutSeconds,
        $DelayMilliseconds
    )
    $encodedWorker = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes($workerExpression)
    )
    $workerCommandLine = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand {0}" -f
        $encodedWorker
    )
    $created = Invoke-CimMethod `
        -ClassName Win32_Process `
        -MethodName Create `
        -Arguments @{ CommandLine = $workerCommandLine } `
        -ErrorAction Stop
    if ([int]$created.ReturnValue -ne 0 -or [int]$created.ProcessId -le 0) {
        throw "Windows could not create the detached desktop stop worker."
    }
    Write-Output "Detached desktop stop worker started successfully."
    return
}

if ($DelayMilliseconds -gt 0) {
    Start-Sleep -Milliseconds $DelayMilliseconds
}

if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw "Desktop application runtime state is missing: $statePath"
}

$state = Read-RuntimeState `
    -StatePath $statePath `
    -ExpectedProjectRoot $projectRoot
$rootProcess = Get-ProcessById -ProcessId ([int]$state.pid)
if ($null -eq $rootProcess) {
    $matchingProcesses = @(
        Get-MatchingOwnedProcesses -ExpectedSourceRoot $sourceRoot
    )
    if ($matchingProcesses.Count -ne 0) {
        throw "Runtime state identity is untrusted: a matching application process still exists."
    }

    $listeners = @(Get-FixedPortListeners)
    if ($listeners.Count -ne 0) {
        throw "Runtime state identity is untrusted: port 8000 still has a listener."
    }

    Remove-Item -LiteralPath $statePath -Force
    Write-Output "Stale desktop application runtime state was removed safely."
    return
}
Assert-OwnedProcessIdentity `
    -Process $rootProcess `
    -ExpectedSourceRoot $sourceRoot

$ownedTreeIds = @(Get-ProcessTreeIds -RootProcessId ([int]$state.pid))
$terminationIds = @(
    $ownedTreeIds | Where-Object { [int]$_ -ne [int]$PID }
)
if ($terminationIds.Count -eq 0) {
    throw "Runtime process identity is untrusted: no application process remains to stop."
}
$listeners = @(Get-FixedPortListeners)
$ownedListeners = @(
    $listeners | Where-Object {
        $_.LocalAddress -eq $HostAddress -and
        $ownedTreeIds -contains [int]$_.OwningProcess
    }
)
if ($ownedListeners.Count -ne 1) {
    throw "Runtime process identity is untrusted: expected one owned 127.0.0.1:8000 listener."
}
if ([int]$ownedListeners[0].OwningProcess -ne [int]$state.listener_pid) {
    throw "Runtime process identity is untrusted: listener PID does not match runtime state."
}

Stop-Process -Id $terminationIds -Force -ErrorAction Stop

$deadline = [DateTimeOffset]::Now.AddSeconds($TimeoutSeconds)
do {
    $remainingProcesses = @(
        foreach ($processId in $terminationIds) {
            $candidate = Get-ProcessById -ProcessId ([int]$processId)
            if (
                $null -ne $candidate -and
                $candidate.PSObject.Properties.Name -contains "ProcessId" -and
                [int]$candidate.ProcessId -eq [int]$processId
            ) {
                $candidate
            }
        }
    )
    $remainingListeners = @(Get-FixedPortListeners)
    if ($remainingProcesses.Count -eq 0 -and $remainingListeners.Count -eq 0) {
        break
    }
    Start-Sleep -Milliseconds 100
} while ([DateTimeOffset]::Now -lt $deadline)

if ($remainingProcesses.Count -ne 0) {
    throw "Owned process tree did not exit within $TimeoutSeconds seconds."
}
if ($remainingListeners.Count -ne 0) {
    throw "Port 8000 was not released within $TimeoutSeconds seconds."
}

Remove-Item -LiteralPath $statePath -Force
Write-Output "Desktop application stopped successfully."
