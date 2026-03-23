from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.workflow.service import (
    ActiveWorkflowExistsError,
    CompleteWorkflowInput,
    CreateCheckpointInput,
    FailureListEntry,
    InvalidStateTransitionError,
    MemoryStats,
    PersistenceError,
    RegisterWorkspaceInput,
    ResumableStatus,
    StartWorkflowInput,
    ValidationError,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptMismatchError,
    WorkflowAttemptStatus,
    WorkflowCompleteResult,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowListEntry,
    WorkflowService,
    WorkflowStats,
    _status_count_dict,
)

from .conftest import make_service_and_uow, register_workspace


def test_start_workflow_creates_running_workflow_and_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)

    result = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-123",
            metadata={"priority": "high"},
        )
    )

    assert result.workflow_instance.workspace_id == workspace.workspace_id
    assert result.workflow_instance.ticket_id == "TICKET-123"
    assert result.workflow_instance.status == WorkflowInstanceStatus.RUNNING

    assert result.attempt.workflow_instance_id == result.workflow_instance.workflow_instance_id
    assert result.attempt.attempt_number == 1
    assert result.attempt.status == WorkflowAttemptStatus.RUNNING

    assert result.workflow_instance.workflow_instance_id in uow.workflows_by_id
    assert result.attempt.attempt_id in uow.attempts_by_id


def test_start_workflow_rejects_second_running_workflow_in_same_workspace() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-1",
        )
    )

    try:
        service.start_workflow(
            StartWorkflowInput(
                workspace_id=workspace.workspace_id,
                ticket_id="TICKET-2",
            )
        )
    except ActiveWorkflowExistsError as exc:
        assert exc.code == "active_workflow_exists"
    else:
        raise AssertionError("Expected ActiveWorkflowExistsError")


def test_create_checkpoint_persists_snapshot_and_verify_report() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-123",
        )
    )

    result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="edit_files",
            summary="Updated workflow docs",
            checkpoint_json={
                "current_objective": "Expand architecture and workflow docs",
                "next_intended_action": "Implement repositories",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["lint"], "status": "passed"},
        )
    )

    assert result.checkpoint.step_name == "edit_files"
    assert result.checkpoint.summary == "Updated workflow docs"
    assert result.checkpoint.checkpoint_json["next_intended_action"] == "Implement repositories"

    assert result.verify_report is not None
    assert result.verify_report.status == VerifyStatus.PASSED
    assert result.attempt.verify_status == VerifyStatus.PASSED

    stored_attempt = uow.attempts_by_id.get(started.attempt.attempt_id)
    assert stored_attempt is not None
    assert stored_attempt.verify_status == VerifyStatus.PASSED


def test_create_checkpoint_rejects_attempt_from_another_workflow() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    first = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="A")
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=first.workflow_instance.workflow_instance_id,
            attempt_id=first.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    second = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="B")
    )

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=second.workflow_instance.workflow_instance_id,
                attempt_id=first.attempt.attempt_id,
                step_name="bad_linkage",
            )
        )
    except WorkflowAttemptMismatchError as exc:
        assert exc.code == "workflow_attempt_mismatch"
    else:
        raise AssertionError("Expected WorkflowAttemptMismatchError")


def test_complete_workflow_moves_workflow_and_attempt_to_terminal_states() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-456",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["tests"], "status": "passed"},
        )
    )

    assert isinstance(result, WorkflowCompleteResult)
    assert result.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert result.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert result.attempt.finished_at is not None
    assert result.verify_report is not None
    assert result.verify_report.status == VerifyStatus.PASSED


