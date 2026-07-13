[CmdletBinding()]
param(
    [Parameter()]
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,

    [Parameter()]
    [ValidateRange(1, 300)]
    [int]$TimeoutSeconds = 30
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

function Get-OwnedProcessIds {
    param([Parameter(Mandatory = $true)][int]$RootProcessId)

    $snapshot = @(
        Get-CimInstance Win32_Process |
            Select-Object ProcessId, ParentProcessId
    )
    $owned = @()
    $pending = New-Object "System.Collections.Generic.Queue[int]"
    $pending.Enqueue($RootProcessId)

    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        if ($owned -notcontains $current) {
            $owned += [int]$current
            foreach ($child in @($snapshot | Where-Object { $_.ParentProcessId -eq $current })) {
                $pending.Enqueue([int]$child.ProcessId)
            }
        }
    }

    return $owned
}

function Stop-OwnedProcessTree {
    param(
        [Parameter(Mandatory = $true)][int]$RootProcessId,
        [Parameter(Mandatory = $true)][string]$ShutdownLog,
        [Parameter(Mandatory = $true)][int]$Run
    )

    $ownedIds = @(Get-OwnedProcessIds -RootProcessId $RootProcessId)
    $descendantIds = @(
        $ownedIds |
            Where-Object { $_ -ne $RootProcessId } |
            Sort-Object -Descending
    )

    foreach ($processId in $descendantIds) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction Stop
                Add-Content -LiteralPath $ShutdownLog -Encoding UTF8 -Value "[run $Run] stopped owned process $processId"
            }
            catch {
                if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
                    throw
                }
                Add-Content -LiteralPath $ShutdownLog -Encoding UTF8 -Value "[run $Run] owned process $processId exited before stop"
            }
        }
    }

    $rootProcess = Get-Process -Id $RootProcessId -ErrorAction SilentlyContinue
    if ($null -ne $rootProcess) {
        try {
            Stop-Process -Id $RootProcessId -Force -ErrorAction Stop
            Add-Content -LiteralPath $ShutdownLog -Encoding UTF8 -Value "[run $Run] stopped root process $RootProcessId"
        }
        catch {
            if ($null -ne (Get-Process -Id $RootProcessId -ErrorAction SilentlyContinue)) {
                throw
            }
            Add-Content -LiteralPath $ShutdownLog -Encoding UTF8 -Value "[run $Run] root process $RootProcessId exited before stop"
        }
    }
}

function Wait-ForPortRelease {
    param(
        [Parameter(Mandatory = $true)][int]$LocalPort,
        [Parameter(Mandatory = $true)][int]$Timeout
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Timeout)
    do {
        $listeners = @(
            Get-NetTCPConnection -State Listen -LocalPort $LocalPort -ErrorAction SilentlyContinue
        )
        if ($listeners.Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "Port $LocalPort remains in the Listen state after shutdown."
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "smoke.ps1 supports Windows only."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $PSScriptRoot "start.ps1"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$evidenceRoot = Join-Path $projectRoot ".artifacts\loan-interest-accrual-v1\startup"
$setupLog = Join-Path $evidenceRoot "setup.log"
$startupLog = Join-Path $evidenceRoot "startup.log"
$listenerLog = Join-Path $evidenceRoot "listener.json"
$shutdownLog = Join-Path $evidenceRoot "shutdown.log"

New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
Set-Content -LiteralPath $setupLog -Encoding UTF8 -Value "Timestamp=$([DateTimeOffset]::Now.ToString('o'))"
Set-Content -LiteralPath $startupLog -Encoding UTF8 -Value "Timestamp=$([DateTimeOffset]::Now.ToString('o'))"
Set-Content -LiteralPath $shutdownLog -Encoding UTF8 -Value "Timestamp=$([DateTimeOffset]::Now.ToString('o'))"

if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
    throw "Start script is missing: $startScript"
}
if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "Pinned requirements file is missing: $requirementsPath"
}
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "Project virtual environment Python is missing: $venvPython"
}

