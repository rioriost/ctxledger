from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

from ctxledger.workflow.service import (
    ActiveWorkflowExistsError,
    AttemptNotFoundError,
    CompleteWorkflowInput,
    CreateCheckpointInput,
    InvalidStateTransitionError,
    ProjectionInfo,
    ProjectionStateRepository,
    ProjectionStatus,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyReport,
    VerifyReportRepository,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptMismatchError,
    WorkflowAttemptRepository,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowCheckpointRepository,
    WorkflowCompleteResult,
    WorkflowError,
    WorkflowInstance,
    WorkflowInstanceRepository,
    WorkflowInstanceStatus,
    WorkflowNotFoundError,
    WorkflowResume,
    WorkflowService,
    Workspace,
    WorkspaceNotFoundError,
    WorkspaceRegistrationConflictError,
    WorkspaceRepository,
)


class InMemoryWorkspaceRepository(WorkspaceRepository):
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


class InMemoryWorkflowInstanceRepository(WorkflowInstanceRepository):
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
        return max(candidates, key=lambda item: item.created_at, default=None)

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self.items[workflow.workflow_instance_id] = workflow
        return workflow

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self.items[workflow.workflow_instance_id] = workflow
        return workflow


class InMemoryWorkflowAttemptRepository(WorkflowAttemptRepository):
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


class InMemoryWorkflowCheckpointRepository(WorkflowCheckpointRepository):
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


class InMemoryVerifyReportRepository(VerifyReportRepository):
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


class InMemoryProjectionStateRepository(ProjectionStateRepository):
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, UUID], ProjectionInfo] = {}

    def get_resume_projection(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> ProjectionInfo | None:
        return self.items.get((workspace_id, workflow_instance_id))


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.workspaces = InMemoryWorkspaceRepository()
        self.workflow_instances = InMemoryWorkflowInstanceRepository()
        self.workflow_attempts = InMemoryWorkflowAttemptRepository()
        self.workflow_checkpoints = InMemoryWorkflowCheckpointRepository()
        self.verify_reports = InMemoryVerifyReportRepository()
        self.projection_states = InMemoryProjectionStateRepository()
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> InMemoryUnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def make_service_and_uow() -> tuple[WorkflowService, InMemoryUnitOfWork]:
    uow = InMemoryUnitOfWork()
    service = WorkflowService(lambda: uow)
    return service, uow


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

    assert workspace.workspace_id in uow.workspaces.items
    assert workspace.repo_url == "https://example.com/org/repo.git"
    assert workspace.canonical_path == "/tmp/repo"
    assert workspace.default_branch == "main"
    assert workspace.metadata == {"language": "python"}
    assert uow.committed is True


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

    assert result.workflow_instance.workflow_instance_id in uow.workflow_instances.items
    assert result.attempt.attempt_id in uow.workflow_attempts.items


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

    stored_attempt = uow.workflow_attempts.get_by_id(started.attempt.attempt_id)
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

    uow.projection_states.items[
        (workspace.workspace_id, started.workflow_instance.workflow_instance_id)
    ] = ProjectionInfo(
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
    assert resume.projection is not None
    assert resume.projection.status == ProjectionStatus.STALE
    assert any(warning.code == "stale_projection" for warning in resume.warnings)
    assert resume.next_hint == "Resume implementation"


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
