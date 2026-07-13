[CmdletBinding()]
param(
    [Parameter()]
    [ValidateRange(1, 300)]
    [int]$HealthTimeoutSeconds = 30,

    [Parameter()]
    [switch]$NoDialog,

    [Parameter()]
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ApplicationId = "loan-interest-accrual-desktop-v1"
$HostAddress = "127.0.0.1"
$Port = 8000
$HomeUrl = "http://127.0.0.1:8000/"
$HealthUrl = "http://127.0.0.1:8000/health"

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Get-LaunchMutexName {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $normalizedIdentity = (Get-NormalizedPath -Path $ProjectRoot).ToUpperInvariant()
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash(
            [System.Text.Encoding]::UTF8.GetBytes($normalizedIdentity)
        )
    }
    finally {
        $sha256.Dispose()
    }
    $projectHash = [System.BitConverter]::ToString($hashBytes).
        Replace("-", "").
        ToLowerInvariant()
    return "Global\$ApplicationId-$projectHash"
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

function Remove-StaleRuntimeStateIfSafe {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)][string]$SourceRoot
    )

    $recordedProcess = Get-ProcessById -ProcessId ([int]$State.pid)
    if ($null -ne $recordedProcess) {
        return $false
    }

    $matchingProcesses = @(
        Get-MatchingOwnedProcesses -ExpectedSourceRoot $SourceRoot
    )
    if ($matchingProcesses.Count -ne 0) {
        throw "Runtime state identity is untrusted: a matching application process still exists."
    }

    $listeners = @(Get-FixedPortListeners)
    if ($listeners.Count -ne 0) {
        throw "Runtime state identity is untrusted: port 8000 still has a listener."
    }

    Remove-Item -LiteralPath $StatePath -Force
    return $true
}

function Write-RuntimeState {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][int]$ListenerProcessId,
        [Parameter(Mandatory = $true)][string]$OwnershipToken
    )

    $state = [ordered]@{
        schema_version = 2
        application_id = $ApplicationId
        project_root = $ProjectRoot
        host = $HostAddress
        port = $Port
        pid = $ProcessId
        listener_pid = $ListenerProcessId
        launch_token = $OwnershipToken
        started_at = [DateTimeOffset]::Now.ToString("o")
    }
    $temporaryPath = "$StatePath.$OwnershipToken.tmp"
    $backupPath = "$StatePath.$OwnershipToken.bak"
    $json = $state | ConvertTo-Json -Depth 3
    $encoding = New-Object System.Text.UTF8Encoding($false)
    try {
        [System.IO.File]::WriteAllText($temporaryPath, $json, $encoding)
        if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
            [System.IO.File]::Replace(
                $temporaryPath,
                $StatePath,
                $backupPath
            )
        }
        else {
            [System.IO.File]::Move($temporaryPath, $StatePath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
        if (Test-Path -LiteralPath $backupPath -PathType Leaf) {
            Remove-Item -LiteralPath $backupPath -Force
        }
    }
}

function Remove-RuntimeStateIfOwnedByLaunch {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)][string]$ExpectedProjectRoot,
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][int]$ListenerProcessId,
        [Parameter(Mandatory = $true)][string]$OwnershipToken
    )

    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        return $false
    }

    $state = Read-RuntimeState `
        -StatePath $StatePath `
        -ExpectedProjectRoot $ExpectedProjectRoot
    if (
        [int]$state.pid -ne $ProcessId -or
        [int]$state.listener_pid -ne $ListenerProcessId -or
        [string]$state.launch_token -cne $OwnershipToken
    ) {
        return $false
    }

    Remove-Item -LiteralPath $StatePath -Force
    return $true
}

