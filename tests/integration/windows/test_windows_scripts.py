from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
SETUP_SCRIPT = SCRIPTS_ROOT / "setup.ps1"
START_SCRIPT = SCRIPTS_ROOT / "start.ps1"
SMOKE_SCRIPT = SCRIPTS_ROOT / "smoke.ps1"
EVIDENCE_ROOT = (
    PROJECT_ROOT
    / ".artifacts"
    / "loan-interest-accrual-v1"
    / "startup"
)
POWERSHELL = (
    Path(os.environ["SystemRoot"])
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)


def _run_script(
    script: Path,
    *arguments: str,
    cwd: Path = PROJECT_ROOT,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *arguments,
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_setup_requires_exact_python_pins_without_browser_download() -> None:
    source = SETUP_SCRIPT.read_text(encoding="utf-8")
    normalized = source.replace("`", "").lower()

    assert '$erroractionpreference = "stop"' in normalized
    assert "py -3.12" in normalized
    assert ".venv\\scripts\\python.exe" in normalized
    assert "-m pip install" in normalized
    assert "requirements.txt" in normalized
    assert "-m playwright install chromium" not in normalized
    assert "&&" not in source

    requirements = (PROJECT_ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    )
    entries = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert entries
    assert all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*==[^=\s]+", entry) for entry in entries)


def test_setup_fails_when_py_3_12_launcher_is_unavailable(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    copied_setup = scripts / "setup.ps1"
    shutil.copy2(SETUP_SCRIPT, copied_setup)
    shutil.copy2(PROJECT_ROOT / "requirements.txt", tmp_path / "requirements.txt")

    clean_env = os.environ.copy()
    clean_env["PATH"] = os.pathsep.join(
        [
            str(Path(os.environ["SystemRoot"]) / "System32"),
            str(Path(os.environ["SystemRoot"])),
        ]
    )
    result = _run_script(
        copied_setup,
        cwd=tmp_path,
        env=clean_env,
        timeout=20,
    )

    assert result.returncode != 0
    assert "py -3.12" in _combined_output(result)
    assert not (tmp_path / ".venv").exists()


def test_start_uses_only_project_venv_loopback_and_exact_app() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")
    normalized = source.replace("`", "").lower()

    assert '$erroractionpreference = "stop"' in normalized
    assert ".venv\\scripts\\python.exe" in normalized
    assert "127.0.0.1" in source
    assert "-m uvicorn" in normalized
    assert "loan_interest_accrual.web:app" in source
    assert "--host" in normalized
    assert "--port" in normalized
    assert "validaterange(1, 65535)" in normalized
    assert "&&" not in source


@pytest.mark.parametrize(
    ("arguments", "expected_text"),
    [
        (("-HostAddress", "0.0.0.0", "-Port", "8123"), "127.0.0.1"),
        (("-Port", "0"), "Port"),
        (("-Port", "65536"), "Port"),
    ],
)
def test_start_rejects_non_loopback_and_invalid_ports(
    arguments: tuple[str, ...],
    expected_text: str,
) -> None:
    result = _run_script(START_SCRIPT, *arguments, timeout=20)

    assert result.returncode != 0
    assert expected_text.lower() in _combined_output(result).lower()


def test_start_fails_when_project_virtual_environment_is_missing(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    copied_start = scripts / "start.ps1"
    shutil.copy2(START_SCRIPT, copied_start)

    result = _run_script(
        copied_start,
        "-Port",
        str(_unused_loopback_port()),
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode != 0
    assert ".venv\\Scripts\\python.exe" in _combined_output(result)


def test_start_rejects_an_occupied_loopback_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = int(listener.getsockname()[1])

        result = _run_script(START_SCRIPT, "-Port", str(port), timeout=20)

    assert result.returncode != 0
    assert "already in use" in _combined_output(result).lower()


def test_smoke_contract_is_hidden_owned_loopback_and_two_runs() -> None:
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")
    normalized = source.replace("`", "").lower()

    assert "start-process" in normalized
    assert "-windowstyle hidden" in normalized
    assert "start.ps1" in normalized
    assert "/health" in source
    assert "/static/styles.css" in source
    assert "get-nettcpconnection" in normalized
    assert "127.0.0.1" in source
    assert "1..2" in normalized
    assert "setup.log" in normalized
    assert "startup.log" in normalized
    assert "listener.json" in normalized
    assert "shutdown.log" in normalized
    assert "stop-process" in normalized
    assert "&&" not in source

    urls = re.findall(r"https?://[^\s'\"`]+", source)
    assert urls
    assert all(url.startswith("http://127.0.0.1") for url in urls)


def test_smoke_waits_for_redirect_handle_release_before_log_cleanup() -> None:
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")
    normalized = source.replace("`", "").lower()

    wait_call = "wait-for-rootprocessexitandredirectrelease"
    stop_call = (
        "stop-ownedprocesstree -rootprocessid $serverprocess.id"
    )
    capture_call = "get-content -literalpath $logpath"

    assert wait_call in normalized
    assert ".waitforexit(" in normalized
    assert ".dispose()" in normalized
    assert "[system.io.fileshare]::none" in normalized
    assert normalized.index(stop_call) < normalized.index(wait_call)
    assert normalized.index(wait_call) < normalized.index(capture_call)


def test_smoke_starts_checks_and_cleans_the_owned_process_twice() -> None:
    port = _unused_loopback_port()
    result = _run_script(
        SMOKE_SCRIPT,
        "-Port",
        str(port),
        "-TimeoutSeconds",
        "30",
        timeout=90,
    )

    assert result.returncode == 0, _combined_output(result)

    expected_files = {
        "setup.log",
        "startup.log",
        "listener.json",
        "shutdown.log",
    }
    assert expected_files <= {
        path.name for path in EVIDENCE_ROOT.iterdir() if path.is_file()
    }

    setup_log = (EVIDENCE_ROOT / "setup.log").read_text(encoding="utf-8")
    startup_log = (EVIDENCE_ROOT / "startup.log").read_text(encoding="utf-8")
    shutdown_log = (EVIDENCE_ROOT / "shutdown.log").read_text(
        encoding="utf-8"
    )
    listeners = json.loads(
        (EVIDENCE_ROOT / "listener.json").read_text(encoding="utf-8-sig")
    )

    assert "PythonLauncher=3.12" in setup_log
    assert "VenvPython=3.12" in setup_log
    assert "[run 1]" in startup_log
    assert "[run 2]" in startup_log
    assert "[run 1] port released" in shutdown_log
    assert "[run 2] port released" in shutdown_log
    assert [record["run"] for record in listeners] == [1, 2]
    assert all(record["local_address"] == "127.0.0.1" for record in listeners)
    assert all(record["local_port"] == port for record in listeners)
    assert all(record["owning_process"] in record["owned_process_ids"] for record in listeners)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))
