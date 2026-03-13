from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import signal
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.config import (
    AppSettings,
    DatabaseSettings,
    DebugSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    ProjectionSettings,
)
from ctxledger.projection.writer import ResumeProjectionWriter
from ctxledger.runtime.database_health import (
    DefaultDatabaseHealthChecker,
    PostgresDatabaseHealthChecker,
    ServerBootstrapError,
    build_database_health_checker,
)
from ctxledger.runtime.introspection import (
    RuntimeIntrospection,
    collect_runtime_introspection,
)
from ctxledger.runtime.orchestration import (
    apply_overrides,
    create_runtime,
    install_signal_handlers,
    print_runtime_summary,
    run_server,
)
from ctxledger.runtime.server_factory import build_workflow_service_factory
from ctxledger.runtime.server_responses import (
    build_projection_failures_ignore_response,
    build_projection_failures_resolve_response,
    build_runtime_introspection_response,
    build_runtime_routes_response,
    build_runtime_tools_response,
    build_workflow_detail_resource_response,
    build_workspace_resume_resource_response,
)
from ctxledger.runtime.status import build_health_status, build_readiness_status
from ctxledger.runtime.types import RuntimeIntrospectionResponse
from ctxledger.server import CtxLedgerServer
from ctxledger.workflow.service import ProjectionArtifactType, ResumableStatus


def make_settings(
    *,
    database_url: str = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
    host: str = "127.0.0.1",
    port: int = 8080,
    path: str = "/mcp",
    debug_enabled: bool = True,
) -> AppSettings:
    return AppSettings(
        app_name="ctxledger",
        app_version="0.1.0",
        environment="test",
        database=DatabaseSettings(
            url=database_url,
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
        ),
        http=HttpSettings(
            host=host,
            port=port,
            path=path,
        ),
        debug=DebugSettings(enabled=debug_enabled),
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


class FakeDbChecker:
    def ping(self) -> None:
        return None

    def schema_ready(self) -> bool:
        return True


class FakeRuntime:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


class FakeWorkflowService:
    def __init__(self) -> None:
        self.resume = {"ok": True}
        self.register_workspace_calls: list[object] = []
        self.start_workflow_calls: list[object] = []
        self.create_checkpoint_calls: list[object] = []
        self.complete_workflow_calls: list[object] = []
        self.ignore_calls: list[dict[str, object]] = []
        self.resolve_calls: list[dict[str, object]] = []

    def resume_workflow(self, data: object) -> dict[str, object]:
        return {"workflow_instance_id": str(data.workflow_instance_id)}

    def register_workspace(self, data: object) -> dict[str, object]:
        self.register_workspace_calls.append(data)
        return {"workspace_id": str(uuid4())}

    def start_workflow(self, data: object) -> dict[str, object]:
        self.start_workflow_calls.append(data)
        return {"workflow_instance_id": str(uuid4())}

    def create_checkpoint(self, data: object) -> dict[str, object]:
        self.create_checkpoint_calls.append(data)
        return {"checkpoint_id": str(uuid4())}

    def complete_workflow(self, data: object) -> dict[str, object]:
        self.complete_workflow_calls.append(data)
        return {"workflow_instance_id": str(uuid4())}

    def ignore_resume_projection_failures(
        self,
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        self.ignore_calls.append(
            {
                "workspace_id": workspace_id,
                "workflow_instance_id": workflow_instance_id,
                "projection_type": projection_type,
            }
        )
        return 1

    def resolve_resume_projection_failures(
        self,
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        self.resolve_calls.append(
            {
                "workspace_id": workspace_id,
                "workflow_instance_id": workflow_instance_id,
                "projection_type": projection_type,
            }
        )
        return 2


def make_server(
    *,
    settings: AppSettings | None = None,
    runtime: object | None = None,
    workflow_service_factory=None,
) -> CtxLedgerServer:
    return CtxLedgerServer(
        settings=settings or make_settings(),
        db_health_checker=FakeDbChecker(),
        runtime=runtime,
        workflow_service_factory=workflow_service_factory,
    )


class FailingDbChecker(FakeDbChecker):
    def __init__(
        self,
        *,
        ping_error: Exception | None = None,
        schema_error: Exception | None = None,
        schema_ready_value: bool = True,
    ) -> None:
        self.ping_error = ping_error
        self.schema_error = schema_error
        self.schema_ready_value = schema_ready_value

    def ping(self) -> None:
        if self.ping_error is not None:
            raise self.ping_error

    def schema_ready(self) -> bool:
        if self.schema_error is not None:
            raise self.schema_error
        return self.schema_ready_value


def test_default_database_health_checker_ping_and_schema_ready() -> None:
    checker = DefaultDatabaseHealthChecker(
        "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
    )

    checker.ping()

    assert checker.schema_ready() is True


def test_default_database_health_checker_raises_without_database_url() -> None:
    checker = DefaultDatabaseHealthChecker(None)

    with pytest.raises(ServerBootstrapError, match="database_url is not configured"):
        checker.ping()

    assert checker.schema_ready() is False


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        (None, 5),
        ("postgresql://example/db", 5),
        ("postgresql://example/db?connect_timeout=7", 7),
        ("postgresql://example/db?connect_timeout=0", 5),
        ("postgresql://example/db?connect_timeout=-1", 5),
        ("postgresql://example/db?connect_timeout=abc", 5),
    ],
)
def test_postgres_database_health_checker_connect_timeout_parsing(
    database_url: str | None,
    expected: int,
) -> None:
    checker = PostgresDatabaseHealthChecker(database_url)
    assert checker._connect_timeout_seconds() == expected


def test_postgres_database_health_checker_connect_requires_database_url() -> None:
    checker = PostgresDatabaseHealthChecker(None)

    with pytest.raises(ServerBootstrapError, match="database_url is not configured"):
        checker._connect()


def test_postgres_database_health_checker_connect_requires_psycopg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            raise ImportError("psycopg missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    with pytest.raises(
        ServerBootstrapError,
        match="PostgreSQL health checker requires psycopg to be installed",
    ):
        checker._connect()


def test_postgres_database_health_checker_ping_executes_select_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, object | None]] = []

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed.append((query.strip(), params))

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(
        connect=lambda *_args, **_kwargs: FakeConnection()
    )
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db?connect_timeout=9")
    checker.ping()

    assert executed == [("SELECT 1", None)]


