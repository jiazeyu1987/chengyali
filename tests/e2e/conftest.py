from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import pytest
from playwright.sync_api import Browser, Playwright, sync_playwright

from tests.fixtures.e2e.workbooks import (
    write_invalid_workbook,
    write_valid_workbook,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = (
    PROJECT_ROOT / ".artifacts" / "loan-interest-accrual-v1" / "release"
)
DESKTOP_RUNTIME_ROOT = (
    PROJECT_ROOT
    / ".artifacts"
    / "loan-interest-accrual-desktop-v1"
    / "runtime"
)


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _required_browser_executable() -> Path:
    raw = os.environ.get("LIA_PLAYWRIGHT_EXECUTABLE")
    if not raw:
        pytest.fail(
            "LIA_PLAYWRIGHT_EXECUTABLE must explicitly point to Chromium.",
            pytrace=False,
        )
    executable = Path(raw)
    if not executable.is_file():
        pytest.fail(
            f"LIA_PLAYWRIGHT_EXECUTABLE does not exist: {executable}",
            pytrace=False,
        )
    return executable


def _wait_for_port_release(port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.1)
    pytest.fail(f"Task-owned server port was not released: {port}", pytrace=False)


def _wait_for_health(
    base_url: str,
    process: subprocess.CompletedProcess[str],
) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    pytest.fail(
        "desktop-launch.ps1 did not produce a healthy fixed-port service. "
        f"stdout={process.stdout!r} stderr={process.stderr!r}",
        pytrace=False,
    )


@pytest.fixture(scope="session", autouse=True)
def release_directories() -> None:
    for directory in [
        RELEASE_ROOT,
        RELEASE_ROOT / "downloads",
        RELEASE_ROOT / "logs",
        RELEASE_ROOT / "screenshots",
        RELEASE_ROOT / "traces",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def browser_executable() -> Path:
    return _required_browser_executable()


@pytest.fixture(scope="session")
def app_url(release_directories: None) -> str:
    port = _unused_loopback_port()
    stdout_path = RELEASE_ROOT / "logs" / "e2e-server.stdout.log"
    stderr_path = RELEASE_ROOT / "logs" / "e2e-server.stderr.log"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PROJECT_ROOT / "scripts" / "start.ps1"),
        "-HostAddress",
        "127.0.0.1",
        "-Port",
        str(port),
    ]
    with (
        stdout_path.open("w", encoding="utf-8") as stdout_file,
        stderr_path.open("w", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(
                    "start.ps1 exited before readiness. "
                    f"See {stdout_path.name} and {stderr_path.name}.",
                    pytrace=False,
                )
            try:
                with urlopen(f"{base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.2)
        else:
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
            pytest.fail("Timed out waiting for the task-owned server.", pytrace=False)

        yield base_url

        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    _wait_for_port_release(port)


@pytest.fixture()
def desktop_app_url(release_directories: None) -> str:
    state_path = DESKTOP_RUNTIME_ROOT / "app.json"
    launch_stdout_path = DESKTOP_RUNTIME_ROOT / "e2e-launch.stdout.log"
    launch_stderr_path = DESKTOP_RUNTIME_ROOT / "e2e-launch.stderr.log"
    stop_stdout_path = DESKTOP_RUNTIME_ROOT / "e2e-stop.stdout.log"
    stop_stderr_path = DESKTOP_RUNTIME_ROOT / "e2e-stop.stderr.log"
    if state_path.exists():
        pytest.fail(
            f"Fixed-port desktop runtime state must be absent before E2E: {state_path}",
            pytrace=False,
        )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            pytest.fail(
                "Fixed desktop port 8000 must be free before E2E.",
                pytrace=False,
            )

    DESKTOP_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    with (
        launch_stdout_path.open("w", encoding="utf-8") as stdout_file,
        launch_stderr_path.open("w", encoding="utf-8") as stderr_file,
    ):
        launched = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(PROJECT_ROOT / "scripts" / "desktop-launch.ps1"),
                "-NoDialog",
                "-NoBrowser",
            ],
            cwd=PROJECT_ROOT,
            stdout=stdout_file,
            stderr=stderr_file,
            timeout=40,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    assert launched.returncode == 0, (
        "desktop-launch.ps1 failed. "
        f"See {launch_stdout_path.name} and {launch_stderr_path.name}."
    )
    base_url = "http://127.0.0.1:8000"
    _wait_for_health(base_url, launched)

    yield base_url

    if state_path.exists():
        with (
            stop_stdout_path.open("w", encoding="utf-8") as stdout_file,
            stop_stderr_path.open("w", encoding="utf-8") as stderr_file,
        ):
            stopped = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(PROJECT_ROOT / "scripts" / "desktop-stop.ps1"),
                ],
                cwd=PROJECT_ROOT,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=20,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        assert stopped.returncode == 0, (
            "desktop-stop.ps1 cleanup failed. "
            f"See {stop_stdout_path.name} and {stop_stderr_path.name}."
        )
    _wait_for_port_release(8000)


@pytest.fixture(scope="session")
def playwright_runtime() -> Playwright:
    with sync_playwright() as runtime:
        yield runtime


@pytest.fixture(scope="session")
def browser(
    playwright_runtime: Playwright,
    browser_executable: Path,
) -> Browser:
    instance = playwright_runtime.chromium.launch(
        executable_path=str(browser_executable),
        headless=True,
    )
    yield instance
    instance.close()


@pytest.fixture()
def valid_workbook(tmp_path: Path) -> Path:
    return write_valid_workbook(tmp_path / "valid-e2e.xlsx")


@pytest.fixture()
def invalid_workbook(tmp_path: Path) -> Path:
    return write_invalid_workbook(tmp_path / "invalid-e2e.xlsx")
