from __future__ import annotations

import importlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
from ctxledger.memory.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryFeature,
    MemoryItemRecord,
    MemoryServiceError,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeIssue,
    StartWorkflowInput,
    ValidationError,
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowService,
    Workspace,
)


def test_workflow_service_stats_helper_error_branches() -> None:
    class UnsupportedCountRepository:
        pass

    class UnsupportedStatusRepository:
        pass

    class UnsupportedDatetimeRepository:
        pass

    class UnsupportedProvenanceRepository:
        pass

    service = WorkflowService(lambda: None)

    with pytest.raises(
        Exception,
        match="stats counting is not supported for repository 'workspaces'",
    ):
        service._count_rows(
            SimpleNamespace(workspaces=UnsupportedCountRepository()),
            "workspaces",
        )

    with pytest.raises(
        Exception,
        match="stats status aggregation is not supported for repository 'workflow_instances'",
    ):
        service._count_grouped_statuses(
            SimpleNamespace(workflow_instances=UnsupportedStatusRepository()),
            repository_name="workflow_instances",
            allowed_statuses=("running",),
        )

    with pytest.raises(
        Exception,
        match="stats datetime aggregation is not supported for repository 'workflow_instances'",
    ):
        service._max_datetime_field(
            SimpleNamespace(workflow_instances=UnsupportedDatetimeRepository()),
            repository_name="workflow_instances",
            field_name="updated_at",
        )

    with pytest.raises(
        Exception,
        match="memory stats provenance aggregation is not supported for memory items",
    ):
        service._count_memory_item_provenance(
            SimpleNamespace(memory_items=UnsupportedProvenanceRepository())
        )


def test_workflow_service_validation_error_branches() -> None:
    service = WorkflowService(lambda: None)

    with pytest.raises(
        Exception,
        match="workflow cannot be completed into a non-terminal state",
    ):
        service._map_workflow_status_to_attempt_status(WorkflowInstanceStatus.RUNNING)

    with pytest.raises(
        Exception,
        match="status must be one of running, completed, failed, or cancelled",
    ):
        service.list_workflows(limit=1, status="paused")

    assert service.list_failures(limit=1, status="paused") == ()


