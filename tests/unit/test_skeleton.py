"""Sanity tests for Ares project scaffolding."""

from typer.testing import CliRunner

import ares
from ares.cli.main import app
from ares.config.settings import Settings

runner = CliRunner()


def test_ares_version() -> None:
    """Verify package version is defined."""
    assert ares.__version__ == "0.1.0"


def test_settings_initialization(test_settings: Settings) -> None:
    """Verify settings loads properly."""
    assert test_settings.app_name == "Ares-Test"
    assert test_settings.sandbox_timeout_seconds == 30
    assert "postgresql://" in test_settings.postgres_dsn


def test_cli_version_command() -> None:
    """Verify CLI version command outputs valid info."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Ares" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_help() -> None:
    """Verify CLI root help displays subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fix" in result.stdout
    assert "version" in result.stdout
    assert "config" in result.stdout