def test_complete_workflow_rejects_terminal_workflow_recompletion() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="T-1")
    )

    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.CANCELLED,
        )
    )

    try:
        service.complete_workflow(
            CompleteWorkflowInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                workflow_status=WorkflowInstanceStatus.COMPLETED,
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_create_checkpoint_rejects_terminal_workflow() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="DONE")
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="after_terminal",
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
        assert "terminal workflow" in str(exc)
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_create_checkpoint_rejects_terminal_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="MANUAL")
    )

    terminal_attempt = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=WorkflowAttemptStatus.FAILED,
        failure_reason="manual override",
        verify_status=started.attempt.verify_status,
        started_at=started.attempt.started_at,
        finished_at=datetime(2024, 1, 1, tzinfo=UTC),
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[terminal_attempt.attempt_id] = terminal_attempt

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="after_failed_attempt",
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
        assert "terminal attempt" in str(exc)
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_completed_workflow_requires_new_workflow_for_additional_work() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    first = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="CLOSED-1")
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=first.workflow_instance.workflow_instance_id,
            attempt_id=first.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    second = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="CLOSED-2")
    )

    assert (
        second.workflow_instance.workflow_instance_id
        != first.workflow_instance.workflow_instance_id
    )
    assert second.workflow_instance.status == WorkflowInstanceStatus.RUNNING
    assert second.attempt.status == WorkflowAttemptStatus.RUNNING
    assert second.attempt.attempt_number == 1


def test_complete_workflow_without_verify_status_preserves_attempt_verify_status() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="KEEP-VERIFY")
    )

    attempt_with_verify = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=started.attempt.status,
        failure_reason=started.attempt.failure_reason,
        verify_status=VerifyStatus.SKIPPED,
        started_at=started.attempt.started_at,
        finished_at=started.attempt.finished_at,
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[attempt_with_verify.attempt_id] = attempt_with_verify

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.FAILED,
            failure_reason="tests failed",
        )
    )

    assert result.attempt.verify_status == VerifyStatus.SKIPPED
    assert result.attempt.failure_reason == "tests failed"
    assert result.verify_report is None


def test_derive_next_hint_covers_inconsistent_and_blocked_without_checkpoint() -> None:
    service, _ = make_service_and_uow()

    workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="HINT-1",
        status=WorkflowInstanceStatus.RUNNING,
    )
    running_attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    inconsistent_hint = service._derive_next_hint(
        workflow,
        None,
        None,
        ResumableStatus.INCONSISTENT,
    )
    blocked_without_checkpoint_hint = service._derive_next_hint(
        workflow,
        running_attempt,
        None,
        ResumableStatus.BLOCKED,
    )

    assert (
        inconsistent_hint
        == "No attempt is available. Inspect workflow consistency before continuing."
    )
    assert (
        blocked_without_checkpoint_hint
        == "Create an initial checkpoint to establish resumable state."
    )


def test_status_count_dict_and_grouped_status_zero_fill_behavior() -> None:
    counts = _status_count_dict(
        ("running", "completed", "failed"),
        {"running": 2, "failed": 1, "ignored": 99},
    )

    assert counts == {
        "running": 2,
        "completed": 0,
        "failed": 1,
    }


def test_count_helpers_support_in_memory_repositories_and_missing_methods() -> None:
    service, _ = make_service_and_uow()

    class CountRepo:
        def count_all(self) -> int:
            return 7

    class CountByStatusRepo:
        def count_by_status(self) -> dict[str, int]:
            return {"running": 3, "completed": 2}

    class MaxDatetimeRepo:
        def max_datetime(self, field_name: str):  # noqa: ANN001
            assert field_name == "updated_at"
            return datetime(2024, 1, 8, tzinfo=UTC)

    class OpenFailureRepo:
        def count_open_failures(self) -> int:
            return 4

    uow = SimpleNamespace(
        rows=CountRepo(),
        grouped=CountByStatusRepo(),
        latest=MaxDatetimeRepo(),
        failures=OpenFailureRepo(),
        memory_items=SimpleNamespace(),
    )

    assert service._count_rows(uow, "rows") == 7

    with pytest.raises(
        PersistenceError,
        match="stats counting is not supported for repository 'memory_items'",
    ):
        service._count_rows(uow, "memory_items")

    assert service._count_grouped_statuses(
        uow,
        repository_name="grouped",
        allowed_statuses=("running", "completed", "failed"),
    ) == {
        "running": 3,
        "completed": 2,
        "failed": 0,
    }

    with pytest.raises(
        PersistenceError,
        match="stats status aggregation is not supported for repository 'rows'",
    ):
        service._count_grouped_statuses(
            uow,
            repository_name="rows",
            allowed_statuses=("running",),
        )

    assert service._max_datetime_field(
        uow,
        repository_name="latest",
        field_name="updated_at",
    ) == datetime(2024, 1, 8, tzinfo=UTC)

    with pytest.raises(
        PersistenceError,
        match="stats datetime aggregation is not supported for repository 'rows'",
    ):
        service._max_datetime_field(
            uow,
            repository_name="rows",
            field_name="updated_at",
        )

    assert uow.failures.count_open_failures() == 4
    assert not hasattr(service, "_count_open_projection_failures")