def test_workflow_service_stats_and_listing_helpers_cover_repository_branches() -> None:
    class CountRepository:
        def __init__(self, count: int) -> None:
            self.count = count

        def count_all(self) -> int:
            return self.count

    now = datetime(2024, 10, 2, tzinfo=UTC)

    class StatsUow:
        def __init__(self) -> None:
            self.workspaces = CountRepository(2)
            self.workflow_checkpoints = SimpleNamespace(
                count_all=lambda: 5,
                max_datetime=lambda field_name: now,
                get_latest_by_workflow_id=lambda workflow_instance_id: None,
            )
            self.memory_episodes = SimpleNamespace(
                count_all=lambda: 7,
                max_datetime=lambda field_name: now,
            )
            self.memory_items = SimpleNamespace(
                count_all=lambda: 11,
                max_datetime=lambda field_name: now,
                count_by_provenance=lambda: {
                    "episode": 3,
                    "workflow_complete_auto": 2,
                },
            )
            self.memory_embeddings = SimpleNamespace(
                count_all=lambda: 13,
                max_datetime=lambda field_name: now,
            )
            self.memory_relations = SimpleNamespace(
                count_all=lambda: 17,
                max_datetime=lambda field_name: now,
            )
            self.workflow_instances = SimpleNamespace(
                count_by_status=lambda: {
                    "running": 2,
                    "completed": 1,
                    "unexpected": 99,
                },
                max_datetime=lambda field_name: now,
            )
            self.workflow_attempts = SimpleNamespace(
                count_by_status=lambda: {
                    "running": 1,
                    "succeeded": 4,
                    "ignored": 99,
                }
            )
            self.verify_reports = SimpleNamespace(
                count_by_status=lambda: {
                    "pending": 2,
                    "passed": 6,
                    "mystery": 5,
                },
                max_datetime=lambda field_name: now,
            )

        def __enter__(self) -> "StatsUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    service = WorkflowService(lambda: StatsUow())

    stats = service.get_stats()
    assert stats.workspace_count == 2
    assert stats.checkpoint_count == 5
    assert stats.episode_count == 7
    assert stats.memory_item_count == 11
    assert stats.memory_embedding_count == 13
    assert stats.workflow_status_counts == {
        "running": 2,
        "completed": 1,
        "failed": 0,
        "cancelled": 0,
    }
    assert stats.attempt_status_counts == {
        "running": 1,
        "succeeded": 4,
        "failed": 0,
        "cancelled": 0,
    }
    assert stats.verify_status_counts == {
        "pending": 2,
        "passed": 6,
        "failed": 0,
        "skipped": 0,
    }
    assert stats.latest_workflow_updated_at == now
    assert stats.latest_checkpoint_created_at == now
    assert stats.latest_verify_report_created_at == now
    assert stats.latest_episode_created_at == now
    assert stats.latest_memory_item_created_at == now
    assert stats.latest_memory_embedding_created_at == now

    memory_stats = service.get_memory_stats()
    assert memory_stats.episode_count == 7
    assert memory_stats.memory_item_count == 11
    assert memory_stats.memory_embedding_count == 13
    assert memory_stats.memory_relation_count == 17
    assert memory_stats.memory_item_provenance_counts == {
        "episode": 3,
        "workflow_complete_auto": 2,
    }
    assert memory_stats.latest_memory_relation_created_at == now

    workspace_id = uuid4()
    workflow_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()
    verify_id = uuid4()

    class ListedUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda value: Workspace(
                    workspace_id=value,
                    repo_url="https://example.com/repo.git",
                    canonical_path="/tmp/repo",
                    default_branch="main",
                    metadata={},
                    created_at=now,
                    updated_at=now,
                )
            )
            self.workflow_instances = SimpleNamespace(
                list_recent=lambda **kwargs: (
                    WorkflowInstance(
                        workflow_instance_id=workflow_id,
                        workspace_id=workspace_id,
                        ticket_id="T-123",
                        status=WorkflowInstanceStatus.RUNNING,
                        metadata={},
                        created_at=now,
                        updated_at=now,
                    ),
                )
            )
            self.workflow_attempts = SimpleNamespace(
                get_latest_by_workflow_id=lambda value: WorkflowAttempt(
                    attempt_id=attempt_id,
                    workflow_instance_id=value,
                    attempt_number=2,
                    status=WorkflowAttemptStatus.RUNNING,
                    failure_reason=None,
                    verify_status=VerifyStatus.PASSED,
                    started_at=now,
                    finished_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda value: WorkflowCheckpoint(
                    checkpoint_id=checkpoint_id,
                    workflow_instance_id=value,
                    attempt_id=attempt_id,
                    step_name="implement-tests",
                    summary="Added targeted tests",
                    checkpoint_json={},
                    created_at=now,
                )
            )
            self.verify_reports = SimpleNamespace(
                get_latest_by_attempt_id=lambda value: VerifyReport(
                    verify_id=verify_id,
                    attempt_id=value,
                    status=VerifyStatus.FAILED,
                    report_json={},
                    created_at=now,
                )
            )

        def __enter__(self) -> "ListedUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    service = WorkflowService(lambda: ListedUow())
    entries = service.list_workflows(
        limit=2,
        status=" running ",
        ticket_id=" T-123 ",
    )
    assert len(entries) == 1
    assert entries[0].canonical_path == "/tmp/repo"
    assert entries[0].latest_step_name == "implement-tests"
    assert entries[0].latest_verify_status == VerifyStatus.FAILED.value

    class FallbackUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(get_by_id=lambda value: None)
            self.workflow_instances = SimpleNamespace(
                list_recent=lambda **kwargs: (
                    WorkflowInstance(
                        workflow_instance_id=workflow_id,
                        workspace_id=workspace_id,
                        ticket_id="T-456",
                        status=WorkflowInstanceStatus.COMPLETED,
                        metadata={},
                        created_at=now,
                        updated_at=now,
                    ),
                )
            )
            self.workflow_attempts = SimpleNamespace(
                get_latest_by_workflow_id=lambda value: WorkflowAttempt(
                    attempt_id=attempt_id,
                    workflow_instance_id=value,
                    attempt_number=1,
                    status=WorkflowAttemptStatus.SUCCEEDED,
                    failure_reason=None,
                    verify_status=VerifyStatus.SKIPPED,
                    started_at=now,
                    finished_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda value: None
            )
            self.verify_reports = SimpleNamespace(
                get_latest_by_attempt_id=lambda value: None
            )

        def __enter__(self) -> "FallbackUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    service = WorkflowService(lambda: FallbackUow())
    fallback_entries = service.list_workflows(limit=1, status="   ", ticket_id="   ")
    assert len(fallback_entries) == 1
    assert fallback_entries[0].canonical_path is None
    assert fallback_entries[0].latest_step_name is None
    assert fallback_entries[0].latest_verify_status == VerifyStatus.SKIPPED.value


def test_workflow_service_stats_and_listing_cover_none_and_validation_paths() -> None:
    class NoneStatsUow:
        def __init__(self) -> None:
            self.workspaces = None
            self.workflow_checkpoints = None
            self.memory_episodes = None
            self.memory_items = None
            self.memory_embeddings = None
            self.memory_relations = None
            self.workflow_instances = None
            self.workflow_attempts = None
            self.verify_reports = None

        def __enter__(self) -> "NoneStatsUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    service = WorkflowService(lambda: NoneStatsUow())
    stats = service.get_stats()
    assert stats.workspace_count == 0
    assert stats.checkpoint_count == 0
    assert stats.episode_count == 0
    assert stats.memory_item_count == 0
    assert stats.memory_embedding_count == 0
    assert stats.workflow_status_counts == {
        "running": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
    }
    assert stats.attempt_status_counts == {
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "cancelled": 0,
    }
    assert stats.verify_status_counts == {
        "pending": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
    }
    assert stats.latest_workflow_updated_at is None
    assert stats.latest_checkpoint_created_at is None
    assert stats.latest_verify_report_created_at is None
    assert stats.latest_episode_created_at is None
    assert stats.latest_memory_item_created_at is None
    assert stats.latest_memory_embedding_created_at is None

    memory_stats = service.get_memory_stats()
    assert memory_stats.episode_count == 0
    assert memory_stats.memory_item_count == 0
    assert memory_stats.memory_embedding_count == 0
    assert memory_stats.memory_relation_count == 0
    assert memory_stats.memory_item_provenance_counts == {}
    assert memory_stats.latest_episode_created_at is None
    assert memory_stats.latest_memory_item_created_at is None
    assert memory_stats.latest_memory_embedding_created_at is None
    assert memory_stats.latest_memory_relation_created_at is None

    with pytest.raises(ValidationError, match="limit must be greater than zero"):
        service.list_workflows(limit=0)

    assert service.list_failures(limit=0) == ()


def test_workflow_service_resume_and_completion_warning_branches() -> None:
    service = WorkflowService(lambda: None)

    running_workspace = Workspace(
        workspace_id=uuid4(),
        repo_url="https://example.com/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
        metadata={},
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 1, tzinfo=UTC),
    )
    running_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=running_workspace.workspace_id,
        ticket_id="resume-1",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={},
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 1, tzinfo=UTC),
    )
    running_attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=running_workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        failure_reason=None,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 10, 1, tzinfo=UTC),
        finished_at=None,
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 1, tzinfo=UTC),
    )

    assert (
        service._classify_resumable_status(
            running_workflow,
            None,
            None,
            [ResumeIssue(code="running_workflow_without_attempt", message="missing")],
        )
        == ResumableStatus.INCONSISTENT
    )
    assert (
        service._classify_resumable_status(
            running_workflow,
            None,
            None,
            [],
        )
        == ResumableStatus.BLOCKED
    )
    assert (
        service._classify_resumable_status(
            running_workflow,
            WorkflowAttempt(
                attempt_id=running_attempt.attempt_id,
                workflow_instance_id=running_attempt.workflow_instance_id,
                attempt_number=running_attempt.attempt_number,
                status=WorkflowAttemptStatus.SUCCEEDED,
                failure_reason=None,
                verify_status=running_attempt.verify_status,
                started_at=running_attempt.started_at,
                finished_at=datetime(2024, 10, 2, tzinfo=UTC),
                created_at=running_attempt.created_at,
                updated_at=datetime(2024, 10, 2, tzinfo=UTC),
            ),
            None,
            [],
        )
        == ResumableStatus.BLOCKED
    )
    assert (
        service._classify_resumable_status(
            running_workflow,
            running_attempt,
            None,
            [],
        )
        == ResumableStatus.BLOCKED
    )

    terminal_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=running_workspace.workspace_id,
        ticket_id="resume-2",
        status=WorkflowInstanceStatus.COMPLETED,
        metadata={},
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 2, tzinfo=UTC),
    )
    assert (
        service._classify_resumable_status(
            terminal_workflow,
            running_attempt,
            None,
            [],
        )
        == ResumableStatus.TERMINAL
    )

    checkpoint_without_summary = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=running_workflow.workflow_instance_id,
        attempt_id=running_attempt.attempt_id,
        step_name="investigate",
        summary=None,
        checkpoint_json={},
        created_at=datetime(2024, 10, 2, tzinfo=UTC),
    )
    assert (
        service._derive_next_hint(
            terminal_workflow,
            running_attempt,
            checkpoint_without_summary,
            ResumableStatus.TERMINAL,
        )
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            None,
            None,
            ResumableStatus.BLOCKED,
        )
        == "No attempt is available. Inspect workflow consistency before continuing."
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            running_attempt,
            None,
            ResumableStatus.BLOCKED,
        )
        == "Create an initial checkpoint to establish resumable state."
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            running_attempt,
            checkpoint_without_summary,
            ResumableStatus.RESUMABLE,
        )
        == "Resume from step 'investigate'."
    )
    checkpoint_with_summary = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=running_workflow.workflow_instance_id,
        attempt_id=running_attempt.attempt_id,
        step_name="implement",
        summary="Added the missing branch",
        checkpoint_json={},
        created_at=datetime(2024, 10, 2, tzinfo=UTC),
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            running_attempt,
            checkpoint_with_summary,
            ResumableStatus.RESUMABLE,
        )
        == "Resume from step 'implement' using the latest checkpoint summary."
    )

    warnings = service._build_resume_warnings(
        running_workflow,
        running_attempt,
        checkpoint_with_summary,
        None,
    )
    warning_codes = {warning.code for warning in warnings}
    assert "missing_verify_report" in warning_codes

    class ExplodingBridge:
        embedding_generator = None

        def record_workflow_completion_memory(self, **kwargs: object) -> object:
            raise RuntimeError("bridge exploded")

    store = InMemoryStore.create()
    complete_service = WorkflowService(
        build_in_memory_uow_factory(store),
        workflow_memory_bridge=ExplodingBridge(),
    )
    workspace = complete_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
        )
    )
    started = complete_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="completion-warning",
        )
    )
    result = complete_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )
    assert result.auto_memory_details is None
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "auto_memory_recording_failed"


