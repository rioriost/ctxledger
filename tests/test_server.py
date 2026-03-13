from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.config import (
    AppSettings,
    AuthSettings,
    DatabaseSettings,
    DebugSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    ProjectionSettings,
    TransportMode,
)
from ctxledger.mcp.resource_handlers import (
    build_workflow_detail_resource_handler,
    build_workspace_resume_resource_handler,
    parse_workflow_detail_resource_uri,
    parse_workspace_resume_resource_uri,
)
from ctxledger.mcp.tool_handlers import (
    build_memory_get_context_tool_handler,
    build_memory_remember_episode_tool_handler,
    build_memory_search_tool_handler,
    build_projection_failures_ignore_tool_handler,
    build_projection_failures_resolve_tool_handler,
    build_resume_workflow_tool_handler,
    build_workflow_checkpoint_tool_handler,
    build_workflow_complete_tool_handler,
    build_workflow_start_tool_handler,
    build_workspace_register_tool_handler,
)
from ctxledger.memory.service import MemoryService
from ctxledger.runtime.http_handlers import (
    build_closed_projection_failures_http_handler,
    build_projection_failures_ignore_http_handler,
    build_projection_failures_resolve_http_handler,
    build_runtime_introspection_http_handler,
    build_workflow_resume_http_handler,
    parse_closed_projection_failures_request_path,
    parse_workflow_resume_request_path,
)
from ctxledger.runtime.introspection import collect_runtime_introspection
from ctxledger.runtime.serializers import (
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
    serialize_workflow_resume,
)
from ctxledger.runtime.server_responses import (
    build_closed_projection_failures_response,
    build_runtime_introspection_response,
)
from ctxledger.runtime.types import (
    McpHttpResponse,
    McpResourceResponse,
    McpToolResponse,
    ProjectionFailureActionResponse,
    ProjectionFailureHistoryResponse,
    ReadinessStatus,
    RuntimeDispatchResult,
    RuntimeIntrospectionResponse,
    WorkflowResumeResponse,
)
from ctxledger.server import (
    CtxLedgerServer,
    HttpRuntimeAdapter,
    RuntimeIntrospection,
    ServerBootstrapError,
    _print_runtime_summary,
    build_database_health_checker,
    build_http_runtime_adapter,
    create_runtime,
    create_server,
    dispatch_http_request,
)
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    ProjectionArtifactType,
    ProjectionInfo,
    ProjectionStatus,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeIssue,
    StartWorkflowInput,
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


@dataclass
class FakeWorkflowService:
    resume_result: WorkflowResume
    resume_calls: list[object] | None = None
    register_workspace_result: Workspace | None = None
    register_workspace_calls: list[object] | None = None
    start_workflow_result: object | None = None
    start_workflow_calls: list[object] | None = None
    create_checkpoint_result: object | None = None
    create_checkpoint_calls: list[object] | None = None
    complete_workflow_result: object | None = None
    complete_workflow_calls: list[object] | None = None
    ignore_result: int = 0
    resolve_result: int = 0
    ignore_calls: list[object] | None = None
    resolve_calls: list[object] | None = None

    def __post_init__(self) -> None:
        if self.resume_calls is None:
            self.resume_calls = []
        if self.register_workspace_calls is None:
            self.register_workspace_calls = []
        if self.start_workflow_calls is None:
            self.start_workflow_calls = []
        if self.create_checkpoint_calls is None:
            self.create_checkpoint_calls = []
        if self.complete_workflow_calls is None:
            self.complete_workflow_calls = []
        if self.ignore_calls is None:
            self.ignore_calls = []
        if self.resolve_calls is None:
            self.resolve_calls = []

    def resume_workflow(self, data: object) -> WorkflowResume:
        assert self.resume_calls is not None
        self.resume_calls.append(data)
        return self.resume_result

    def register_workspace(self, data: object) -> Workspace:
        assert self.register_workspace_calls is not None
        assert self.register_workspace_result is not None
        self.register_workspace_calls.append(data)
        return self.register_workspace_result

    def start_workflow(self, data: object) -> object:
        assert self.start_workflow_calls is not None
        assert self.start_workflow_result is not None
        self.start_workflow_calls.append(data)
        return self.start_workflow_result

    def create_checkpoint(self, data: object) -> object:
        assert self.create_checkpoint_calls is not None
        assert self.create_checkpoint_result is not None
        self.create_checkpoint_calls.append(data)
        return self.create_checkpoint_result

    def complete_workflow(self, data: object) -> object:
        assert self.complete_workflow_calls is not None
        assert self.complete_workflow_result is not None
        self.complete_workflow_calls.append(data)
        return self.complete_workflow_result

    def ignore_resume_projection_failures(
        self,
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        assert self.ignore_calls is not None
        self.ignore_calls.append(
            {
                "workspace_id": workspace_id,
                "workflow_instance_id": workflow_instance_id,
                "projection_type": projection_type,
            }
        )
        return self.ignore_result

    def resolve_resume_projection_failures(
        self,
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        assert self.resolve_calls is not None
        self.resolve_calls.append(
            {
                "workspace_id": workspace_id,
                "workflow_instance_id": workflow_instance_id,
                "projection_type": projection_type,
            }
        )
        return self.resolve_result


def make_resume_fixture(
    *,
    closed_projection_failures: tuple[object, ...] = (),
) -> WorkflowResume:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()
    verify_id = uuid4()

    workspace = Workspace(
        workspace_id=workspace_id,
        repo_url="https://example.com/org/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
        metadata={"team": "platform"},
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    workflow_instance = WorkflowInstance(
        workflow_instance_id=workflow_instance_id,
        workspace_id=workspace_id,
        ticket_id="SRV-123",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={"priority": "high"},
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, tzinfo=UTC),
    )
    attempt = WorkflowAttempt(
        attempt_id=attempt_id,
        workflow_instance_id=workflow_instance_id,
        attempt_number=2,
        status=WorkflowAttemptStatus.RUNNING,
        failure_reason=None,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 1, 5, tzinfo=UTC),
        finished_at=None,
        created_at=datetime(2024, 1, 5, tzinfo=UTC),
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        step_name="implement_server_api",
        summary="Expose workflow resume payload",
        checkpoint_json={"next_intended_action": "Serialize resume output"},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
    )
    latest_verify_report = VerifyReport(
        verify_id=verify_id,
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        report_json={"checks": ["pytest"], "status": "passed"},
        created_at=datetime(2024, 1, 7, tzinfo=UTC),
    )
    projections = (
        ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
            last_successful_write_at=datetime(2024, 1, 8, tzinfo=UTC),
            last_canonical_update_at=datetime(2024, 1, 8, tzinfo=UTC),
            open_failure_count=0,
        ),
        ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_MD,
            status=ProjectionStatus.STALE,
            target_path=".agent/resume.md",
            last_successful_write_at=datetime(2024, 1, 8, tzinfo=UTC),
            last_canonical_update_at=datetime(2024, 1, 7, tzinfo=UTC),
            open_failure_count=1,
        ),
    )
    warnings = (
        ResumeIssue(
            code="stale_projection",
            message="resume projection is stale relative to canonical workflow state",
            details={
                "projection_type": "resume_md",
                "target_path": ".agent/resume.md",
            },
        ),
    )

    return WorkflowResume(
        workspace=workspace,
        workflow_instance=workflow_instance,
        attempt=attempt,
        latest_checkpoint=latest_checkpoint,
        latest_verify_report=latest_verify_report,
        resumable_status=ResumableStatus.RESUMABLE,
        projections=projections,
        warnings=warnings,
        closed_projection_failures=closed_projection_failures,
        next_hint="Serialize resume output",
    )


