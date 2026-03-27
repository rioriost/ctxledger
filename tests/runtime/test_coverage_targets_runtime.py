from __future__ import annotations

import argparse
import signal
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.memory.service import MemoryServiceError
from ctxledger.runtime.database_health import (
    DefaultDatabaseHealthChecker,
    PostgresDatabaseHealthChecker,
    ServerBootstrapError,
    build_database_health_checker,
)
from ctxledger.runtime.http_runtime import HttpRuntimeAdapter, register_http_runtime_handlers
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
    _age_prototype_runtime_details,
    _workflow_resume_error_payload,
    build_runtime_introspection_response,
    build_runtime_routes_response,
    build_runtime_tools_response,
)
from ctxledger.runtime.status import build_health_status, build_readiness_status
from ctxledger.runtime.types import (
    McpResourceResponse,
    McpToolResponse,
    RuntimeIntrospectionResponse,
)
from ctxledger.server import CtxLedgerServer, create_server
from ctxledger.version import get_app_name, get_app_version
from ctxledger.workflow.service import WorkflowError

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

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
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

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
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

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    assert checker.schema_ready() is False


def test_build_database_health_checker_prefers_default_without_url() -> None:
    checker = build_database_health_checker(None)
    assert isinstance(checker, DefaultDatabaseHealthChecker)


def test_default_database_health_checker_age_methods_return_placeholder_values() -> None:
    checker = DefaultDatabaseHealthChecker("postgresql://example/db")

    assert checker.age_available() is False
    assert checker.age_graph_status("ctxledger_memory") == "unknown"