function Get-HealthyOwnedListener {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$SourceRoot
    )

    $process = Get-ProcessById -ProcessId ([int]$State.pid)
    Assert-OwnedProcessIdentity -Process $process -ExpectedSourceRoot $SourceRoot
    $treeIds = @(Get-ProcessTreeIds -RootProcessId ([int]$State.pid))
    $listeners = @(Get-FixedPortListeners)
    $ownedListeners = @(
        $listeners | Where-Object {
            $_.LocalAddress -eq $HostAddress -and
            $treeIds -contains [int]$_.OwningProcess
        }
    )
    if ($ownedListeners.Count -ne 1) {
        return $null
    }

    $listener = $ownedListeners[0]
    if (
        [int]$State.listener_pid -gt 0 -and
        [int]$State.listener_pid -ne [int]$listener.OwningProcess
    ) {
        throw "Runtime state listener identity is untrusted."
    }

    try {
        $health = Invoke-RestMethod `
            -Uri $HealthUrl `
            -Method Get `
            -TimeoutSec 2 `
            -ErrorAction Stop
    }
    catch {
        return $null
    }
    if ([string]$health.status -cne "ok") {
        return $null
    }

    return $listener
}

function Stop-NewOwnedProcess {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$SourceRoot
    )

    $process = Get-ProcessById -ProcessId $ProcessId
    if ($null -eq $process) {
        return
    }
    Assert-OwnedProcessIdentity -Process $process -ExpectedSourceRoot $SourceRoot
    $treeIds = @(Get-ProcessTreeIds -RootProcessId $ProcessId)
    Stop-Process -Id $treeIds -Force -ErrorAction Stop
}

function Show-LaunchFailure {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [Parameter(Mandatory = $true)][string]$RuntimeRoot,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][bool]$SuppressDialog
    )

    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    $logLines = @(
        "Timestamp=$([DateTimeOffset]::Now.ToString('o'))"
        "Status=failed"
        "Error=$Message"
    )
    Set-Content -LiteralPath $LogPath -Encoding UTF8 -Value $logLines

    if (-not $SuppressDialog) {
        $shell = New-Object -ComObject WScript.Shell
        $failureTitle = -join @(
            [char]0x8D37,
            [char]0x6B3E,
            [char]0x5229,
            [char]0x606F,
            [char]0x81EA,
            [char]0x52A8,
            [char]0x8BA1,
            [char]0x63D0,
            [char]0x5DE5,
            [char]0x5177,
            [char]0x542F,
            [char]0x52A8,
            [char]0x5931,
            [char]0x8D25
        )
        $failurePrefix = -join @(
            [char]0x5DE5,
            [char]0x5177,
            [char]0x542F,
            [char]0x52A8,
            [char]0x5931,
            [char]0x8D25
        )
        $logLabel = -join @(
            [char]0x9519,
            [char]0x8BEF,
            [char]0x65E5,
            [char]0x5FD7
        )
        $body = -join @(
            $failurePrefix
            ":`r`n"
            $Message
            "`r`n`r`n"
            $logLabel
            ":"
            $LogPath
        )
        [void]$shell.Popup(
            $body,
            0,
            $failureTitle,
            16
        )
    }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "desktop-launch.ps1 supports Windows only."
}

$projectRoot = Get-NormalizedPath -Path (Split-Path -Parent $PSScriptRoot)
$sourceRoot = Join-Path $projectRoot "src"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runtimeRoot = Join-Path $projectRoot ".artifacts\loan-interest-accrual-desktop-v1\runtime"
$statePath = Join-Path $runtimeRoot "app.json"
$stdoutPath = Join-Path $runtimeRoot "stdout.log"
$stderrPath = Join-Path $runtimeRoot "stderr.log"
$launcherErrorPath = Join-Path $runtimeRoot "launcher-error.log"
$launchMutex = $null
$launchMutexAcquired = $false

trap {
    $message = $_.Exception.Message
    Show-LaunchFailure `
        -Message $message `
        -RuntimeRoot $runtimeRoot `
        -LogPath $launcherErrorPath `
        -SuppressDialog ([bool]$NoDialog)
    [Console]::Error.WriteLine("Desktop application startup failed: $message")
    exit 1
}

