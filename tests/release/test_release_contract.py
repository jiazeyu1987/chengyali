from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.e2e.conftest import _required_browser_executable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = (
    PROJECT_ROOT / ".artifacts" / "loan-interest-accrual-v1" / "release"
)
EXPORT_SHEETS = [
    "计提结果",
    "分段明细",
    "公司汇总",
    "资本化汇总",
    "校验结果",
    "计算参数",
]


def _json(name: str) -> object:
    path = RELEASE_ROOT / name
    assert path.is_file(), f"missing release evidence: {name}"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_release_verifier_exists_and_is_fail_fast() -> None:
    script = PROJECT_ROOT / "scripts" / "verify-release.ps1"
    assert script.is_file(), "scripts/verify-release.ps1 is required"
    text = script.read_text(encoding="utf-8-sig")
    assert '$ErrorActionPreference = "Stop"' in text
    assert "LIA_PLAYWRIGHT_EXECUTABLE" in text
    assert "playwright install" not in text
    assert "Write-Warning" not in text

    ordered_stages = [
        "tests\\bootstrap",
        "tests\\unit",
        "tests\\integration",
        "tests\\historical",
        "scripts\\smoke.ps1",
        "tests\\e2e",
        "tests\\release",
    ]
    positions = [text.index(stage) for stage in ordered_stages]
    assert positions == sorted(positions)


def test_browser_executable_must_be_explicit_and_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("LIA_PLAYWRIGHT_EXECUTABLE", raising=False)
    with pytest.raises(pytest.fail.Exception):
        _required_browser_executable()

    missing = tmp_path / "missing-chromium.exe"
    monkeypatch.setenv("LIA_PLAYWRIGHT_EXECUTABLE", str(missing))
    with pytest.raises(pytest.fail.Exception):
        _required_browser_executable()


def test_release_evidence_bundle_is_complete_and_consistent() -> None:
    matrix = _json("acceptance-matrix.json")
    requests = _json("network-requests.json")
    inspection = _json("workbook-inspection.json")
    hashes = _json("source-hashes.json")

    assert matrix["result"] in {"pass", "blocked"}
    criteria = matrix["acceptance_criteria"]
    assert [item["acceptance_id"] for item in criteria] == [
        f"AC-{number:02d}" for number in range(1, 33)
    ]
    assert all(item["status"] in {"pass", "blocked"} for item in criteria)
    assert all(item["evidence"] for item in criteria)
    blocked = [item for item in criteria if item["status"] == "blocked"]
    if matrix["result"] == "blocked":
        assert [item["acceptance_id"] for item in blocked] == [
            "AC-01",
            "AC-31",
            "AC-32",
        ]
        required_changes = _json("required-changes.json")
        assert required_changes["status"] == "blocked"
        assert required_changes["required_changes"][0]["path"] == "/favicon.ico"
    else:
        assert blocked == []

    assert requests
    for request in requests:
        parsed = urlsplit(request["url"])
        assert parsed.scheme == "http"
        assert parsed.hostname == "127.0.0.1"

    assert inspection["template"]["sheet_names"] == ["贷款主表", "资金变动"]
    assert inspection["export"]["sheet_names"] == EXPORT_SHEETS
    assert inspection["export"]["formula_count"] == 0
    assert inspection["export"]["package_problems"] == []

    assert hashes["valid_source"]["unchanged"] is True
    assert hashes["invalid_source"]["unchanged"] is True
    assert hashes["export_download"]["distinct_from_valid_source"] is True
    if "historical_source" in hashes:
        historical = hashes["historical_source"]
        entries = historical if isinstance(historical, list) else [historical]
        assert entries
        assert all(item["unchanged"] is True for item in entries)

    required_artifacts = {
        "downloads": {".xlsx"},
        "screenshots": {".png"},
        "traces": {".zip"},
    }
    for directory, suffixes in required_artifacts.items():
        evidence_directory = RELEASE_ROOT / directory
        assert evidence_directory.is_dir()
        files = [path for path in evidence_directory.iterdir() if path.is_file()]
        assert files
        assert suffixes.issubset({path.suffix.lower() for path in files})
        assert all(path.stat().st_size > 0 for path in files)