def test_postgres_database_health_checker_age_available_true_when_extension_loaded(
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

        def fetchone(self) -> tuple[bool]:
            return (True,)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    assert checker.age_available() is True
    assert executed == [
        ("LOAD 'age'", None),
        (
            "SELECT EXISTS (\n                            SELECT 1\n                            FROM pg_extension\n                            WHERE extname = 'age'\n                        )",
            None,
        ),
    ]


def test_postgres_database_health_checker_age_available_false_when_extension_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            return None

        def fetchone(self) -> tuple[bool]:
            return (False,)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    assert checker.age_available() is False


def test_postgres_database_health_checker_age_available_false_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            raise RuntimeError("age load failed")

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")

    assert checker.age_available() is False


def test_postgres_database_health_checker_age_graph_status_returns_age_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = PostgresDatabaseHealthChecker("postgresql://example/db")
    monkeypatch.setattr(checker, "age_available", lambda: False)

    assert checker.age_graph_status("ctxledger_memory") == "age_unavailable"


def test_postgres_database_health_checker_age_graph_status_returns_graph_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_rows: Iterator[tuple[bool]] = iter([(False,)])
    executed: list[tuple[str, object | None]] = []

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed.append((query.strip(), params))

        def fetchone(self) -> tuple[bool]:
            return next(fetch_rows)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")
    monkeypatch.setattr(checker, "age_available", lambda: True)

    assert checker.age_graph_status("ctxledger_memory") == "graph_unavailable"
    assert executed == [
        ("LOAD 'age'", None),
        ('SET search_path = ag_catalog, "$user", public', None),
        (
            "SELECT EXISTS (\n                            SELECT 1\n                            FROM ag_catalog.ag_graph\n                            WHERE name = %s\n                        )",
            ("ctxledger_memory",),
        ),
    ]


def test_postgres_database_health_checker_age_graph_status_returns_graph_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_rows: Iterator[tuple[bool] | tuple[object]] = iter([(True,), ("node",)])
    executed: list[tuple[str, object | None]] = []

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed.append((query.strip(), params))

        def fetchone(self) -> tuple[bool] | tuple[object]:
            return next(fetch_rows)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")
    monkeypatch.setattr(checker, "age_available", lambda: True)

    assert checker.age_graph_status("ctxledger_memory") == "graph_ready"
    assert executed[0] == ("LOAD 'age'", None)
    assert executed[1] == ('SET search_path = ag_catalog, "$user", public', None)
    assert executed[2] == (
        "SELECT EXISTS (\n                            SELECT 1\n                            FROM ag_catalog.ag_graph\n                            WHERE name = %s\n                        )",
        ("ctxledger_memory",),
    )
    assert "FROM cypher(" in executed[3][0]


def test_postgres_database_health_checker_age_graph_status_returns_unknown_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            raise RuntimeError("graph query failed")

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    fake_psycopg = types.SimpleNamespace(connect=lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    checker = PostgresDatabaseHealthChecker("postgresql://example/db")
    monkeypatch.setattr(checker, "age_available", lambda: True)

    assert checker.age_graph_status("ctxledger_memory") == "unknown"


def test_build_database_health_checker_prefers_default_when_psycopg_missing(
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
            raise ImportError("missing driver")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    checker = build_database_health_checker("postgresql://example/db")

    assert isinstance(checker, DefaultDatabaseHealthChecker)


def test_build_database_health_checker_prefers_postgres_when_psycopg_present(
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
            return types.SimpleNamespace()
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    checker = build_database_health_checker("postgresql://example/db")

    assert isinstance(checker, PostgresDatabaseHealthChecker)


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

    created = create_runtime(settings, server="server-ref", http_runtime_builder=builder)

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
    assert "ctxledger 0.9.0 started" in captured.err
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
        "version": "0.9.0",
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
        db_health_checker=FailingDbChecker(schema_error=RuntimeError("schema lookup failed")),
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


def test_http_runtime_extract_interaction_scope_ids_reads_nested_payloads() -> None:
    runtime = HttpRuntimeAdapter(make_settings())

    workspace_id, workflow_instance_id = runtime._extract_interaction_scope_ids(
        arguments={},
        response_payload={
            "resource": {
                "workspace": {"workspace_id": "workspace-nested"},
                "workflow": {"workflow_instance_id": "workflow-nested"},
            }
        },
    )

    assert workspace_id == "workspace-nested"
    assert workflow_instance_id == "workflow-nested"


def test_http_runtime_extract_interaction_scope_ids_prefers_arguments_and_selection() -> None:
    runtime = HttpRuntimeAdapter(make_settings())

    workspace_id, workflow_instance_id = runtime._extract_interaction_scope_ids(
        arguments={"workspace_id": "workspace-arg"},
        response_payload={
            "selection": {"selected_workflow_instance_id": "workflow-selected"},
            "workspace": {"workspace_id": "workspace-response"},
        },
    )

    assert workspace_id == "workspace-arg"
    assert workflow_instance_id == "workflow-selected"


def test_http_runtime_persist_interaction_event_pair_returns_without_server() -> None:
    runtime = HttpRuntimeAdapter(make_settings(), server=None)

    runtime._persist_interaction_event_pair(
        request_content="request",
        request_metadata={"kind": "request"},
        response_content="response",
        response_metadata={"kind": "response"},
    )


def test_http_runtime_persist_interaction_event_pair_returns_when_persist_not_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = make_server(runtime=None)
    runtime = HttpRuntimeAdapter(make_settings(), server=server)

    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_workflow_backed_memory_service",
        lambda _server: SimpleNamespace(persist_interaction_memory=None),
    )

    runtime._persist_interaction_event_pair(
        request_content="request",
        request_metadata={"kind": "request"},
        response_content="response",
        response_metadata={"kind": "response"},
    )


def test_http_runtime_persist_interaction_event_pair_swallows_memory_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = make_server(runtime=None)
    runtime = HttpRuntimeAdapter(make_settings(), server=server)

    def persist_interaction_memory(**_: object) -> None:
        raise MemoryServiceError(
            code="memory_invalid_request",
            message="persist failed",
            feature="memory_remember_episode",
            details={},
        )

    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_workflow_backed_memory_service",
        lambda _server: SimpleNamespace(persist_interaction_memory=persist_interaction_memory),
    )

    runtime._persist_interaction_event_pair(
        request_content="request",
        request_metadata={"kind": "request"},
        response_content="response",
        response_metadata={"kind": "response"},
        workspace_id="workspace-1",
        workflow_instance_id="workflow-1",
    )


def test_http_runtime_dispatch_resource_returns_not_found_for_unknown_uri() -> None:
    runtime = HttpRuntimeAdapter(make_settings(), server=make_server(runtime=None))

    response = runtime.dispatch_resource("workspace://missing/resource")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "resource_not_found",
            "message": "unknown MCP resource 'workspace://missing/resource'",
        }
    }