def make_settings(
    *,
    database_url: str = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
    transport: TransportMode = TransportMode.HTTP,
    http_enabled: bool = True,
    host: str = "127.0.0.1",
    port: int = 8080,
    auth_bearer_token: str | None = None,
    require_auth: bool = False,
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
        auth=AuthSettings(
            bearer_token=auth_bearer_token,
            require_auth=require_auth,
        ),
        debug=DebugSettings(
            enabled=True,
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
    assert health.details["runtime"] == []

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.details["database_reachable"] is True
    assert readiness.details["schema_ready"] is True
    assert readiness.details["runtime"] == []

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
    assert readiness.details["runtime"] == []


def test_startup_raises_for_invalid_configuration() -> None:
    settings = make_settings(
        transport=TransportMode.HTTP,
        http_enabled=False,
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
    )

    runtime = create_runtime(settings)

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


def test_get_workflow_resume_returns_resume_from_initialized_workflow_service() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    server.startup()
    returned = server.get_workflow_resume(resume.workflow_instance.workflow_instance_id)

    assert returned == resume
    assert fake_workflow_service.resume_calls is not None
    assert len(fake_workflow_service.resume_calls) == 1
    assert (
        fake_workflow_service.resume_calls[0].workflow_instance_id
        == resume.workflow_instance.workflow_instance_id
    )


def test_get_workflow_resume_raises_when_workflow_service_is_not_initialized() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    with pytest.raises(
        ServerBootstrapError,
        match="workflow service is not initialized",
    ):
        server.get_workflow_resume(uuid4())


def test_serialize_workflow_resume_returns_api_ready_payload() -> None:
    resume = make_resume_fixture()

    payload = serialize_workflow_resume(resume)

    assert payload["workspace"]["workspace_id"] == str(resume.workspace.workspace_id)
    assert payload["workspace"]["repo_url"] == resume.workspace.repo_url
    assert payload["workflow"]["workflow_instance_id"] == str(
        resume.workflow_instance.workflow_instance_id
    )
    assert payload["workflow"]["ticket_id"] == resume.workflow_instance.ticket_id
    assert payload["attempt"]["attempt_id"] == str(resume.attempt.attempt_id)
    assert payload["attempt"]["status"] == resume.attempt.status.value
    assert payload["latest_checkpoint"]["step_name"] == "implement_server_api"
    assert payload["latest_verify_report"]["status"] == VerifyStatus.PASSED.value
    assert payload["projections"] == [
        {
            "projection_type": "resume_json",
            "status": "fresh",
            "target_path": ".agent/resume.json",
            "last_successful_write_at": "2024-01-08T00:00:00+00:00",
            "last_canonical_update_at": "2024-01-08T00:00:00+00:00",
            "open_failure_count": 0,
        },
        {
            "projection_type": "resume_md",
            "status": "stale",
            "target_path": ".agent/resume.md",
            "last_successful_write_at": "2024-01-08T00:00:00+00:00",
            "last_canonical_update_at": "2024-01-07T00:00:00+00:00",
            "open_failure_count": 1,
        },
    ]
    assert payload["resumable_status"] == "resumable"
    assert payload["next_hint"] == "Serialize resume output"
    assert payload["warnings"] == [
        {
            "code": "stale_projection",
            "message": "resume projection is stale relative to canonical workflow state",
            "details": {
                "projection_type": "resume_md",
                "target_path": ".agent/resume.md",
            },
        }
    ]
    assert payload["closed_projection_failures"] == []


def test_serialize_workflow_resume_includes_closed_projection_failures() -> None:
    attempt_id = uuid4()
    closed_projection_failures = (
        type(
            "ClosedProjectionFailure",
            (),
            {
                "projection_type": ProjectionArtifactType.RESUME_JSON,
                "target_path": ".agent/resume.json",
                "attempt_id": attempt_id,
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": datetime(2024, 1, 9, tzinfo=UTC),
                "resolved_at": datetime(2024, 1, 10, tzinfo=UTC),
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            },
        )(),
    )
    resume = make_resume_fixture(
        closed_projection_failures=closed_projection_failures,
    )

    payload = serialize_workflow_resume(resume)

    assert payload["closed_projection_failures"] == [
        {
            "projection_type": "resume_json",
            "target_path": ".agent/resume.json",
            "attempt_id": str(attempt_id),
            "error_code": "EACCES",
            "error_message": "permission denied",
            "occurred_at": "2024-01-09T00:00:00+00:00",
            "resolved_at": "2024-01-10T00:00:00+00:00",
            "open_failure_count": 0,
            "retry_count": 2,
            "status": "ignored",
        }
    ]


def test_build_workflow_resume_response_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    server.startup()

    response = server.build_workflow_resume_response(
        resume.workflow_instance.workflow_instance_id
    )

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)


def test_build_workflow_resume_response_returns_503_when_workflow_service_is_not_initialized() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    response = server.build_workflow_resume_response(uuid4())

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }


def test_build_closed_projection_failures_response_returns_success_payload() -> None:
    attempt_id = uuid4()
    closed_projection_failures = (
        type(
            "ClosedProjectionFailure",
            (),
            {
                "projection_type": ProjectionArtifactType.RESUME_JSON,
                "target_path": ".agent/resume.json",
                "attempt_id": attempt_id,
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": datetime(2024, 1, 9, tzinfo=UTC),
                "resolved_at": datetime(2024, 1, 10, tzinfo=UTC),
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            },
        )(),
    )
    resume = make_resume_fixture(
        closed_projection_failures=closed_projection_failures,
    )
    settings = make_settings()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    server.startup()

    response = build_closed_projection_failures_response(
        server,
        resume.workflow_instance.workflow_instance_id,
    )

    assert isinstance(response, ProjectionFailureHistoryResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
        "closed_projection_failures": [
            {
                "projection_type": "resume_json",
                "target_path": ".agent/resume.json",
                "attempt_id": str(attempt_id),
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": "2024-01-09T00:00:00+00:00",
                "resolved_at": "2024-01-10T00:00:00+00:00",
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            }
        ],
    }


def test_build_closed_projection_failures_response_returns_503_when_workflow_service_is_not_initialized() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    response = build_closed_projection_failures_response(server, uuid4())

    assert isinstance(response, ProjectionFailureHistoryResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }


def test_parse_workflow_resume_request_path_returns_uuid_for_valid_path() -> None:
    workflow_instance_id = uuid4()

    assert (
        parse_workflow_resume_request_path(f"/workflow-resume/{workflow_instance_id}")
        == workflow_instance_id
    )
    assert (
        parse_workflow_resume_request_path(
            f"/workflow-resume/{workflow_instance_id}?format=json"
        )
        == workflow_instance_id
    )


def test_parse_workflow_resume_request_path_returns_none_for_invalid_path() -> None:
    assert parse_workflow_resume_request_path("") is None
    assert parse_workflow_resume_request_path("/") is None
    assert parse_workflow_resume_request_path("/workflow-resume") is None
    assert parse_workflow_resume_request_path("/workflow-resume/not-a-uuid") is None
    assert parse_workflow_resume_request_path("/other/endpoint") is None


def test_parse_closed_projection_failures_request_path_returns_uuid_for_valid_path() -> (
    None
):
    workflow_instance_id = uuid4()

    assert (
        parse_closed_projection_failures_request_path(
            f"/workflow-resume/{workflow_instance_id}/closed-projection-failures"
        )
        == workflow_instance_id
    )
    assert (
        parse_closed_projection_failures_request_path(
            f"/workflow-resume/{workflow_instance_id}/closed-projection-failures?format=json"
        )
        == workflow_instance_id
    )


def test_parse_closed_projection_failures_request_path_returns_none_for_invalid_path() -> (
    None
):
    assert parse_closed_projection_failures_request_path("") is None
    assert parse_closed_projection_failures_request_path("/") is None
    assert parse_closed_projection_failures_request_path("/workflow-resume") is None
    assert (
        parse_closed_projection_failures_request_path(
            "/workflow-resume/not-a-uuid/closed-projection-failures"
        )
        is None
    )
    assert (
        parse_closed_projection_failures_request_path("/workflow-resume/not-a-uuid")
        is None
    )
    assert parse_closed_projection_failures_request_path("/other/endpoint") is None


def test_build_workflow_resume_http_handler_returns_success_response() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workflow_resume_http_handler(server)

    server.startup()

    response = handler(
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}"
    )

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_http_handler_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_resume_http_handler(server)

    response = handler("/workflow-resume/not-a-uuid")

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workflow resume endpoint requires /workflow-resume/{workflow_instance_id}",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_http_handler_returns_503_when_server_is_not_ready() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_resume_http_handler(server)

    response = handler(f"/workflow-resume/{uuid4()}")

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_closed_projection_failures_http_handler_returns_success_response() -> (
    None
):
    attempt_id = uuid4()
    closed_projection_failures = (
        type(
            "ClosedProjectionFailure",
            (),
            {
                "projection_type": ProjectionArtifactType.RESUME_JSON,
                "target_path": ".agent/resume.json",
                "attempt_id": attempt_id,
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": datetime(2024, 1, 9, tzinfo=UTC),
                "resolved_at": datetime(2024, 1, 10, tzinfo=UTC),
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            },
        )(),
    )
    resume = make_resume_fixture(
        closed_projection_failures=closed_projection_failures,
    )
    settings = make_settings()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_closed_projection_failures_http_handler(server)

    server.startup()

    response = handler(
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}/closed-projection-failures"
    )

    assert isinstance(response, ProjectionFailureHistoryResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
        "closed_projection_failures": [
            {
                "projection_type": "resume_json",
                "target_path": ".agent/resume.json",
                "attempt_id": str(attempt_id),
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": "2024-01-09T00:00:00+00:00",
                "resolved_at": "2024-01-10T00:00:00+00:00",
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            }
        ],
    }


