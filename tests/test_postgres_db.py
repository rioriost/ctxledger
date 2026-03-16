from __future__ import annotations

import importlib
import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace, TracebackType
from uuid import UUID, uuid4

import pytest

from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryItemRecord,
    MemoryItemRepository,
    PersistenceError,
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


def test_unit_of_work_contract_shape_can_be_satisfied_by_postgres_impl() -> None:
    class PostgresStyleUnitOfWork(UnitOfWork):
        def __init__(self) -> None:
            self.workspaces = _WorkspaceRepoStub()
            self.workflow_instances = _WorkflowInstanceRepoStub()
            self.workflow_attempts = _WorkflowAttemptRepoStub()
            self.workflow_checkpoints = _WorkflowCheckpointRepoStub()
            self.verify_reports = _VerifyReportRepoStub()
            self.memory_items = _MemoryItemRepoStub()
            self.memory_embeddings = _MemoryEmbeddingRepoStub()
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
    assert isinstance(uow.memory_items, MemoryItemRepository)
    assert isinstance(uow.memory_embeddings, MemoryEmbeddingRepository)

    uow.commit()
    uow.rollback()

    assert uow.committed is True
    assert uow.rolled_back is True


def test_postgres_unit_of_work_records_checkout_and_session_timing_fields() -> None:
    postgres_module = importlib.import_module("ctxledger.db.postgres")
    connection = FakeConnection()
    pool = FakeConnectionPool(connection)
    config = postgres_module.PostgresConfig(
        database_url="postgresql://example",
        schema_name="ctxledger",
    )

    original_perf_counter = postgres_module.time.perf_counter
    perf_counter_values = iter(
        [
            100.0,
            100.001,
            100.003,
            100.004,
            100.009,
            100.010,
            100.016,
            100.020,
        ]
    )

    postgres_module.time.perf_counter = lambda: next(perf_counter_values)

    try:
        uow = postgres_module.PostgresUnitOfWork(config, pool)
        entered = uow.__enter__()
    finally:
        postgres_module.time.perf_counter = original_perf_counter

    assert entered is uow
    assert 0 <= uow.checkout_context_create_duration_ms <= 2
    assert 4 <= uow.pool_checkout_duration_ms <= 5
    assert 5 <= uow.session_setup_duration_ms <= 6
    assert 19 <= uow.enter_duration_ms <= 20
    assert pool.connection_calls == 1
    assert len(pool.contexts) == 1
    assert pool.contexts[0].enter_calls == 1
    assert connection.executed[:2] == [
        ("SET statement_timeout = 0", None),
        ('SET search_path TO "ctxledger", public', None),
    ]


def test_resume_workflow_debug_logging_includes_uow_timing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_module = importlib.import_module("ctxledger.workflow.service")
    logger = workflow_module.logger

    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)
    checkpoint = sample_checkpoint(
        workflow.workflow_instance_id,
        attempt.attempt_id,
    )
    verify_report = sample_verify_report(attempt.attempt_id)

    class ResumeLoggingUow:
        def __init__(self) -> None:
            self.enter_duration_ms = 23
            self.pool_checkout_duration_ms = 17
            self.session_setup_duration_ms = 5
            self.checkout_context_create_duration_ms = 2
            self.workspaces = SimpleNamespace(
                get_by_id=lambda workspace_id: (
                    workspace if workspace_id == workspace.workspace_id else None
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda workflow_instance_id: (
                    workflow
                    if workflow_instance_id == workflow.workflow_instance_id
                    else None
                )
            )
            self.workflow_attempts = SimpleNamespace(
                get_running_by_workflow_id=lambda workflow_instance_id: (
                    attempt
                    if workflow_instance_id == workflow.workflow_instance_id
                    else None
                ),
                get_latest_by_workflow_id=lambda workflow_instance_id: attempt,
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda workflow_instance_id: checkpoint
            )
            self.verify_reports = SimpleNamespace(
                get_latest_by_attempt_id=lambda attempt_id: verify_report
            )

        def __enter__(self) -> "ResumeLoggingUow":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            return None

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service = workflow_module.WorkflowService(lambda: ResumeLoggingUow())
    service.resume_workflow(
        workflow_module.ResumeWorkflowInput(
            workflow_instance_id=workflow.workflow_instance_id
        )
    )

    uow_enter_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow unit of work enter complete"
    ]
    assert len(uow_enter_extras) == 1
    enter_extra = uow_enter_extras[0]
    assert isinstance(enter_extra, dict)
    assert enter_extra["workflow_instance_id"] == str(workflow.workflow_instance_id)
    assert enter_extra["uow_enter_duration_ms"] == 23
    assert enter_extra["pool_checkout_duration_ms"] == 17
    assert enter_extra["session_setup_duration_ms"] == 5
    assert enter_extra["checkout_context_create_duration_ms"] == 2
    assert enter_extra["duration_ms"] == 23

    complete_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow complete"
    ]
    assert len(complete_extras) == 1
    complete_extra = complete_extras[0]
    assert isinstance(complete_extra, dict)
    assert complete_extra["uow_enter_duration_ms"] == 23
    assert complete_extra["pool_checkout_duration_ms"] == 17
    assert complete_extra["session_setup_duration_ms"] == 5
    assert complete_extra["checkout_context_create_duration_ms"] == 2


