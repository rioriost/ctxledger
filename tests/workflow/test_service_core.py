from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.workflow.service import (
    ActiveWorkflowExistsError,
    CompleteWorkflowInput,
    CreateCheckpointInput,
    InvalidStateTransitionError,
    RegisterWorkspaceInput,
    ResumableStatus,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptMismatchError,
    WorkflowAttemptStatus,
    WorkflowCompleteResult,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowService,
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

    assert (
        result.attempt.workflow_instance_id
        == result.workflow_instance.workflow_instance_id
    )
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
    assert (
        result.checkpoint.checkpoint_json["next_intended_action"]
        == "Implement repositories"
    )

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


def test_complete_workflow_without_verify_status_preserves_attempt_verify_status() -> (
    None
):
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
    from ctxledger.workflow.service import _status_count_dict

    counts = _status_count_dict(
        ("running", "completed", "failed"),
        {"running": 2, "failed": 1, "ignored": 99},
    )

    assert counts == {
        "running": 2,
        "completed": 0,
        "failed": 1,
    }


def test_complete_workflow_returns_default_auto_memory_details_when_bridge_returns_none() -> (
    None
):
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


def test_complete_workflow_adds_embedding_warning_when_auto_memory_embedding_fails() -> (
    None
):
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
