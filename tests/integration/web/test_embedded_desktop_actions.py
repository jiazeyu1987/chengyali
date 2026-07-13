from __future__ import annotations

from pathlib import Path

from loan_interest_accrual.web.desktop_actions import DesktopActions


class RecordingProcess:
    def __init__(self) -> None:
        self.return_code: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True
        self.return_code = -15

    def wait(self, timeout: float | None = None) -> int:
        assert timeout is None or timeout > 0
        assert self.return_code is not None
        return self.return_code


class FailingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], int]] = []

    def __call__(
        self,
        command: tuple[str, ...],
        *,
        creationflags: int,
    ) -> RecordingProcess:
        self.calls.append((command, creationflags))
        raise AssertionError("standalone EXE exit must not invoke shell scripts")


def test_embedded_exit_handler_does_not_require_project_stop_script(
    tmp_path: Path,
) -> None:
    process = RecordingProcess()
    calls: list[str] = []

    def embedded_exit() -> RecordingProcess:
        calls.append("embedded_exit")
        return process

    actions = DesktopActions(
        downloads_path=tmp_path,
        stop_script_path=None,
        runner=FailingRunner(),
        exit_handler=embedded_exit,
        exit_command_description="embedded uvicorn shutdown",
    )

    request_id = actions.exit()
    status = actions.exit_status(request_id)

    assert calls == ["embedded_exit"]
    assert status.state == "shutdown_pending"
    assert "退出" in status.message
