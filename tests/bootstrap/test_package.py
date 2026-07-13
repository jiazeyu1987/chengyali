from dataclasses import FrozenInstanceError
from ipaddress import ip_address
from pathlib import Path

import pytest

import loan_interest_accrual
from loan_interest_accrual.settings import DEFAULT_SETTINGS
from loan_interest_accrual.version import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_package_exposes_application_version() -> None:
    assert __version__ == "0.1.0"
    assert loan_interest_accrual.__version__ == __version__
    assert Path(loan_interest_accrual.__file__).resolve().parent == (
        PROJECT_ROOT / "src" / "loan_interest_accrual"
    )


def test_default_settings_are_immutable_and_loopback_only() -> None:
    assert DEFAULT_SETTINGS.host == "127.0.0.1"
    assert ip_address(DEFAULT_SETTINGS.host).is_loopback
    assert DEFAULT_SETTINGS.port == 8000

    with pytest.raises(FrozenInstanceError):
        DEFAULT_SETTINGS.host = "0.0.0.0"