def test_memory_uow_module_reexports_expected_symbols() -> None:
    module = importlib.import_module("ctxledger.db.memory_uow")

    assert module.make_in_memory_uow_factory is module.build_in_memory_uow_factory
    assert "make_in_memory_uow_factory" in module.__all__
    assert "InMemoryUnitOfWork" in module.__all__


def test_in_memory_workspace_repository_update_replaces_canonical_path_index() -> None:
    from ctxledger.db import InMemoryWorkspaceRepository

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
    from ctxledger.db import InMemoryWorkflowInstanceRepository

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
    from ctxledger.db import InMemoryWorkflowAttemptRepository

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
    from ctxledger.db import (
        InMemoryVerifyReportRepository,
        InMemoryWorkflowCheckpointRepository,
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


def test_in_memory_workflow_instance_repository_list_methods_cover_recent_ordering() -> (
    None
):
    from ctxledger.db import InMemoryWorkflowInstanceRepository

    workspace_id = uuid4()
    other_workspace_id = uuid4()
    first = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="TICKET-A",
        status=WorkflowInstanceStatus.RUNNING,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    second = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="TICKET-B",
        status=WorkflowInstanceStatus.COMPLETED,
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, tzinfo=UTC),
    )
    third = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=other_workspace_id,
        ticket_id="TICKET-A",
        status=WorkflowInstanceStatus.RUNNING,
        created_at=datetime(2024, 1, 5, tzinfo=UTC),
        updated_at=datetime(2024, 1, 6, tzinfo=UTC),
    )

    repo = InMemoryWorkflowInstanceRepository(
        {
            first.workflow_instance_id: first,
            second.workflow_instance_id: second,
            third.workflow_instance_id: third,
        }
    )

    assert repo.list_by_workspace_id(workspace_id, limit=5) == (second, first)
    assert repo.list_by_ticket_id("TICKET-A", limit=5) == (third, first)


