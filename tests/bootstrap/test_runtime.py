import platform
import sys


def test_bootstrap_requires_windows_and_exact_python_3_12() -> None:
    assert platform.system() == "Windows"
    assert sys.version_info[:2] == (3, 12)