def test_postgres_database_health_checker_schema_ready_true_when_all_tables_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, tuple[str, ...] | None]] = []

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: tuple[str, ...] | None = None) -> None:
            executed.append((query.strip(), params))

        def fetchone(self) -> tuple[bool]:
            return (True,)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(
        connect=lambda *_args, **_kwargs: FakeConnection()
    )
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    assert checker.schema_ready() is True
    assert len(executed) == 6
    assert [params for _, params in executed] == [
        ("workspaces",),
        ("workflow_instances",),
        ("workflow_attempts",),
        ("workflow_checkpoints",),
        ("verify_reports",),
        ("projection_states",),
    ]


def test_postgres_database_health_checker_schema_ready_false_when_table_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = iter([(True,), (True,), (False,)])

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: tuple[str, ...] | None = None) -> None:
            return None

        def fetchone(self) -> tuple[bool] | None:
            return next(rows)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(
        connect=lambda *_args, **_kwargs: FakeConnection()
    )
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    assert checker.schema_ready() is False


def test_build_database_health_checker_prefers_default_without_url() -> None:
    checker = build_database_health_checker(None)
    assert isinstance(checker, DefaultDatabaseHealthChecker)


def test_apply_overrides_returns_same_settings_when_no_overrides() -> None:
    settings = make_settings()

    overridden = apply_overrides(settings)

    assert overridden is settings


def test_apply_overrides_rejects_non_http_transport() -> None:
    with pytest.raises(ValueError, match="transport override must be 'http'"):
        apply_overrides(make_settings(), transport="stdio")


def test_apply_overrides_reflects_current_auth_field_regression() -> None:
    settings = make_settings(host="127.0.0.1", port=8080)

    with pytest.raises(AttributeError, match="auth"):
        apply_overrides(
            settings,
            transport="http",
            host="0.0.0.0",
            port=9090,
        )


def test_create_runtime_uses_http_runtime_builder() -> None:
    settings = make_settings()
    sentinel_runtime = object()
    received: list[object] = []

    def builder(server: object) -> object:
        received.append(server)
        return sentinel_runtime

    created = create_runtime(
        settings, server="server-ref", http_runtime_builder=builder
    )

    assert created is sentinel_runtime
    assert received == ["server-ref"]


def test_install_signal_handlers_registers_sigint_and_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered: list[tuple[signal.Signals, object]] = []

    def fake_signal(sig: signal.Signals, handler: object) -> None:
        registered.append((sig, handler))

    monkeypatch.setattr(signal, "signal", fake_signal)

    install_signal_handlers(server=object())

    assert [sig for sig, _ in registered] == [signal.SIGINT, signal.SIGTERM]


