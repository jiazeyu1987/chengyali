from __future__ import annotations

import socket
import threading
import time
import traceback
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import uvicorn
from tkinter import messagebox

from loan_interest_accrual.web import create_app
from loan_interest_accrual.web.desktop_actions import (
    configure_embedded_exit_handler,
)


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
HOME_URL = f"http://{LOOPBACK_HOST}:{DEFAULT_PORT}/"
HEALTH_URL = f"http://{LOOPBACK_HOST}:{DEFAULT_PORT}/health"
STARTUP_TIMEOUT_SECONDS = 20.0
SHUTDOWN_DELAY_SECONDS = 0.5
LOG_DIR = Path.home() / "AppData" / "Local" / "贷款利息自动计提工具"
STARTUP_LOG = LOG_DIR / "startup.log"


@dataclass
class EmbeddedShutdownProcess:
    return_code: int | None = None
    terminated: bool = False

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True
        self.return_code = -15

    def wait(self, timeout: float | None = None) -> int:
        deadline = None if timeout is None else time.monotonic() + timeout
        while self.return_code is None:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("embedded shutdown did not complete")
            time.sleep(0.05)
        return self.return_code


def _assert_fixed_port_available() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((LOOPBACK_HOST, DEFAULT_PORT))


def _write_startup_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with STARTUP_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def _open_browser_when_ready() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(HOME_URL)
                    return
        except OSError:
            time.sleep(0.25)
    messagebox.showerror(
        "贷款利息自动计提工具",
        "工具已启动，但未能自动打开页面。请重新双击可执行文件。",
    )


def _make_embedded_exit_handler(
    server: uvicorn.Server,
) -> Callable[[], EmbeddedShutdownProcess]:
    def request_shutdown() -> EmbeddedShutdownProcess:
        process = EmbeddedShutdownProcess()

        def stop_server() -> None:
            time.sleep(SHUTDOWN_DELAY_SECONDS)
            server.should_exit = True
            process.return_code = 0

        threading.Thread(target=stop_server, daemon=True).start()
        return process

    return request_shutdown


def main() -> int:
    try:
        _write_startup_log("starting standalone exe")
        _assert_fixed_port_available()
        _write_startup_log("fixed port is available")
        app = create_app()
        _write_startup_log("fastapi app created")
        config = uvicorn.Config(
            app,
            host=LOOPBACK_HOST,
            port=DEFAULT_PORT,
            log_level="warning",
            log_config=None,
            access_log=False,
        )
        server = uvicorn.Server(config)
        configure_embedded_exit_handler(_make_embedded_exit_handler(server))
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()
        _write_startup_log("starting embedded uvicorn server")
        server.run()
        _write_startup_log("embedded uvicorn server stopped")
    except Exception as error:
        _write_startup_log("startup failed")
        _write_startup_log(traceback.format_exc())
        messagebox.showerror("贷款利息自动计提工具", str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