def test_memory_embedding_repository_contract_exposes_similarity_query() -> None:
    repo = _MemoryEmbeddingRepoStub()
    first_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="first",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0, 0.0),
        content_hash="second",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    repo.create(first_embedding)
    repo.create(second_embedding)

    matches = repo.find_similar((1.0, 0.0, 0.0), limit=3)

    assert matches == ()


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


def test_memory_item_repository_contract_tracks_workspace_and_episode_items() -> None:
    repo = _MemoryItemRepoStub()
    workspace = sample_workspace()
    older_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Older memory item",
        metadata={"kind": "investigation"},
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    newer_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=older_item.episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer memory item",
        metadata={"kind": "implementation"},
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
        updated_at=datetime(2024, 1, 9, tzinfo=UTC),
    )
    unrelated_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Unrelated memory item",
        metadata={"kind": "other"},
        created_at=datetime(2024, 1, 10, tzinfo=UTC),
        updated_at=datetime(2024, 1, 10, tzinfo=UTC),
    )

    assert repo.create(older_item) == older_item
    assert repo.create(newer_item) == newer_item
    assert repo.create(unrelated_item) == unrelated_item
    assert repo.list_by_workspace_id(workspace.workspace_id, limit=10) == (
        newer_item,
        older_item,
    )
    assert repo.list_by_episode_id(older_item.episode_id, limit=10) == (
        newer_item,
        older_item,
    )


def test_memory_embedding_repository_contract_tracks_embeddings_by_memory_item() -> (
    None
):
    repo = _MemoryEmbeddingRepoStub()
    memory_id = uuid4()
    older_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-model",
        embedding=(0.1, 0.2, 0.3),
        content_hash="older-hash",
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    newer_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-model-v2",
        embedding=(0.4, 0.5, 0.6),
        content_hash="newer-hash",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )
    unrelated_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="other-model",
        embedding=(0.7, 0.8, 0.9),
        content_hash="other-hash",
        created_at=datetime(2024, 1, 10, tzinfo=UTC),
    )

    assert repo.create(older_embedding) == older_embedding
    assert repo.create(newer_embedding) == newer_embedding
    assert repo.create(unrelated_embedding) == unrelated_embedding
    assert repo.list_by_memory_id(memory_id, limit=10) == (
        newer_embedding,
        older_embedding,
    )


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


class _MemoryItemRepoStub(MemoryItemRepository):
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


class _MemoryEmbeddingRepoStub(MemoryEmbeddingRepository):
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


