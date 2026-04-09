from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from .memory_bridge import WorkflowMemoryBridge

logger = logging.getLogger(__name__)

_RESUME_LATENCY_WARNING_THRESHOLD_MS = 2000


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
class MemoryRelationRecord:
    memory_relation_id: UUID
    source_memory_id: UUID
    target_memory_id: UUID
    relation_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
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
    warnings: tuple[ResumeIssue, ...] = ()
    auto_memory_details: dict[str, Any] | None = None


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
    checkpoint_auto_memory_recorded_count: int = 0
    checkpoint_auto_memory_skipped_count: int = 0
    workflow_completion_auto_memory_recorded_count: int = 0
    workflow_completion_auto_memory_skipped_count: int = 0
    interaction_memory_item_count: int = 0
    file_work_memory_item_count: int = 0
    memory_summary_count: int = 0
    memory_summary_membership_count: int = 0
    derived_memory_item_count: int = 0
    derived_memory_item_state: str = "unknown"
    derived_memory_item_reason: str | None = None
    derived_memory_graph_status: str | None = None
    structured_checkpoint_coverage: dict[str, int] = field(default_factory=dict)
    summary_backlog_count: int = 0
    age_summary_graph_ready_count: int = 0
    age_summary_graph_stale_count: int = 0
    age_summary_graph_degraded_count: int = 0
    age_summary_graph_unknown_count: int = 0
    latest_workflow_updated_at: datetime | None = None
    latest_checkpoint_created_at: datetime | None = None
    latest_verify_report_created_at: datetime | None = None
    latest_episode_created_at: datetime | None = None
    latest_memory_item_created_at: datetime | None = None
    latest_memory_embedding_created_at: datetime | None = None
    completion_summary_build_request_count: int = 0
    completion_summary_build_attempted_count: int = 0
    completion_summary_build_success_count: int = 0
    completion_summary_build_request_rate_base: int = 0
    completion_summary_build_attempted_rate_base: int = 0
    completion_summary_build_success_rate_base: int = 0
    completion_summary_build_request_rate: float = 0.0
    completion_summary_build_attempted_rate: float = 0.0
    completion_summary_build_success_rate: float = 0.0
    completion_summary_build_skipped_reason_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class MemoryStats:
    episode_count: int
    memory_item_count: int
    memory_embedding_count: int
    memory_relation_count: int
    memory_item_provenance_counts: dict[str, int]
    checkpoint_auto_memory_recorded_count: int = 0
    checkpoint_auto_memory_skipped_count: int = 0
    workflow_completion_auto_memory_recorded_count: int = 0
    workflow_completion_auto_memory_skipped_count: int = 0
    interaction_memory_item_count: int = 0
    file_work_memory_item_count: int = 0
    memory_summary_count: int = 0
    memory_summary_membership_count: int = 0
    derived_memory_item_count: int = 0
    derived_memory_item_state: str = "unknown"
    derived_memory_item_reason: str | None = None
    derived_memory_graph_status: str | None = None
    age_summary_graph_ready_count: int = 0
    age_summary_graph_stale_count: int = 0
    age_summary_graph_degraded_count: int = 0
    age_summary_graph_unknown_count: int = 0
    latest_episode_created_at: datetime | None = None
    latest_memory_item_created_at: datetime | None = None
    latest_memory_embedding_created_at: datetime | None = None
    latest_memory_relation_created_at: datetime | None = None
    latest_derived_memory_item_created_at: datetime | None = None
    completion_summary_build_request_count: int = 0
    completion_summary_build_attempted_count: int = 0
    completion_summary_build_success_count: int = 0
    completion_summary_build_request_rate_base: int = 0
    completion_summary_build_attempted_rate_base: int = 0
    completion_summary_build_success_rate_base: int = 0
    completion_summary_build_request_rate: float = 0.0
    completion_summary_build_attempted_rate: float = 0.0
    completion_summary_build_success_rate: float = 0.0
    completion_summary_build_skipped_reason_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class FailureListEntry:
    failure_scope: str
    failure_type: str
    failure_status: str
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

    def get_running_by_workspace_id(self, workspace_id: UUID) -> WorkflowInstance | None:
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

    def get_running_by_workflow_id(self, workflow_instance_id: UUID) -> WorkflowAttempt | None:
        raise NotImplementedError

    def get_latest_by_workflow_id(self, workflow_instance_id: UUID) -> WorkflowAttempt | None:
        raise NotImplementedError

    def get_next_attempt_number(self, workflow_instance_id: UUID) -> int:
        raise NotImplementedError

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        raise NotImplementedError

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        raise NotImplementedError


