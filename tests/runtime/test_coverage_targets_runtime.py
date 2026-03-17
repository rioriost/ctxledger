from __future__ import annotations

import argparse
import signal
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import ctxledger.__init__ as cli_module
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
    build_runtime_introspection_response,
    build_runtime_routes_response,
    build_runtime_tools_response,
)
from ctxledger.runtime.status import build_health_status, build_readiness_status
from ctxledger.runtime.types import RuntimeIntrospectionResponse
from ctxledger.server import CtxLedgerServer

from ..support.coverage_targets_support import (
    FailingDbChecker,
    make_server,
    make_settings,
)


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
    assert len(executed) == 5
    assert [params for _, params in executed] == [
        ("workspaces",),
        ("workflow_instances",),
        ("workflow_attempts",),
        ("workflow_checkpoints",),
        ("verify_reports",),
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


def test_apply_overrides_applies_http_override_successfully() -> None:
    settings = make_settings(host="127.0.0.1", port=8443)

    overridden = apply_overrides(
        settings,
        transport="http",
        host="0.0.0.0",
        port=8443,
    )

    assert overridden is not settings
    assert overridden.http.host == "0.0.0.0"
    assert overridden.http.port == 8443
    assert overridden.http.path == settings.http.path


def test_run_server_passes_override_arguments_through_apply_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    fake_server = SimpleNamespace(
        startup=lambda: None,
        settings=settings,
        runtime=None,
        health=lambda: SimpleNamespace(status="ok"),
        readiness=lambda: SimpleNamespace(status="ready"),
    )
    override_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.get_settings",
        lambda: settings,
    )

    def fake_apply_overrides(
        received_settings: object,
        *,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        override_calls.append(
            {
                "settings": received_settings,
                "transport": transport,
                "host": host,
                "port": port,
            }
        )
        return settings

    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        fake_apply_overrides,
    )
    monkeypatch.setattr("ctxledger.server.create_server", lambda _settings: fake_server)
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.install_signal_handlers",
        lambda _server: None,
    )
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.print_runtime_summary",
        lambda _server: None,
    )

    exit_code = run_server(
        transport="http",
        host="0.0.0.0",
        port=9090,
    )

    assert exit_code == 0
    assert override_calls == [
        {
            "settings": settings,
            "transport": "http",
            "host": "0.0.0.0",
            "port": 9090,
        }
    ]


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


def test_install_signal_handlers_registered_handler_shuts_down_server_and_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered: dict[signal.Signals, object] = {}
    shutdown_calls: list[str] = []

    class FakeServer:
        def shutdown(self) -> None:
            shutdown_calls.append("shutdown")

    def fake_signal(sig: signal.Signals, handler: object) -> None:
        registered[sig] = handler

    monkeypatch.setattr(signal, "signal", fake_signal)

    install_signal_handlers(server=FakeServer())

    with pytest.raises(SystemExit, match="0"):
        registered[signal.SIGINT](int(signal.SIGINT), None)

    assert shutdown_calls == ["shutdown"]


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
    assert captured.out.strip() == "0.5.4"


def test_build_health_status_handles_missing_runtime() -> None:
    server = make_server(runtime=None)
    server.workflow_service = None
    server._started = False

    status = build_health_status(server)

    assert status.ok is True
    assert status.status == "ok"
    assert status.details["runtime"] == []
    assert status.details["workflow_service_initialized"] is False


def test_build_readiness_status_covers_not_started_database_unavailable_and_schema_not_ready() -> (
    None
):
    not_started_server = make_server(runtime=None)
    not_started_status = build_readiness_status(not_started_server)
    assert not_started_status.ready is False
    assert not_started_status.status == "not_started"

    database_unavailable_server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FailingDbChecker(ping_error=RuntimeError("db offline")),
        runtime=None,
    )
    database_unavailable_server._started = True
    database_unavailable_status = build_readiness_status(database_unavailable_server)
    assert database_unavailable_status.ready is False
    assert database_unavailable_status.status == "database_unavailable"
    assert database_unavailable_status.details["error"] == "db offline"

    schema_not_ready_server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FailingDbChecker(schema_ready_value=False),
        runtime=None,
    )
    schema_not_ready_server._started = True
    schema_not_ready_status = build_readiness_status(schema_not_ready_server)
    assert schema_not_ready_status.ready is False
    assert schema_not_ready_status.status == "schema_not_ready"


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
        def from_settings(cls, settings):
            captured["settings"] = settings
            return "postgres-config"

    def fake_build_postgres_uow_factory(
        config: object,
        *,
        pool: object | None = None,
    ):
        captured["config"] = config
        captured["pool"] = pool

        def _uow_factory():
            return "uow"

        return _uow_factory

    class FakeWorkflowService:
        def __init__(self, uow_factory, **kwargs: object) -> None:
            self.uow_factory = uow_factory
            self.kwargs = kwargs

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
    factory = build_workflow_service_factory(settings, connection_pool="POOL")

    assert factory is not None
    service = factory()

    assert captured["settings"] is settings
    assert captured["config"] == "postgres-config"
    assert captured["pool"] == "POOL"
    assert isinstance(service, FakeWorkflowService)
    assert callable(service.uow_factory)
    assert service.uow_factory() == "uow"
