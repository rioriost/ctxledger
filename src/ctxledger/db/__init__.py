from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ctxledger.db.postgres import (
    PostgresDatabaseHealthChecker,
    PostgresUnitOfWork,
)
from ctxledger.memory.types import MemorySummaryMembershipRecord, MemorySummaryRecord
from ctxledger.workflow.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryItemRecord,
    MemoryItemRepository,
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
)


def _latest_or_none(
    items: Any,
    *,
    key: Callable[[Any], Any],
) -> Any | None:
    sorted_items = sorted(items, key=key, reverse=True)
    return sorted_items[0] if sorted_items else None


def _sorted_limited(
    items: Any,
    *,
    key: Callable[[Any], Any],
    limit: int,
) -> tuple[Any, ...]:
    return tuple(sorted(items, key=key, reverse=True)[:limit])


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
        self._workspaces_by_canonical_path[workspace.canonical_path] = workspace.workspace_id
        return workspace

    def update(self, workspace: Workspace) -> Workspace:
        existing = self._workspaces_by_id.get(workspace.workspace_id)
        if existing is not None and existing.canonical_path != workspace.canonical_path:
            self._workspaces_by_canonical_path.pop(existing.canonical_path, None)

        self._workspaces_by_id[workspace.workspace_id] = workspace
        self._workspaces_by_canonical_path[workspace.canonical_path] = workspace.workspace_id
        return workspace