def test_unit_of_work_lookup_repository_handles_missing_workflow_and_projection_absence() -> (
    None
):
    missing_uow = SimpleNamespace(
        __enter__=lambda self: self,
        __exit__=lambda self, exc_type, exc, tb: None,
        workflow_instances=SimpleNamespace(get_by_id=lambda workflow_id: None),
    )

    class MissingUow:
        def __enter__(self) -> object:
            return missing_uow

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    repo = UnitOfWorkWorkflowLookupRepository(lambda: MissingUow())
    workflow_id = uuid4()

    assert repo.workflow_exists(workflow_id) is False
    assert repo.workflow_freshness_by_id(workflow_id) == {
        "workflow_status": None,
        "workflow_is_terminal": None,
        "workflow_updated_at": None,
        "latest_attempt_status": None,
        "latest_attempt_is_terminal": None,
        "has_latest_attempt": False,
        "latest_attempt_verify_status": None,
        "latest_attempt_started_at": None,
        "has_latest_checkpoint": False,
        "latest_checkpoint_created_at": None,
        "latest_verify_report_created_at": None,
    }

    workspace_id = uuid4()
    workflow = WorkflowInstance(
        workflow_instance_id=workflow_id,
        workspace_id=workspace_id,
        ticket_id="NO-PROJECTION",
        status=WorkflowInstanceStatus.RUNNING,
        updated_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 1, 2, tzinfo=UTC),
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    class NoProjectionUow:
        def __enter__(self) -> "NoProjectionUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        workflow_instances = SimpleNamespace(
            get_by_id=lambda self, workflow_id_arg=None: workflow
        )  # type: ignore[assignment]
        workflow_attempts = SimpleNamespace(
            get_latest_by_workflow_id=lambda workflow_id_arg: attempt
        )
        workflow_checkpoints = SimpleNamespace(
            get_latest_by_workflow_id=lambda workflow_id_arg: None
        )
        verify_reports = SimpleNamespace(
            get_latest_by_attempt_id=lambda attempt_id_arg: None
        )

    repo = UnitOfWorkWorkflowLookupRepository(lambda: NoProjectionUow())
    freshness = repo.workflow_freshness_by_id(workflow_id)

    assert repo.workflow_exists(workflow_id) is True
    assert freshness["workflow_status"] == "running"
    assert freshness["has_latest_attempt"] is True
    assert freshness["has_latest_checkpoint"] is False