def test_http_runtime_dispatch_tool_returns_not_found_for_unknown_tool() -> None:
    runtime = HttpRuntimeAdapter(make_settings(), server=make_server(runtime=None))

    response = runtime.dispatch_tool("missing_tool", {})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "tool_not_found",
            "message": "unknown MCP tool 'missing_tool'",
            "details": {},
        },
    }


def test_http_runtime_dispatch_uses_mcp_handler_for_rpc_route() -> None:
    runtime = HttpRuntimeAdapter(make_settings())
    expected = SimpleNamespace(status_code=200, payload={"ok": True}, headers={})

    runtime.register_handler("mcp_rpc", lambda path, body: (path, body, expected)[2])

    response = runtime.dispatch("mcp_rpc", "/mcp", body='{"jsonrpc":"2.0"}')

    assert response is expected


def test_http_runtime_dispatch_uses_simple_handler_for_non_rpc_route() -> None:
    runtime = HttpRuntimeAdapter(make_settings())
    expected = SimpleNamespace(status_code=200, payload={"ok": True}, headers={})

    runtime.register_handler("workflow_resume", lambda path: (path, expected)[1])

    response = runtime.dispatch("workflow_resume", "/resume")

    assert response is expected


def test_http_runtime_dispatch_returns_not_found_when_route_missing() -> None:
    runtime = HttpRuntimeAdapter(make_settings())

    response = runtime.dispatch("missing_route", "/missing")

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "route_not_found",
            "message": "no HTTP handler is registered for route 'missing_route'",
        }
    }


def test_http_runtime_stop_returns_early_when_not_started(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = HttpRuntimeAdapter(make_settings())

    with caplog.at_level("INFO"):
        runtime.stop()

    assert "HTTP runtime adapter stopping" not in caplog.text


def test_register_http_runtime_handlers_skips_debug_routes_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = HttpRuntimeAdapter(make_settings())
    server = make_server(runtime=None)
    server.settings = types.SimpleNamespace(debug=types.SimpleNamespace(enabled=False))

    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_mcp_http_handler",
        lambda _runtime, _server: "mcp-handler",
    )
    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_runtime_introspection_http_handler",
        lambda _server: "introspection-handler",
    )
    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_runtime_routes_http_handler",
        lambda _server: "routes-handler",
    )
    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_runtime_tools_http_handler",
        lambda _server: "tools-handler",
    )
    monkeypatch.setattr(
        "ctxledger.runtime.http_runtime.build_workflow_resume_http_handler",
        lambda _server: "resume-handler",
    )

    registered = register_http_runtime_handlers(runtime, server)

    assert registered is runtime
    assert runtime.handler("mcp_rpc") == "mcp-handler"
    assert runtime.handler("workflow_resume") == "resume-handler"
    assert runtime.handler("runtime_introspection") is None
    assert runtime.handler("runtime_routes") is None
    assert runtime.handler("runtime_tools") is None


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
        ],
        "age_prototype": {
            "age_enabled": False,
            "age_graph_name": "ctxledger_memory",
            "observability_routes": [
                "/debug/runtime",
                "/debug/routes",
                "/debug/tools",
            ],
            "summary_graph_mirroring": {
                "enabled": False,
                "canonical_source": [
                    "memory_summaries",
                    "memory_summary_memberships",
                ],
                "derived_graph_labels": [
                    "memory_summary",
                    "memory_item",
                    "summarizes",
                ],
                "relation_type": "summarizes",
                "selection_route": "graph_summary_auxiliary",
                "explainability_scope": "readiness",
                "refresh_command": "ctxledger refresh-age-summary-graph",
                "read_path_scope": "narrow_auxiliary_summary_member_traversal",
                "readiness_state": "unknown",
                "stale": False,
                "degraded": False,
                "operator_action": "inspect_age_graph_readiness",
                "graph_status": "unknown",
                "ready": False,
            },
            "workflow_summary_automation": {
                "orchestration_point": "workflow_completion_auto_memory",
                "default_requested": False,
                "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
                "trigger": "latest_checkpoint.build_episode_summary_true",
                "target_scope": "workflow_completion_auto_memory_episode",
                "summary_kind": "episode_summary",
                "replace_existing": True,
                "non_fatal": True,
            },
            "age_graph_status": "unknown",
        },
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
    assert captured.out.strip() == get_app_version()


