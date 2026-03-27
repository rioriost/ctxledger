from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import pytest

from ctxledger.config import (
    AppSettings,
    ConfigError,
    DatabaseSettings,
    DebugSettings,
    EmbeddingProvider,
    EmbeddingSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    _format_expected_values,
    _get_env,
    _parse_bool,
    _parse_embedding_provider,
    _parse_int,
    _parse_log_level,
    _parse_optional_int,
    _validate_optional_url,
    get_settings,
    load_settings,
)
from ctxledger.version import get_app_version


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


def minimum_valid_env(**overrides: str | None) -> dict[str, str | None]:
    env: dict[str, str | None] = {
        "CTXLEDGER_DATABASE_URL": "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
        "CTXLEDGER_HOST": "0.0.0.0",
        "CTXLEDGER_PORT": "8080",
        "CTXLEDGER_HTTP_PATH": "/mcp",
        "CTXLEDGER_ENABLE_DEBUG_ENDPOINTS": "true",
        "CTXLEDGER_LOG_LEVEL": "info",
        "CTXLEDGER_LOG_STRUCTURED": "true",
        "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS": "5",
        "CTXLEDGER_EMBEDDING_ENABLED": "false",
        "CTXLEDGER_EMBEDDING_PROVIDER": "local_stub",
        "CTXLEDGER_EMBEDDING_MODEL": "text-embedding-3-small",
    }
    env.update(overrides)
    return env


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
    assert settings.database.age_enabled is False
    assert settings.database.age_graph_name == "ctxledger_memory"
    assert settings.embedding.enabled is False
    assert settings.embedding.provider is EmbeddingProvider.LOCAL_STUB
    assert settings.embedding.model == "text-embedding-3-small"
    assert settings.embedding.api_key is None
    assert settings.embedding.base_url is None
    assert settings.embedding.dimensions == 16


def test_get_settings_returns_validated_settings(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env()):
        settings = get_settings()

    assert isinstance(settings, AppSettings)
    assert settings.app_name == "ctxledger"
    assert settings.app_version == get_app_version()


def test_missing_database_url_raises_config_error(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_DATABASE_URL="")):
        with pytest.raises(ConfigError, match="CTXLEDGER_DATABASE_URL is required"):
            load_settings()


def test_invalid_boolean_value_raises_config_error(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_ENABLE_DEBUG_ENDPOINTS="maybe")):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_ENABLE_DEBUG_ENDPOINTS must be a boolean value",
        ):
            load_settings()


def test_invalid_log_level_raises_config_error(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_LOG_LEVEL="verbose")):
        with pytest.raises(ConfigError, match="CTXLEDGER_LOG_LEVEL must be one of"):
            load_settings()


def test_non_integer_port_raises_config_error(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_PORT="not-a-number")):
        with pytest.raises(ConfigError, match="CTXLEDGER_PORT must be an integer"):
            load_settings()


def test_invalid_port_raises_config_error(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_PORT="70000")):
        with pytest.raises(ConfigError, match="CTXLEDGER_PORT must be between 1 and 65535"):
            load_settings()


def test_debug_endpoints_enabled_by_default(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env()):
        settings = load_settings()

    assert settings.debug.enabled is True


def test_invalid_debug_endpoints_value_raises_config_error(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_ENABLE_DEBUG_ENDPOINTS="maybe")):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_ENABLE_DEBUG_ENDPOINTS must be a boolean value",
        ):
            load_settings()


def test_debug_endpoints_can_be_disabled(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_ENABLE_DEBUG_ENDPOINTS="false")):
        settings = load_settings()

    assert settings.debug.enabled is False


def test_db_connect_timeout_must_be_positive(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS="0")):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS must be greater than 0",
        ):
            load_settings()


def test_db_statement_timeout_must_be_positive_when_set(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_DB_STATEMENT_TIMEOUT_MS="-1")):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_DB_STATEMENT_TIMEOUT_MS must be greater than 0",
        ):
            load_settings()


def test_optional_statement_timeout_can_be_omitted(clean_ctxledger_env: None) -> None:
    with patched_env(**minimum_valid_env(CTXLEDGER_DB_STATEMENT_TIMEOUT_MS=None)):
        settings = load_settings()

    assert settings.database.statement_timeout_ms is None


