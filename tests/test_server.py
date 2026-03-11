from __future__ import annotations

from dataclasses import dataclass

import pytest

from ctxledger.config import (
    AppSettings,
    AuthSettings,
    DatabaseSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    ProjectionSettings,
    StdioSettings,
    TransportMode,
)
from ctxledger.server import (
    CtxLedgerServer,
    ReadinessStatus,
    ServerBootstrapError,
    create_runtime,
)


@dataclass
class FakeDatabaseHealthChecker:
    ping_should_fail: bool = False
    schema_ready_value: bool = True
    ping_calls: int = 0
    schema_ready_calls: int = 0

    def ping(self) -> None:
        self.ping_calls += 1
        if self.ping_should_fail:
            raise RuntimeError("database unavailable")

    def schema_ready(self) -> bool:
        self.schema_ready_calls += 1
        return self.schema_ready_value


@dataclass
class FakeRuntime:
    start_calls: int = 0
    stop_calls: int = 0
    start_should_fail: bool = False

    def start(self) -> None:
        self.start_calls += 1
        if self.start_should_fail:
            raise RuntimeError("runtime start failed")

    def stop(self) -> None:
        self.stop_calls += 1


def make_settings(
    *,
    database_url: str = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
    transport: TransportMode = TransportMode.HTTP,
    http_enabled: bool = True,
    stdio_enabled: bool = False,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> AppSettings:
    return AppSettings(
        app_name="ctxledger",
        app_version="0.1.0",
        environment="test",
        transport=transport,
        database=DatabaseSettings(
            url=database_url,
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
        ),
        http=HttpSettings(
            enabled=http_enabled,
            host=host,
            port=port,
            path="/mcp",
        ),
        stdio=StdioSettings(
            enabled=stdio_enabled,
        ),
        auth=AuthSettings(
            bearer_token=None,
            require_auth=False,
        ),
        projection=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
        logging=LoggingSettings(
            level=LogLevel.INFO,
            structured=True,
        ),
    )


def test_startup_marks_server_started_when_configuration_and_db_are_valid() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )

    server.startup()

    health = server.health()
    readiness = server.readiness()

    assert health.ok is True
    assert health.status == "ok"
    assert health.details["started"] is True

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.details["database_reachable"] is True
    assert readiness.details["schema_ready"] is True

    assert db_checker.ping_calls >= 2
    assert db_checker.schema_ready_calls >= 2
    assert runtime.start_calls == 1


def test_startup_raises_when_database_check_fails() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker(ping_should_fail=True)
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        server.startup()

    readiness = server.readiness()
    assert readiness.ready is False
    assert readiness.status == "not_started"
    assert runtime.start_calls == 0


def test_startup_raises_when_schema_is_not_ready() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker(schema_ready_value=False)
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )

    with pytest.raises(ServerBootstrapError, match="database schema is not ready"):
        server.startup()

    readiness = server.readiness()
    assert readiness.ready is False
    assert readiness.status == "not_started"
    assert runtime.start_calls == 0


def test_shutdown_stops_runtime_after_successful_startup() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )

    server.startup()
    server.shutdown()

    assert runtime.start_calls == 1
    assert runtime.stop_calls == 1
    assert server.health().details["started"] is False


def test_readiness_reports_database_unavailable_after_start_if_ping_fails() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )

    server.startup()
    db_checker.ping_should_fail = True

    readiness = server.readiness()

    assert readiness.ready is False
    assert readiness.status == "database_unavailable"
    assert readiness.details["database_reachable"] is False
    assert "database unavailable" in readiness.details["error"]


def test_readiness_reports_schema_not_ready_after_start() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )

    server.startup()
    db_checker.schema_ready_value = False

    readiness = server.readiness()

    assert readiness.ready is False
    assert readiness.status == "schema_not_ready"
    assert readiness.details["schema_ready"] is False


def test_readiness_reports_not_started_before_startup() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    readiness = server.readiness()

    assert isinstance(readiness, ReadinessStatus)
    assert readiness.ready is False
    assert readiness.status == "not_started"
    assert readiness.details["started"] is False


def test_startup_raises_for_invalid_configuration() -> None:
    settings = make_settings(
        transport=TransportMode.HTTP,
        http_enabled=False,
        stdio_enabled=False,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    with pytest.raises(Exception):
        server.startup()


def test_create_runtime_returns_http_adapter_when_http_only() -> None:
    settings = make_settings(
        transport=TransportMode.HTTP,
        http_enabled=True,
        stdio_enabled=False,
    )

    runtime = create_runtime(settings)

    assert runtime is not None
    assert runtime.__class__.__name__ == "HttpRuntimeAdapter"


def test_create_runtime_returns_stdio_adapter_when_stdio_only() -> None:
    settings = make_settings(
        transport=TransportMode.STDIO,
        http_enabled=False,
        stdio_enabled=True,
    )

    runtime = create_runtime(settings)

    assert runtime is not None
    assert runtime.__class__.__name__ == "StdioRuntimeAdapter"


def test_create_runtime_returns_composite_adapter_when_both_transports_enabled() -> (
    None
):
    settings = make_settings(
        transport=TransportMode.BOTH,
        http_enabled=True,
        stdio_enabled=True,
    )

    runtime = create_runtime(settings)

    assert runtime is not None
    assert runtime.__class__.__name__ == "CompositeRuntimeAdapter"
