from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.workflow.service import (
    AttemptNotFoundError,
    CompleteWorkflowInput,
    CreateCheckpointInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    ValidationError,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowInstanceStatus,
    WorkflowNotFoundError,
    WorkspaceNotFoundError,
)

from .conftest import make_service_and_uow, register_workspace


def test_resume_workflow_returns_blocked_when_running_attempt_has_no_checkpoint() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-RESUME-2",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
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


def test_resume_workflow_terminal_result_is_for_inspection_not_continuation() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INSPECT-ONLY",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="finalize",
            checkpoint_json={"next_intended_action": "No further execution"},
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
    assert resume.attempt is not None
    assert resume.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert resume.latest_checkpoint is not None
    assert resume.latest_checkpoint.step_name == "finalize"
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


def test_resume_workflow_rejects_workspace_id_misuse() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    try:
        service.resume_workflow(
            ResumeWorkflowInput(workflow_instance_id=workspace.workspace_id)
        )
    except ValidationError as exc:
        assert exc.code == "validation_error"
        assert (
            str(exc)
            == "provided workflow_instance_id appears to be a workspace_id; use "
            "workspace://{workspace_id}/resume or provide a real "
            "workflow_instance_id"
        )
        assert exc.details == {
            "workflow_instance_id": str(workspace.workspace_id),
            "workspace_id": str(workspace.workspace_id),
        }
    else:
        raise AssertionError("Expected ValidationError")


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


def test_resume_workflow_returns_inconsistent_without_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NO-ATTEMPT",
        )
    )

    uow.attempts_by_id.pop(started.attempt.attempt_id, None)

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.attempt is None
    assert resume.resumable_status == ResumableStatus.INCONSISTENT
    assert any(
        warning.code == "running_workflow_without_attempt"
        for warning in resume.warnings
    )
    assert (
        resume.next_hint
        == "No attempt is available. Inspect workflow consistency before continuing."
    )


def test_resume_workflow_returns_blocked_for_non_running_latest_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="STOPPED-ATTEMPT",
        )
    )

    stopped_attempt = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=WorkflowAttemptStatus.FAILED,
        failure_reason="stopped",
        verify_status=started.attempt.verify_status,
        started_at=started.attempt.started_at,
        finished_at=datetime(2024, 1, 1, tzinfo=UTC),
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[stopped_attempt.attempt_id] = stopped_attempt

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.attempt is not None
    assert resume.attempt.status == WorkflowAttemptStatus.FAILED
    assert resume.resumable_status == ResumableStatus.BLOCKED


def test_resume_workflow_adds_missing_verify_report_warning() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="VERIFY-WARNING",
        )
    )

    attempt_with_verify = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=started.attempt.status,
        failure_reason=started.attempt.failure_reason,
        verify_status=VerifyStatus.PASSED,
        started_at=started.attempt.started_at,
        finished_at=started.attempt.finished_at,
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[attempt_with_verify.attempt_id] = attempt_with_verify

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    missing_verify_warning = next(
        warning
        for warning in resume.warnings
        if warning.code == "missing_verify_report"
    )
    assert missing_verify_warning.details == {
        "attempt_id": str(started.attempt.attempt_id)
    }


def test_derive_next_hint_uses_summary_when_next_action_missing() -> None:
    service, _ = make_service_and_uow()

    hint = service._derive_next_hint(
        object(),
        object(),
        type(
            "CheckpointStub",
            (),
            {
                "step_name": "implement_feature",
                "summary": "Continue implementation",
                "checkpoint_json": {},
            },
        )(),
        ResumableStatus.RESUMABLE,
    )

    assert (
        hint
        == "Resume from step 'implement_feature' using the latest checkpoint summary."
    )


def test_derive_next_hint_uses_step_name_when_summary_missing() -> None:
    service, _ = make_service_and_uow()

    hint = service._derive_next_hint(
        object(),
        object(),
        type(
            "CheckpointStub",
            (),
            {
                "step_name": "implement_feature",
                "summary": None,
                "checkpoint_json": {},
            },
        )(),
        ResumableStatus.RESUMABLE,
    )

    assert hint == "Resume from step 'implement_feature'."


def test_resume_workflow_debug_logging_path_executes_without_changing_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME",
        )
    )
    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume",
            summary="Checkpoint for debug logging coverage",
            checkpoint_json={"next_intended_action": "Resume with debug enabled"},
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.workspace.workspace_id == workspace.workspace_id
    assert resume.attempt is not None
    assert resume.latest_checkpoint is not None
    assert (
        resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert len(debug_messages) >= 6
    assert debug_messages[0][0] == "resume_workflow started"
    assert any(message == "resume_workflow complete" for message, _ in debug_messages)


def test_resume_workflow_debug_logging_includes_stage_duration_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-DURATIONS",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_durations",
            summary="Checkpoint for duration metadata coverage",
            checkpoint_json={"next_intended_action": "Inspect duration metadata"},
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    expected_messages = {
        "resume_workflow workflow lookup complete",
        "resume_workflow workspace lookup complete",
        "resume_workflow attempt lookup complete",
        "resume_workflow checkpoint lookup complete",
        "resume_workflow verify report lookup complete",
        "resume_workflow response assembly complete",
        "resume_workflow complete",
    }

    seen_messages = {message for message, _ in debug_messages}
    assert expected_messages.issubset(seen_messages)

    for message, extra in debug_messages:
        if message not in expected_messages:
            continue
        assert isinstance(extra, dict)
        assert "duration_ms" in extra
        assert isinstance(extra["duration_ms"], int)
        assert extra["duration_ms"] >= 0


def test_resume_workflow_complete_debug_logging_includes_response_assembly_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-ASSEMBLY-METADATA",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_response_assembly_metadata",
            summary="Checkpoint for response assembly metadata coverage",
            checkpoint_json={
                "next_intended_action": "Inspect response assembly metadata"
            },
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    response_assembly_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow response assembly complete"
    ]

    assert len(response_assembly_extras) == 1
    extra = response_assembly_extras[0]
    assert isinstance(extra, dict)
    assert extra["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert extra["workspace_id"] == str(workspace.workspace_id)
    assert extra["attempt_id"] == str(started.attempt.attempt_id)
    assert extra["warning_count"] == 0
    assert extra["resumable_status"] == "resumable"
    assert "duration_ms" in extra
    assert isinstance(extra["duration_ms"], int)
    assert extra["duration_ms"] >= 0


def test_resume_workflow_debug_logging_includes_attempt_lookup_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-ATTEMPT-STRATEGY",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_attempt_strategy",
            summary="Checkpoint for attempt lookup strategy coverage",
            checkpoint_json={"next_intended_action": "Inspect attempt lookup strategy"},
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    attempt_lookup_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow attempt lookup complete"
    ]

    assert len(attempt_lookup_extras) == 1
    extra = attempt_lookup_extras[0]
    assert isinstance(extra, dict)
    assert extra["attempt_lookup_strategy"] == "running"
    assert extra["attempt_id"] == str(started.attempt.attempt_id)