def test_parse_embedding_provider_returns_default_when_missing(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(CTXLEDGER_EMBEDDING_PROVIDER=None):
        assert (
            _parse_embedding_provider(
                "CTXLEDGER_EMBEDDING_PROVIDER",
                EmbeddingProvider.DISABLED,
            )
            is EmbeddingProvider.DISABLED
        )


def test_parse_embedding_provider_accepts_supported_value(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(CTXLEDGER_EMBEDDING_PROVIDER="voyageai"):
        assert (
            _parse_embedding_provider(
                "CTXLEDGER_EMBEDDING_PROVIDER",
                EmbeddingProvider.DISABLED,
            )
            is EmbeddingProvider.VOYAGEAI
        )


def test_parse_embedding_provider_rejects_unknown_value(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(CTXLEDGER_EMBEDDING_PROVIDER="weird"):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_EMBEDDING_PROVIDER must be one of",
        ):
            _parse_embedding_provider(
                "CTXLEDGER_EMBEDDING_PROVIDER",
                EmbeddingProvider.DISABLED,
            )


def test_validate_optional_url_accepts_absolute_url() -> None:
    _validate_optional_url(
        name="CTXLEDGER_EMBEDDING_BASE_URL",
        value="https://api.example.com/v1",
    )


def test_validate_optional_url_rejects_invalid_url() -> None:
    with pytest.raises(
        ConfigError,
        match="CTXLEDGER_EMBEDDING_BASE_URL must be a valid absolute URL",
    ):
        _validate_optional_url(
            name="CTXLEDGER_EMBEDDING_BASE_URL",
            value="not-a-url",
        )


def test_get_env_returns_default_for_missing_value(clean_ctxledger_env: None) -> None:
    with patched_env(CTXLEDGER_SAMPLE=None):
        assert _get_env("CTXLEDGER_SAMPLE", "fallback") == "fallback"


def test_get_env_strips_existing_value(clean_ctxledger_env: None) -> None:
    with patched_env(CTXLEDGER_SAMPLE="  value  "):
        assert _get_env("CTXLEDGER_SAMPLE") == "value"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("TRUE", True),
        (" yes ", True),
        ("0", False),
        ("Off", False),
    ],
)
def test_parse_bool_accepts_supported_values(
    clean_ctxledger_env: None,
    raw_value: str,
    expected: bool,
) -> None:
    with patched_env(CTXLEDGER_SAMPLE_BOOL=raw_value):
        assert _parse_bool("CTXLEDGER_SAMPLE_BOOL", default=not expected) is expected


def test_parse_bool_returns_default_when_missing(clean_ctxledger_env: None) -> None:
    with patched_env(CTXLEDGER_SAMPLE_BOOL=None):
        assert _parse_bool("CTXLEDGER_SAMPLE_BOOL", default=False) is False


def test_parse_int_returns_default_when_missing(clean_ctxledger_env: None) -> None:
    with patched_env(CTXLEDGER_SAMPLE_INT=None):
        assert _parse_int("CTXLEDGER_SAMPLE_INT", default=17) == 17


def test_parse_optional_int_parses_value(clean_ctxledger_env: None) -> None:
    with patched_env(CTXLEDGER_SAMPLE_INT="42"):
        assert _parse_optional_int("CTXLEDGER_SAMPLE_INT") == 42


def test_parse_optional_int_rejects_invalid_value(clean_ctxledger_env: None) -> None:
    with patched_env(CTXLEDGER_SAMPLE_INT="abc"):
        with pytest.raises(
            ConfigError,
            match="CTXLEDGER_SAMPLE_INT must be an integer",
        ):
            _parse_optional_int("CTXLEDGER_SAMPLE_INT")


def test_parse_log_level_returns_default_when_missing(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(CTXLEDGER_LOG_LEVEL=None):
        assert _parse_log_level("CTXLEDGER_LOG_LEVEL", LogLevel.WARNING) is LogLevel.WARNING


def test_format_expected_values_supports_non_collection_object() -> None:
    assert _format_expected_values("value") == "value"


def test_database_settings_is_configured_reflects_url_presence() -> None:
    configured = DatabaseSettings(
        url="postgresql://example/db",
        connect_timeout_seconds=5,
        statement_timeout_ms=None,
        schema_name="public",
        pool_min_size=1,
        pool_max_size=10,
        pool_timeout_seconds=5,
        age_enabled=False,
        age_graph_name="ctxledger_memory",
    )
    missing = DatabaseSettings(
        url="",
        connect_timeout_seconds=5,
        statement_timeout_ms=None,
        schema_name="public",
        pool_min_size=1,
        pool_max_size=10,
        pool_timeout_seconds=5,
        age_enabled=False,
        age_graph_name="ctxledger_memory",
    )

    assert configured.is_configured is True
    assert missing.is_configured is False


def test_http_settings_base_url_and_mcp_url_normalize_path() -> None:
    settings = HttpSettings(host="127.0.0.1", port=9000, path="mcp")

    assert settings.base_url == "http://127.0.0.1:9000"
    assert settings.mcp_url == "http://127.0.0.1:9000/mcp"


def test_load_settings_reads_age_database_settings(clean_ctxledger_env: None) -> None:
    with patched_env(
        **minimum_valid_env(
            CTXLEDGER_DB_AGE_ENABLED="true",
            CTXLEDGER_DB_AGE_GRAPH_NAME="ctxledger_test_graph",
        )
    ):
        settings = load_settings()

    assert settings.database.age_enabled is True
    assert settings.database.age_graph_name == "ctxledger_test_graph"


def test_app_settings_validate_rejects_empty_host() -> None:
    settings = AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url="postgresql://ctxledger:test@localhost:5432/ctxledger",
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(host="", port=8080, path="/mcp"),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(level=LogLevel.INFO, structured=True),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            model="text-embedding-3-small",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
        ),
    )

    with pytest.raises(ConfigError, match="CTXLEDGER_HOST must not be empty"):
        settings.validate()