def test_install_signal_handlers_skips_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[signal.Signals] = []

    def fake_signal(sig: signal.Signals, handler: object) -> None:
        calls.append(sig)
        raise ValueError("not main thread")

    monkeypatch.setattr(signal, "signal", fake_signal)

    install_signal_handlers(server=object())

    assert calls == [signal.SIGINT, signal.SIGTERM]


def test_print_runtime_summary_writes_expected_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = make_server(runtime=None)
    server.startup()

    print_runtime_summary(server)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ctxledger 0.1.0 started" in captured.err
    assert "health=ok" in captured.err
    assert "readiness=ready" in captured.err
    assert "runtime=[]" in captured.err
    assert "mcp_endpoint=http://127.0.0.1:8080/mcp" in captured.err


def test_build_health_status_reports_workflow_service_and_runtime() -> None:
    runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=("workflow_resume",),
            resources=("workspace://{workspace_id}/resume",),
        )
    )
    server = make_server(runtime=runtime)
    server.workflow_service = object()
    server._started = True

    status = build_health_status(server)

    assert status.ok is True
    assert status.status == "ok"
    assert status.details == {
        "service": "ctxledger",
        "version": "0.1.0",
        "started": True,
        "workflow_service_initialized": True,
        "runtime": [
            {
                "transport": "http",
                "routes": ["workflow_resume"],
                "tools": ["workflow_resume"],
                "resources": ["workspace://{workspace_id}/resume"],
            }
        ],
    }


def test_build_readiness_status_reports_schema_check_failed() -> None:
    server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FailingDbChecker(
            schema_error=RuntimeError("schema lookup failed")
        ),
        runtime=None,
    )
    server._started = True

    status = build_readiness_status(server)

    assert status.ready is False
    assert status.status == "schema_check_failed"
    assert status.details["database_reachable"] is True
    assert status.details["schema_ready"] is False
    assert status.details["error"] == "schema lookup failed"


def test_collect_runtime_introspection_flattens_nested_runtimes() -> None:
    nested_runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=("workflow_resume",),
            resources=("workspace://{workspace_id}/resume",),
        )
    )
    runtime = types.SimpleNamespace(_runtimes=[nested_runtime])

    introspections = collect_runtime_introspection(runtime)

    assert introspections == (
        RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=("workflow_resume",),
            resources=("workspace://{workspace_id}/resume",),
        ),
    )


def test_collect_runtime_introspection_ignores_non_introspection_payload() -> None:
    runtime = types.SimpleNamespace(introspect=lambda: object())

    assert collect_runtime_introspection(runtime) == ()


def test_build_runtime_routes_and_tools_responses_filter_empty_entries() -> None:
    runtime = types.SimpleNamespace(
        _runtimes=[
            types.SimpleNamespace(
                introspect=lambda: RuntimeIntrospection(
                    transport="http",
                    routes=("workflow_resume",),
                    tools=("workflow_resume",),
                    resources=(),
                )
            ),
            types.SimpleNamespace(
                introspect=lambda: RuntimeIntrospection(
                    transport="shadow",
                    routes=(),
                    tools=(),
                    resources=(),
                )
            ),
        ]
    )
    server = make_server(runtime=runtime)

    routes_response = build_runtime_routes_response(server)
    tools_response = build_runtime_tools_response(server)

    assert isinstance(routes_response, RuntimeIntrospectionResponse)
    assert routes_response.payload == {
        "routes": [{"transport": "http", "routes": ["workflow_resume"]}]
    }
    assert tools_response.payload == {
        "tools": [{"transport": "http", "tools": ["workflow_resume"]}]
    }


def test_build_projection_failure_responses_cover_not_ready_and_error_mapping() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    not_ready_server = make_server()
    ignore_not_ready = build_projection_failures_ignore_response(
        not_ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
    )
    resolve_not_ready = build_projection_failures_resolve_response(
        not_ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
    )

    assert ignore_not_ready.status_code == 503
    assert resolve_not_ready.status_code == 503

    service = FakeWorkflowService()

    def raise_not_found(**kwargs: object) -> int:
        raise RuntimeError("workflow not found")

    def raise_mismatch(**kwargs: object) -> int:
        raise RuntimeError("workflow instance does not belong to workspace")

    def raise_generic(**kwargs: object) -> int:
        raise RuntimeError("projection storage exploded")

    ready_server = make_server(workflow_service_factory=lambda: service)
    ready_server.startup()

    service.ignore_resume_projection_failures = raise_not_found
    response = build_projection_failures_ignore_response(
        ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
    )
    assert response.status_code == 404
    assert response.payload["error"]["code"] == "not_found"

    service.ignore_resume_projection_failures = raise_mismatch
    response = build_projection_failures_ignore_response(
        ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
    )
    assert response.status_code == 400
    assert response.payload["error"]["code"] == "invalid_request"

    service.resolve_resume_projection_failures = raise_generic
    response = build_projection_failures_resolve_response(
        ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
    )
    assert response.status_code == 500
    assert response.payload["error"]["code"] == "server_error"


