from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4

from .memory_bridge import WorkflowCompletionMemoryRecordResult, WorkflowMemoryBridge

logger = logging.getLogger(__name__)


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


class ProjectionArtifactType(StrEnum):
    RESUME_JSON = "resume_json"
    RESUME_MD = "resume_md"


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
    projection_type: ProjectionArtifactType
    status: ProjectionStatus
    target_path: str | None = None
    last_successful_write_at: datetime | None = None
    last_canonical_update_at: datetime | None = None
    open_failure_count: int = 0


@dataclass(slots=True, frozen=True)
class ProjectionFailureInfo:
    projection_type: ProjectionArtifactType
    error_code: str | None
    error_message: str
    target_path: str
    attempt_id: UUID | None = None
    occurred_at: datetime | None = None
    resolved_at: datetime | None = None
    open_failure_count: int = 1
    retry_count: int = 0
    status: str = "open"


@dataclass(slots=True, frozen=True)
class RecordProjectionStateInput:
    workspace_id: UUID
    workflow_instance_id: UUID
    projection_type: ProjectionArtifactType
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
            projection_type=self.projection_type,
            status=self.status,
            target_path=self.target_path,
            last_successful_write_at=write_at,
            last_canonical_update_at=canonical_update_at,
        )


@dataclass(slots=True, frozen=True)
class RecordProjectionFailureInput:
    workspace_id: UUID
    workflow_instance_id: UUID
    projection_type: ProjectionArtifactType
    target_path: str
    error_message: str
    attempt_id: UUID | None = None
    error_code: str | None = None


@dataclass(slots=True, frozen=True)
class EpisodeRecord:
    episode_id: UUID
    workflow_instance_id: UUID
    summary: str
    attempt_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "recorded"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True, frozen=True)
class MemoryItemRecord:
    memory_id: UUID
    workspace_id: UUID | None = None
    episode_id: UUID | None = None
    type: str = "episode_note"
    provenance: str = "episode"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True, frozen=True)
class MemoryEmbeddingRecord:
    memory_embedding_id: UUID
    memory_id: UUID
    embedding_model: str
    embedding: tuple[float, ...] = ()
    content_hash: str | None = None
    created_at: datetime = field(default_factory=utc_now)


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
    projections: tuple[ProjectionInfo, ...] = ()
    warnings: tuple[ResumeIssue, ...] = ()
    closed_projection_failures: tuple[ProjectionFailureInfo, ...] = ()
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
    warnings: tuple[ResumeIssue, ...] = ()
    auto_memory_details: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class WorkflowStats:
    workspace_count: int
    workflow_status_counts: dict[str, int]
    attempt_status_counts: dict[str, int]
    verify_status_counts: dict[str, int]
    checkpoint_count: int
    episode_count: int
    memory_item_count: int
    memory_embedding_count: int
    open_projection_failure_count: int
    latest_workflow_updated_at: datetime | None = None
    latest_checkpoint_created_at: datetime | None = None
    latest_verify_report_created_at: datetime | None = None
    latest_episode_created_at: datetime | None = None
    latest_memory_item_created_at: datetime | None = None
    latest_memory_embedding_created_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class MemoryStats:
    episode_count: int
    memory_item_count: int
    memory_embedding_count: int
    memory_relation_count: int
    memory_item_provenance_counts: dict[str, int]
    latest_episode_created_at: datetime | None = None
    latest_memory_item_created_at: datetime | None = None
    latest_memory_embedding_created_at: datetime | None = None
    latest_memory_relation_created_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class FailureListEntry:
    failure_scope: str
    failure_type: str
    failure_status: str
    projection_type: str | None = None
    target_path: str | None = None
    error_code: str | None = None
    error_message: str = ""
    attempt_id: UUID | None = None
    occurred_at: datetime | None = None
    resolved_at: datetime | None = None
    open_failure_count: int = 0
    retry_count: int = 0


@dataclass(slots=True, frozen=True)
class WorkflowListEntry:
    workflow_instance_id: UUID
    workspace_id: UUID
    canonical_path: str | None
    ticket_id: str
    workflow_status: str
    latest_step_name: str | None = None
    latest_verify_status: str | None = None
    updated_at: datetime | None = None


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

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        raise NotImplementedError

    def list_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        raise NotImplementedError

    def list_recent(
        self,
        *,
        limit: int,
        status: str | None = None,
        workspace_id: UUID | None = None,
        ticket_id: str | None = None,
    ) -> tuple[WorkflowInstance, ...]:
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


