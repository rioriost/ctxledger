from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from ctxledger.config import DebugSettings, LoggingSettings, LogLevel
from ctxledger.runtime.database_health import build_database_health_checker
from ctxledger.runtime.errors import ServerBootstrapError
from ctxledger.runtime.http_runtime import HttpRuntimeAdapter
from ctxledger.runtime.orchestration import create_runtime, print_runtime_summary
from ctxledger.runtime.types import ReadinessStatus
from ctxledger.server import create_server
from tests.support.server_test_support import (
    FakeDatabaseHealthChecker,
    FakeRuntime,
    build_runtime_summary_payload,
    install_logging_info_capture,
    make_http_runtime,
    make_server,
    make_settings,
)


def test_startup_marks_server_started_when_configuration_and_db_are_valid() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    server = make_server(
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
    assert health.details["runtime"] == []

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.details["database_reachable"] is True
    assert readiness.details["schema_ready"] is True
    assert readiness.details["runtime"] == []

    assert db_checker.ping_calls >= 2
    assert db_checker.schema_ready_calls >= 2
    assert runtime.start_calls == 1


def test_configure_logging_sets_ctxledger_and_root_logger_levels() -> None:
    settings = replace(
        make_settings(),
        logging=LoggingSettings(level=LogLevel.DEBUG, structured=True),
    )
    server = make_server(settings=settings)

    original_basic_config = logging.basicConfig
    original_root_level = logging.getLogger().level
    original_ctxledger_level = logging.getLogger("ctxledger").level
    original_workflow_level = logging.getLogger("ctxledger.workflow.service").level
    original_server_level = logging.getLogger("ctxledger.server").level
    basic_config_calls: list[dict[str, object]] = []

    def fake_basic_config(**kwargs: object) -> None:
        basic_config_calls.append(dict(kwargs))
        level = kwargs.get("level", logging.INFO)
        logging.getLogger().setLevel(level)
        logging.getLogger("ctxledger").setLevel(level)
        logging.getLogger("ctxledger.workflow.service").setLevel(level)
        logging.getLogger("ctxledger.server").setLevel(level)

    try:
        logging.basicConfig = fake_basic_config
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("ctxledger").setLevel(logging.WARNING)
        logging.getLogger("ctxledger.workflow.service").setLevel(logging.WARNING)
        logging.getLogger("ctxledger.server").setLevel(logging.WARNING)

        server.configure_logging()
    finally:
        logging.basicConfig = original_basic_config
        logging.getLogger().setLevel(original_root_level)
        logging.getLogger("ctxledger").setLevel(original_ctxledger_level)
        logging.getLogger("ctxledger.workflow.service").setLevel(
            original_workflow_level
        )
        logging.getLogger("ctxledger.server").setLevel(original_server_level)

    assert basic_config_calls == [
        {
            "level": logging.DEBUG,
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "force": True,
        }
    ]


def test_configure_logging_explicitly_sets_uvicorn_logger_levels() -> None:
    settings = replace(
        make_settings(),
        logging=LoggingSettings(level=LogLevel.DEBUG, structured=True),
    )
    server = make_server(settings=settings)

    original_basic_config = logging.basicConfig
    original_root_level = logging.getLogger().level
    original_uvicorn_level = logging.getLogger("uvicorn").level
    original_uvicorn_error_level = logging.getLogger("uvicorn.error").level
    original_uvicorn_access_level = logging.getLogger("uvicorn.access").level

    def fake_basic_config(**kwargs: object) -> None:
        level = kwargs.get("level", logging.INFO)
        logging.getLogger().setLevel(level)

    try:
        logging.basicConfig = fake_basic_config
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)

        server.configure_logging()

        assert logging.getLogger().level == logging.DEBUG
        assert logging.getLogger("uvicorn").level == logging.DEBUG
        assert logging.getLogger("uvicorn.error").level == logging.DEBUG
        assert logging.getLogger("uvicorn.access").level == logging.DEBUG
    finally:
        logging.basicConfig = original_basic_config
        logging.getLogger().setLevel(original_root_level)
        logging.getLogger("uvicorn").setLevel(original_uvicorn_level)
        logging.getLogger("uvicorn.error").setLevel(original_uvicorn_error_level)
        logging.getLogger("uvicorn.access").setLevel(original_uvicorn_access_level)