def test_runtime_introspection_response_uses_runtime_collection() -> None:
    runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=("workflow_resume",),
            resources=("workspace://{workspace_id}/resume",),
        )
    )
    server = make_server(runtime=runtime)

    response = build_runtime_introspection_response(server)

    assert response.status_code == 200
    assert response.payload == {
        "runtime": [
            {
                "transport": "http",
                "routes": ["workflow_resume"],
                "tools": ["workflow_resume"],
                "resources": ["workspace://{workspace_id}/resume"],
            }
        ]
    }


def test_cli_helpers_cover_schema_path_and_version_fallback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_schema_path",
        lambda: Path("/tmp/project/schemas/postgres.sql"),
    )

    absolute_exit_code = cli_module._print_schema_path(True)
    relative_exit_code = cli_module._print_schema_path(False)

    captured = capsys.readouterr()
    assert absolute_exit_code == 0
    assert relative_exit_code == 0
    assert "/tmp/project/schemas/postgres.sql" in captured.out

    original_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "importlib.metadata":
            raise ImportError("metadata unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    exit_code = cli_module._print_version()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "0.1.0"


def test_cli_apply_schema_covers_missing_url_and_driver_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(database_url=None)
    monkeypatch.setattr(
        "ctxledger.config.get_settings", lambda: make_settings(database_url="")
    )

    original_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            return types.SimpleNamespace(connect=lambda *_args, **_kwargs: None)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    exit_code = cli_module._apply_schema(args)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        in captured.err
    )

    def fake_import_missing_driver(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            raise ImportError("missing driver")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import_missing_driver)

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://example/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Failed to import PostgreSQL driver. Install psycopg[binary] first."
        in captured.err
    )


def test_cli_serve_and_main_dispatch_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_server_calls: list[dict[str, object]] = []

    def fake_run_server(**kwargs: object) -> int:
        run_server_calls.append(dict(kwargs))
        return 7

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    args = SimpleNamespace(transport="http", host="0.0.0.0", port=9090)
    assert cli_module._serve(args) == 7
    assert run_server_calls == [{"transport": "http", "host": "0.0.0.0", "port": 9090}]

    parse_args_calls: list[list[str] | None] = []

    class FakeParser:
        def parse_args(self, argv: list[str] | None) -> object:
            parse_args_calls.append(argv)
            return SimpleNamespace(command="version")

        def error(self, message: str) -> None:
            raise AssertionError(message)

    monkeypatch.setattr(cli_module, "_build_parser", lambda: FakeParser())
    monkeypatch.setattr(cli_module, "_print_version", lambda: 11)

    assert cli_module.main(["version"]) == 11
    assert parse_args_calls == [["version"]]

    class UnknownParser:
        def parse_args(self, argv: list[str] | None) -> object:
            return SimpleNamespace(command="mystery")

        def error(self, message: str) -> None:
            raise RuntimeError(message)

    monkeypatch.setattr(cli_module, "_build_parser", lambda: UnknownParser())

    with pytest.raises(RuntimeError, match="Unknown command: mystery"):
        cli_module.main(["mystery"])


def test_run_server_returns_zero_on_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakeServer:
        def __init__(self) -> None:
            self.settings = settings
            self.runtime = None
            self.startup_calls = 0

        def startup(self) -> None:
            self.startup_calls += 1

        def readiness(self):
            return types.SimpleNamespace(status="ready")

        def health(self):
            return types.SimpleNamespace(status="ok")

    fake_server = FakeServer()

    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        lambda settings, **kwargs: settings,
    )
    monkeypatch.setattr("ctxledger.server.create_server", lambda _settings: fake_server)

    exit_code = run_server()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert fake_server.startup_calls == 1
    assert "ctxledger 0.1.0 started" in captured.err


def test_run_server_returns_one_for_bootstrap_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakeServer:
        def startup(self) -> None:
            raise ServerBootstrapError("database schema is not ready")

    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        lambda settings, **kwargs: settings,
    )
    monkeypatch.setattr(
        "ctxledger.server.create_server", lambda _settings: FakeServer()
    )

    exit_code = run_server()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Startup failed: database schema is not ready" in captured.err


