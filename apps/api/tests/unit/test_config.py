"""Unit tests for configuration management and environment validation."""

import pytest
from pydantic import ValidationError

from logpilot_api.core.config import Settings


def test_default_settings() -> None:
    """Verify default settings values and properties."""
    settings = Settings()
    assert settings.app_name == "LogPilot"
    assert settings.app_env in {"development", "testing", "staging", "production"}
    assert settings.api_port == 8000
    assert not settings.is_production


def test_invalid_app_env() -> None:
    """Verify invalid app_env raises validation error."""
    with pytest.raises(ValidationError):
        Settings(app_env="invalid_environment")


def test_invalid_log_level() -> None:
    """Verify invalid log_level raises validation error."""
    with pytest.raises(ValidationError):
        Settings(log_level="VERBOSE")


def test_invalid_api_port() -> None:
    """Verify out-of-range port raises validation error."""
    with pytest.raises(ValidationError):
        Settings(api_port=99999)


def test_testing_mode_flag() -> None:
    """Verify is_testing property."""
    settings = Settings(app_env="testing")
    assert settings.is_testing
    assert not settings.is_production
