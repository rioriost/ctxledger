from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import signal
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib import error as urllib_error
from uuid import UUID, uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.config import (
    AppSettings,
    DatabaseSettings,
    DebugSettings,
    EmbeddingProvider,
    EmbeddingSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    ProjectionSettings,
)
from ctxledger.memory.embeddings import (
    DisabledEmbeddingGenerator,
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
    ExternalAPIEmbeddingGenerator,
    LocalStubEmbeddingGenerator,
    build_embedding_generator,
    compute_content_hash,
)
from ctxledger.memory.service import (
    EpisodeRecord,
    GetContextResponse,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryService,
    MemoryServiceError,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)
from ctxledger.projection.writer import ProjectionWriteError, ResumeProjectionWriter
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
from ctxledger.runtime.serializers import (
    serialize_closed_projection_failures_history,
    serialize_get_context_response,
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
    serialize_search_memory_response,
    serialize_stub_response,
    serialize_workflow_resume,
)
from ctxledger.runtime.server_factory import build_workflow_service_factory
from ctxledger.runtime.server_responses import (
    build_closed_projection_failures_response,
    build_projection_failures_ignore_response,
    build_projection_failures_resolve_response,
    build_runtime_introspection_response,
    build_runtime_routes_response,
    build_runtime_tools_response,
    build_workflow_detail_resource_response,
    build_workflow_resume_response,
    build_workspace_resume_resource_response,
)
from ctxledger.runtime.status import build_health_status, build_readiness_status
from ctxledger.runtime.types import RuntimeIntrospectionResponse
from ctxledger.server import CtxLedgerServer
from ctxledger.workflow.service import (
    ProjectionArtifactType,
    ProjectionFailureInfo,
    ProjectionInfo,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    ResumableStatus,
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowResume,
    Workspace,
)


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
            schema_name="public",
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
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            model="local-stub-v1",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
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
        received_settings: AppSettings,
        *,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> AppSettings:
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


def test_runtime_introspection_and_tool_route_responses_handle_generic_error_mapping() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    ready_server = make_server()
    ready_server.workflow_service = SimpleNamespace(
        ignore_resume_projection_failures=lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("")
        ),
        resolve_resume_projection_failures=lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("")
        ),
    )

    ignore_response = build_projection_failures_ignore_response(
        ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
    )
    resolve_response = build_projection_failures_resolve_response(
        ready_server,
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
    )

    assert ignore_response.status_code == 500
    assert ignore_response.payload == {
        "error": {
            "code": "server_error",
            "message": "failed to ignore projection failures",
        }
    }
    assert ignore_response.headers == {"content-type": "application/json"}
    assert resolve_response.status_code == 500
    assert resolve_response.payload == {
        "error": {
            "code": "server_error",
            "message": "failed to resolve projection failures",
        }
    }
    assert resolve_response.headers == {"content-type": "application/json"}


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
    assert captured.out.strip() == "0.2.0"


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


def test_http_app_request_helpers_cover_missing_authorization_and_default_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)

    request = SimpleNamespace(
        headers={"authorization": "   "},
        query_params=SimpleNamespace(multi_items=lambda: [("x", "1")]),
        url=SimpleNamespace(path="/debug/runtime"),
    )

    assert http_app._authorization_query_value(request) is None
    assert http_app._query_items_with_authorization(request) == [("x", "1")]
    assert http_app._query_string_from_request(request) == "x=1"
    assert http_app._full_path_with_query(request) == "/debug/runtime?x=1"

    response = http_app._response_from_runtime_result(
        SimpleNamespace(
            payload={"ok": True},
            status_code=200,
            headers=None,
        )
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.body.decode("utf-8")) == {"ok": True}


def test_http_app_build_get_and_post_routes_return_server_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    server = make_server(runtime=None)

    def get_factory(_server: object):
        def handler(path: str) -> object:
            raise AssertionError("get handler should not be called")

        return handler

    def post_factory(_runtime: object, _server: object):
        def handler(path: str, body: str | None) -> object:
            raise AssertionError("post handler should not be called")

        return handler

    get_route = http_app._build_get_route(server, get_factory)
    post_route = http_app._build_post_route(server, post_factory)

    request = SimpleNamespace(
        headers={},
        query_params=SimpleNamespace(multi_items=lambda: []),
        url=SimpleNamespace(path="/mcp"),
        body=lambda: None,
    )

    get_response = asyncio.run(get_route(request))
    post_response = asyncio.run(post_route(request))

    assert get_response.status_code == 503
    assert post_response.status_code == 503
    assert json.loads(get_response.body.decode("utf-8")) == {
        "error": {
            "code": "server_not_ready",
            "message": "runtime is not initialized",
        }
    }
    assert json.loads(post_response.body.decode("utf-8")) == {
        "error": {
            "code": "server_not_ready",
            "message": "runtime is not initialized",
        }
    }


def test_http_handlers_parse_required_uuid_argument_success() -> None:
    from ctxledger.runtime.http_handlers import parse_required_uuid_argument

    value = uuid4()

    parsed = parse_required_uuid_argument({"workspace_id": str(value)}, "workspace_id")

    assert parsed == value


def test_http_handlers_parse_required_uuid_argument_rejects_missing_value() -> None:
    from ctxledger.runtime.http_handlers import parse_required_uuid_argument

    response = parse_required_uuid_argument({}, "workspace_id")

    assert response.payload["error"]["code"] == "invalid_request"
    assert (
        response.payload["error"]["message"]
        == "workspace_id must be a non-empty string"
    )


def test_http_handlers_parse_required_uuid_argument_rejects_invalid_uuid() -> None:
    from ctxledger.runtime.http_handlers import parse_required_uuid_argument

    response = parse_required_uuid_argument(
        {"workspace_id": "not-a-uuid"},
        "workspace_id",
    )

    assert response.payload["error"]["code"] == "invalid_request"
    assert response.payload["error"]["message"] == "workspace_id must be a valid UUID"


def test_http_handlers_parse_optional_projection_type_argument_success() -> None:
    from ctxledger.runtime.http_handlers import (
        parse_optional_projection_type_argument,
    )

    parsed = parse_optional_projection_type_argument({"projection_type": "resume_json"})

    assert parsed == ProjectionArtifactType.RESUME_JSON


def test_http_handlers_parse_optional_projection_type_argument_rejects_blank_value() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        parse_optional_projection_type_argument,
    )

    response = parse_optional_projection_type_argument({"projection_type": "   "})

    assert response.payload["error"]["code"] == "invalid_request"
    assert (
        response.payload["error"]["message"]
        == "projection_type must be a non-empty string when provided"
    )


def test_http_handlers_parse_optional_projection_type_argument_rejects_unknown_value() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        parse_optional_projection_type_argument,
    )

    response = parse_optional_projection_type_argument({"projection_type": "unknown"})

    assert response.payload["error"]["code"] == "invalid_request"
    assert (
        response.payload["error"]["message"]
        == "projection_type must be a supported projection artifact type"
    )
    assert response.payload["error"]["details"]["allowed_values"] == [
        "resume_json",
        "resume_md",
    ]


def test_http_handlers_parse_request_paths_cover_success_and_invalid_cases() -> None:
    from ctxledger.runtime.http_handlers import (
        parse_closed_projection_failures_request_path,
        parse_workflow_resume_request_path,
    )

    workflow_instance_id = uuid4()

    assert (
        parse_workflow_resume_request_path(
            f"/workflow-resume/{workflow_instance_id}?x=1"
        )
        == workflow_instance_id
    )
    assert parse_workflow_resume_request_path("/workflow-resume/not-a-uuid") is None
    assert parse_workflow_resume_request_path("/wrong/path") is None

    assert (
        parse_closed_projection_failures_request_path(
            f"/workflow-resume/{workflow_instance_id}/closed-projection-failures?x=1"
        )
        == workflow_instance_id
    )
    assert (
        parse_closed_projection_failures_request_path(
            "/workflow-resume/not-a-uuid/closed-projection-failures"
        )
        is None
    )
    assert (
        parse_closed_projection_failures_request_path(
            f"/workflow-resume/{workflow_instance_id}/wrong"
        )
        is None
    )


def test_http_handlers_build_workflow_resume_http_handler_returns_404_for_invalid_path() -> (
    None
):
    from ctxledger.runtime.http_handlers import build_workflow_resume_http_handler

    response = build_workflow_resume_http_handler(make_server())("/wrong/path")

    assert response.status_code == 404
    assert response.payload["error"]["code"] == "not_found"


def test_http_handlers_build_closed_projection_failures_http_handler_returns_404_for_invalid_path() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        build_closed_projection_failures_http_handler,
    )

    response = build_closed_projection_failures_http_handler(make_server())(
        "/wrong/path"
    )

    assert response.status_code == 404
    assert response.payload["error"]["code"] == "not_found"


def test_http_handlers_build_projection_failures_ignore_http_handler_covers_not_found_and_validation() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        build_projection_failures_ignore_http_handler,
    )

    handler = build_projection_failures_ignore_http_handler(make_server())

    not_found = handler("/wrong/path")
    missing_workspace = handler("/projection_failures_ignore")
    invalid_projection_type = handler(
        f"/projection_failures_ignore?workspace_id={uuid4()}&workflow_instance_id={uuid4()}&projection_type=unknown"
    )

    assert not_found.status_code == 404
    assert missing_workspace.status_code == 400
    assert invalid_projection_type.status_code == 400
    assert (
        invalid_projection_type.payload["error"]["details"]["field"]
        == "projection_type"
    )


def test_http_handlers_build_projection_failures_resolve_http_handler_covers_not_found_and_validation() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        build_projection_failures_resolve_http_handler,
    )

    handler = build_projection_failures_resolve_http_handler(make_server())

    not_found = handler("/wrong/path")
    missing_workflow = handler(f"/projection_failures_resolve?workspace_id={uuid4()}")
    invalid_projection_type = handler(
        f"/projection_failures_resolve?workspace_id={uuid4()}&workflow_instance_id={uuid4()}&projection_type=unknown"
    )

    assert not_found.status_code == 404
    assert missing_workflow.status_code == 400
    assert invalid_projection_type.status_code == 400
    assert (
        invalid_projection_type.payload["error"]["details"]["field"]
        == "projection_type"
    )


