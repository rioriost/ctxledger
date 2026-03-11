from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkflowInstanceStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerifyStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResumableStatus(StrEnum):
    RESUMABLE = "resumable"
    TERMINAL = "terminal"
    BLOCKED = "blocked"
    INCONSISTENT = "inconsistent"


class ProjectionStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    FAILED = "failed"


class WorkflowError(Exception):
    code = "workflow_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ValidationError(WorkflowError):
    code = "validation_error"


class AuthenticationError(WorkflowError):
    code = "authentication_error"


class NotFoundError(WorkflowError):
    code = "not_found"


class WorkspaceNotFoundError(NotFoundError):
    code = "workspace_not_found"


class WorkflowNotFoundError(NotFoundError):
    code = "workflow_not_found"


class AttemptNotFoundError(NotFoundError):
    code = "attempt_not_found"


class ConflictError(WorkflowError):
    code = "conflict"


class ActiveWorkflowExistsError(ConflictError):
    code = "active_workflow_exists"


class WorkspaceRegistrationConflictError(ConflictError):
    code = "workspace_registration_conflict"


class InvalidStateTransitionError(ConflictError):
    code = "invalid_state_transition"


class WorkflowAttemptMismatchError(ConflictError):
    code = "workflow_attempt_mismatch"


class PersistenceError(WorkflowError):
    code = "persistence_error"


@dataclass(slots=True, frozen=True)
class Workspace:
    workspace_id: UUID
    repo_url: str
    canonical_path: str
    default_branch: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True, frozen=True)
class WorkflowInstance:
    workflow_instance_id: UUID
    workspace_id: UUID
    ticket_id: str
    status: WorkflowInstanceStatus
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            WorkflowInstanceStatus.COMPLETED,
            WorkflowInstanceStatus.FAILED,
            WorkflowInstanceStatus.CANCELLED,
        }


@dataclass(slots=True, frozen=True)
class WorkflowAttempt:
    attempt_id: UUID
    workflow_instance_id: UUID
    attempt_number: int
    status: WorkflowAttemptStatus
    failure_reason: str | None = None
    verify_status: VerifyStatus | None = None
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            WorkflowAttemptStatus.SUCCEEDED,
            WorkflowAttemptStatus.FAILED,
            WorkflowAttemptStatus.CANCELLED,
        }


@dataclass(slots=True, frozen=True)
class WorkflowCheckpoint:
    checkpoint_id: UUID
    workflow_instance_id: UUID
    attempt_id: UUID
    step_name: str
    summary: str | None = None
    checkpoint_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True, frozen=True)
class VerifyReport:
    verify_id: UUID
    attempt_id: UUID
    status: VerifyStatus
    report_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True, frozen=True)
class ProjectionInfo:
    status: ProjectionStatus
    target_path: str | None = None
    last_successful_write_at: datetime | None = None
    last_canonical_update_at: datetime | None = None
    open_failure_count: int = 0


@dataclass(slots=True, frozen=True)
class ProjectionFailureInfo:
    error_code: str | None
    error_message: str
    target_path: str
    open_failure_count: int = 1


@dataclass(slots=True, frozen=True)
class RecordProjectionStateInput:
    workspace_id: UUID
    workflow_instance_id: UUID
    status: ProjectionStatus
    target_path: str
    last_successful_write_at: datetime | None = None
    last_canonical_update_at: datetime | None = None

    def normalized(self) -> RecordProjectionStateInput:
        if self.status != ProjectionStatus.FRESH:
            return self

        write_at = self.last_successful_write_at or utc_now()
        canonical_update_at = self.last_canonical_update_at or write_at
        return RecordProjectionStateInput(
            workspace_id=self.workspace_id,
            workflow_instance_id=self.workflow_instance_id,
            status=self.status,
            target_path=self.target_path,
            last_successful_write_at=write_at,
            last_canonical_update_at=canonical_update_at,
        )


@dataclass(slots=True, frozen=True)
class RecordProjectionFailureInput:
    workspace_id: UUID
    workflow_instance_id: UUID
    target_path: str
    error_message: str
    error_code: str | None = None


@dataclass(slots=True, frozen=True)
class ResumeIssue:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class WorkflowResume:
    workspace: Workspace
    workflow_instance: WorkflowInstance
    attempt: WorkflowAttempt | None
    latest_checkpoint: WorkflowCheckpoint | None
    latest_verify_report: VerifyReport | None
    resumable_status: ResumableStatus
    projection: ProjectionInfo | None = None
    warnings: tuple[ResumeIssue, ...] = ()
    next_hint: str | None = None