def test_build_closed_projection_failures_http_handler_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_closed_projection_failures_http_handler(server)

    response = handler("/workflow-resume/not-a-uuid/closed-projection-failures")

    assert isinstance(response, ProjectionFailureHistoryResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "closed projection failures endpoint requires /workflow-resume/{workflow_instance_id}/closed-projection-failures",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_closed_projection_failures_http_handler_returns_503_when_server_is_not_ready() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_closed_projection_failures_http_handler(server)

    response = handler(f"/workflow-resume/{uuid4()}/closed-projection-failures")

    assert isinstance(response, ProjectionFailureHistoryResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_ignore_http_handler_returns_success_response() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    workspace_id = resume.workspace.workspace_id
    workflow_instance_id = resume.workflow_instance.workflow_instance_id
    fake_workflow_service = FakeWorkflowService(
        resume,
        ignore_result=2,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_ignore"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
            "&projection_type=resume_json"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 200
    assert response.payload == {
        "workspace_id": str(workspace_id),
        "workflow_instance_id": str(workflow_instance_id),
        "projection_type": "resume_json",
        "updated_failure_count": 2,
        "status": "ignored",
    }
    assert response.headers == {"content-type": "application/json"}
    assert fake_workflow_service.ignore_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": ProjectionArtifactType.RESUME_JSON,
        }
    ]


def test_build_projection_failures_ignore_http_handler_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/not_projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "projection failure ignore endpoint requires /projection_failures_ignore",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_ignore_http_handler_returns_invalid_request_for_bad_projection_type() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
            "&projection_type=not-a-real-projection"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "projection_type must be a supported projection artifact type",
            "details": {
                "field": "projection_type",
                "allowed_values": ["resume_json", "resume_md"],
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_ignore_http_handler_returns_invalid_request_for_missing_workspace_id() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_ignore"
            f"?workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workspace_id must be a non-empty string",
            "details": {"field": "workspace_id"},
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_ignore_http_handler_returns_not_found_for_service_not_found_error() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    def raise_not_found(
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        raise RuntimeError("workflow not found")

    fake_workflow_service.ignore_resume_projection_failures = raise_not_found
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workflow not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_ignore_http_handler_returns_invalid_request_for_workspace_mismatch_error() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    def raise_workspace_mismatch(
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        raise RuntimeError("workflow instance does not belong to workspace")

    fake_workflow_service.ignore_resume_projection_failures = raise_workspace_mismatch
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow instance does not belong to workspace",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_ignore_http_handler_returns_server_error_for_unmapped_service_error() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    def raise_generic_error(
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        raise RuntimeError("projection storage exploded")

    fake_workflow_service.ignore_resume_projection_failures = raise_generic_error
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 500
    assert response.payload == {
        "error": {
            "code": "server_error",
            "message": "projection storage exploded",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_resolve_http_handler_returns_success_response() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    workspace_id = resume.workspace.workspace_id
    workflow_instance_id = resume.workflow_instance.workflow_instance_id
    fake_workflow_service = FakeWorkflowService(
        resume,
        resolve_result=3,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_resolve"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 200
    assert response.payload == {
        "workspace_id": str(workspace_id),
        "workflow_instance_id": str(workflow_instance_id),
        "projection_type": None,
        "updated_failure_count": 3,
        "status": "resolved",
    }
    assert response.headers == {"content-type": "application/json"}
    assert fake_workflow_service.resolve_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": None,
        }
    ]


def test_build_projection_failures_resolve_http_handler_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/not_projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "projection failure resolve endpoint requires /projection_failures_resolve",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_resolve_http_handler_returns_invalid_request_for_bad_workflow_id() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            "&workflow_instance_id=not-a-uuid"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a valid UUID",
            "details": {"field": "workflow_instance_id"},
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_resolve_http_handler_returns_invalid_request_for_bad_projection_type() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
            "&projection_type=not-a-real-projection"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "projection_type must be a supported projection artifact type",
            "details": {
                "field": "projection_type",
                "allowed_values": ["resume_json", "resume_md"],
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_resolve_http_handler_returns_not_found_for_service_not_found_error() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    def raise_not_found(
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        raise RuntimeError("workflow not found")

    fake_workflow_service.resolve_resume_projection_failures = raise_not_found
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workflow not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_resolve_http_handler_returns_invalid_request_for_workspace_mismatch_error() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    def raise_workspace_mismatch(
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        raise RuntimeError("workflow instance does not belong to workspace")

    fake_workflow_service.resolve_resume_projection_failures = raise_workspace_mismatch
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow instance does not belong to workspace",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_projection_failures_resolve_http_handler_returns_server_error_for_unmapped_service_error() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    def raise_generic_error(
        *,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: object = None,
    ) -> int:
        raise RuntimeError("projection storage exploded")

    fake_workflow_service.resolve_resume_projection_failures = raise_generic_error
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_http_handler(server)

    server.startup()

    response = handler(
        (
            "/projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.status_code == 500
    assert response.payload == {
        "error": {
            "code": "server_error",
            "message": "projection storage exploded",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_runtime_adapter_dispatches_registered_workflow_resume_handler() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = HttpRuntimeAdapter(settings)
    runtime.register_handler(
        "workflow_resume",
        build_workflow_resume_http_handler(server),
    )

    server.startup()

    response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)
    assert response.headers == {"content-type": "application/json"}
    assert runtime.handler("workflow_resume") is not None
    assert runtime.registered_routes() == ("workflow_resume",)


def test_http_runtime_adapter_returns_404_for_unregistered_route() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)

    response = runtime.dispatch("missing_route", f"/workflow-resume/{uuid4()}")

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "route_not_found",
            "message": "no HTTP handler is registered for route 'missing_route'",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_http_runtime_adapter_registers_workflow_resume_route() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    assert isinstance(runtime, HttpRuntimeAdapter)
    assert runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )

    server.startup()

    response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)


def test_http_mcp_route_supports_initialize_over_http() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        (
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{'
            '"protocolVersion":"2024-11-05",'
            '"capabilities":{},'
            '"clientInfo":{"name":"test-client","version":"0.1.0"}'
            "}}"
        ),
    )

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ctxledger",
                "version": settings.app_version,
            },
            "capabilities": {
                "tools": {},
                "resources": {},
            },
        },
    }


def test_http_mcp_route_supports_tools_list_over_http() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
    )

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}

    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 2
    tools = response.payload["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]

    assert tool_names == [
        "memory_get_context",
        "memory_remember_episode",
        "memory_search",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "workflow_checkpoint",
        "workflow_complete",
        "workflow_resume",
        "workflow_start",
        "workspace_register",
    ]

    workspace_register_tool = next(
        tool for tool in tools if tool["name"] == "workspace_register"
    )
    assert workspace_register_tool["inputSchema"] == {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "minLength": 1,
                "description": "Repository URL for the workspace.",
            },
            "canonical_path": {
                "type": "string",
                "minLength": 1,
                "description": "Canonical local filesystem path for the workspace checkout.",
            },
            "default_branch": {
                "type": "string",
                "minLength": 1,
                "description": "Default branch name for the workspace repository.",
            },
            "workspace_id": {
                "type": "string",
                "format": "uuid",
                "description": "Existing workspace identity for explicit update operations.",
            },
            "metadata": {
                "type": "object",
                "description": "Optional workspace metadata.",
                "additionalProperties": True,
            },
        },
        "required": ["repo_url", "canonical_path", "default_branch"],
        "additionalProperties": False,
    }


def test_http_mcp_route_supports_tools_call_over_http() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        (
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{'
            '"name":"workflow_resume",'
            f'"arguments":{{"workflow_instance_id":"{resume.workflow_instance.workflow_instance_id}"}}'
            "}}"
        ),
    )

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 3

    content = response.payload["result"]["content"]
    assert content[0]["type"] == "text"
    assert '"ok": true' in content[0]["text"]
    assert str(resume.workflow_instance.workflow_instance_id) in content[0]["text"]


def test_http_mcp_route_requires_json_rpc_body() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch("mcp_rpc", "/mcp")

    assert response.status_code == 400
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "HTTP MCP endpoint requires a JSON-RPC request body",
        }
    }


def test_http_mcp_route_requires_configured_mcp_path() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "mcp_rpc",
        "/not-mcp",
        '{"jsonrpc":"2.0","id":4,"method":"tools/list","params":{}}',
    )

    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "MCP endpoint requires /mcp",
        }
    }


def test_http_mcp_route_requires_bearer_token_when_auth_is_enabled() -> None:
    settings = make_settings(
        auth_bearer_token="secret-token",
        require_auth=True,
    )
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    missing_token_response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        '{"jsonrpc":"2.0","id":5,"method":"tools/list","params":{}}',
    )
    invalid_token_response = runtime.dispatch(
        "mcp_rpc",
        "/mcp?authorization=Bearer wrong-token",
        '{"jsonrpc":"2.0","id":6,"method":"tools/list","params":{}}',
    )
    valid_token_response = runtime.dispatch(
        "mcp_rpc",
        "/mcp?authorization=Bearer secret-token",
        '{"jsonrpc":"2.0","id":7,"method":"tools/list","params":{}}',
    )

    expected_auth_headers = {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert missing_token_response.status_code == 401
    assert missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert missing_token_response.headers == expected_auth_headers

    assert invalid_token_response.status_code == 401
    assert invalid_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "invalid bearer token",
        }
    }
    assert invalid_token_response.headers == expected_auth_headers

    assert valid_token_response.status_code == 200
    assert valid_token_response.headers == {"content-type": "application/json"}
    assert valid_token_response.payload["result"]["tools"]