def test_run_server_returns_one_for_unhandled_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakeServer:
        def startup(self) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        lambda settings, **kwargs: settings,
    )
    monkeypatch.setattr(
        "ctxledger.server.create_server", lambda _settings: FakeServer()
    )

    exit_code = run_server()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Unhandled server error: boom" in captured.err


def test_build_workflow_service_factory_returns_none_without_database_url() -> None:
    settings = make_settings(database_url="")

    assert build_workflow_service_factory(settings) is None


def test_build_workflow_service_factory_builds_workflow_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, settings: AppSettings) -> str:
            captured["settings"] = settings
            return "postgres-config"

    def fake_build_postgres_uow_factory(config: object):
        captured["config"] = config

        def _uow_factory():
            return "uow"

        return _uow_factory

    class FakeWorkflowService:
        def __init__(self, uow_factory) -> None:
            self.uow_factory = uow_factory

    monkeypatch.setattr(
        "ctxledger.runtime.server_factory.PostgresConfig",
        FakePostgresConfig,
    )
    monkeypatch.setattr(
        "ctxledger.runtime.server_factory.build_postgres_uow_factory",
        fake_build_postgres_uow_factory,
    )
    monkeypatch.setattr(
        "ctxledger.runtime.server_factory.WorkflowService",
        FakeWorkflowService,
    )

    settings = make_settings()
    factory = build_workflow_service_factory(settings)

    assert factory is not None
    service = factory()

    assert captured["settings"] is settings
    assert captured["config"] == "postgres-config"
    assert isinstance(service, FakeWorkflowService)
    assert callable(service.uow_factory)
    assert service.uow_factory() == "uow"


def test_memory_uow_module_reexports_expected_symbols() -> None:
    module = importlib.import_module("ctxledger.db.memory_uow")

    assert module.make_in_memory_uow_factory is module.build_in_memory_uow_factory
    assert "make_in_memory_uow_factory" in module.__all__
    assert "InMemoryUnitOfWork" in module.__all__


def _load_http_app_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )
    sys.modules.pop("ctxledger.http_app", None)
    return importlib.import_module("ctxledger.http_app")


def test_http_app_request_helpers_and_response_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)

    request = SimpleNamespace(
        headers={"authorization": " Bearer test-token "},
        query_params=SimpleNamespace(
            multi_items=lambda: [("x", "1"), ("authorization", "old-token")]
        ),
        url=SimpleNamespace(path="/debug/runtime"),
    )

    assert http_app._authorization_query_value(request) == "Bearer test-token"
    assert http_app._query_items_with_authorization(request) == [
        ("x", "1"),
        ("authorization", "Bearer test-token"),
    ]
    assert (
        http_app._query_string_from_request(request)
        == "x=1&authorization=Bearer+test-token"
    )
    assert (
        http_app._full_path_with_query(request)
        == "/debug/runtime?x=1&authorization=Bearer+test-token"
    )
    assert http_app._request_body_text(b"hello") == "hello"
    assert http_app._request_body_text(b"") is None
    assert (
        http_app._encode_payload({"message": "hello"}).decode("utf-8")
        == '{"message": "hello"}'
    )

    response = http_app._response_from_runtime_result(
        SimpleNamespace(
            payload={"ok": True},
            status_code=201,
            headers={"x-test": "1"},
        )
    )

    assert response.status_code == 201
    assert response.headers["x-test"] == "1"
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.body.decode("utf-8")) == {"ok": True}


def test_http_app_server_not_ready_response_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)

    response = http_app._server_not_ready_response()

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.body.decode("utf-8")) == {
        "error": {
            "code": "server_not_ready",
            "message": "runtime is not initialized",
        }
    }


def test_http_app_build_get_and_post_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    server = make_server(runtime=object())

    def get_factory(_server: object):
        def handler(path: str) -> object:
            return SimpleNamespace(
                payload={"path": path},
                status_code=200,
                headers={"x-kind": "get"},
            )

        return handler

    def post_factory(_runtime: object, _server: object):
        def handler(path: str, body: str | None) -> object:
            return SimpleNamespace(
                payload={"path": path, "body": body},
                status_code=202,
                headers={"x-kind": "post"},
            )

        return handler

    get_route = http_app._build_get_route(server, get_factory)
    post_route = http_app._build_post_route(server, post_factory)

    get_request = SimpleNamespace(
        headers={"authorization": "Bearer abc"},
        query_params=SimpleNamespace(multi_items=lambda: [("q", "1")]),
        url=SimpleNamespace(path="/debug/runtime"),
    )

    async def body_bytes() -> bytes:
        return b'{"hello":"world"}'

    post_request = SimpleNamespace(
        headers={},
        query_params=SimpleNamespace(multi_items=lambda: []),
        url=SimpleNamespace(path="/mcp"),
        body=body_bytes,
    )

    get_response = asyncio.run(get_route(get_request))
    post_response = asyncio.run(post_route(post_request))

    assert get_response.status_code == 200
    assert json.loads(get_response.body.decode("utf-8")) == {
        "path": "/debug/runtime?q=1&authorization=Bearer+abc"
    }
    assert post_response.status_code == 202
    assert json.loads(post_response.body.decode("utf-8")) == {
        "path": "/mcp",
        "body": '{"hello":"world"}',
    }


