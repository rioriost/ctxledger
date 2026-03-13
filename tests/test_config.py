from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import pytest

from ctxledger.config import (
    AppSettings,
    ConfigError,
    LogLevel,
    get_settings,
    load_settings,
)


@contextmanager
def patched_env(**updates: str | None) -> Iterator[None]:
    original: dict[str, str | None] = {}
    keys = set(updates)

    for key in keys:
        original[key] = os.environ.get(key)

    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def minimum_valid_env() -> dict[str, str]:
    return {
        "CTXLEDGER_DATABASE_URL": "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
        "CTXLEDGER_HOST": "0.0.0.0",
        "CTXLEDGER_PORT": "8080",
        "CTXLEDGER_HTTP_PATH": "/mcp",
        "CTXLEDGER_ENABLE_DEBUG_ENDPOINTS": "true",
        "CTXLEDGER_PROJECTION_ENABLED": "true",
        "CTXLEDGER_PROJECTION_DIRECTORY": ".agent",
        "CTXLEDGER_PROJECTION_WRITE_JSON": "true",
        "CTXLEDGER_PROJECTION_WRITE_MARKDOWN": "true",
        "CTXLEDGER_LOG_LEVEL": "info",
        "CTXLEDGER_LOG_STRUCTURED": "true",
        "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS": "5",
    }


@pytest.fixture
def clean_ctxledger_env() -> Iterator[None]:
    original = dict(os.environ)
    try:
        for key in list(os.environ):
            if key.startswith("CTXLEDGER_"):
                os.environ.pop(key, None)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def test_load_settings_with_minimum_valid_env(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env()):
        settings = load_settings()

    assert isinstance(settings, AppSettings)
    assert settings.database.url == minimum_valid_env()["CTXLEDGER_DATABASE_URL"]
    assert settings.http.host == "0.0.0.0"
    assert settings.http.port == 8080
    assert settings.http.path == "/mcp"
    assert settings.http.mcp_url == "http://0.0.0.0:8080/mcp"
    assert settings.logging.level == LogLevel.INFO
    assert settings.debug.enabled is True
    assert settings.projection.enabled is True
    assert settings.projection.directory_name == ".agent"


def test_get_settings_returns_validated_settings(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env()):
        settings = get_settings()

    assert isinstance(settings, AppSettings)
    assert settings.app_name == "ctxledger"
    assert settings.app_version == "0.1.0"


def test_missing_database_url_raises_config_error(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_DATABASE_URL"] = ""

    with patched_env(**env):
        with pytest.raises(ConfigError, match="CTXLEDGER_DATABASE_URL is required"):
            load_settings()


def test_invalid_boolean_value_raises_config_error(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_ENABLE_DEBUG_ENDPOINTS"] = "maybe"

    with patched_env(**env):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_ENABLE_DEBUG_ENDPOINTS must be a boolean value",
        ):
            load_settings()


def test_invalid_log_level_raises_config_error(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_LOG_LEVEL"] = "verbose"

    with patched_env(**env):
        with pytest.raises(ConfigError, match="CTXLEDGER_LOG_LEVEL must be one of"):
            load_settings()


def test_non_integer_port_raises_config_error(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_PORT"] = "not-a-number"

    with patched_env(**env):
        with pytest.raises(ConfigError, match="CTXLEDGER_PORT must be an integer"):
            load_settings()


def test_invalid_port_raises_config_error(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_PORT"] = "70000"

    with patched_env(**env):
        with pytest.raises(
            ConfigError, match="CTXLEDGER_PORT must be between 1 and 65535"
        ):
            load_settings()


def test_debug_endpoints_enabled_by_default(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env()):
        settings = load_settings()

    assert settings.debug.enabled is True


def test_invalid_debug_endpoints_value_raises_config_error(
    clean_ctxledger_env: None,
) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_ENABLE_DEBUG_ENDPOINTS"] = "maybe"

    with patched_env(**env):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_ENABLE_DEBUG_ENDPOINTS must be a boolean value",
        ):
            load_settings()


def test_debug_endpoints_can_be_disabled(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_ENABLE_DEBUG_ENDPOINTS"] = "false"

    with patched_env(**env):
        settings = load_settings()

    assert settings.debug.enabled is False


def test_projection_directory_must_not_be_empty(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env.pop("CTXLEDGER_PROJECTION_DIRECTORY", None)

    with patched_env(**env):
        os.environ["CTXLEDGER_PROJECTION_DIRECTORY"] = ""
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_PROJECTION_DIRECTORY must not be empty",
        ):
            load_settings()


def test_projection_outputs_must_include_at_least_one_format(
    clean_ctxledger_env: None,
) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_PROJECTION_WRITE_JSON"] = "false"
    env["CTXLEDGER_PROJECTION_WRITE_MARKDOWN"] = "false"

    with patched_env(**env):
        with pytest.raises(
            ConfigError,
            match="At least one projection output must be enabled when projections are enabled",
        ):
            load_settings()


def test_db_connect_timeout_must_be_positive(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS"] = "0"

    with patched_env(**env):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS must be greater than 0",
        ):
            load_settings()


def test_db_statement_timeout_must_be_positive_when_set(
    clean_ctxledger_env: None,
) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_DB_STATEMENT_TIMEOUT_MS"] = "-1"

    with patched_env(**env):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_DB_STATEMENT_TIMEOUT_MS must be greater than 0",
        ):
            load_settings()


def test_optional_statement_timeout_can_be_omitted(clean_ctxledger_env: None) -> None:
    env = minimum_valid_env()
    env["CTXLEDGER_DB_STATEMENT_TIMEOUT_MS"] = None

    with patched_env(**env):
        settings = load_settings()

    assert settings.database.statement_timeout_ms is None