def test_count_memory_item_provenance_uses_repository_when_available() -> None:
    service, _ = make_service_and_uow()

    class ProvenanceRepo:
        def count_by_provenance(self) -> dict[str, int]:
            return {"episode_summary": 5, "workflow_completion": 1}

    counts = service._count_memory_item_provenance(SimpleNamespace(memory_items=ProvenanceRepo()))

    assert counts == {
        "episode_summary": 5,
        "workflow_completion": 1,
    }


def test_count_memory_item_provenance_raises_without_repository_support() -> None:
    service, _ = make_service_and_uow()

    with pytest.raises(
        PersistenceError,
        match="memory stats provenance aggregation is not supported for memory items",
    ):
        service._count_memory_item_provenance(SimpleNamespace(memory_items=SimpleNamespace()))


def test_get_stats_collects_counts_and_latest_timestamps() -> None:
    service, _ = make_service_and_uow()

    expected_time = datetime(2024, 2, 1, tzinfo=UTC)

    class FakeUow:
        def __enter__(self) -> "FakeUow":
            self.workspaces = SimpleNamespace(
                count_all=lambda: 2, max_datetime=lambda field: expected_time
            )
            self.workflow_instances = SimpleNamespace(
                count_all=lambda: 4,
                count_by_status=lambda: {"running": 1, "completed": 2},
                max_datetime=lambda field: expected_time,
            )
            self.workflow_attempts = SimpleNamespace(
                count_all=lambda: 5,
                count_by_status=lambda: {"running": 1, "succeeded": 3, "failed": 1},
            )
            self.workflow_checkpoints = SimpleNamespace(
                count_all=lambda: 6,
                max_datetime=lambda field: expected_time,
            )
            self.verify_reports = SimpleNamespace(
                count_all=lambda: 3,
                count_by_status=lambda: {"passed": 2, "failed": 1},
                max_datetime=lambda field: expected_time,
            )
            self.memory_episodes = SimpleNamespace(
                count_all=lambda: 7, max_datetime=lambda field: expected_time
            )
            self.memory_items = SimpleNamespace(
                count_all=lambda: 8, max_datetime=lambda field: expected_time
            )
            self.memory_embeddings = SimpleNamespace(
                count_all=lambda: 9, max_datetime=lambda field: expected_time
            )
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    service._uow_factory = lambda: FakeUow()  # type: ignore[assignment]

    stats = service.get_stats()

    assert stats == WorkflowStats(
        workspace_count=2,
        workflow_status_counts={
            "running": 1,
            "completed": 2,
            "failed": 0,
            "cancelled": 0,
        },
        attempt_status_counts={
            "running": 1,
            "succeeded": 3,
            "failed": 1,
            "cancelled": 0,
        },
        verify_status_counts={
            "passed": 2,
            "failed": 1,
            "pending": 0,
            "skipped": 0,
        },
        checkpoint_count=6,
        episode_count=7,
        memory_item_count=8,
        memory_embedding_count=9,
        latest_workflow_updated_at=expected_time,
        latest_checkpoint_created_at=expected_time,
        latest_verify_report_created_at=expected_time,
        latest_episode_created_at=expected_time,
        latest_memory_item_created_at=expected_time,
        latest_memory_embedding_created_at=expected_time,
    )