def test_http_handlers_build_runtime_debug_handlers_return_404_for_wrong_paths() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        build_runtime_introspection_http_handler,
        build_runtime_routes_http_handler,
        build_runtime_tools_http_handler,
    )

    server = make_server()

    assert build_runtime_introspection_http_handler(server)("/wrong").status_code == 404
    assert build_runtime_routes_http_handler(server)("/wrong").status_code == 404
    assert build_runtime_tools_http_handler(server)("/wrong").status_code == 404


def test_http_handlers_parse_projection_type_accepts_missing_value() -> None:
    from ctxledger.runtime.http_handlers import (
        parse_optional_projection_type_argument,
    )

    parsed = parse_optional_projection_type_argument({})

    assert parsed is None


def test_http_handlers_build_projection_failure_http_handlers_accept_valid_projection_type() -> (
    None
):
    from ctxledger.runtime.http_handlers import (
        build_projection_failures_ignore_http_handler,
        build_projection_failures_resolve_http_handler,
    )

    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    ignore_server = make_server()
    ignore_server.workflow_service = SimpleNamespace(
        ignore_resume_projection_failures=lambda **kwargs: 3
    )
    resolve_server = make_server()
    resolve_server.workflow_service = SimpleNamespace(
        resolve_resume_projection_failures=lambda **kwargs: 4
    )

    ignore_response = build_projection_failures_ignore_http_handler(ignore_server)(
        f"/projection_failures_ignore?workspace_id={workspace_id}&workflow_instance_id={workflow_instance_id}&projection_type=resume_json"
    )
    resolve_response = build_projection_failures_resolve_http_handler(resolve_server)(
        f"/projection_failures_resolve?workspace_id={workspace_id}&workflow_instance_id={workflow_instance_id}&projection_type=resume_md"
    )

    assert ignore_response.status_code == 200
    assert ignore_response.payload == {
        "workspace_id": str(workspace_id),
        "workflow_instance_id": str(workflow_instance_id),
        "projection_type": "resume_json",
        "updated_failure_count": 3,
        "status": "ignored",
    }
    assert resolve_response.status_code == 200
    assert resolve_response.payload == {
        "workspace_id": str(workspace_id),
        "workflow_instance_id": str(workflow_instance_id),
        "projection_type": "resume_md",
        "updated_failure_count": 4,
        "status": "resolved",
    }


def test_http_handlers_build_runtime_debug_handlers_accept_query_string() -> None:
    from ctxledger.runtime.http_handlers import (
        build_runtime_introspection_http_handler,
        build_runtime_routes_http_handler,
        build_runtime_tools_http_handler,
    )

    runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=("workflow_resume",),
            resources=("workspace://{workspace_id}/resume",),
        )
    )
    server = make_server(runtime=runtime)

    introspection_response = build_runtime_introspection_http_handler(server)(
        "/debug/runtime?verbose=1"
    )
    routes_response = build_runtime_routes_http_handler(server)("/debug/routes?x=1")
    tools_response = build_runtime_tools_http_handler(server)("/debug/tools?x=1")

    assert introspection_response.status_code == 200
    assert introspection_response.payload == {
        "runtime": [
            {
                "transport": "http",
                "routes": ["workflow_resume"],
                "tools": ["workflow_resume"],
                "resources": ["workspace://{workspace_id}/resume"],
            }
        ]
    }
    assert routes_response.status_code == 200
    assert routes_response.payload == {
        "routes": [{"transport": "http", "routes": ["workflow_resume"]}]
    }
    assert tools_response.status_code == 200
    assert tools_response.payload == {
        "tools": [{"transport": "http", "tools": ["workflow_resume"]}]
    }


def test_http_handlers_build_mcp_http_handler_adapts_streamable_http_endpoint() -> None:
    from ctxledger.runtime.http_handlers import build_mcp_http_handler

    runtime = SimpleNamespace(
        settings=SimpleNamespace(app_name="ctxledger", app_version="0.1.0")
    )
    server = make_server(settings=make_settings(path="/mcp"))
    handler = build_mcp_http_handler(runtime, server)

    initialize_response = handler(
        "/mcp",
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        ),
    )
    invalid_json_response = handler("/mcp", "{invalid json")

    assert initialize_response.status_code == 200
    assert initialize_response.payload["result"]["protocolVersion"] == "2024-11-05"
    assert invalid_json_response.status_code == 400
    assert invalid_json_response.payload["error"]["code"] == "invalid_request"


def test_build_workflow_resume_response_returns_server_not_ready() -> None:
    workflow_instance_id = uuid4()
    server = make_server()

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_uses_default_string_when_bootstrap_error_has_no_message() -> (
    None
):
    workflow_instance_id = uuid4()
    server = make_server()

    class SilentBootstrapError(ServerBootstrapError):
        def __str__(self) -> str:
            return ""

    def raise_silent_bootstrap_error(_workflow_instance_id: object) -> object:
        return (_ for _ in ()).throw(SilentBootstrapError("silent"))

    server.get_workflow_resume = raise_silent_bootstrap_error

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_serializes_resume_payload() -> None:
    workflow_instance_id = uuid4()
    expected_payload = {"workflow_instance_id": str(workflow_instance_id), "ok": True}
    server = make_server()
    server.workflow_service = SimpleNamespace(
        resume_workflow=lambda data: SimpleNamespace(
            workflow_instance_id=data.workflow_instance_id
        )
    )

    import ctxledger.runtime.serializers as serializers_module

    original_serializer = serializers_module.serialize_workflow_resume

    def fake_serialize_workflow_resume(resume: object) -> dict[str, object]:
        assert getattr(resume, "workflow_instance_id") == workflow_instance_id
        return expected_payload

    serializers_module.serialize_workflow_resume = fake_serialize_workflow_resume
    try:
        response = build_workflow_resume_response(server, workflow_instance_id)
    finally:
        serializers_module.serialize_workflow_resume = original_serializer

    assert response.status_code == 200
    assert response.payload == expected_payload
    assert response.headers == {"content-type": "application/json"}


def test_build_closed_projection_failures_response_returns_server_not_ready() -> None:
    workflow_instance_id = uuid4()
    server = make_server()

    response = build_closed_projection_failures_response(server, workflow_instance_id)

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_closed_projection_failures_response_serializes_history() -> None:
    workflow_instance_id = uuid4()
    closed_failures = (SimpleNamespace(status="resolved"),)
    expected_payload = {
        "workflow_instance_id": str(workflow_instance_id),
        "history": [],
    }
    server = make_server()
    server.workflow_service = SimpleNamespace(
        resume_workflow=lambda data: SimpleNamespace(
            closed_projection_failures=closed_failures
        )
    )

    import ctxledger.runtime.serializers as serializers_module

    original_serializer = (
        serializers_module.serialize_closed_projection_failures_history
    )

    def fake_serialize_closed_projection_failures_history(
        current_workflow_instance_id: object,
        current_closed_failures: object,
    ) -> dict[str, object]:
        assert current_workflow_instance_id == workflow_instance_id
        assert current_closed_failures == closed_failures
        return expected_payload

    serializers_module.serialize_closed_projection_failures_history = (
        fake_serialize_closed_projection_failures_history
    )
    try:
        response = build_closed_projection_failures_response(
            server, workflow_instance_id
        )
    finally:
        serializers_module.serialize_closed_projection_failures_history = (
            original_serializer
        )

    assert response.status_code == 200
    assert response.payload == expected_payload
    assert response.headers == {"content-type": "application/json"}


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


def test_build_runtime_introspection_response_uses_empty_collection_when_runtime_missing() -> (
    None
):
    server = make_server(runtime=None)

    response = build_runtime_introspection_response(server)

    assert response.status_code == 200
    assert response.payload == {"runtime": []}
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


def test_build_workflow_detail_resource_response_uow_branch_returns_invalid_request_on_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda _workflow_instance_id: SimpleNamespace(
                    workflow_instance_id=workflow_instance_id,
                    workspace_id=other_workspace_id,
                )
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

    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow instance does not belong to workspace",
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


def test_in_memory_workspace_repository_update_replaces_canonical_path_index() -> None:
    from ctxledger.db import InMemoryWorkspaceRepository
    from ctxledger.workflow.service import Workspace

    workspace_id = uuid4()
    original = Workspace(
        workspace_id=workspace_id,
        repo_url="https://example.com/org/repo.git",
        canonical_path="/tmp/original",
        default_branch="main",
    )
    updated = Workspace(
        workspace_id=workspace_id,
        repo_url="https://example.com/org/repo.git",
        canonical_path="/tmp/updated",
        default_branch="main",
    )

    repo = InMemoryWorkspaceRepository({}, {})
    repo.create(original)
    repo.update(updated)

    assert repo.get_by_canonical_path("/tmp/original") is None
    assert repo.get_by_canonical_path("/tmp/updated") == updated


def test_in_memory_workflow_instance_repository_returns_latest_running_and_latest_updated() -> (
    None
):
    from datetime import UTC, datetime

    from ctxledger.db import InMemoryWorkflowInstanceRepository
    from ctxledger.workflow.service import WorkflowInstance, WorkflowInstanceStatus

    workspace_id = uuid4()
    older_running = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="A",
        status=WorkflowInstanceStatus.RUNNING,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    newer_running = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="B",
        status=WorkflowInstanceStatus.RUNNING,
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
        updated_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    latest_terminal = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="C",
        status=WorkflowInstanceStatus.COMPLETED,
        created_at=datetime(2024, 1, 4, tzinfo=UTC),
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )

    repo = InMemoryWorkflowInstanceRepository(
        {
            older_running.workflow_instance_id: older_running,
            newer_running.workflow_instance_id: newer_running,
            latest_terminal.workflow_instance_id: latest_terminal,
        }
    )

    assert repo.get_running_by_workspace_id(workspace_id) == newer_running
    assert repo.get_latest_by_workspace_id(workspace_id) == latest_terminal