def test_cli_print_missing_database_url_with_and_without_override_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli_module._print_missing_database_url() == 1
    assert cli_module._print_missing_database_url(include_override_hint=True) == 1

    captured = capsys.readouterr()
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err
    assert (
        "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        in captured.err
    )


def test_cli_age_graph_readiness_returns_missing_database_url_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        in captured.err
    )


def test_cli_age_graph_readiness_requires_graph_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()
    settings = settings.__class__(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        database=settings.database.__class__(
            url=settings.database.url,
            connect_timeout_seconds=settings.database.connect_timeout_seconds,
            statement_timeout_ms=settings.database.statement_timeout_ms,
            schema_name=settings.database.schema_name,
            pool_min_size=settings.database.pool_min_size,
            pool_max_size=settings.database.pool_max_size,
            pool_timeout_seconds=settings.database.pool_timeout_seconds,
            age_enabled=settings.database.age_enabled,
            age_graph_name="",
        ),
        http=settings.http,
        debug=settings.debug,
        logging=settings.logging,
        embedding=settings.embedding,
    )
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "AGE graph name is required. Set CTXLEDGER_DB_AGE_GRAPH_NAME or pass --graph-name."
        in captured.err
    )


def test_cli_age_graph_readiness_prints_status_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakePostgresConfig:
        def __init__(
            self,
            *,
            database_url: str,
            connect_timeout_seconds: int,
            statement_timeout_ms: int | None,
            schema_name: str,
            pool_min_size: int,
            pool_max_size: int,
            pool_timeout_seconds: int,
            age_enabled: bool,
            age_graph_name: str,
        ) -> None:
            self.database_url = database_url
            self.age_enabled = age_enabled
            self.age_graph_name = age_graph_name

    class FakeChecker:
        def __init__(self, config: object) -> None:
            self.config = config

        def age_graph_status(self, graph_name: str) -> str:
            assert graph_name == "ctxledger_memory"
            return "graph_ready"

        def age_available(self) -> bool:
            return True

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresDatabaseHealthChecker", FakeChecker)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.strip() == (
        '{"age_enabled": false, "age_graph_name": "ctxledger_memory", '
        '"age_available": true, "age_graph_status": "graph_ready", '
        '"summary_graph_mirroring": {"enabled": false, "canonical_source": ["memory_summaries", '
        '"memory_summary_memberships"], "derived_graph_labels": ["memory_summary", "memory_item", '
        '"summarizes"], "relation_type": "summarizes", "selection_route": "graph_summary_auxiliary", '
        '"explainability_scope": "readiness", "refresh_command": "ctxledger refresh-age-summary-graph", '
        '"read_path_scope": "narrow_auxiliary_summary_member_traversal", "readiness_state": "ready", '
        '"stale": false, "degraded": false, "operator_action": "no_action_required", '
        '"age_available": true, "graph_status": "graph_ready", "ready": true}, '
        '"workflow_summary_automation": {"orchestration_point": "workflow_completion_auto_memory", '
        '"default_requested": false, "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary", '
        '"trigger": "latest_checkpoint.build_episode_summary_true", "target_scope": '
        '"workflow_completion_auto_memory_episode", "summary_kind": "episode_summary", '
        '"replace_existing": true, "non_fatal": true}}'
    )


