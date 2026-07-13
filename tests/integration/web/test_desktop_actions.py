from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from loan_interest_accrual.web import create_app
from loan_interest_accrual.web.desktop_actions import (
    DesktopActions,
    get_desktop_actions,
)


WEB_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "loan_interest_accrual"
    / "web"
)
LOCAL_ACTION_HEADERS = {
    "X-Local-Tool-Action": "loan-interest-accrual",
}


class RecordingRunner:
    def __init__(
        self,
        failure: OSError | None = None,
        process: RecordingProcess | None = None,
    ) -> None:
        self.failure = failure
        self.process = process or RecordingProcess()
        self.calls: list[tuple[tuple[str, ...], int]] = []

    def __call__(
        self,
        command: tuple[str, ...],
        *,
        creationflags: int,
    ) -> RecordingProcess:
        self.calls.append((command, creationflags))
        if self.failure is not None:
            raise self.failure
        return self.process


class RecordingProcess:
    def __init__(self, return_code: int | None = None) -> None:
        self.return_code = return_code
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


def _client(actions: DesktopActions) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_desktop_actions] = lambda: actions
    return TestClient(application)


def test_homepage_exposes_local_only_statement_and_accessible_instructions() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "数据仅在本机处理，不会上传到外部网络" in response.text
    assert 'id="usage-dialog"' in response.text
    assert 'aria-labelledby="usage-dialog-title"' in response.text
    assert 'id="usage-dialog-title"' in response.text
    assert "下载标准模板" in response.text
    assert "选择计提月份" in response.text
    assert "上传填写完成的 .xlsx 文件" in response.text
    assert "计算并预览" in response.text
    assert "导出结果" in response.text
    assert 'id="open-downloads-button"' in response.text
    assert 'id="exit-tool-button"' in response.text
    assert "http://" not in response.text
    assert "https://" not in response.text


def test_desktop_actions_are_post_only() -> None:
    application = create_app()

    with TestClient(application) as client:
        downloads = client.get("/desktop/open-downloads")
        exit_request = client.get("/desktop/exit")

    assert downloads.status_code == 405
    assert exit_request.status_code == 405


def test_desktop_actions_reject_requests_without_local_action_header(
    tmp_path: Path,
) -> None:
    downloads_path = tmp_path / "Downloads"
    downloads_path.mkdir()
    stop_script = tmp_path / "scripts" / "desktop-stop.ps1"
    stop_script.parent.mkdir()
    stop_script.write_text("exit 0", encoding="utf-8")
    runner = RecordingRunner()
    actions = DesktopActions(
        downloads_path=downloads_path,
        stop_script_path=stop_script,
        runner=runner,
    )

    with _client(actions) as client:
        downloads = client.post("/desktop/open-downloads")
        exit_request = client.post("/desktop/exit")

    assert downloads.status_code == 403
    assert exit_request.status_code == 403
    assert downloads.json()["error_code"] == "LOCAL_ACTION_FORBIDDEN"
    assert exit_request.json()["error_code"] == "LOCAL_ACTION_FORBIDDEN"
    assert runner.calls == []


def test_default_actions_target_current_user_and_exact_project_stop_script() -> None:
    actions = get_desktop_actions()

    assert actions.downloads_path == Path.home() / "Downloads"
    assert actions.stop_script_path == (
        WEB_ROOT.parents[2] / "scripts" / "desktop-stop.ps1"
    )


def test_open_downloads_uses_current_user_folder_and_structured_success(
    tmp_path: Path,
) -> None:
    downloads_path = tmp_path / "Downloads"
    downloads_path.mkdir()
    runner = RecordingRunner()
    actions = DesktopActions(
        downloads_path=downloads_path,
        stop_script_path=tmp_path / "desktop-stop.ps1",
        runner=runner,
    )

    with _client(actions) as client:
        response = client.post(
            "/desktop/open-downloads",
            json={"command": "ignored-by-contract"},
            headers=LOCAL_ACTION_HEADERS,
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "action": "open_downloads",
        "state": "success",
        "message": "已打开当前用户的下载目录。",
    }
    assert runner.calls == [
        (("explorer.exe", str(downloads_path)), 0),
    ]