def test_get_memory_stats_collects_relation_and_provenance_information() -> None:
    service, _ = make_service_and_uow()

    expected_time = datetime(2024, 3, 1, tzinfo=UTC)

    class FakeUow:
        def __enter__(self) -> "FakeUow":
            self.memory_episodes = SimpleNamespace(
                count_all=lambda: 2, max_datetime=lambda field: expected_time
            )
            self.memory_items = SimpleNamespace(
                count_all=lambda: 4,
                max_datetime=lambda field: expected_time,
                count_by_provenance=lambda: {"episode_summary": 3, "workflow_completion": 1},
            )
            self.memory_embeddings = SimpleNamespace(
                count_all=lambda: 5, max_datetime=lambda field: expected_time
            )
            self.memory_relations = SimpleNamespace(
                count_all=lambda: 6, max_datetime=lambda field: expected_time
            )
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    service._uow_factory = lambda: FakeUow()  # type: ignore[assignment]

    stats = service.get_memory_stats()

    assert stats == MemoryStats(
        episode_count=2,
        memory_item_count=4,
        memory_embedding_count=5,
        memory_relation_count=6,
        memory_item_provenance_counts={
            "episode_summary": 3,
            "workflow_completion": 1,
        },
        latest_episode_created_at=expected_time,
        latest_memory_item_created_at=expected_time,
        latest_memory_embedding_created_at=expected_time,
        latest_memory_relation_created_at=expected_time,
    )


def test_list_workflows_validates_inputs_and_maps_related_state() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="LIST-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="inspect",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["tests"], "status": "passed"},
        )
    )

    entries = service.list_workflows(
        limit=5,
        status=" running ",
        workspace_id=workspace.workspace_id,
        ticket_id=" LIST-1 ",
    )

    assert entries == (
        WorkflowListEntry(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            workspace_id=workspace.workspace_id,
            canonical_path=workspace.canonical_path,
            ticket_id="LIST-1",
            workflow_status=WorkflowInstanceStatus.RUNNING.value,
            latest_step_name="inspect",
            latest_verify_status=VerifyStatus.PASSED.value,
            updated_at=started.workflow_instance.updated_at,
        ),
    )

    with pytest.raises(ValidationError, match="limit must be greater than zero"):
        service.list_workflows(limit=0)

    with pytest.raises(
        ValidationError,
        match="status must be one of running, completed, failed, or cancelled",
    ):
        service.list_workflows(status="unknown")


def test_list_workflows_falls_back_to_attempt_verify_status_without_verify_report() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="LIST-VERIFY-FALLBACK",
        )
    )

    updated_attempt = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=started.attempt.status,
        failure_reason=started.attempt.failure_reason,
        verify_status=VerifyStatus.SKIPPED,
        started_at=started.attempt.started_at,
        finished_at=started.attempt.finished_at,
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    uow.attempts_by_id[updated_attempt.attempt_id] = updated_attempt

    entries = service.list_workflows(limit=5)

    assert len(entries) == 1
    assert entries[0].latest_verify_status == VerifyStatus.SKIPPED.value


def test_list_failures_currently_returns_empty_tuple() -> None:
    service, _ = make_service_and_uow()

    assert service.list_failures() == ()


def test_complete_workflow_returns_default_auto_memory_details_when_bridge_returns_none() -> None:
    class NoneReturningBridge:
        embedding_generator = None

        def record_workflow_completion_memory(self, **kwargs: object) -> None:
            return None

    service, _ = make_service_and_uow(
        workflow_memory_bridge=NoneReturningBridge()  # type: ignore[arg-type]
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-NONE",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "no_completion_summary_source",
    }
    assert result.warnings == ()