def test_cli_age_graph_readiness_returns_failure_on_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakePostgresConfig:
        def __init__(
            self,
            *,
            database_url: str,
            connect_timeout_seconds: int,
            statement_timeout_ms: int | None,
            schema_name: str,
            pool_min_size: int,
            pool_max_size: int,
            pool_timeout_seconds: int,
            age_enabled: bool,
            age_graph_name: str,
        ) -> None:
            return None

    class FakeChecker:
        def __init__(self, config: object) -> None:
            raise RuntimeError("health checker init failed")

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresDatabaseHealthChecker", FakeChecker)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failed to check AGE graph readiness: health checker init failed" in captured.err


def test_age_prototype_runtime_details_records_age_available_error() -> None:
    class FailingAgeAvailableChecker:
        def age_available(self) -> bool:
            raise RuntimeError("age unavailable check failed")

    server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FailingAgeAvailableChecker(),
        runtime=None,
    )

    details = _age_prototype_runtime_details(server)

    assert details == {
        "age_enabled": False,
        "age_graph_name": "ctxledger_memory",
        "observability_routes": [
            "/debug/runtime",
            "/debug/routes",
            "/debug/tools",
        ],
        "summary_graph_mirroring": {
            "enabled": False,
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "relation_type": "summarizes",
            "selection_route": "graph_summary_auxiliary",
            "explainability_scope": "readiness",
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
            "readiness_state": "unknown",
            "stale": False,
            "degraded": False,
            "operator_action": "inspect_age_graph_readiness",
            "age_available_error": "age unavailable check failed",
            "graph_status": "unknown",
            "ready": False,
        },
        "workflow_summary_automation": {
            "orchestration_point": "workflow_completion_auto_memory",
            "default_requested": False,
            "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
            "trigger": "latest_checkpoint.build_episode_summary_true",
            "target_scope": "workflow_completion_auto_memory_episode",
            "summary_kind": "episode_summary",
            "replace_existing": True,
            "non_fatal": True,
        },
        "age_available_error": "age unavailable check failed",
        "age_graph_status": "unknown",
    }


def test_age_prototype_runtime_details_records_age_graph_status_error() -> None:
    class FailingAgeGraphStatusChecker:
        def age_available(self) -> bool:
            return True

        def age_graph_status(self, graph_name: str) -> str:
            assert graph_name == "ctxledger_memory"
            raise RuntimeError("graph status failed")

    server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FailingAgeGraphStatusChecker(),
        runtime=None,
    )

    details = _age_prototype_runtime_details(server)

    assert details == {
        "age_enabled": False,
        "age_graph_name": "ctxledger_memory",
        "observability_routes": [
            "/debug/runtime",
            "/debug/routes",
            "/debug/tools",
        ],
        "summary_graph_mirroring": {
            "enabled": False,
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "relation_type": "summarizes",
            "selection_route": "graph_summary_auxiliary",
            "explainability_scope": "readiness",
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
            "readiness_state": "unknown",
            "stale": False,
            "degraded": False,
            "operator_action": "inspect_age_graph_readiness",
            "age_available": True,
            "graph_status_error": "graph status failed",
            "graph_status": "unknown",
            "ready": False,
        },
        "workflow_summary_automation": {
            "orchestration_point": "workflow_completion_auto_memory",
            "default_requested": False,
            "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
            "trigger": "latest_checkpoint.build_episode_summary_true",
            "target_scope": "workflow_completion_auto_memory_episode",
            "summary_kind": "episode_summary",
            "replace_existing": True,
            "non_fatal": True,
        },
        "age_available": True,
        "age_graph_status_error": "graph status failed",
        "age_graph_status": "unknown",
    }


