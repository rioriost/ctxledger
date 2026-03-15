from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ctxledger.db.postgres import (
    PostgresDatabaseHealthChecker,
    PostgresUnitOfWork,
    build_postgres_uow_factory,
)
from ctxledger.workflow.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryItemRecord,
    MemoryItemRepository,
    ProjectionArtifactType,
    ProjectionFailureInfo,
    ProjectionFailureRepository,
    ProjectionInfo,
    ProjectionStateRepository,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    UnitOfWork,
    VerifyReport,
    VerifyReportRepository,
    WorkflowAttempt,
    WorkflowAttemptRepository,
    WorkflowCheckpoint,
    WorkflowCheckpointRepository,
    WorkflowInstance,
    WorkflowInstanceRepository,
    Workspace,
    WorkspaceRepository,
    utc_now,
)


class InMemoryWorkspaceRepository(WorkspaceRepository):
    def __init__(
        self,
        workspaces_by_id: dict[object, Workspace],
        workspaces_by_canonical_path: dict[str, object],
    ) -> None:
        self._workspaces_by_id = workspaces_by_id
        self._workspaces_by_canonical_path = workspaces_by_canonical_path

    def get_by_id(self, workspace_id: object) -> Workspace | None:
        return self._workspaces_by_id.get(workspace_id)

    def get_by_canonical_path(self, canonical_path: str) -> Workspace | None:
        workspace_id = self._workspaces_by_canonical_path.get(canonical_path)
        if workspace_id is None:
            return None
        return self._workspaces_by_id.get(workspace_id)

    def get_by_repo_url(self, repo_url: str) -> list[Workspace]:
        return [
            workspace
            for workspace in self._workspaces_by_id.values()
            if workspace.repo_url == repo_url
        ]

    def create(self, workspace: Workspace) -> Workspace:
        self._workspaces_by_id[workspace.workspace_id] = workspace
        self._workspaces_by_canonical_path[workspace.canonical_path] = (
            workspace.workspace_id
        )
        return workspace

    def update(self, workspace: Workspace) -> Workspace:
        existing = self._workspaces_by_id.get(workspace.workspace_id)
        if existing is not None and existing.canonical_path != workspace.canonical_path:
            self._workspaces_by_canonical_path.pop(existing.canonical_path, None)

        self._workspaces_by_id[workspace.workspace_id] = workspace
        self._workspaces_by_canonical_path[workspace.canonical_path] = (
            workspace.workspace_id
        )
        return workspace


