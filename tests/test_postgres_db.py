from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from ctxledger.workflow.service import (
    PersistenceError,
    ProjectionArtifactType,
    ProjectionFailureInfo,
    ProjectionInfo,
    ProjectionStateRepository,
    ProjectionStatus,
    RecordProjectionStateInput,
    UnitOfWork,
    VerifyReport,
    VerifyReportRepository,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptRepository,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowCheckpointRepository,
    WorkflowInstance,
    WorkflowInstanceRepository,
    WorkflowInstanceStatus,
    Workspace,
    WorkspaceRepository,
)


class FakeCursor(AbstractContextManager["FakeCursor"]):
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.closed = False

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def execute(
        self, query: str, params: tuple[object, ...] | None = None
    ) -> FakeCursor:
        self.connection.executed.append((query, params))
        return self

    def fetchone(self) -> tuple[object, ...] | None:
        if self.connection.fetchone_results:
            return self.connection.fetchone_results.pop(0)
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        if self.connection.fetchall_results:
            return self.connection.fetchall_results.pop(0)
        return []


class FakeConnection(AbstractContextManager["FakeConnection"]):
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []
        self.fetchone_results: list[tuple[object, ...] | None] = []
        self.fetchall_results: list[list[tuple[object, ...]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.closed = False

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


@dataclass
class FakeConnectionFactory:
    connection: FakeConnection

    def __call__(self) -> FakeConnection:
        return self.connection


def sample_workspace() -> Workspace:
    return Workspace(
        workspace_id=uuid4(),
        repo_url="https://example.com/org/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
        metadata={"language": "python"},
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )


def sample_workflow(workspace_id: UUID) -> WorkflowInstance:
    return WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="TICKET-123",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={"priority": "high"},
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, tzinfo=UTC),
    )


def sample_attempt(workflow_instance_id: UUID) -> WorkflowAttempt:
    return WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        failure_reason=None,
        verify_status=VerifyStatus.PENDING,
        started_at=datetime(2024, 1, 5, tzinfo=UTC),
        finished_at=None,
        created_at=datetime(2024, 1, 5, tzinfo=UTC),
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )


def sample_checkpoint(
    workflow_instance_id: UUID,
    attempt_id: UUID,
) -> WorkflowCheckpoint:
    return WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        step_name="edit_files",
        summary="Updated service implementation",
        checkpoint_json={"next_intended_action": "Run tests"},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
    )


def sample_verify_report(attempt_id: UUID) -> VerifyReport:
    return VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        report_json={"checks": ["pytest"], "status": "passed"},
        created_at=datetime(2024, 1, 7, tzinfo=UTC),
    )


def sample_projection_info() -> ProjectionInfo:
    return ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.json",
        last_successful_write_at=datetime(2024, 1, 8, tzinfo=UTC),
        last_canonical_update_at=datetime(2024, 1, 8, tzinfo=UTC),
        open_failure_count=0,
    )


def test_schema_file_exists() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "postgres.sql"

    assert schema_path.exists()
    assert (
        schema_path.read_text(encoding="utf-8")
        .strip()
        .startswith("-- ctxledger PostgreSQL schema")
    )


def test_schema_contains_core_workflow_tables() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "postgres.sql"
    schema = schema_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS workspaces" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_instances" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_attempts" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_checkpoints" in schema
    assert "CREATE TABLE IF NOT EXISTS verify_reports" in schema
    assert "CREATE TABLE IF NOT EXISTS projection_states" in schema


def test_unit_of_work_contract_shape_can_be_satisfied_by_postgres_impl() -> None:
    class PostgresStyleUnitOfWork(UnitOfWork):
        def __init__(self) -> None:
            self.workspaces = _WorkspaceRepoStub()
            self.workflow_instances = _WorkflowInstanceRepoStub()
            self.workflow_attempts = _WorkflowAttemptRepoStub()
            self.workflow_checkpoints = _WorkflowCheckpointRepoStub()
            self.verify_reports = _VerifyReportRepoStub()
            self.projection_states = _ProjectionStateRepoStub()
            self.committed = False
            self.rolled_back = False

        def commit(self) -> None:
            self.committed = True

        def rollback(self) -> None:
            self.rolled_back = True

    uow = PostgresStyleUnitOfWork()

    assert isinstance(uow.workspaces, WorkspaceRepository)
    assert isinstance(uow.workflow_instances, WorkflowInstanceRepository)
    assert isinstance(uow.workflow_attempts, WorkflowAttemptRepository)
    assert isinstance(uow.workflow_checkpoints, WorkflowCheckpointRepository)
    assert isinstance(uow.verify_reports, VerifyReportRepository)
    assert isinstance(uow.projection_states, ProjectionStateRepository)

    uow.commit()
    uow.rollback()

    assert uow.committed is True
    assert uow.rolled_back is True