def test_in_memory_workflow_attempt_repository_returns_running_latest_and_next_attempt_number() -> (
    None
):
    from datetime import UTC, datetime

    from ctxledger.db import InMemoryWorkflowAttemptRepository
    from ctxledger.workflow.service import WorkflowAttempt, WorkflowAttemptStatus

    workflow_instance_id = uuid4()
    first_running = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    latest_terminal = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_number=3,
        status=WorkflowAttemptStatus.SUCCEEDED,
        started_at=datetime(2024, 1, 3, tzinfo=UTC),
        finished_at=datetime(2024, 1, 3, tzinfo=UTC),
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
        updated_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    latest_running = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_number=2,
        status=WorkflowAttemptStatus.RUNNING,
        started_at=datetime(2024, 1, 4, tzinfo=UTC),
        created_at=datetime(2024, 1, 4, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, tzinfo=UTC),
    )

    repo = InMemoryWorkflowAttemptRepository(
        {
            first_running.attempt_id: first_running,
            latest_terminal.attempt_id: latest_terminal,
            latest_running.attempt_id: latest_running,
        }
    )

    assert repo.get_running_by_workflow_id(workflow_instance_id) == latest_running
    assert repo.get_latest_by_workflow_id(workflow_instance_id) == latest_terminal
    assert repo.get_next_attempt_number(workflow_instance_id) == 4
    assert repo.get_next_attempt_number(uuid4()) == 1


def test_in_memory_checkpoint_and_verify_report_repositories_return_latest_items() -> (
    None
):
    from datetime import UTC, datetime

    from ctxledger.db import (
        InMemoryVerifyReportRepository,
        InMemoryWorkflowCheckpointRepository,
    )
    from ctxledger.workflow.service import (
        VerifyReport,
        VerifyStatus,
        WorkflowCheckpoint,
    )

    workflow_instance_id = uuid4()
    attempt_id = uuid4()

    older_checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        step_name="older",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        step_name="latest",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    checkpoint_repo = InMemoryWorkflowCheckpointRepository(
        {
            older_checkpoint.checkpoint_id: older_checkpoint,
            latest_checkpoint.checkpoint_id: latest_checkpoint,
        }
    )

    older_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    latest_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.FAILED,
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    verify_repo = InMemoryVerifyReportRepository(
        {
            older_report.verify_id: older_report,
            latest_report.verify_id: latest_report,
        }
    )

    assert (
        checkpoint_repo.get_latest_by_workflow_id(workflow_instance_id)
        == latest_checkpoint
    )
    assert checkpoint_repo.get_latest_by_attempt_id(attempt_id) == latest_checkpoint
    assert verify_repo.get_latest_by_attempt_id(attempt_id) == latest_report


def test_in_memory_projection_state_repository_orders_and_records_projection_state() -> (
    None
):
    from datetime import UTC, datetime

    from ctxledger.db import InMemoryProjectionStateRepository
    from ctxledger.workflow.service import ProjectionInfo, ProjectionStatus

    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    key_json = (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_JSON)
    key_md = (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_MD)

    repo = InMemoryProjectionStateRepository(
        {
            key_json: ProjectionInfo(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
                last_successful_write_at=datetime(2024, 1, 2, tzinfo=UTC),
                last_canonical_update_at=datetime(2024, 1, 2, tzinfo=UTC),
                open_failure_count=1,
            ),
            key_md: ProjectionInfo(
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.STALE,
                target_path=".agent/resume.md",
                last_successful_write_at=datetime(2024, 1, 1, tzinfo=UTC),
                last_canonical_update_at=datetime(2024, 1, 1, tzinfo=UTC),
                open_failure_count=0,
            ),
        }
    )

    projections = repo.get_resume_projections(workspace_id, workflow_instance_id)
    assert [projection.projection_type for projection in projections] == [
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    ]

    repo.record_resume_projection(
        SimpleNamespace(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.MISSING,
            target_path=".agent/resume.json",
            last_successful_write_at=None,
            last_canonical_update_at=None,
        )
    )

    updated_projections = repo.get_resume_projections(
        workspace_id, workflow_instance_id
    )
    updated_projection = next(
        projection
        for projection in updated_projections
        if projection.projection_type == ProjectionArtifactType.RESUME_JSON
    )
    assert updated_projection.status == ProjectionStatus.MISSING
    assert updated_projection.open_failure_count == 1

    replacement = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.FRESH,
        target_path=".agent/new-resume.md",
        open_failure_count=0,
    )
    repo.set_resume_projection(workspace_id, workflow_instance_id, replacement)

    projections = repo.get_resume_projections(workspace_id, workflow_instance_id)
    assert any(
        projection.target_path == ".agent/new-resume.md" for projection in projections
    )


def test_in_memory_projection_failure_repository_records_open_and_closed_failures() -> (
    None
):
    from ctxledger.db import InMemoryProjectionFailureRepository
    from ctxledger.workflow.service import ProjectionInfo, ProjectionStatus

    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    key = (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_JSON)

    projection_states_by_key = {
        key: ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
            open_failure_count=0,
        )
    }
    repo = InMemoryProjectionFailureRepository({}, projection_states_by_key)

    recorded = repo.record_resume_projection_failure(
        SimpleNamespace(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="write failed",
            attempt_id=attempt_id,
            error_code="io_error",
        )
    )

    assert recorded.status == "open"
    assert recorded.open_failure_count == 1
    assert recorded.retry_count == 0
    assert (
        len(repo.get_open_failures_by_workflow_id(workspace_id, workflow_instance_id))
        == 1
    )
    assert projection_states_by_key[key].open_failure_count == 1

    resolved_count = repo.resolve_resume_projection_failures(
        workspace_id,
        workflow_instance_id,
        ProjectionArtifactType.RESUME_JSON,
    )
    assert resolved_count == 1
    assert (
        repo.get_open_failures_by_workflow_id(workspace_id, workflow_instance_id) == []
    )
    closed_failures = repo.get_closed_failures_by_workflow_id(
        workspace_id,
        workflow_instance_id,
    )
    assert len(closed_failures) == 1
    assert closed_failures[0].status == "resolved"
    assert projection_states_by_key[key].open_failure_count == 0


def test_in_memory_projection_failure_repository_ignore_and_multi_projection_paths() -> (
    None
):
    from ctxledger.db import InMemoryProjectionFailureRepository
    from ctxledger.workflow.service import ProjectionInfo, ProjectionStatus

    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    json_key = (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_JSON)
    md_key = (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_MD)

    projection_states_by_key = {
        json_key: ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
            open_failure_count=0,
        ),
        md_key: ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_MD,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.md",
            open_failure_count=0,
        ),
    }
    repo = InMemoryProjectionFailureRepository({}, projection_states_by_key)

    repo.record_resume_projection_failure(
        SimpleNamespace(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="json failed",
            attempt_id=None,
            error_code=None,
        )
    )
    repo.record_resume_projection_failure(
        SimpleNamespace(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="md failed",
            attempt_id=None,
            error_code=None,
        )
    )

    ignored_count = repo.ignore_resume_projection_failures(
        workspace_id,
        workflow_instance_id,
    )

    assert ignored_count == 2
    closed_failures = repo.get_closed_failures_by_workflow_id(
        workspace_id,
        workflow_instance_id,
    )
    assert {failure.status for failure in closed_failures} == {"ignored"}
    assert projection_states_by_key[json_key].open_failure_count == 0
    assert projection_states_by_key[md_key].open_failure_count == 0


def test_in_memory_unit_of_work_exit_commit_and_rollback_flags() -> None:
    from ctxledger.db import InMemoryUnitOfWork

    committed_uow = InMemoryUnitOfWork()
    with committed_uow as current_uow:
        current_uow.commit()

    assert committed_uow._committed is True
    assert committed_uow._rolled_back is False

    rolled_back_uow = InMemoryUnitOfWork()
    try:
        with rolled_back_uow:
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert rolled_back_uow._rolled_back is True


def test_in_memory_store_snapshot_and_factory_share_backing_store() -> None:
    from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
    from ctxledger.workflow.service import Workspace

    store = InMemoryStore.create()
    workspace = Workspace(
        workspace_id=uuid4(),
        repo_url="https://example.com/org/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
    )
    store.workspaces_by_id[workspace.workspace_id] = workspace
    store.workspaces_by_canonical_path[workspace.canonical_path] = (
        workspace.workspace_id
    )

    snapshot = store.snapshot()
    assert snapshot.workspaces_by_id == store.workspaces_by_id
    assert snapshot.workspaces_by_id is not store.workspaces_by_id
    assert (
        snapshot.workspaces_by_canonical_path is not store.workspaces_by_canonical_path
    )

    factory = build_in_memory_uow_factory(store)
    first_uow = factory()
    second_uow = factory()

    assert first_uow.workspaces.get_by_id(workspace.workspace_id) == workspace
    first_uow.workspaces.update(
        Workspace(
            workspace_id=workspace.workspace_id,
            repo_url=workspace.repo_url,
            canonical_path="/tmp/updated-repo",
            default_branch=workspace.default_branch,
        )
    )
    assert second_uow.workspaces.get_by_canonical_path("/tmp/updated-repo") is not None


def test_serialize_workflow_resume_includes_optional_and_closed_failure_fields() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()
    verify_id = uuid4()

    resume = WorkflowResume(
        workspace=Workspace(
            workspace_id=workspace_id,
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
            metadata={"team": "platform"},
        ),
        workflow_instance=WorkflowInstance(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            ticket_id="SER-1",
            status=WorkflowInstanceStatus.RUNNING,
            metadata={"priority": "high"},
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_instance_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.RUNNING,
            verify_status=VerifyStatus.PASSED,
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            finished_at=None,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=checkpoint_id,
            workflow_instance_id=workflow_instance_id,
            attempt_id=attempt_id,
            step_name="implement_feature",
            summary="Add serializer coverage",
            checkpoint_json={"next_intended_action": "Run tests"},
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
        ),
        latest_verify_report=VerifyReport(
            verify_id=verify_id,
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"]},
            created_at=datetime(2024, 1, 3, tzinfo=UTC),
        ),
        resumable_status=ResumableStatus.RESUMABLE,
        projections=(
            ProjectionInfo(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
                last_successful_write_at=datetime(2024, 1, 4, tzinfo=UTC),
                last_canonical_update_at=datetime(2024, 1, 4, tzinfo=UTC),
                open_failure_count=0,
            ),
        ),
        warnings=(),
        closed_projection_failures=(
            ProjectionFailureInfo(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                error_code="io_error",
                error_message="resolved failure",
                target_path=".agent/resume.json",
                attempt_id=attempt_id,
                occurred_at=datetime(2024, 1, 5, tzinfo=UTC),
                resolved_at=datetime(2024, 1, 6, tzinfo=UTC),
                open_failure_count=0,
                retry_count=1,
                status="resolved",
            ),
        ),
        next_hint="Resume safely",
    )

    payload = serialize_workflow_resume(resume)

    assert payload["workspace"]["workspace_id"] == str(workspace_id)
    assert payload["workflow"]["workflow_instance_id"] == str(workflow_instance_id)
    assert payload["attempt"]["attempt_id"] == str(attempt_id)
    assert payload["latest_checkpoint"]["checkpoint_id"] == str(checkpoint_id)
    assert payload["latest_verify_report"]["verify_id"] == str(verify_id)
    assert payload["projections"][0]["projection_type"] == "resume_json"
    assert payload["closed_projection_failures"][0]["status"] == "resolved"
    assert payload["next_hint"] == "Resume safely"