def test_complete_workflow_adds_embedding_warning_when_auto_memory_embedding_fails() -> None:
    class EmbeddingFailureBridge:
        embedding_generator = None

        def record_workflow_completion_memory(self, **kwargs: object):
            return SimpleNamespace(
                details={
                    "auto_memory_recorded": True,
                    "embedding_persistence_status": "failed",
                    "embedding_generation_skipped_reason": "embedding_generation_failed:test",
                    "embedding_generation_failure": {
                        "provider": "test",
                        "message": "boom",
                    },
                }
            )

    service, _ = make_service_and_uow(
        workflow_memory_bridge=EmbeddingFailureBridge()  # type: ignore[arg-type]
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-EMBEDDING-FAIL",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "failed",
        "embedding_generation_skipped_reason": "embedding_generation_failed:test",
        "embedding_generation_failure": {
            "provider": "test",
            "message": "boom",
        },
    }
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "auto_memory_embedding_failed"
    assert result.warnings[0].details == {
        "embedding_generation_skipped_reason": "embedding_generation_failed:test",
        "embedding_generation_failure": {
            "provider": "test",
            "message": "boom",
        },
    }


def test_stats_helpers_cover_records_by_id_and_values_by_id_paths() -> None:
    service = WorkflowService(lambda: None)
    now = datetime(2024, 1, 10, tzinfo=UTC)

    records_repo = SimpleNamespace(
        _records_by_id={
            uuid4(): SimpleNamespace(
                status=WorkflowInstanceStatus.RUNNING,
                updated_at=now,
            ),
            uuid4(): SimpleNamespace(
                status=WorkflowInstanceStatus.COMPLETED,
                updated_at=now.replace(day=11),
            ),
        }
    )
    values_repo = SimpleNamespace(
        _values_by_id={
            uuid4(): SimpleNamespace(
                status=VerifyStatus.PASSED,
                created_at=now,
            ),
            uuid4(): SimpleNamespace(
                status=VerifyStatus.FAILED,
                created_at=now.replace(day=12),
            ),
        }
    )

    records_count = service._count_rows(
        SimpleNamespace(workflow_instances=records_repo),
        "workflow_instances",
    )
    values_count = service._count_rows(
        SimpleNamespace(verify_reports=values_repo),
        "verify_reports",
    )
    grouped_records = service._count_grouped_statuses(
        SimpleNamespace(workflow_instances=records_repo),
        repository_name="workflow_instances",
        allowed_statuses=(
            WorkflowInstanceStatus.RUNNING.value,
            WorkflowInstanceStatus.COMPLETED.value,
            WorkflowInstanceStatus.FAILED.value,
        ),
    )
    grouped_values = service._count_grouped_statuses(
        SimpleNamespace(verify_reports=values_repo),
        repository_name="verify_reports",
        allowed_statuses=(
            VerifyStatus.PASSED.value,
            VerifyStatus.FAILED.value,
            VerifyStatus.SKIPPED.value,
        ),
    )
    max_records = service._max_datetime_field(
        SimpleNamespace(workflow_instances=records_repo),
        repository_name="workflow_instances",
        field_name="updated_at",
    )
    max_values = service._max_datetime_field(
        SimpleNamespace(verify_reports=values_repo),
        repository_name="verify_reports",
        field_name="created_at",
    )

    assert records_count == 2
    assert values_count == 2
    assert grouped_records == {
        "running": 1,
        "completed": 1,
        "failed": 0,
    }
    assert grouped_values == {
        "passed": 1,
        "failed": 1,
        "skipped": 0,
    }
    assert max_records == now.replace(day=11)
    assert max_values == now.replace(day=12)


def test_validate_helpers_reject_empty_values() -> None:
    service, _ = make_service_and_uow()

    with pytest.raises(Exception, match="repo_url must not be empty"):
        service._validate_workspace_input(
            RegisterWorkspaceInput(
                repo_url="   ",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )

    with pytest.raises(Exception, match="canonical_path must not be empty"):
        service._validate_workspace_input(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/repo.git",
                canonical_path="   ",
                default_branch="main",
            )
        )

    with pytest.raises(Exception, match="default_branch must not be empty"):
        service._validate_workspace_input(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/repo.git",
                canonical_path="/tmp/repo",
                default_branch="   ",
            )
        )

    with pytest.raises(Exception, match="ticket_id must not be empty"):
        service._validate_ticket_id("   ")

    with pytest.raises(Exception, match="step_name must not be empty"):
        service._validate_step_name("   ")
