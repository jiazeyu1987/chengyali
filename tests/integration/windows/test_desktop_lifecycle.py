from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
INSTALL_SCRIPT = SCRIPTS_ROOT / "install.ps1"
LAUNCH_SCRIPT = SCRIPTS_ROOT / "desktop-launch.ps1"
STOP_SCRIPT = SCRIPTS_ROOT / "desktop-stop.ps1"
UNINSTALL_SCRIPT = SCRIPTS_ROOT / "uninstall.ps1"
POWERSHELL = (
    Path(os.environ["SystemRoot"])
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)
SHORTCUT_NAME = "贷款利息自动计提工具.lnk"
APP_ID = "loan-interest-accrual-desktop-v1"


def _run_script(
    script: Path,
    *arguments: str,
    cwd: Path,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(POWERSHELL),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *arguments,
    ]
    with (
        tempfile.TemporaryFile(
            mode="w+",
            encoding="utf-8",
            errors="replace",
        ) as stdout_file,
        tempfile.TemporaryFile(
            mode="w+",
            encoding="utf-8",
            errors="replace",
        ) as stderr_file,
    ):
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            completed.args,
            completed.returncode,
            stdout_file.read(),
            stderr_file.read(),
        )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _powershell_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _copy_scripts(project_root: Path, *scripts: Path) -> None:
    target = project_root / "scripts"
    target.mkdir(parents=True, exist_ok=True)
    for script in scripts:
        shutil.copy2(script, target / script.name)


def _create_launch_prerequisites(project_root: Path) -> None:
    python_path = project_root / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_bytes(b"test executable placeholder")
    (project_root / "src").mkdir(parents=True, exist_ok=True)


def _runtime_root(project_root: Path) -> Path:
    return project_root / ".artifacts" / APP_ID / "runtime"


def _write_runtime_state(
    project_root: Path,
    *,
    pid: int,
    listener_pid: int | None = None,
    launch_token: str = "a" * 32,
) -> Path:
    runtime_root = _runtime_root(project_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    state_path = runtime_root / "app.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "application_id": APP_ID,
                "project_root": str(project_root.resolve()),
                "host": "127.0.0.1",
                "port": 8000,
                "pid": pid,
                "listener_pid": listener_pid if listener_pid is not None else pid,
                "launch_token": launch_token,
            }
        ),
        encoding="utf-8",
    )
    return state_path


def _read_shortcut(shortcut: Path) -> dict[str, str]:
    command = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({_powershell_literal(shortcut)})",
            "[pscustomobject]@{",
            "  TargetPath = $shortcut.TargetPath",
            "  Arguments = $shortcut.Arguments",
            "  WorkingDirectory = $shortcut.WorkingDirectory",
            "} | ConvertTo-Json -Compress",
        ]
    )
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, _combined_output(result)
    return json.loads(result.stdout)