def test_http_runtime_adapter_dispatches_registered_closed_projection_failures_handler() -> (
    None
):
    attempt_id = uuid4()
    closed_projection_failures = (
        type(
            "ClosedProjectionFailure",
            (),
            {
                "projection_type": ProjectionArtifactType.RESUME_JSON,
                "target_path": ".agent/resume.json",
                "attempt_id": attempt_id,
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": datetime(2024, 1, 9, tzinfo=UTC),
                "resolved_at": datetime(2024, 1, 10, tzinfo=UTC),
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            },
        )(),
    )
    resume = make_resume_fixture(
        closed_projection_failures=closed_projection_failures,
    )
    settings = make_settings()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "workflow_closed_projection_failures",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}/closed-projection-failures",
    )

    assert response.status_code == 200
    assert response.payload == {
        "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
        "closed_projection_failures": [
            {
                "projection_type": "resume_json",
                "target_path": ".agent/resume.json",
                "attempt_id": str(attempt_id),
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": "2024-01-09T00:00:00+00:00",
                "resolved_at": "2024-01-10T00:00:00+00:00",
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            }
        ],
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_workflow_resume_route_requires_bearer_token_when_auth_is_enabled() -> (
    None
):
    settings = make_settings(
        auth_bearer_token="secret-token",
        require_auth=True,
    )
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    assert isinstance(runtime, HttpRuntimeAdapter)
    assert runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )

    server.startup()

    missing_token_response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )
    invalid_token_response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}?authorization=Bearer wrong-token",
    )
    valid_token_response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}?authorization=Bearer secret-token",
    )

    assert missing_token_response.status_code == 401
    assert missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert missing_token_response.headers == {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert invalid_token_response.status_code == 401
    assert invalid_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "invalid bearer token",
        }
    }
    assert invalid_token_response.headers == {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert valid_token_response.status_code == 200
    assert valid_token_response.payload == serialize_workflow_resume(resume)


def test_http_closed_projection_failures_route_requires_bearer_token_when_auth_is_enabled() -> (
    None
):
    attempt_id = uuid4()
    closed_projection_failures = (
        type(
            "ClosedProjectionFailure",
            (),
            {
                "projection_type": ProjectionArtifactType.RESUME_JSON,
                "target_path": ".agent/resume.json",
                "attempt_id": attempt_id,
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": datetime(2024, 1, 9, tzinfo=UTC),
                "resolved_at": datetime(2024, 1, 10, tzinfo=UTC),
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            },
        )(),
    )
    resume = make_resume_fixture(
        closed_projection_failures=closed_projection_failures,
    )
    settings = make_settings(
        auth_bearer_token="secret-token",
        require_auth=True,
    )
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    missing_token_response = runtime.dispatch(
        "workflow_closed_projection_failures",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}/closed-projection-failures",
    )
    invalid_token_response = runtime.dispatch(
        "workflow_closed_projection_failures",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}/closed-projection-failures?authorization=Bearer wrong-token",
    )
    valid_token_response = runtime.dispatch(
        "workflow_closed_projection_failures",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}/closed-projection-failures?authorization=Bearer secret-token",
    )

    assert missing_token_response.status_code == 401
    assert missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert missing_token_response.headers == {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert invalid_token_response.status_code == 401
    assert invalid_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "invalid bearer token",
        }
    }
    assert invalid_token_response.headers == {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert valid_token_response.status_code == 200
    assert valid_token_response.payload == {
        "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
        "closed_projection_failures": [
            {
                "projection_type": "resume_json",
                "target_path": ".agent/resume.json",
                "attempt_id": str(attempt_id),
                "error_code": "EACCES",
                "error_message": "permission denied",
                "occurred_at": "2024-01-09T00:00:00+00:00",
                "resolved_at": "2024-01-10T00:00:00+00:00",
                "open_failure_count": 0,
                "retry_count": 2,
                "status": "ignored",
            }
        ],
    }


def test_http_projection_failures_ignore_route_requires_bearer_token_when_auth_is_enabled() -> (
    None
):
    settings = make_settings(
        auth_bearer_token="secret-token",
        require_auth=True,
    )
    resume = make_resume_fixture()
    workspace_id = resume.workspace.workspace_id
    workflow_instance_id = resume.workflow_instance.workflow_instance_id
    fake_workflow_service = FakeWorkflowService(
        resume,
        ignore_result=2,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    missing_token_response = runtime.dispatch(
        "projection_failures_ignore",
        (
            "/projection_failures_ignore"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
            "&projection_type=resume_json"
        ),
    )
    invalid_token_response = runtime.dispatch(
        "projection_failures_ignore",
        (
            "/projection_failures_ignore"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
            "&projection_type=resume_json"
            "&authorization=Bearer wrong-token"
        ),
    )
    valid_token_response = runtime.dispatch(
        "projection_failures_ignore",
        (
            "/projection_failures_ignore"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
            "&projection_type=resume_json"
            "&authorization=Bearer secret-token"
        ),
    )

    expected_auth_headers = {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert missing_token_response.status_code == 401
    assert missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert missing_token_response.headers == expected_auth_headers

    assert invalid_token_response.status_code == 401
    assert invalid_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "invalid bearer token",
        }
    }
    assert invalid_token_response.headers == expected_auth_headers

    assert valid_token_response.status_code == 200
    assert isinstance(valid_token_response, ProjectionFailureActionResponse)
    assert valid_token_response.payload == {
        "workspace_id": str(workspace_id),
        "workflow_instance_id": str(workflow_instance_id),
        "projection_type": "resume_json",
        "updated_failure_count": 2,
        "status": "ignored",
    }
    assert fake_workflow_service.ignore_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": ProjectionArtifactType.RESUME_JSON,
        }
    ]


def test_http_projection_failures_ignore_route_returns_invalid_request_for_bad_projection_type() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "projection_failures_ignore",
        (
            "/projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
            "&projection_type=not-a-real-projection"
        ),
    )

    assert response.status_code == 400
    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "projection_type must be a supported projection artifact type",
            "details": {
                "field": "projection_type",
                "allowed_values": ["resume_json", "resume_md"],
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_projection_failures_ignore_route_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "projection_failures_ignore",
        (
            "/not_projection_failures_ignore"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        ),
    )

    assert response.status_code == 404
    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "projection failure ignore endpoint requires /projection_failures_ignore",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_projection_failures_ignore_route_returns_server_not_ready_error() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    runtime = build_http_runtime_adapter(server)

    response = runtime.dispatch(
        "projection_failures_ignore",
        (
            "/projection_failures_ignore"
            f"?workspace_id={uuid4()}"
            f"&workflow_instance_id={uuid4()}"
        ),
    )

    assert response.status_code == 503
    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_projection_failures_resolve_route_requires_bearer_token_when_auth_is_enabled() -> (
    None
):
    settings = make_settings(
        auth_bearer_token="secret-token",
        require_auth=True,
    )
    resume = make_resume_fixture()
    workspace_id = resume.workspace.workspace_id
    workflow_instance_id = resume.workflow_instance.workflow_instance_id
    fake_workflow_service = FakeWorkflowService(
        resume,
        resolve_result=3,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    missing_token_response = runtime.dispatch(
        "projection_failures_resolve",
        (
            "/projection_failures_resolve"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
        ),
    )
    invalid_token_response = runtime.dispatch(
        "projection_failures_resolve",
        (
            "/projection_failures_resolve"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
            "&authorization=Bearer wrong-token"
        ),
    )
    valid_token_response = runtime.dispatch(
        "projection_failures_resolve",
        (
            "/projection_failures_resolve"
            f"?workspace_id={workspace_id}"
            f"&workflow_instance_id={workflow_instance_id}"
            "&authorization=Bearer secret-token"
        ),
    )

    expected_auth_headers = {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert missing_token_response.status_code == 401
    assert missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert missing_token_response.headers == expected_auth_headers

    assert invalid_token_response.status_code == 401
    assert invalid_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "invalid bearer token",
        }
    }
    assert invalid_token_response.headers == expected_auth_headers

    assert valid_token_response.status_code == 200
    assert isinstance(valid_token_response, ProjectionFailureActionResponse)
    assert valid_token_response.payload == {
        "workspace_id": str(workspace_id),
        "workflow_instance_id": str(workflow_instance_id),
        "projection_type": None,
        "updated_failure_count": 3,
        "status": "resolved",
    }
    assert fake_workflow_service.resolve_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": None,
        }
    ]


