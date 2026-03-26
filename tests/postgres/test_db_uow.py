from __future__ import annotations

import importlib
import logging
from types import SimpleNamespace, TracebackType

import pytest

from ctxledger.db import postgres_uow as postgres_uow_module
from ctxledger.memory.protocols import (
    MemorySummaryMembershipRepository,
    MemorySummaryRepository,
)
from ctxledger.workflow.service import (
    MemoryEmbeddingRepository,
    MemoryItemRepository,
    PersistenceError,
    UnitOfWork,
    VerifyReportRepository,
    WorkflowAttemptRepository,
    WorkflowCheckpointRepository,
    WorkflowInstanceRepository,
    WorkspaceRepository,
)

from .conftest import (
    FakeConnection,
    FakeConnectionPool,
    MemoryEmbeddingRepoStub,
    MemoryItemRepoStub,
    MemorySummaryMembershipRepoStub,
    MemorySummaryRepoStub,
    VerifyReportRepoStub,
    WorkflowAttemptRepoStub,
    WorkflowCheckpointRepoStub,
    WorkflowInstanceRepoStub,
    WorkspaceRepoStub,
    sample_attempt,
    sample_checkpoint,
    sample_verify_report,
    sample_workflow,
    sample_workspace,
)


def test_unit_of_work_contract_shape_can_be_satisfied_by_postgres_impl() -> None:
    class PostgresStyleUnitOfWork(UnitOfWork):
        def __init__(self) -> None:
            self.workspaces = WorkspaceRepoStub()
            self.workflow_instances = WorkflowInstanceRepoStub()
            self.workflow_attempts = WorkflowAttemptRepoStub()
            self.workflow_checkpoints = WorkflowCheckpointRepoStub()
            self.verify_reports = VerifyReportRepoStub()
            self.memory_items = MemoryItemRepoStub()
            self.memory_summaries = MemorySummaryRepoStub()
            self.memory_summary_memberships = MemorySummaryMembershipRepoStub()
            self.memory_embeddings = MemoryEmbeddingRepoStub()
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
    assert isinstance(uow.memory_summaries, MemorySummaryRepository)
    assert isinstance(uow.memory_summary_memberships, MemorySummaryMembershipRepository)
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

    original_perf_counter = postgres_uow_module.time.perf_counter
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

    postgres_uow_module.time.perf_counter = lambda: next(perf_counter_values)

    try:
        uow = postgres_module.PostgresUnitOfWork(config, pool)
        entered = uow.__enter__()
    finally:
        postgres_uow_module.time.perf_counter = original_perf_counter

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
                    workflow if workflow_instance_id == workflow.workflow_instance_id else None
                )
            )
            self.workflow_attempts = SimpleNamespace(
                get_running_by_workflow_id=lambda workflow_instance_id: (
                    attempt if workflow_instance_id == workflow.workflow_instance_id else None
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
        workflow_module.ResumeWorkflowInput(workflow_instance_id=workflow.workflow_instance_id)
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
        extra for message, extra in debug_messages if message == "resume_workflow complete"
    ]
    assert len(complete_extras) == 1
    complete_extra = complete_extras[0]
    assert isinstance(complete_extra, dict)
    assert complete_extra["uow_enter_duration_ms"] == 23
    assert complete_extra["pool_checkout_duration_ms"] == 17
    assert complete_extra["session_setup_duration_ms"] == 5
    assert complete_extra["checkout_context_create_duration_ms"] == 2


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
        assert current.memory_summaries is not None
        assert current.memory_summary_memberships is not None
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
