from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Callable, Protocol
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_STOP_SCRIPT = PROJECT_ROOT / "scripts" / "desktop-stop.ps1"


class ProcessHandle(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class ProcessRunner(Protocol):
    def __call__(
        self,
        command: tuple[str, ...],
        *,
        creationflags: int,
    ) -> ProcessHandle: ...


EmbeddedExitHandler = Callable[[], ProcessHandle]
_embedded_exit_handler: EmbeddedExitHandler | None = None


class DesktopActionError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class DesktopExitStatus:
    state: str
    message: str


@dataclass(frozen=True)
class _ExitRequest:
    process: ProcessHandle
    started_at: float


@dataclass
class DesktopActions:
    downloads_path: Path
    stop_script_path: Path | None
    runner: ProcessRunner
    exit_handler: EmbeddedExitHandler | None = None
    exit_command_description: str = "desktop-stop.ps1"
    clock: Callable[[], float] = time.monotonic
    exit_timeout_seconds: float = 12.0
    _exit_requests: dict[str, _ExitRequest] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _exit_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def open_downloads(self) -> None:
        if not self.downloads_path.is_dir():
            raise DesktopActionError(
                "DOWNLOADS_NOT_FOUND",
                f"当前用户的下载目录不存在：{self.downloads_path}",
            )
        try:
            self.runner(
                ("explorer.exe", str(self.downloads_path)),
                creationflags=0,
            )
        except OSError as error:
            raise DesktopActionError(
                "DOWNLOADS_OPEN_FAILED",
                "无法打开当前用户的下载目录，请确认 Windows 资源管理器可用。",
            ) from error

    def ensure_exit_available(self) -> None:
        if self.exit_handler is not None:
            return
        if self.stop_script_path is None or not self.stop_script_path.is_file():
            raise DesktopActionError(
                "DESKTOP_STOP_SCRIPT_NOT_FOUND",
                f"退出脚本不存在：{self.stop_script_path}",
            )

    def exit(self) -> str:
        self.ensure_exit_available()
        process = self._start_exit_process()
        if process is None:
            raise DesktopActionError(
                "DESKTOP_STOP_TRACKING_FAILED",
                "安全退出程序已启动，但无法跟踪执行结果。工具仍在运行，请重试。",
            )

        request_id = uuid4().hex
        with self._exit_lock:
            self._exit_requests[request_id] = _ExitRequest(
                process=process,
                started_at=self.clock(),
            )
        return request_id

    def _start_exit_process(self) -> ProcessHandle:
        if self.exit_handler is not None:
            try:
                return self.exit_handler()
            except OSError as error:
                raise DesktopActionError(
                    "DESKTOP_STOP_FAILED",
                    "无法启动安全退出程序，请重新打开工具后重试。",
                ) from error

        if self.stop_script_path is None:
            raise DesktopActionError(
                "DESKTOP_STOP_SCRIPT_NOT_FOUND",
                "退出脚本不存在。",
            )
        command = (
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(self.stop_script_path),
            "-DelayMilliseconds",
            "750",
            "-Detach",
        )
        try:
            return self.runner(
                command,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError as error:
            raise DesktopActionError(
                "DESKTOP_STOP_FAILED",
                "无法启动安全退出程序，请重新打开工具后重试。",
            ) from error

    def exit_status(self, request_id: str) -> DesktopExitStatus:
        with self._exit_lock:
            request = self._exit_requests.get(request_id)
            if request is None:
                raise DesktopActionError(
                    "DESKTOP_EXIT_REQUEST_NOT_FOUND",
                    "退出状态请求不存在或已结束，请重新发起退出。",
                )
            try:
                return_code = request.process.poll()
            except OSError as error:
                del self._exit_requests[request_id]
                raise DesktopActionError(
                    "DESKTOP_STOP_FAILED",
                    "安全退出失败，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
                ) from error

            elapsed = self.clock() - request.started_at
            if return_code is not None and return_code != 0:
                del self._exit_requests[request_id]
                raise DesktopActionError(
                    "DESKTOP_STOP_FAILED",
                    "安全退出失败，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
                )
            if elapsed < self.exit_timeout_seconds:
                return DesktopExitStatus(
                    state="shutdown_pending",
                    message="安全退出正在执行，请稍候。",
                )
            del self._exit_requests[request_id]

        if return_code is None:
            try:
                request.process.terminate()
                request.process.wait(timeout=2.0)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise DesktopActionError(
                    "DESKTOP_STOP_TIMEOUT",
                    "安全退出超时，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
                ) from error
            raise DesktopActionError(
                "DESKTOP_STOP_TIMEOUT",
                "安全退出超时，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
            )

        raise DesktopActionError(
            "DESKTOP_STOP_TIMEOUT",
            "安全退出超时，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
        )


def _run_process(
    command: tuple[str, ...],
    *,
    creationflags: int,
) -> ProcessHandle:
    return subprocess.Popen(
        command,
        creationflags=creationflags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def configure_embedded_exit_handler(handler: EmbeddedExitHandler) -> None:
    global _embedded_exit_handler
    _embedded_exit_handler = handler
    get_desktop_actions.cache_clear()


@lru_cache(maxsize=1)
def get_desktop_actions() -> DesktopActions:
    embedded = _embedded_exit_handler
    return DesktopActions(
        downloads_path=Path.home() / "Downloads",
        stop_script_path=None if embedded is not None else DESKTOP_STOP_SCRIPT,
        runner=_run_process,
        exit_handler=embedded,
        exit_command_description=(
            "embedded server shutdown"
            if embedded is not None
            else "desktop-stop.ps1"
        ),
    )
