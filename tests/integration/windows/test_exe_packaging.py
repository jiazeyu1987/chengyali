from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = PROJECT_ROOT / "src" / "loan_interest_accrual" / "desktop_exe.py"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-exe.ps1"
BUILD_REQUIREMENTS = PROJECT_ROOT / "requirements-build.txt"


def test_standalone_exe_entrypoint_is_local_double_click_runtime() -> None:
    assert ENTRYPOINT.is_file(), "standalone EXE entrypoint is required"
    source = ENTRYPOINT.read_text(encoding="utf-8")
    normalized = source.lower()

    assert "127.0.0.1" in source
    assert "8000" in source
    assert "uvicorn.Server" in source
    assert "log_config=None" in source
    assert "webbrowser.open" in source
    assert "configure_embedded_exit_handler" in source
    assert ".venv" not in normalized
    assert "desktop-launch.ps1" not in normalized
    assert "desktop-stop.ps1" not in normalized
    assert "powershell" not in normalized


def test_build_script_creates_onefile_windowed_exe_with_all_web_assets() -> None:
    assert BUILD_SCRIPT.is_file(), "scripts/build-exe.ps1 is required"
    script = BUILD_SCRIPT.read_text(encoding="utf-8-sig")
    normalized = script.replace("`", "").lower()

    assert '$erroractionpreference = "stop"' in normalized
    assert "-m PyInstaller" in script
    assert "--onefile" in script
    assert "--windowed" in script
    assert "--clean" in script
    assert "--noconfirm" in script
    assert "贷款利息自动计提工具" in script
    assert "36151" in script
    assert "20855" in script
    assert "src\\loan_interest_accrual\\web\\templates" in script
    assert "src\\loan_interest_accrual\\web\\static" in script
    assert "loan_interest_accrual.desktop_exe" not in script
    assert "src\\loan_interest_accrual\\desktop_exe.py" in script
    assert "&&" not in script


def test_build_dependencies_are_pinned_and_separate_from_runtime() -> None:
    assert BUILD_REQUIREMENTS.is_file()
    entries = [
        line.strip()
        for line in BUILD_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert entries == ["pyinstaller==6.11.1"]
    assert all(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*==[^=\s]+", entry)
        for entry in entries
    )