def test_http_projection_failures_resolve_route_returns_invalid_request_for_bad_workflow_id() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "projection_failures_resolve",
        (
            "/projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            "&workflow_instance_id=not-a-uuid"
        ),
    )

    assert response.status_code == 400
    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a valid UUID",
            "details": {"field": "workflow_instance_id"},
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_projection_failures_resolve_route_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    server.startup()

    response = runtime.dispatch(
        "projection_failures_resolve",
        (
            "/not_projection_failures_resolve"
            f"?workspace_id={resume.workspace.workspace_id}"
            f"&workflow_instance_id={resume.workflow_instance.workflow_instance_id}"
        ),
    )

    assert response.status_code == 404
    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "projection failure resolve endpoint requires /projection_failures_resolve",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_projection_failures_resolve_route_returns_server_not_ready_error() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )

    runtime = build_http_runtime_adapter(server)

    response = runtime.dispatch(
        "projection_failures_resolve",
        (
            "/projection_failures_resolve"
            f"?workspace_id={uuid4()}"
            f"&workflow_instance_id={uuid4()}"
        ),
    )

    assert response.status_code == 503
    assert isinstance(response, ProjectionFailureActionResponse)
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_http_debug_routes_require_bearer_token_when_auth_is_enabled() -> None:
    settings = make_settings(
        auth_bearer_token="secret-token",
        require_auth=True,
    )
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )

    runtime_introspection_missing_token_response = server.runtime.dispatch(
        "runtime_introspection",
        "/debug/runtime",
    )
    runtime_introspection_valid_token_response = server.runtime.dispatch(
        "runtime_introspection",
        "/debug/runtime?authorization=Bearer secret-token",
    )

    runtime_routes_missing_token_response = server.runtime.dispatch(
        "runtime_routes",
        "/debug/routes",
    )
    runtime_routes_valid_token_response = server.runtime.dispatch(
        "runtime_routes",
        "/debug/routes?authorization=Bearer secret-token",
    )

    runtime_tools_missing_token_response = server.runtime.dispatch(
        "runtime_tools",
        "/debug/tools",
    )
    runtime_tools_valid_token_response = server.runtime.dispatch(
        "runtime_tools",
        "/debug/tools?authorization=Bearer secret-token",
    )

    expected_auth_headers = {
        "content-type": "application/json",
        "www-authenticate": 'Bearer realm="ctxledger"',
    }

    assert runtime_introspection_missing_token_response.status_code == 401
    assert runtime_introspection_missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert runtime_introspection_missing_token_response.headers == expected_auth_headers
    assert runtime_introspection_valid_token_response.status_code == 200

    assert runtime_routes_missing_token_response.status_code == 401
    assert runtime_routes_missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert runtime_routes_missing_token_response.headers == expected_auth_headers
    assert runtime_routes_valid_token_response.status_code == 200

    assert runtime_tools_missing_token_response.status_code == 401
    assert runtime_tools_missing_token_response.payload == {
        "error": {
            "code": "authentication_error",
            "message": "missing bearer token",
        }
    }
    assert runtime_tools_missing_token_response.headers == expected_auth_headers
    assert runtime_tools_valid_token_response.status_code == 200


def test_create_server_wires_http_runtime_with_workflow_resume_route() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)

    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )

    server.startup()

    response = server.runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)


def test_create_server_returns_http_runtime_by_default() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)