def test_postgres_low_level_helpers_and_pool_builder() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    assert postgres._json_dumps({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert postgres._json_loads(None) == {}
    assert postgres._json_loads('{"a": 1}') == {"a": 1}
    assert postgres._json_object_or_none(None) is None
    assert postgres._json_object_or_none({"a": 1}) == {"a": 1}
    assert postgres._json_object_or_none('{"a": 1}') == {"a": 1}
    assert postgres._json_object_or_none("[1,2]") is None
    assert postgres._json_object_or_none([("a", 1)]) == {"a": 1}

    aware = datetime(2024, 1, 1, tzinfo=UTC)
    naive = datetime(2024, 1, 1)
    assert postgres._to_datetime(aware) == aware
    assert postgres._to_datetime(naive).tzinfo == UTC
    with pytest.raises(PersistenceError, match="Expected datetime, got str"):
        postgres._to_datetime("bad")

    value_uuid = uuid4()
    assert postgres._to_uuid(value_uuid) == value_uuid
    assert postgres._to_uuid(str(value_uuid)) == value_uuid
    assert postgres._optional_datetime(None) is None
    assert postgres._optional_datetime(aware) == aware
    assert postgres._optional_str_enum(VerifyStatus, None) is None
    assert postgres._optional_str_enum(VerifyStatus, "passed") == VerifyStatus.PASSED
    assert postgres._normalized_schema_name(None) == "public"
    assert postgres._normalized_schema_name("  ") == "public"
    assert postgres._normalized_schema_name(" custom ") == "custom"
    assert postgres._parse_embedding_values(None) == ()
    assert postgres._parse_embedding_values("") == ()
    assert postgres._parse_embedding_values("[1, 2.5]") == (1.0, 2.5)
    assert postgres._parse_embedding_values((1, "2.5")) == (1.0, 2.5)
    assert postgres._quote_ident('a"b') == '"a""b"'
    assert postgres._episode_status(None) == "recorded"
    assert postgres._episode_status("ignored") == "ignored"
    assert postgres._pgvector_literal((1.0, 2.5)) == "[1,2.5]"

    class FakePool:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    original_pool = postgres.ConnectionPool
    try:
        postgres.ConnectionPool = FakePool
        config = postgres.PostgresConfig(
            database_url="postgresql://example/db",
            pool_min_size=2,
            pool_max_size=7,
            pool_timeout_seconds=9,
        )
        pool = postgres.build_connection_pool(config)
    finally:
        postgres.ConnectionPool = original_pool

    assert isinstance(pool, FakePool)
    assert pool.kwargs["conninfo"] == "postgresql://example/db"
    assert pool.kwargs["min_size"] == 2
    assert pool.kwargs["max_size"] == 7
    assert pool.kwargs["timeout"] == 9
    assert pool.kwargs["open"] is True


def test_postgres_config_from_settings_and_schema_loader() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    settings = SimpleNamespace(
        database=SimpleNamespace(
            url="postgresql://example/db",
            connect_timeout_seconds=11,
            statement_timeout_ms=222,
            schema_name="  custom  ",
            pool_min_size=3,
            pool_max_size=6,
            pool_timeout_seconds=12,
        )
    )

    config = postgres.PostgresConfig.from_settings(settings)

    assert config.database_url == "postgresql://example/db"
    assert config.connect_timeout_seconds == 11
    assert config.statement_timeout_ms == 222
    assert config.schema_name == "custom"
    assert config.pool_min_size == 3
    assert config.pool_max_size == 6
    assert config.pool_timeout_seconds == 12

    schema_sql = postgres.load_postgres_schema_sql()
    assert "-- ctxledger PostgreSQL schema" in schema_sql


def test_postgres_database_health_checker_ping_and_schema_ready() -> None:
    from ctxledger.db.postgres import PostgresConfig, PostgresDatabaseHealthChecker

    config = PostgresConfig(
        database_url="postgresql://example/db",
        statement_timeout_ms=250,
        schema_name="custom",
    )
    checker = PostgresDatabaseHealthChecker(config)

    ping_connection = FakeConnection()
    schema_connection = FakeConnection()
    schema_connection.fetchall_results.append(
        [
            {"table_name": "workspaces"},
            {"table_name": "workflow_instances"},
            {"table_name": "workflow_attempts"},
            {"table_name": "workflow_checkpoints"},
            {"table_name": "verify_reports"},
        ]
    )

    postgres = importlib.import_module("ctxledger.db.postgres")
    original_connect = postgres._connect
    calls = [ping_connection, schema_connection]

    try:
        postgres._connect = lambda database_url: calls.pop(0)
        checker.ping()
        ready = checker.schema_ready()
    finally:
        postgres._connect = original_connect

    assert ready is True
    assert ping_connection.executed[0][0] == "SET statement_timeout = 250"
    assert ping_connection.executed[1][0] == 'SET search_path TO "custom", public'
    assert ping_connection.executed[2][0] == "SELECT 1"
    assert "FROM information_schema.tables" in schema_connection.executed[2][0]

    not_ready_connection = FakeConnection()
    not_ready_connection.fetchall_results.append([{"table_name": "workspaces"}])
    try:
        postgres._connect = lambda database_url: not_ready_connection
        not_ready = checker.schema_ready()
    finally:
        postgres._connect = original_connect

    assert not_ready is False


def test_postgres_workspace_repository_create_update_and_queries() -> None:
    from ctxledger.db.postgres import PostgresWorkspaceRepository

    connection = FakeConnection()
    repo = PostgresWorkspaceRepository(connection)
    workspace = sample_workspace()

    connection.fetchone_results.append(
        {
            "workspace_id": workspace.workspace_id,
            "repo_url": workspace.repo_url,
            "canonical_path": workspace.canonical_path,
            "default_branch": workspace.default_branch,
            "metadata_json": workspace.metadata,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }
    )
    created = repo.create(workspace)
    assert created == workspace

    updated_workspace = Workspace(
        workspace_id=workspace.workspace_id,
        repo_url=workspace.repo_url,
        canonical_path="/tmp/updated-repo",
        default_branch="develop",
        metadata={"language": "python", "team": "platform"},
        created_at=workspace.created_at,
        updated_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    connection.fetchone_results.append(
        {
            "workspace_id": updated_workspace.workspace_id,
            "repo_url": updated_workspace.repo_url,
            "canonical_path": updated_workspace.canonical_path,
            "default_branch": updated_workspace.default_branch,
            "metadata_json": updated_workspace.metadata,
            "created_at": updated_workspace.created_at,
            "updated_at": updated_workspace.updated_at,
        }
    )
    updated = repo.update(updated_workspace)
    assert updated == updated_workspace

    connection.fetchone_results.append(
        {
            "workspace_id": workspace.workspace_id,
            "repo_url": workspace.repo_url,
            "canonical_path": workspace.canonical_path,
            "default_branch": workspace.default_branch,
            "metadata_json": workspace.metadata,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }
    )
    assert repo.get_by_id(workspace.workspace_id) == workspace

    connection.fetchone_results.append(None)
    assert repo.get_by_id(uuid4()) is None

    connection.fetchone_results.append(
        {
            "workspace_id": workspace.workspace_id,
            "repo_url": workspace.repo_url,
            "canonical_path": workspace.canonical_path,
            "default_branch": workspace.default_branch,
            "metadata_json": workspace.metadata,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }
    )
    assert repo.get_by_canonical_path(workspace.canonical_path) == workspace

    connection.fetchall_results.append(
        [
            {
                "workspace_id": workspace.workspace_id,
                "repo_url": workspace.repo_url,
                "canonical_path": workspace.canonical_path,
                "default_branch": workspace.default_branch,
                "metadata_json": workspace.metadata,
                "created_at": workspace.created_at,
                "updated_at": workspace.updated_at,
            },
            {
                "workspace_id": updated_workspace.workspace_id,
                "repo_url": updated_workspace.repo_url,
                "canonical_path": updated_workspace.canonical_path,
                "default_branch": updated_workspace.default_branch,
                "metadata_json": updated_workspace.metadata,
                "created_at": updated_workspace.created_at,
                "updated_at": updated_workspace.updated_at,
            },
        ]
    )
    by_repo = repo.get_by_repo_url(workspace.repo_url)
    assert by_repo == [workspace, updated_workspace]

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to insert workspace"):
        repo.create(workspace)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to update workspace"):
        repo.update(workspace)


def test_postgres_workflow_instance_repository_create_update_and_list_recent() -> None:
    from ctxledger.db.postgres import PostgresWorkflowInstanceRepository

    connection = FakeConnection()
    repo = PostgresWorkflowInstanceRepository(connection)
    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)

    connection.fetchone_results.append(
        {
            "workflow_instance_id": workflow.workflow_instance_id,
            "workspace_id": workflow.workspace_id,
            "ticket_id": workflow.ticket_id,
            "status": workflow.status.value,
            "metadata_json": workflow.metadata,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )
    created = repo.create(workflow)
    assert created == workflow

    updated_workflow = WorkflowInstance(
        workflow_instance_id=workflow.workflow_instance_id,
        workspace_id=workflow.workspace_id,
        ticket_id="TICKET-456",
        status=WorkflowInstanceStatus.COMPLETED,
        metadata={"priority": "low"},
        created_at=workflow.created_at,
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    connection.fetchone_results.append(
        {
            "workflow_instance_id": updated_workflow.workflow_instance_id,
            "workspace_id": updated_workflow.workspace_id,
            "ticket_id": updated_workflow.ticket_id,
            "status": updated_workflow.status.value,
            "metadata_json": updated_workflow.metadata,
            "created_at": updated_workflow.created_at,
            "updated_at": updated_workflow.updated_at,
        }
    )
    updated = repo.update(updated_workflow)
    assert updated == updated_workflow

    connection.fetchone_results.append(
        {
            "workflow_instance_id": workflow.workflow_instance_id,
            "workspace_id": workflow.workspace_id,
            "ticket_id": workflow.ticket_id,
            "status": workflow.status.value,
            "metadata_json": workflow.metadata,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )
    assert repo.get_by_id(workflow.workflow_instance_id) == workflow

    connection.fetchone_results.append(
        {
            "workflow_instance_id": workflow.workflow_instance_id,
            "workspace_id": workflow.workspace_id,
            "ticket_id": workflow.ticket_id,
            "status": workflow.status.value,
            "metadata_json": workflow.metadata,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )
    assert repo.get_running_by_workspace_id(workflow.workspace_id) == workflow

    connection.fetchone_results.append(
        {
            "workflow_instance_id": updated_workflow.workflow_instance_id,
            "workspace_id": updated_workflow.workspace_id,
            "ticket_id": updated_workflow.ticket_id,
            "status": updated_workflow.status.value,
            "metadata_json": updated_workflow.metadata,
            "created_at": updated_workflow.created_at,
            "updated_at": updated_workflow.updated_at,
        }
    )
    assert repo.get_latest_by_workspace_id(workflow.workspace_id) == updated_workflow

    another_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workflow.workspace_id,
        ticket_id="TICKET-789",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
        updated_at=datetime(2024, 1, 7, tzinfo=UTC),
    )
    connection.fetchall_results.append(
        [
            {
                "workflow_instance_id": updated_workflow.workflow_instance_id,
                "workspace_id": updated_workflow.workspace_id,
                "ticket_id": updated_workflow.ticket_id,
                "status": updated_workflow.status.value,
                "metadata_json": updated_workflow.metadata,
                "created_at": updated_workflow.created_at,
                "updated_at": updated_workflow.updated_at,
            },
            {
                "workflow_instance_id": another_workflow.workflow_instance_id,
                "workspace_id": another_workflow.workspace_id,
                "ticket_id": another_workflow.ticket_id,
                "status": another_workflow.status.value,
                "metadata_json": another_workflow.metadata,
                "created_at": another_workflow.created_at,
                "updated_at": another_workflow.updated_at,
            },
        ]
    )
    recent = repo.list_recent(
        limit=5,
        status=WorkflowInstanceStatus.RUNNING.value,
        workspace_id=workflow.workspace_id,
        ticket_id="TICKET",
    )
    assert recent == (updated_workflow, another_workflow)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to insert workflow instance"):
        repo.create(workflow)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to update workflow instance"):
        repo.update(workflow)


def test_postgres_workflow_attempt_repository_create_update_and_next_number() -> None:
    from ctxledger.db.postgres import PostgresWorkflowAttemptRepository

    connection = FakeConnection()
    repo = PostgresWorkflowAttemptRepository(connection)
    attempt = sample_attempt(uuid4())

    connection.fetchone_results.append(
        {
            "attempt_id": attempt.attempt_id,
            "workflow_instance_id": attempt.workflow_instance_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status.value,
            "failure_reason": attempt.failure_reason,
            "verify_status": attempt.verify_status.value,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
    )
    created = repo.create(attempt)
    assert created == attempt

    updated_attempt = WorkflowAttempt(
        attempt_id=attempt.attempt_id,
        workflow_instance_id=attempt.workflow_instance_id,
        attempt_number=attempt.attempt_number,
        status=WorkflowAttemptStatus.SUCCEEDED,
        failure_reason=None,
        verify_status=VerifyStatus.PASSED,
        started_at=attempt.started_at,
        finished_at=datetime(2024, 1, 6, tzinfo=UTC),
        created_at=attempt.created_at,
        updated_at=datetime(2024, 1, 6, tzinfo=UTC),
    )
    connection.fetchone_results.append(
        {
            "attempt_id": updated_attempt.attempt_id,
            "workflow_instance_id": updated_attempt.workflow_instance_id,
            "attempt_number": updated_attempt.attempt_number,
            "status": updated_attempt.status.value,
            "failure_reason": updated_attempt.failure_reason,
            "verify_status": updated_attempt.verify_status.value,
            "started_at": updated_attempt.started_at,
            "finished_at": updated_attempt.finished_at,
            "created_at": updated_attempt.created_at,
            "updated_at": updated_attempt.updated_at,
        }
    )
    updated = repo.update(updated_attempt)
    assert updated == updated_attempt

    connection.fetchone_results.append(
        {
            "attempt_id": attempt.attempt_id,
            "workflow_instance_id": attempt.workflow_instance_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status.value,
            "failure_reason": attempt.failure_reason,
            "verify_status": attempt.verify_status.value,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
    )
    assert repo.get_by_id(attempt.attempt_id) == attempt

    connection.fetchone_results.append(
        {
            "attempt_id": attempt.attempt_id,
            "workflow_instance_id": attempt.workflow_instance_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status.value,
            "failure_reason": attempt.failure_reason,
            "verify_status": attempt.verify_status.value,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
    )
    assert repo.get_running_by_workflow_id(attempt.workflow_instance_id) == attempt

    connection.fetchone_results.append(
        {
            "attempt_id": updated_attempt.attempt_id,
            "workflow_instance_id": updated_attempt.workflow_instance_id,
            "attempt_number": updated_attempt.attempt_number,
            "status": updated_attempt.status.value,
            "failure_reason": updated_attempt.failure_reason,
            "verify_status": updated_attempt.verify_status.value,
            "started_at": updated_attempt.started_at,
            "finished_at": updated_attempt.finished_at,
            "created_at": updated_attempt.created_at,
            "updated_at": updated_attempt.updated_at,
        }
    )
    assert (
        repo.get_latest_by_workflow_id(attempt.workflow_instance_id) == updated_attempt
    )

    connection.fetchone_results.append({"max_attempt_number": 3})
    assert repo.get_next_attempt_number(attempt.workflow_instance_id) == 4

    connection.fetchone_results.append(None)
    assert repo.get_next_attempt_number(attempt.workflow_instance_id) == 1

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to insert workflow attempt"):
        repo.create(attempt)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to update workflow attempt"):
        repo.update(attempt)


def test_postgres_checkpoint_verify_episode_repositories_create_and_lookup() -> None:
    from ctxledger.db.postgres import (
        PostgresMemoryEpisodeRepository,
        PostgresVerifyReportRepository,
        PostgresWorkflowCheckpointRepository,
    )

    connection = FakeConnection()
    checkpoint_repo = PostgresWorkflowCheckpointRepository(connection)
    verify_repo = PostgresVerifyReportRepository(connection)
    episode_repo = PostgresMemoryEpisodeRepository(connection)

    workflow = sample_workflow(uuid4())
    attempt = sample_attempt(workflow.workflow_instance_id)
    checkpoint = sample_checkpoint(workflow.workflow_instance_id, attempt.attempt_id)
    verify_report = sample_verify_report(attempt.attempt_id)
    episode = importlib.import_module("ctxledger.workflow.service").EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        summary="Episode summary",
        attempt_id=attempt.attempt_id,
        metadata={"kind": "checkpoint"},
        status="recorded",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
        updated_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    connection.fetchone_results.append(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workflow_instance_id": checkpoint.workflow_instance_id,
            "attempt_id": checkpoint.attempt_id,
            "step_name": checkpoint.step_name,
            "summary": checkpoint.summary,
            "checkpoint_json": checkpoint.checkpoint_json,
            "created_at": checkpoint.created_at,
        }
    )
    assert checkpoint_repo.create(checkpoint) == checkpoint

    connection.fetchone_results.append(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workflow_instance_id": checkpoint.workflow_instance_id,
            "attempt_id": checkpoint.attempt_id,
            "step_name": checkpoint.step_name,
            "summary": checkpoint.summary,
            "checkpoint_json": checkpoint.checkpoint_json,
            "created_at": checkpoint.created_at,
        }
    )
    assert (
        checkpoint_repo.get_latest_by_workflow_id(workflow.workflow_instance_id)
        == checkpoint
    )

    connection.fetchone_results.append(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workflow_instance_id": checkpoint.workflow_instance_id,
            "attempt_id": checkpoint.attempt_id,
            "step_name": checkpoint.step_name,
            "summary": checkpoint.summary,
            "checkpoint_json": checkpoint.checkpoint_json,
            "created_at": checkpoint.created_at,
        }
    )
    assert checkpoint_repo.get_latest_by_attempt_id(attempt.attempt_id) == checkpoint

    connection.fetchone_results.append(
        {
            "verify_id": verify_report.verify_id,
            "attempt_id": verify_report.attempt_id,
            "status": verify_report.status.value,
            "report_json": verify_report.report_json,
            "created_at": verify_report.created_at,
        }
    )
    assert verify_repo.create(verify_report) == verify_report

    connection.fetchone_results.append(
        {
            "verify_id": verify_report.verify_id,
            "attempt_id": verify_report.attempt_id,
            "status": verify_report.status.value,
            "report_json": verify_report.report_json,
            "created_at": verify_report.created_at,
        }
    )
    assert verify_repo.get_latest_by_attempt_id(attempt.attempt_id) == verify_report

    connection.fetchone_results.append(
        {
            "episode_id": episode.episode_id,
            "workflow_instance_id": episode.workflow_instance_id,
            "summary": episode.summary,
            "attempt_id": episode.attempt_id,
            "metadata_json": episode.metadata,
            "status": episode.status,
            "created_at": episode.created_at,
            "updated_at": episode.updated_at,
        }
    )
    assert episode_repo.create(episode) == episode

    connection.fetchall_results.append(
        [
            {
                "episode_id": episode.episode_id,
                "workflow_instance_id": episode.workflow_instance_id,
                "summary": episode.summary,
                "attempt_id": episode.attempt_id,
                "metadata_json": episode.metadata,
                "status": episode.status,
                "created_at": episode.created_at,
                "updated_at": episode.updated_at,
            }
        ]
    )
    assert episode_repo.list_by_workflow_id(workflow.workflow_instance_id, limit=5) == (
        episode,
    )


def test_postgres_memory_item_and_embedding_repositories_create_and_list() -> None:
    from ctxledger.db.postgres import (
        PostgresMemoryEmbeddingRepository,
        PostgresMemoryItemRepository,
    )

    connection = FakeConnection()
    item_repo = PostgresMemoryItemRepository(connection)
    embedding_repo = PostgresMemoryEmbeddingRepository(connection)

    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Stored memory item",
        metadata={"kind": "note"},
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_item.memory_id,
        embedding_model="test-model",
        embedding=(0.1, 0.2, 0.3),
        content_hash="hash-123",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    connection.fetchone_results.append(
        {
            "memory_id": memory_item.memory_id,
            "workspace_id": memory_item.workspace_id,
            "episode_id": memory_item.episode_id,
            "type": memory_item.type,
            "provenance": memory_item.provenance,
            "content": memory_item.content,
            "metadata_json": memory_item.metadata,
            "created_at": memory_item.created_at,
            "updated_at": memory_item.updated_at,
        }
    )
    assert item_repo.create(memory_item) == memory_item

    connection.fetchall_results.append(
        [
            {
                "memory_id": memory_item.memory_id,
                "workspace_id": memory_item.workspace_id,
                "episode_id": memory_item.episode_id,
                "type": memory_item.type,
                "provenance": memory_item.provenance,
                "content": memory_item.content,
                "metadata_json": memory_item.metadata,
                "created_at": memory_item.created_at,
                "updated_at": memory_item.updated_at,
            }
        ]
    )
    assert item_repo.list_by_workspace_id(memory_item.workspace_id, limit=5) == (
        memory_item,
    )

    connection.fetchall_results.append(
        [
            {
                "memory_id": memory_item.memory_id,
                "workspace_id": memory_item.workspace_id,
                "episode_id": memory_item.episode_id,
                "type": memory_item.type,
                "provenance": memory_item.provenance,
                "content": memory_item.content,
                "metadata_json": memory_item.metadata,
                "created_at": memory_item.created_at,
                "updated_at": memory_item.updated_at,
            }
        ]
    )
    assert item_repo.list_by_episode_id(memory_item.episode_id, limit=5) == (
        memory_item,
    )

    connection.fetchone_results.append(
        {
            "memory_embedding_id": embedding.memory_embedding_id,
            "memory_id": embedding.memory_id,
            "embedding_model": embedding.embedding_model,
            "embedding": "[0.1,0.2,0.3]",
            "content_hash": embedding.content_hash,
            "created_at": embedding.created_at,
        }
    )
    created_embedding = embedding_repo.create(embedding)
    assert created_embedding.embedding == (0.1, 0.2, 0.3)

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding.memory_embedding_id,
                "memory_id": embedding.memory_id,
                "embedding_model": embedding.embedding_model,
                "embedding": [0.1, 0.2, 0.3],
                "content_hash": embedding.content_hash,
                "created_at": embedding.created_at,
            }
        ]
    )
    listed = embedding_repo.list_by_memory_id(memory_item.memory_id, limit=5)
    assert len(listed) == 1
    assert listed[0].embedding == (0.1, 0.2, 0.3)

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding.memory_embedding_id,
                "memory_id": embedding.memory_id,
                "embedding_model": embedding.embedding_model,
                "embedding": "[0.1,0.2,0.3]",
                "content_hash": embedding.content_hash,
                "created_at": embedding.created_at,
            }
        ]
    )
    similar = embedding_repo.find_similar((0.1, 0.2, 0.3), limit=3)
    assert len(similar) == 1
    assert similar[0].memory_id == memory_item.memory_id

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding.memory_embedding_id,
                "memory_id": embedding.memory_id,
                "embedding_model": embedding.embedding_model,
                "embedding": "[0.1,0.2,0.3]",
                "content_hash": embedding.content_hash,
                "created_at": embedding.created_at,
            }
        ]
    )
    similar_with_workspace = embedding_repo.find_similar(
        (0.1, 0.2, 0.3),
        limit=3,
        workspace_id=memory_item.workspace_id,
    )
    assert len(similar_with_workspace) == 1

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to create memory item"):
        item_repo.create(memory_item)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to create memory embedding"):
        embedding_repo.create(embedding)