def _wait_for_loopback_port(port: int, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            if client.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise AssertionError(f"127.0.0.1:{port} did not start listening")


@contextmanager
def _foreign_fixed_port_listener() -> Iterator[None]:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 8000))
    except OSError:
        probe.close()
        yield
        return
    probe.close()

    process = subprocess.Popen(
        [
            str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "http.server",
            "8000",
            "--bind",
            "127.0.0.1",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_loopback_port(8000)
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_ac_d01_launch_is_hidden_fixed_loopback_and_opens_after_health() -> None:
    source = LAUNCH_SCRIPT.read_text(encoding="utf-8")
    normalized = source.replace("`", "").lower()

    assert '$hostaddress = "127.0.0.1"' in normalized
    assert "$port = 8000" in normalized
    assert ".artifacts\\loan-interest-accrual-desktop-v1\\runtime" in normalized
    assert "start-process" in normalized
    assert "-windowstyle hidden" in normalized
    assert "/health" in source
    assert "invoke-restmethod" in normalized
    assert "http://127.0.0.1:8000/" in source
    assert "&&" not in source
    assert "netstat.exe" in source
    assert "Get-NetTCPConnection" not in source
    assert "System.Threading.Mutex" in source
    assert 'return "Global\\$ApplicationId-$projectHash"' in source
    assert "launch_token" in source
    assert "[System.IO.File]::Replace" in source

    health_position = normalized.index("invoke-restmethod")
    browser_position = normalized.rindex("start-process")
    assert health_position < browser_position


def test_ac_d03_hidden_launch_failures_are_logged_and_user_visible() -> None:
    source = LAUNCH_SCRIPT.read_text(encoding="utf-8")

    assert "[switch]$NoDialog" in source
    assert "launcher-error.log" in source
    assert "WScript.Shell" in source
    assert ".Popup(" in source
    assert "$failureTitle" in source
    assert "[char]0x8D37" in source
    assert "[char]0x8D25" in source


def test_ac_d04_stop_supports_a_bounded_response_delay() -> None:
    source = STOP_SCRIPT.read_text(encoding="utf-8")

    assert "[int]$DelayMilliseconds = 0" in source
    assert "[ValidateRange(0, 5000)]" in source
    assert "Start-Sleep -Milliseconds $DelayMilliseconds" in source


def test_ac_d01_launch_waits_for_health_then_opens_browser(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)
    _create_launch_prerequisites(project_root)
    launch = project_root / "scripts" / LAUNCH_SCRIPT.name
    harness = tmp_path / "launch-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "$global:events = New-Object System.Collections.Generic.List[string]",
                "$global:serviceStarted = $false",
                f"$launch = {_powershell_literal(launch)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $launch)",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                "function Invoke-DesktopNetstat {",
                "  if ($global:serviceStarted) {",
                "    'TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 4242'",
                "  }",
                "}",
                "function Get-CimInstance {",
                "  param($ClassName, $Filter, $ErrorAction)",
                "  $commandLine = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
                "  [pscustomobject]@{ ProcessId = 4242; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $commandLine }",
                "}",
                "function Start-Sleep { param($Milliseconds, $Seconds) }",
                "function Invoke-RestMethod {",
                "  param($Uri, $Method, $TimeoutSec, $ErrorAction)",
                "  $global:events.Add('health')",
                "  [pscustomobject]@{ status = 'ok' }",
                "}",
                "function Start-Process {",
                "  param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)",
                "  if ([string]$FilePath -eq $venvPython) {",
                "    if ($WindowStyle -ne 'Hidden') { throw 'service was not hidden' }",
                "    $global:events.Add('service:hidden')",
                "    $global:serviceStarted = $true",
                "    return [pscustomobject]@{ Id = 4242; HasExited = $false }",
                "  }",
                "  $global:events.Add(('browser:{0}' -f $FilePath))",
                "}",
                "& $launch -HealthTimeoutSeconds 1 -NoDialog",
                "$global:events | ConvertTo-Json -Compress",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert result.returncode == 0, _combined_output(result)
    events = json.loads(result.stdout.splitlines()[-1])
    assert events == [
        "service:hidden",
        "health",
        "browser:http://127.0.0.1:8000/",
    ]
    state = json.loads((_runtime_root(project_root) / "app.json").read_text(encoding="utf-8"))
    assert state["application_id"] == APP_ID
    assert state["project_root"] == str(project_root.resolve())
    assert state["pid"] == 4242
    assert state["listener_pid"] == 4242


def test_ac_d02_reuses_only_identity_matched_healthy_state(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)
    _create_launch_prerequisites(project_root)
    launch = project_root / "scripts" / LAUNCH_SCRIPT.name
    _write_runtime_state(project_root, pid=4242)
    harness = tmp_path / "reuse-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "$global:events = New-Object System.Collections.Generic.List[string]",
                f"$launch = {_powershell_literal(launch)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $launch)",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                "function Invoke-DesktopNetstat {",
                "  'TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 4242'",
                "}",
                "function Get-CimInstance {",
                "  param($ClassName, $Filter, $ErrorAction)",
                "  $commandLine = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
                "  [pscustomobject]@{ ProcessId = 4242; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $commandLine }",
                "}",
                "function Invoke-RestMethod {",
                "  param($Uri, $Method, $TimeoutSec, $ErrorAction)",
                "  $global:events.Add('health')",
                "  [pscustomobject]@{ status = 'ok' }",
                "}",
                "function Start-Process {",
                "  param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)",
                "  if ([string]$FilePath -eq $venvPython) { throw 'second service instance attempted' }",
                "  $global:events.Add(('browser:{0}' -f $FilePath))",
                "}",
                "& $launch -HealthTimeoutSeconds 1",
                "$global:events | ConvertTo-Json -Compress",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert result.returncode == 0, _combined_output(result)
    assert json.loads(result.stdout.splitlines()[-1]) == [
        "health",
        "browser:http://127.0.0.1:8000/",
    ]


def test_ac_d02_concurrent_launches_serialize_and_reuse_single_owned_instance(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)
    _create_launch_prerequisites(project_root)
    launch = project_root / "scripts" / LAUNCH_SCRIPT.name
    service_marker = project_root / "service-ready.txt"
    start_count = project_root / "service-starts.txt"
    harness = tmp_path / "concurrent-launch-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$launch = {_powershell_literal(launch)}",
                f"$serviceMarker = {_powershell_literal(service_marker)}",
                f"$startCount = {_powershell_literal(start_count)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $launch)",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                "$ownedCommand = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
                "function Invoke-DesktopNetstat {",
                "  if (Test-Path -LiteralPath $serviceMarker -PathType Leaf) {",
                "    'TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 4242'",
                "  }",
                "}",
                "function Get-CimInstance {",
                "  param($ClassName, $Filter, $ErrorAction)",
                "  if (-not (Test-Path -LiteralPath $serviceMarker -PathType Leaf)) {",
                "    if ($Filter) { return $null }",
                "    return @()",
                "  }",
                "  $process = [pscustomobject]@{ ProcessId = 4242; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $ownedCommand }",
                "  if ($Filter) { return $process }",
                "  return @($process)",
                "}",
                "function Invoke-RestMethod {",
                "  param($Uri, $Method, $TimeoutSec, $ErrorAction)",
                "  [pscustomobject]@{ status = 'ok' }",
                "}",
                "function Start-Process {",
                "  param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)",
                "  if ([string]$FilePath -ne $venvPython) { throw 'unexpected browser start' }",
                "  Add-Content -LiteralPath $startCount -Encoding UTF8 -Value 'start'",
                "  Start-Sleep -Milliseconds 750",
                "  Set-Content -LiteralPath $serviceMarker -Encoding UTF8 -Value 'ready'",
                "  [pscustomobject]@{ Id = 4242; HasExited = $false }",
                "}",
                "& $launch -HealthTimeoutSeconds 3 -NoDialog -NoBrowser",
            ]
        ),
        encoding="utf-8",
    )
    command = [
        str(POWERSHELL),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(harness),
    ]
    first = subprocess.Popen(
        command,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    time.sleep(0.1)
    second = subprocess.Popen(
        command,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    first_stdout, first_stderr = first.communicate(timeout=20)
    second_stdout, second_stderr = second.communicate(timeout=20)

    assert first.returncode == 0, f"{first_stdout}\n{first_stderr}"
    assert second.returncode == 0, f"{second_stdout}\n{second_stderr}"
    outputs = f"{first_stdout}\n{second_stdout}"
    assert outputs.count("Desktop application started successfully.") == 1
    assert outputs.count("Reused healthy desktop application instance.") == 1
    assert start_count.read_text(encoding="utf-8-sig").splitlines() == ["start"]
    state = json.loads(
        (_runtime_root(project_root) / "app.json").read_text(encoding="utf-8")
    )
    assert state["schema_version"] == 2
    assert re.fullmatch(r"[0-9a-f]{32}", state["launch_token"])
    assert state["pid"] == 4242
    assert state["listener_pid"] == 4242


def test_ac_d02_restarts_after_stale_state_when_owned_process_and_port_are_absent(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)
    _create_launch_prerequisites(project_root)
    launch = project_root / "scripts" / LAUNCH_SCRIPT.name
    _write_runtime_state(project_root, pid=2_000_000_000)
    harness = tmp_path / "stale-launch-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "$global:started = $false",
                "$global:events = New-Object System.Collections.Generic.List[string]",
                f"$launch = {_powershell_literal(launch)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $launch)",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                "$ownedCommand = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
                "function Get-CimInstance {",
                "  param($ClassName, $Filter, $ErrorAction)",
                "  if ($Filter -and $Filter -match '4242' -and $global:started) {",
                "    return [pscustomobject]@{ ProcessId = 4242; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $ownedCommand }",
                "  }",
                "  if ($Filter) { return $null }",
                "  if ($global:started) {",
                "    return @([pscustomobject]@{ ProcessId = 4242; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $ownedCommand })",
                "  }",
                "  return @()",
                "}",
                "function Invoke-DesktopNetstat {",
                "  if ($global:started) {",
                "    return 'TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 4242'",
                "  }",
                "  return @()",
                "}",
                "function Invoke-RestMethod {",
                "  param($Uri, $Method, $TimeoutSec, $ErrorAction)",
                "  $global:events.Add('health')",
                "  [pscustomobject]@{ status = 'ok' }",
                "}",
                "function Start-Process {",
                "  param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)",
                "  if ([string]$FilePath -eq $venvPython) {",
                "    $global:started = $true",
                "    $global:events.Add('service:hidden')",
                "    return [pscustomobject]@{ Id = 4242 }",
                "  }",
                "  $global:events.Add(('browser:{0}' -f $FilePath))",
                "}",
                "function Start-Sleep { param($Milliseconds, $Seconds) }",
                "& $launch -HealthTimeoutSeconds 1",
                "$global:events | ConvertTo-Json -Compress",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert result.returncode == 0, _combined_output(result)
    assert json.loads(result.stdout.splitlines()[-1]) == [
        "service:hidden",
        "health",
        "browser:http://127.0.0.1:8000/",
    ]
    state = json.loads(
        (_runtime_root(project_root) / "app.json").read_text(encoding="utf-8")
    )
    assert state["pid"] == 4242
    assert state["listener_pid"] == 4242


def test_ac_d03_fixed_port_conflict_fails_without_scanning(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)
    _create_launch_prerequisites(project_root)

    with _foreign_fixed_port_listener():
        result = _run_script(
            project_root / "scripts" / LAUNCH_SCRIPT.name,
            "-NoDialog",
            cwd=project_root,
            timeout=20,
        )

    assert result.returncode != 0
    output = _combined_output(result).lower()
    assert "port 8000" in output
    assert "already in use" in output
    assert not (_runtime_root(project_root) / "app.json").exists()


def test_ac_d03_missing_prerequisite_fails_without_runtime_state(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)

    result = _run_script(
        project_root / "scripts" / LAUNCH_SCRIPT.name,
        "-NoDialog",
        cwd=project_root,
        timeout=20,
    )

    assert result.returncode != 0
    assert ".venv\\Scripts\\python.exe" in _combined_output(result)
    assert not (_runtime_root(project_root) / "app.json").exists()


def test_ac_d03_failed_launch_cleanup_preserves_replaced_state(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, LAUNCH_SCRIPT)
    _create_launch_prerequisites(project_root)
    launch = project_root / "scripts" / LAUNCH_SCRIPT.name
    winner_token = "b" * 32
    harness = tmp_path / "cleanup-ownership-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "$global:started = $false",
                "$global:winnerWritten = $false",
                f"$launch = {_powershell_literal(launch)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $launch)",
                "$runtimeRoot = Join-Path $projectRoot '.artifacts\\loan-interest-accrual-desktop-v1\\runtime'",
                "$statePath = Join-Path $runtimeRoot 'app.json'",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                "$ownedCommand = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
                "function Get-CimInstance {",
                "  param($ClassName, $Filter, $ErrorAction)",
                "  if (-not $global:started) {",
                "    if ($Filter) { return $null }",
                "    return @()",
                "  }",
                "  $process = [pscustomobject]@{ ProcessId = 4242; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $ownedCommand }",
                "  if ($Filter) { return $process }",
                "  return @($process)",
                "}",
                "function Invoke-DesktopNetstat {",
                "  if ($global:started -and -not $global:winnerWritten) {",
                "    $winner = [ordered]@{",
                "      schema_version = 2",
                "      application_id = 'loan-interest-accrual-desktop-v1'",
                "      project_root = $projectRoot",
                "      host = '127.0.0.1'",
                "      port = 8000",
                "      pid = 5252",
                "      listener_pid = 5252",
                f"      launch_token = '{winner_token}'",
                "      started_at = [DateTimeOffset]::Now.ToString('o')",
                "    }",
                "    $json = $winner | ConvertTo-Json -Depth 3",
                "    $encoding = New-Object System.Text.UTF8Encoding($false)",
                "    [System.IO.File]::WriteAllText($statePath, $json, $encoding)",
                "    $global:winnerWritten = $true",
                "  }",
                "  return @()",
                "}",
                "function Start-Process {",
                "  param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)",
                "  $global:started = $true",
                "  [pscustomobject]@{ Id = 4242; HasExited = $false }",
                "}",
                "function Stop-Process { param([int[]]$Id, [switch]$Force, $ErrorAction) }",
                "& $launch -HealthTimeoutSeconds 1 -NoDialog -NoBrowser",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert "startup failed" in _combined_output(result).lower()
    assert (_runtime_root(project_root) / "app.json").is_file()
    state = json.loads(
        (_runtime_root(project_root) / "app.json").read_text(encoding="utf-8")
    )
    assert state["launch_token"] == winner_token
    assert state["pid"] == 5252
    assert state["listener_pid"] == 5252


def test_ac_d04_stop_removes_owned_stale_state_when_port_is_free(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, STOP_SCRIPT)
    stop = project_root / "scripts" / STOP_SCRIPT.name
    state_path = _write_runtime_state(project_root, pid=2_000_000_000)
    harness = tmp_path / "stale-stop-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$stopScript = {_powershell_literal(stop)}",
                "function Get-CimInstance { param($ClassName, $Filter, $ErrorAction); return @() }",
                "function Invoke-DesktopNetstat { return @() }",
                "& $stopScript -TimeoutSeconds 1",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert result.returncode == 0, _combined_output(result)
    assert "stale" in _combined_output(result).lower()
    assert not state_path.exists()


def test_ac_d04_stop_detaches_worker_through_windows_cim(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, STOP_SCRIPT)
    stop = project_root / "scripts" / STOP_SCRIPT.name
    harness = tmp_path / "detach-stop-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "$global:createdCommandLine = $null",
                f"$stopScript = {_powershell_literal(stop)}",
                "function Invoke-CimMethod {",
                "  param($ClassName, $MethodName, $Arguments, $ErrorAction)",
                "  $global:createdCommandLine = [string]$Arguments.CommandLine",
                "  [pscustomobject]@{ ReturnValue = 0; ProcessId = 7001 }",
                "}",
                "& $stopScript -DelayMilliseconds 750 -Detach",
                "$global:createdCommandLine",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert result.returncode == 0, _combined_output(result)
    command_line = result.stdout.splitlines()[-1]
    encoded_match = re.search(r"-EncodedCommand\s+(\S+)", command_line)
    assert encoded_match is not None
    worker_script = base64.b64decode(encoded_match.group(1)).decode("utf-16-le")
    assert str(stop) in worker_script
    assert "-DelayMilliseconds 750" in worker_script
    assert "-DetachedWorker" in worker_script
    assert re.search(r"(?:^|\s)-Detach(?:\s|$)", worker_script) is None


def test_ac_d04_stop_rejects_live_untrusted_pid_without_killing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, STOP_SCRIPT)
    sleeper = subprocess.Popen(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-Command",
            "Start-Sleep -Seconds 60",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    state_path = _write_runtime_state(project_root, pid=sleeper.pid)

    try:
        result = _run_script(
            project_root / "scripts" / STOP_SCRIPT.name,
            cwd=project_root,
            timeout=20,
        )

        assert result.returncode != 0
        output = _combined_output(result).lower()
        assert "identity" in output or "untrusted" in output
        assert state_path.exists()
        assert sleeper.poll() is None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            try:
                sleeper.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sleeper.kill()
                sleeper.wait(timeout=5)


def test_ac_d04_stop_terminates_only_validated_owned_tree(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(project_root, STOP_SCRIPT)
    stop = project_root / "scripts" / STOP_SCRIPT.name
    _write_runtime_state(project_root, pid=5000, listener_pid=5001)
    harness = tmp_path / "stop-harness.ps1"
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                "$global:stopped = New-Object System.Collections.Generic.List[int]",
                f"$stopScript = {_powershell_literal(stop)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $stopScript)",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                "$ownedCommand = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
                "function Get-CimInstance {",
                "  param($ClassName, $Filter, $ErrorAction)",
                "  if ($Filter) {",
                "    if ($global:stopped.Count -ne 0) { return $null }",
                "    if ($Filter -match '5000') { return [pscustomobject]@{ ProcessId = 5000; ParentProcessId = 10; CreationDate = [datetime]'2026-07-11T00:10:00'; ExecutablePath = $venvPython; CommandLine = $ownedCommand } }",
                "    if ($Filter -match '5001') { return [pscustomobject]@{ ProcessId = 5001; ParentProcessId = 5000; CreationDate = [datetime]'2026-07-11T00:10:01'; ExecutablePath = $venvPython; CommandLine = 'worker' } }",
                "    return $null",
                "  }",
                "  @(",
                "    [pscustomobject]@{ ProcessId = 5000; ParentProcessId = 10; CreationDate = [datetime]'2026-07-11T00:10:00'; ExecutablePath = $venvPython; CommandLine = $ownedCommand },",
                "    [pscustomobject]@{ ProcessId = 5001; ParentProcessId = 5000; CreationDate = [datetime]'2026-07-11T00:10:01'; ExecutablePath = $venvPython; CommandLine = 'worker' },",
                "    [pscustomobject]@{ ProcessId = $PID; ParentProcessId = 5001; CreationDate = [datetime]'2026-07-11T00:10:02'; ExecutablePath = 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe'; CommandLine = 'desktop-stop.ps1' },",
                "    [pscustomobject]@{ ProcessId = 6000; ParentProcessId = 5000; CreationDate = [datetime]'2026-07-10T00:00:00'; ExecutablePath = 'C:\\Windows\\notepad.exe'; CommandLine = 'notepad.exe' }",
                "  )",
                "}",
                "function Invoke-DesktopNetstat {",
                "  if ($global:stopped.Count -eq 0) {",
                "    'TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 5001'",
                "  }",
                "}",
                "function Stop-Process {",
                "  param([int[]]$Id, [switch]$Force, $ErrorAction)",
                "  foreach ($processId in $Id) { $global:stopped.Add($processId) }",
                "}",
                "function Start-Sleep { param($Milliseconds, $Seconds) }",
                "& $stopScript -TimeoutSeconds 1",
                "$global:stopped | ConvertTo-Json -Compress",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=20)

    assert result.returncode == 0, _combined_output(result)
    stopped = set(json.loads(result.stdout.splitlines()[-1]))
    assert stopped == {5000, 5001}
    assert not (_runtime_root(project_root) / "app.json").exists()


def test_ac_d05_install_and_uninstall_manage_only_owned_artifacts(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(
        project_root,
        INSTALL_SCRIPT,
        LAUNCH_SCRIPT,
        STOP_SCRIPT,
        UNINSTALL_SCRIPT,
    )
    setup = project_root / "scripts" / "setup.ps1"
    setup.write_text(
        "$ErrorActionPreference = 'Stop'\nWrite-Output 'setup complete'\n",
        encoding="utf-8",
    )
    desktop = tmp_path / "Desktop"
    start_menu = tmp_path / "StartMenu"
    desktop.mkdir()
    start_menu.mkdir()
    desktop_keep = desktop / "keep.txt"
    start_keep = start_menu / "keep.txt"
    desktop_keep.write_text("keep", encoding="utf-8")
    start_keep.write_text("keep", encoding="utf-8")
    dependency_sentinel = project_root / ".venv" / "dependency.txt"
    dependency_sentinel.parent.mkdir(parents=True)
    dependency_sentinel.write_text("keep dependency", encoding="utf-8")
    user_data = project_root / "user-data.xlsx"
    user_data.write_bytes(b"keep user data")

    install = _run_script(
        project_root / "scripts" / INSTALL_SCRIPT.name,
        "-DesktopDirectory",
        str(desktop),
        "-StartMenuDirectory",
        str(start_menu),
        cwd=project_root,
        timeout=30,
    )

    assert install.returncode == 0, _combined_output(install)
    desktop_shortcut = desktop / SHORTCUT_NAME
    start_shortcut = start_menu / SHORTCUT_NAME
    assert desktop_shortcut.is_file()
    assert start_shortcut.is_file()
    for shortcut_path in (desktop_shortcut, start_shortcut):
        shortcut = _read_shortcut(shortcut_path)
        assert Path(shortcut["TargetPath"]).resolve() == POWERSHELL.resolve()
        assert "-WindowStyle Hidden" in shortcut["Arguments"]
        assert "desktop-launch.ps1" in shortcut["Arguments"]
        assert Path(shortcut["WorkingDirectory"]).resolve() == project_root.resolve()

    runtime_root = _runtime_root(project_root)
    runtime_root.mkdir(parents=True)
    (runtime_root / "stdout.log").write_text("owned runtime", encoding="utf-8")
    _write_runtime_state(project_root, pid=2_000_000_000)
    uninstall = _run_script(
        project_root / "scripts" / UNINSTALL_SCRIPT.name,
        "-DesktopDirectory",
        str(desktop),
        "-StartMenuDirectory",
        str(start_menu),
        cwd=project_root,
        timeout=30,
    )

    assert uninstall.returncode == 0, _combined_output(uninstall)
    assert not desktop_shortcut.exists()
    assert not start_shortcut.exists()
    assert not runtime_root.exists()
    assert desktop_keep.read_text(encoding="utf-8") == "keep"
    assert start_keep.read_text(encoding="utf-8") == "keep"
    assert dependency_sentinel.read_text(encoding="utf-8") == "keep dependency"
    assert user_data.read_bytes() == b"keep user data"


@pytest.mark.parametrize(
    "live_condition",
    ["matching_process", "fixed_port_listener"],
)
def test_ac_d05_uninstall_missing_state_fails_closed(
    tmp_path: Path,
    live_condition: str,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(
        project_root,
        INSTALL_SCRIPT,
        LAUNCH_SCRIPT,
        STOP_SCRIPT,
        UNINSTALL_SCRIPT,
    )
    (project_root / "scripts" / "setup.ps1").write_text(
        "$ErrorActionPreference = 'Stop'\nWrite-Output 'setup complete'\n",
        encoding="utf-8",
    )
    desktop = tmp_path / "Desktop"
    start_menu = tmp_path / "StartMenu"
    desktop.mkdir()
    start_menu.mkdir()
    install = _run_script(
        project_root / "scripts" / INSTALL_SCRIPT.name,
        "-DesktopDirectory",
        str(desktop),
        "-StartMenuDirectory",
        str(start_menu),
        cwd=project_root,
        timeout=30,
    )
    assert install.returncode == 0, _combined_output(install)

    runtime_root = _runtime_root(project_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_sentinel = runtime_root / "preserve.log"
    runtime_sentinel.write_text("preserve", encoding="utf-8")
    state_path = runtime_root / "app.json"
    assert not state_path.exists()
    uninstall = project_root / "scripts" / UNINSTALL_SCRIPT.name
    harness = tmp_path / f"uninstall-{live_condition}-harness.ps1"
    process_lines = (
        [
            "function Get-CimInstance {",
            "  param($ClassName, $Filter, $ErrorAction)",
            "  $commandLine = ('\"{0}\" -m uvicorn loan_interest_accrual.web:app --app-dir \"{1}\" --host 127.0.0.1 --port 8000' -f $venvPython, $sourceRoot)",
            "  [pscustomobject]@{ ProcessId = 6001; ParentProcessId = 1; ExecutablePath = $venvPython; CommandLine = $commandLine }",
            "}",
        ]
        if live_condition == "matching_process"
        else [
            "function Get-CimInstance { param($ClassName, $Filter, $ErrorAction); return @() }",
        ]
    )
    netstat_lines = (
        [
            "function Invoke-DesktopNetstat { return @() }",
        ]
        if live_condition == "matching_process"
        else [
            "function Invoke-DesktopNetstat {",
            "  'TCP 0.0.0.0:8000 0.0.0.0:0 LISTENING 7001'",
            "}",
        ]
    )
    harness.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$uninstall = {_powershell_literal(uninstall)}",
                f"$desktop = {_powershell_literal(desktop)}",
                f"$startMenu = {_powershell_literal(start_menu)}",
                "$projectRoot = Split-Path -Parent (Split-Path -Parent $uninstall)",
                "$venvPython = Join-Path $projectRoot '.venv\\Scripts\\python.exe'",
                "$sourceRoot = Join-Path $projectRoot 'src'",
                *process_lines,
                *netstat_lines,
                "& $uninstall -DesktopDirectory $desktop -StartMenuDirectory $startMenu",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(harness, cwd=project_root, timeout=30)

    assert result.returncode != 0
    output = _combined_output(result).lower()
    assert "runtime state is missing" in output
    if live_condition == "matching_process":
        assert "matching application process" in output
    else:
        assert "port 8000" in output
    assert (desktop / SHORTCUT_NAME).is_file()
    assert (start_menu / SHORTCUT_NAME).is_file()
    assert runtime_sentinel.read_text(encoding="utf-8") == "preserve"


def test_ac_d05_install_failure_creates_no_shortcuts(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "desktop-product"
    _copy_scripts(
        project_root,
        INSTALL_SCRIPT,
        LAUNCH_SCRIPT,
        STOP_SCRIPT,
        UNINSTALL_SCRIPT,
    )
    (project_root / "scripts" / "setup.ps1").write_text(
        "Write-Error 'required setup failed'\nexit 17\n",
        encoding="utf-8",
    )
    desktop = tmp_path / "Desktop"
    start_menu = tmp_path / "StartMenu"

    result = _run_script(
        project_root / "scripts" / INSTALL_SCRIPT.name,
        "-DesktopDirectory",
        str(desktop),
        "-StartMenuDirectory",
        str(start_menu),
        cwd=project_root,
        timeout=30,
    )

    assert result.returncode != 0
    assert "setup" in _combined_output(result).lower()
    assert not (desktop / SHORTCUT_NAME).exists()
    assert not (start_menu / SHORTCUT_NAME).exists()