@dataclass(slots=True, frozen=True)
class WorkflowStartResult:
    workflow_instance: WorkflowInstance
    attempt: WorkflowAttempt


@dataclass(slots=True, frozen=True)
class WorkflowCheckpointResult:
    checkpoint: WorkflowCheckpoint
    workflow_instance: WorkflowInstance
    attempt: WorkflowAttempt
    verify_report: VerifyReport | None = None


@dataclass(slots=True, frozen=True)
class WorkflowCompleteResult:
    workflow_instance: WorkflowInstance
    attempt: WorkflowAttempt
    verify_report: VerifyReport | None = None


@dataclass(slots=True, frozen=True)
class RegisterWorkspaceInput:
    repo_url: str
    canonical_path: str
    default_branch: str
    workspace_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class StartWorkflowInput:
    workspace_id: UUID
    ticket_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class CreateCheckpointInput:
    workflow_instance_id: UUID
    attempt_id: UUID
    step_name: str
    summary: str | None = None
    checkpoint_json: dict[str, Any] = field(default_factory=dict)
    verify_status: VerifyStatus | None = None
    verify_report: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class ResumeWorkflowInput:
    workflow_instance_id: UUID


@dataclass(slots=True, frozen=True)
class CompleteWorkflowInput:
    workflow_instance_id: UUID
    attempt_id: UUID
    workflow_status: WorkflowInstanceStatus
    summary: str | None = None
    verify_status: VerifyStatus | None = None
    verify_report: dict[str, Any] | None = None
    failure_reason: str | None = None


class WorkspaceRepository:
    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        raise NotImplementedError

    def get_by_canonical_path(self, canonical_path: str) -> Workspace | None:
        raise NotImplementedError

    def get_by_repo_url(self, repo_url: str) -> list[Workspace]:
        raise NotImplementedError

    def create(self, workspace: Workspace) -> Workspace:
        raise NotImplementedError

    def update(self, workspace: Workspace) -> Workspace:
        raise NotImplementedError


