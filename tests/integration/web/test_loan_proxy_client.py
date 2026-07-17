from __future__ import annotations

from importlib import import_module

import httpx
from fastapi.testclient import TestClient


class _RecordingClient:
    def __init__(self) -> None:
        self.get_paths: list[str] = []
        self.closed = False

    async def get(self, path: str) -> httpx.Response:
        self.get_paths.append(path)
        return httpx.Response(200, json={"status": "ok"})

    async def aclose(self) -> None:
        self.closed = True


def test_loan_proxy_reuses_one_client_and_closes_it_on_shutdown(monkeypatch) -> None:
    app_module = import_module("loan_interest_accrual.web.app")
    remote_client = _RecordingClient()
    factory_calls = 0

    def client_factory():
        nonlocal factory_calls
        factory_calls += 1
        return remote_client

    monkeypatch.setattr(app_module, "create_loan_proxy_client", client_factory)
    application = app_module.create_app()

    with TestClient(application) as client:
        first = client.get("/loan-interest/health")
        second = client.get("/loan-interest/health")

        assert first.status_code == 200
        assert second.status_code == 200
        assert application.state.loan_proxy_client is remote_client
        assert remote_client.closed is False

    assert factory_calls == 1
    assert remote_client.get_paths == ["/health", "/health"]
    assert remote_client.closed is True
