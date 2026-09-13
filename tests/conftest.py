"""Pytest fixtures for Ares."""

import pytest

from ares.config.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Return test configuration settings."""
    return Settings(
        app_name="Ares-Test",
        debug=True,
    )