def test_http_app_create_fastapi_app_from_settings_and_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    settings = make_settings()

    created_servers: list[object] = []
    created_apps: list[object] = []

    sentinel_server = object()
    sentinel_app_1 = object()
    sentinel_app_2 = object()

    original_create_server = http_app.create_server
    original_create_fastapi_app = http_app.create_fastapi_app

    def fake_create_server(received_settings: AppSettings) -> object:
        created_servers.append(received_settings)
        return sentinel_server

    def fake_create_fastapi_app(server: object) -> object:
        created_apps.append(server)
        return sentinel_app_1 if len(created_apps) == 1 else sentinel_app_2

    try:
        http_app.create_server = fake_create_server
        http_app.create_fastapi_app = fake_create_fastapi_app
        app_from_settings = http_app.create_fastapi_app_from_settings(settings)
        default_app = http_app.create_default_fastapi_app()
    finally:
        http_app.create_server = original_create_server
        http_app.create_fastapi_app = original_create_fastapi_app

    assert app_from_settings is sentinel_app_1
    assert default_app is sentinel_app_2
    assert created_servers[0] is settings
    assert isinstance(created_servers[1], AppSettings)
    assert created_apps == [sentinel_server, sentinel_server]


def test_http_app_create_fastapi_app_registers_expected_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    server = make_server(settings=make_settings(path="mcp"))

    app = http_app.create_fastapi_app(server)

    paths = {route.path for route in app.routes}
    assert "/mcp" in paths
    assert "/debug/runtime" in paths
    assert "/debug/routes" in paths
    assert "/debug/tools" in paths
    assert "/workflow-resume/{workflow_instance_id}" in paths
    assert "/workflow-resume/{workflow_instance_id}/closed-projection-failures" in paths
    assert "/projection_failures_ignore" in paths
    assert "/projection_failures_resolve" in paths


def test_build_workspace_resume_resource_response_uses_resume_result_branch() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workspace_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workspace": {
                    "workspace_id": str(workspace_id),
                },
                "workflow_instance_id": str(workflow_instance_id),
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workspace": {
                "workspace_id": str(workspace_id),
            },
            "workflow_instance_id": str(workflow_instance_id),
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_returns_not_found_for_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=other_workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=other_workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == other_workspace_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workspace": {
                    "workspace_id": str(other_workspace_id),
                },
                "workflow_instance_id": str(workflow_instance_id),
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workspace '{workspace_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uses_resume_result_branch() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/workflow/{workflow_instance_id}",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_returns_not_found_for_missing_workflow() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    other_workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=other_workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> dict[str, object]:
            return {"workflow_instance_id": str(data.workflow_instance_id)}

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workflow '{workflow_instance_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_returns_invalid_request_for_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=other_workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> dict[str, object]:
            return {"workflow_instance_id": str(data.workflow_instance_id)}

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow instance does not belong to workspace",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_runtime_routes_response_returns_empty_routes_when_runtime_has_no_routes() -> (
    None
):
    runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=(),
            tools=("workflow_resume",),
            resources=(),
        )
    )
    server = make_server(runtime=runtime)

    response = build_runtime_routes_response(server)

    assert response.status_code == 200
    assert response.payload == {"routes": []}
    assert response.headers == {"content-type": "application/json"}


