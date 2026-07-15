from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_test_server_deploy_script_uses_committed_source_and_test_target() -> None:
    script = (
        PROJECT_ROOT / "scripts" / "deploy-test-server.ps1"
    ).read_text(encoding="utf-8")

    assert 'ServerHost = "172.30.30.58"' in script
    assert 'RemoteRoot = "/opt/loan-interest-accrual"' in script
    assert "HostPort = 18082" in script
    assert 'ServiceName = "loan-interest-accrual-test"' in script
    assert 'RemotePython = "/opt/intpp-backend/venv/bin/python"' in script
    assert "git archive --format=tar" in script
    assert "git status --porcelain --untracked-files=no" in script
    assert "pip download" in script
    assert "--platform manylinux2014_x86_64" in script
    assert "systemctl restart" in script
    assert "ExecStart=`$venv_dir/bin/python -m uvicorn" in script
    assert "http://127.0.0.1:`$host_port/health" in script


def test_test_server_deploy_script_does_not_target_other_environments() -> None:
    script = (
        PROJECT_ROOT / "scripts" / "deploy-test-server.ps1"
    ).read_text(encoding="utf-8").lower()

    forbidden = [
        "172.30.30.57",
        "172.30.30.59",
        "promote-prod",
        "promote-backup",
        "restore-data",
        "backup-now",
    ]
    for token in forbidden:
        assert token not in script
