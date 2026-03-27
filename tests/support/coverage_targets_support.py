from __future__ import annotations

import signal
from datetime import UTC, datetime
from types import SimpleNamespace
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
from ctxledger.server import CtxLedgerServer
from ctxledger.workflow.service import (
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
        app_version="0.9.0",
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
            path=path,
        ),
        debug=DebugSettings(enabled=debug_enabled),
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
        connection_pool=object(),
    )


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
        step_name="implement_server_handlers",
        summary="Added runtime and handler coverage",
        checkpoint_json={"next_intended_action": "run focused tests"},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
    )
    latest_verify_report = VerifyReport(
        verify_id=verify_id,
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        report_json={"checks": ["pytest"], "status": "passed"},
        created_at=datetime(2024, 1, 7, tzinfo=UTC),
    )

    return WorkflowResume(
        workspace=workspace,
        workflow_instance=workflow_instance,
        current_attempt=attempt,
        latest_checkpoint=latest_checkpoint,
        latest_verify_report=latest_verify_report,
        resumable_status="resumable",
        issues=(),
        next_hint="Resume from step 'implement_server_handlers' using the latest checkpoint summary.",
    )


def make_signal_registry() -> tuple[dict[signal.Signals, object], object]:
    registered: dict[signal.Signals, object] = {}

    def fake_signal(sig: signal.Signals, handler: object) -> None:
        registered[sig] = handler

    return registered, fake_signal


def make_ready_server_summary() -> SimpleNamespace:
    return SimpleNamespace(
        startup=lambda: None,
        runtime=None,
        health=lambda: SimpleNamespace(status="ok"),
        readiness=lambda: SimpleNamespace(status="ready"),
    )
