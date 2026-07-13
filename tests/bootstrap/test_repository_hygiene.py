from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_generated_python_and_environment_files_are_ignored() -> None:
    ignored_entries = {
        line.strip()
        for line in (PROJECT_ROOT / ".gitignore")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        "*.py[cod]",
        "*.egg-info/",
        "build/",
        "dist/",
    } <= ignored_entries