def test_workspace_repository_contract_can_round_trip_entity() -> None:
    repo = _WorkspaceRepoStub()
    workspace = sample_workspace()

    created = repo.create(workspace)

    assert created == workspace
    assert repo.get_by_id(workspace.workspace_id) == workspace
    assert repo.get_by_canonical_path(workspace.canonical_path) == workspace
    assert repo.get_by_repo_url(workspace.repo_url) == [workspace]


def test_workflow_instance_repository_contract_tracks_running_and_latest() -> None:
    repo = _WorkflowInstanceRepoStub()
    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)

    created = repo.create(workflow)

    assert created == workflow
    assert repo.get_by_id(workflow.workflow_instance_id) == workflow
    assert repo.get_running_by_workspace_id(workspace.workspace_id) == workflow
    assert repo.get_latest_by_workspace_id(workspace.workspace_id) == workflow


def test_workflow_attempt_repository_contract_tracks_next_attempt_number() -> None:
    repo = _WorkflowAttemptRepoStub()
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)

    created = repo.create(attempt)

    assert created == attempt
    assert repo.get_by_id(attempt.attempt_id) == attempt
    assert repo.get_running_by_workflow_id(workflow.workflow_instance_id) == attempt
    assert repo.get_latest_by_workflow_id(workflow.workflow_instance_id) == attempt
    assert repo.get_next_attempt_number(workflow.workflow_instance_id) == 2


def test_checkpoint_repository_contract_returns_latest_for_workflow_and_attempt() -> (
    None
):
    repo = _WorkflowCheckpointRepoStub()
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)
    checkpoint = sample_checkpoint(workflow.workflow_instance_id, attempt.attempt_id)

    created = repo.create(checkpoint)

    assert created == checkpoint
    assert repo.get_latest_by_workflow_id(workflow.workflow_instance_id) == checkpoint
    assert repo.get_latest_by_attempt_id(attempt.attempt_id) == checkpoint


def test_verify_report_repository_contract_returns_latest_by_attempt() -> None:
    repo = _VerifyReportRepoStub()
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)
    verify_report = sample_verify_report(attempt.attempt_id)

    created = repo.create(verify_report)

    assert created == verify_report
    assert repo.get_latest_by_attempt_id(attempt.attempt_id) == verify_report


def test_projection_state_repository_contract_returns_resume_projection() -> None:
    repo = _ProjectionStateRepoStub()
    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)
    projection = sample_projection_info()

    repo.items[
        (
            workspace.workspace_id,
            workflow.workflow_instance_id,
            projection.projection_type,
        )
    ] = projection

    assert repo.get_resume_projections(
        workspace.workspace_id, workflow.workflow_instance_id
    ) == (projection,)


@pytest.mark.parametrize(
    ("query", "expected_fragment"),
    [
        ("SELECT 1", "SELECT 1"),
        ("SELECT to_regclass('workspaces')", "to_regclass"),
    ],
)
def test_fake_connection_records_executed_queries(
    query: str,
    expected_fragment: str,
) -> None:
    connection = FakeConnection()

    with connection.cursor() as cursor:
        cursor.execute(query)

    assert len(connection.executed) == 1
    assert expected_fragment in connection.executed[0][0]


def test_fake_connection_supports_fetchone_and_fetchall() -> None:
    connection = FakeConnection()
    connection.fetchone_results.append((1,))
    connection.fetchall_results.append([("a",), ("b",)])

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        one = cursor.fetchone()
        many = cursor.fetchall()

    assert one == (1,)
    assert many == [("a",), ("b",)]


def test_fake_connection_factory_returns_shared_connection() -> None:
    connection = FakeConnection()
    factory = FakeConnectionFactory(connection)

    first = factory()
    second = factory()

    assert first is connection
    assert second is connection


class _WorkspaceRepoStub(WorkspaceRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Workspace] = {}

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        return self.items.get(workspace_id)

    def get_by_canonical_path(self, canonical_path: str) -> Workspace | None:
        for workspace in self.items.values():
            if workspace.canonical_path == canonical_path:
                return workspace
        return None

    def get_by_repo_url(self, repo_url: str) -> list[Workspace]:
        return [
            workspace
            for workspace in self.items.values()
            if workspace.repo_url == repo_url
        ]

    def create(self, workspace: Workspace) -> Workspace:
        self.items[workspace.workspace_id] = workspace
        return workspace

    def update(self, workspace: Workspace) -> Workspace:
        self.items[workspace.workspace_id] = workspace
        return workspace


