from __future__ import annotations

from fastapi.testclient import TestClient

from loan_interest_accrual.web.app import create_app


def test_settings_switches_to_the_remote_backed_loan_page_and_back() -> None:
    with TestClient(create_app()) as client:
        amortization_page = client.get("/")
        loan_page = client.get("/loan-interest")
        polish_css = client.get("/static/polish.css")

    assert amortization_page.status_code == 200
    assert 'id="settings-button"' in amortization_page.text
    assert 'href="/loan-interest"' in amortization_page.text
    assert "本机内置最终版" in amortization_page.text
    assert amortization_page.text.count('class="program-status-badge"') == 1
    assert 'href="/static/program_switch.css?v=20260716-2"' in amortization_page.text
    assert 'href="/static/polish.css?v=20260716-3"' in amortization_page.text

    assert loan_page.status_code == 200
    assert 'id="settings-button"' in loan_page.text
    assert 'href="/"' in loan_page.text
    assert "切换回摊销程序" in loan_page.text
    assert loan_page.text.count('class="program-status-badge"') == 1
    assert 'href="/loan-interest/template"' in loan_page.text
    assert 'src="/static/loan_interest.js?v=20260716-1"' in loan_page.text
    assert 'href="/static/program_switch.css?v=20260716-2"' in loan_page.text
    assert 'href="/static/polish.css?v=20260716-3"' in loan_page.text

    assert polish_css.status_code == 200
    assert ".amortization-table-shell" in polish_css.text
    assert "overflow: scroll" in polish_css.text
