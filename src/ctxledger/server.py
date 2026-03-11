from __future__ import annotations

import logging
import signal
import sys
from dataclasses import dataclass
from types import FrameType
from typing import Any, Protocol

from .config import AppSettings, LogLevel, TransportMode, get_settings

logger = logging.getLogger(__name__)


class SettingsProtocol(Protocol):
    database_url: str | None
    host: str
    port: int
    enable_http: bool
    enable_stdio: bool
    auth_bearer_token: str | None
    log_level: str


class DatabaseHealthChecker(Protocol):
    def ping(self) -> None: ...
    def schema_ready(self) -> bool: ...


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


@dataclass(slots=True)
class HealthStatus:
    ok: bool
    status: str
    details: dict[str, Any]


@dataclass(slots=True)
class ReadinessStatus:
    ready: bool
    status: str
    details: dict[str, Any]


class ServerBootstrapError(RuntimeError):
    pass


class DefaultDatabaseHealthChecker:
    """
    Lightweight placeholder health checker.

    This implementation intentionally avoids a hard dependency on a specific
    PostgreSQL driver in the initial runtime bootstrap. It validates that a DB
    URL is configured and treats schema readiness as a deploy-time guarantee.

    A future implementation should:
    - open a real DB connection
    - run a lightweight ping query
    - verify required tables/indexes/schema version
    """

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    def ping(self) -> None:
        if not self._database_url:
            raise ServerBootstrapError("database_url is not configured")

    def schema_ready(self) -> bool:
        return bool(self._database_url)


class HttpRuntimeAdapter:
    """
    Placeholder HTTP runtime adapter.

    This class establishes the lifecycle and logging contract for the future
    MCP Streamable HTTP implementation.
    """

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._started = False

    def start(self) -> None:
        logger.info(
            "HTTP runtime adapter starting",
            extra={
                "transport": "http",
                "host": self.settings.http.host,
                "port": self.settings.http.port,
                "path": self.settings.http.path,
                "mcp_url": self.settings.http.mcp_url,
            },
        )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        logger.info(
            "HTTP runtime adapter stopping",
            extra={
                "transport": "http",
                "host": self.settings.http.host,
                "port": self.settings.http.port,
            },
        )
        self._started = False


class StdioRuntimeAdapter:
    """
    Placeholder stdio runtime adapter.

    This class establishes the lifecycle and logging contract for the future
    MCP stdio implementation.
    """

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._started = False

    def start(self) -> None:
        logger.info(
            "stdio runtime adapter starting",
            extra={
                "transport": "stdio",
            },
        )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        logger.info(
            "stdio runtime adapter stopping",
            extra={
                "transport": "stdio",
            },
        )
        self._started = False


class CompositeRuntimeAdapter:
    """
    Aggregates multiple runtime adapters behind a single lifecycle boundary.
    """

    def __init__(self, runtimes: list[ServerRuntime]) -> None:
        self._runtimes = runtimes
        self._started = False

    def start(self) -> None:
        started: list[ServerRuntime] = []
        try:
            for runtime in self._runtimes:
                runtime.start()
                started.append(runtime)
            self._started = True
        except Exception:
            for runtime in reversed(started):
                try:
                    runtime.stop()
                except Exception:
                    logger.exception("Failed to stop partially started runtime")
            raise

    def stop(self) -> None:
        if not self._started:
            return

        for runtime in reversed(self._runtimes):
            try:
                runtime.stop()
            except Exception:
                logger.exception("Runtime shutdown failed")

        self._started = False


class CtxLedgerServer:
    """
    Application bootstrap and operational status surface for ctxledger.

    Responsibilities:
    - validate startup configuration
    - initialize runtime dependencies
    - expose liveness and readiness checks
    - provide a lifecycle boundary for HTTP/stdio adapters
    """

    def __init__(
        self,
        settings: AppSettings,
        db_health_checker: DatabaseHealthChecker | None = None,
        runtime: ServerRuntime | None = None,
    ) -> None:
        self.settings = settings
        self.db_health_checker = db_health_checker or DefaultDatabaseHealthChecker(
            settings.database.url
        )
        self.runtime = runtime
        self._started = False

    def validate_configuration(self) -> None:
        self.settings.validate()

    def configure_logging(self) -> None:
        level_name = self.settings.logging.level.value.upper()
        level = getattr(logging, level_name, logging.INFO)

        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            force=True,
        )

    def startup(self) -> None:
        self.configure_logging()
        logger.info(
            "ctxledger startup initiated",
            extra={
                "app_name": self.settings.app_name,
                "app_version": self.settings.app_version,
                "environment": self.settings.environment,
            },
        )

        self.validate_configuration()
        self.db_health_checker.ping()

        if not self.db_health_checker.schema_ready():
            raise ServerBootstrapError("database schema is not ready")

        if self.runtime is not None:
            self.runtime.start()

        self._started = True
        logger.info(
            "ctxledger startup complete",
            extra={
                "http_enabled": self.settings.http.enabled,
                "stdio_enabled": self.settings.stdio.enabled,
                "host": self.settings.http.host,
                "port": self.settings.http.port,
                "mcp_url": self.settings.http.mcp_url,
            },
        )

    def shutdown(self) -> None:
        logger.info("ctxledger shutdown initiated")

        if self.runtime is not None and self._started:
            self.runtime.stop()

        self._started = False
        logger.info("ctxledger shutdown complete")

    def health(self) -> HealthStatus:
        return HealthStatus(
            ok=True,
            status="ok",
            details={
                "service": self.settings.app_name,
                "version": self.settings.app_version,
                "started": self._started,
            },
        )

    def readiness(self) -> ReadinessStatus:
        details: dict[str, Any] = {
            "service": self.settings.app_name,
            "version": self.settings.app_version,
            "started": self._started,
            "database_configured": bool(self.settings.database.url),
            "http_enabled": self.settings.http.enabled,
            "stdio_enabled": self.settings.stdio.enabled,
        }

        if not self._started:
            return ReadinessStatus(
                ready=False,
                status="not_started",
                details=details,
            )

        try:
            self.db_health_checker.ping()
            details["database_reachable"] = True
        except Exception as exc:
            details["database_reachable"] = False
            details["error"] = str(exc)
            return ReadinessStatus(
                ready=False,
                status="database_unavailable",
                details=details,
            )

        try:
            schema_ready = self.db_health_checker.schema_ready()
            details["schema_ready"] = schema_ready
        except Exception as exc:
            details["schema_ready"] = False
            details["error"] = str(exc)
            return ReadinessStatus(
                ready=False,
                status="schema_check_failed",
                details=details,
            )

        if not details["schema_ready"]:
            return ReadinessStatus(
                ready=False,
                status="schema_not_ready",
                details=details,
            )

        return ReadinessStatus(
            ready=True,
            status="ready",
            details=details,
        )