def test_unit_of_work_lookup_repository_lists_workspace_and_ticket_workflows() -> None:
    workspace_id = uuid4()
    matching_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace_id,
        ticket_id="LOOKUP-1",
        status=WorkflowInstanceStatus.RUNNING,
        updated_at=datetime(2024, 3, 1, tzinfo=UTC),
    )
    other_workspace_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="LOOKUP-1",
        status=WorkflowInstanceStatus.RUNNING,
        updated_at=datetime(2024, 3, 2, tzinfo=UTC),
    )

    class LookupUow:
        def __enter__(self) -> "LookupUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        workflow_instances = SimpleNamespace(
            get_by_id=lambda workflow_instance_id: (
                matching_workflow
                if workflow_instance_id == matching_workflow.workflow_instance_id
                else None
            ),
            list_by_workspace_id=lambda workspace_uuid, limit: (
                (matching_workflow,) if workspace_uuid == workspace_id else ()
            ),
            list_by_ticket_id=lambda ticket_id, limit: (
                (other_workspace_workflow, matching_workflow)
                if ticket_id == "LOOKUP-1"
                else ()
            ),
        )

    repo = UnitOfWorkWorkflowLookupRepository(lambda: LookupUow())

    assert repo.workflow_ids_by_workspace_id(str(workspace_id), limit=5) == (
        matching_workflow.workflow_instance_id,
    )
    assert repo.workflow_ids_by_ticket_id("LOOKUP-1", limit=5) == (
        other_workspace_workflow.workflow_instance_id,
        matching_workflow.workflow_instance_id,
    )