class _WorkflowInstanceRepoStub(WorkflowInstanceRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, WorkflowInstance] = {}

    def get_by_id(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        return self.items.get(workflow_instance_id)

    def get_running_by_workspace_id(
        self, workspace_id: UUID
    ) -> WorkflowInstance | None:
        candidates = [
            workflow
            for workflow in self.items.values()
            if workflow.workspace_id == workspace_id
            and workflow.status == WorkflowInstanceStatus.RUNNING
        ]
        return max(candidates, key=lambda item: item.created_at, default=None)

    def get_latest_by_workspace_id(self, workspace_id: UUID) -> WorkflowInstance | None:
        candidates = [
            workflow
            for workflow in self.items.values()
            if workflow.workspace_id == workspace_id
        ]
        return max(candidates, key=lambda item: item.updated_at, default=None)

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self.items[workflow.workflow_instance_id] = workflow
        return workflow

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self.items[workflow.workflow_instance_id] = workflow
        return workflow


class _WorkflowAttemptRepoStub(WorkflowAttemptRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, WorkflowAttempt] = {}

    def get_by_id(self, attempt_id: UUID) -> WorkflowAttempt | None:
        return self.items.get(attempt_id)

    def get_running_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowAttempt | None:
        candidates = [
            attempt
            for attempt in self.items.values()
            if attempt.workflow_instance_id == workflow_instance_id
            and attempt.status == WorkflowAttemptStatus.RUNNING
        ]
        return max(candidates, key=lambda item: item.started_at, default=None)

    def get_latest_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowAttempt | None:
        candidates = [
            attempt
            for attempt in self.items.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        return max(
            candidates,
            key=lambda item: (item.attempt_number, item.started_at),
            default=None,
        )

    def get_next_attempt_number(self, workflow_instance_id: UUID) -> int:
        latest = self.get_latest_by_workflow_id(workflow_instance_id)
        if latest is None:
            return 1
        return latest.attempt_number + 1

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self.items[attempt.attempt_id] = attempt
        return attempt

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self.items[attempt.attempt_id] = attempt
        return attempt


class _WorkflowCheckpointRepoStub(WorkflowCheckpointRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, WorkflowCheckpoint] = {}

    def get_latest_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowCheckpoint | None:
        candidates = [
            checkpoint
            for checkpoint in self.items.values()
            if checkpoint.workflow_instance_id == workflow_instance_id
        ]
        return max(candidates, key=lambda item: item.created_at, default=None)

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> WorkflowCheckpoint | None:
        candidates = [
            checkpoint
            for checkpoint in self.items.values()
            if checkpoint.attempt_id == attempt_id
        ]
        return max(candidates, key=lambda item: item.created_at, default=None)

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self.items[checkpoint.checkpoint_id] = checkpoint
        return checkpoint


class _VerifyReportRepoStub(VerifyReportRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, VerifyReport] = {}

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> VerifyReport | None:
        candidates = [
            report for report in self.items.values() if report.attempt_id == attempt_id
        ]
        return max(candidates, key=lambda item: item.created_at, default=None)

    def create(self, verify_report: VerifyReport) -> VerifyReport:
        self.items[verify_report.verify_id] = verify_report
        return verify_report


class _ProjectionStateRepoStub(ProjectionStateRepository):
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, UUID, ProjectionArtifactType], ProjectionInfo] = {}

    def get_resume_projections(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> tuple[ProjectionInfo, ...]:
        candidates = [
            projection
            for (
                candidate_workspace_id,
                candidate_workflow_instance_id,
                _,
            ), projection in self.items.items()
            if candidate_workspace_id == workspace_id
            and candidate_workflow_instance_id == workflow_instance_id
        ]
        candidates.sort(
            key=lambda projection: (
                projection.last_canonical_update_at is not None,
                projection.last_canonical_update_at,
                projection.last_successful_write_at is not None,
                projection.last_successful_write_at,
                projection.projection_type.value,
            ),
            reverse=True,
        )
        return tuple(candidates)

    def record_resume_projection(self, projection: RecordProjectionStateInput) -> None:
        self.items[
            (
                projection.workspace_id,
                projection.workflow_instance_id,
                projection.projection_type,
            )
        ] = ProjectionInfo(
            projection_type=projection.projection_type,
            status=projection.status,
            target_path=projection.target_path,
            last_successful_write_at=projection.last_successful_write_at,
            last_canonical_update_at=projection.last_canonical_update_at,
            open_failure_count=0,
        )