def test_age_prototype_runtime_details_records_age_graph_available_error() -> None:
    class FailingAgeGraphAvailableChecker:
        def age_available(self) -> bool:
            return True

        def age_graph_available(self, graph_name: str) -> bool:
            assert graph_name == "ctxledger_memory"
            raise RuntimeError("graph availability failed")

    server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FailingAgeGraphAvailableChecker(),
        runtime=None,
    )

    details = _age_prototype_runtime_details(server)

    assert details == {
        "age_enabled": False,
        "age_graph_name": "ctxledger_memory",
        "observability_routes": [
            "/debug/runtime",
            "/debug/routes",
            "/debug/tools",
        ],
        "summary_graph_mirroring": {
            "enabled": False,
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "relation_type": "summarizes",
            "selection_route": "graph_summary_auxiliary",
            "explainability_scope": "readiness",
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
            "readiness_state": "unknown",
            "stale": False,
            "degraded": False,
            "operator_action": "inspect_age_graph_readiness",
            "age_available": True,
            "graph_available_error": "graph availability failed",
            "graph_status": "unknown",
            "ready": False,
        },
        "workflow_summary_automation": {
            "orchestration_point": "workflow_completion_auto_memory",
            "default_requested": False,
            "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
            "trigger": "latest_checkpoint.build_episode_summary_true",
            "target_scope": "workflow_completion_auto_memory_episode",
            "summary_kind": "episode_summary",
            "replace_existing": True,
            "non_fatal": True,
        },
        "age_available": True,
        "age_graph_available_error": "graph availability failed",
        "age_graph_status": "unknown",
    }


def test_workflow_resume_error_payload_maps_not_found_codes() -> None:
    workflow_instance_id = uuid4()

    class NotFoundWorkflowError(WorkflowError):
        code = "not_found"

        def __init__(self) -> None:
            super().__init__("missing workflow", details={})

    status_code, code, message, details = _workflow_resume_error_payload(
        NotFoundWorkflowError(),
        workflow_instance_id=workflow_instance_id,
    )

    assert (status_code, code, message) == (404, "not_found", "missing workflow")
    assert details == {"workflow_instance_id": str(workflow_instance_id)}


def test_workflow_resume_error_payload_maps_validation_errors() -> None:
    workflow_instance_id = uuid4()

    class ValidationWorkflowError(WorkflowError):
        code = "validation_error"

        def __init__(self) -> None:
            super().__init__("bad request", details={"field": "workflow_instance_id"})

    status_code, code, message, details = _workflow_resume_error_payload(
        ValidationWorkflowError(),
        workflow_instance_id=workflow_instance_id,
    )

    assert (status_code, code, message) == (400, "invalid_request", "bad request")
    assert details == {"field": "workflow_instance_id"}


def test_workflow_resume_error_payload_maps_unknown_errors_to_server_error() -> None:
    workflow_instance_id = uuid4()

    class UnknownWorkflowError(WorkflowError):
        code = "unexpected_failure"

        def __init__(self) -> None:
            super().__init__("resume failed", details={"reason": "boom"})

    status_code, code, message, details = _workflow_resume_error_payload(
        UnknownWorkflowError(),
        workflow_instance_id=workflow_instance_id,
    )

    assert (status_code, code, message) == (500, "server_error", "resume failed")
    assert details == {"reason": "boom"}


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
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings(database_url=""))

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

    exit_code = cli_module._apply_schema(argparse.Namespace(database_url="postgresql://example/db"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failed to import PostgreSQL driver. Install psycopg[binary] first." in captured.err


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

    monkeypatch.setattr("ctxledger.runtime.orchestration.get_settings", lambda: settings)
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        lambda settings, **kwargs: settings,
    )
    monkeypatch.setattr("ctxledger.server.create_server", lambda _settings: fake_server)

    exit_code = run_server()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert fake_server.startup_calls == 1
    assert "ctxledger 0.9.0 started" in captured.err


def test_run_server_returns_one_for_bootstrap_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakeServer:
        def startup(self) -> None:
            raise ServerBootstrapError("database schema is not ready")

    monkeypatch.setattr("ctxledger.runtime.orchestration.get_settings", lambda: settings)
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        lambda settings, **kwargs: settings,
    )
    monkeypatch.setattr("ctxledger.server.create_server", lambda _settings: FakeServer())

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

    monkeypatch.setattr("ctxledger.runtime.orchestration.get_settings", lambda: settings)
    monkeypatch.setattr(
        "ctxledger.runtime.orchestration.apply_overrides",
        lambda settings, **kwargs: settings,
    )
    monkeypatch.setattr("ctxledger.server.create_server", lambda _settings: FakeServer())

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