def test_app_settings_validate_rejects_empty_http_path() -> None:
    settings = AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url="postgresql://ctxledger:test@localhost:5432/ctxledger",
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(host="127.0.0.1", port=8080, path=""),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(level=LogLevel.INFO, structured=True),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            model="text-embedding-3-small",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
        ),
    )

    with pytest.raises(ConfigError, match="CTXLEDGER_HTTP_PATH must not be empty"):
        settings.validate()


def test_app_settings_validate_requires_embedding_model_when_enabled() -> None:
    settings = AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url="postgresql://ctxledger:test@localhost:5432/ctxledger",
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(host="127.0.0.1", port=8080, path="/mcp"),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(level=LogLevel.INFO, structured=True),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=True,
        ),
    )

    with pytest.raises(
        ConfigError,
        match="OPENAI_API_KEY is required for the selected embedding provider",
    ):
        settings.validate()


def test_app_settings_validate_requires_api_key_for_external_embedding_provider() -> None:
    settings = AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url="postgresql://ctxledger:test@localhost:5432/ctxledger",
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(host="127.0.0.1", port=8080, path="/mcp"),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(level=LogLevel.INFO, structured=True),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.OPENAI,
            model="",
            api_key="secret",
            base_url=None,
            dimensions=None,
            enabled=True,
        ),
    )

    with pytest.raises(
        ConfigError,
        match="CTXLEDGER_EMBEDDING_MODEL must not be empty",
    ):
        settings.validate()


def test_app_settings_validate_requires_base_url_for_custom_http_embedding_provider() -> None:
    settings = AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url="postgresql://ctxledger:test@localhost:5432/ctxledger",
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(host="127.0.0.1", port=8080, path="/mcp"),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(level=LogLevel.INFO, structured=True),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.CUSTOM_HTTP,
            model="text-embedding-3-small",
            api_key="secret",
            base_url=None,
            dimensions=None,
            enabled=True,
        ),
    )

    with pytest.raises(
        ConfigError,
        match="CTXLEDGER_EMBEDDING_BASE_URL is required when CTXLEDGER_EMBEDDING_PROVIDER=custom_http",
    ):
        settings.validate()


def test_app_settings_validate_rejects_non_positive_embedding_dimensions() -> None:
    settings = AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url="postgresql://ctxledger:test@localhost:5432/ctxledger",
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(host="127.0.0.1", port=8080, path="/mcp"),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(level=LogLevel.INFO, structured=True),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.LOCAL_STUB,
            model="text-embedding-3-small",
            api_key=None,
            base_url=None,
            dimensions=0,
            enabled=True,
        ),
    )

    with pytest.raises(
        ConfigError,
        match="CTXLEDGER_EMBEDDING_DIMENSIONS must be greater than 0 when provided",
    ):
        settings.validate()


def test_load_settings_uses_defaults_for_optional_values(
    clean_ctxledger_env: None,
) -> None:
    with patched_env(CTXLEDGER_DATABASE_URL="postgresql://example/db"):
        settings = load_settings()

    assert settings.app_name == "ctxledger"
    assert settings.app_version == get_app_version()
    assert settings.environment == "development"
    assert settings.http.host == "0.0.0.0"
    assert settings.http.port == 8080
    assert settings.http.path == "/mcp"
    assert settings.debug.enabled is True
    assert settings.logging.level is LogLevel.INFO
    assert settings.database.pool_min_size == 1
    assert settings.database.pool_max_size == 10
    assert settings.database.pool_timeout_seconds == 5
    assert settings.database.age_enabled is False
    assert settings.database.age_graph_name == "ctxledger_memory"
    assert settings.logging.structured is True
    assert settings.database.connect_timeout_seconds == 5
    assert settings.database.statement_timeout_ms is None
    assert settings.embedding.enabled is False
    assert settings.embedding.provider is EmbeddingProvider.LOCAL_STUB
    assert settings.embedding.model == "text-embedding-3-small"
    assert settings.embedding.api_key is None
    assert settings.embedding.base_url is None
    assert settings.embedding.dimensions == 16
