from __future__ import annotations

from ctxledger.workflow.service import (
    ActiveWorkflowExistsError,
    AttemptNotFoundError,
    InvalidStateTransitionError,
    ValidationError,
    WorkflowAttemptMismatchError,
    WorkflowError,
    WorkflowNotFoundError,
    WorkspaceNotFoundError,
    WorkspaceRegistrationConflictError,
)


def test_workflow_error_hierarchy_exposes_expected_codes_and_details() -> None:
    validation_error = ValidationError(
        "validation failed",
        details={"field": "ticket_id"},
    )
    workspace_not_found = WorkspaceNotFoundError(
        "workspace not found",
        details={"workspace_id": "abc"},
    )
    workflow_not_found = WorkflowNotFoundError(
        "workflow not found",
        details={"workflow_instance_id": "wf-1"},
    )
    attempt_not_found = AttemptNotFoundError(
        "attempt not found",
        details={"attempt_id": "att-1"},
    )
    active_workflow_exists = ActiveWorkflowExistsError(
        "workspace already has a running workflow",
        details={"workspace_id": "ws-1"},
    )
    workspace_conflict = WorkspaceRegistrationConflictError(
        "repo_url belongs to another workspace",
        details={"repo_url": "https://example.com/repo.git"},
    )
    invalid_transition = InvalidStateTransitionError(
        "workflow is already terminal",
        details={"status": "completed"},
    )
    workflow_attempt_mismatch = WorkflowAttemptMismatchError(
        "attempt does not belong to workflow",
        details={"attempt_id": "att-2"},
    )

    assert isinstance(validation_error, WorkflowError)
    assert validation_error.code == "validation_error"
    assert validation_error.details == {"field": "ticket_id"}
    assert str(validation_error) == "validation failed"

    assert isinstance(workspace_not_found, WorkflowError)
    assert workspace_not_found.code == "workspace_not_found"
    assert workspace_not_found.details == {"workspace_id": "abc"}
    assert str(workspace_not_found) == "workspace not found"

    assert isinstance(workflow_not_found, WorkflowError)
    assert workflow_not_found.code == "workflow_not_found"
    assert workflow_not_found.details == {"workflow_instance_id": "wf-1"}
    assert str(workflow_not_found) == "workflow not found"

    assert isinstance(attempt_not_found, WorkflowError)
    assert attempt_not_found.code == "attempt_not_found"
    assert attempt_not_found.details == {"attempt_id": "att-1"}
    assert str(attempt_not_found) == "attempt not found"

    assert isinstance(active_workflow_exists, WorkflowError)
    assert active_workflow_exists.code == "active_workflow_exists"
    assert active_workflow_exists.details == {"workspace_id": "ws-1"}
    assert str(active_workflow_exists) == "workspace already has a running workflow"

    assert isinstance(workspace_conflict, WorkflowError)
    assert workspace_conflict.code == "workspace_registration_conflict"
    assert workspace_conflict.details == {"repo_url": "https://example.com/repo.git"}
    assert str(workspace_conflict) == "repo_url belongs to another workspace"

    assert isinstance(invalid_transition, WorkflowError)
    assert invalid_transition.code == "invalid_state_transition"
    assert invalid_transition.details == {"status": "completed"}
    assert str(invalid_transition) == "workflow is already terminal"

    assert isinstance(workflow_attempt_mismatch, WorkflowError)
    assert workflow_attempt_mismatch.code == "workflow_attempt_mismatch"
    assert workflow_attempt_mismatch.details == {"attempt_id": "att-2"}
    assert str(workflow_attempt_mismatch) == "attempt does not belong to workflow"


def test_workflow_error_defaults_details_to_empty_dict() -> None:
    error = WorkflowError("boom")

    assert error.code == "workflow_error"
    assert error.details == {}
    assert str(error) == "boom"


def test_workflow_error_preserves_explicit_empty_details_dict() -> None:
    error = WorkflowError("boom", details={})

    assert error.code == "workflow_error"
    assert error.details == {}
    assert str(error) == "boom"
