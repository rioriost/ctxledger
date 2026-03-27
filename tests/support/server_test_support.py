from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ctxledger.config import (
    AppSettings,
    DatabaseSettings,
    DebugSettings,
    EmbeddingProvider,
    EmbeddingSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
)
from ctxledger.runtime.http_runtime import (
    HttpRuntimeAdapter,
    build_http_runtime_adapter,
)
from ctxledger.runtime.types import WorkflowResumeResponse
from ctxledger.server import CtxLedgerServer
from ctxledger.workflow.service import (
    ResumableStatus,
    ResumeIssue,
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
    age_available_value: bool = True
    age_graph_available_value: bool = True
    ping_calls: int = 0
    schema_ready_calls: int = 0
    age_available_calls: int = 0
    age_graph_available_calls: int = 0
    age_graph_status_calls: int = 0
    requested_graph_names: list[str] | None = None

    def __post_init__(self) -> None:
        if self.requested_graph_names is None:
            self.requested_graph_names = []

    def ping(self) -> None:
        self.ping_calls += 1
        if self.ping_should_fail:
            raise RuntimeError("database unavailable")

    def schema_ready(self) -> bool:
        self.schema_ready_calls += 1
        return self.schema_ready_value

    def age_available(self) -> bool:
        self.age_available_calls += 1
        return self.age_available_value

    def age_graph_available(self, graph_name: str) -> bool:
        self.age_graph_available_calls += 1
        if self.requested_graph_names is not None:
            self.requested_graph_names.append(graph_name)
        return self.age_graph_available_value

    def age_graph_status(self, graph_name: str) -> str:
        self.age_graph_status_calls += 1
        if self.requested_graph_names is not None:
            self.requested_graph_names.append(graph_name)
        if not self.age_available_value:
            return "age_unavailable"
        if not self.age_graph_available_value:
            return "graph_unavailable"
        return "graph_ready"


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


def make_resume_fixture() -> WorkflowResume:
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
    warnings = (
        ResumeIssue(
            code="resume_warning",
            message="resume state requires operator review before continuing",
            details={
                "reason": "operator_review_required",
                "scope": "workflow_resume",
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
        warnings=warnings,
        next_hint="Serialize resume output",
    )


def make_settings(
    *,
    database_url: str = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
    host: str = "127.0.0.1",
    port: int = 8080,
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
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(
            host=host,
            port=port,
            path="/mcp",
        ),
        debug=DebugSettings(
            enabled=True,
        ),
        logging=LoggingSettings(
            level=LogLevel.INFO,
            structured=True,
        ),
        embedding=EmbeddingSettings(
            enabled=False,
            provider=EmbeddingProvider.DISABLED,
            model="local-stub-v1",
            api_key=None,
            base_url=None,
            dimensions=None,
        ),
    )


_MISSING = object()
_EXPLICIT_NONE = object()


def make_server(
    *,
    settings: AppSettings | None = None,
    db_health_checker: FakeDatabaseHealthChecker | None | object = _MISSING,
    runtime: FakeRuntime | HttpRuntimeAdapter | None = None,
    workflow_service_factory: object | None = None,
) -> CtxLedgerServer:
    kwargs: dict[str, Any] = {
        "settings": settings or make_settings(),
        "runtime": runtime or FakeRuntime(),
        "connection_pool": object(),
    }
    if db_health_checker is _MISSING:
        kwargs["db_health_checker"] = FakeDatabaseHealthChecker()
    elif db_health_checker is _EXPLICIT_NONE:
        kwargs["db_health_checker"] = None
    else:
        kwargs["db_health_checker"] = db_health_checker
    if workflow_service_factory is not None:
        kwargs["workflow_service_factory"] = workflow_service_factory
    return CtxLedgerServer(**kwargs)


def make_ready_server(
    *,
    settings: AppSettings | None = None,
    db_health_checker: FakeDatabaseHealthChecker | None | object = _MISSING,
    runtime: FakeRuntime | HttpRuntimeAdapter | None = None,
    workflow_service_factory: object | None = None,
) -> CtxLedgerServer:
    server = make_server(
        settings=settings,
        db_health_checker=db_health_checker,
        runtime=runtime,
        workflow_service_factory=workflow_service_factory,
    )
    server.startup()
    return server


def make_ready_server_with_resume(
    *,
    resume: WorkflowResume | None = None,
    settings: AppSettings | None = None,
    fake_workflow_service: FakeWorkflowService | None = None,
) -> tuple[CtxLedgerServer, WorkflowResume, FakeWorkflowService]:
    resume_result = resume or make_resume_fixture()
    workflow_service = fake_workflow_service or FakeWorkflowService(resume_result)
    server = make_ready_server(
        settings=settings,
        workflow_service_factory=lambda: workflow_service,
    )
    return server, resume_result, workflow_service


def make_ready_server_with_handler(
    handler_builder: object,
    *,
    settings: AppSettings | None = None,
    resume: WorkflowResume | None = None,
    fake_workflow_service: FakeWorkflowService | None = None,
) -> tuple[CtxLedgerServer, object, WorkflowResume, FakeWorkflowService]:
    server, resume_result, workflow_service = make_ready_server_with_resume(
        resume=resume,
        settings=settings,
        fake_workflow_service=fake_workflow_service,
    )
    handler = handler_builder(server)
    return server, handler, resume_result, workflow_service


def make_resource_handler(
    handler_builder: object,
    *,
    settings: AppSettings | None = None,
) -> object:
    server = make_server(settings=settings)
    return handler_builder(server)


def make_ready_resource_handler(
    handler_builder: object,
    *,
    settings: AppSettings | None = None,
    resume: WorkflowResume | None = None,
    fake_workflow_service: FakeWorkflowService | None = None,
) -> tuple[object, WorkflowResume, FakeWorkflowService]:
    _, handler, resume_result, workflow_service = make_ready_server_with_handler(
        handler_builder,
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
    )
    return handler, resume_result, workflow_service


def make_tool_handler(
    handler_builder: object,
    *,
    settings: AppSettings | None = None,
    resume: WorkflowResume | None = None,
    fake_workflow_service: FakeWorkflowService | None = None,
) -> tuple[object, WorkflowResume, FakeWorkflowService]:
    resume_result = resume or make_resume_fixture()
    workflow_service = fake_workflow_service or FakeWorkflowService(resume_result)
    server = make_server(
        settings=settings,
        workflow_service_factory=lambda: workflow_service,
    )
    handler = handler_builder(server)
    return handler, resume_result, workflow_service


def make_ready_tool_handler(
    handler_builder: object,
    *,
    settings: AppSettings | None = None,
    resume: WorkflowResume | None = None,
    fake_workflow_service: FakeWorkflowService | None = None,
) -> tuple[object, WorkflowResume, FakeWorkflowService]:
    resume_result = resume or make_resume_fixture()
    workflow_service = fake_workflow_service or FakeWorkflowService(resume_result)
    server = make_ready_server(
        settings=settings,
        workflow_service_factory=lambda: workflow_service,
    )
    handler = handler_builder(server)
    return handler, resume_result, workflow_service


def make_http_runtime(
    *,
    settings: AppSettings | None = None,
    resume: WorkflowResume | None = None,
    fake_workflow_service: FakeWorkflowService | None = None,
    started: bool = False,
) -> tuple[CtxLedgerServer, HttpRuntimeAdapter, WorkflowResume, FakeWorkflowService]:
    resume_result = resume or make_resume_fixture()
    workflow_service = fake_workflow_service or FakeWorkflowService(resume_result)
    runtime = FakeRuntime()
    server = make_server(
        settings=settings,
        runtime=runtime,
        workflow_service_factory=lambda: workflow_service,
    )
    http_runtime = build_http_runtime_adapter(server)
    server.runtime = http_runtime
    if started:
        server.startup()
    return server, http_runtime, resume_result, workflow_service


def build_runtime_summary_payload(
    *,
    include_debug_routes: bool = True,
) -> list[dict[str, object]]:
    routes = ["mcp_rpc", "workflow_resume"]
    if include_debug_routes:
        routes[1:1] = [
            "runtime_introspection",
            "runtime_routes",
            "runtime_tools",
        ]

    return [
        {
            "transport": "http",
            "routes": routes,
            "tools": [
                "memory_get_context",
                "memory_remember_episode",
                "memory_search",
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


def install_logging_info_capture(
    monkeypatch: object,
) -> list[tuple[str, dict[str, object]]]:
    info_calls: list[tuple[str, dict[str, object]]] = []
    logger = logging.getLogger("ctxledger.server")
    original_logger_info = logger.info

    def capture_info(message: str, *args: object, **kwargs: object) -> None:
        extra = kwargs.get("extra")
        if isinstance(extra, dict):
            info_calls.append((message, dict(extra)))
        original_logger_info(message, *args, **kwargs)

    monkeypatch.setattr(logger, "info", capture_info)
    return info_calls


def make_completed_workflow_result_stub(
    *,
    resume: WorkflowResume | None = None,
    summary: str = "Completed successfully",
    verify_status: VerifyStatus = VerifyStatus.PASSED,
    warning: ResumeIssue | None = None,
    auto_memory_details: dict[str, object] | None = None,
) -> tuple[WorkflowResume, object]:
    resume_result = resume or make_resume_fixture()
    finished_attempt = replace(
        resume_result.attempt,
        status=WorkflowAttemptStatus.SUCCEEDED,
        finished_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    completed_workflow = replace(
        resume_result.workflow_instance,
        status=WorkflowInstanceStatus.COMPLETED,
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    warnings = () if warning is None else (warning,)

    result = type(
        "WorkflowCompleteResultStub",
        (),
        {
            "workflow_instance": completed_workflow,
            "attempt": finished_attempt,
            "verify_report": replace(
                resume_result.latest_verify_report,
                status=verify_status,
                report_json={"checks": ["pytest"], "status": summary.lower()},
            ),
            "warnings": warnings,
            "auto_memory_details": auto_memory_details,
        },
    )()

    return resume_result, result


def build_server_not_ready_response() -> WorkflowResumeResponse:
    return WorkflowResumeResponse(
        status_code=503,
        payload={
            "error": {
                "code": "server_not_ready",
                "message": "workflow service is not initialized",
            }
        },
        headers={"content-type": "application/json"},
    )