class WorkflowInstanceRepository:
    def get_by_id(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        raise NotImplementedError

    def get_running_by_workspace_id(
        self, workspace_id: UUID
    ) -> WorkflowInstance | None:
        raise NotImplementedError

    def get_latest_by_workspace_id(self, workspace_id: UUID) -> WorkflowInstance | None:
        raise NotImplementedError

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        raise NotImplementedError

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        raise NotImplementedError


class WorkflowAttemptRepository:
    def get_by_id(self, attempt_id: UUID) -> WorkflowAttempt | None:
        raise NotImplementedError

    def get_running_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowAttempt | None:
        raise NotImplementedError

    def get_latest_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowAttempt | None:
        raise NotImplementedError

    def get_next_attempt_number(self, workflow_instance_id: UUID) -> int:
        raise NotImplementedError

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        raise NotImplementedError

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        raise NotImplementedError


class WorkflowCheckpointRepository:
    def get_latest_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> WorkflowCheckpoint | None:
        raise NotImplementedError

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> WorkflowCheckpoint | None:
        raise NotImplementedError

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        raise NotImplementedError


class VerifyReportRepository:
    def get_latest_by_attempt_id(self, attempt_id: UUID) -> VerifyReport | None:
        raise NotImplementedError

    def create(self, verify_report: VerifyReport) -> VerifyReport:
        raise NotImplementedError


class ProjectionStateRepository:
    def get_resume_projection(
        self, workspace_id: UUID, workflow_instance_id: UUID
    ) -> ProjectionInfo | None:
        raise NotImplementedError

    def record_resume_projection(self, projection: RecordProjectionStateInput) -> None:
        raise NotImplementedError


class ProjectionFailureRepository:
    def get_open_failures_by_workflow_id(
        self, workspace_id: UUID, workflow_instance_id: UUID
    ) -> list[ProjectionFailureInfo]:
        raise NotImplementedError

    def record_resume_projection_failure(
        self, failure: RecordProjectionFailureInput
    ) -> ProjectionFailureInfo:
        raise NotImplementedError


class UnitOfWork:
    workspaces: WorkspaceRepository
    workflow_instances: WorkflowInstanceRepository
    workflow_attempts: WorkflowAttemptRepository
    workflow_checkpoints: WorkflowCheckpointRepository
    verify_reports: VerifyReportRepository
    projection_states: ProjectionStateRepository | None
    projection_failures: ProjectionFailureRepository | None

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class WorkflowService:
    def __init__(self, uow_factory: Any) -> None:
        self._uow_factory = uow_factory

    def register_workspace(self, data: RegisterWorkspaceInput) -> Workspace:
        self._validate_workspace_input(data)

        with self._uow_factory() as uow:
            existing_by_path = uow.workspaces.get_by_canonical_path(data.canonical_path)
            repo_matches = uow.workspaces.get_by_repo_url(data.repo_url)

            if data.workspace_id is None:
                if existing_by_path is not None:
                    raise WorkspaceRegistrationConflictError(
                        "canonical_path is already registered",
                        details={
                            "canonical_path": data.canonical_path,
                            "workspace_id": str(existing_by_path.workspace_id),
                        },
                    )
                if repo_matches:
                    raise WorkspaceRegistrationConflictError(
                        "repo_url is already registered and explicit workspace_id is required for updates",
                        details={"repo_url": data.repo_url},
                    )

                workspace = Workspace(
                    workspace_id=uuid4(),
                    repo_url=data.repo_url,
                    canonical_path=data.canonical_path,
                    default_branch=data.default_branch,
                    metadata=dict(data.metadata),
                )
                created = uow.workspaces.create(workspace)
                uow.commit()
                return created

            existing = uow.workspaces.get_by_id(data.workspace_id)
            if existing is None:
                raise WorkspaceNotFoundError(
                    "workspace not found",
                    details={"workspace_id": str(data.workspace_id)},
                )

            if (
                existing_by_path is not None
                and existing_by_path.workspace_id != existing.workspace_id
            ):
                raise WorkspaceRegistrationConflictError(
                    "canonical_path belongs to another workspace",
                    details={
                        "canonical_path": data.canonical_path,
                        "workspace_id": str(existing_by_path.workspace_id),
                    },
                )

            for repo_workspace in repo_matches:
                if repo_workspace.workspace_id != existing.workspace_id:
                    raise WorkspaceRegistrationConflictError(
                        "repo_url belongs to another workspace",
                        details={
                            "repo_url": data.repo_url,
                            "workspace_id": str(repo_workspace.workspace_id),
                        },
                    )

            updated = Workspace(
                workspace_id=existing.workspace_id,
                repo_url=data.repo_url,
                canonical_path=data.canonical_path,
                default_branch=data.default_branch,
                metadata=dict(data.metadata),
                created_at=existing.created_at,
                updated_at=utc_now(),
            )
            saved = uow.workspaces.update(updated)
            uow.commit()
            return saved

    def start_workflow(self, data: StartWorkflowInput) -> WorkflowStartResult:
        self._validate_ticket_id(data.ticket_id)

        with self._uow_factory() as uow:
            workspace = uow.workspaces.get_by_id(data.workspace_id)
            if workspace is None:
                raise WorkspaceNotFoundError(
                    "workspace not found",
                    details={"workspace_id": str(data.workspace_id)},
                )

            running = uow.workflow_instances.get_running_by_workspace_id(
                data.workspace_id
            )
            if running is not None:
                raise ActiveWorkflowExistsError(
                    "workspace already has a running workflow",
                    details={
                        "workspace_id": str(data.workspace_id),
                        "workflow_instance_id": str(running.workflow_instance_id),
                    },
                )

            workflow = WorkflowInstance(
                workflow_instance_id=uuid4(),
                workspace_id=data.workspace_id,
                ticket_id=data.ticket_id.strip(),
                status=WorkflowInstanceStatus.RUNNING,
                metadata=dict(data.metadata),
            )
            workflow = uow.workflow_instances.create(workflow)

            attempt = WorkflowAttempt(
                attempt_id=uuid4(),
                workflow_instance_id=workflow.workflow_instance_id,
                attempt_number=1,
                status=WorkflowAttemptStatus.RUNNING,
            )
            attempt = uow.workflow_attempts.create(attempt)
            uow.commit()
            return WorkflowStartResult(workflow_instance=workflow, attempt=attempt)

    def create_checkpoint(
        self, data: CreateCheckpointInput
    ) -> WorkflowCheckpointResult:
        self._validate_step_name(data.step_name)

        with self._uow_factory() as uow:
            workflow = self._require_workflow(uow, data.workflow_instance_id)
            attempt = self._require_attempt(uow, data.attempt_id)
            self._ensure_attempt_matches_workflow(workflow, attempt)

            if workflow.is_terminal:
                raise InvalidStateTransitionError(
                    "cannot create checkpoint for terminal workflow",
                    details={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "status": workflow.status.value,
                    },
                )

            if attempt.is_terminal:
                raise InvalidStateTransitionError(
                    "cannot create checkpoint for terminal attempt",
                    details={
                        "attempt_id": str(attempt.attempt_id),
                        "status": attempt.status.value,
                    },
                )

            checkpoint = WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=workflow.workflow_instance_id,
                attempt_id=attempt.attempt_id,
                step_name=data.step_name.strip(),
                summary=data.summary,
                checkpoint_json=dict(data.checkpoint_json),
            )
            checkpoint = uow.workflow_checkpoints.create(checkpoint)

            verify_report = None
            if data.verify_status is not None:
                verify_report = VerifyReport(
                    verify_id=uuid4(),
                    attempt_id=attempt.attempt_id,
                    status=data.verify_status,
                    report_json=dict(data.verify_report or {}),
                )
                verify_report = uow.verify_reports.create(verify_report)

                attempt = WorkflowAttempt(
                    attempt_id=attempt.attempt_id,
                    workflow_instance_id=attempt.workflow_instance_id,
                    attempt_number=attempt.attempt_number,
                    status=attempt.status,
                    failure_reason=attempt.failure_reason,
                    verify_status=data.verify_status,
                    started_at=attempt.started_at,
                    finished_at=attempt.finished_at,
                    created_at=attempt.created_at,
                    updated_at=utc_now(),
                )
                attempt = uow.workflow_attempts.update(attempt)

            uow.commit()
            return WorkflowCheckpointResult(
                checkpoint=checkpoint,
                workflow_instance=workflow,
                attempt=attempt,
                verify_report=verify_report,
            )

    def resume_workflow(self, data: ResumeWorkflowInput) -> WorkflowResume:
        with self._uow_factory() as uow:
            workflow = self._require_workflow(uow, data.workflow_instance_id)
            workspace = self._require_workspace(uow, workflow.workspace_id)

            attempt = uow.workflow_attempts.get_running_by_workflow_id(
                workflow.workflow_instance_id
            )
            if attempt is None:
                attempt = uow.workflow_attempts.get_latest_by_workflow_id(
                    workflow.workflow_instance_id
                )

            latest_checkpoint = uow.workflow_checkpoints.get_latest_by_workflow_id(
                workflow.workflow_instance_id
            )
            latest_verify_report = (
                uow.verify_reports.get_latest_by_attempt_id(attempt.attempt_id)
                if attempt is not None
                else None
            )

            projection = None
            if getattr(uow, "projection_states", None) is not None:
                projection = uow.projection_states.get_resume_projection(
                    workspace.workspace_id,
                    workflow.workflow_instance_id,
                )

            warnings = list(
                self._build_resume_warnings(
                    workflow,
                    attempt,
                    latest_checkpoint,
                    latest_verify_report,
                    projection,
                )
            )
            resumable_status = self._classify_resumable_status(
                workflow, attempt, latest_checkpoint, warnings
            )
            next_hint = self._derive_next_hint(
                workflow, attempt, latest_checkpoint, resumable_status
            )

            return WorkflowResume(
                workspace=workspace,
                workflow_instance=workflow,
                attempt=attempt,
                latest_checkpoint=latest_checkpoint,
                latest_verify_report=latest_verify_report,
                resumable_status=resumable_status,
                projection=projection,
                warnings=tuple(warnings),
                next_hint=next_hint,
            )

    def record_resume_projection(
        self, data: RecordProjectionStateInput
    ) -> ProjectionInfo:
        if not data.target_path.strip():
            raise ValidationError("target_path must not be empty")

        normalized = data.normalized()

        with self._uow_factory() as uow:
            workspace = self._require_workspace(uow, normalized.workspace_id)
            workflow = self._require_workflow(uow, normalized.workflow_instance_id)

            if workflow.workspace_id != workspace.workspace_id:
                raise WorkflowAttemptMismatchError(
                    "workflow does not belong to workspace",
                    details={
                        "workspace_id": str(workspace.workspace_id),
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workflow.workspace_id": str(workflow.workspace_id),
                    },
                )

            if getattr(uow, "projection_states", None) is None:
                raise PersistenceError("projection state repository is not available")

            uow.projection_states.record_resume_projection(normalized)
            uow.commit()

            return ProjectionInfo(
                status=normalized.status,
                target_path=normalized.target_path,
                last_successful_write_at=normalized.last_successful_write_at,
                last_canonical_update_at=normalized.last_canonical_update_at,
                open_failure_count=0,
            )

    def complete_workflow(self, data: CompleteWorkflowInput) -> WorkflowCompleteResult:
        with self._uow_factory() as uow:
            workflow = self._require_workflow(uow, data.workflow_instance_id)
            attempt = self._require_attempt(uow, data.attempt_id)
            self._ensure_attempt_matches_workflow(workflow, attempt)

            if workflow.is_terminal:
                raise InvalidStateTransitionError(
                    "workflow is already terminal",
                    details={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "status": workflow.status.value,
                    },
                )

            target_attempt_status = self._map_workflow_status_to_attempt_status(
                data.workflow_status
            )
            finished_at = utc_now()

            updated_attempt = WorkflowAttempt(
                attempt_id=attempt.attempt_id,
                workflow_instance_id=attempt.workflow_instance_id,
                attempt_number=attempt.attempt_number,
                status=target_attempt_status,
                failure_reason=data.failure_reason,
                verify_status=data.verify_status or attempt.verify_status,
                started_at=attempt.started_at,
                finished_at=finished_at,
                created_at=attempt.created_at,
                updated_at=finished_at,
            )
            updated_attempt = uow.workflow_attempts.update(updated_attempt)

            updated_workflow = WorkflowInstance(
                workflow_instance_id=workflow.workflow_instance_id,
                workspace_id=workflow.workspace_id,
                ticket_id=workflow.ticket_id,
                status=data.workflow_status,
                metadata=dict(workflow.metadata),
                created_at=workflow.created_at,
                updated_at=finished_at,
            )
            updated_workflow = uow.workflow_instances.update(updated_workflow)

            verify_report = None
            if data.verify_status is not None:
                verify_report = VerifyReport(
                    verify_id=uuid4(),
                    attempt_id=updated_attempt.attempt_id,
                    status=data.verify_status,
                    report_json=dict(data.verify_report or {}),
                )
                verify_report = uow.verify_reports.create(verify_report)

            uow.commit()
            return WorkflowCompleteResult(
                workflow_instance=updated_workflow,
                attempt=updated_attempt,
                verify_report=verify_report,
            )

    def _require_workspace(self, uow: UnitOfWork, workspace_id: UUID) -> Workspace:
        workspace = uow.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError(
                "workspace not found",
                details={"workspace_id": str(workspace_id)},
            )
        return workspace

    def _require_workflow(
        self, uow: UnitOfWork, workflow_instance_id: UUID
    ) -> WorkflowInstance:
        workflow = uow.workflow_instances.get_by_id(workflow_instance_id)
        if workflow is None:
            raise WorkflowNotFoundError(
                "workflow not found",
                details={"workflow_instance_id": str(workflow_instance_id)},
            )
        return workflow

    def _require_attempt(self, uow: UnitOfWork, attempt_id: UUID) -> WorkflowAttempt:
        attempt = uow.workflow_attempts.get_by_id(attempt_id)
        if attempt is None:
            raise AttemptNotFoundError(
                "attempt not found",
                details={"attempt_id": str(attempt_id)},
            )
        return attempt

    def _ensure_attempt_matches_workflow(
        self,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
    ) -> None:
        if attempt.workflow_instance_id != workflow.workflow_instance_id:
            raise WorkflowAttemptMismatchError(
                "attempt does not belong to workflow",
                details={
                    "workflow_instance_id": str(workflow.workflow_instance_id),
                    "attempt_id": str(attempt.attempt_id),
                    "attempt.workflow_instance_id": str(attempt.workflow_instance_id),
                },
            )

    def _classify_resumable_status(
        self,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt | None,
        latest_checkpoint: WorkflowCheckpoint | None,
        warnings: list[ResumeIssue],
    ) -> ResumableStatus:
        if workflow.is_terminal:
            return ResumableStatus.TERMINAL

        warning_codes = {warning.code for warning in warnings}

        if "running_workflow_without_attempt" in warning_codes:
            return ResumableStatus.INCONSISTENT

        if attempt is None:
            return ResumableStatus.BLOCKED

        if attempt.status != WorkflowAttemptStatus.RUNNING:
            return ResumableStatus.BLOCKED

        if latest_checkpoint is None:
            return ResumableStatus.BLOCKED

        if (
            "stale_projection" in warning_codes
            or "open_projection_failure" in warning_codes
        ):
            return ResumableStatus.RESUMABLE

        return ResumableStatus.RESUMABLE

    def _build_resume_warnings(
        self,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt | None,
        latest_checkpoint: WorkflowCheckpoint | None,
        latest_verify_report: VerifyReport | None,
        projection: ProjectionInfo | None,
    ) -> list[ResumeIssue]:
        warnings: list[ResumeIssue] = []

        if workflow.status == WorkflowInstanceStatus.RUNNING and attempt is None:
            warnings.append(
                ResumeIssue(
                    code="running_workflow_without_attempt",
                    message="workflow is running but no active or latest attempt was found",
                )
            )

        if (
            attempt is not None
            and attempt.status == WorkflowAttemptStatus.RUNNING
            and latest_checkpoint is None
        ):
            warnings.append(
                ResumeIssue(
                    code="running_attempt_without_checkpoint",
                    message="attempt is running but no checkpoint exists yet",
                    details={"attempt_id": str(attempt.attempt_id)},
                )
            )

        if (
            attempt is not None
            and attempt.verify_status is not None
            and latest_verify_report is None
        ):
            warnings.append(
                ResumeIssue(
                    code="missing_verify_report",
                    message="attempt has verify_status but no latest verify report was found",
                    details={"attempt_id": str(attempt.attempt_id)},
                )
            )

        if projection is not None:
            if projection.status == ProjectionStatus.STALE:
                warnings.append(
                    ResumeIssue(
                        code="stale_projection",
                        message="resume projection is stale relative to canonical workflow state",
                        details={"target_path": projection.target_path or ""},
                    )
                )
            elif projection.status == ProjectionStatus.FAILED:
                warnings.append(
                    ResumeIssue(
                        code="open_projection_failure",
                        message="resume projection has unresolved write failures",
                        details={
                            "target_path": projection.target_path or "",
                            "open_failure_count": projection.open_failure_count,
                        },
                    )
                )
            elif projection.status == ProjectionStatus.MISSING:
                warnings.append(
                    ResumeIssue(
                        code="missing_projection",
                        message="resume projection has not been generated yet",
                        details={"target_path": projection.target_path or ""},
                    )
                )

        return warnings

    def _derive_next_hint(
        self,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt | None,
        latest_checkpoint: WorkflowCheckpoint | None,
        resumable_status: ResumableStatus,
    ) -> str | None:
        if resumable_status == ResumableStatus.TERMINAL:
            return "Workflow is terminal. Inspect the final state instead of resuming execution."

        if attempt is None:
            return "No attempt is available. Inspect workflow consistency before continuing."

        if latest_checkpoint is None:
            return "Create an initial checkpoint to establish resumable state."

        next_action = latest_checkpoint.checkpoint_json.get("next_intended_action")
        if isinstance(next_action, str) and next_action.strip():
            return next_action.strip()

        if latest_checkpoint.summary:
            return f"Resume from step '{latest_checkpoint.step_name}' using the latest checkpoint summary."

        return f"Resume from step '{latest_checkpoint.step_name}'."

    def _map_workflow_status_to_attempt_status(
        self,
        workflow_status: WorkflowInstanceStatus,
    ) -> WorkflowAttemptStatus:
        mapping = {
            WorkflowInstanceStatus.COMPLETED: WorkflowAttemptStatus.SUCCEEDED,
            WorkflowInstanceStatus.FAILED: WorkflowAttemptStatus.FAILED,
            WorkflowInstanceStatus.CANCELLED: WorkflowAttemptStatus.CANCELLED,
        }
        try:
            return mapping[workflow_status]
        except KeyError as exc:
            raise InvalidStateTransitionError(
                "workflow cannot be completed into a non-terminal state",
                details={"workflow_status": workflow_status.value},
            ) from exc

    def _validate_workspace_input(self, data: RegisterWorkspaceInput) -> None:
        if not data.repo_url.strip():
            raise ValidationError("repo_url must not be empty")
        if not data.canonical_path.strip():
            raise ValidationError("canonical_path must not be empty")
        if not data.default_branch.strip():
            raise ValidationError("default_branch must not be empty")

    def _validate_ticket_id(self, ticket_id: str) -> None:
        if not ticket_id.strip():
            raise ValidationError("ticket_id must not be empty")

    def _validate_step_name(self, step_name: str) -> None:
        if not step_name.strip():
            raise ValidationError("step_name must not be empty")