def test_build_runtime_tools_response_returns_empty_tools_when_runtime_has_no_tools() -> (
    None
):
    runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=(),
            resources=(),
        )
    )
    server = make_server(runtime=runtime)

    response = build_runtime_tools_response(server)

    assert response.status_code == 200
    assert response.payload == {"tools": []}
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_propagates_non_success_workflow_response() -> (
    None
):
    workspace_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=uuid4(),
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workspace_id
        return SimpleNamespace(
            status_code=503,
            payload={
                "error": {
                    "code": "server_not_ready",
                    "message": "workflow service is not initialized",
                }
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_returns_workspace_not_found() -> (
    None
):
    workspace_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(get_by_id=lambda _workspace_id: None)
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workspace_resume_resource_response(server, workspace_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workspace '{workspace_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_returns_no_workflow() -> (
    None
):
    workspace_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workspace_resume_resource_response(server, workspace_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"no workflow is available for workspace '{workspace_id}'",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_uses_latest_when_running_missing() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(
                    workspace_id=workspace_id
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: SimpleNamespace(
                    workflow_instance_id=workflow_instance_id
                ),
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_propagates_non_success_workflow_response() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=503,
            payload={
                "error": {
                    "code": "server_not_ready",
                    "message": "workflow service is not initialized",
                }
            },
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uow_branch_returns_not_found() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda _workflow_instance_id: None
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workflow '{workflow_instance_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uow_branch_propagates_success() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda _workflow_instance_id: SimpleNamespace(
                    workflow_instance_id=workflow_instance_id,
                    workspace_id=workspace_id,
                )
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(
        _server: object, workflow_id: object
    ) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ] = fake_build_workflow_resume_response
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__[
            "build_workflow_resume_response"
        ] = original_builder

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/workflow/{workflow_instance_id}",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_mcp_dispatch_rpc_method_exit_raises_system_exit() -> None:
    with pytest.raises(SystemExit) as exc_info:
        from ctxledger.mcp.rpc import dispatch_rpc_method

        dispatch_rpc_method(
            SimpleNamespace(),
            method="exit",
            params={},
        )

    assert exc_info.value.code == 0


def test_mcp_dispatch_rpc_method_raises_for_unknown_method() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    with pytest.raises(ValueError, match="Unknown method: unknown/method"):
        dispatch_rpc_method(
            SimpleNamespace(),
            method="unknown/method",
            params={},
        )


def test_mcp_dispatch_rpc_method_validates_tools_call_params() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    runtime = SimpleNamespace()

    with pytest.raises(ValueError, match="tools/call requires 'params' \\(object\\)"):
        dispatch_rpc_method(runtime, method="tools/call", params=None)

    with pytest.raises(ValueError, match="tools/call requires 'name' \\(string\\)"):
        dispatch_rpc_method(runtime, method="tools/call", params={"arguments": {}})

    with pytest.raises(
        ValueError, match="tools/call requires 'arguments' \\(object\\)"
    ):
        dispatch_rpc_method(
            runtime,
            method="tools/call",
            params={"name": "demo_tool", "arguments": "not-an-object"},
        )


def test_mcp_dispatch_rpc_method_validates_resources_read_params() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    runtime = SimpleNamespace()

    with pytest.raises(
        ValueError, match="resources/read requires 'params' \\(object\\)"
    ):
        dispatch_rpc_method(runtime, method="resources/read", params=None)

    with pytest.raises(ValueError, match="resources/read requires 'uri' \\(string\\)"):
        dispatch_rpc_method(runtime, method="resources/read", params={})


def test_mcp_handle_request_returns_none_for_notification_and_lifecycle_none() -> None:
    from ctxledger.mcp.rpc import handle_mcp_rpc_request

    runtime = SimpleNamespace()
    request = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}

    response = handle_mcp_rpc_request(runtime, request)

    assert response is None
    assert hasattr(runtime, "_mcp_lifecycle_state")
    assert runtime._mcp_lifecycle_state.initialized is True


def test_mcp_handle_request_returns_none_for_notification_without_id() -> None:
    from ctxledger.mcp.rpc import handle_mcp_rpc_request

    runtime = SimpleNamespace(
        dispatch_tool=lambda name, arguments: SimpleNamespace(payload={"ok": True}),
    )
    runtime.registered_tools = lambda: ()
    runtime.registered_resources = lambda: ()
    runtime.tool_schema = lambda tool_name: SimpleNamespace(
        type="object",
        properties={},
        required=(),
    )
    runtime.dispatch_resource = lambda uri: SimpleNamespace(payload={"ok": True})

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "demo_tool", "arguments": {}},
        },
    )

    assert response is None


def test_mcp_ensure_lifecycle_state_reuses_existing_state() -> None:
    from ctxledger.mcp.rpc import McpLifecycleState, ensure_lifecycle_state

    existing_state = McpLifecycleState(initialized=True)
    runtime = SimpleNamespace(_mcp_lifecycle_state=existing_state)

    state = ensure_lifecycle_state(runtime)

    assert state is existing_state


