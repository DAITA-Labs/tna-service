"""Tests for app/config and app/enums/environment."""
from app.config.settings import Settings
from app.enums.environment import Environment


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    s = Settings()
    assert s.anthropic_api_key == "sk-test"
    assert s.app_env == Environment.TEST
    assert s.anthropic_model == "claude-sonnet-4-6"


def test_settings_defaults():
    """Optional knobs have sensible defaults."""
    s = Settings(anthropic_api_key="x", app_env="development")
    assert s.max_tokens == 4096
    assert s.temperature == 0.0
    assert s.retry_limit == 1
    assert s.log_level == "INFO"


def test_environment_enum_values():
    assert Environment.DEVELOPMENT.value == "development"
    assert Environment.PRODUCTION.value == "production"
    assert Environment.TEST.value == "test"
    assert Environment.STAGING.value == "staging"