def test_build_resume_workflow_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_resume_workflow_tool_handler(server)

    server.startup()

    response = handler(
        {"workflow_instance_id": str(resume.workflow_instance.workflow_instance_id)}
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is True
    assert response.payload["result"]["workflow"]["workflow_instance_id"] == str(
        resume.workflow_instance.workflow_instance_id
    )


def test_build_resume_workflow_tool_handler_returns_invalid_request_for_missing_id() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_resume_workflow_tool_handler(server)

    response = handler({})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a non-empty string",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_resume_workflow_tool_handler_returns_invalid_request_for_bad_uuid() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_resume_workflow_tool_handler(server)

    response = handler({"workflow_instance_id": "not-a-uuid"})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a valid UUID",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_resume_workflow_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_resume_workflow_tool_handler(server)

    response = handler({"workflow_instance_id": str(uuid4())})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workspace_register_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    registered_workspace = replace(
        resume.workspace,
        repo_url="https://example.com/registered.git",
        canonical_path="/tmp/registered",
        default_branch="main",
        metadata={"team": "platform"},
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        register_workspace_result=registered_workspace,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workspace_register_tool_handler(server)

    server.startup()

    response = handler(
        {
            "repo_url": registered_workspace.repo_url,
            "canonical_path": registered_workspace.canonical_path,
            "default_branch": registered_workspace.default_branch,
            "metadata": {"team": "platform"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(registered_workspace.workspace_id),
            "repo_url": registered_workspace.repo_url,
            "canonical_path": registered_workspace.canonical_path,
            "default_branch": registered_workspace.default_branch,
            "metadata": registered_workspace.metadata,
            "created_at": registered_workspace.created_at.isoformat(),
            "updated_at": registered_workspace.updated_at.isoformat(),
        },
    }
    assert fake_workflow_service.register_workspace_calls == [
        RegisterWorkspaceInput(
            workspace_id=None,
            repo_url=registered_workspace.repo_url,
            canonical_path=registered_workspace.canonical_path,
            default_branch=registered_workspace.default_branch,
            metadata={"team": "platform"},
        )
    ]


def test_build_workspace_register_tool_handler_returns_invalid_request_for_missing_repo_url() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workspace_register_tool_handler(server)

    response = handler(
        {
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "repo_url must be a non-empty string",
            "details": {"field": "repo_url"},
        },
    }


def test_build_workspace_register_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workspace_register_tool_handler(server)

    response = handler(
        {
            "repo_url": "https://example.com/repo.git",
            "canonical_path": "/tmp/repo",
            "default_branch": "main",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workflow_start_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(
        resume,
        start_workflow_result=type(
            "WorkflowStartResultStub",
            (),
            {
                "workflow_instance": resume.workflow_instance,
                "attempt": resume.attempt,
            },
        )(),
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workflow_start_tool_handler(server)

    server.startup()

    response = handler(
        {
            "workspace_id": str(resume.workspace.workspace_id),
            "ticket_id": resume.workflow_instance.ticket_id,
            "metadata": {"priority": "high"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "workspace_id": str(resume.workflow_instance.workspace_id),
            "ticket_id": resume.workflow_instance.ticket_id,
            "workflow_status": resume.workflow_instance.status.value,
            "attempt_status": resume.attempt.status.value,
            "created_at": resume.workflow_instance.created_at.isoformat(),
        },
    }
    assert fake_workflow_service.start_workflow_calls == [
        StartWorkflowInput(
            workspace_id=resume.workspace.workspace_id,
            ticket_id=resume.workflow_instance.ticket_id,
            metadata={"priority": "high"},
        )
    ]


def test_build_workflow_start_tool_handler_returns_invalid_request_for_bad_workspace_id() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_start_tool_handler(server)

    response = handler(
        {
            "workspace_id": "not-a-uuid",
            "ticket_id": "SRV-123",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workspace_id must be a valid UUID",
            "details": {"field": "workspace_id"},
        },
    }


def test_build_workflow_start_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_start_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "ticket_id": "SRV-123",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workflow_checkpoint_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(
        resume,
        create_checkpoint_result=type(
            "WorkflowCheckpointResultStub",
            (),
            {
                "checkpoint": resume.latest_checkpoint,
                "workflow_instance": resume.workflow_instance,
                "attempt": resume.attempt,
                "verify_report": resume.latest_verify_report,
            },
        )(),
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workflow_checkpoint_tool_handler(server)

    server.startup()

    response = handler(
        {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "step_name": resume.latest_checkpoint.step_name,
            "summary": resume.latest_checkpoint.summary,
            "checkpoint_json": resume.latest_checkpoint.checkpoint_json,
            "verify_status": resume.latest_verify_report.status.value,
            "verify_report": resume.latest_verify_report.report_json,
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "checkpoint_id": str(resume.latest_checkpoint.checkpoint_id),
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "step_name": resume.latest_checkpoint.step_name,
            "created_at": resume.latest_checkpoint.created_at.isoformat(),
            "latest_verify_status": resume.latest_verify_report.status.value,
        },
    }
    assert fake_workflow_service.create_checkpoint_calls == [
        CreateCheckpointInput(
            workflow_instance_id=resume.workflow_instance.workflow_instance_id,
            attempt_id=resume.attempt.attempt_id,
            step_name=resume.latest_checkpoint.step_name,
            summary=resume.latest_checkpoint.summary,
            checkpoint_json=resume.latest_checkpoint.checkpoint_json,
            verify_status=resume.latest_verify_report.status,
            verify_report=resume.latest_verify_report.report_json,
        )
    ]


def test_build_workflow_checkpoint_tool_handler_returns_invalid_request_for_missing_step_name() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_checkpoint_tool_handler(server)

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "step_name must be a non-empty string",
            "details": {"field": "step_name"},
        },
    }


def test_build_workflow_checkpoint_tool_handler_returns_server_not_ready_error() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_checkpoint_tool_handler(server)

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "step_name": "implement_server_api",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_workflow_complete_tool_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    finished_attempt = replace(
        resume.attempt,
        status=WorkflowAttemptStatus.SUCCEEDED,
        finished_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    completed_workflow = replace(
        resume.workflow_instance,
        status=WorkflowInstanceStatus.COMPLETED,
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        complete_workflow_result=type(
            "WorkflowCompleteResultStub",
            (),
            {
                "workflow_instance": completed_workflow,
                "attempt": finished_attempt,
                "verify_report": resume.latest_verify_report,
            },
        )(),
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workflow_complete_tool_handler(server)

    server.startup()

    response = handler(
        {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "attempt_id": str(resume.attempt.attempt_id),
            "workflow_status": WorkflowInstanceStatus.COMPLETED.value,
            "summary": "Completed successfully",
            "verify_status": VerifyStatus.PASSED.value,
            "verify_report": {"checks": ["pytest"], "status": "passed"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workflow_instance_id": str(completed_workflow.workflow_instance_id),
            "attempt_id": str(finished_attempt.attempt_id),
            "workflow_status": completed_workflow.status.value,
            "attempt_status": finished_attempt.status.value,
            "finished_at": finished_attempt.finished_at.isoformat(),
            "latest_verify_status": resume.latest_verify_report.status.value,
        },
    }
    assert fake_workflow_service.complete_workflow_calls == [
        CompleteWorkflowInput(
            workflow_instance_id=resume.workflow_instance.workflow_instance_id,
            attempt_id=resume.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed successfully",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
            failure_reason=None,
        )
    ]


def test_build_workflow_complete_tool_handler_returns_invalid_request_for_bad_status() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_complete_tool_handler(server)

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": "not-a-real-status",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_status must be a supported workflow status",
            "details": {
                "field": "workflow_status",
                "allowed_values": ["running", "completed", "failed", "cancelled"],
            },
        },
    }


def test_build_workflow_complete_tool_handler_returns_server_not_ready_error() -> None:
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_complete_tool_handler(server)

    response = handler(
        {
            "workflow_instance_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "workflow_status": WorkflowInstanceStatus.COMPLETED.value,
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_projection_failures_ignore_tool_handler_returns_success_payload() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    workspace_id = resume.workspace.workspace_id
    workflow_instance_id = resume.workflow_instance.workflow_instance_id
    fake_workflow_service = FakeWorkflowService(
        resume,
        ignore_result=2,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_ignore_tool_handler(server)

    server.startup()

    response = handler(
        {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
            "projection_type": "resume_json",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
            "projection_type": "resume_json",
            "updated_failure_count": 2,
            "status": "ignored",
        },
    }
    assert fake_workflow_service.ignore_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": ProjectionArtifactType.RESUME_JSON,
        }
    ]


def test_build_projection_failures_ignore_tool_handler_returns_invalid_request_for_missing_workspace_id() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_ignore_tool_handler(server)

    response = handler({"workflow_instance_id": str(uuid4())})

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workspace_id must be a non-empty string",
            "details": {"field": "workspace_id"},
        },
    }


def test_build_projection_failures_ignore_tool_handler_returns_invalid_request_for_bad_workflow_id() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_ignore_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": "not-a-uuid",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a valid UUID",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_projection_failures_ignore_tool_handler_returns_invalid_request_for_bad_projection_type() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_ignore_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
            "projection_type": "not-a-real-projection",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "projection_type must be a supported projection artifact type",
            "details": {
                "field": "projection_type",
                "allowed_values": ["resume_json", "resume_md"],
            },
        },
    }


def test_build_projection_failures_ignore_tool_handler_returns_server_not_ready_error() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_ignore_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_projection_failures_resolve_tool_handler_returns_success_payload() -> (
    None
):
    settings = make_settings()
    resume = make_resume_fixture()
    workspace_id = resume.workspace.workspace_id
    workflow_instance_id = resume.workflow_instance.workflow_instance_id
    fake_workflow_service = FakeWorkflowService(
        resume,
        resolve_result=3,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_projection_failures_resolve_tool_handler(server)

    server.startup()

    response = handler(
        {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": True,
        "result": {
            "workspace_id": str(workspace_id),
            "workflow_instance_id": str(workflow_instance_id),
            "projection_type": None,
            "updated_failure_count": 3,
            "status": "resolved",
        },
    }
    assert fake_workflow_service.resolve_calls == [
        {
            "workspace_id": workspace_id,
            "workflow_instance_id": workflow_instance_id,
            "projection_type": None,
        }
    ]


def test_build_projection_failures_resolve_tool_handler_returns_invalid_request_for_bad_workflow_id() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_resolve_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": "not-a-uuid",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "workflow_instance_id must be a valid UUID",
            "details": {"field": "workflow_instance_id"},
        },
    }


def test_build_projection_failures_resolve_tool_handler_returns_server_not_ready_error() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_resolve_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
            "details": {},
        },
    }


def test_build_projection_failures_resolve_tool_handler_returns_invalid_request_for_bad_projection_type() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_projection_failures_resolve_tool_handler(server)

    response = handler(
        {
            "workspace_id": str(uuid4()),
            "workflow_instance_id": str(uuid4()),
            "projection_type": "not-a-real-projection",
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload == {
        "ok": False,
        "error": {
            "code": "invalid_request",
            "message": "projection_type must be a supported projection artifact type",
            "details": {
                "field": "projection_type",
                "allowed_values": ["resume_json", "resume_md"],
            },
        },
    }


def test_build_memory_remember_episode_tool_handler_returns_stub_payload() -> None:
    handler = build_memory_remember_episode_tool_handler(MemoryService())

    response = handler(
        {
            "workflow_instance_id": "wf-123",
            "summary": "Capture useful implementation notes",
            "attempt_id": "attempt-1",
            "metadata": {"source": "agent"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_remember_episode"
    assert response.payload["result"]["implemented"] is False


def test_build_memory_remember_episode_tool_handler_returns_invalid_request() -> None:
    handler = build_memory_remember_episode_tool_handler(MemoryService())

    response = handler({"workflow_instance_id": "", "summary": ""})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_build_memory_search_tool_handler_returns_stub_payload() -> None:
    handler = build_memory_search_tool_handler(MemoryService())

    response = handler(
        {
            "query": "projection drift",
            "workspace_id": "workspace-1",
            "limit": 5,
            "filters": {"kind": "summary"},
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_search"
    assert response.payload["result"]["implemented"] is False


def test_build_memory_search_tool_handler_returns_invalid_request() -> None:
    handler = build_memory_search_tool_handler(MemoryService())

    response = handler({"query": "", "limit": 0})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_build_memory_get_context_tool_handler_returns_stub_payload() -> None:
    handler = build_memory_get_context_tool_handler(MemoryService())

    response = handler(
        {
            "workflow_instance_id": "wf-123",
            "limit": 3,
            "include_episodes": True,
            "include_memory_items": False,
            "include_summaries": True,
        }
    )

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_get_context"
    assert response.payload["result"]["implemented"] is False


def test_build_memory_get_context_tool_handler_returns_invalid_request() -> None:
    handler = build_memory_get_context_tool_handler(MemoryService())

    response = handler({})

    assert isinstance(response, McpToolResponse)
    assert response.payload["ok"] is False
    assert response.payload["error"]["code"] == "memory_invalid_request"


def test_http_mcp_rpc_initialize_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ctxledger",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
                "resources": {},
            },
        },
    }


def test_http_mcp_rpc_tools_list_returns_registered_tools_with_input_schemas() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    result = response.payload["result"]
    tools = {tool["name"]: tool for tool in result["tools"]}

    assert "workspace_register" in tools
    assert tools["workspace_register"]["inputSchema"]["required"] == [
        "repo_url",
        "canonical_path",
        "default_branch",
    ]
    assert (
        tools["workflow_start"]["inputSchema"]["properties"]["workspace_id"]["format"]
        == "uuid"
    )
    assert (
        tools["memory_get_context"]["inputSchema"]["properties"]["include_summaries"][
            "type"
        ]
        == "boolean"
    )


def test_http_mcp_rpc_tools_call_returns_workspace_register_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    registered_workspace = replace(
        resume.workspace,
        repo_url="https://example.com/registered.git",
        canonical_path="/tmp/registered",
        default_branch="main",
        metadata={"team": "platform"},
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        register_workspace_result=registered_workspace,
    )
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)
    server.startup()

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "workspace_register",
                    "arguments": {
                        "repo_url": registered_workspace.repo_url,
                        "canonical_path": registered_workspace.canonical_path,
                        "default_branch": registered_workspace.default_branch,
                        "metadata": {"team": "platform"},
                    },
                },
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "ok": True,
                            "result": {
                                "workspace_id": str(registered_workspace.workspace_id),
                                "repo_url": registered_workspace.repo_url,
                                "canonical_path": registered_workspace.canonical_path,
                                "default_branch": registered_workspace.default_branch,
                                "metadata": registered_workspace.metadata,
                                "created_at": registered_workspace.created_at.isoformat(),
                                "updated_at": registered_workspace.updated_at.isoformat(),
                            },
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        },
    }


def test_http_mcp_rpc_resources_list_returns_registered_resources() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/list",
                "params": {},
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 4,
        "result": {
            "resources": [
                {
                    "uri": "workspace://{workspace_id}/resume",
                    "name": "workspace://{workspace_id}/resume",
                    "description": "workspace://{workspace_id}/resume resource",
                },
                {
                    "uri": "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                    "name": "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                    "description": (
                        "workspace://{workspace_id}/workflow/"
                        "{workflow_instance_id} resource"
                    ),
                },
            ]
        },
    }


def test_http_mcp_rpc_resources_read_returns_workspace_resume_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )

    runtime = build_http_runtime_adapter(server)
    server.startup()

    uri = f"workspace://{resume.workspace.workspace_id}/resume"
    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "resources/read",
                "params": {
                    "uri": uri,
                },
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 5,
        "result": {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(
                        {
                            "uri": uri,
                            "resource": serialize_workflow_resume(resume),
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        },
    }


def test_dispatch_http_request_returns_dispatch_result_for_success() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    result = dispatch_http_request(
        runtime,
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert isinstance(result, RuntimeDispatchResult)
    assert result.transport == "http"
    assert result.target == "workflow_resume"
    assert result.status == "ok"
    assert isinstance(result.response, WorkflowResumeResponse)
    assert result.response.status_code == 200
    assert result.response.payload == serialize_workflow_resume(resume)


def test_dispatch_http_request_returns_route_not_found_result() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)

    result = dispatch_http_request(
        runtime,
        "missing_route",
        f"/workflow-resume/{uuid4()}",
    )

    assert isinstance(result, RuntimeDispatchResult)
    assert result.transport == "http"
    assert result.target == "missing_route"
    assert result.status == "route_not_found"
    assert isinstance(result.response, WorkflowResumeResponse)
    assert result.response.status_code == 404
    assert result.response.payload == {
        "error": {
            "code": "route_not_found",
            "message": "no HTTP handler is registered for route 'missing_route'",
        }
    }


def test_dispatch_http_request_returns_error_result_for_handler_error_response() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    runtime = build_http_runtime_adapter(server)

    result = dispatch_http_request(
        runtime,
        "workflow_resume",
        f"/workflow-resume/{uuid4()}",
    )

    assert isinstance(result, RuntimeDispatchResult)
    assert result.transport == "http"
    assert result.target == "workflow_resume"
    assert result.status == "error"
    assert isinstance(result.response, WorkflowResumeResponse)
    assert result.response.status_code == 503
    assert result.response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }


