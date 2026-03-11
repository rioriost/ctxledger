from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
from ctxledger.workflow.service import (
    ActiveWorkflowExistsError,
    AttemptNotFoundError,
    CompleteWorkflowInput,
    CreateCheckpointInput,
    InvalidStateTransitionError,
    ProjectionArtifactType,
    ProjectionFailureInfo,
    ProjectionInfo,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowAttemptMismatchError,
    WorkflowAttemptStatus,
    WorkflowCompleteResult,
    WorkflowInstanceStatus,
    WorkflowNotFoundError,
    WorkflowResume,
    WorkflowService,
    Workspace,
    WorkspaceNotFoundError,
    WorkspaceRegistrationConflictError,
)


def make_service_and_uow() -> tuple[WorkflowService, object]:
    store = InMemoryStore.create()
    uow_factory = build_in_memory_uow_factory(store)
    service = WorkflowService(uow_factory)
    return service, store


def register_workspace(service: WorkflowService) -> Workspace:
    return service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
        )
    )


def test_register_workspace_creates_workspace() -> None:
    service, uow = make_service_and_uow()

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
            metadata={"language": "python"},
        )
    )

    assert workspace.workspace_id in uow.workspaces_by_id
    assert workspace.repo_url == "https://example.com/org/repo.git"
    assert workspace.canonical_path == "/tmp/repo"
    assert workspace.default_branch == "main"
    assert workspace.metadata == {"language": "python"}


def test_register_workspace_rejects_canonical_path_conflict_without_workspace_id() -> (
    None
):
    service, _ = make_service_and_uow()
    register_workspace(service)

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/other.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "canonical_path" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


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


def test_resume_workflow_returns_resumable_with_projection_warning() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-789",
        )
    )
    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            summary="Checkpoint stored",
            checkpoint_json={"next_intended_action": "Resume implementation"},
        )
    )

    uow.projection_states_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        )
    ] = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.STALE,
        target_path=".agent/resume.json",
        open_failure_count=0,
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert isinstance(resume, WorkflowResume)
    assert resume.workspace.workspace_id == workspace.workspace_id
    assert (
        resume.workflow_instance.workflow_instance_id
        == started.workflow_instance.workflow_instance_id
    )
    assert resume.attempt is not None
    assert resume.attempt.attempt_id == started.attempt.attempt_id
    assert resume.latest_checkpoint is not None
    assert (
        resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.STALE
    assert any(warning.code == "stale_projection" for warning in resume.warnings)
    stale_warning = next(
        warning for warning in resume.warnings if warning.code == "stale_projection"
    )
    assert stale_warning.details["projection_type"] == "resume_json"
    assert resume.next_hint == "Resume implementation"


def test_record_resume_projection_persists_projection_state() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-PROJECTION",
        )
    )

    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert recorded.projection_type == ProjectionArtifactType.RESUME_JSON
    assert recorded.status == ProjectionStatus.FRESH
    assert recorded.target_path == ".agent/resume.json"
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"


def test_record_resume_projection_rejects_empty_target_path() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-PROJECTION-EMPTY",
        )
    )

    try:
        service.record_resume_projection(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path="   ",
            )
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "validation_error"
    else:
        raise AssertionError("Expected validation_error for empty target_path")


def test_record_resume_projection_rejects_workflow_from_another_workspace() -> None:
    service, _ = make_service_and_uow()
    first_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="TICKET-PROJECTION-MISMATCH",
        )
    )

    try:
        service.record_resume_projection(
            RecordProjectionStateInput(
                workspace_id=second_workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.STALE,
                target_path=".agent/resume.json",
            )
        )
    except WorkflowAttemptMismatchError as exc:
        assert exc.code == "workflow_attempt_mismatch"
    else:
        raise AssertionError("Expected WorkflowAttemptMismatchError")


def test_resume_workflow_returns_blocked_when_running_attempt_has_no_checkpoint() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-NO-CHECKPOINT",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.BLOCKED
    assert resume.latest_checkpoint is None
    assert any(
        warning.code == "running_attempt_without_checkpoint"
        for warning in resume.warnings
    )
    assert (
        resume.next_hint == "Create an initial checkpoint to establish resumable state."
    )


def test_resume_workflow_returns_terminal_for_completed_workflow() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-DONE",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="done_step",
            checkpoint_json={"next_intended_action": "Nothing"},
        )
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.TERMINAL
    assert (
        resume.next_hint
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )


def test_resume_workflow_raises_for_unknown_workflow() -> None:
    service, _ = make_service_and_uow()

    try:
        service.resume_workflow(ResumeWorkflowInput(workflow_instance_id=uuid4()))
    except WorkflowNotFoundError as exc:
        assert exc.code == "workflow_not_found"
    else:
        raise AssertionError("Expected WorkflowNotFoundError")


def test_start_workflow_raises_for_unknown_workspace() -> None:
    service, _ = make_service_and_uow()

    try:
        service.start_workflow(
            StartWorkflowInput(workspace_id=uuid4(), ticket_id="MISSING")
        )
    except WorkspaceNotFoundError as exc:
        assert exc.code == "workspace_not_found"
    else:
        raise AssertionError("Expected WorkspaceNotFoundError")


def test_create_checkpoint_raises_for_unknown_attempt() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="KNOWN")
    )

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=uuid4(),
                step_name="missing_attempt",
            )
        )
    except AttemptNotFoundError as exc:
        assert exc.code == "attempt_not_found"
    else:
        raise AssertionError("Expected AttemptNotFoundError")