def test_serialize_closed_projection_failures_history_serializes_failures() -> None:
    workflow_instance_id = uuid4()
    attempt_id = uuid4()

    payload = serialize_closed_projection_failures_history(
        workflow_instance_id,
        [
            ProjectionFailureInfo(
                projection_type=ProjectionArtifactType.RESUME_MD,
                error_code=None,
                error_message="ignored failure",
                target_path=".agent/resume.md",
                attempt_id=attempt_id,
                occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
                resolved_at=datetime(2024, 1, 2, tzinfo=UTC),
                open_failure_count=0,
                retry_count=2,
                status="ignored",
            )
        ],
    )

    assert payload["workflow_instance_id"] == str(workflow_instance_id)
    assert payload["closed_projection_failures"][0]["projection_type"] == "resume_md"
    assert payload["closed_projection_failures"][0]["attempt_id"] == str(attempt_id)
    assert payload["closed_projection_failures"][0]["status"] == "ignored"


def test_serialize_stub_response_and_runtime_introspection_helpers() -> None:
    stub_response = StubResponse(
        feature=MemoryFeature.SEARCH,
        implemented=False,
        message="Not implemented",
        details={"limit": 10},
    )
    introspection = RuntimeIntrospection(
        transport="http",
        routes=("route_a",),
        tools=("tool_a",),
        resources=("resource_a",),
    )

    serialized_stub = serialize_stub_response(stub_response)
    serialized_runtime = serialize_runtime_introspection(introspection)
    serialized_collection = serialize_runtime_introspection_collection((introspection,))

    assert serialized_stub["feature"] == "memory_search"
    assert serialized_stub["implemented"] is False
    assert serialized_runtime == {
        "transport": "http",
        "routes": ["route_a"],
        "tools": ["tool_a"],
        "resources": ["resource_a"],
    }
    assert serialized_collection == [serialized_runtime]


def test_serialize_search_memory_response_serializes_results() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 3, 4, 5, 6, 7, tzinfo=UTC)
    response = SearchMemoryResponse(
        feature=MemoryFeature.SEARCH,
        implemented=True,
        message="Hybrid lexical and semantic memory search completed successfully.",
        status="ok",
        available_in_version="0.3.0",
        timestamp=created_at,
        results=(
            SearchResultRecord(
                memory_id=uuid4(),
                workspace_id=workflow_id,
                episode_id=uuid4(),
                workflow_instance_id=None,
                summary="Recovered context",
                attempt_id=attempt_id,
                metadata={"kind": "root-cause"},
                score=4.5,
                matched_fields=("content", "embedding_similarity"),
                lexical_score=3.0,
                semantic_score=0.75,
                ranking_details={
                    "lexical_component": 3.0,
                    "semantic_component": 0.75,
                    "score_mode": "hybrid",
                    "semantic_only_discount_applied": False,
                },
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": "root cause",
            "normalized_query": "root cause",
            "workspace_id": str(workflow_id),
            "limit": 3,
            "filters": {"kind": "episode"},
            "search_mode": "hybrid_memory_item_search",
            "memory_items_considered": 2,
            "semantic_candidates_considered": 2,
            "semantic_query_generated": True,
            "hybrid_scoring": {
                "lexical_weight": 1.0,
                "semantic_weight": 1.0,
                "semantic_only_discount": 0.75,
            },
            "result_mode_counts": {
                "hybrid": 1,
                "lexical_only": 0,
                "semantic_only_discounted": 0,
            },
            "results_returned": 1,
        },
    )

    payload = serialize_search_memory_response(response)

    assert payload["feature"] == "memory_search"
    assert payload["implemented"] is True
    assert (
        payload["message"]
        == "Hybrid lexical and semantic memory search completed successfully."
    )
    assert payload["status"] == "ok"
    assert payload["available_in_version"] == "0.3.0"
    assert payload["timestamp"] == created_at.isoformat()
    assert payload["details"] == {
        "query": "root cause",
        "normalized_query": "root cause",
        "workspace_id": str(workflow_id),
        "limit": 3,
        "filters": {"kind": "episode"},
        "search_mode": "hybrid_memory_item_search",
        "memory_items_considered": 2,
        "semantic_candidates_considered": 2,
        "semantic_query_generated": True,
        "hybrid_scoring": {
            "lexical_weight": 1.0,
            "semantic_weight": 1.0,
            "semantic_only_discount": 0.75,
        },
        "result_mode_counts": {
            "hybrid": 1,
            "lexical_only": 0,
            "semantic_only_discounted": 0,
        },
        "results_returned": 1,
    }
    assert payload["results"] == [
        {
            "memory_id": str(response.results[0].memory_id),
            "workspace_id": str(workflow_id),
            "episode_id": str(response.results[0].episode_id),
            "workflow_instance_id": None,
            "summary": "Recovered context",
            "attempt_id": str(attempt_id),
            "metadata": {"kind": "root-cause"},
            "score": 4.5,
            "matched_fields": ["content", "embedding_similarity"],
            "lexical_score": 3.0,
            "semantic_score": 0.75,
            "ranking_details": {
                "lexical_component": 3.0,
                "semantic_component": 0.75,
                "score_mode": "hybrid",
                "semantic_only_discount_applied": False,
            },
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]


def test_build_embedding_generator_returns_disabled_generator_when_disabled() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            model="unused",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
        )
    )

    assert isinstance(generator, DisabledEmbeddingGenerator)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello"))

    assert exc_info.value.provider == "disabled"


def test_memory_service_persists_local_stub_embedding_after_memory_item_ingest() -> (
    None
):
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-EMBED-1",
            }
        }
    )
    embedding_generator = LocalStubEmbeddingGenerator(
        model="local-stub-v1",
        dimensions=8,
    )
    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=embedding_generator,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    response = service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(workflow_id),
            summary="Persist embedding for this memory item",
            metadata={"kind": "checkpoint", "component": "memory"},
        )
    )

    assert response.feature == MemoryFeature.REMEMBER_EPISODE
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 1
    assert (
        memory_embedding_repository.embeddings[0].memory_id
        == memory_item_repository.memory_items[0].memory_id
    )
    assert memory_embedding_repository.embeddings[0].embedding_model == "local-stub-v1"
    assert len(memory_embedding_repository.embeddings[0].embedding) == 8
    assert memory_embedding_repository.embeddings[
        0
    ].content_hash == compute_content_hash(
        "Persist embedding for this memory item",
        {"kind": "checkpoint", "component": "memory"},
    )


def test_memory_service_skips_embedding_persistence_when_external_provider_is_unimplemented() -> (
    None
):
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-EMBED-2",
            }
        }
    )
    embedding_generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )
    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=embedding_generator,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    response = service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(workflow_id),
            summary="External embedding provider remains optional",
            metadata={"kind": "checkpoint", "component": "memory"},
        )
    )

    assert response.feature == MemoryFeature.REMEMBER_EPISODE
    assert len(memory_item_repository.memory_items) == 1
    assert memory_embedding_repository.embeddings == ()


def test_build_embedding_generator_returns_local_stub_generator() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.LOCAL_STUB,
            model="local-stub-v1",
            api_key=None,
            base_url=None,
            dimensions=8,
            enabled=True,
        )
    )

    assert isinstance(generator, LocalStubEmbeddingGenerator)

    result = generator.generate(
        EmbeddingRequest(
            text="hello world",
            metadata={"kind": "checkpoint"},
        )
    )

    assert result.provider == "local_stub"
    assert result.model == "local-stub-v1"
    assert len(result.vector) == 8
    assert result.content_hash == compute_content_hash(
        "hello world",
        {"kind": "checkpoint"},
    )
    assert all(-1.0 <= value <= 1.0 for value in result.vector)


def test_local_stub_embedding_generator_is_deterministic() -> None:
    generator = LocalStubEmbeddingGenerator(model="local-stub-v1", dimensions=6)

    first = generator.generate(
        EmbeddingRequest(
            text="deterministic text",
            metadata={"kind": "episode"},
        )
    )
    second = generator.generate(
        EmbeddingRequest(
            text="deterministic text",
            metadata={"kind": "episode"},
        )
    )

    assert first == second
    assert len(first.vector) == 6


def test_local_stub_embedding_generator_rejects_empty_text() -> None:
    generator = LocalStubEmbeddingGenerator(model="local-stub-v1", dimensions=4)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="   "))

    assert exc_info.value.provider == "local_stub"
    assert exc_info.value.details == {"field": "text"}


def test_build_embedding_generator_returns_external_provider_descriptor() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            api_key="secret",
            base_url="https://api.openai.com/v1",
            dimensions=1536,
            enabled=True,
        )
    )

    assert isinstance(generator, ExternalAPIEmbeddingGenerator)


def test_external_embedding_generator_requires_api_key_at_runtime() -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model="text-embedding-3-small",
        api_key=None,
        base_url="https://api.openai.com/v1",
    )

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello"))

    assert exc_info.value.provider == "openai"
    assert exc_info.value.details == {"field": "api_key"}


def test_external_embedding_generator_reports_not_implemented_provider_details() -> (
    None
):
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model="text-embedding-3-small",
        api_key="secret",
        base_url="https://api.openai.com/v1",
    )

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "openai"
    assert exc_info.value.details == {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "base_url": "https://api.openai.com/v1",
    }