def test_http_runtime_adapter_introspect_returns_registered_routes() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)
    runtime.register_handler(
        "workflow_resume",
        lambda path: WorkflowResumeResponse(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    introspection = runtime.introspect()

    assert isinstance(introspection, RuntimeIntrospection)
    assert introspection.transport == "http"
    assert introspection.routes == ("workflow_resume",)
    assert introspection.tools == (
        "memory_get_context",
        "memory_remember_episode",
        "memory_search",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "workflow_checkpoint",
        "workflow_complete",
        "workflow_resume",
        "workflow_start",
        "workspace_register",
    )
    assert introspection.resources == (
        "workspace://{workspace_id}/resume",
        "workspace://{workspace_id}/workflow/{workflow_instance_id}",
    )


def test_parse_workspace_resume_resource_uri_returns_workspace_id_for_valid_uri() -> (
    None
):
    workspace_id = uuid4()

    assert (
        parse_workspace_resume_resource_uri(f"workspace://{workspace_id}/resume")
        == workspace_id
    )


def test_parse_workspace_resume_resource_uri_returns_none_for_invalid_uri() -> None:
    assert parse_workspace_resume_resource_uri("") is None
    assert parse_workspace_resume_resource_uri("workspace://not-a-uuid/resume") is None
    assert parse_workspace_resume_resource_uri("workspace://abc/workflow") is None
    assert parse_workspace_resume_resource_uri("memory://episode/123") is None


def test_parse_workflow_detail_resource_uri_returns_ids_for_valid_uri() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    assert parse_workflow_detail_resource_uri(
        f"workspace://{workspace_id}/workflow/{workflow_instance_id}"
    ) == (workspace_id, workflow_instance_id)


def test_parse_workflow_detail_resource_uri_returns_none_for_invalid_uri() -> None:
    workspace_id = uuid4()

    assert parse_workflow_detail_resource_uri("") is None
    assert (
        parse_workflow_detail_resource_uri(
            f"workspace://{workspace_id}/workflow/not-a-uuid"
        )
        is None
    )
    assert (
        parse_workflow_detail_resource_uri(f"workspace://not-a-uuid/workflow/{uuid4()}")
        is None
    )
    assert parse_workflow_detail_resource_uri("workspace://abc/resume") is None


def test_build_workspace_resume_resource_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workspace_resume_resource_handler(server)

    server.startup()

    response = handler(f"workspace://{resume.workspace.workspace_id}/resume")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{resume.workspace.workspace_id}/resume",
        "resource": serialize_workflow_resume(resume),
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_handler_returns_not_found_for_invalid_uri() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workspace_resume_resource_handler(server)

    response = handler("workspace://not-a-uuid/resume")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workspace resume resource requires workspace://{workspace_id}/resume",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_handler_returns_server_not_ready_error() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workspace_resume_resource_handler(server)

    response = handler(f"workspace://{uuid4()}/resume")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_handler_returns_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workflow_detail_resource_handler(server)

    server.startup()

    response = handler(
        (
            f"workspace://{resume.workspace.workspace_id}/workflow/"
            f"{resume.workflow_instance.workflow_instance_id}"
        )
    )

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 200
    assert response.payload == {
        "uri": (
            f"workspace://{resume.workspace.workspace_id}/workflow/"
            f"{resume.workflow_instance.workflow_instance_id}"
        ),
        "resource": serialize_workflow_resume(resume),
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_handler_returns_not_found_for_invalid_uri() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_detail_resource_handler(server)

    response = handler("workspace://not-a-uuid/workflow/not-a-uuid")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": (
                "workflow detail resource requires "
                "workspace://{workspace_id}/workflow/{workflow_instance_id}"
            ),
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_handler_returns_server_not_ready_error() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_detail_resource_handler(server)

    response = handler(f"workspace://{uuid4()}/workflow/{uuid4()}")

    assert isinstance(response, McpResourceResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_collect_runtime_introspection_returns_empty_tuple_for_none() -> None:
    assert collect_runtime_introspection(None) == ()


def test_collect_runtime_introspection_returns_http_runtime_introspection() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)
    runtime.register_handler(
        "workflow_resume",
        lambda path: WorkflowResumeResponse(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    introspections = collect_runtime_introspection(runtime)

    assert introspections == (
        RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=(
                "memory_get_context",
                "memory_remember_episode",
                "memory_search",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "workflow_checkpoint",
                "workflow_complete",
                "workflow_resume",
                "workflow_start",
                "workspace_register",
            ),
            resources=(
                "workspace://{workspace_id}/resume",
                "workspace://{workspace_id}/workflow/{workflow_instance_id}",
            ),
        ),
    )


def test_serialize_runtime_introspection_returns_json_ready_payload() -> None:
    introspection = RuntimeIntrospection(
        transport="http",
        routes=("workflow_resume",),
        tools=(),
    )

    payload = serialize_runtime_introspection(introspection)

    assert payload == {
        "transport": "http",
        "routes": ["workflow_resume"],
        "tools": [],
        "resources": [],
    }


def test_serialize_runtime_introspection_collection_returns_json_ready_payloads() -> (
    None
):
    introspections = (
        RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=(),
            resources=(),
        ),
    )

    payload = serialize_runtime_introspection_collection(introspections)

    assert payload == [
        {
            "transport": "http",
            "routes": ["workflow_resume"],
            "tools": [],
            "resources": [],
        },
    ]


def test_build_runtime_introspection_response_returns_http_payload_for_single_runtime() -> (
    None
):
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    response = build_runtime_introspection_response(server)

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_closed_projection_failures",
                    "workflow_resume",
                ],
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
                "resources": [
                    "workspace://{workspace_id}/resume",
                    "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                ],
            }
        ]
    }