def test_projection_writer_status_summary_covers_terminal_blocked_and_inconsistent() -> (
    None
):
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    assert writer._status_summary(ResumableStatus.TERMINAL) == (
        "Workflow is terminal and should be inspected, not resumed."
    )
    assert writer._status_summary(ResumableStatus.BLOCKED) == (
        "Workflow is blocked and requires additional canonical progress."
    )
    assert writer._status_summary("unexpected-status") == (
        "Workflow state is inconsistent and requires investigation."
    )


def test_projection_writer_build_resume_markdown_covers_empty_sections() -> None:
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    resume = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=uuid4(),
            ticket_id="TEST-123",
            status=SimpleNamespace(value="running"),
        ),
        resumable_status=SimpleNamespace(value="blocked"),
        workspace=SimpleNamespace(
            repo_url="https://example.com/repo.git",
            canonical_path="/tmp/workspace",
            default_branch="main",
        ),
        attempt=None,
        latest_checkpoint=None,
        projections=(),
        warnings=(),
        next_hint=None,
    )

    markdown = writer._build_resume_markdown(resume)

    assert "- No attempt available" in markdown
    assert "- No checkpoint available" in markdown
    assert "- No projection metadata available" in markdown
    assert "- None" in markdown
    assert "No next hint available." in markdown


def test_projection_writer_build_resume_markdown_includes_next_action_and_projection_details() -> (
    None
):
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    resume = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=uuid4(),
            ticket_id="TEST-456",
            status=SimpleNamespace(value="running"),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        workspace=SimpleNamespace(
            repo_url="https://example.com/repo.git",
            canonical_path="/tmp/workspace",
            default_branch="main",
        ),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            attempt_number=2,
            status=SimpleNamespace(value="running"),
            verify_status=SimpleNamespace(value="passed"),
        ),
        latest_checkpoint=SimpleNamespace(
            step_name="implement_feature",
            summary="Add branch coverage",
            checkpoint_json={"next_intended_action": "  run tests  "},
        ),
        projections=(
            SimpleNamespace(
                projection_type=SimpleNamespace(value="resume_json"),
                status=SimpleNamespace(value="fresh"),
                target_path=".agent/resume.json",
                open_failure_count=0,
            ),
        ),
        warnings=(
            SimpleNamespace(
                code="stale_projection",
                message="projection is stale",
            ),
        ),
        next_hint="Run coverage",
    )

    markdown = writer._build_resume_markdown(resume)

    assert "- Verify status: `passed`" in markdown
    assert "- Summary: Add branch coverage" in markdown
    assert "- Next intended action: run tests" in markdown
    assert "- Projection type: `resume_json`" in markdown
    assert "  - Projection status: `fresh`" in markdown
    assert "  - Target path: `.agent/resume.json`" in markdown
    assert "  - Open failure count: `0`" in markdown
    assert "- `stale_projection`: projection is stale" in markdown
    assert "Run coverage" in markdown


def test_projection_writer_build_failure_update_uses_string_error_code_only() -> None:
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    class StringCodeError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("write failed")
            self.code = "E_WRITE"

    class NonStringCodeError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("write failed")
            self.code = 123

    string_code_update = writer._build_failure_update(
        workspace_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        exc=StringCodeError(),
    )
    non_string_code_update = writer._build_failure_update(
        workspace_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        projection_type=ProjectionArtifactType.RESUME_MD,
        target_path=".agent/resume.md",
        exc=NonStringCodeError(),
    )

    assert string_code_update.error_code == "E_WRITE"
    assert non_string_code_update.error_code is None


def test_projection_writer_build_resume_json_covers_optional_none_fields() -> None:
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=uuid4(),
            repo_url="https://example.com/repo.git",
            canonical_path="/tmp/workspace",
            default_branch="main",
            metadata={},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="JSON-1",
            status=SimpleNamespace(value="running"),
            metadata={},
        ),
        attempt=None,
        latest_checkpoint=None,
        latest_verify_report=None,
        projections=(
            SimpleNamespace(
                projection_type=SimpleNamespace(value="resume_json"),
                status=SimpleNamespace(value="fresh"),
                target_path=".agent/resume.json",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=0,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        next_hint=None,
        warnings=(),
    )

    payload = json.loads(writer._build_resume_json(resume))

    assert payload["attempt"] is None
    assert payload["latest_checkpoint"] is None
    assert payload["latest_verify_report"] is None
    assert payload["projections"] == [
        {
            "projection_type": "resume_json",
            "status": "fresh",
            "target_path": ".agent/resume.json",
            "last_successful_write_at": None,
            "last_canonical_update_at": None,
            "open_failure_count": 0,
        }
    ]
    assert payload["warnings"] == []
    assert payload["next_hint"] is None