def test_custom_http_embedding_generator_returns_embedding_from_top_level_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "custom-model-v2",
                    "embedding": [0.25, -0.5, 1],
                }
            ).encode("utf-8")

    def fake_urlopen(request: object) -> FakeResponse:
        captured["full_url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["accept"] = request.get_header("Accept")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = generator.generate(
        EmbeddingRequest(
            text="hello world",
            metadata={"kind": "episode"},
        )
    )

    assert result.provider == "custom_http"
    assert result.model == "custom-model-v2"
    assert result.vector == (0.25, -0.5, 1.0)
    assert result.content_hash == compute_content_hash(
        "hello world",
        {"kind": "episode"},
    )
    assert captured == {
        "full_url": "https://embeddings.example.com/v1",
        "method": "POST",
        "authorization": "Bearer secret",
        "content_type": "application/json",
        "accept": "application/json",
        "body": {
            "text": "hello world",
            "model": "custom-model",
            "metadata": {"kind": "episode"},
        },
    }


def test_custom_http_embedding_generator_returns_embedding_from_nested_data_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "data": [
                        {
                            "model": "nested-model",
                            "embedding": [1, 2.5, -3],
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda _request: FakeResponse())

    result = generator.generate(EmbeddingRequest(text="hello world"))

    assert result.provider == "custom_http"
    assert result.model == "nested-model"
    assert result.vector == (1.0, 2.5, -3.0)


def test_custom_http_embedding_generator_reports_http_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    def fake_urlopen(_request: object) -> object:
        raise urllib_error.HTTPError(
            url="https://embeddings.example.com/v1",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details["status_code"] == 503
    assert exc_info.value.details["base_url"] == "https://embeddings.example.com/v1"


def test_custom_http_embedding_generator_rejects_invalid_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr("urllib.request.urlopen", lambda _request: FakeResponse())

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details["base_url"] == "https://embeddings.example.com/v1"
    assert exc_info.value.details["response_body"] == "not-json"


def test_custom_http_embedding_generator_rejects_missing_embedding_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"data": [{"model": "custom-model"}]}).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda _request: FakeResponse())

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details == {"field": "embedding"}


def test_in_memory_memory_embedding_repository_find_similar_orders_by_similarity() -> (
    None
):
    repository = InMemoryMemoryEmbeddingRepository()
    first_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="first-hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.5, 0.5, 0.0),
        content_hash="second-hash",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    third_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0, 0.0),
        content_hash="third-hash",
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )

    repository.create(first_embedding)
    repository.create(second_embedding)
    repository.create(third_embedding)

    matches = repository.find_similar((1.0, 0.0, 0.0), limit=2)

    assert matches == (first_embedding, second_embedding)


def test_in_memory_memory_embedding_repository_find_similar_ignores_dimension_mismatch() -> (
    None
):
    repository = InMemoryMemoryEmbeddingRepository()
    matching_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0),
        content_hash="matching-hash",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    mismatched_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="mismatched-hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    repository.create(matching_embedding)
    repository.create(mismatched_embedding)

    matches = repository.find_similar((0.0, 1.0), limit=5)

    assert matches == (matching_embedding,)


def test_in_memory_memory_embedding_repository_find_similar_returns_empty_for_empty_query() -> (
    None
):
    repository = InMemoryMemoryEmbeddingRepository()
    repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=uuid4(),
            embedding_model="local-stub-v1",
            embedding=(1.0, 0.0),
            content_hash="hash",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )

    matches = repository.find_similar((), limit=5)

    assert matches == ()


def test_compute_content_hash_uses_text_and_metadata() -> None:
    first = compute_content_hash("same text", {"kind": "episode"})
    second = compute_content_hash("same text", {"kind": "episode"})
    different_text = compute_content_hash("other text", {"kind": "episode"})
    different_metadata = compute_content_hash("same text", {"kind": "checkpoint"})

    assert first == second
    assert first != different_text
    assert first != different_metadata


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
    assert database_unavailable_status.details["database_reachable"] is False
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
    assert schema_not_ready_status.details["database_reachable"] is True
    assert schema_not_ready_status.details["schema_ready"] is False


def test_memory_service_records_episodes_and_returns_search_results() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-1",
            }
        }
    )
    memory_item_repository = InMemoryMemoryItemRepository()
    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    remember_response = service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(workflow_id),
            summary="Episode summary with relevant context",
            attempt_id=str(attempt_id),
            metadata={"kind": "checkpoint", "topic": "relevant context"},
        )
    )
    search_response = service.search(
        SearchMemoryRequest(
            query="relevant context",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={"kind": "episode"},
        )
    )
    context_response = service.get_context(
        GetMemoryContextRequest(
            query="relevant context",
            workspace_id="ws-1",
            workflow_instance_id=str(workflow_id),
            ticket_id="TICKET-1",
            limit=3,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert isinstance(remember_response, RememberEpisodeResponse)
    assert remember_response.feature == MemoryFeature.REMEMBER_EPISODE
    assert remember_response.implemented is True
    assert remember_response.status == "recorded"
    assert remember_response.episode is not None
    assert remember_response.episode.workflow_instance_id == workflow_id
    assert remember_response.episode.attempt_id == attempt_id
    assert remember_response.episode.summary == "Episode summary with relevant context"
    assert remember_response.episode.metadata == {
        "kind": "checkpoint",
        "topic": "relevant context",
    }
    assert remember_response.details == {
        "workflow_instance_id": str(workflow_id),
        "attempt_id": str(attempt_id),
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert memory_item_repository.memory_items[0].workspace_id == UUID(
        "00000000-0000-0000-0000-000000000001"
    )
    assert (
        memory_item_repository.memory_items[0].episode_id
        == remember_response.episode.episode_id
    )
    assert memory_item_repository.memory_items[0].type == "episode_note"
    assert memory_item_repository.memory_items[0].provenance == "episode"
    assert (
        memory_item_repository.memory_items[0].content
        == "Episode summary with relevant context"
    )
    assert memory_item_repository.memory_items[0].metadata == {
        "kind": "checkpoint",
        "topic": "relevant context",
    }

    assert search_response.feature == MemoryFeature.SEARCH
    assert search_response.implemented is True
    assert search_response.status == "ok"
    assert search_response.available_in_version == "0.3.0"
    assert search_response.details["limit"] == 5
    assert search_response.details["filters"] == {"kind": "episode"}
    assert search_response.details["search_mode"] == "memory_item_lexical"
    assert search_response.details["memory_items_considered"] == 1
    assert search_response.details["semantic_candidates_considered"] == 0
    assert search_response.details["semantic_query_generated"] is False
    assert (
        search_response.details["semantic_generation_skipped_reason"]
        == "embedding_search_not_configured"
    )
    assert search_response.details["results_returned"] == 1
    assert len(search_response.results) == 1
    assert (
        search_response.results[0].memory_id
        == memory_item_repository.memory_items[0].memory_id
    )
    assert search_response.results[0].workspace_id == UUID(
        "00000000-0000-0000-0000-000000000001"
    )
    assert search_response.results[0].episode_id == remember_response.episode.episode_id
    assert search_response.results[0].workflow_instance_id is None
    assert search_response.results[0].attempt_id is None
    assert search_response.results[0].summary == "Episode summary with relevant context"
    assert search_response.results[0].metadata == {
        "kind": "checkpoint",
        "topic": "relevant context",
    }
    assert "content" in search_response.results[0].matched_fields
    assert search_response.results[0].lexical_score > 0
    assert search_response.results[0].semantic_score == 0.0
    assert search_response.results[0].score == search_response.results[0].lexical_score

    assert context_response.feature == MemoryFeature.GET_CONTEXT


def test_memory_service_hybrid_ranking_prefers_lexical_evidence() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-HYBRID-1",
            }
        }
    )

    lexical_and_semantic_memory_id = uuid4()
    semantic_only_memory_id = uuid4()
    lexical_and_semantic_episode_id = uuid4()
    semantic_only_episode_id = uuid4()
    created_at = datetime(2024, 1, 2, tzinfo=UTC)

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=lexical_and_semantic_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=lexical_and_semantic_episode_id,
            type="episode_note",
            provenance="episode",
            content="Projection drift root cause identified in deployment workflow",
            metadata={"kind": "root-cause"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=semantic_only_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=semantic_only_episode_id,
            type="episode_note",
            provenance="episode",
            content="Background note with no lexical overlap",
            metadata={"kind": "background"},
            created_at=datetime(2024, 1, 3, tzinfo=UTC),
            updated_at=datetime(2024, 1, 3, tzinfo=UTC),
        )
    )

    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=lexical_and_semantic_memory_id,
            embedding_model="test-hybrid-v1",
            embedding=(0.8, 0.0),
            content_hash="lexical-and-semantic-hash",
            created_at=created_at,
        )
    )
    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=semantic_only_memory_id,
            embedding_model="test-hybrid-v1",
            embedding=(1.0, 0.0),
            content_hash="semantic-only-hash",
            created_at=datetime(2024, 1, 3, tzinfo=UTC),
        )
    )

    class FixedEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            assert request.text == "projection drift root cause"
            return EmbeddingResult(
                provider="test",
                model="test-hybrid-v1",
                vector=(1.0, 0.0),
                content_hash="query-hash",
            )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=FixedEmbeddingGenerator(),
        workflow_lookup=workflow_lookup,
    )

    search_response = service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={},
        )
    )

    assert search_response.feature == MemoryFeature.SEARCH
    assert search_response.details["search_mode"] == "hybrid_memory_item_search"
    assert search_response.details["semantic_candidates_considered"] == 2
    assert search_response.details["semantic_query_generated"] is True
    assert search_response.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 1,
        "semantic_only_discounted": 1,
    }
    assert search_response.details["results_returned"] == 2
    assert [result.memory_id for result in search_response.results] == [
        lexical_and_semantic_memory_id,
        semantic_only_memory_id,
    ]
    assert "content" in search_response.results[0].matched_fields
    assert search_response.results[0].lexical_score > 0.0
    assert search_response.results[0].semantic_score == 0.0
    assert search_response.results[0].ranking_details == {
        "lexical_component": search_response.results[0].lexical_score,
        "semantic_component": 0.0,
        "score_mode": "lexical_only",
        "semantic_only_discount_applied": False,
    }
    assert search_response.results[0].score > search_response.results[1].score
    assert search_response.results[1].lexical_score == 0.0
    assert search_response.results[1].ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": search_response.results[1].semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert search_response.results[1].semantic_score == 1.0


