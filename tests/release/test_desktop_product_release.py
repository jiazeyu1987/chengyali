from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_RELEASE_ROOT = (
    PROJECT_ROOT
    / ".artifacts"
    / "loan-interest-accrual-desktop-v1"
    / "release"
)


def test_release_verifier_owns_desktop_product_evidence_and_current_records() -> None:
    script = (
        PROJECT_ROOT / "scripts" / "verify-release.ps1"
    ).read_text(encoding="utf-8-sig")

    assert ".artifacts\\loan-interest-accrual-desktop-v1\\release" in script
    assert "doc\\tasks\\loan-interest-accrual-v1\\task.md" in script
    assert "doc\\tasks\\loan-interest-accrual-v1\\verification-report.md" in script
    assert "doc\\tasks\\loan-interest-accrual-desktop-v1\\task.md" in script
    assert (
        "doc\\tasks\\loan-interest-accrual-desktop-v1"
        "\\verification-report.md"
    ) in script
    assert "doc\\tasks\\loan-interest-accrual-desktop-v1\\frontend-feature-evidence.md" not in script
    assert "doc\\tasks\\loan-interest-accrual-desktop-v1\\test-plan.md" not in script
    assert "doc\\tasks\\loan-interest-accrual-desktop-v1\\task-state.json" not in script
    assert "doc\\tasks\\loan-interest-accrual-v1\\dev-plan.md" not in script
    assert "doc\\tasks\\loan-interest-accrual-v1\\test-report.md" not in script


def test_desktop_product_browser_evidence_is_complete() -> None:
    evidence_path = DESKTOP_RELEASE_ROOT / "desktop-ui.json"
    assert evidence_path.is_file()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert evidence["result"] == "pass"
    assert evidence["local_only_notice"] is True
    assert evidence["usage_dialog"] is True
    assert evidence["local_action_header"] is True
    assert [item["path"] for item in evidence["action_requests"]] == [
        "/desktop/open-downloads",
    ]

    lifecycle_path = DESKTOP_RELEASE_ROOT / "desktop-lifecycle.json"
    assert lifecycle_path.is_file()
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    assert lifecycle == {
        "result": "pass",
        "launcher": "scripts/desktop-launch.ps1",
        "fixed_port": 8000,
        "exit_route": "/desktop/exit",
        "request_mocked": False,
        "launch_token_present": True,
        "state_removed": True,
    }

    screenshots = DESKTOP_RELEASE_ROOT / "screenshots"
    assert (screenshots / "usage-dialog.png").stat().st_size > 0
    assert (screenshots / "desktop-actions.png").stat().st_size > 0
    assert (screenshots / "real-desktop-exit.png").stat().st_size > 0


def test_release_integration_evidence_covers_desktop_launch_ownership() -> None:
    junit_path = (
        PROJECT_ROOT
        / ".artifacts"
        / "loan-interest-accrual-v1"
        / "release"
        / "junit"
        / "integration.xml"
    )
    assert junit_path.is_file()
    test_cases = {
        case.attrib["name"]: case
        for case in ET.parse(junit_path).iter("testcase")
    }
    required_cases = {
        "test_ac_d02_concurrent_launches_serialize_and_reuse_single_owned_instance",
        "test_ac_d03_failed_launch_cleanup_preserves_replaced_state",
        "test_ac_d05_uninstall_missing_state_fails_closed[matching_process]",
        "test_ac_d05_uninstall_missing_state_fails_closed[fixed_port_listener]",
    }

    assert required_cases <= test_cases.keys()
    for name in required_cases:
        assert test_cases[name].find("failure") is None
        assert test_cases[name].find("error") is None
