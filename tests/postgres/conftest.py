from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryItemRecord,
    MemoryItemRepository,
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
        self.fetchone_results: list[object | None] = []
        self.fetchall_results: list[list[object]] = []
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


class FakePoolConnectionContext(AbstractContextManager["FakeConnection"]):
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.enter_calls = 0
        self.exit_calls = 0

    def __enter__(self) -> FakeConnection:
        self.enter_calls += 1
        return self.connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.exit_calls += 1


class FakeConnectionPool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection_resource = connection
        self.connection_calls = 0
        self.contexts: list[FakePoolConnectionContext] = []

    def connection(self) -> FakePoolConnectionContext:
        self.connection_calls += 1
        context = FakePoolConnectionContext(self.connection_resource)
        self.contexts.append(context)
        return context


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


class WorkspaceRepoStub(WorkspaceRepository):
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


class WorkflowInstanceRepoStub(WorkflowInstanceRepository):
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


class WorkflowAttemptRepoStub(WorkflowAttemptRepository):
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


class WorkflowCheckpointRepoStub(WorkflowCheckpointRepository):
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


class VerifyReportRepoStub(VerifyReportRepository):
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


class MemoryItemRepoStub(MemoryItemRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, MemoryItemRecord] = {}

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        self.items[memory_item.memory_id] = memory_item
        return memory_item

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        candidates = [
            memory_item
            for memory_item in self.items.values()
            if memory_item.workspace_id == workspace_id
        ]
        candidates.sort(key=lambda item: item.created_at, reverse=True)
        return tuple(candidates[:limit])

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        candidates = [
            memory_item
            for memory_item in self.items.values()
            if memory_item.episode_id == episode_id
        ]
        candidates.sort(key=lambda item: item.created_at, reverse=True)
        return tuple(candidates[:limit])


class MemoryEmbeddingRepoStub(MemoryEmbeddingRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, MemoryEmbeddingRecord] = {}

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        self.items[embedding.memory_embedding_id] = embedding
        return embedding

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        matches = [
            embedding
            for embedding in self.items.values()
            if embedding.memory_id == memory_id
        ]
        matches.sort(key=lambda embedding: embedding.created_at, reverse=True)
        return tuple(matches[:limit])

    def find_similar(
        self,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
        workspace_id: UUID | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        return ()