class InMemoryWorkflowInstanceRepository(WorkflowInstanceRepository):
    def __init__(self, workflows_by_id: dict[object, WorkflowInstance]) -> None:
        self._workflows_by_id = workflows_by_id

    def get_by_id(self, workflow_instance_id: object) -> WorkflowInstance | None:
        return self._workflows_by_id.get(workflow_instance_id)

    def get_running_by_workspace_id(self, workspace_id: object) -> WorkflowInstance | None:
        return _latest_or_none(
            (
                workflow
                for workflow in self._workflows_by_id.values()
                if workflow.workspace_id == workspace_id and workflow.status.value == "running"
            ),
            key=lambda workflow: workflow.created_at,
        )

    def get_latest_by_workspace_id(self, workspace_id: object) -> WorkflowInstance | None:
        return _latest_or_none(
            (
                workflow
                for workflow in self._workflows_by_id.values()
                if workflow.workspace_id == workspace_id
            ),
            key=lambda workflow: workflow.updated_at,
        )

    def list_by_workspace_id(
        self,
        workspace_id: object,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        return _sorted_limited(
            (
                workflow
                for workflow in self._workflows_by_id.values()
                if workflow.workspace_id == workspace_id
            ),
            key=lambda workflow: workflow.updated_at,
            limit=limit,
        )

    def list_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[WorkflowInstance, ...]:
        return _sorted_limited(
            (
                workflow
                for workflow in self._workflows_by_id.values()
                if workflow.ticket_id == ticket_id
            ),
            key=lambda workflow: workflow.updated_at,
            limit=limit,
        )

    def list_recent(
        self,
        *,
        limit: int,
        status: str | None = None,
        workspace_id: object | None = None,
        ticket_id: str | None = None,
    ) -> tuple[WorkflowInstance, ...]:
        return _sorted_limited(
            (
                workflow
                for workflow in self._workflows_by_id.values()
                if (status is None or workflow.status.value == status)
                and (workspace_id is None or workflow.workspace_id == workspace_id)
                and (ticket_id is None or workflow.ticket_id == ticket_id)
            ),
            key=lambda workflow: (workflow.updated_at, workflow.created_at),
            limit=limit,
        )

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

    def get_running_by_workflow_id(self, workflow_instance_id: object) -> WorkflowAttempt | None:
        return _latest_or_none(
            (
                attempt
                for attempt in self._attempts_by_id.values()
                if (
                    attempt.workflow_instance_id == workflow_instance_id
                    and attempt.status.value == "running"
                )
            ),
            key=lambda attempt: attempt.started_at,
        )

    def get_latest_by_workflow_id(self, workflow_instance_id: object) -> WorkflowAttempt | None:
        return _latest_or_none(
            (
                attempt
                for attempt in self._attempts_by_id.values()
                if attempt.workflow_instance_id == workflow_instance_id
            ),
            key=lambda attempt: (attempt.attempt_number, attempt.started_at),
        )

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

    def get_latest_by_workflow_id(self, workflow_instance_id: object) -> WorkflowCheckpoint | None:
        return _latest_or_none(
            (
                checkpoint
                for checkpoint in self._checkpoints_by_id.values()
                if checkpoint.workflow_instance_id == workflow_instance_id
            ),
            key=lambda checkpoint: checkpoint.created_at,
        )

    def get_latest_by_attempt_id(self, attempt_id: object) -> WorkflowCheckpoint | None:
        return _latest_or_none(
            (
                checkpoint
                for checkpoint in self._checkpoints_by_id.values()
                if checkpoint.attempt_id == attempt_id
            ),
            key=lambda checkpoint: checkpoint.created_at,
        )

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self._checkpoints_by_id[checkpoint.checkpoint_id] = checkpoint
        return checkpoint


class InMemoryVerifyReportRepository(VerifyReportRepository):
    def __init__(self, verify_reports_by_id: dict[object, VerifyReport]) -> None:
        self._verify_reports_by_id = verify_reports_by_id

    def get_latest_by_attempt_id(self, attempt_id: object) -> VerifyReport | None:
        return _latest_or_none(
            (
                verify_report
                for verify_report in self._verify_reports_by_id.values()
                if verify_report.attempt_id == attempt_id
            ),
            key=lambda report: report.created_at,
        )

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
        return _sorted_limited(
            (
                episode
                for episode in self._episodes_by_id.values()
                if episode.workflow_instance_id == workflow_instance_id
            ),
            key=lambda episode: episode.created_at,
            limit=limit,
        )


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
        return _sorted_limited(
            (
                memory_item
                for memory_item in self._memory_items_by_id.values()
                if memory_item.workspace_id == workspace_id
            ),
            key=lambda memory_item: memory_item.created_at,
            limit=limit,
        )

    def list_by_episode_id(
        self,
        episode_id: object,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        return _sorted_limited(
            (
                memory_item
                for memory_item in self._memory_items_by_id.values()
                if memory_item.episode_id == episode_id
            ),
            key=lambda memory_item: memory_item.created_at,
            limit=limit,
        )

    def count_by_provenance(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for memory_item in self._memory_items_by_id.values():
            counts[memory_item.provenance] = counts.get(memory_item.provenance, 0) + 1
        return counts


class InMemoryMemorySummaryRepository:
    def __init__(self, memory_summaries_by_id: dict[object, MemorySummaryRecord]) -> None:
        self._memory_summaries_by_id = memory_summaries_by_id

    def create(self, summary: MemorySummaryRecord) -> MemorySummaryRecord:
        self._memory_summaries_by_id[summary.memory_summary_id] = summary
        return summary

    def list_by_workspace_id(
        self,
        workspace_id: object,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        return _sorted_limited(
            (
                summary
                for summary in self._memory_summaries_by_id.values()
                if summary.workspace_id == workspace_id
            ),
            key=lambda summary: summary.created_at,
            limit=limit,
        )

    def list_by_episode_id(
        self,
        episode_id: object,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        return _sorted_limited(
            (
                summary
                for summary in self._memory_summaries_by_id.values()
                if summary.episode_id == episode_id
            ),
            key=lambda summary: summary.created_at,
            limit=limit,
        )

    def list_by_summary_ids(
        self,
        summary_ids: tuple[object, ...],
    ) -> tuple[MemorySummaryRecord, ...]:
        if not summary_ids:
            return ()

        summary_id_set = set(summary_ids)
        return tuple(
            sorted(
                (
                    summary
                    for summary in self._memory_summaries_by_id.values()
                    if summary.memory_summary_id in summary_id_set
                ),
                key=lambda summary: summary.created_at,
                reverse=True,
            )
        )


class InMemoryMemorySummaryMembershipRepository:
    def __init__(
        self,
        memory_summary_memberships_by_id: dict[object, MemorySummaryMembershipRecord],
    ) -> None:
        self._memory_summary_memberships_by_id = memory_summary_memberships_by_id

    def create(
        self,
        membership: MemorySummaryMembershipRecord,
    ) -> MemorySummaryMembershipRecord:
        self._memory_summary_memberships_by_id[membership.memory_summary_membership_id] = membership
        return membership

    def list_by_summary_id(
        self,
        memory_summary_id: object,
        *,
        limit: int,
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        memberships = sorted(
            (
                membership
                for membership in self._memory_summary_memberships_by_id.values()
                if membership.memory_summary_id == memory_summary_id
            ),
            key=lambda membership: (
                membership.membership_order is None,
                membership.membership_order if membership.membership_order is not None else 0,
                membership.created_at,
                membership.memory_summary_membership_id,
            ),
        )
        return tuple(memberships[:limit])

    def list_by_summary_ids(
        self,
        memory_summary_ids: tuple[object, ...],
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        if not memory_summary_ids:
            return ()

        summary_id_set = set(memory_summary_ids)
        return tuple(
            sorted(
                (
                    membership
                    for membership in self._memory_summary_memberships_by_id.values()
                    if membership.memory_summary_id in summary_id_set
                ),
                key=lambda membership: (
                    membership.memory_summary_id,
                    membership.membership_order is None,
                    membership.membership_order if membership.membership_order is not None else 0,
                    membership.created_at,
                    membership.memory_summary_membership_id,
                ),
            )
        )


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
        return _sorted_limited(
            (
                embedding
                for embedding in self._memory_embeddings_by_id.values()
                if embedding.memory_id == memory_id
            ),
            key=lambda embedding: embedding.created_at,
            limit=limit,
        )


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
        memory_summaries_by_id: dict[object, MemorySummaryRecord] | None = None,
        memory_summary_memberships_by_id: dict[object, MemorySummaryMembershipRecord] | None = None,
        memory_embeddings_by_id: dict[object, MemoryEmbeddingRecord] | None = None,
    ) -> None:
        self._workspaces_by_id = workspaces_by_id if workspaces_by_id is not None else {}
        self._workspaces_by_canonical_path = (
            workspaces_by_canonical_path if workspaces_by_canonical_path is not None else {}
        )
        self._workflows_by_id = workflows_by_id if workflows_by_id is not None else {}
        self._attempts_by_id = attempts_by_id if attempts_by_id is not None else {}
        self._checkpoints_by_id = checkpoints_by_id if checkpoints_by_id is not None else {}
        self._verify_reports_by_id = (
            verify_reports_by_id if verify_reports_by_id is not None else {}
        )
        self._episodes_by_id = episodes_by_id if episodes_by_id is not None else {}
        self._memory_items_by_id = memory_items_by_id if memory_items_by_id is not None else {}
        self._memory_summaries_by_id = (
            memory_summaries_by_id if memory_summaries_by_id is not None else {}
        )
        self._memory_summary_memberships_by_id = (
            memory_summary_memberships_by_id if memory_summary_memberships_by_id is not None else {}
        )
        self._memory_embeddings_by_id = (
            memory_embeddings_by_id if memory_embeddings_by_id is not None else {}
        )

        self._committed = False
        self._rolled_back = False

        self.workspaces = InMemoryWorkspaceRepository(
            self._workspaces_by_id,
            self._workspaces_by_canonical_path,
        )
        self.workflow_instances = InMemoryWorkflowInstanceRepository(self._workflows_by_id)
        self.workflow_attempts = InMemoryWorkflowAttemptRepository(self._attempts_by_id)
        self.workflow_checkpoints = InMemoryWorkflowCheckpointRepository(self._checkpoints_by_id)
        self.verify_reports = InMemoryVerifyReportRepository(self._verify_reports_by_id)
        self.memory_episodes = InMemoryMemoryEpisodeRepository(self._episodes_by_id)
        self.memory_items = InMemoryMemoryItemRepository(self._memory_items_by_id)
        self.memory_summaries = InMemoryMemorySummaryRepository(self._memory_summaries_by_id)
        self.memory_summary_memberships = InMemoryMemorySummaryMembershipRepository(
            self._memory_summary_memberships_by_id
        )
        self.memory_embeddings = InMemoryMemoryEmbeddingRepository(self._memory_embeddings_by_id)

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
    memory_summaries_by_id: dict[object, MemorySummaryRecord]
    memory_summary_memberships_by_id: dict[object, MemorySummaryMembershipRecord]
    memory_embeddings_by_id: dict[object, MemoryEmbeddingRecord]

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
            memory_summaries_by_id={},
            memory_summary_memberships_by_id={},
            memory_embeddings_by_id={},
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
            memory_summaries_by_id=dict(self.memory_summaries_by_id),
            memory_summary_memberships_by_id=dict(self.memory_summary_memberships_by_id),
            memory_embeddings_by_id=dict(self.memory_embeddings_by_id),
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
            memory_summaries_by_id=backing_store.memory_summaries_by_id,
            memory_summary_memberships_by_id=backing_store.memory_summary_memberships_by_id,
            memory_embeddings_by_id=backing_store.memory_embeddings_by_id,
        )

    return _factory


__all__ = [
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
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