def test_open_downloads_reports_runner_failure_without_fallback(
    tmp_path: Path,
) -> None:
    downloads_path = tmp_path / "Downloads"
    downloads_path.mkdir()
    runner = RecordingRunner(OSError("explorer unavailable"))
    actions = DesktopActions(
        downloads_path=downloads_path,
        stop_script_path=tmp_path / "desktop-stop.ps1",
        runner=runner,
    )

    with _client(actions) as client:
        response = client.post(
            "/desktop/open-downloads",
            headers=LOCAL_ACTION_HEADERS,
        )

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "action": "open_downloads",
        "state": "failure",
        "error_code": "DOWNLOADS_OPEN_FAILED",
        "message": "无法打开当前用户的下载目录，请确认 Windows 资源管理器可用。",
    }
    assert runner.calls == [
        (("explorer.exe", str(downloads_path)), 0),
    ]


def test_open_downloads_reports_missing_folder_without_running_command(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    actions = DesktopActions(
        downloads_path=tmp_path / "Downloads",
        stop_script_path=tmp_path / "desktop-stop.ps1",
        runner=runner,
    )

    with _client(actions) as client:
        response = client.post(
            "/desktop/open-downloads",
            headers=LOCAL_ACTION_HEADERS,
        )

    assert response.status_code == 503
    assert response.json()["error_code"] == "DOWNLOADS_NOT_FOUND"
    assert runner.calls == []


def test_exit_request_runs_exact_hidden_project_stop_command(
    tmp_path: Path,
) -> None:
    stop_script = tmp_path / "scripts" / "desktop-stop.ps1"
    stop_script.parent.mkdir()
    stop_script.write_text("exit 0", encoding="utf-8")
    runner = RecordingRunner()
    actions = DesktopActions(
        downloads_path=tmp_path / "Downloads",
        stop_script_path=stop_script,
        runner=runner,
    )

    with _client(actions) as client:
        response = client.post(
            "/desktop/exit",
            json={
                "command": "Stop-Process",
                "arguments": ["-Id", "1"],
            },
            headers=LOCAL_ACTION_HEADERS,
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload == {
        "success": True,
        "action": "exit",
        "state": "shutdown_requested",
        "request_id": payload["request_id"],
        "status_url": f"/desktop/exit-status/{payload['request_id']}",
        "message": "退出请求已提交，工具即将关闭。",
    }
    assert runner.calls == [
        (
            (
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                    str(stop_script),
                    "-DelayMilliseconds",
                    "750",
                    "-Detach",
                ),
                subprocess.CREATE_NO_WINDOW,
            )
        ]


def test_exit_request_reports_runner_failure_without_success(
    tmp_path: Path,
) -> None:
    stop_script = tmp_path / "scripts" / "desktop-stop.ps1"
    stop_script.parent.mkdir()
    stop_script.write_text("exit 0", encoding="utf-8")
    runner = RecordingRunner(OSError("powershell unavailable"))
    actions = DesktopActions(
        downloads_path=tmp_path / "Downloads",
        stop_script_path=stop_script,
        runner=runner,
    )

    with _client(actions) as client:
        response = client.post(
            "/desktop/exit",
            headers=LOCAL_ACTION_HEADERS,
        )

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "action": "exit",
        "state": "failure",
        "error_code": "DESKTOP_STOP_FAILED",
        "message": "无法启动安全退出程序，请重新打开工具后重试。",
    }
    assert len(runner.calls) == 1


def test_exit_request_reports_missing_project_stop_script(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    actions = DesktopActions(
        downloads_path=tmp_path / "Downloads",
        stop_script_path=tmp_path / "scripts" / "desktop-stop.ps1",
        runner=runner,
    )

    with _client(actions) as client:
        response = client.post(
            "/desktop/exit",
            headers=LOCAL_ACTION_HEADERS,
        )

    assert response.status_code == 503
    assert response.json()["error_code"] == "DESKTOP_STOP_SCRIPT_NOT_FOUND"
    assert response.json()["state"] == "failure"
    assert runner.calls == []


def test_exit_helper_nonzero_is_observable_and_not_reported_as_success(
    tmp_path: Path,
) -> None:
    stop_script = tmp_path / "scripts" / "desktop-stop.ps1"
    stop_script.parent.mkdir()
    stop_script.write_text("exit 17", encoding="utf-8")
    process = RecordingProcess()
    runner = RecordingRunner(process=process)
    actions = DesktopActions(
        downloads_path=tmp_path / "Downloads",
        stop_script_path=stop_script,
        runner=runner,
    )

    with _client(actions) as client:
        requested = client.post(
            "/desktop/exit",
            headers=LOCAL_ACTION_HEADERS,
        )
        request_id = requested.json()["request_id"]
        process.return_code = 17
        completed = client.get(
            f"/desktop/exit-status/{request_id}",
            headers=LOCAL_ACTION_HEADERS,
        )

    assert requested.status_code == 202
    assert completed.status_code == 503
    assert completed.json() == {
        "success": False,
        "action": "exit",
        "state": "failure",
        "error_code": "DESKTOP_STOP_FAILED",
        "message": "安全退出失败，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
    }


def test_detached_worker_acceptance_stays_pending_until_shutdown_timeout(
    tmp_path: Path,
) -> None:
    stop_script = tmp_path / "scripts" / "desktop-stop.ps1"
    stop_script.parent.mkdir()
    stop_script.write_text("exit 0", encoding="utf-8")
    process = RecordingProcess(return_code=0)
    runner = RecordingRunner(process=process)
    now = [10.0]
    actions = DesktopActions(
        downloads_path=tmp_path / "Downloads",
        stop_script_path=stop_script,
        runner=runner,
        clock=lambda: now[0],
        exit_timeout_seconds=2.0,
    )

    with _client(actions) as client:
        requested = client.post(
            "/desktop/exit",
            headers=LOCAL_ACTION_HEADERS,
        )
        request_id = requested.json()["request_id"]
        pending = client.get(
            f"/desktop/exit-status/{request_id}",
            headers=LOCAL_ACTION_HEADERS,
        )
        now[0] = 12.1
        timed_out = client.get(
            f"/desktop/exit-status/{request_id}",
            headers=LOCAL_ACTION_HEADERS,
        )

    assert pending.status_code == 202
    assert pending.json()["state"] == "shutdown_pending"
    assert timed_out.status_code == 503
    assert timed_out.json()["error_code"] == "DESKTOP_STOP_TIMEOUT"


def test_frontend_uses_clear_chinese_action_states_and_existing_contracts() -> None:
    script = (WEB_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'fetch("/calculate"' in script
    assert 'fetch("/export"' in script
    assert 'fetch("/desktop/open-downloads"' in script
    assert 'fetch("/desktop/exit"' in script
    assert "fetch(statusUrl" in script
    assert 'fetch("/health"' in script
    assert '"X-Local-Tool-Action": "loan-interest-accrual"' in script
    assert 'method: "POST"' in script
    assert "正在打开下载目录" in script
    assert "正在提交退出请求" in script
    assert "操作失败" in script
    assert "正在安全退出" in script
    assert "工具已安全退出" in script
    assert "安全退出失败，工具仍在运行" in script


def test_desktop_layout_styles_keep_page_width_and_actions_stable() -> None:
    stylesheet = (WEB_ROOT / "static" / "styles.css").read_text(
        encoding="utf-8"
    )

    assert "overflow-x: hidden" in stylesheet
    assert ".desktop-actions" in stylesheet
    assert "flex-wrap: wrap" in stylesheet
    assert ".table-shell" in stylesheet
    assert "overflow-x: auto" in stylesheet
    assert "@media (max-width: 860px)" in stylesheet
    assert "@media (max-width: 520px)" in stylesheet