def test_postgres_unit_of_work_and_factory_cover_pool_lifecycle() -> None:
    from ctxledger.db.postgres import (
        PostgresConfig,
        PostgresUnitOfWork,
        build_postgres_uow_factory,
    )

    connection = FakeConnection()

    class PoolConnectionContext:
        def __init__(self, conn: FakeConnection) -> None:
            self._conn = conn
            self.exit_calls: list[tuple[object, object, object]] = []

        def __enter__(self) -> FakeConnection:
            return self._conn

        def __exit__(self, exc_type, exc, tb) -> None:
            self.exit_calls.append((exc_type, exc, tb))

    class FakePool:
        def __init__(self, conn: FakeConnection) -> None:
            self._context = PoolConnectionContext(conn)

        def connection(self) -> PoolConnectionContext:
            return self._context

    config = PostgresConfig(
        database_url="postgresql://example/db",
        statement_timeout_ms=123,
        schema_name="custom",
    )
    pool = FakePool(connection)
    uow = PostgresUnitOfWork(config, pool)

    with uow as current:
        assert current.workspaces is not None
        assert current.workflow_instances is not None
        assert current.workflow_attempts is not None
        assert current.workflow_checkpoints is not None
        assert current.verify_reports is not None
        assert current.memory_items is not None
        assert current.memory_embeddings is not None
        current.commit()

    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert pool._context.exit_calls == [(None, None, None)]
    assert connection.executed[0][0] == "SET statement_timeout = 123"
    assert connection.executed[1][0] == 'SET search_path TO "custom", public'

    rollback_connection = FakeConnection()
    rollback_pool = FakePool(rollback_connection)
    rollback_uow = PostgresUnitOfWork(config, rollback_pool)
    with rollback_uow:
        pass

    assert rollback_connection.commit_calls == 0
    assert rollback_connection.rollback_calls == 1

    exception_connection = FakeConnection()
    exception_pool = FakePool(exception_connection)
    exception_uow = PostgresUnitOfWork(config, exception_pool)
    with pytest.raises(RuntimeError, match="boom"):
        with exception_uow:
            raise RuntimeError("boom")

    assert exception_connection.rollback_calls == 1

    inactive_uow = PostgresUnitOfWork(config, pool)
    with pytest.raises(PersistenceError, match="Unit of work is not active"):
        inactive_uow.commit()
    with pytest.raises(PersistenceError, match="Unit of work is not active"):
        inactive_uow.rollback()

    factory = build_postgres_uow_factory(config, pool)
    produced_uow = factory()
    assert isinstance(produced_uow, PostgresUnitOfWork)

    with pytest.raises(
        ValueError,
        match="A shared PostgreSQL connection pool is required",
    ):
        build_postgres_uow_factory(config, None)