def test_memory_service_hybrid_ranking_uses_similarity_gap_for_semantic_scores() -> (
    None
):
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-HYBRID-2",
            }
        }
    )

    strongest_memory_id = uuid4()
    middle_memory_id = uuid4()
    weakest_memory_id = uuid4()
    created_at = datetime(2024, 1, 4, tzinfo=UTC)

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=strongest_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="Semantic strongest memory item",
            metadata={"kind": "semantic"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=middle_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="Semantic middle memory item",
            metadata={"kind": "semantic"},
            created_at=datetime(2024, 1, 5, tzinfo=UTC),
            updated_at=datetime(2024, 1, 5, tzinfo=UTC),
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=weakest_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="Semantic weakest memory item",
            metadata={"kind": "semantic"},
            created_at=datetime(2024, 1, 6, tzinfo=UTC),
            updated_at=datetime(2024, 1, 6, tzinfo=UTC),
        )
    )

    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=strongest_memory_id,
            embedding_model="test-hybrid-v2",
            embedding=(1.0, 0.0),
            content_hash="strongest-hash",
            created_at=created_at,
        )
    )
    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=middle_memory_id,
            embedding_model="test-hybrid-v2",
            embedding=(0.6, 0.0),
            content_hash="middle-hash",
            created_at=datetime(2024, 1, 5, tzinfo=UTC),
        )
    )
    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=weakest_memory_id,
            embedding_model="test-hybrid-v2",
            embedding=(0.2, 0.0),
            content_hash="weakest-hash",
            created_at=datetime(2024, 1, 6, tzinfo=UTC),
        )
    )

    class FixedEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            assert request.text == "semantic query"
            return EmbeddingResult(
                provider="test",
                model="test-hybrid-v2",
                vector=(1.0, 0.0),
                content_hash="query-hash",
            )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=FixedEmbeddingGenerator(),
        workflow_lookup=workflow_lookup,
    )

    search_response = service.search(
        SearchMemoryRequest(
            query="semantic query",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={},
        )
    )

    assert [result.memory_id for result in search_response.results] == [
        strongest_memory_id,
        middle_memory_id,
    ]
    assert search_response.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 0,
        "semantic_only_discounted": 2,
    }
    assert search_response.results[0].semantic_score == pytest.approx(1.0)
    assert search_response.results[1].semantic_score == pytest.approx(0.390625)
    assert search_response.results[0].ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": search_response.results[0].semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert search_response.results[1].ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": search_response.results[1].semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert search_response.results[0].score == pytest.approx(0.75)
    assert search_response.results[1].score == pytest.approx(0.29296875)


def test_memory_service_raises_validation_errors_for_invalid_requests() -> None:
    workflow_id = uuid4()
    service = MemoryService(
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    with pytest.raises(MemoryServiceError) as remember_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id="   ",
                summary="Episode summary",
            )
        )
    assert remember_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert remember_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert remember_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as invalid_uuid_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id="not-a-uuid",
                summary="Episode summary",
            )
        )
    assert invalid_uuid_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert invalid_uuid_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert invalid_uuid_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as missing_workflow_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(uuid4()),
                summary="Episode summary",
            )
        )
    assert missing_workflow_error.value.code == MemoryErrorCode.WORKFLOW_NOT_FOUND
    assert missing_workflow_error.value.feature == MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as search_error:
        service.search(
            SearchMemoryRequest(
                query="valid query",
                limit=0,
            )
        )
    assert search_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert search_error.value.feature == MemoryFeature.SEARCH
    assert search_error.value.details == {"field": "limit", "value": 0}

    with pytest.raises(MemoryServiceError) as context_error:
        service.get_context(
            GetMemoryContextRequest(
                query=None,
                workspace_id=None,
                workflow_instance_id=None,
                ticket_id=None,
                limit=1,
            )
        )
    assert context_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert context_error.value.feature == MemoryFeature.GET_CONTEXT
    assert (
        context_error.value.message
        == "At least one of query, workspace_id, workflow_instance_id, or ticket_id must be provided."
    )


def test_memory_get_context_returns_episode_oriented_results() -> None:
    workflow_id = uuid4()
    other_workflow_id = uuid4()
    attempt_id = uuid4()
    now = datetime(2024, 1, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    older_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Older episode",
        attempt_id=attempt_id,
        metadata={"kind": "design"},
        created_at=now,
        updated_at=now,
    )
    newer_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Newer episode",
        attempt_id=None,
        metadata={"kind": "fix"},
        created_at=datetime(2024, 1, 11, tzinfo=UTC),
        updated_at=datetime(2024, 1, 11, tzinfo=UTC),
    )
    unrelated_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=other_workflow_id,
        summary="Unrelated episode",
        attempt_id=None,
        metadata={"kind": "other"},
        created_at=datetime(2024, 1, 12, tzinfo=UTC),
        updated_at=datetime(2024, 1, 12, tzinfo=UTC),
    )

    episode_repository.create(older_episode)
    episode_repository.create(newer_episode)
    episode_repository.create(unrelated_episode)

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            {workflow_id, other_workflow_id}
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=5,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert isinstance(response, GetContextResponse)
    assert response.feature == MemoryFeature.GET_CONTEXT
    assert response.implemented is True
    assert response.status == "ok"
    assert response.available_in_version == "0.2.0"
    assert [episode.summary for episode in response.episodes] == [
        "Newer episode",
        "Older episode",
    ]
    assert response.details == {
        "query": None,
        "normalized_query": None,
        "lookup_scope": "workflow_instance",
        "workspace_id": None,
        "workflow_instance_id": str(workflow_id),
        "ticket_id": None,
        "limit": 5,
        "include_episodes": True,
        "include_memory_items": False,
        "include_summaries": False,
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": False,
        "episodes_before_query_filter": 2,
        "matched_episode_count": 2,
        "episodes_returned": 2,
    }


def test_memory_get_context_respects_limit_and_include_episodes_flag() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    for index in range(3):
        episode_repository.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_id,
                summary=f"Episode {index}",
                metadata={"index": index},
                created_at=created_at.replace(day=index + 1),
                updated_at=created_at.replace(day=index + 1),
            )
        )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    limited_response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=2,
            include_episodes=True,
        )
    )
    no_episode_response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=2,
            include_episodes=False,
        )
    )

    assert [episode.summary for episode in limited_response.episodes] == [
        "Episode 2",
        "Episode 1",
    ]
    assert limited_response.details["lookup_scope"] == "workflow_instance"
    assert limited_response.details["resolved_workflow_count"] == 1
    assert limited_response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert limited_response.details["query_filter_applied"] is False
    assert limited_response.details["episodes_before_query_filter"] == 2
    assert limited_response.details["matched_episode_count"] == 2
    assert limited_response.details["episodes_returned"] == 2

    assert no_episode_response.episodes == ()
    assert no_episode_response.details["lookup_scope"] == "workflow_instance"
    assert no_episode_response.details["resolved_workflow_count"] == 1
    assert no_episode_response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert no_episode_response.details["query_filter_applied"] is False
    assert no_episode_response.details["episodes_before_query_filter"] == 0
    assert no_episode_response.details["matched_episode_count"] == 0
    assert no_episode_response.details["episodes_returned"] == 0
    assert no_episode_response.details["workflow_instance_id"] == str(workflow_id)


def test_memory_get_context_applies_initial_query_filtering() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 1, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Fix flaky postgres startup ordering",
            metadata={"kind": "stabilization", "component": "postgres"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"kind": "docs", "component": "release"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="postgres",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Fix flaky postgres startup ordering"
    ]
    assert response.details == {
        "query": "postgres",
        "normalized_query": "postgres",
        "lookup_scope": "workflow_instance",
        "workspace_id": None,
        "workflow_instance_id": str(workflow_id),
        "ticket_id": None,
        "limit": 10,
        "include_episodes": True,
        "include_memory_items": False,
        "include_summaries": False,
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": True,
        "episodes_before_query_filter": 2,
        "matched_episode_count": 1,
        "episodes_returned": 1,
    }


def test_memory_get_context_matches_query_against_metadata_keys() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 5, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"kind": "docs", "component": "release"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Capture workflow evidence",
            metadata={"kind": "ops", "service": "postgres"},
            created_at=created_at.replace(day=6),
            updated_at=created_at.replace(day=6),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="component",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Document release checklist"
    ]
    assert response.details == {
        "query": "component",
        "normalized_query": "component",
        "lookup_scope": "workflow_instance",
        "workspace_id": None,
        "workflow_instance_id": str(workflow_id),
        "ticket_id": None,
        "limit": 10,
        "include_episodes": True,
        "include_memory_items": False,
        "include_summaries": False,
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": True,
        "episodes_before_query_filter": 2,
        "matched_episode_count": 1,
        "episodes_returned": 1,
    }


def test_memory_get_context_matches_query_against_metadata_values() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 7, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"kind": "docs", "component": "release"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Capture workflow evidence",
            metadata={"kind": "ops", "service": "postgres"},
            created_at=created_at.replace(day=8),
            updated_at=created_at.replace(day=8),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="release",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Document release checklist"
    ]
    assert response.details == {
        "query": "release",
        "normalized_query": "release",
        "lookup_scope": "workflow_instance",
        "workspace_id": None,
        "workflow_instance_id": str(workflow_id),
        "ticket_id": None,
        "limit": 10,
        "include_episodes": True,
        "include_memory_items": False,
        "include_summaries": False,
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": True,
        "episodes_before_query_filter": 2,
        "matched_episode_count": 1,
        "episodes_returned": 1,
    }


def test_serialize_get_context_response_serializes_episode_payloads() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 3, 4, 5, 6, 7, tzinfo=UTC)
    response = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_id,
                summary="Recovered context",
                attempt_id=attempt_id,
                metadata={"kind": "root-cause"},
                status="recorded",
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": "root cause",
            "normalized_query": "root cause",
            "lookup_scope": "workflow_instance",
            "workflow_instance_id": str(workflow_id),
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(workflow_id)],
            "query_filter_applied": True,
            "episodes_before_query_filter": 3,
            "matched_episode_count": 1,
            "episodes_returned": 1,
        },
    )

    payload = serialize_get_context_response(response)

    assert payload["feature"] == "memory_get_context"
    assert payload["implemented"] is True
    assert (
        payload["message"] == "Episode-oriented memory context retrieved successfully."
    )
    assert payload["status"] == "ok"
    assert payload["available_in_version"] == "0.2.0"
    assert payload["timestamp"] == created_at.isoformat()
    assert payload["details"] == {
        "query": "root cause",
        "normalized_query": "root cause",
        "lookup_scope": "workflow_instance",
        "workflow_instance_id": str(workflow_id),
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": True,
        "episodes_before_query_filter": 3,
        "matched_episode_count": 1,
        "episodes_returned": 1,
    }
    assert payload["episodes"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary": "Recovered context",
            "attempt_id": str(attempt_id),
            "metadata": {"kind": "root-cause"},
            "status": "recorded",
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]