def create_runtime(settings: AppSettings) -> ServerRuntime | None:
    runtimes: list[ServerRuntime] = []

    if settings.http.enabled:
        runtimes.append(HttpRuntimeAdapter(settings))

    if settings.stdio.enabled:
        runtimes.append(StdioRuntimeAdapter(settings))

    if not runtimes:
        return None

    if len(runtimes) == 1:
        return runtimes[0]

    return CompositeRuntimeAdapter(runtimes)


def create_server(
    settings: AppSettings,
    db_health_checker: DatabaseHealthChecker | None = None,
    runtime: ServerRuntime | None = None,
) -> CtxLedgerServer:
    return CtxLedgerServer(
        settings=settings,
        db_health_checker=db_health_checker,
        runtime=runtime if runtime is not None else create_runtime(settings),
    )


def _apply_overrides(
    settings: AppSettings,
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> AppSettings:
    if transport is None and host is None and port is None:
        return settings

    transport_mode = settings.transport
    http_enabled = settings.http.enabled
    stdio_enabled = settings.stdio.enabled

    if transport is not None:
        transport_mode = TransportMode(transport)
        http_enabled = transport_mode in (TransportMode.HTTP, TransportMode.BOTH)
        stdio_enabled = transport_mode in (TransportMode.STDIO, TransportMode.BOTH)

    http_settings = type(settings.http)(
        enabled=http_enabled,
        host=host if host is not None else settings.http.host,
        port=port if port is not None else settings.http.port,
        path=settings.http.path,
    )

    stdio_settings = type(settings.stdio)(
        enabled=stdio_enabled,
    )

    overridden = type(settings)(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        transport=transport_mode,
        database=settings.database,
        http=http_settings,
        stdio=stdio_settings,
        auth=settings.auth,
        projection=settings.projection,
        logging=settings.logging,
    )
    overridden.validate()
    return overridden


def _install_signal_handlers(server: CtxLedgerServer) -> None:
    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info(
            "Received shutdown signal",
            extra={"signal": signum},
        )
        server.shutdown()
        raise SystemExit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except ValueError:
            # Signal registration can fail outside the main thread.
            logger.debug("Signal handler registration skipped", extra={"signal": sig})


def _print_runtime_summary(server: CtxLedgerServer) -> None:
    readiness = server.readiness()
    health = server.health()

    print(
        f"{server.settings.app_name} {server.settings.app_version} started",
        file=sys.stderr,
    )
    print(f"health={health.status}", file=sys.stderr)
    print(f"readiness={readiness.status}", file=sys.stderr)

    if server.settings.http.enabled:
        print(f"mcp_endpoint={server.settings.http.mcp_url}", file=sys.stderr)
    if server.settings.stdio.enabled:
        print("stdio_transport=enabled", file=sys.stderr)


def run_server(
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> int:
    """
    Runnable server entrypoint used by the CLI.

    In v0.1.0 this starts bootstrap/runtime adapters and reports health/readiness.
    The actual MCP transport implementations can later replace the placeholder
    adapters without changing the entrypoint contract.
    """
    try:
        settings = get_settings()
        settings = _apply_overrides(
            settings,
            transport=transport,
            host=host,
            port=port,
        )
        server = create_server(settings)
        _install_signal_handlers(server)
        server.startup()
        _print_runtime_summary(server)
        return 0
    except ServerBootstrapError as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled server error: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "CompositeRuntimeAdapter",
    "CtxLedgerServer",
    "DatabaseHealthChecker",
    "DefaultDatabaseHealthChecker",
    "HealthStatus",
    "HttpRuntimeAdapter",
    "ReadinessStatus",
    "ServerBootstrapError",
    "ServerRuntime",
    "StdioRuntimeAdapter",
    "create_runtime",
    "create_server",
    "run_server",
]
