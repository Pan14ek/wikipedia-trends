"""M01 smoke tests for package import and CLI startup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import wiki_trends

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_package_imports() -> None:
    assert wiki_trends.__version__ == "0.1.0"


def test_cli_help_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/analyze.py", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