def test_unit_of_work_repositories_raise_when_memory_backing_is_missing() -> None:
    class MissingEpisodeAttrUow:
        memory_items = None
        memory_embeddings = None

        def __enter__(self) -> "MissingEpisodeAttrUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

    class MissingItemAttrUow:
        memory_episodes = None
        memory_embeddings = None

        def __enter__(self) -> "MissingItemAttrUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

    class MissingEmbeddingAttrUow:
        memory_episodes = None
        memory_items = None

        def __enter__(self) -> "MissingEmbeddingAttrUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

    class NoneBackedUow:
        memory_episodes = None
        memory_items = None
        memory_embeddings = None

        def __enter__(self) -> "NoneBackedUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

    workflow_id = uuid4()
    episode_record = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary",
    )
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        content="Memory item",
    )
    embedding_record = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_item.memory_id,
        embedding_model="test-model",
    )

    episode_repo = UnitOfWorkEpisodeRepository(lambda: MissingEpisodeAttrUow())
    item_repo = UnitOfWorkMemoryItemRepository(lambda: MissingItemAttrUow())
    embedding_repo = UnitOfWorkMemoryEmbeddingRepository(
        lambda: MissingEmbeddingAttrUow()
    )

    with pytest.raises(MemoryServiceError) as episode_create_error:
        episode_repo.create(episode_record)
    assert episode_create_error.value.feature is MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as episode_list_error:
        episode_repo.list_by_workflow_id(workflow_id, limit=5)
    assert episode_list_error.value.feature is MemoryFeature.GET_CONTEXT

    with pytest.raises(MemoryServiceError) as item_create_error:
        item_repo.create(memory_item)
    assert item_create_error.value.feature is MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as item_workspace_error:
        item_repo.list_by_workspace_id(uuid4(), limit=5)
    assert item_workspace_error.value.feature is MemoryFeature.SEARCH

    with pytest.raises(MemoryServiceError) as item_episode_error:
        item_repo.list_by_episode_id(uuid4(), limit=5)
    assert item_episode_error.value.feature is MemoryFeature.GET_CONTEXT

    with pytest.raises(MemoryServiceError) as embedding_create_error:
        embedding_repo.create(embedding_record)
    assert embedding_create_error.value.feature is MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as embedding_list_error:
        embedding_repo.list_by_memory_id(memory_item.memory_id, limit=5)
    assert embedding_list_error.value.feature is MemoryFeature.SEARCH

    with pytest.raises(MemoryServiceError) as embedding_search_error:
        embedding_repo.find_similar((1.0, 2.0), limit=5)
    assert embedding_search_error.value.feature is MemoryFeature.SEARCH

    none_episode_repo = UnitOfWorkEpisodeRepository(lambda: NoneBackedUow())
    none_item_repo = UnitOfWorkMemoryItemRepository(lambda: NoneBackedUow())
    none_embedding_repo = UnitOfWorkMemoryEmbeddingRepository(lambda: NoneBackedUow())

    with pytest.raises(
        AttributeError, match="'NoneType' object has no attribute 'create'"
    ):
        none_episode_repo.create(episode_record)

    with pytest.raises(
        AttributeError, match="'NoneType' object has no attribute 'list_by_workflow_id'"
    ):
        none_episode_repo.list_by_workflow_id(workflow_id, limit=5)

    with pytest.raises(MemoryServiceError) as none_item_create_error:
        none_item_repo.create(memory_item)
    assert none_item_create_error.value.feature is MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as none_item_workspace_error:
        none_item_repo.list_by_workspace_id(uuid4(), limit=5)
    assert none_item_workspace_error.value.feature is MemoryFeature.SEARCH

    with pytest.raises(MemoryServiceError) as none_item_episode_error:
        none_item_repo.list_by_episode_id(uuid4(), limit=5)
    assert none_item_episode_error.value.feature is MemoryFeature.GET_CONTEXT

    with pytest.raises(MemoryServiceError) as none_embedding_create_error:
        none_embedding_repo.create(embedding_record)
    assert none_embedding_create_error.value.feature is MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as none_embedding_list_error:
        none_embedding_repo.list_by_memory_id(memory_item.memory_id, limit=5)
    assert none_embedding_list_error.value.feature is MemoryFeature.SEARCH

    with pytest.raises(MemoryServiceError) as none_embedding_search_error:
        none_embedding_repo.find_similar((1.0, 2.0), limit=5)
    assert none_embedding_search_error.value.feature is MemoryFeature.SEARCH


def test_unit_of_work_workspace_lookup_returns_none_for_missing_workflow() -> None:
    class LookupUow:
        workflow_instances = SimpleNamespace(get_by_id=lambda workflow_id: None)

        def __enter__(self) -> "LookupUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    repo = UnitOfWorkWorkspaceLookupRepository(lambda: LookupUow())

    assert repo.workspace_id_by_workflow_id(uuid4()) is None