def test_startup_raises_when_database_check_fails() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker(ping_should_fail=True)
    runtime = FakeRuntime()
    server = make_server(
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
    server = make_server(
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
    server = make_server(
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
    server = make_server(
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
    server = make_server(
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
    server = make_server(settings=settings)

    readiness = server.readiness()

    assert isinstance(readiness, ReadinessStatus)
    assert readiness.ready is False
    assert readiness.status == "not_started"
    assert readiness.details["started"] is False
    assert readiness.details["runtime"] == []


def test_startup_raises_for_invalid_configuration() -> None:
    settings = make_settings(host="")
    server = make_server(settings=settings)

    with pytest.raises(Exception):
        server.startup()


def test_create_runtime_returns_http_adapter_when_http_only() -> None:
    settings = make_settings()

    runtime = create_runtime(
        settings,
        server=None,
        http_runtime_builder=lambda server: HttpRuntimeAdapter(settings),
    )

    assert runtime is not None
    assert runtime.__class__.__name__ == "HttpRuntimeAdapter"


def test_build_database_health_checker_returns_default_when_database_url_is_missing() -> (
    None
):
    checker = build_database_health_checker(None)

    assert checker.__class__.__name__ == "DefaultDatabaseHealthChecker"


def test_build_database_health_checker_returns_default_when_psycopg_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            raise ImportError("psycopg not installed")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    checker = build_database_health_checker(
        "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
    )

    assert checker.__class__.__name__ == "DefaultDatabaseHealthChecker"


def test_build_database_health_checker_returns_postgres_when_psycopg_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePsycopgModule:
        pass

    original_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            return FakePsycopgModule()
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    checker = build_database_health_checker(
        "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
    )

    assert checker.__class__.__name__ == "PostgresDatabaseHealthChecker"


def test_create_server_wires_http_runtime_with_workflow_resume_route() -> None:
    settings = make_settings()

    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: None,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.introspection_endpoints() == (
        "mcp_rpc",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_resume",
    )


def test_create_server_returns_http_runtime_by_default() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: None,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)


def test_health_includes_runtime_summary_details_for_http_runtime() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(settings=settings)

    health = server.health()

    assert health.ok is True
    assert health.status == "ok"
    assert health.details["runtime"] == build_runtime_summary_payload()


def test_readiness_includes_runtime_summary_details_for_http_runtime() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    readiness = server.readiness()

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.details["runtime"] == build_runtime_summary_payload()


def test_startup_logs_runtime_introspection_metadata_for_http_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(settings=settings)
    info_calls = install_logging_info_capture(monkeypatch)

    server.startup()

    startup_complete_extra = next(
        extra
        for message, extra in info_calls
        if message == "ctxledger startup complete"
    )

    assert startup_complete_extra["host"] == settings.http.host
    assert startup_complete_extra["port"] == settings.http.port
    assert startup_complete_extra["mcp_url"] == settings.http.mcp_url
    assert startup_complete_extra["workflow_service_initialized"] is True
    assert startup_complete_extra["runtime"] == build_runtime_summary_payload()


def test_print_runtime_summary_includes_http_runtime_introspection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    print_runtime_summary(server)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ctxledger 0.1.0 started" in captured.err
    assert "health=ok" in captured.err
    assert "readiness=ready" in captured.err
    assert "runtime=[{'transport': 'http'" in captured.err
    assert "'workflow_resume'" in captured.err
    assert "'workspace_register'" in captured.err
    assert "'workspace://{workspace_id}/resume'" in captured.err
    assert f"mcp_endpoint={server.settings.http.mcp_url}" in captured.err


def test_create_server_omits_debug_routes_when_debug_endpoints_are_disabled() -> None:
    settings = replace(
        make_settings(),
        debug=DebugSettings(enabled=False),
    )

    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: None,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.introspection_endpoints() == (
        "mcp_rpc",
        "workflow_resume",
    )