def test_projection_writer_write_resume_projection_handles_success_and_failures(
    tmp_path: Path,
) -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()

    resume = WorkflowResume(
        workspace=Workspace(
            workspace_id=workspace_id,
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        ),
        workflow_instance=WorkflowInstance(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            ticket_id="WRITER-1",
            status=WorkflowInstanceStatus.RUNNING,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_instance_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.RUNNING,
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=attempt_id,
            step_name="implement_writer",
            summary="Write projections",
            checkpoint_json={"next_intended_action": "Run reconciliation"},
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
        ),
        latest_verify_report=None,
        resumable_status=ResumableStatus.RESUMABLE,
        projections=(),
        warnings=(),
        next_hint="Proceed",
    )

    class StubWorkflowService:
        def __init__(self, response: WorkflowResume) -> None:
            self.response = response
            self.reconcile_calls: list[dict[str, object]] = []

        def resume_workflow(self, request: object) -> WorkflowResume:
            assert request.workflow_instance_id == workflow_instance_id
            return self.response

        def reconcile_resume_projection(
            self,
            *,
            success_updates: tuple[RecordProjectionStateInput, ...],
            failure_updates: tuple[RecordProjectionFailureInput, ...],
        ) -> None:
            self.reconcile_calls.append(
                {
                    "success_updates": success_updates,
                    "failure_updates": failure_updates,
                }
            )

    service = StubWorkflowService(resume)
    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    result = writer.write_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=workflow_instance_id,
        workspace_id=workspace_id,
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert len(result.state_updates) == 2
    assert result.failure_updates == ()
    assert json.loads(result.json_path.read_text(encoding="utf-8"))["workflow"][
        "workflow_instance_id"
    ] == str(workflow_instance_id)
    assert "## Next hint" in result.markdown_path.read_text(encoding="utf-8")

    reconciled = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=workflow_instance_id,
        workspace_id=workspace_id,
    )
    assert reconciled.state_updates == result.state_updates
    assert len(service.reconcile_calls) == 1

    failing_writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=False,
            write_json=True,
        ),
    )
    original_build_resume_json = ResumeProjectionWriter._build_resume_json

    def raising_build_resume_json(self, resume: WorkflowResume) -> str:
        raise RuntimeError("json write failed")

    ResumeProjectionWriter._build_resume_json = raising_build_resume_json
    try:
        failing_result = failing_writer.write_resume_projection(
            workspace_root=tmp_path,
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        )
    finally:
        ResumeProjectionWriter._build_resume_json = original_build_resume_json

    assert len(failing_result.state_updates) == 1
    assert failing_result.state_updates[0].status == ProjectionStatus.FAILED
    assert len(failing_result.failure_updates) == 1
    assert failing_result.failure_updates[0].error_message == "json write failed"
    assert failing_result.failure_updates[0].attempt_id == attempt_id


def test_projection_writer_projection_root_and_safe_path_guards(tmp_path: Path) -> None:
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name="   ",
            write_markdown=True,
            write_json=True,
        ),
    )

    with pytest.raises(
        ProjectionWriteError, match="Projection directory name must not be empty"
    ):
        writer._projection_root(tmp_path)

    safe_writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    outside_path = tmp_path.parent / "outside" / "resume.json"
    with pytest.raises(
        ProjectionWriteError,
        match="Projection path must stay within the workspace root",
    ):
        safe_writer._safe_projection_path(tmp_path, outside_path)

    inside_path = tmp_path / ".agent" / "resume.json"
    resolved_inside_path = safe_writer._safe_projection_path(tmp_path, inside_path)
    assert resolved_inside_path == inside_path.resolve()
    assert (
        safe_writer._relative_target_path(tmp_path.resolve(), resolved_inside_path)
        == ".agent/resume.json"
    )


def test_projection_writer_build_state_and_failure_updates() -> None:
    writer = ResumeProjectionWriter(
        workflow_service=SimpleNamespace(),
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()

    state_update = writer._build_state_update(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
    )
    failed_state_update = writer._build_failed_state_update(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_MD,
        target_path=".agent/resume.md",
    )

    class StringCodeError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("write failed")
            self.code = "E_WRITE"

    failure_update = writer._build_failure_update(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        exc=StringCodeError(),
    )

    assert state_update == RecordProjectionStateInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.json",
    )
    assert failed_state_update == RecordProjectionStateInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.FAILED,
        target_path=".agent/resume.md",
    )
    assert failure_update == RecordProjectionFailureInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        error_message="write failed",
        error_code="E_WRITE",
    )


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

    def dispatch_tool(name: object, arguments: object) -> SimpleNamespace:
        return SimpleNamespace(payload={"ok": True})

    def registered_tools() -> tuple[()]:
        return ()

    def registered_resources() -> tuple[()]:
        return ()

    def tool_schema(tool_name: object) -> SimpleNamespace:
        return SimpleNamespace(
            type="object",
            properties={},
            required=(),
        )

    def dispatch_resource(uri: object) -> SimpleNamespace:
        return SimpleNamespace(payload={"ok": True})

    runtime = SimpleNamespace(
        dispatch_tool=dispatch_tool,
    )
    runtime.registered_tools = registered_tools
    runtime.registered_resources = registered_resources
    runtime.tool_schema = tool_schema
    runtime.dispatch_resource = dispatch_resource

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


def test_http_runtime_adapter_handler_registration_and_lookup() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    handler = object()
    runtime.register_handler("demo", handler)

    assert runtime.handler("demo") is handler
    assert runtime.handler("missing") is None
    assert runtime.require_handler("demo") is handler

    with pytest.raises(KeyError, match="missing"):
        runtime.require_handler("missing")


def test_http_runtime_adapter_introspection_and_schema_defaults() -> None:
    from ctxledger.mcp.tool_schemas import DEFAULT_EMPTY_MCP_TOOL_SCHEMA
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    assert runtime.introspection_endpoints() == ()
    assert "workflow_resume" in runtime.registered_tools()
    assert "workspace://{workspace_id}/resume" in runtime.registered_resources()
    assert runtime.tool_schema("unknown_tool") is DEFAULT_EMPTY_MCP_TOOL_SCHEMA

    runtime.register_handler("zeta", object())
    runtime.register_handler("alpha", object())

    assert runtime.introspection_endpoints() == ("alpha", "zeta")
    assert runtime.introspect().transport == "http"


def test_http_runtime_adapter_dispatch_resource_returns_not_found_for_unknown_uri() -> (
    None
):
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    response = runtime.dispatch_resource("workspace://unknown/resource")

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "resource_not_found",
            "message": "unknown MCP resource 'workspace://unknown/resource'",
        }
    }


def test_http_runtime_adapter_dispatch_tool_returns_not_found_for_unknown_tool() -> (
    None
):
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    response = runtime.dispatch_tool("unknown_tool", {})

    assert response.payload["error"]["code"] == "tool_not_found"


def test_http_runtime_adapter_dispatch_covers_missing_route_and_mcp_rpc() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings(path="/mcp"))

    missing_route_response = runtime.dispatch("missing", "/missing")

    runtime.register_handler(
        "mcp_rpc",
        lambda path, body=None: SimpleNamespace(
            status_code=202,
            payload={"path": path, "body": body},
            headers={"content-type": "application/json"},
        ),
    )
    runtime.register_handler(
        "workflow_resume",
        lambda path: SimpleNamespace(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    mcp_response = runtime.dispatch("mcp_rpc", "/mcp", "payload")
    workflow_response = runtime.dispatch("workflow_resume", "/workflow-resume/demo")

    assert missing_route_response.status_code == 404
    assert missing_route_response.payload["error"]["code"] == "route_not_found"
    assert mcp_response.status_code == 202
    assert mcp_response.payload == {"path": "/mcp", "body": "payload"}
    assert workflow_response.status_code == 200
    assert workflow_response.payload == {"path": "/workflow-resume/demo"}


def test_http_runtime_adapter_start_and_stop_cover_idempotent_stop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())
    caplog.set_level("INFO")

    runtime.stop()
    runtime.start()
    runtime.stop()

    assert runtime._started is False
    assert any(
        "HTTP runtime adapter starting" in message for message in caplog.messages
    )
    assert any(
        "HTTP runtime adapter stopping" in message for message in caplog.messages
    )


def test_http_runtime_register_handlers_respects_debug_toggle() -> None:
    from ctxledger.runtime.http_runtime import (
        HttpRuntimeAdapter,
        register_http_runtime_handlers,
    )

    debug_server = make_server(settings=make_settings(debug_enabled=True))
    no_debug_server = make_server(settings=make_settings(debug_enabled=False))

    debug_runtime = register_http_runtime_handlers(
        HttpRuntimeAdapter(debug_server.settings, server=debug_server),
        debug_server,
    )
    no_debug_runtime = register_http_runtime_handlers(
        HttpRuntimeAdapter(no_debug_server.settings, server=no_debug_server),
        no_debug_server,
    )

    assert "mcp_rpc" in debug_runtime.introspection_endpoints()
    assert "runtime_introspection" in debug_runtime.introspection_endpoints()
    assert "runtime_routes" in debug_runtime.introspection_endpoints()
    assert "runtime_tools" in debug_runtime.introspection_endpoints()

    assert "mcp_rpc" in no_debug_runtime.introspection_endpoints()
    assert "runtime_introspection" not in no_debug_runtime.introspection_endpoints()
    assert "runtime_routes" not in no_debug_runtime.introspection_endpoints()
    assert "runtime_tools" not in no_debug_runtime.introspection_endpoints()


def test_http_runtime_build_http_runtime_adapter_returns_registered_runtime() -> None:
    from ctxledger.runtime.http_runtime import (
        HttpRuntimeAdapter,
        build_http_runtime_adapter,
    )

    server = make_server(settings=make_settings())

    runtime = build_http_runtime_adapter(server)

    assert isinstance(runtime, HttpRuntimeAdapter)
    assert runtime.handler("mcp_rpc") is not None
    assert runtime.handler("workflow_resume") is not None
    assert runtime.handler("projection_failures_ignore") is not None
    assert runtime.handler("projection_failures_resolve") is not None


def test_build_runtime_routes_and_tools_responses_include_multiple_non_empty_introspections() -> (
    None
):
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
                    transport="mcp",
                    routes=("runtime_introspection",),
                    tools=("tool_a", "tool_b"),
                    resources=(),
                )
            ),
        ]
    )
    server = make_server(runtime=runtime)

    routes_response = build_runtime_routes_response(server)
    tools_response = build_runtime_tools_response(server)

    assert routes_response.status_code == 200
    assert routes_response.payload == {
        "routes": [
            {"transport": "http", "routes": ["workflow_resume"]},
            {"transport": "mcp", "routes": ["runtime_introspection"]},
        ]
    }
    assert tools_response.status_code == 200
    assert tools_response.payload == {
        "tools": [
            {"transport": "http", "tools": ["workflow_resume"]},
            {"transport": "mcp", "tools": ["tool_a", "tool_b"]},
        ]
    }


