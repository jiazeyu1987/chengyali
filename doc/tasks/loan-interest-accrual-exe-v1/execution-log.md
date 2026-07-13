# Execution Log

BDD: Standalone EXE launch -> Given the finance user has only the packaged exe, When they double-click it, Then it starts the local service on 127.0.0.1:8000 and opens the browser without requiring Python or project scripts.

BDD: Standalone EXE exit -> Given the standalone exe is running, When the user clicks the page exit button, Then the embedded server shuts down directly without invoking PowerShell stop scripts.

RED: .venv\Scripts\python.exe -m pytest tests\integration\web\test_embedded_desktop_actions.py tests\integration\windows\test_exe_packaging.py -> expected FAIL before implementation because DesktopActions has no embedded exit handler and EXE packaging files do not exist.

RED: .venv\Scripts\python.exe -m pytest tests\integration\web\test_embedded_desktop_actions.py tests\integration\windows\test_exe_packaging.py -> FAIL, DesktopActions.__init__ rejects exit_handler and desktop_exe.py, scripts/build-exe.ps1, requirements-build.txt are missing.

Implementation: Added embedded shutdown support, standalone desktop_exe entrypoint, pinned PyInstaller build requirement, onefile windowed build script, and package-data declarations for web assets.

Investigation: Source entrypoint starts and exits cleanly through the embedded exit route, while first PyInstaller EXE smoke stayed alive without opening the health endpoint. Added startup logging under the current user's local app data to fail fast with inspectable evidence instead of a silent windowed process.

Fix: Windowed PyInstaller runtime has no console stream, so Uvicorn's default logging formatter fails when it checks stream.isatty. Set Uvicorn log_config=None for the standalone EXE and covered it in packaging tests.

GREEN: .venv\Scripts\python.exe -m pytest tests\integration\web\test_embedded_desktop_actions.py tests\integration\windows\test_exe_packaging.py tests\integration\web\test_desktop_actions.py -> PASS, 18 passed.

GREEN: scripts\build-exe.ps1 -> PASS, generated `dist/贷款利息自动计提工具.exe` as a single-file PyInstaller windowed executable.

GREEN: isolated EXE runtime verification -> PASS, copied the executable to a temporary directory and verified health, template download, Excel calculation, Excel export, zero formulas in exported workbook, embedded exit, and port release.

Cleanup preview command -> PASS, delete candidates are limited to `.artifacts/loan-interest-accrual-exe-v1/pyinstaller-build` and `.artifacts/loan-interest-accrual-exe-v1/pyinstaller-spec`.

Cleanup apply command -> PASS, removed PyInstaller build/spec intermediate directories and preserved the final EXE plus release evidence.

Final status update -> completed.
