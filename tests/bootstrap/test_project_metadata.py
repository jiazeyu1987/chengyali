from pathlib import Path
import re
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"

EXPECTED_RUNTIME_DEPENDENCIES = {
    "fastapi": "0.115.5",
    "httpx": "0.28.1",
    "jinja2": "3.1.6",
    "openpyxl": "3.1.5",
    "python-multipart": "0.0.22",
    "uvicorn": "0.32.0",
}
EXPECTED_TEST_DEPENDENCIES = {
    "playwright": "1.58.0",
    "pytest": "8.4.2",
}
FORBIDDEN_DEPENDENCY_PREFIXES = {
    "alembic",
    "asyncpg",
    "auth0",
    "authlib",
    "azure",
    "boto3",
    "botocore",
    "databases",
    "datadog",
    "django",
    "firebase",
    "google-cloud",
    "motor",
    "mysqlclient",
    "newrelic",
    "oauthlib",
    "openai",
    "opentelemetry",
    "oracledb",
    "passlib",
    "prometheus-client",
    "psycopg",
    "pymongo",
    "pymysql",
    "pyjwt",
    "python-jose",
    "redis",
    "requests-oauthlib",
    "sentry-sdk",
    "sqlalchemy",
    "stripe",
    "supabase",
    "twilio",
}
PINNED_DEPENDENCY_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)$"
)


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_pinned_dependencies(entries: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for entry in entries:
        match = PINNED_DEPENDENCY_PATTERN.fullmatch(entry.strip())
        assert match is not None, f"dependency must use an exact == pin: {entry}"
        name = _normalize_name(match.group("name"))
        assert name not in parsed, f"duplicate dependency declaration: {name}"
        parsed[name] = match.group("version")
    return parsed


def _read_requirements() -> list[str]:
    return [
        line.strip()
        for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_pyproject_declares_exact_python_and_src_layout() -> None:
    configuration = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert configuration["project"]["requires-python"] == "==3.12.*"
    assert configuration["project"]["version"] == "0.1.0"
    assert configuration["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert configuration["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert configuration["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert configuration["tool"]["pytest"]["ini_options"]["pythonpath"] == ["src"]


def test_all_approved_direct_dependencies_are_exactly_pinned() -> None:
    configuration = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    runtime_dependencies = _parse_pinned_dependencies(
        configuration["project"]["dependencies"]
    )
    test_dependencies = _parse_pinned_dependencies(
        configuration["project"]["optional-dependencies"]["test"]
    )
    requirements = _parse_pinned_dependencies(_read_requirements())

    assert runtime_dependencies == EXPECTED_RUNTIME_DEPENDENCIES
    assert test_dependencies == EXPECTED_TEST_DEPENDENCIES
    assert requirements == EXPECTED_RUNTIME_DEPENDENCIES | EXPECTED_TEST_DEPENDENCIES


def test_dependency_metadata_rejects_forbidden_dependency_classes() -> None:
    configuration = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    dependency_groups = [
        configuration["build-system"]["requires"],
        configuration["project"]["dependencies"],
        *configuration["project"]["optional-dependencies"].values(),
        _read_requirements(),
    ]
    declared = {
        name
        for dependency_group in dependency_groups
        for name in _parse_pinned_dependencies(dependency_group)
    }

    forbidden = {
        name
        for name in declared
        if any(
            name == prefix or name.startswith(f"{prefix}-")
            for prefix in FORBIDDEN_DEPENDENCY_PREFIXES
        )
    }
    assert forbidden == set()
