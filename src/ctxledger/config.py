from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class ConfigError(ValueError):
    """Raised when runtime configuration is invalid."""


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


_TRUE_VALUES: Final[set[str]] = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES: Final[set[str]] = {"0", "false", "f", "no", "n", "off"}


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _parse_bool(name: str, default: bool) -> bool:
    raw = _get_env(name)
    if raw is None:
        return default

    lowered = raw.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False

    raise ConfigError(
        f"{name} must be a boolean value "
        f"({_format_expected_values(sorted(_TRUE_VALUES | _FALSE_VALUES))})"
    )


def _parse_int(name: str, default: int) -> int:
    raw = _get_env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _parse_optional_int(name: str) -> int | None:
    raw = _get_env(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _parse_log_level(name: str, default: LogLevel) -> LogLevel:
    raw = _get_env(name)
    if raw is None:
        return default
    try:
        return LogLevel(raw.lower())
    except ValueError as exc:
        expected = _format_expected_values(level.value for level in LogLevel)
        raise ConfigError(f"{name} must be one of {expected}") from exc


def _format_expected_values(
    values: list[str] | set[str] | tuple[str, ...] | object,
) -> str:
    if isinstance(values, (list, set, tuple)):
        return ", ".join(f"'{value}'" for value in values)
    return str(values)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: str
    connect_timeout_seconds: int
    statement_timeout_ms: int | None
    schema_name: str

    @property
    def is_configured(self) -> bool:
        return bool(self.url)


@dataclass(frozen=True, slots=True)
class HttpSettings:
    host: str
    port: int
    path: str

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def mcp_url(self) -> str:
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        return f"{self.base_url}{path}"


@dataclass(frozen=True, slots=True)
class DebugSettings:
    enabled: bool


@dataclass(frozen=True, slots=True)
class ProjectionSettings:
    enabled: bool
    directory_name: str
    write_markdown: bool
    write_json: bool


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    level: LogLevel
    structured: bool


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_name: str
    app_version: str
    environment: str
    database: DatabaseSettings
    http: HttpSettings
    debug: DebugSettings
    projection: ProjectionSettings
    logging: LoggingSettings

    def validate(self) -> None:
        if not self.database.url:
            raise ConfigError("CTXLEDGER_DATABASE_URL is required")

        if not self.http.host:
            raise ConfigError("CTXLEDGER_HOST must not be empty")
        if not (1 <= self.http.port <= 65535):
            raise ConfigError("CTXLEDGER_PORT must be between 1 and 65535")
        if not self.http.path:
            raise ConfigError("CTXLEDGER_HTTP_PATH must not be empty")

        if self.projection.directory_name == "":
            raise ConfigError("CTXLEDGER_PROJECTION_DIRECTORY must not be empty")

        if not self.projection.write_json and not self.projection.write_markdown:
            raise ConfigError(
                "At least one projection output must be enabled when projections are enabled"
            )

        if self.database.connect_timeout_seconds <= 0:
            raise ConfigError(
                "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS must be greater than 0"
            )

        if (
            self.database.statement_timeout_ms is not None
            and self.database.statement_timeout_ms <= 0
        ):
            raise ConfigError(
                "CTXLEDGER_DB_STATEMENT_TIMEOUT_MS must be greater than 0"
            )

        if not self.database.schema_name:
            raise ConfigError("CTXLEDGER_DB_SCHEMA_NAME must not be empty")


def load_settings() -> AppSettings:
    settings = AppSettings(
        app_name=_get_env("CTXLEDGER_APP_NAME", "ctxledger") or "ctxledger",
        app_version=_get_env("CTXLEDGER_APP_VERSION", "0.1.0") or "0.1.0",
        environment=_get_env("CTXLEDGER_ENV", "development") or "development",
        database=DatabaseSettings(
            url=_get_env("CTXLEDGER_DATABASE_URL", "") or "",
            connect_timeout_seconds=_parse_int(
                "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS", 5
            ),
            statement_timeout_ms=_parse_optional_int(
                "CTXLEDGER_DB_STATEMENT_TIMEOUT_MS"
            ),
            schema_name=_get_env("CTXLEDGER_DB_SCHEMA_NAME", "public") or "public",
        ),
        http=HttpSettings(
            host=_get_env("CTXLEDGER_HOST", "0.0.0.0") or "0.0.0.0",
            port=_parse_int("CTXLEDGER_PORT", 8080),
            path=_get_env("CTXLEDGER_HTTP_PATH", "/mcp") or "/mcp",
        ),
        debug=DebugSettings(
            enabled=_parse_bool("CTXLEDGER_ENABLE_DEBUG_ENDPOINTS", True),
        ),
        projection=ProjectionSettings(
            enabled=_parse_bool("CTXLEDGER_PROJECTION_ENABLED", True),
            directory_name=_get_env("CTXLEDGER_PROJECTION_DIRECTORY", ".agent"),
            write_markdown=_parse_bool("CTXLEDGER_PROJECTION_WRITE_MARKDOWN", True),
            write_json=_parse_bool("CTXLEDGER_PROJECTION_WRITE_JSON", True),
        ),
        logging=LoggingSettings(
            level=_parse_log_level("CTXLEDGER_LOG_LEVEL", LogLevel.INFO),
            structured=_parse_bool("CTXLEDGER_LOG_STRUCTURED", True),
        ),
    )

    settings.validate()
    return settings


def get_settings() -> AppSettings:
    return load_settings()
