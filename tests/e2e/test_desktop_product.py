from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import Browser, Page, expect


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_RELEASE_ROOT = (
    PROJECT_ROOT
    / ".artifacts"
    / "loan-interest-accrual-desktop-v1"
    / "release"
)


def _fulfill_json(route, payload: dict[str, object], status: int) -> None:
    route.fulfill(
        status=status,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, ensure_ascii=False),
    )


def test_finance_user_desktop_actions_and_help(
    browser: Browser,
    app_url: str,
) -> None:
    screenshots = DESKTOP_RELEASE_ROOT / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    page: Page = browser.new_page(viewport={"width": 1366, "height": 768})
    action_requests: list[dict[str, object]] = []

    def open_downloads(route, request) -> None:
        action_requests.append(
            {
                "path": "/desktop/open-downloads",
                "method": request.method,
                "headers": request.headers,
            }
        )
        _fulfill_json(
            route,
            {
                "success": True,
                "action": "open_downloads",
                "state": "success",
                "message": "已打开当前用户的下载目录。",
            },
            200,
        )

    page.route("**/desktop/open-downloads", open_downloads)
    try:
        page.goto(app_url, wait_until="networkidle")
        expect(page.get_by_text("数据仅在本机处理，不会上传到外部网络")).to_be_visible()

        page.locator("#usage-button").click()
        dialog = page.locator("#usage-dialog")
        expect(dialog).to_be_visible()
        expect(dialog.get_by_text("完成一次贷款利息计提")).to_be_visible()
        expect(dialog.locator("li")).to_have_count(5)
        expect(
            dialog.get_by_text("也可以上传已覆盖规则的历史台账，月份需与台账中实际数据一致。")
        ).to_be_visible()
        page.screenshot(path=screenshots / "usage-dialog.png", full_page=True)
        dialog.locator(".dialog-confirm").click()
        expect(dialog).to_be_hidden()
        expect(page.locator("#usage-button")).to_be_focused()

        page.locator("#open-downloads-button").click()
        expect(page.locator("#status-title")).to_have_text("操作成功")
        expect(page.locator("#status-message")).to_have_text(
            "已打开当前用户的下载目录。"
        )

        page.screenshot(path=screenshots / "desktop-actions.png", full_page=True)

        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth"
        )
        assert [item["path"] for item in action_requests] == [
            "/desktop/open-downloads",
        ]
        for request in action_requests:
            assert request["method"] == "POST"
            headers = request["headers"]
            assert (
                headers["x-local-tool-action"]
                == "loan-interest-accrual"
            )
    finally:
        page.close()

    (DESKTOP_RELEASE_ROOT / "desktop-ui.json").write_text(
        json.dumps(
            {
                "result": "pass",
                "local_only_notice": True,
                "usage_dialog": True,
                "local_action_header": True,
                "action_requests": action_requests,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_failed_stop_helper_reenables_desktop_actions(
    browser: Browser,
    app_url: str,
) -> None:
    page: Page = browser.new_page(viewport={"width": 1366, "height": 768})

    def exit_tool(route) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "action": "exit",
                "state": "shutdown_requested",
                "message": "退出请求已提交，正在确认安全关闭结果。",
                "request_id": "failed-stop",
                "status_url": "/desktop/exit-status/failed-stop",
            },
            202,
        )

    def failed_status(route) -> None:
        _fulfill_json(
            route,
            {
                "success": False,
                "action": "exit",
                "state": "failure",
                "error_code": "DESKTOP_STOP_FAILED",
                "message": "安全退出失败，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
            },
            503,
        )

    page.route("**/desktop/exit", exit_tool)
    page.route("**/desktop/exit-status/failed-stop", failed_status)
    try:
        page.goto(app_url, wait_until="networkidle")
        page.once("dialog", lambda prompt: prompt.accept())
        page.locator("#exit-tool-button").click()

        expect(page.locator("#status-title")).to_have_text("操作失败")
        expect(page.locator("#status-message")).to_have_text(
            "安全退出失败，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。"
        )
        expect(page.locator("#exit-tool-button")).to_be_enabled()
        expect(page.locator("#calculate-button")).to_be_enabled()
        expect(page.locator("#open-downloads-button")).to_be_enabled()
    finally:
        page.close()


def test_real_fixed_port_desktop_exit_stops_owned_service(
    browser: Browser,
    desktop_app_url: str,
) -> None:
    screenshots = DESKTOP_RELEASE_ROOT / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    state_path = (
        PROJECT_ROOT
        / ".artifacts"
        / "loan-interest-accrual-desktop-v1"
        / "runtime"
        / "app.json"
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["schema_version"] == 2
    assert re.fullmatch(r"[0-9a-f]{32}", state["launch_token"])
    page: Page = browser.new_page(viewport={"width": 1366, "height": 768})
    try:
        page.goto(desktop_app_url, wait_until="networkidle")
        page.once("dialog", lambda prompt: prompt.accept())
        page.locator("#exit-tool-button").click()

        expect(page.locator("#status-title")).to_have_text("正在安全退出")
        expect(page.locator("#status-title")).to_have_text(
            "工具已安全退出",
            timeout=15_000,
        )
        expect(page.locator("#status-message")).to_have_text(
            "本机服务已停止，可以关闭此页面。"
        )
        page.screenshot(
            path=screenshots / "real-desktop-exit.png",
            full_page=True,
        )
    finally:
        page.close()

    deadline = time.monotonic() + 10
    while state_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not state_path.exists()
    (DESKTOP_RELEASE_ROOT / "desktop-lifecycle.json").write_text(
        json.dumps(
            {
                "result": "pass",
                "launcher": "scripts/desktop-launch.ps1",
                "fixed_port": 8000,
                "exit_route": "/desktop/exit",
                "request_mocked": False,
                "launch_token_present": True,
                "state_removed": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