def test_postgres_row_mapping_helpers_cover_memory_records() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")
    memory_id = uuid4()
    workspace_id = uuid4()
    episode_id = uuid4()
    embedding_id = uuid4()

    item_record = postgres._memory_item_row_to_record(
        {
            "memory_id": memory_id,
            "workspace_id": workspace_id,
            "episode_id": episode_id,
            "type": "episode_note",
            "provenance": "episode",
            "content": "Memory item content",
            "metadata_json": {"kind": "note"},
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
        }
    )
    assert item_record.memory_id == memory_id
    assert item_record.workspace_id == workspace_id
    assert item_record.episode_id == episode_id

    item_without_optional_ids = postgres._memory_item_row_to_record(
        {
            "memory_id": memory_id,
            "workspace_id": None,
            "episode_id": None,
            "type": "episode_note",
            "provenance": "episode",
            "content": "Memory item content",
            "metadata_json": None,
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
        }
    )
    assert item_without_optional_ids.workspace_id is None
    assert item_without_optional_ids.episode_id is None
    assert item_without_optional_ids.metadata == {}

    embedding_record = postgres._memory_embedding_row_to_record(
        {
            "memory_embedding_id": embedding_id,
            "memory_id": memory_id,
            "embedding_model": "test-model",
            "embedding": "[1,2.5]",
            "content_hash": "hash-123",
            "created_at": datetime(2024, 1, 3, tzinfo=UTC),
        }
    )
    assert embedding_record.memory_embedding_id == embedding_id
    assert embedding_record.embedding == (1.0, 2.5)
    assert embedding_record.content_hash == "hash-123"

    embedding_without_hash = postgres._memory_embedding_row_to_record(
        {
            "memory_embedding_id": embedding_id,
            "memory_id": memory_id,
            "embedding_model": "test-model",
            "embedding": None,
            "content_hash": None,
            "created_at": datetime(2024, 1, 3, tzinfo=UTC),
        }
    )
    assert embedding_without_hash.embedding == ()
    assert embedding_without_hash.content_hash is None


def test_postgres_connect_requires_driver_and_passes_row_factory() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")
    original_psycopg = postgres.psycopg
    original_dict_row = postgres.dict_row

    try:
        postgres.psycopg = None
        postgres.dict_row = None
        with pytest.raises(RuntimeError, match="psycopg is required"):
            postgres._require_psycopg()

        class FakePsycopg:
            def __init__(self) -> None:
                self.calls: list[tuple[str, object]] = []

            def connect(self, database_url: str, row_factory: object = None) -> str:
                self.calls.append((database_url, row_factory))
                return "CONNECTION"

        fake_psycopg = FakePsycopg()
        postgres.psycopg = fake_psycopg
        postgres.dict_row = "DICT_ROW"
        connection = postgres._connect("postgresql://example/db")
    finally:
        postgres.psycopg = original_psycopg
        postgres.dict_row = original_dict_row

    assert connection == "CONNECTION"
    assert fake_psycopg.calls == [("postgresql://example/db", "DICT_ROW")]