def test_build_workflow_service_factory_builds_connection_pool_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, settings):
            captured["settings"] = settings
            return "postgres-config"

    def fake_build_connection_pool(config: object) -> object:
        captured["connection_pool_config"] = config
        return "BUILT-POOL"

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
        "ctxledger.runtime.server_factory.build_connection_pool",
        fake_build_connection_pool,
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
    factory = build_workflow_service_factory(settings, connection_pool=None)

    assert factory is not None
    service = factory()

    assert captured["settings"] is settings
    assert captured["connection_pool_config"] == "postgres-config"
    assert captured["config"] == "postgres-config"
    assert captured["pool"] == "BUILT-POOL"
    assert isinstance(service, FakeWorkflowService)
    assert callable(service.uow_factory)
    assert service.uow_factory() == "uow"


def test_build_workflow_service_factory_prefers_factory_connection_pool_over_built_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, settings):
            captured["settings"] = settings
            return "postgres-config"

    def fake_build_connection_pool(config: object) -> object:
        captured["built_pool_config"] = config
        return "BUILT-POOL"

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
        "ctxledger.runtime.server_factory.build_connection_pool",
        fake_build_connection_pool,
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
    factory = build_workflow_service_factory(settings, connection_pool="FACTORY-POOL")

    assert factory is not None
    service = factory()

    assert captured["settings"] is settings
    assert "built_pool_config" not in captured
    assert captured["config"] == "postgres-config"
    assert captured["pool"] == "FACTORY-POOL"
    assert isinstance(service, FakeWorkflowService)
    assert callable(service.uow_factory)
    assert service.uow_factory() == "uow"


def test_build_workflow_service_factory_prefers_call_time_connection_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, settings):
            captured["settings"] = settings
            return "postgres-config"

    def fake_build_connection_pool(config: object) -> object:
        captured["built_pool_config"] = config
        return "BUILT-POOL"

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
        "ctxledger.runtime.server_factory.build_connection_pool",
        fake_build_connection_pool,
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
    factory = build_workflow_service_factory(settings, connection_pool="FACTORY-POOL")

    assert factory is not None
    service = factory(connection_pool="CALL-POOL")

    assert captured["settings"] is settings
    assert "built_pool_config" not in captured
    assert captured["config"] == "postgres-config"
    assert captured["pool"] == "CALL-POOL"
    assert isinstance(service, FakeWorkflowService)
    assert callable(service.uow_factory)
    assert service.uow_factory() == "uow"