def test_build_runtime_introspection_response_returns_empty_runtime_list_when_runtime_is_missing() -> (
    None
):
    settings = make_settings()
    server = CtxLedgerServer(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=None,
    )

    response = build_runtime_introspection_response(server)

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {"runtime": []}


def test_build_runtime_introspection_http_handler_returns_success_response() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )
    handler = build_runtime_introspection_http_handler(server)

    response = handler("/debug/runtime")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_closed_projection_failures",
                    "workflow_resume",
                ],
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
                "resources": [
                    "workspace://{workspace_id}/resume",
                    "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                ],
            }
        ]
    }


def test_build_runtime_introspection_http_handler_returns_not_found_for_invalid_path() -> (
    None
):
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )
    handler = build_runtime_introspection_http_handler(server)

    response = handler("/debug/routes")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "runtime introspection endpoint requires /debug/runtime",
        }
    }


def test_build_http_runtime_adapter_omits_runtime_introspection_route_when_debug_endpoints_are_disabled() -> (
    None
):
    settings = make_settings()
    settings = replace(
        settings,
        debug=DebugSettings(enabled=False),
    )
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.handler("runtime_introspection") is None
    assert server.runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )


def test_http_runtime_adapter_dispatches_registered_runtime_introspection_handler() -> (
    None
):
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )
    assert isinstance(server.runtime, HttpRuntimeAdapter)

    response = server.runtime.dispatch(
        "runtime_introspection",
        "/debug/runtime",
    )

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_closed_projection_failures",
                    "workflow_resume",
                ],
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
                "resources": [
                    "workspace://{workspace_id}/resume",
                    "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                ],
            }
        ]
    }


def test_health_includes_runtime_summary_details_for_http_runtime() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    health = server.health()

    assert health.ok is True
    assert health.status == "ok"
    assert health.details["runtime"] == [
        {
            "transport": "http",
            "routes": [
                "mcp_rpc",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "runtime_introspection",
                "runtime_routes",
                "runtime_tools",
                "workflow_closed_projection_failures",
                "workflow_resume",
            ],
            "tools": [
                "memory_get_context",
                "memory_remember_episode",
                "memory_search",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "workflow_checkpoint",
                "workflow_complete",
                "workflow_resume",
                "workflow_start",
                "workspace_register",
            ],
            "resources": [
                "workspace://{workspace_id}/resume",
                "workspace://{workspace_id}/workflow/{workflow_instance_id}",
            ],
        }
    ]


def test_readiness_includes_runtime_summary_details_for_http_runtime() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    server.startup()
    readiness = server.readiness()

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.details["runtime"] == [
        {
            "transport": "http",
            "routes": [
                "mcp_rpc",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "runtime_introspection",
                "runtime_routes",
                "runtime_tools",
                "workflow_closed_projection_failures",
                "workflow_resume",
            ],
            "tools": [
                "memory_get_context",
                "memory_remember_episode",
                "memory_search",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "workflow_checkpoint",
                "workflow_complete",
                "workflow_resume",
                "workflow_start",
                "workspace_register",
            ],
            "resources": [
                "workspace://{workspace_id}/resume",
                "workspace://{workspace_id}/workflow/{workflow_instance_id}",
            ],
        }
    ]


def test_startup_logs_runtime_introspection_metadata_for_http_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )
    info_calls: list[tuple[str, dict[str, object]]] = []

    original_logger_info = logging.getLogger("ctxledger.server").info

    def capture_info(message: str, *args: object, **kwargs: object) -> None:
        extra = kwargs.get("extra")
        if isinstance(extra, dict):
            info_calls.append((message, dict(extra)))
        original_logger_info(message, *args, **kwargs)

    monkeypatch.setattr(logging.getLogger("ctxledger.server"), "info", capture_info)

    server.startup()

    startup_complete_extra = next(
        extra
        for message, extra in info_calls
        if message == "ctxledger startup complete"
    )

    assert startup_complete_extra["http_enabled"] is True
    assert startup_complete_extra["host"] == settings.http.host
    assert startup_complete_extra["port"] == settings.http.port
    assert startup_complete_extra["mcp_url"] == settings.http.mcp_url
    assert startup_complete_extra["workflow_service_initialized"] is True
    assert startup_complete_extra["runtime"] == [
        {
            "transport": "http",
            "routes": [
                "mcp_rpc",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "runtime_introspection",
                "runtime_routes",
                "runtime_tools",
                "workflow_closed_projection_failures",
                "workflow_resume",
            ],
            "tools": [
                "memory_get_context",
                "memory_remember_episode",
                "memory_search",
                "projection_failures_ignore",
                "projection_failures_resolve",
                "workflow_checkpoint",
                "workflow_complete",
                "workflow_resume",
                "workflow_start",
                "workspace_register",
            ],
            "resources": [
                "workspace://{workspace_id}/resume",
                "workspace://{workspace_id}/workflow/{workflow_instance_id}",
            ],
        }
    ]


def test_build_debug_routes_http_handler_returns_runtime_routes_only() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    handler = server.runtime.require_handler("runtime_routes")
    response = handler("/debug/routes")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "routes": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_closed_projection_failures",
                    "workflow_resume",
                ],
            }
        ]
    }


def test_build_debug_routes_http_handler_returns_not_found_for_invalid_path() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    handler = server.runtime.require_handler("runtime_routes")
    response = handler("/debug/runtime")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "runtime routes endpoint requires /debug/routes",
        }
    }


def test_build_http_runtime_adapter_omits_runtime_routes_handler_when_debug_endpoints_are_disabled() -> (
    None
):
    settings = make_settings()
    settings = replace(
        settings,
        debug=DebugSettings(enabled=False),
    )
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.handler("runtime_routes") is None
    assert server.runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )


def test_build_debug_tools_http_handler_returns_runtime_tools_only() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    handler = server.runtime.require_handler("runtime_tools")
    response = handler("/debug/tools")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "tools": [
            {
                "transport": "http",
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
            }
        ]
    }


def test_build_debug_tools_http_handler_returns_http_only_empty_tools() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    handler = server.runtime.require_handler("runtime_tools")
    response = handler("/debug/tools")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "tools": [
            {
                "transport": "http",
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
            }
        ]
    }


def test_build_debug_tools_http_handler_returns_not_found_for_invalid_path() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    handler = server.runtime.require_handler("runtime_tools")
    response = handler("/debug/routes")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "runtime tools endpoint requires /debug/tools",
        }
    }


def test_build_http_runtime_adapter_omits_runtime_tools_handler_when_debug_endpoints_are_disabled() -> (
    None
):
    settings = make_settings()
    settings = replace(
        settings,
        debug=DebugSettings(enabled=False),
    )
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.handler("runtime_tools") is None
    assert server.runtime.registered_routes() == (
        "mcp_rpc",
        "projection_failures_ignore",
        "projection_failures_resolve",
        "workflow_closed_projection_failures",
        "workflow_resume",
    )


def test_print_runtime_summary_includes_http_runtime_introspection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    server.startup()
    _print_runtime_summary(server)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ctxledger 0.1.0 started" in captured.err
    assert "health=ok" in captured.err
    assert "readiness=ready" in captured.err
    assert (
        "runtime=[{'transport': 'http', 'routes': ['mcp_rpc', "
        "'projection_failures_ignore', 'projection_failures_resolve', "
        "'runtime_introspection', 'runtime_routes', 'runtime_tools', "
        "'workflow_closed_projection_failures', 'workflow_resume'], 'tools': "
        "['memory_get_context', 'memory_remember_episode', 'memory_search', "
        "'projection_failures_ignore', 'projection_failures_resolve', "
        "'workflow_checkpoint', 'workflow_complete', 'workflow_resume', "
        "'workflow_start', 'workspace_register'], 'resources': "
        "['workspace://{workspace_id}/resume', "
        "'workspace://{workspace_id}/workflow/{workflow_instance_id}']}]"
        in captured.err
    )
    assert f"mcp_endpoint={server.settings.http.mcp_url}" in captured.err


def test_http_runtime_adapter_dispatches_registered_debug_routes_handler() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    response = server.runtime.dispatch(
        "runtime_routes",
        "/debug/routes",
    )

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "routes": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_closed_projection_failures",
                    "workflow_resume",
                ],
            }
        ]
    }


def test_http_runtime_adapter_dispatches_registered_debug_tools_handler() -> None:
    settings = make_settings()
    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        workflow_service_factory=lambda: FakeWorkflowService(make_resume_fixture()),
    )

    response = server.runtime.dispatch(
        "runtime_tools",
        "/debug/tools",
    )

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "tools": [
            {
                "transport": "http",
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "projection_failures_ignore",
                    "projection_failures_resolve",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
            }
        ]
    }
