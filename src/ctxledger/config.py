from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class ConfigError(ValueError):
    """Raised when runtime configuration is invalid."""


class TransportMode(StrEnum):
    HTTP = "http"
    STDIO = "stdio"
    BOTH = "both"


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
    value = value.strip()
    return value if value != "" else default


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


def _parse_transport(name: str, default: TransportMode) -> TransportMode:
    raw = _get_env(name)
    if raw is None:
        return default
    try:
        return TransportMode(raw.lower())
    except ValueError as exc:
        expected = _format_expected_values(mode.value for mode in TransportMode)
        raise ConfigError(f"{name} must be one of {expected}") from exc


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

    @property
    def is_configured(self) -> bool:
        return bool(self.url)


@dataclass(frozen=True, slots=True)
class HttpSettings:
    enabled: bool
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
class StdioSettings:
    enabled: bool


@dataclass(frozen=True, slots=True)
class AuthSettings:
    bearer_token: str | None
    require_auth: bool

    @property
    def is_enabled(self) -> bool:
        return self.require_auth and self.bearer_token is not None


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
    transport: TransportMode
    database: DatabaseSettings
    http: HttpSettings
    stdio: StdioSettings
    auth: AuthSettings
    projection: ProjectionSettings
    logging: LoggingSettings

    def validate(self) -> None:
        if not self.database.url:
            raise ConfigError("CTXLEDGER_DATABASE_URL is required")

        if self.http.enabled:
            if not self.http.host:
                raise ConfigError(
                    "CTXLEDGER_HOST must not be empty when HTTP is enabled"
                )
            if not (1 <= self.http.port <= 65535):
                raise ConfigError("CTXLEDGER_PORT must be between 1 and 65535")
            if not self.http.path:
                raise ConfigError(
                    "CTXLEDGER_HTTP_PATH must not be empty when HTTP is enabled"
                )

        if self.auth.require_auth and not self.auth.bearer_token:
            raise ConfigError(
                "CTXLEDGER_AUTH_BEARER_TOKEN is required when CTXLEDGER_REQUIRE_AUTH is enabled"
            )

        if not self.http.enabled and not self.stdio.enabled:
            raise ConfigError("At least one transport must be enabled")

        expected_http_enabled = self.transport in (
            TransportMode.HTTP,
            TransportMode.BOTH,
        )
        expected_stdio_enabled = self.transport in (
            TransportMode.STDIO,
            TransportMode.BOTH,
        )

        if self.http.enabled != expected_http_enabled:
            raise ConfigError(
                "HTTP enablement does not match CTXLEDGER_TRANSPORT; "
                "set transport consistently with CTXLEDGER_ENABLE_HTTP"
            )

        if self.stdio.enabled != expected_stdio_enabled:
            raise ConfigError(
                "stdio enablement does not match CTXLEDGER_TRANSPORT; "
                "set transport consistently with CTXLEDGER_ENABLE_STDIO"
            )

        if self.projection.directory_name.strip() == "":
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


def load_settings() -> AppSettings:
    transport = _parse_transport("CTXLEDGER_TRANSPORT", TransportMode.HTTP)

    http_enabled = _parse_bool(
        "CTXLEDGER_ENABLE_HTTP",
        default=transport in (TransportMode.HTTP, TransportMode.BOTH),
    )
    stdio_enabled = _parse_bool(
        "CTXLEDGER_ENABLE_STDIO",
        default=transport in (TransportMode.STDIO, TransportMode.BOTH),
    )

    settings = AppSettings(
        app_name=_get_env("CTXLEDGER_APP_NAME", "ctxledger") or "ctxledger",
        app_version=_get_env("CTXLEDGER_APP_VERSION", "0.1.0") or "0.1.0",
        environment=_get_env("CTXLEDGER_ENV", "development") or "development",
        transport=transport,
        database=DatabaseSettings(
            url=_get_env("CTXLEDGER_DATABASE_URL", "") or "",
            connect_timeout_seconds=_parse_int(
                "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS", 5
            ),
            statement_timeout_ms=_parse_optional_int(
                "CTXLEDGER_DB_STATEMENT_TIMEOUT_MS"
            ),
        ),
        http=HttpSettings(
            enabled=http_enabled,
            host=_get_env("CTXLEDGER_HOST", "0.0.0.0") or "0.0.0.0",
            port=_parse_int("CTXLEDGER_PORT", 8080),
            path=_get_env("CTXLEDGER_HTTP_PATH", "/mcp") or "/mcp",
        ),
        stdio=StdioSettings(
            enabled=stdio_enabled,
        ),
        auth=AuthSettings(
            bearer_token=_get_env("CTXLEDGER_AUTH_BEARER_TOKEN"),
            require_auth=_parse_bool("CTXLEDGER_REQUIRE_AUTH", False),
        ),
        projection=ProjectionSettings(
            enabled=_parse_bool("CTXLEDGER_PROJECTION_ENABLED", True),
            directory_name=_get_env("CTXLEDGER_PROJECTION_DIRECTORY", ".agent")
            or ".agent",
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
