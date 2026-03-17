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
from ctxledger.server import CtxLedgerServer, create_server, run_server
from tests.support.server_test_support import (
    FakeDatabaseHealthChecker,
    FakeRuntime,
    build_runtime_summary_payload,
    install_logging_info_capture,
    make_http_runtime,
    make_resume_fixture,
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


def test_server_response_builder_methods_delegate_to_runtime_response_helpers() -> None:
    server = make_server(runtime=None)
    workflow_instance_id = make_resume_fixture().workflow_instance.workflow_instance_id

    resume_response = server.build_workflow_resume_response(workflow_instance_id)
    introspection_response = server.build_runtime_introspection_response()
    routes_response = server.build_runtime_routes_response()
    tools_response = server.build_runtime_tools_response()

    assert resume_response.status_code == 503
    assert resume_response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert introspection_response.status_code == 200
    assert introspection_response.payload == {"runtime": []}
    assert routes_response.status_code == 200
    assert routes_response.payload == {"routes": []}
    assert tools_response.status_code == 200
    assert tools_response.payload == {"tools": []}


def test_build_workspace_and_workflow_resource_responses_delegate_to_runtime_helpers() -> (
    None
):
    workspace_id = make_resume_fixture().workspace.workspace_id
    workflow_instance_id = make_resume_fixture().workflow_instance.workflow_instance_id
    server = make_server(runtime=None)

    workspace_response = server.build_workspace_resume_resource_response(workspace_id)
    workflow_response = server.build_workflow_detail_resource_response(
        workspace_id,
        workflow_instance_id,
    )

    assert workspace_response.status_code == 503
    assert workspace_response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert workflow_response.status_code == 503
    assert workflow_response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }


def test_run_server_wrapper_delegates_to_runtime_orchestration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_server(
        *,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> int:
        captured["transport"] = transport
        captured["host"] = host
        captured["port"] = port
        return 17

    monkeypatch.setattr("ctxledger.runtime.orchestration.run_server", fake_run_server)

    exit_code = run_server(
        transport="http",
        host="0.0.0.0",
        port=9000,
    )

    assert exit_code == 17
    assert captured == {
        "transport": "http",
        "host": "0.0.0.0",
        "port": 9000,
    }


def test_startup_builds_owned_connection_pool_and_falls_back_when_factory_rejects_connection_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    built_pools: list[object] = []
    postgres_configs: list[object] = []

    class FakePool:
        def close(self) -> None:
            return None

    fake_pool = FakePool()

    def fake_from_settings(received_settings: object) -> object:
        postgres_configs.append(received_settings)
        return "postgres-config"

    def fake_build_connection_pool(config: object) -> object:
        built_pools.append(config)
        return fake_pool

    class RejectingFactory:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def __call__(self, **kwargs: object) -> object:
            self.calls.append(dict(kwargs))
            if "connection_pool" in kwargs:
                raise TypeError("connection_pool is not accepted")
            return "workflow-service"

    rejecting_factory = RejectingFactory()
    server = make_server(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )
    server.connection_pool = None
    server.workflow_service_factory = rejecting_factory
    server._owns_connection_pool = True

    monkeypatch.setattr(
        "ctxledger.server.PostgresConfig.from_settings", fake_from_settings
    )
    monkeypatch.setattr(
        "ctxledger.server.build_connection_pool", fake_build_connection_pool
    )

    server.startup()

    assert postgres_configs == [settings]
    assert built_pools == ["postgres-config"]
    assert rejecting_factory.calls == [
        {"connection_pool": fake_pool},
        {},
    ]
    assert server.connection_pool is fake_pool
    assert server.workflow_service == "workflow-service"
    assert runtime.start_calls == 1
    assert server.health().details["started"] is True


def test_startup_raises_type_error_when_factory_failure_is_not_connection_pool_related(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()

    class FakePool:
        def close(self) -> None:
            return None

    def fake_from_settings(received_settings: object) -> object:
        assert received_settings is settings
        return "postgres-config"

    def fake_build_connection_pool(config: object) -> object:
        assert config == "postgres-config"
        return FakePool()

    def exploding_factory(**kwargs: object) -> object:
        raise TypeError("unexpected keyword")

    server = make_server(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )
    server.connection_pool = None
    server.workflow_service_factory = exploding_factory
    server._owns_connection_pool = True

    monkeypatch.setattr(
        "ctxledger.server.PostgresConfig.from_settings", fake_from_settings
    )
    monkeypatch.setattr(
        "ctxledger.server.build_connection_pool", fake_build_connection_pool
    )

    with pytest.raises(TypeError, match="unexpected keyword"):
        server.startup()

    assert runtime.start_calls == 0
    assert server.health().details["started"] is False


def test_shutdown_closes_owned_connection_pool_and_clears_workflow_service() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    close_calls: list[str] = []

    class FakePool:
        def close(self) -> None:
            close_calls.append("close")

    server = make_server(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )
    server.connection_pool = FakePool()
    server.workflow_service = object()
    server._owns_connection_pool = True
    server._started = True

    server.shutdown()

    assert runtime.stop_calls == 1
    assert close_calls == ["close"]
    assert server.connection_pool is None
    assert server.workflow_service is None
    assert server.health().details["started"] is False


def test_shutdown_keeps_external_connection_pool_open() -> None:
    settings = make_settings()
    db_checker = FakeDatabaseHealthChecker()
    runtime = FakeRuntime()
    close_calls: list[str] = []

    class FakePool:
        def close(self) -> None:
            close_calls.append("close")

    pool = FakePool()
    server = make_server(
        settings=settings,
        db_health_checker=db_checker,
        runtime=runtime,
    )
    server.connection_pool = pool
    server._owns_connection_pool = False
    server._started = True

    server.shutdown()

    assert runtime.stop_calls == 1
    assert close_calls == []
    assert server.connection_pool is pool
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

    assert isinstance(server, CtxLedgerServer)
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

    assert isinstance(server, CtxLedgerServer)
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
