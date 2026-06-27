"""Phase 0 CLI 골격 동작 검증."""

from __future__ import annotations

from typer.testing import CliRunner

from pouch import __version__
from pouch.cli import app

runner = CliRunner()


def test_version_flag_prints_version() -> None:
    # Arrange / Act
    result = runner.invoke(app, ["--version"])

    # Assert
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_bare_invocation_shows_status() -> None:
    # Arrange / Act
    result = runner.invoke(app, [])

    # Assert
    assert result.exit_code == 0
    assert "pouch" in result.stdout


def test_help_lists_app_name() -> None:
    # Arrange / Act
    result = runner.invoke(app, ["--help"])

    # Assert
    assert result.exit_code == 0
    assert "pouch" in result.stdout