def test_build_workflow_service_factory_uses_uow_memory_backing_when_uow_is_provided(
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

    class FakeWorkflowMemoryBridge:
        def __init__(
            self,
            *,
            episode_repository: object,
            memory_item_repository: object,
            memory_embedding_repository: object,
            memory_relation_repository: object,
            summary_builder: object | None = None,
        ) -> None:
            self.episode_repository = episode_repository
            self.memory_item_repository = memory_item_repository
            self.memory_embedding_repository = memory_embedding_repository
            self.memory_relation_repository = memory_relation_repository
            self.summary_builder = summary_builder

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
        "ctxledger.runtime.server_factory.WorkflowMemoryBridge",
        FakeWorkflowMemoryBridge,
    )
    monkeypatch.setattr(
        "ctxledger.runtime.server_factory.WorkflowService",
        FakeWorkflowService,
    )

    fake_uow = SimpleNamespace(
        memory_episodes="EPISODES",
        memory_items="ITEMS",
        memory_embeddings="EMBEDDINGS",
        memory_relations="RELATIONS",
    )

    settings = make_settings()
    factory = build_workflow_service_factory(settings, connection_pool="POOL")

    assert factory is not None
    service = factory(uow=fake_uow)

    bridge = service.kwargs["workflow_memory_bridge"]
    assert bridge.episode_repository == "EPISODES"
    assert bridge.memory_item_repository == "ITEMS"
    assert bridge.memory_embedding_repository == "EMBEDDINGS"
    assert bridge.memory_relation_repository == "RELATIONS"
    assert captured["settings"] is settings
    assert captured["config"] == "postgres-config"
    assert captured["pool"] == "POOL"


def test_create_server_uses_provided_runtime_and_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    sentinel_factory = object()
    sentinel_runtime = object()

    build_factory_calls: list[object] = []
    build_runtime_calls: list[object] = []

    monkeypatch.setattr(
        "ctxledger.server.build_workflow_service_factory",
        lambda received_settings: build_factory_calls.append(received_settings) or "BUILT-FACTORY",
    )
    monkeypatch.setattr(
        "ctxledger.server.build_http_runtime_adapter",
        lambda server: build_runtime_calls.append(server) or "BUILT-RUNTIME",
    )

    server = create_server(
        settings,
        workflow_service_factory=sentinel_factory,
        runtime=sentinel_runtime,
    )

    assert isinstance(server, CtxLedgerServer)
    assert server.workflow_service_factory is sentinel_factory
    assert server.runtime is sentinel_runtime
    assert build_factory_calls == []
    assert build_runtime_calls == []


def test_create_server_builds_defaults_when_runtime_and_factory_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()

    build_factory_calls: list[object] = []
    build_runtime_calls: list[object] = []

    monkeypatch.setattr(
        "ctxledger.server.build_workflow_service_factory",
        lambda received_settings: build_factory_calls.append(received_settings) or "BUILT-FACTORY",
    )
    monkeypatch.setattr(
        "ctxledger.server.build_http_runtime_adapter",
        lambda server: build_runtime_calls.append(server) or "BUILT-RUNTIME",
    )

    server = create_server(settings)

    assert isinstance(server, CtxLedgerServer)
    assert server.workflow_service_factory == "BUILT-FACTORY"
    assert server.runtime == "BUILT-RUNTIME"
    assert build_factory_calls == [settings]
    assert build_runtime_calls == [server]


def test_version_helpers_read_name_and_raise_for_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyproject_text = """
[build-system]
requires = ["setuptools"]

[project]
name = "ctxledger"
version = "0.1.0"

[tool.pytest.ini_options]
addopts = "-q"
""".strip()

    class FakePath:
        def __init__(self, text: str) -> None:
            self._text = text

        def resolve(self) -> "FakePath":
            return self

        @property
        def parents(self) -> list["FakePath"]:
            return [self, self, self]

        def __truediv__(self, other: object) -> "FakePath":
            return self

        def read_text(self, encoding: str = "utf-8") -> str:
            assert encoding == "utf-8"
            return self._text

    monkeypatch.setattr(
        "ctxledger.version.Path", lambda *_args, **_kwargs: FakePath(pyproject_text)
    )

    assert get_app_name() == "ctxledger"
    assert get_app_version() == "0.1.0"

    missing_version_text = """
[project]
name = "ctxledger"
""".strip()
    monkeypatch.setattr(
        "ctxledger.version.Path",
        lambda *_args, **_kwargs: FakePath(missing_version_text),
    )

    with pytest.raises(
        RuntimeError,
        match="Could not determine ctxledger version from pyproject.toml",
    ):
        get_app_version()