$pyLauncher = Get-Command py.exe -ErrorAction Stop
& py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
Assert-LastExitCode "py -3.12 verification"
Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value @(
    "Launcher=$($pyLauncher.Source)"
    "PythonLauncher=3.12"
)

$venvVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Assert-LastExitCode "Virtual environment Python verification"
if ($venvVersion.Trim() -ne "3.12") {
    throw "Project virtual environment must use Python 3.12; found $($venvVersion.Trim())."
}
Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "VenvPython=3.12"

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
        throw "Required package is not installed in .venv: $packageName==$requiredVersion"
    }
    if ($installed[$packageName] -ne $requiredVersion) {
        throw "Installed package version mismatch for ${packageName}: required $requiredVersion, found $($installed[$packageName])."
    }
}
Add-Content -LiteralPath $setupLog -Encoding UTF8 -Value "PinnedRequirements=verified"

$preexistingListeners = @(
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
)
if ($preexistingListeners.Count -ne 0) {
    throw "Task-owned smoke port $Port is already in use."
}

$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$listenerRecords = @()

foreach ($run in 1..2) {
    $serverProcess = $null
    $runFailure = $null
    $stdoutPath = Join-Path $evidenceRoot "startup-run-$run.stdout.log"
    $stderrPath = Join-Path $evidenceRoot "startup-run-$run.stderr.log"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    Add-Content -LiteralPath $startupLog -Encoding UTF8 -Value "[run $run] starting on http://127.0.0.1:$Port"

    try {
        $arguments = @(
            "-NoProfile"
            "-ExecutionPolicy"
            "Bypass"
            "-File"
            "`"$startScript`""
            "-HostAddress"
            "127.0.0.1"
            "-Port"
            "$Port"
        )
        $serverProcess = Start-Process `
            -FilePath $powershellPath `
            -ArgumentList $arguments `
            -PassThru `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath
        Add-Content -LiteralPath $startupLog -Encoding UTF8 -Value "[run $run] root process $($serverProcess.Id)"

        $healthUri = "http://127.0.0.1:$Port/health"
        $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        $healthy = $false
        $lastPollError = ""
        do {
            $serverProcess.Refresh()
            if ($serverProcess.HasExited) {
                throw "Owned startup process exited before health check with code $($serverProcess.ExitCode)."
            }
            try {
                $healthResponse = Invoke-WebRequest -UseBasicParsing -Uri $healthUri -TimeoutSec 2
                if ($healthResponse.StatusCode -eq 200 -and $healthResponse.Content -match '"status"\s*:\s*"ok"') {
                    $healthy = $true
                    break
                }
                $lastPollError = "Unexpected health response status or body."
            }
            catch {
                $lastPollError = $_.Exception.Message
            }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $deadline)

        if (-not $healthy) {
            throw "Health check timed out: $lastPollError"
        }

        $homepageResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/" -TimeoutSec 5
        if ($homepageResponse.StatusCode -ne 200) {
            throw "Homepage returned status $($homepageResponse.StatusCode)."
        }
        $staticResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/static/styles.css" -TimeoutSec 5
        if ($staticResponse.StatusCode -ne 200 -or $staticResponse.Content.Length -eq 0) {
            throw "Static stylesheet request failed."
        }
        Add-Content -LiteralPath $startupLog -Encoding UTF8 -Value "[run $run] health, homepage, and static asset passed"

        $ownedProcessIds = @(Get-OwnedProcessIds -RootProcessId $serverProcess.Id)
        $listeners = @(
            Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
        )
        if ($listeners.Count -ne 1) {
            throw "Expected exactly one listener on port $Port; found $($listeners.Count)."
        }
        $listener = $listeners[0]
        if ($listener.LocalAddress -cne "127.0.0.1") {
            throw "Listener address must be exactly 127.0.0.1; found $($listener.LocalAddress)."
        }
        if ($ownedProcessIds -notcontains [int]$listener.OwningProcess) {
            throw "Listener process $($listener.OwningProcess) is outside the owned process tree."
        }

        $listenerRecords += [pscustomobject]@{
            run = $run
            local_address = [string]$listener.LocalAddress
            local_port = [int]$listener.LocalPort
            owning_process = [int]$listener.OwningProcess
            root_process = [int]$serverProcess.Id
            owned_process_ids = @($ownedProcessIds)
        }
    }
    catch {
        $runFailure = $_
    }
    finally {
        if ($null -ne $serverProcess) {
            try {
                Stop-OwnedProcessTree -RootProcessId $serverProcess.Id -ShutdownLog $shutdownLog -Run $run
            }
            catch {
                if ($null -eq $runFailure) {
                    $runFailure = $_
                }
                else {
                    Add-Content -LiteralPath $shutdownLog -Encoding UTF8 -Value "[run $run] cleanup error: $($_.Exception.Message)"
                }
            }

            function Wait-For-RootProcessExitAndRedirectRelease {
                param(
                    [Parameter(Mandatory = $true)]
                    [System.Diagnostics.Process]$RootProcess,

                    [Parameter(Mandatory = $true)]
                    [string[]]$RedirectPaths,

                    [Parameter(Mandatory = $true)]
                    [ValidateRange(1, 300)]
                    [int]$Timeout
                )

                $rootProcessId = $RootProcess.Id
                try {
                    if (-not $RootProcess.WaitForExit($Timeout * 1000)) {
                        throw "Root process $rootProcessId did not exit within $Timeout seconds."
                    }
                    $RootProcess.WaitForExit()
                }
                finally {
                    $RootProcess.Dispose()
                }

                foreach ($redirectPath in $RedirectPaths) {
                    $deadline = [DateTime]::UtcNow.AddSeconds($Timeout)
                    $lastOpenError = $null

                    while ($true) {
                        $exclusiveStream = $null
                        try {
                            $exclusiveStream = [System.IO.File]::Open(
                                $redirectPath,
                                [System.IO.FileMode]::Open,
                                [System.IO.FileAccess]::Read,
                                [System.IO.FileShare]::None
                            )
                            break
                        }
                        catch [System.IO.IOException] {
                            $lastOpenError = $_.Exception
                        }
                        finally {
                            if ($null -ne $exclusiveStream) {
                                $exclusiveStream.Dispose()
                            }
                        }

                        if ([DateTime]::UtcNow -ge $deadline) {
                            throw "Redirect log '$redirectPath' was not released within $Timeout seconds. Last error: $($lastOpenError.Message)"
                        }
                        Start-Sleep -Milliseconds 100
                    }
                }
            }

            Wait-For-RootProcessExitAndRedirectRelease `
                -RootProcess $serverProcess `
                -RedirectPaths @($stdoutPath, $stderrPath) `
                -Timeout 10
        }

        foreach ($logPath in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $logPath -PathType Leaf) {
                Add-Content -LiteralPath $startupLog -Encoding UTF8 -Value "[run $run] captured $([IO.Path]::GetFileName($logPath))"
                Get-Content -LiteralPath $logPath -Encoding UTF8 |
                    Add-Content -LiteralPath $startupLog -Encoding UTF8
                Remove-Item -LiteralPath $logPath -Force
            }
        }

        try {
            Wait-ForPortRelease -LocalPort $Port -Timeout 10
            Add-Content -LiteralPath $shutdownLog -Encoding UTF8 -Value "[run $run] port released"
        }
        catch {
            if ($null -eq $runFailure) {
                $runFailure = $_
            }
            else {
                Add-Content -LiteralPath $shutdownLog -Encoding UTF8 -Value "[run $run] release error: $($_.Exception.Message)"
            }
        }
    }

    if ($null -ne $runFailure) {
        $listenerRecords |
            ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath $listenerLog -Encoding UTF8
        throw $runFailure
    }
}

$listenerRecords |
    ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $listenerLog -Encoding UTF8

Write-Output "Windows startup smoke passed twice on 127.0.0.1:$Port."