class InMemoryWorkflowInstanceRepository(WorkflowInstanceRepository):
    def __init__(self, workflows_by_id: dict[object, WorkflowInstance]) -> None:
        self._workflows_by_id = workflows_by_id

    def get_by_id(self, workflow_instance_id: object) -> WorkflowInstance | None:
        return self._workflows_by_id.get(workflow_instance_id)

    def get_running_by_workspace_id(
        self, workspace_id: object
    ) -> WorkflowInstance | None:
        workflows = [
            workflow
            for workflow in self._workflows_by_id.values()
            if workflow.workspace_id == workspace_id
            and workflow.status.value == "running"
        ]
        workflows.sort(key=lambda workflow: workflow.created_at, reverse=True)
        return workflows[0] if workflows else None

    def get_latest_by_workspace_id(
        self, workspace_id: object
    ) -> WorkflowInstance | None:
        workflows = [
            workflow
            for workflow in self._workflows_by_id.values()
            if workflow.workspace_id == workspace_id
        ]
        workflows.sort(key=lambda workflow: workflow.updated_at, reverse=True)
        return workflows[0] if workflows else None

    def list_by_workspace_id(
        self,
        workspace_id: object,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        workflows = [
            workflow
            for workflow in self._workflows_by_id.values()
            if workflow.workspace_id == workspace_id
        ]
        workflows.sort(key=lambda workflow: workflow.updated_at, reverse=True)
        return tuple(workflows[:limit])

    def list_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        workflows = [
            workflow
            for workflow in self._workflows_by_id.values()
            if workflow.ticket_id == ticket_id
        ]
        workflows.sort(key=lambda workflow: workflow.updated_at, reverse=True)
        return tuple(workflows[:limit])

    def list_recent(
        self,
        *,
        limit: int,
        status: str | None = None,
        workspace_id: object | None = None,
        ticket_id: str | None = None,
    ) -> tuple[WorkflowInstance, ...]:
        workflows = list(self._workflows_by_id.values())

        if status is not None:
            workflows = [
                workflow for workflow in workflows if workflow.status.value == status
            ]
        if workspace_id is not None:
            workflows = [
                workflow
                for workflow in workflows
                if workflow.workspace_id == workspace_id
            ]
        if ticket_id is not None:
            workflows = [
                workflow for workflow in workflows if workflow.ticket_id == ticket_id
            ]

        workflows.sort(
            key=lambda workflow: (workflow.updated_at, workflow.created_at),
            reverse=True,
        )
        return tuple(workflows[:limit])

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self._workflows_by_id[workflow.workflow_instance_id] = workflow
        return workflow

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self._workflows_by_id[workflow.workflow_instance_id] = workflow
        return workflow


class InMemoryWorkflowAttemptRepository(WorkflowAttemptRepository):
    def __init__(self, attempts_by_id: dict[object, WorkflowAttempt]) -> None:
        self._attempts_by_id = attempts_by_id

    def get_by_id(self, attempt_id: object) -> WorkflowAttempt | None:
        return self._attempts_by_id.get(attempt_id)

    def get_running_by_workflow_id(
        self, workflow_instance_id: object
    ) -> WorkflowAttempt | None:
        attempts = [
            attempt
            for attempt in self._attempts_by_id.values()
            if (
                attempt.workflow_instance_id == workflow_instance_id
                and attempt.status.value == "running"
            )
        ]
        attempts.sort(key=lambda attempt: attempt.started_at, reverse=True)
        return attempts[0] if attempts else None

    def get_latest_by_workflow_id(
        self, workflow_instance_id: object
    ) -> WorkflowAttempt | None:
        attempts = [
            attempt
            for attempt in self._attempts_by_id.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        attempts.sort(
            key=lambda attempt: (attempt.attempt_number, attempt.started_at),
            reverse=True,
        )
        return attempts[0] if attempts else None

    def get_next_attempt_number(self, workflow_instance_id: object) -> int:
        attempts = [
            attempt.attempt_number
            for attempt in self._attempts_by_id.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        return (max(attempts) + 1) if attempts else 1

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self._attempts_by_id[attempt.attempt_id] = attempt
        return attempt

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self._attempts_by_id[attempt.attempt_id] = attempt
        return attempt


class InMemoryWorkflowCheckpointRepository(WorkflowCheckpointRepository):
    def __init__(self, checkpoints_by_id: dict[object, WorkflowCheckpoint]) -> None:
        self._checkpoints_by_id = checkpoints_by_id

    def get_latest_by_workflow_id(
        self, workflow_instance_id: object
    ) -> WorkflowCheckpoint | None:
        checkpoints = [
            checkpoint
            for checkpoint in self._checkpoints_by_id.values()
            if checkpoint.workflow_instance_id == workflow_instance_id
        ]
        checkpoints.sort(key=lambda checkpoint: checkpoint.created_at, reverse=True)
        return checkpoints[0] if checkpoints else None

    def get_latest_by_attempt_id(self, attempt_id: object) -> WorkflowCheckpoint | None:
        checkpoints = [
            checkpoint
            for checkpoint in self._checkpoints_by_id.values()
            if checkpoint.attempt_id == attempt_id
        ]
        checkpoints.sort(key=lambda checkpoint: checkpoint.created_at, reverse=True)
        return checkpoints[0] if checkpoints else None

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self._checkpoints_by_id[checkpoint.checkpoint_id] = checkpoint
        return checkpoint


class InMemoryVerifyReportRepository(VerifyReportRepository):
    def __init__(self, verify_reports_by_id: dict[object, VerifyReport]) -> None:
        self._verify_reports_by_id = verify_reports_by_id

    def get_latest_by_attempt_id(self, attempt_id: object) -> VerifyReport | None:
        verify_reports = [
            verify_report
            for verify_report in self._verify_reports_by_id.values()
            if verify_report.attempt_id == attempt_id
        ]
        verify_reports.sort(key=lambda report: report.created_at, reverse=True)
        return verify_reports[0] if verify_reports else None

    def create(self, verify_report: VerifyReport) -> VerifyReport:
        self._verify_reports_by_id[verify_report.verify_id] = verify_report
        return verify_report


class InMemoryMemoryEpisodeRepository:
    def __init__(self, episodes_by_id: dict[object, EpisodeRecord]) -> None:
        self._episodes_by_id = episodes_by_id

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        self._episodes_by_id[episode.episode_id] = episode
        return episode

    def list_by_workflow_id(
        self,
        workflow_instance_id: object,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        episodes = [
            episode
            for episode in self._episodes_by_id.values()
            if episode.workflow_instance_id == workflow_instance_id
        ]
        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])


class InMemoryMemoryItemRepository(MemoryItemRepository):
    def __init__(self, memory_items_by_id: dict[object, MemoryItemRecord]) -> None:
        self._memory_items_by_id = memory_items_by_id

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        self._memory_items_by_id[memory_item.memory_id] = memory_item
        return memory_item

    def list_by_workspace_id(
        self,
        workspace_id: object,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        memory_items = [
            memory_item
            for memory_item in self._memory_items_by_id.values()
            if memory_item.workspace_id == workspace_id
        ]
        memory_items.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(memory_items[:limit])

    def list_by_episode_id(
        self,
        episode_id: object,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        memory_items = [
            memory_item
            for memory_item in self._memory_items_by_id.values()
            if memory_item.episode_id == episode_id
        ]
        memory_items.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(memory_items[:limit])

    def count_by_provenance(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for memory_item in self._memory_items_by_id.values():
            counts[memory_item.provenance] = counts.get(memory_item.provenance, 0) + 1
        return counts


class InMemoryMemoryEmbeddingRepository(MemoryEmbeddingRepository):
    def __init__(
        self,
        memory_embeddings_by_id: dict[object, MemoryEmbeddingRecord],
    ) -> None:
        self._memory_embeddings_by_id = memory_embeddings_by_id

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        self._memory_embeddings_by_id[embedding.memory_embedding_id] = embedding
        return embedding

    def list_by_memory_id(
        self,
        memory_id: object,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        embeddings = [
            embedding
            for embedding in self._memory_embeddings_by_id.values()
            if embedding.memory_id == memory_id
        ]
        embeddings.sort(key=lambda embedding: embedding.created_at, reverse=True)
        return tuple(embeddings[:limit])


class InMemoryProjectionStateRepository(ProjectionStateRepository):
    def __init__(
        self,
        projection_states_by_key: dict[
            tuple[object, object, ProjectionArtifactType], ProjectionInfo
        ],
    ) -> None:
        self._projection_states_by_key = projection_states_by_key

    def get_resume_projections(
        self,
        workspace_id: object,
        workflow_instance_id: object,
    ) -> tuple[ProjectionInfo, ...]:
        candidates = [
            projection
            for (
                candidate_workspace_id,
                candidate_workflow_instance_id,
                _,
            ), projection in self._projection_states_by_key.items()
            if candidate_workspace_id == workspace_id
            and candidate_workflow_instance_id == workflow_instance_id
        ]
        candidates.sort(
            key=lambda projection: (
                projection.last_canonical_update_at is not None,
                projection.last_canonical_update_at,
                projection.last_successful_write_at is not None,
                projection.last_successful_write_at,
                projection.projection_type.value,
            ),
            reverse=True,
        )
        return tuple(candidates)

    def record_resume_projection(self, projection: RecordProjectionStateInput) -> None:
        key = (
            projection.workspace_id,
            projection.workflow_instance_id,
            projection.projection_type,
        )
        existing = self._projection_states_by_key.get(key)
        open_failure_count = existing.open_failure_count if existing is not None else 0
        self._projection_states_by_key[key] = ProjectionInfo(
            projection_type=projection.projection_type,
            status=projection.status,
            target_path=projection.target_path,
            last_successful_write_at=projection.last_successful_write_at,
            last_canonical_update_at=projection.last_canonical_update_at,
            open_failure_count=open_failure_count,
        )

    def set_resume_projection(
        self,
        workspace_id: object,
        workflow_instance_id: object,
        projection: ProjectionInfo,
    ) -> None:
        self._projection_states_by_key[
            (workspace_id, workflow_instance_id, projection.projection_type)
        ] = projection


class InMemoryProjectionFailureRepository(ProjectionFailureRepository):
    def __init__(
        self,
        failures_by_key: dict[
            tuple[object, object, ProjectionArtifactType], list[ProjectionFailureInfo]
        ],
        projection_states_by_key: dict[
            tuple[object, object, ProjectionArtifactType], ProjectionInfo
        ],
    ) -> None:
        self._failures_by_key = failures_by_key
        self._projection_states_by_key = projection_states_by_key

    def get_open_failures_by_workflow_id(
        self,
        workspace_id: object,
        workflow_instance_id: object,
    ) -> list[ProjectionFailureInfo]:
        failures: list[ProjectionFailureInfo] = []
        for (
            candidate_workspace_id,
            candidate_workflow_instance_id,
            _,
        ), candidate_failures in self._failures_by_key.items():
            if (
                candidate_workspace_id == workspace_id
                and candidate_workflow_instance_id == workflow_instance_id
            ):
                failures.extend(
                    failure
                    for failure in candidate_failures
                    if failure.status == "open"
                )
        return list(failures)

    def get_closed_failures_by_workflow_id(
        self,
        workspace_id: object,
        workflow_instance_id: object,
    ) -> list[ProjectionFailureInfo]:
        failures: list[ProjectionFailureInfo] = []
        for (
            candidate_workspace_id,
            candidate_workflow_instance_id,
            _,
        ), candidate_failures in self._failures_by_key.items():
            if (
                candidate_workspace_id == workspace_id
                and candidate_workflow_instance_id == workflow_instance_id
            ):
                failures.extend(
                    failure
                    for failure in candidate_failures
                    if failure.status in {"resolved", "ignored"}
                )
        return list(failures)

    def list_failures(
        self,
        *,
        limit: int,
        status: str | None = None,
        open_only: bool = False,
    ) -> tuple[ProjectionFailureInfo, ...]:
        failures: list[ProjectionFailureInfo] = []
        for candidate_failures in self._failures_by_key.values():
            failures.extend(candidate_failures)

        if open_only:
            failures = [failure for failure in failures if failure.status == "open"]
        elif status is not None:
            failures = [failure for failure in failures if failure.status == status]

        failures.sort(
            key=lambda failure: (
                failure.occurred_at is not None,
                failure.occurred_at,
                failure.projection_type.value,
                failure.target_path,
            ),
            reverse=True,
        )
        return tuple(failures[:limit])

    def record_resume_projection_failure(
        self,
        failure: RecordProjectionFailureInput,
    ) -> ProjectionFailureInfo:
        key = (
            failure.workspace_id,
            failure.workflow_instance_id,
            failure.projection_type,
        )
        existing = self._failures_by_key.get(key, [])
        failure_info = ProjectionFailureInfo(
            projection_type=failure.projection_type,
            error_code=failure.error_code,
            error_message=failure.error_message,
            target_path=failure.target_path,
            attempt_id=failure.attempt_id,
            occurred_at=utc_now(),
            open_failure_count=len(existing) + 1,
            retry_count=len(existing),
            status="open",
        )
        existing.append(failure_info)
        self._failures_by_key[key] = existing

        current_projection = self._projection_states_by_key.get(key)
        if current_projection is not None:
            self._projection_states_by_key[key] = ProjectionInfo(
                projection_type=current_projection.projection_type,
                status=current_projection.status,
                target_path=current_projection.target_path,
                last_successful_write_at=current_projection.last_successful_write_at,
                last_canonical_update_at=current_projection.last_canonical_update_at,
                open_failure_count=len(existing),
            )

        return failure_info

    def resolve_resume_projection_failures(
        self,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        resolved_count = 0

        projection_types = (
            (projection_type,)
            if projection_type is not None
            else (
                ProjectionArtifactType.RESUME_JSON,
                ProjectionArtifactType.RESUME_MD,
            )
        )

        for candidate_projection_type in projection_types:
            key = (
                workspace_id,
                workflow_instance_id,
                candidate_projection_type,
            )
            existing = self._failures_by_key.get(key, [])
            resolved_count += len(existing)

            if existing:
                resolved_at = utc_now()
                self._failures_by_key[key] = [
                    ProjectionFailureInfo(
                        projection_type=failure.projection_type,
                        error_code=failure.error_code,
                        error_message=failure.error_message,
                        target_path=failure.target_path,
                        attempt_id=failure.attempt_id,
                        occurred_at=failure.occurred_at,
                        resolved_at=resolved_at,
                        open_failure_count=failure.open_failure_count,
                        retry_count=failure.retry_count,
                        status="resolved",
                    )
                    for failure in existing
                ]

            current_projection = self._projection_states_by_key.get(key)
            if current_projection is not None:
                self._projection_states_by_key[key] = ProjectionInfo(
                    projection_type=current_projection.projection_type,
                    status=current_projection.status,
                    target_path=current_projection.target_path,
                    last_successful_write_at=current_projection.last_successful_write_at,
                    last_canonical_update_at=current_projection.last_canonical_update_at,
                    open_failure_count=0,
                )

        return resolved_count

    def ignore_resume_projection_failures(
        self,
        workspace_id: object,
        workflow_instance_id: object,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        ignored_count = 0

        projection_types = (
            (projection_type,)
            if projection_type is not None
            else (
                ProjectionArtifactType.RESUME_JSON,
                ProjectionArtifactType.RESUME_MD,
            )
        )

        for candidate_projection_type in projection_types:
            key = (
                workspace_id,
                workflow_instance_id,
                candidate_projection_type,
            )
            existing = self._failures_by_key.get(key, [])
            ignored_count += len(existing)

            if existing:
                resolved_at = utc_now()
                self._failures_by_key[key] = [
                    ProjectionFailureInfo(
                        projection_type=failure.projection_type,
                        error_code=failure.error_code,
                        error_message=failure.error_message,
                        target_path=failure.target_path,
                        attempt_id=failure.attempt_id,
                        occurred_at=failure.occurred_at,
                        resolved_at=resolved_at,
                        open_failure_count=failure.open_failure_count,
                        retry_count=failure.retry_count,
                        status="ignored",
                    )
                    for failure in existing
                ]

            current_projection = self._projection_states_by_key.get(key)
            if current_projection is not None:
                self._projection_states_by_key[key] = ProjectionInfo(
                    projection_type=current_projection.projection_type,
                    status=current_projection.status,
                    target_path=current_projection.target_path,
                    last_successful_write_at=current_projection.last_successful_write_at,
                    last_canonical_update_at=current_projection.last_canonical_update_at,
                    open_failure_count=0,
                )

        return ignored_count


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(
        self,
        *,
        workspaces_by_id: dict[object, Workspace] | None = None,
        workspaces_by_canonical_path: dict[str, object] | None = None,
        workflows_by_id: dict[object, WorkflowInstance] | None = None,
        attempts_by_id: dict[object, WorkflowAttempt] | None = None,
        checkpoints_by_id: dict[object, WorkflowCheckpoint] | None = None,
        verify_reports_by_id: dict[object, VerifyReport] | None = None,
        episodes_by_id: dict[object, EpisodeRecord] | None = None,
        memory_items_by_id: dict[object, MemoryItemRecord] | None = None,
        memory_embeddings_by_id: dict[object, MemoryEmbeddingRecord] | None = None,
        projection_states_by_key: dict[
            tuple[object, object, ProjectionArtifactType], ProjectionInfo
        ]
        | None = None,
        projection_failures_by_key: dict[
            tuple[object, object, ProjectionArtifactType], list[ProjectionFailureInfo]
        ]
        | None = None,
    ) -> None:
        self._workspaces_by_id = (
            workspaces_by_id if workspaces_by_id is not None else {}
        )
        self._workspaces_by_canonical_path = (
            workspaces_by_canonical_path
            if workspaces_by_canonical_path is not None
            else {}
        )
        self._workflows_by_id = workflows_by_id if workflows_by_id is not None else {}
        self._attempts_by_id = attempts_by_id if attempts_by_id is not None else {}
        self._checkpoints_by_id = (
            checkpoints_by_id if checkpoints_by_id is not None else {}
        )
        self._verify_reports_by_id = (
            verify_reports_by_id if verify_reports_by_id is not None else {}
        )
        self._episodes_by_id = episodes_by_id if episodes_by_id is not None else {}
        self._memory_items_by_id = (
            memory_items_by_id if memory_items_by_id is not None else {}
        )
        self._memory_embeddings_by_id = (
            memory_embeddings_by_id if memory_embeddings_by_id is not None else {}
        )
        self._projection_states_by_key = (
            projection_states_by_key if projection_states_by_key is not None else {}
        )
        self._projection_failures_by_key = (
            projection_failures_by_key if projection_failures_by_key is not None else {}
        )

        self._committed = False
        self._rolled_back = False

        self.workspaces = InMemoryWorkspaceRepository(
            self._workspaces_by_id,
            self._workspaces_by_canonical_path,
        )
        self.workflow_instances = InMemoryWorkflowInstanceRepository(
            self._workflows_by_id
        )
        self.workflow_attempts = InMemoryWorkflowAttemptRepository(self._attempts_by_id)
        self.workflow_checkpoints = InMemoryWorkflowCheckpointRepository(
            self._checkpoints_by_id
        )
        self.verify_reports = InMemoryVerifyReportRepository(self._verify_reports_by_id)
        self.memory_episodes = InMemoryMemoryEpisodeRepository(self._episodes_by_id)
        self.memory_items = InMemoryMemoryItemRepository(self._memory_items_by_id)
        self.memory_embeddings = InMemoryMemoryEmbeddingRepository(
            self._memory_embeddings_by_id
        )
        self.projection_states = InMemoryProjectionStateRepository(
            self._projection_states_by_key
        )
        self.projection_failures = InMemoryProjectionFailureRepository(
            self._projection_failures_by_key,
            self._projection_states_by_key,
        )

    def __enter__(self) -> InMemoryUnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None and not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._rolled_back = True


@dataclass(slots=True)
class InMemoryStore:
    workspaces_by_id: dict[object, Workspace]
    workspaces_by_canonical_path: dict[str, object]
    workflows_by_id: dict[object, WorkflowInstance]
    attempts_by_id: dict[object, WorkflowAttempt]
    checkpoints_by_id: dict[object, WorkflowCheckpoint]
    verify_reports_by_id: dict[object, VerifyReport]
    episodes_by_id: dict[object, EpisodeRecord]
    memory_items_by_id: dict[object, MemoryItemRecord]
    memory_embeddings_by_id: dict[object, MemoryEmbeddingRecord]
    projection_states_by_key: dict[
        tuple[object, object, ProjectionArtifactType], ProjectionInfo
    ]
    projection_failures_by_key: dict[
        tuple[object, object, ProjectionArtifactType], list[ProjectionFailureInfo]
    ]

    @classmethod
    def create(cls) -> InMemoryStore:
        return cls(
            workspaces_by_id={},
            workspaces_by_canonical_path={},
            workflows_by_id={},
            attempts_by_id={},
            checkpoints_by_id={},
            verify_reports_by_id={},
            episodes_by_id={},
            memory_items_by_id={},
            memory_embeddings_by_id={},
            projection_states_by_key={},
            projection_failures_by_key={},
        )

    def snapshot(self) -> InMemoryStore:
        return InMemoryStore(
            workspaces_by_id=dict(self.workspaces_by_id),
            workspaces_by_canonical_path=dict(self.workspaces_by_canonical_path),
            workflows_by_id=dict(self.workflows_by_id),
            attempts_by_id=dict(self.attempts_by_id),
            checkpoints_by_id=dict(self.checkpoints_by_id),
            verify_reports_by_id=dict(self.verify_reports_by_id),
            episodes_by_id=dict(self.episodes_by_id),
            memory_items_by_id=dict(self.memory_items_by_id),
            memory_embeddings_by_id=dict(self.memory_embeddings_by_id),
            projection_states_by_key=dict(self.projection_states_by_key),
            projection_failures_by_key={
                key: list(value)
                for key, value in self.projection_failures_by_key.items()
            },
        )


def build_in_memory_uow_factory(
    store: InMemoryStore | None = None,
) -> Callable[[], InMemoryUnitOfWork]:
    backing_store = store or InMemoryStore.create()

    def _factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(
            workspaces_by_id=backing_store.workspaces_by_id,
            workspaces_by_canonical_path=backing_store.workspaces_by_canonical_path,
            workflows_by_id=backing_store.workflows_by_id,
            attempts_by_id=backing_store.attempts_by_id,
            checkpoints_by_id=backing_store.checkpoints_by_id,
            verify_reports_by_id=backing_store.verify_reports_by_id,
            episodes_by_id=backing_store.episodes_by_id,
            memory_items_by_id=backing_store.memory_items_by_id,
            memory_embeddings_by_id=backing_store.memory_embeddings_by_id,
            projection_states_by_key=backing_store.projection_states_by_key,
            projection_failures_by_key=backing_store.projection_failures_by_key,
        )

    return _factory


__all__ = [
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryProjectionFailureRepository,
    InMemoryProjectionStateRepository,
    InMemoryStore,
    "InMemoryUnitOfWork",
    "InMemoryVerifyReportRepository",
    "InMemoryWorkflowAttemptRepository",
    "InMemoryWorkflowCheckpointRepository",
    "InMemoryWorkflowInstanceRepository",
    "InMemoryWorkspaceRepository",
    "build_in_memory_uow_factory",
    "PostgresDatabaseHealthChecker",
    "PostgresUnitOfWork",
]