class MemoryEpisodeRepository:
    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        raise NotImplementedError

    def list_by_workflow_id(
        self,
        workflow_instance_id: UUID,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        raise NotImplementedError


class MemoryItemRepository:
    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        raise NotImplementedError

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        raise NotImplementedError

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        raise NotImplementedError

    def count_by_provenance(self) -> dict[str, int]:
        raise NotImplementedError


class MemoryEmbeddingRepository:
    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        raise NotImplementedError

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        raise NotImplementedError


class ProjectionStateRepository:
    def get_resume_projections(
        self, workspace_id: UUID, workflow_instance_id: UUID
    ) -> tuple[ProjectionInfo, ...]:
        raise NotImplementedError

    def record_resume_projection(self, projection: RecordProjectionStateInput) -> None:
        raise NotImplementedError


class ProjectionFailureRepository:
    def get_open_failures_by_workflow_id(
        self, workspace_id: UUID, workflow_instance_id: UUID
    ) -> list[ProjectionFailureInfo]:
        raise NotImplementedError

    def get_closed_failures_by_workflow_id(
        self, workspace_id: UUID, workflow_instance_id: UUID
    ) -> list[ProjectionFailureInfo]:
        raise NotImplementedError

    def list_failures(
        self,
        *,
        limit: int,
        status: str | None = None,
        open_only: bool = False,
    ) -> tuple[ProjectionFailureInfo, ...]:
        raise NotImplementedError

    def record_resume_projection_failure(
        self, failure: RecordProjectionFailureInput
    ) -> ProjectionFailureInfo:
        raise NotImplementedError

    def resolve_resume_projection_failures(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        raise NotImplementedError

    def ignore_resume_projection_failures(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        raise NotImplementedError


class UnitOfWork:
    workspaces: WorkspaceRepository
    workflow_instances: WorkflowInstanceRepository
    workflow_attempts: WorkflowAttemptRepository
    workflow_checkpoints: WorkflowCheckpointRepository
    verify_reports: VerifyReportRepository
    memory_episodes: MemoryEpisodeRepository | None
    memory_items: MemoryItemRepository | None
    memory_embeddings: MemoryEmbeddingRepository | None
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


def _status_count_dict(
    values: tuple[str, ...],
    counts: dict[str, int],
) -> dict[str, int]:
    return {value: int(counts.get(value, 0)) for value in values}


class WorkflowService:
    def __init__(
        self,
        uow_factory: Any,
        *,
        workflow_memory_bridge: WorkflowMemoryBridge | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._workflow_memory_bridge = workflow_memory_bridge

    def get_stats(self) -> WorkflowStats:
        with self._uow_factory() as uow:
            workspace_count = self._count_rows(uow, "workspaces")
            checkpoint_count = self._count_rows(uow, "workflow_checkpoints")
            episode_count = self._count_rows(uow, "memory_episodes")
            memory_item_count = self._count_rows(uow, "memory_items")
            memory_embedding_count = self._count_rows(uow, "memory_embeddings")

            workflow_status_counts = self._count_grouped_statuses(
                uow,
                repository_name="workflow_instances",
                allowed_statuses=(
                    WorkflowInstanceStatus.RUNNING.value,
                    WorkflowInstanceStatus.COMPLETED.value,
                    WorkflowInstanceStatus.FAILED.value,
                    WorkflowInstanceStatus.CANCELLED.value,
                ),
            )
            attempt_status_counts = self._count_grouped_statuses(
                uow,
                repository_name="workflow_attempts",
                allowed_statuses=(
                    WorkflowAttemptStatus.RUNNING.value,
                    WorkflowAttemptStatus.SUCCEEDED.value,
                    WorkflowAttemptStatus.FAILED.value,
                    WorkflowAttemptStatus.CANCELLED.value,
                ),
            )
            verify_status_counts = self._count_grouped_statuses(
                uow,
                repository_name="verify_reports",
                allowed_statuses=(
                    VerifyStatus.PENDING.value,
                    VerifyStatus.PASSED.value,
                    VerifyStatus.FAILED.value,
                    VerifyStatus.SKIPPED.value,
                ),
            )

            latest_workflow_updated_at = self._max_datetime_field(
                uow,
                repository_name="workflow_instances",
                field_name="updated_at",
            )
            latest_checkpoint_created_at = self._max_datetime_field(
                uow,
                repository_name="workflow_checkpoints",
                field_name="created_at",
            )
            latest_verify_report_created_at = self._max_datetime_field(
                uow,
                repository_name="verify_reports",
                field_name="created_at",
            )
            latest_episode_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_episodes",
                field_name="created_at",
            )
            latest_memory_item_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_items",
                field_name="created_at",
            )
            latest_memory_embedding_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_embeddings",
                field_name="created_at",
            )

            open_projection_failure_count = self._count_open_projection_failures(uow)

            return WorkflowStats(
                workspace_count=workspace_count,
                workflow_status_counts=workflow_status_counts,
                attempt_status_counts=attempt_status_counts,
                verify_status_counts=verify_status_counts,
                checkpoint_count=checkpoint_count,
                episode_count=episode_count,
                memory_item_count=memory_item_count,
                memory_embedding_count=memory_embedding_count,
                open_projection_failure_count=open_projection_failure_count,
                latest_workflow_updated_at=latest_workflow_updated_at,
                latest_checkpoint_created_at=latest_checkpoint_created_at,
                latest_verify_report_created_at=latest_verify_report_created_at,
                latest_episode_created_at=latest_episode_created_at,
                latest_memory_item_created_at=latest_memory_item_created_at,
                latest_memory_embedding_created_at=latest_memory_embedding_created_at,
            )

    def get_memory_stats(self) -> MemoryStats:
        with self._uow_factory() as uow:
            episode_count = self._count_rows(uow, "memory_episodes")
            memory_item_count = self._count_rows(uow, "memory_items")
            memory_embedding_count = self._count_rows(uow, "memory_embeddings")
            memory_relation_count = self._count_rows(uow, "memory_relations")

            latest_episode_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_episodes",
                field_name="created_at",
            )
            latest_memory_item_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_items",
                field_name="created_at",
            )
            latest_memory_embedding_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_embeddings",
                field_name="created_at",
            )
            latest_memory_relation_created_at = self._max_datetime_field(
                uow,
                repository_name="memory_relations",
                field_name="created_at",
            )

            memory_item_provenance_counts = self._count_memory_item_provenance(uow)

            return MemoryStats(
                episode_count=episode_count,
                memory_item_count=memory_item_count,
                memory_embedding_count=memory_embedding_count,
                memory_relation_count=memory_relation_count,
                memory_item_provenance_counts=memory_item_provenance_counts,
                latest_episode_created_at=latest_episode_created_at,
                latest_memory_item_created_at=latest_memory_item_created_at,
                latest_memory_embedding_created_at=latest_memory_embedding_created_at,
                latest_memory_relation_created_at=latest_memory_relation_created_at,
            )

    def list_workflows(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        workspace_id: UUID | None = None,
        ticket_id: str | None = None,
    ) -> tuple[WorkflowListEntry, ...]:
        if limit <= 0:
            raise ValidationError("limit must be greater than zero")

        normalized_status = status.strip() if isinstance(status, str) else None
        if normalized_status == "":
            normalized_status = None

        if normalized_status is not None:
            allowed_statuses = {
                WorkflowInstanceStatus.RUNNING.value,
                WorkflowInstanceStatus.COMPLETED.value,
                WorkflowInstanceStatus.FAILED.value,
                WorkflowInstanceStatus.CANCELLED.value,
            }
            if normalized_status not in allowed_statuses:
                raise ValidationError(
                    "status must be one of running, completed, failed, or cancelled"
                )

        normalized_ticket_id = ticket_id.strip() if isinstance(ticket_id, str) else None
        if normalized_ticket_id == "":
            normalized_ticket_id = None

        with self._uow_factory() as uow:
            workflows = uow.workflow_instances.list_recent(
                limit=limit,
                status=normalized_status,
                workspace_id=workspace_id,
                ticket_id=normalized_ticket_id,
            )

            entries: list[WorkflowListEntry] = []
            for workflow in workflows:
                workspace = uow.workspaces.get_by_id(workflow.workspace_id)
                latest_attempt = uow.workflow_attempts.get_latest_by_workflow_id(
                    workflow.workflow_instance_id
                )
                latest_checkpoint = uow.workflow_checkpoints.get_latest_by_workflow_id(
                    workflow.workflow_instance_id
                )
                latest_verify_report = (
                    uow.verify_reports.get_latest_by_attempt_id(
                        latest_attempt.attempt_id
                    )
                    if latest_attempt is not None
                    else None
                )

                entries.append(
                    WorkflowListEntry(
                        workflow_instance_id=workflow.workflow_instance_id,
                        workspace_id=workflow.workspace_id,
                        canonical_path=(
                            workspace.canonical_path if workspace is not None else None
                        ),
                        ticket_id=workflow.ticket_id,
                        workflow_status=workflow.status.value,
                        latest_step_name=(
                            latest_checkpoint.step_name
                            if latest_checkpoint is not None
                            else None
                        ),
                        latest_verify_status=(
                            latest_verify_report.status.value
                            if latest_verify_report is not None
                            else (
                                latest_attempt.verify_status.value
                                if (
                                    latest_attempt is not None
                                    and latest_attempt.verify_status is not None
                                )
                                else None
                            )
                        ),
                        updated_at=workflow.updated_at,
                    )
                )

            return tuple(entries)

    def list_failures(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        open_only: bool = False,
    ) -> tuple[FailureListEntry, ...]:
        if limit <= 0:
            raise ValidationError("limit must be greater than zero")

        normalized_status = status.strip() if isinstance(status, str) else None
        if normalized_status == "":
            normalized_status = None

        allowed_statuses = {"open", "resolved", "ignored"}
        if normalized_status is not None and normalized_status not in allowed_statuses:
            raise ValidationError("status must be one of open, resolved, or ignored")

        if open_only:
            normalized_status = "open"

        with self._uow_factory() as uow:
            repository = getattr(uow, "projection_failures", None)
            if repository is None:
                return ()

            failures = repository.list_failures(
                limit=limit,
                status=normalized_status,
                open_only=open_only,
            )

            return tuple(
                FailureListEntry(
                    failure_scope="projection",
                    failure_type=failure.projection_type.value,
                    failure_status=failure.status,
                    projection_type=failure.projection_type.value,
                    target_path=failure.target_path,
                    error_code=failure.error_code,
                    error_message=failure.error_message,
                    attempt_id=failure.attempt_id,
                    occurred_at=failure.occurred_at,
                    resolved_at=failure.resolved_at,
                    open_failure_count=failure.open_failure_count,
                    retry_count=failure.retry_count,
                )
                for failure in failures
            )

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

            projections: tuple[ProjectionInfo, ...] = ()
            if getattr(uow, "projection_states", None) is not None:
                projections = uow.projection_states.get_resume_projections(
                    workspace.workspace_id,
                    workflow.workflow_instance_id,
                )

            open_projection_failures: list[ProjectionFailureInfo] = []
            closed_projection_failures: list[ProjectionFailureInfo] = []
            if getattr(uow, "projection_failures", None) is not None:
                open_projection_failures = (
                    uow.projection_failures.get_open_failures_by_workflow_id(
                        workspace.workspace_id,
                        workflow.workflow_instance_id,
                    )
                )
                closed_projection_failures = (
                    uow.projection_failures.get_closed_failures_by_workflow_id(
                        workspace.workspace_id,
                        workflow.workflow_instance_id,
                    )
                )

            warnings = list(
                self._build_resume_warnings(
                    workflow,
                    attempt,
                    latest_checkpoint,
                    latest_verify_report,
                    projections,
                    open_projection_failures,
                    closed_projection_failures,
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
                projections=projections,
                warnings=tuple(warnings),
                closed_projection_failures=tuple(closed_projection_failures),
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
                projection_type=normalized.projection_type,
                status=normalized.status,
                target_path=normalized.target_path,
                last_successful_write_at=normalized.last_successful_write_at,
                last_canonical_update_at=normalized.last_canonical_update_at,
                open_failure_count=0,
            )

    def record_resume_projection_failure(
        self, data: RecordProjectionFailureInput
    ) -> ProjectionFailureInfo:
        if not data.target_path.strip():
            raise ValidationError("target_path must not be empty")
        if not data.error_message.strip():
            raise ValidationError("error_message must not be empty")

        with self._uow_factory() as uow:
            workspace = self._require_workspace(uow, data.workspace_id)
            workflow = self._require_workflow(uow, data.workflow_instance_id)

            if workflow.workspace_id != workspace.workspace_id:
                raise WorkflowAttemptMismatchError(
                    "workflow does not belong to workspace",
                    details={
                        "workspace_id": str(workspace.workspace_id),
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workflow.workspace_id": str(workflow.workspace_id),
                    },
                )

            if getattr(uow, "projection_failures", None) is None:
                raise PersistenceError("projection failure repository is not available")

            failure_info = uow.projection_failures.record_resume_projection_failure(
                data
            )
            uow.commit()
            return failure_info

    def resolve_resume_projection_failures(
        self,
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        with self._uow_factory() as uow:
            workspace = self._require_workspace(uow, workspace_id)
            workflow = self._require_workflow(uow, workflow_instance_id)

            if workflow.workspace_id != workspace.workspace_id:
                raise WorkflowAttemptMismatchError(
                    "workflow does not belong to workspace",
                    details={
                        "workspace_id": str(workspace.workspace_id),
                        "workflow_instance_id": str(workflow_instance_id),
                        "workflow.workspace_id": str(workflow.workspace_id),
                    },
                )

            if getattr(uow, "projection_failures", None) is None:
                raise PersistenceError("projection failure repository is not available")

            resolved_count = uow.projection_failures.resolve_resume_projection_failures(
                workspace.workspace_id,
                workflow.workflow_instance_id,
                projection_type,
            )
            uow.commit()
            return resolved_count

    def ignore_resume_projection_failures(
        self,
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        with self._uow_factory() as uow:
            workspace = self._require_workspace(uow, workspace_id)
            workflow = self._require_workflow(uow, workflow_instance_id)

            if workflow.workspace_id != workspace.workspace_id:
                raise WorkflowAttemptMismatchError(
                    "workflow does not belong to workspace",
                    details={
                        "workspace_id": str(workspace.workspace_id),
                        "workflow_instance_id": str(workflow_instance_id),
                        "workflow.workspace_id": str(workflow.workspace_id),
                    },
                )

            if getattr(uow, "projection_failures", None) is None:
                raise PersistenceError("projection failure repository is not available")

            ignored_count = uow.projection_failures.ignore_resume_projection_failures(
                workspace.workspace_id,
                workflow.workflow_instance_id,
                projection_type,
            )
            uow.commit()
            return ignored_count

    def reconcile_resume_projection(
        self,
        *,
        success_updates: tuple[RecordProjectionStateInput, ...] = (),
        failure_updates: tuple[RecordProjectionFailureInput, ...] = (),
    ) -> tuple[ProjectionInfo, ...]:
        reconciled: list[ProjectionInfo] = []

        resolved_projections: set[tuple[UUID, UUID, ProjectionArtifactType]] = set()

        for state in success_updates:
            key = (
                state.workspace_id,
                state.workflow_instance_id,
                state.projection_type,
            )
            if key not in resolved_projections:
                self.resolve_resume_projection_failures(
                    workspace_id=state.workspace_id,
                    workflow_instance_id=state.workflow_instance_id,
                    projection_type=state.projection_type,
                )
                resolved_projections.add(key)
            reconciled.append(self.record_resume_projection(state))

        for failure in failure_updates:
            self.record_resume_projection_failure(failure)

        return tuple(reconciled)

    def complete_workflow(self, data: CompleteWorkflowInput) -> WorkflowCompleteResult:
        logger.info(
            "workflow completion service entry",
            extra={
                "workflow_instance_id": str(data.workflow_instance_id),
                "attempt_id": str(data.attempt_id),
                "workflow_status": data.workflow_status.value,
                "has_summary": data.summary is not None,
                "has_verify_status": data.verify_status is not None,
                "has_verify_report": data.verify_report is not None,
                "has_failure_reason": data.failure_reason is not None,
                "has_workflow_memory_bridge": self._workflow_memory_bridge is not None,
                "workflow_memory_bridge_type": (
                    type(self._workflow_memory_bridge).__name__
                    if self._workflow_memory_bridge is not None
                    else None
                ),
            },
        )
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

            latest_checkpoint = uow.workflow_checkpoints.get_latest_by_workflow_id(
                workflow.workflow_instance_id
            )

            completion_warnings: list[ResumeIssue] = []
            auto_memory_details: dict[str, Any] | None = None

            workflow_memory_bridge = self._workflow_memory_bridge
            if (
                workflow_memory_bridge is not None
                and type(uow).__name__ == "PostgresUnitOfWork"
                and uow.memory_episodes is not None
                and uow.memory_items is not None
            ):
                workflow_memory_bridge = WorkflowMemoryBridge(
                    episode_repository=uow.memory_episodes,
                    memory_item_repository=uow.memory_items,
                    memory_embedding_repository=uow.memory_embeddings,
                    embedding_generator=workflow_memory_bridge.embedding_generator,
                )

            if workflow_memory_bridge is not None:
                try:
                    auto_memory_result = (
                        workflow_memory_bridge.record_workflow_completion_memory(
                            workflow=updated_workflow,
                            attempt=updated_attempt,
                            latest_checkpoint=latest_checkpoint,
                            verify_report=verify_report,
                            summary=data.summary,
                            failure_reason=data.failure_reason,
                        )
                    )
                except Exception as exc:
                    completion_warnings.append(
                        ResumeIssue(
                            code="auto_memory_recording_failed",
                            message=(
                                "workflow completion succeeded but automatic memory "
                                "recording failed"
                            ),
                            details={
                                "error_type": type(exc).__name__,
                                "error_message": str(exc),
                            },
                        )
                    )
                else:
                    if auto_memory_result is None:
                        auto_memory_details = {
                            "auto_memory_recorded": False,
                            "auto_memory_skipped_reason": (
                                "no_completion_summary_source"
                            ),
                        }
                    else:
                        auto_memory_details = dict(auto_memory_result.details)
                        if (
                            auto_memory_result.details.get(
                                "embedding_persistence_status"
                            )
                            == "failed"
                        ):
                            completion_warnings.append(
                                ResumeIssue(
                                    code="auto_memory_embedding_failed",
                                    message=(
                                        "workflow completion succeeded but automatic "
                                        "memory embedding generation failed"
                                    ),
                                    details={
                                        "embedding_generation_skipped_reason": (
                                            auto_memory_result.details.get(
                                                "embedding_generation_skipped_reason"
                                            )
                                        ),
                                        "embedding_generation_failure": (
                                            auto_memory_result.details.get(
                                                "embedding_generation_failure"
                                            )
                                        ),
                                    },
                                )
                            )

            uow.commit()

            return WorkflowCompleteResult(
                workflow_instance=updated_workflow,
                attempt=updated_attempt,
                verify_report=verify_report,
                warnings=tuple(completion_warnings),
                auto_memory_details=auto_memory_details,
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
        projections: tuple[ProjectionInfo, ...],
        open_projection_failures: list[ProjectionFailureInfo] | None = None,
        closed_projection_failures: list[ProjectionFailureInfo] | None = None,
    ) -> tuple[ResumeIssue, ...]:
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

        failures_by_projection_type: dict[
            ProjectionArtifactType, list[ProjectionFailureInfo]
        ] = {}
        if open_projection_failures:
            for failure in open_projection_failures:
                failures_by_projection_type.setdefault(
                    failure.projection_type, []
                ).append(failure)

        closed_failures_by_projection_type: dict[
            ProjectionArtifactType, list[ProjectionFailureInfo]
        ] = {}
        if closed_projection_failures:
            for failure in closed_projection_failures:
                closed_failures_by_projection_type.setdefault(
                    failure.projection_type, []
                ).append(failure)

        for projection in projections:
            if projection.status == ProjectionStatus.STALE:
                warnings.append(
                    ResumeIssue(
                        code="stale_projection",
                        message="resume projection is stale relative to canonical workflow state",
                        details={
                            "projection_type": projection.projection_type.value,
                            "target_path": projection.target_path or "",
                        },
                    )
                )
            elif projection.status == ProjectionStatus.FAILED:
                projection_failures = failures_by_projection_type.get(
                    projection.projection_type, []
                )
                closed_failures = closed_failures_by_projection_type.get(
                    projection.projection_type, []
                )
                if projection.open_failure_count > 0:
                    failure_details: dict[str, Any] = {
                        "projection_type": projection.projection_type.value,
                        "target_path": projection.target_path or "",
                        "open_failure_count": projection.open_failure_count,
                    }
                    if projection_failures:
                        failure_details["failures"] = [
                            {
                                "projection_type": failure.projection_type.value,
                                "target_path": failure.target_path,
                                "attempt_id": (
                                    str(failure.attempt_id)
                                    if failure.attempt_id is not None
                                    else None
                                ),
                                "error_code": failure.error_code,
                                "error_message": failure.error_message,
                                "occurred_at": (
                                    failure.occurred_at.isoformat()
                                    if failure.occurred_at is not None
                                    else None
                                ),
                                "resolved_at": (
                                    failure.resolved_at.isoformat()
                                    if failure.resolved_at is not None
                                    else None
                                ),
                                "open_failure_count": failure.open_failure_count,
                                "retry_count": failure.retry_count,
                                "status": failure.status,
                            }
                            for failure in projection_failures
                        ]

                    warnings.append(
                        ResumeIssue(
                            code="open_projection_failure",
                            message="resume projection has unresolved write failures",
                            details=failure_details,
                        )
                    )
                elif closed_failures:
                    warning_code = (
                        "ignored_projection_failure"
                        if any(
                            failure.status == "ignored" for failure in closed_failures
                        )
                        else "resolved_projection_failure"
                    )
                    warning_message = (
                        "resume projection has ignored write failures"
                        if warning_code == "ignored_projection_failure"
                        else "resume projection has previously resolved write failures"
                    )
                    warnings.append(
                        ResumeIssue(
                            code=warning_code,
                            message=warning_message,
                            details={
                                "projection_type": projection.projection_type.value,
                                "target_path": projection.target_path or "",
                                "open_failure_count": projection.open_failure_count,
                                "failures": [
                                    {
                                        "projection_type": failure.projection_type.value,
                                        "target_path": failure.target_path,
                                        "attempt_id": (
                                            str(failure.attempt_id)
                                            if failure.attempt_id is not None
                                            else None
                                        ),
                                        "error_code": failure.error_code,
                                        "error_message": failure.error_message,
                                        "occurred_at": (
                                            failure.occurred_at.isoformat()
                                            if failure.occurred_at is not None
                                            else None
                                        ),
                                        "resolved_at": (
                                            failure.resolved_at.isoformat()
                                            if failure.resolved_at is not None
                                            else None
                                        ),
                                        "open_failure_count": failure.open_failure_count,
                                        "retry_count": failure.retry_count,
                                        "status": failure.status,
                                    }
                                    for failure in closed_failures
                                ],
                            },
                        )
                    )
            elif projection.status == ProjectionStatus.MISSING:
                warnings.append(
                    ResumeIssue(
                        code="missing_projection",
                        message="resume projection has not been generated yet",
                        details={
                            "projection_type": projection.projection_type.value,
                            "target_path": projection.target_path or "",
                        },
                    )
                )

        return tuple(warnings)

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

    def _count_rows(
        self,
        uow: UnitOfWork,
        repository_name: str,
    ) -> int:
        repository = getattr(uow, repository_name, None)
        if repository is None:
            return 0

        records_by_id = getattr(repository, "_records_by_id", None)
        if isinstance(records_by_id, dict):
            return len(records_by_id)

        workspaces_by_id = getattr(repository, "_workspaces_by_id", None)
        if isinstance(workspaces_by_id, dict):
            return len(workspaces_by_id)

        values_by_id = getattr(repository, "_values_by_id", None)
        if isinstance(values_by_id, dict):
            return len(values_by_id)

        if repository_name == "projection_failures":
            failures_by_key = getattr(repository, "_failures_by_key", None)
            if isinstance(failures_by_key, dict):
                return sum(len(failures) for failures in failures_by_key.values())

        if repository_name == "projection_states":
            projection_states_by_key = getattr(
                repository, "_projection_states_by_key", None
            )
            if isinstance(projection_states_by_key, dict):
                return len(projection_states_by_key)

        count_method = getattr(repository, "count_all", None)
        if callable(count_method):
            return int(count_method())

        raise PersistenceError(
            f"stats counting is not supported for repository '{repository_name}'"
        )

    def _count_grouped_statuses(
        self,
        uow: UnitOfWork,
        *,
        repository_name: str,
        allowed_statuses: tuple[str, ...],
    ) -> dict[str, int]:
        repository = getattr(uow, repository_name, None)
        if repository is None:
            return _status_count_dict(allowed_statuses, {})

        records_by_id = getattr(repository, "_records_by_id", None)
        if records_by_id is None:
            values_by_id = getattr(repository, "_values_by_id", None)
            if isinstance(values_by_id, dict):
                records_by_id = values_by_id

        if isinstance(records_by_id, dict):
            counts: dict[str, int] = {}
            for record in records_by_id.values():
                status = getattr(record, "status", None)
                if status is None:
                    continue
                status_value = getattr(status, "value", status)
                normalized_status = str(status_value)
                counts[normalized_status] = counts.get(normalized_status, 0) + 1
            return _status_count_dict(allowed_statuses, counts)

        count_method = getattr(repository, "count_by_status", None)
        if callable(count_method):
            return _status_count_dict(
                allowed_statuses,
                {str(key): int(value) for key, value in count_method().items()},
            )

        raise PersistenceError(
            f"stats status aggregation is not supported for repository '{repository_name}'"
        )

    def _max_datetime_field(
        self,
        uow: UnitOfWork,
        *,
        repository_name: str,
        field_name: str,
    ) -> datetime | None:
        repository = getattr(uow, repository_name, None)
        if repository is None:
            return None

        records_by_id = getattr(repository, "_records_by_id", None)
        if records_by_id is None:
            values_by_id = getattr(repository, "_values_by_id", None)
            if isinstance(values_by_id, dict):
                records_by_id = values_by_id

        if isinstance(records_by_id, dict):
            timestamps = [
                value
                for record in records_by_id.values()
                if isinstance((value := getattr(record, field_name, None)), datetime)
            ]
            if not timestamps:
                return None
            return max(timestamps)

        max_method = getattr(repository, "max_datetime", None)
        if callable(max_method):
            value = max_method(field_name)
            return value if isinstance(value, datetime) or value is None else None

        raise PersistenceError(
            f"stats datetime aggregation is not supported for repository '{repository_name}'"
        )

    def _count_open_projection_failures(self, uow: UnitOfWork) -> int:
        repository = getattr(uow, "projection_failures", None)
        if repository is None:
            return 0

        failures_by_key = getattr(repository, "_failures_by_key", None)
        if isinstance(failures_by_key, dict):
            return sum(
                1
                for failures in failures_by_key.values()
                for failure in failures
                if getattr(failure, "status", None) == "open"
            )

        count_method = getattr(repository, "count_open_failures", None)
        if callable(count_method):
            return int(count_method())

        raise PersistenceError(
            "stats failure aggregation is not supported for projection failures"
        )

    def _count_memory_item_provenance(self, uow: UnitOfWork) -> dict[str, int]:
        repository = getattr(uow, "memory_items", None)
        if repository is None:
            return {}

        records_by_id = getattr(repository, "_records_by_id", None)
        if records_by_id is None:
            values_by_id = getattr(repository, "_values_by_id", None)
            if isinstance(values_by_id, dict):
                records_by_id = values_by_id

        if isinstance(records_by_id, dict):
            counts: dict[str, int] = {}
            for record in records_by_id.values():
                provenance = getattr(record, "provenance", None)
                if provenance is None:
                    continue
                normalized_provenance = str(provenance)
                counts[normalized_provenance] = counts.get(normalized_provenance, 0) + 1
            return counts

        memory_items_by_id = getattr(repository, "_memory_items_by_id", None)
        if isinstance(memory_items_by_id, dict):
            counts: dict[str, int] = {}
            for record in memory_items_by_id.values():
                provenance = getattr(record, "provenance", None)
                if provenance is None:
                    continue
                normalized_provenance = str(provenance)
                counts[normalized_provenance] = counts.get(normalized_provenance, 0) + 1
            return counts

        count_method = getattr(repository, "count_by_provenance", None)
        if callable(count_method):
            return {str(key): int(value) for key, value in count_method().items()}

        raise PersistenceError(
            "memory stats provenance aggregation is not supported for memory items"
        )

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