class WorkflowCheckpointRepository:
    def get_latest_by_workflow_id(self, workflow_instance_id: UUID) -> WorkflowCheckpoint | None:
        raise NotImplementedError

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> WorkflowCheckpoint | None:
        raise NotImplementedError

    def list_recent(self, *, limit: int) -> tuple[WorkflowCheckpoint, ...]:
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

    def create_via_postgres_azure_ai(
        self,
        *,
        memory_id: UUID,
        content: str,
        embedding_model: str,
        content_hash: str | None,
        created_at: datetime,
        azure_openai_deployment: str,
        azure_openai_dimensions: int | None = None,
    ) -> MemoryEmbeddingRecord:
        raise NotImplementedError

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        raise NotImplementedError


class MemoryRelationRepository:
    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord:
        raise NotImplementedError

    def list_by_source_memory_id(
        self,
        source_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        raise NotImplementedError

    def list_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryRelationRecord, ...]:
        raise NotImplementedError

    def list_by_target_memory_id(
        self,
        target_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
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
    memory_relations: MemoryRelationRepository | None

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
            memory_summary_count = self._count_rows(uow, "memory_summaries")
            memory_summary_membership_count = self._count_rows(
                uow,
                "memory_summary_memberships",
            )
            memory_item_provenance_counts = self._count_memory_item_provenance(uow)
            structured_checkpoint_coverage = self._count_structured_checkpoint_coverage(
                uow,
                checkpoint_count=checkpoint_count,
            )
            (
                completion_summary_build_request_count,
                completion_summary_build_attempted_count,
                completion_summary_build_success_count,
                completion_summary_build_skipped_reason_counts,
            ) = self._count_completion_summary_build_outcomes(uow)
            completion_summary_build_request_rate_base = memory_item_provenance_counts.get(
                "workflow_complete_auto", 0
            )
            completion_summary_build_attempted_rate_base = memory_item_provenance_counts.get(
                "workflow_complete_auto", 0
            )
            completion_summary_build_success_rate_base = completion_summary_build_attempted_count
            completion_summary_build_request_rate = self._safe_ratio(
                completion_summary_build_request_count,
                completion_summary_build_request_rate_base,
            )
            completion_summary_build_attempted_rate = self._safe_ratio(
                completion_summary_build_attempted_count,
                completion_summary_build_attempted_rate_base,
            )
            completion_summary_build_success_rate = self._safe_ratio(
                completion_summary_build_success_count,
                completion_summary_build_success_rate_base,
            )

            derived_memory_item_count = memory_item_provenance_counts.get("derived", 0)
            age_summary_graph_ready_count = 1 if memory_summary_membership_count > 0 else 0
            age_summary_graph_stale_count = 0
            age_summary_graph_degraded_count = 0
            age_summary_graph_unknown_count = 1 if memory_summary_membership_count == 0 else 0
            (
                derived_memory_item_state,
                derived_memory_item_reason,
                derived_memory_graph_status,
            ) = self._derive_memory_item_state(
                derived_memory_item_count=derived_memory_item_count,
                memory_summary_count=memory_summary_count,
                memory_summary_membership_count=memory_summary_membership_count,
                age_summary_graph_ready_count=age_summary_graph_ready_count,
                age_summary_graph_stale_count=age_summary_graph_stale_count,
                age_summary_graph_degraded_count=age_summary_graph_degraded_count,
                age_summary_graph_unknown_count=age_summary_graph_unknown_count,
            )
            summary_backlog_count = max(episode_count - memory_summary_count, 0)
            interaction_memory_item_count = memory_item_provenance_counts.get("interaction", 0)
            file_work_memory_item_count = self._count_memory_items_with_file_work_metadata(uow)

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

            return WorkflowStats(
                workspace_count=workspace_count,
                workflow_status_counts=workflow_status_counts,
                attempt_status_counts=attempt_status_counts,
                verify_status_counts=verify_status_counts,
                checkpoint_count=checkpoint_count,
                episode_count=episode_count,
                memory_item_count=memory_item_count,
                memory_embedding_count=memory_embedding_count,
                checkpoint_auto_memory_recorded_count=memory_item_provenance_counts.get(
                    "workflow_checkpoint_auto",
                    0,
                ),
                checkpoint_auto_memory_skipped_count=max(
                    checkpoint_count
                    - memory_item_provenance_counts.get("workflow_checkpoint_auto", 0),
                    0,
                ),
                workflow_completion_auto_memory_recorded_count=memory_item_provenance_counts.get(
                    "workflow_complete_auto",
                    0,
                ),
                workflow_completion_auto_memory_skipped_count=max(
                    sum(workflow_status_counts.values())
                    - memory_item_provenance_counts.get("workflow_complete_auto", 0),
                    0,
                ),
                interaction_memory_item_count=interaction_memory_item_count,
                file_work_memory_item_count=file_work_memory_item_count,
                memory_summary_count=memory_summary_count,
                memory_summary_membership_count=memory_summary_membership_count,
                derived_memory_item_count=derived_memory_item_count,
                derived_memory_item_state=derived_memory_item_state,
                derived_memory_item_reason=derived_memory_item_reason,
                derived_memory_graph_status=derived_memory_graph_status,
                structured_checkpoint_coverage=structured_checkpoint_coverage,
                summary_backlog_count=summary_backlog_count,
                age_summary_graph_ready_count=age_summary_graph_ready_count,
                age_summary_graph_stale_count=age_summary_graph_stale_count,
                age_summary_graph_degraded_count=age_summary_graph_degraded_count,
                age_summary_graph_unknown_count=age_summary_graph_unknown_count,
                latest_workflow_updated_at=latest_workflow_updated_at,
                latest_checkpoint_created_at=latest_checkpoint_created_at,
                latest_verify_report_created_at=latest_verify_report_created_at,
                latest_episode_created_at=latest_episode_created_at,
                latest_memory_item_created_at=latest_memory_item_created_at,
                latest_memory_embedding_created_at=latest_memory_embedding_created_at,
                completion_summary_build_request_count=(completion_summary_build_request_count),
                completion_summary_build_attempted_count=(completion_summary_build_attempted_count),
                completion_summary_build_success_count=(completion_summary_build_success_count),
                completion_summary_build_request_rate_base=(
                    completion_summary_build_request_rate_base
                ),
                completion_summary_build_attempted_rate_base=(
                    completion_summary_build_attempted_rate_base
                ),
                completion_summary_build_success_rate_base=(
                    completion_summary_build_success_rate_base
                ),
                completion_summary_build_request_rate=(completion_summary_build_request_rate),
                completion_summary_build_attempted_rate=(completion_summary_build_attempted_rate),
                completion_summary_build_success_rate=(completion_summary_build_success_rate),
                completion_summary_build_skipped_reason_counts=(
                    completion_summary_build_skipped_reason_counts
                ),
            )

    def get_memory_stats(self) -> MemoryStats:
        with self._uow_factory() as uow:
            episode_count = self._count_rows(uow, "memory_episodes")
            memory_item_count = self._count_rows(uow, "memory_items")
            memory_embedding_count = self._count_rows(uow, "memory_embeddings")
            memory_relation_count = self._count_rows(uow, "memory_relations")
            memory_summary_count = self._count_rows(uow, "memory_summaries")
            memory_summary_membership_count = self._count_rows(
                uow,
                "memory_summary_memberships",
            )
            checkpoint_count = self._count_rows(uow, "workflow_checkpoints")
            workflow_count = self._count_rows(uow, "workflow_instances")

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

            derived_memory_item_count = memory_item_provenance_counts.get("derived", 0)
            age_summary_graph_ready_count = 1 if memory_summary_membership_count > 0 else 0
            age_summary_graph_stale_count = 0
            age_summary_graph_degraded_count = 0
            age_summary_graph_unknown_count = 1 if memory_summary_membership_count == 0 else 0
            (
                derived_memory_item_state,
                derived_memory_item_reason,
                derived_memory_graph_status,
            ) = self._derive_memory_item_state(
                derived_memory_item_count=derived_memory_item_count,
                memory_summary_count=memory_summary_count,
                memory_summary_membership_count=memory_summary_membership_count,
                age_summary_graph_ready_count=age_summary_graph_ready_count,
                age_summary_graph_stale_count=age_summary_graph_stale_count,
                age_summary_graph_degraded_count=age_summary_graph_degraded_count,
                age_summary_graph_unknown_count=age_summary_graph_unknown_count,
            )
            interaction_memory_item_count = memory_item_provenance_counts.get("interaction", 0)
            file_work_memory_item_count = self._count_memory_items_with_file_work_metadata(uow)
            latest_derived_memory_item_created_at = self._max_datetime_for_provenance(
                uow,
                provenance="derived",
            )
            (
                completion_summary_build_request_count,
                completion_summary_build_attempted_count,
                completion_summary_build_success_count,
                completion_summary_build_skipped_reason_counts,
            ) = self._count_completion_summary_build_outcomes(uow)
            completion_summary_build_request_rate_base = memory_item_provenance_counts.get(
                "workflow_complete_auto", 0
            )
            completion_summary_build_attempted_rate_base = memory_item_provenance_counts.get(
                "workflow_complete_auto", 0
            )
            completion_summary_build_success_rate_base = completion_summary_build_attempted_count
            completion_summary_build_request_rate = self._safe_ratio(
                completion_summary_build_request_count,
                completion_summary_build_request_rate_base,
            )
            completion_summary_build_attempted_rate = self._safe_ratio(
                completion_summary_build_attempted_count,
                completion_summary_build_attempted_rate_base,
            )
            completion_summary_build_success_rate = self._safe_ratio(
                completion_summary_build_success_count,
                completion_summary_build_success_rate_base,
            )

            return MemoryStats(
                episode_count=episode_count,
                memory_item_count=memory_item_count,
                memory_embedding_count=memory_embedding_count,
                memory_relation_count=memory_relation_count,
                memory_item_provenance_counts=memory_item_provenance_counts,
                checkpoint_auto_memory_recorded_count=memory_item_provenance_counts.get(
                    "workflow_checkpoint_auto",
                    0,
                ),
                checkpoint_auto_memory_skipped_count=max(
                    checkpoint_count
                    - memory_item_provenance_counts.get("workflow_checkpoint_auto", 0),
                    0,
                ),
                workflow_completion_auto_memory_recorded_count=memory_item_provenance_counts.get(
                    "workflow_complete_auto",
                    0,
                ),
                workflow_completion_auto_memory_skipped_count=max(
                    workflow_count - memory_item_provenance_counts.get("workflow_complete_auto", 0),
                    0,
                ),
                interaction_memory_item_count=interaction_memory_item_count,
                file_work_memory_item_count=file_work_memory_item_count,
                memory_summary_count=memory_summary_count,
                memory_summary_membership_count=memory_summary_membership_count,
                derived_memory_item_count=derived_memory_item_count,
                derived_memory_item_state=derived_memory_item_state,
                derived_memory_item_reason=derived_memory_item_reason,
                derived_memory_graph_status=derived_memory_graph_status,
                age_summary_graph_ready_count=age_summary_graph_ready_count,
                age_summary_graph_stale_count=age_summary_graph_stale_count,
                age_summary_graph_degraded_count=age_summary_graph_degraded_count,
                age_summary_graph_unknown_count=age_summary_graph_unknown_count,
                latest_episode_created_at=latest_episode_created_at,
                latest_memory_item_created_at=latest_memory_item_created_at,
                latest_memory_embedding_created_at=latest_memory_embedding_created_at,
                latest_memory_relation_created_at=latest_memory_relation_created_at,
                latest_derived_memory_item_created_at=latest_derived_memory_item_created_at,
                completion_summary_build_request_count=(completion_summary_build_request_count),
                completion_summary_build_attempted_count=(completion_summary_build_attempted_count),
                completion_summary_build_success_count=(completion_summary_build_success_count),
                completion_summary_build_request_rate_base=(
                    completion_summary_build_request_rate_base
                ),
                completion_summary_build_attempted_rate_base=(
                    completion_summary_build_attempted_rate_base
                ),
                completion_summary_build_success_rate_base=(
                    completion_summary_build_success_rate_base
                ),
                completion_summary_build_request_rate=(completion_summary_build_request_rate),
                completion_summary_build_attempted_rate=(completion_summary_build_attempted_rate),
                completion_summary_build_success_rate=(completion_summary_build_success_rate),
                completion_summary_build_skipped_reason_counts=(
                    completion_summary_build_skipped_reason_counts
                ),
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
                    uow.verify_reports.get_latest_by_attempt_id(latest_attempt.attempt_id)
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
                            latest_checkpoint.step_name if latest_checkpoint is not None else None
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
        return ()

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
                        "repo_url is already registered and explicit "
                        "workspace_id is required for updates",
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

            running = uow.workflow_instances.get_running_by_workspace_id(data.workspace_id)
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

    def create_checkpoint(self, data: CreateCheckpointInput) -> WorkflowCheckpointResult:
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

            checkpoint_warnings: list[ResumeIssue] = []
            auto_memory_details: dict[str, Any] | None = None

            workflow_memory_bridge = self._workflow_memory_bridge

            if workflow_memory_bridge is not None:
                try:
                    auto_memory_result = workflow_memory_bridge.record_checkpoint_memory(
                        workflow=workflow,
                        attempt=attempt,
                        checkpoint=checkpoint,
                        verify_report=verify_report,
                    )
                except Exception as exc:
                    checkpoint_warnings.append(
                        ResumeIssue(
                            code="checkpoint_auto_memory_recording_failed",
                            message=(
                                "workflow checkpoint succeeded but automatic memory "
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
                            "auto_memory_skipped_reason": "no_checkpoint_memory_source",
                        }
                    else:
                        auto_memory_details = dict(auto_memory_result.details)
                        if (
                            auto_memory_result.details.get("embedding_persistence_status")
                            == "failed"
                        ):
                            checkpoint_warnings.append(
                                ResumeIssue(
                                    code="checkpoint_auto_memory_embedding_failed",
                                    message=(
                                        "workflow checkpoint succeeded but automatic "
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
            return WorkflowCheckpointResult(
                checkpoint=checkpoint,
                workflow_instance=workflow,
                attempt=attempt,
                verify_report=verify_report,
                warnings=tuple(checkpoint_warnings),
                auto_memory_details=auto_memory_details,
            )

    def resume_workflow(self, data: ResumeWorkflowInput) -> WorkflowResume:
        debug_logging_enabled = logger.isEnabledFor(logging.DEBUG)
        started_at = utc_now()
        latency_warning_threshold_ms = self._resume_latency_warning_threshold_ms()
        if debug_logging_enabled:
            logger.debug(
                "resume_workflow started",
                extra={"workflow_instance_id": str(data.workflow_instance_id)},
            )
        with self._uow_factory() as uow:
            uow_enter_duration_ms = int(getattr(uow, "enter_duration_ms", 0) or 0)
            pool_checkout_duration_ms = int(getattr(uow, "pool_checkout_duration_ms", 0) or 0)
            session_setup_duration_ms = int(getattr(uow, "session_setup_duration_ms", 0) or 0)
            checkout_context_create_duration_ms = int(
                getattr(uow, "checkout_context_create_duration_ms", 0) or 0
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow unit of work enter complete",
                    extra={
                        "workflow_instance_id": str(data.workflow_instance_id),
                        "uow_enter_duration_ms": uow_enter_duration_ms,
                        "pool_checkout_duration_ms": pool_checkout_duration_ms,
                        "session_setup_duration_ms": session_setup_duration_ms,
                        "checkout_context_create_duration_ms": (
                            checkout_context_create_duration_ms
                        ),
                        "duration_ms": uow_enter_duration_ms,
                    },
                )

            workflow_lookup_started_at = utc_now()
            workflow = self._require_workflow(uow, data.workflow_instance_id)
            workflow_lookup_duration_ms = int(
                (utc_now() - workflow_lookup_started_at).total_seconds() * 1000
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow workflow lookup complete",
                    extra={
                        "workflow_instance_id": str(data.workflow_instance_id),
                        "duration_ms": workflow_lookup_duration_ms,
                    },
                )

            workspace_lookup_started_at = utc_now()
            workspace = self._require_workspace(uow, workflow.workspace_id)
            workspace_lookup_duration_ms = int(
                (utc_now() - workspace_lookup_started_at).total_seconds() * 1000
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow workspace lookup complete",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workspace_id": str(workspace.workspace_id),
                        "duration_ms": workspace_lookup_duration_ms,
                    },
                )

            attempt_lookup_started_at = utc_now()
            attempt = uow.workflow_attempts.get_running_by_workflow_id(
                workflow.workflow_instance_id
            )
            attempt_lookup_strategy = "running"
            if attempt is None:
                attempt = uow.workflow_attempts.get_latest_by_workflow_id(
                    workflow.workflow_instance_id
                )
                attempt_lookup_strategy = "latest"
            attempt_lookup_duration_ms = int(
                (utc_now() - attempt_lookup_started_at).total_seconds() * 1000
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow attempt lookup complete",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "attempt_lookup_strategy": attempt_lookup_strategy,
                        "attempt_id": (str(attempt.attempt_id) if attempt is not None else None),
                        "duration_ms": attempt_lookup_duration_ms,
                    },
                )

            checkpoint_lookup_started_at = utc_now()
            latest_checkpoint = uow.workflow_checkpoints.get_latest_by_workflow_id(
                workflow.workflow_instance_id
            )
            checkpoint_lookup_duration_ms = int(
                (utc_now() - checkpoint_lookup_started_at).total_seconds() * 1000
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow checkpoint lookup complete",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "checkpoint_id": (
                            str(latest_checkpoint.checkpoint_id)
                            if latest_checkpoint is not None
                            else None
                        ),
                        "duration_ms": checkpoint_lookup_duration_ms,
                    },
                )

            verify_report_lookup_started_at = utc_now()
            latest_verify_report = (
                uow.verify_reports.get_latest_by_attempt_id(attempt.attempt_id)
                if attempt is not None
                else None
            )
            verify_report_lookup_duration_ms = int(
                (utc_now() - verify_report_lookup_started_at).total_seconds() * 1000
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow verify report lookup complete",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "attempt_id": (str(attempt.attempt_id) if attempt is not None else None),
                        "verify_id": (
                            str(latest_verify_report.verify_id)
                            if latest_verify_report is not None
                            else None
                        ),
                        "duration_ms": verify_report_lookup_duration_ms,
                    },
                )

            response_assembly_started_at = utc_now()
            warnings = list(
                self._build_resume_warnings(
                    workflow,
                    attempt,
                    latest_checkpoint,
                    latest_verify_report,
                )
            )
            resumable_status = self._classify_resumable_status(
                workflow, attempt, latest_checkpoint, warnings
            )
            next_hint = self._derive_next_hint(
                workflow, attempt, latest_checkpoint, resumable_status
            )
            response_assembly_duration_ms = int(
                (utc_now() - response_assembly_started_at).total_seconds() * 1000
            )
            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow response assembly complete",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workspace_id": str(workspace.workspace_id),
                        "attempt_id": (str(attempt.attempt_id) if attempt is not None else None),
                        "checkpoint_id": (
                            str(latest_checkpoint.checkpoint_id)
                            if latest_checkpoint is not None
                            else None
                        ),
                        "warning_count": len(warnings),
                        "resumable_status": resumable_status.value,
                        "duration_ms": response_assembly_duration_ms,
                    },
                )

            duration_ms = int((utc_now() - started_at).total_seconds() * 1000)

            if debug_logging_enabled:
                logger.debug(
                    "resume_workflow complete",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workspace_id": str(workspace.workspace_id),
                        "attempt_id": (str(attempt.attempt_id) if attempt is not None else None),
                        "checkpoint_id": (
                            str(latest_checkpoint.checkpoint_id)
                            if latest_checkpoint is not None
                            else None
                        ),
                        "warning_count": len(warnings),
                        "resumable_status": resumable_status.value,
                        "uow_enter_duration_ms": uow_enter_duration_ms,
                        "pool_checkout_duration_ms": pool_checkout_duration_ms,
                        "session_setup_duration_ms": session_setup_duration_ms,
                        "checkout_context_create_duration_ms": (
                            checkout_context_create_duration_ms
                        ),
                        "workflow_lookup_duration_ms": workflow_lookup_duration_ms,
                        "workspace_lookup_duration_ms": workspace_lookup_duration_ms,
                        "attempt_lookup_duration_ms": attempt_lookup_duration_ms,
                        "checkpoint_lookup_duration_ms": checkpoint_lookup_duration_ms,
                        "verify_report_lookup_duration_ms": (verify_report_lookup_duration_ms),
                        "response_assembly_duration_ms": (response_assembly_duration_ms),
                        "duration_ms": duration_ms,
                    },
                )

            if duration_ms >= latency_warning_threshold_ms:
                logger.warning(
                    "resume_workflow latency exceeded warning threshold",
                    extra={
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workspace_id": str(workspace.workspace_id),
                        "attempt_id": (str(attempt.attempt_id) if attempt is not None else None),
                        "checkpoint_id": (
                            str(latest_checkpoint.checkpoint_id)
                            if latest_checkpoint is not None
                            else None
                        ),
                        "warning_count": len(warnings),
                        "resumable_status": resumable_status.value,
                        "uow_enter_duration_ms": uow_enter_duration_ms,
                        "pool_checkout_duration_ms": pool_checkout_duration_ms,
                        "session_setup_duration_ms": session_setup_duration_ms,
                        "checkout_context_create_duration_ms": (
                            checkout_context_create_duration_ms
                        ),
                        "workflow_lookup_duration_ms": workflow_lookup_duration_ms,
                        "workspace_lookup_duration_ms": workspace_lookup_duration_ms,
                        "attempt_lookup_duration_ms": attempt_lookup_duration_ms,
                        "checkpoint_lookup_duration_ms": checkpoint_lookup_duration_ms,
                        "verify_report_lookup_duration_ms": (verify_report_lookup_duration_ms),
                        "response_assembly_duration_ms": (response_assembly_duration_ms),
                        "duration_ms": duration_ms,
                        "warning_threshold_ms": latency_warning_threshold_ms,
                    },
                )

            return WorkflowResume(
                workspace=workspace,
                workflow_instance=workflow,
                attempt=attempt,
                latest_checkpoint=latest_checkpoint,
                latest_verify_report=latest_verify_report,
                resumable_status=resumable_status,
                warnings=tuple(warnings),
                next_hint=next_hint,
            )

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

            if workflow_memory_bridge is not None:
                try:
                    auto_memory_result = workflow_memory_bridge.record_workflow_completion_memory(
                        workflow=updated_workflow,
                        attempt=updated_attempt,
                        latest_checkpoint=latest_checkpoint,
                        verify_report=verify_report,
                        summary=data.summary,
                        failure_reason=data.failure_reason,
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
                            "auto_memory_skipped_reason": ("no_completion_summary_source"),
                        }
                    else:
                        auto_memory_details = dict(auto_memory_result.details)
                        if (
                            auto_memory_result.details.get("embedding_persistence_status")
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

    def _require_workflow(self, uow: UnitOfWork, workflow_instance_id: UUID) -> WorkflowInstance:
        workflow = uow.workflow_instances.get_by_id(workflow_instance_id)
        if workflow is None:
            workspace = uow.workspaces.get_by_id(workflow_instance_id)
            if workspace is not None:
                raise ValidationError(
                    "provided workflow_instance_id appears to be a workspace_id; "
                    "use workspace://{workspace_id}/resume or provide a real "
                    "workflow_instance_id",
                    details={
                        "workflow_instance_id": str(workflow_instance_id),
                        "workspace_id": str(workspace.workspace_id),
                    },
                )
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

        return ResumableStatus.RESUMABLE

    def _build_resume_warnings(
        self,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt | None,
        latest_checkpoint: WorkflowCheckpoint | None,
        latest_verify_report: VerifyReport | None,
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
            return (
                f"Resume from step '{latest_checkpoint.step_name}' "
                "using the latest checkpoint summary."
            )

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

    def _max_datetime_for_provenance(
        self,
        uow: UnitOfWork,
        *,
        provenance: str,
    ) -> datetime | None:
        repository = getattr(uow, "memory_items", None)
        if repository is None:
            return None

        records_by_id = getattr(repository, "_records_by_id", None)
        if records_by_id is None:
            values_by_id = getattr(repository, "_values_by_id", None)
            if isinstance(values_by_id, dict):
                records_by_id = values_by_id

        if isinstance(records_by_id, dict):
            timestamps = [
                created_at
                for record in records_by_id.values()
                if str(getattr(record, "provenance", "")) == provenance
                and isinstance((created_at := getattr(record, "created_at", None)), datetime)
            ]
            if not timestamps:
                return None
            return max(timestamps)

        max_method = getattr(repository, "max_datetime_for_provenance", None)
        if callable(max_method):
            value = max_method(provenance)
            return value if isinstance(value, datetime) or value is None else None

        list_by_workspace_id = getattr(repository, "list_by_workspace_id", None)
        workspaces = getattr(uow, "workspaces", None)
        list_workspaces = getattr(workspaces, "list_all", None) if workspaces is not None else None
        if callable(list_by_workspace_id) and callable(list_workspaces):
            timestamps: list[datetime] = []
            seen_memory_ids: set[UUID] = set()
            for workspace in list_workspaces(limit=1000):
                workspace_id = getattr(workspace, "workspace_id", None)
                if workspace_id is None:
                    continue
                for memory_item in list_by_workspace_id(workspace_id, limit=10000):
                    memory_id = getattr(memory_item, "memory_id", None)
                    if memory_id in seen_memory_ids:
                        continue
                    seen_memory_ids.add(memory_id)
                    if str(getattr(memory_item, "provenance", "")) != provenance:
                        continue
                    created_at = getattr(memory_item, "created_at", None)
                    if isinstance(created_at, datetime):
                        timestamps.append(created_at)
            if not timestamps:
                return None
            return max(timestamps)

        return None

    def _derive_memory_item_state(
        self,
        *,
        derived_memory_item_count: int,
        memory_summary_count: int,
        memory_summary_membership_count: int,
        age_summary_graph_ready_count: int,
        age_summary_graph_stale_count: int,
        age_summary_graph_degraded_count: int,
        age_summary_graph_unknown_count: int,
    ) -> tuple[str, str | None, str | None]:
        if derived_memory_item_count > 0:
            return (
                "ready",
                "derived memory items are present",
                "graph_ready" if age_summary_graph_ready_count > 0 else None,
            )

        if memory_summary_count == 0:
            return (
                "not_materialized",
                "no canonical summaries exist yet",
                None,
            )

        if memory_summary_membership_count == 0:
            return (
                "not_materialized",
                "no canonical summary memberships exist yet",
                None,
            )

        if age_summary_graph_degraded_count > 0:
            return (
                "degraded",
                "canonical summary state exists but the derived graph layer is degraded",
                "graph_degraded",
            )

        if age_summary_graph_stale_count > 0:
            return (
                "degraded",
                "canonical summary state exists but the derived graph layer is stale",
                "graph_stale",
            )

        if age_summary_graph_unknown_count > 0:
            return (
                "unknown",
                "canonical summary state exists but derived graph readiness is unknown",
                "unknown",
            )

        if age_summary_graph_ready_count > 0:
            return (
                "canonical_only",
                "canonical summary state exists but derived memory items are not materialized",
                "graph_ready",
            )

        return (
            "canonical_only",
            "canonical summary state exists but derived memory items are not materialized",
            None,
        )

    def _count_structured_checkpoint_coverage(
        self,
        uow: UnitOfWork,
        *,
        checkpoint_count: int,
    ) -> dict[str, int]:
        coverage_fields = (
            "current_objective",
            "next_intended_action",
            "verify_target",
            "resume_hint",
            "blocker_or_risk",
            "failure_guard",
            "root_cause",
            "recovery_pattern",
            "what_remains",
        )
        coverage = {field_name: 0 for field_name in coverage_fields}
        coverage["checkpoint_count"] = checkpoint_count

        if checkpoint_count <= 0:
            return coverage

        repository = getattr(uow, "workflow_checkpoints", None)
        if repository is None:
            return coverage

        checkpoints: tuple[WorkflowCheckpoint, ...] | None = None

        records_by_id = getattr(repository, "_records_by_id", None)
        if records_by_id is None:
            values_by_id = getattr(repository, "_values_by_id", None)
            if isinstance(values_by_id, dict):
                records_by_id = values_by_id

        if isinstance(records_by_id, dict):
            checkpoints = tuple(records_by_id.values())
        else:
            list_recent = getattr(repository, "list_recent", None)
            if callable(list_recent):
                checkpoints = tuple(list_recent(limit=checkpoint_count))

        if checkpoints is None:
            raise PersistenceError(
                "structured checkpoint coverage is not supported for workflow checkpoints"
            )

        for checkpoint in checkpoints:
            checkpoint_json = getattr(checkpoint, "checkpoint_json", None)
            if not isinstance(checkpoint_json, dict):
                continue
            for field_name in coverage_fields:
                raw_value = checkpoint_json.get(field_name)
                if isinstance(raw_value, str):
                    if raw_value.strip():
                        coverage[field_name] += 1
                elif raw_value is not None:
                    coverage[field_name] += 1

        return coverage

    def _count_completion_summary_build_outcomes(
        self,
        uow: UnitOfWork,
    ) -> tuple[int, int, int, dict[str, int]]:
        repository = getattr(uow, "memory_items", None)
        if repository is None:
            return 0, 0, 0, {}

        records: tuple[MemoryItem, ...] | None = None

        records_by_id = getattr(repository, "_records_by_id", None)
        if records_by_id is None:
            values_by_id = getattr(repository, "_values_by_id", None)
            if isinstance(values_by_id, dict):
                records_by_id = values_by_id

        if isinstance(records_by_id, dict):
            records = tuple(records_by_id.values())
        else:
            list_by_workspace_id = getattr(repository, "list_by_workspace_id", None)
            workspaces = getattr(uow, "workspaces", None)
            list_workspaces = (
                getattr(workspaces, "list_all", None) if workspaces is not None else None
            )
            if callable(list_by_workspace_id) and callable(list_workspaces):
                collected_records: list[MemoryItem] = []
                seen_memory_ids: set[UUID] = set()
                for workspace in list_workspaces(limit=1000):
                    workspace_id = getattr(workspace, "workspace_id", None)
                    if workspace_id is None:
                        continue
                    for memory_item in list_by_workspace_id(workspace_id, limit=10000):
                        memory_id = getattr(memory_item, "memory_id", None)
                        if memory_id in seen_memory_ids:
                            continue
                        seen_memory_ids.add(memory_id)
                        collected_records.append(memory_item)
                records = tuple(collected_records)

        if records is None:
            return 0, 0, 0, {}

        request_count = 0
        attempted_count = 0
        success_count = 0
        skipped_reason_counts: dict[str, int] = {}

        for memory_item in records:
            if getattr(memory_item, "provenance", None) != "workflow_complete_auto":
                continue
            metadata = getattr(memory_item, "metadata", None)
            if not isinstance(metadata, dict):
                continue

            if bool(metadata.get("summary_build_requested", False)):
                request_count += 1
            if bool(metadata.get("summary_build_attempted", False)):
                attempted_count += 1
            if bool(metadata.get("summary_build_succeeded", False)):
                success_count += 1

            skipped_reason = metadata.get("summary_build_skipped_reason")
            if isinstance(skipped_reason, str) and skipped_reason.strip():
                skipped_reason_counts[skipped_reason] = (
                    skipped_reason_counts.get(skipped_reason, 0) + 1
                )

        return (
            request_count,
            attempted_count,
            success_count,
            skipped_reason_counts,
        )

    @staticmethod
    def _safe_ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator

    def _count_memory_items_with_file_work_metadata(self, uow: Any) -> int:
        memory_items = getattr(uow, "memory_items", None)
        if memory_items is None:
            return 0

        count_all_with_metadata = getattr(
            memory_items,
            "count_with_any_file_work_metadata",
            None,
        )
        if callable(count_all_with_metadata):
            return int(count_all_with_metadata())

        list_by_workspace_id = getattr(memory_items, "list_by_workspace_id", None)
        workflow_instances = getattr(uow, "workflow_instances", None)
        if callable(list_by_workspace_id) and workflow_instances is not None:
            count = 0
            seen_memory_ids: set[UUID] = set()
            workspaces = getattr(uow, "workspaces", None)
            list_workspaces = (
                getattr(workspaces, "list_all", None) if workspaces is not None else None
            )
            if callable(list_workspaces):
                workspace_records = list_workspaces(limit=1000)
                for workspace in workspace_records:
                    workspace_id = getattr(workspace, "workspace_id", None)
                    if workspace_id is None:
                        continue
                    memory_items_for_workspace = list_by_workspace_id(workspace_id, limit=10000)
                    for memory_item in memory_items_for_workspace:
                        memory_id = getattr(memory_item, "memory_id", None)
                        if memory_id in seen_memory_ids:
                            continue
                        metadata = getattr(memory_item, "metadata", {}) or {}
                        if any(
                            isinstance(metadata.get(field_name), str)
                            and metadata.get(field_name, "").strip()
                            for field_name in (
                                "file_name",
                                "file_path",
                                "file_operation",
                                "purpose",
                            )
                        ):
                            seen_memory_ids.add(memory_id)
                            count += 1
                return count

        return 0

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

    def _resume_latency_warning_threshold_ms(self) -> int:
        configured_threshold = getattr(
            self,
            "_resume_latency_warning_threshold_ms_override",
            None,
        )
        if isinstance(configured_threshold, int) and configured_threshold > 0:
            return configured_threshold
        return _RESUME_LATENCY_WARNING_THRESHOLD_MS

    def _validate_step_name(self, step_name: str) -> None:
        if not step_name.strip():
            raise ValidationError("step_name must not be empty")