try {
    $launchMutexName = Get-LaunchMutexName -ProjectRoot $projectRoot
    $launchMutex = [System.Threading.Mutex]::new($false, $launchMutexName)
    try {
        $launchMutexAcquired = $launchMutex.WaitOne(
            [TimeSpan]::FromSeconds($HealthTimeoutSeconds + 10)
        )
    }
    catch [System.Threading.AbandonedMutexException] {
        $launchMutexAcquired = $true
    }
    if (-not $launchMutexAcquired) {
        throw "Timed out waiting for another desktop launch decision to complete."
    }

    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    if (Test-Path -LiteralPath $launcherErrorPath -PathType Leaf) {
        Remove-Item -LiteralPath $launcherErrorPath -Force
    }

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Project virtual environment Python is missing: $venvPython"
    }
    if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
        throw "Application source directory is missing: $sourceRoot"
    }

    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        $state = Read-RuntimeState `
            -StatePath $statePath `
            -ExpectedProjectRoot $projectRoot
        $staleStateRemoved = Remove-StaleRuntimeStateIfSafe `
            -State $state `
            -StatePath $statePath `
            -SourceRoot $sourceRoot
        if (-not $staleStateRemoved) {
            $listener = Get-HealthyOwnedListener `
                -State $state `
                -SourceRoot $sourceRoot
            if ($null -eq $listener) {
                throw "Recorded application instance is not healthy; refusing to reuse or replace it."
            }

            if (-not $NoBrowser) {
                Start-Process -FilePath $HomeUrl
            }
            Write-Output "Reused healthy desktop application instance."
            return
        }
    }

    $listeners = @(Get-FixedPortListeners)
    if ($listeners.Count -ne 0) {
        throw "Port 8000 is already in use; the fixed desktop port will not be changed or scanned."
    }

    $serverArguments = (
        '-m uvicorn loan_interest_accrual.web:app --app-dir "{0}" --host {1} --port {2}' -f
        $sourceRoot,
        $HostAddress,
        $Port
    )
    $launchToken = [Guid]::NewGuid().ToString("N")
    $serverProcess = $null
    $ownedStateListenerProcessId = 0
    try {
        $serverProcess = Start-Process `
            -FilePath $venvPython `
            -ArgumentList $serverArguments `
            -WorkingDirectory $projectRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -PassThru
        $ownedStateListenerProcessId = [int]$serverProcess.Id

        Write-RuntimeState `
            -StatePath $statePath `
            -ProjectRoot $projectRoot `
            -ProcessId ([int]$serverProcess.Id) `
            -ListenerProcessId $ownedStateListenerProcessId `
            -OwnershipToken $launchToken

        $deadline = [DateTimeOffset]::Now.AddSeconds($HealthTimeoutSeconds)
        $listener = $null
        while ([DateTimeOffset]::Now -lt $deadline) {
            $startupState = [pscustomobject]@{
                pid = [int]$serverProcess.Id
                listener_pid = 0
            }
            $listener = Get-HealthyOwnedListener `
                -State $startupState `
                -SourceRoot $sourceRoot
            if ($null -ne $listener) {
                break
            }
            Start-Sleep -Milliseconds 200
        }

        if ($null -eq $listener) {
            throw "Application health check did not succeed within $HealthTimeoutSeconds seconds."
        }

        $ownedStateListenerProcessId = [int]$listener.OwningProcess
        Write-RuntimeState `
            -StatePath $statePath `
            -ProjectRoot $projectRoot `
            -ProcessId ([int]$serverProcess.Id) `
            -ListenerProcessId $ownedStateListenerProcessId `
            -OwnershipToken $launchToken
    }
    catch {
        $startupError = $_.Exception.Message
        try {
            if ($null -ne $serverProcess) {
                Stop-NewOwnedProcess `
                    -ProcessId ([int]$serverProcess.Id) `
                    -SourceRoot $sourceRoot
                [void](Remove-RuntimeStateIfOwnedByLaunch `
                    -StatePath $statePath `
                    -ExpectedProjectRoot $projectRoot `
                    -ProcessId ([int]$serverProcess.Id) `
                    -ListenerProcessId $ownedStateListenerProcessId `
                    -OwnershipToken $launchToken)
            }
        }
        catch {
            throw "Application startup failed: $startupError Cleanup also failed: $($_.Exception.Message)"
        }
        throw "Application startup failed: $startupError"
    }

    if (-not $NoBrowser) {
        Start-Process -FilePath $HomeUrl
    }
    Write-Output "Desktop application started successfully."
}
finally {
    if ($launchMutexAcquired -and $null -ne $launchMutex) {
        $launchMutex.ReleaseMutex()
    }
    if ($null -ne $launchMutex) {
        $launchMutex.Dispose()
    }
}