def test_server_methods_delegate_to_extracted_response_builders() -> None:
    settings = make_settings()
    server = CtxLedgerServer(settings=settings, db_health_checker=FakeDbChecker())
    workflow_instance_id = uuid4()
    workspace_id = uuid4()
    projection_type = ProjectionArtifactType.RESUME_JSON

    calls: list[tuple[str, object]] = []

    def record(name: str, result: object):
        def _inner(*args, **kwargs):
            calls.append((name, (args, kwargs)))
            return result

        return _inner

    original_workflow_resume = server.build_workflow_resume_response.__globals__[
        "extracted_build_workflow_resume_response"
    ]
    original_closed = server.build_closed_projection_failures_response.__globals__[
        "extracted_build_closed_projection_failures_response"
    ]
    original_ignore = server.build_projection_failures_ignore_response.__globals__[
        "extracted_build_projection_failures_ignore_response"
    ]
    original_resolve = server.build_projection_failures_resolve_response.__globals__[
        "extracted_build_projection_failures_resolve_response"
    ]
    original_runtime = server.build_runtime_introspection_response.__globals__[
        "extracted_build_runtime_introspection_response"
    ]
    original_routes = server.build_runtime_routes_response.__globals__[
        "extracted_build_runtime_routes_response"
    ]
    original_tools = server.build_runtime_tools_response.__globals__[
        "extracted_build_runtime_tools_response"
    ]

    try:
        server.build_workflow_resume_response.__globals__[
            "extracted_build_workflow_resume_response"
        ] = record("workflow_resume", "workflow-result")
        server.build_closed_projection_failures_response.__globals__[
            "extracted_build_closed_projection_failures_response"
        ] = record("closed", "closed-result")
        server.build_projection_failures_ignore_response.__globals__[
            "extracted_build_projection_failures_ignore_response"
        ] = record("ignore", "ignore-result")
        server.build_projection_failures_resolve_response.__globals__[
            "extracted_build_projection_failures_resolve_response"
        ] = record("resolve", "resolve-result")
        server.build_runtime_introspection_response.__globals__[
            "extracted_build_runtime_introspection_response"
        ] = record("runtime", "runtime-result")
        server.build_runtime_routes_response.__globals__[
            "extracted_build_runtime_routes_response"
        ] = record("routes", "routes-result")
        server.build_runtime_tools_response.__globals__[
            "extracted_build_runtime_tools_response"
        ] = record("tools", "tools-result")

        assert (
            server.build_workflow_resume_response(workflow_instance_id)
            == "workflow-result"
        )
        assert (
            server.build_closed_projection_failures_response(workflow_instance_id)
            == "closed-result"
        )
        assert (
            server.build_projection_failures_ignore_response(
                workspace_id=workspace_id,
                workflow_instance_id=workflow_instance_id,
                projection_type=projection_type,
            )
            == "ignore-result"
        )
        assert (
            server.build_projection_failures_resolve_response(
                workspace_id=workspace_id,
                workflow_instance_id=workflow_instance_id,
                projection_type=projection_type,
            )
            == "resolve-result"
        )
        assert server.build_runtime_introspection_response() == "runtime-result"
        assert server.build_runtime_routes_response() == "routes-result"
        assert server.build_runtime_tools_response() == "tools-result"
    finally:
        server.build_workflow_resume_response.__globals__[
            "extracted_build_workflow_resume_response"
        ] = original_workflow_resume
        server.build_closed_projection_failures_response.__globals__[
            "extracted_build_closed_projection_failures_response"
        ] = original_closed
        server.build_projection_failures_ignore_response.__globals__[
            "extracted_build_projection_failures_ignore_response"
        ] = original_ignore
        server.build_projection_failures_resolve_response.__globals__[
            "extracted_build_projection_failures_resolve_response"
        ] = original_resolve
        server.build_runtime_introspection_response.__globals__[
            "extracted_build_runtime_introspection_response"
        ] = original_runtime
        server.build_runtime_routes_response.__globals__[
            "extracted_build_runtime_routes_response"
        ] = original_routes
        server.build_runtime_tools_response.__globals__[
            "extracted_build_runtime_tools_response"
        ] = original_tools

    assert [name for name, _ in calls] == [
        "workflow_resume",
        "closed",
        "ignore",
        "resolve",
        "runtime",
        "routes",
        "tools",
    ]


def test_server_resource_response_methods_delegate_to_runtime_builders() -> None:
    settings = make_settings()
    server = CtxLedgerServer(settings=settings, db_health_checker=FakeDbChecker())
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    workspace_calls: list[tuple[object, object]] = []
    workflow_calls: list[tuple[object, object, object]] = []

    import ctxledger.runtime.server_responses as server_responses_module

    original_workspace = (
        server_responses_module.build_workspace_resume_resource_response
    )
    original_workflow = server_responses_module.build_workflow_detail_resource_response

    try:
        server_responses_module.build_workspace_resume_resource_response = (
            lambda current_server, current_workspace_id: (
                workspace_calls.append((current_server, current_workspace_id))
                or "workspace-resource"
            )
        )
        server_responses_module.build_workflow_detail_resource_response = (
            lambda current_server, current_workspace_id, current_workflow_instance_id: (
                workflow_calls.append(
                    (current_server, current_workspace_id, current_workflow_instance_id)
                )
                or "workflow-resource"
            )
        )

        assert (
            server.build_workspace_resume_resource_response(workspace_id)
            == "workspace-resource"
        )
        assert (
            server.build_workflow_detail_resource_response(
                workspace_id,
                workflow_instance_id,
            )
            == "workflow-resource"
        )
    finally:
        server_responses_module.build_workspace_resume_resource_response = (
            original_workspace
        )
        server_responses_module.build_workflow_detail_resource_response = (
            original_workflow
        )

    assert workspace_calls == [(server, workspace_id)]
    assert workflow_calls == [(server, workspace_id, workflow_instance_id)]


def test_server_validate_configuration_and_get_workflow_resume() -> None:
    validate_calls: list[str] = []

    class FakeSettings:
        def __init__(self) -> None:
            self.database = SimpleNamespace(
                url="postgresql://example/db",
                schema_name="public",
            )
            self.http = SimpleNamespace(
                host="127.0.0.1",
                port=8080,
                path="/mcp",
                mcp_url="http://127.0.0.1:8080/mcp",
            )
            self.logging = SimpleNamespace(level=SimpleNamespace(value="info"))
            self.app_name = "ctxledger"
            self.app_version = "0.1.0"
            self.environment = "test"

        def validate(self) -> None:
            validate_calls.append("validated")

    settings = FakeSettings()
    server = CtxLedgerServer(settings=settings, db_health_checker=FakeDbChecker())

    server.validate_configuration()

    assert validate_calls == ["validated"]

    with pytest.raises(
        ServerBootstrapError, match="workflow service is not initialized"
    ):
        server.get_workflow_resume(uuid4())

    expected_resume = SimpleNamespace(result="resume")
    workflow_calls: list[object] = []
    server.workflow_service = SimpleNamespace(
        resume_workflow=lambda data: workflow_calls.append(data) or expected_resume
    )

    workflow_instance_id = uuid4()
    assert server.get_workflow_resume(workflow_instance_id) is expected_resume
    assert workflow_calls[0].workflow_instance_id == workflow_instance_id


def test_server_shutdown_clears_workflow_service_without_started_runtime() -> None:
    runtime = FakeRuntime()
    server = CtxLedgerServer(
        settings=make_settings(),
        db_health_checker=FakeDbChecker(),
        runtime=runtime,
    )
    server.workflow_service = object()

    server.shutdown()

    assert runtime.stop_calls == 0
    assert server.workflow_service is None
    assert server._started is False


def test_create_server_uses_provided_dependencies_and_builds_runtime_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    provided_checker = FakeDbChecker()
    provided_runtime = FakeRuntime()

    def workflow_service_factory_stub() -> str:
        return "workflow-service"

    created_servers: list[object] = []

    def fake_build_http_runtime_adapter(server: object) -> object:
        created_servers.append(server)
        return "built-runtime"

    monkeypatch.setattr(
        "ctxledger.server.build_http_runtime_adapter",
        fake_build_http_runtime_adapter,
    )

    provided = __import__("ctxledger.server", fromlist=["create_server"])
    server_with_provided_runtime = provided.create_server(
        settings,
        db_health_checker=provided_checker,
        runtime=provided_runtime,
        workflow_service_factory=workflow_service_factory_stub,
    )
    server_with_built_runtime = provided.create_server(
        settings,
        db_health_checker=provided_checker,
        runtime=None,
        workflow_service_factory=workflow_service_factory_stub,
    )

    assert server_with_provided_runtime.db_health_checker is provided_checker
    assert server_with_provided_runtime.runtime is provided_runtime
    assert (
        server_with_provided_runtime.workflow_service_factory
        is workflow_service_factory_stub
    )

    assert server_with_built_runtime.db_health_checker is provided_checker
    assert server_with_built_runtime.runtime == "built-runtime"
    assert (
        server_with_built_runtime.workflow_service_factory
        is workflow_service_factory_stub
    )
    assert created_servers == [server_with_built_runtime]
