"""Concrete repository and lookup implementations for the memory subsystem.

This module contains the in-memory and UnitOfWork-backed implementations used
by the memory service layer. It intentionally excludes request/response shapes,
protocol contracts, and service orchestration logic so those concerns can evolve
independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from ..workflow.service import UnitOfWork
from .types import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)


class UnitOfWorkWorkflowLookupRepository:
    """Workflow lookup backed by the application's unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def workflow_exists(self, workflow_instance_id: UUID) -> bool:
        with self._uow_factory() as uow:
            return uow.workflow_instances.get_by_id(workflow_instance_id) is not None

    def workflow_ids_by_workspace_id(
        self,
        workspace_id: str,
        *,
        limit: int,
    ) -> tuple[UUID, ...]:
        workspace_uuid = UUID(workspace_id)
        with self._uow_factory() as uow:
            workflows = uow.workflow_instances.list_by_workspace_id(
                workspace_uuid,
                limit=limit,
            )
            return tuple(workflow.workflow_instance_id for workflow in workflows)

    def workflow_ids_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[UUID, ...]:
        with self._uow_factory() as uow:
            workflows = uow.workflow_instances.list_by_ticket_id(
                ticket_id,
                limit=limit,
            )
            return tuple(workflow.workflow_instance_id for workflow in workflows)

    def workflow_freshness_by_id(
        self,
        workflow_instance_id: UUID,
    ) -> dict[str, datetime | int | str | bool | None]:
        with self._uow_factory() as uow:
            workflow = uow.workflow_instances.get_by_id(workflow_instance_id)
            if workflow is None:
                return {
                    "workflow_status": None,
                    "workflow_is_terminal": None,
                    "workflow_updated_at": None,
                    "latest_attempt_status": None,
                    "latest_attempt_is_terminal": None,
                    "has_latest_attempt": False,
                    "latest_attempt_verify_status": None,
                    "latest_attempt_started_at": None,
                    "has_latest_checkpoint": False,
                    "latest_checkpoint_created_at": None,
                    "latest_verify_report_created_at": None,
                }

            latest_attempt = uow.workflow_attempts.get_latest_by_workflow_id(workflow_instance_id)
            latest_checkpoint = uow.workflow_checkpoints.get_latest_by_workflow_id(
                workflow_instance_id
            )
            latest_verify_report = (
                uow.verify_reports.get_latest_by_attempt_id(latest_attempt.attempt_id)
                if latest_attempt is not None
                else None
            )

            return {
                "workflow_status": workflow.status.value,
                "workflow_is_terminal": workflow.is_terminal,
                "workflow_updated_at": workflow.updated_at,
                "latest_attempt_status": (
                    latest_attempt.status.value if latest_attempt is not None else None
                ),
                "latest_attempt_is_terminal": (
                    latest_attempt.is_terminal if latest_attempt is not None else None
                ),
                "has_latest_attempt": latest_attempt is not None,
                "latest_attempt_verify_status": (
                    latest_attempt.verify_status.value
                    if latest_attempt is not None and latest_attempt.verify_status is not None
                    else None
                ),
                "latest_attempt_started_at": (
                    latest_attempt.started_at if latest_attempt is not None else None
                ),
                "has_latest_checkpoint": latest_checkpoint is not None,
                "latest_checkpoint_created_at": (
                    latest_checkpoint.created_at if latest_checkpoint is not None else None
                ),
                "latest_verify_report_created_at": (
                    latest_verify_report.created_at if latest_verify_report is not None else None
                ),
            }


class UnitOfWorkEpisodeRepository:
    """Episode repository backed by PostgreSQL tables through the unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_episodes"):
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.REMEMBER_EPISODE,
                    message="Episode persistence repository is not configured.",
                    details={},
                )
            created = uow.memory_episodes.create(episode)
            uow.commit()
            return created

    def list_by_workflow_id(
        self,
        workflow_instance_id: UUID,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_episodes"):
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Episode persistence repository is not configured.",
                    details={},
                )
            return uow.memory_episodes.list_by_workflow_id(
                workflow_instance_id,
                limit=limit,
            )


class InMemoryWorkflowLookupRepository:
    """Simple in-memory workflow lookup support for local tests and bootstrap."""

    def __init__(
        self,
        workflow_ids: set[UUID] | None = None,
        workflows_by_id: dict[UUID, dict[str, Any]] | None = None,
    ) -> None:
        self._workflow_ids = workflow_ids if workflow_ids is not None else set()
        self._workflows_by_id = workflows_by_id if workflows_by_id is not None else {}

    def workflow_exists(self, workflow_instance_id: UUID) -> bool:
        return (
            workflow_instance_id in self._workflow_ids
            or workflow_instance_id in self._workflows_by_id
        )

    def workflow_ids_by_workspace_id(
        self,
        workspace_id: str,
        *,
        limit: int,
    ) -> tuple[UUID, ...]:
        matches = [
            workflow_instance_id
            for workflow_instance_id, workflow_info in self._workflows_by_id.items()
            if workflow_info.get("workspace_id") == workspace_id
        ]
        return tuple(matches[:limit])

    def workflow_ids_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[UUID, ...]:
        matches = [
            workflow_instance_id
            for workflow_instance_id, workflow_info in self._workflows_by_id.items()
            if workflow_info.get("ticket_id") == ticket_id
        ]
        return tuple(matches[:limit])

    def workflow_freshness_by_id(
        self,
        workflow_instance_id: UUID,
    ) -> dict[str, datetime | int | str | bool | None]:
        workflow_info = self._workflows_by_id.get(workflow_instance_id, {})
        return {
            "workflow_status": workflow_info.get("workflow_status"),
            "workflow_is_terminal": workflow_info.get("workflow_is_terminal"),
            "workflow_updated_at": workflow_info.get("workflow_updated_at"),
            "latest_attempt_status": workflow_info.get("latest_attempt_status"),
            "latest_attempt_is_terminal": workflow_info.get("latest_attempt_is_terminal"),
            "has_latest_attempt": workflow_info.get(
                "has_latest_attempt",
                workflow_info.get("latest_attempt_status") is not None
                or workflow_info.get("latest_attempt_is_terminal") is not None
                or workflow_info.get("latest_attempt_verify_status") is not None
                or workflow_info.get("latest_attempt_started_at") is not None,
            ),
            "latest_attempt_verify_status": workflow_info.get("latest_attempt_verify_status"),
            "latest_attempt_started_at": workflow_info.get("latest_attempt_started_at"),
            "has_latest_checkpoint": workflow_info.get(
                "has_latest_checkpoint",
                workflow_info.get("latest_checkpoint_created_at") is not None,
            ),
            "latest_checkpoint_created_at": workflow_info.get("latest_checkpoint_created_at"),
            "latest_verify_report_created_at": workflow_info.get("latest_verify_report_created_at"),
        }

    def workspace_id_by_workflow_id(self, workflow_instance_id: UUID) -> UUID | None:
        workflow_info = self._workflows_by_id.get(workflow_instance_id)
        if workflow_info is None:
            return None

        raw_workspace_id = workflow_info.get("workspace_id")
        if raw_workspace_id is None:
            return None
        return UUID(raw_workspace_id)


class InMemoryEpisodeRepository:
    """Simple append-only in-memory episode repository."""

    def __init__(self) -> None:
        self._episodes: list[EpisodeRecord] = []

    @property
    def episodes(self) -> tuple[EpisodeRecord, ...]:
        return tuple(self._episodes)

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        self._episodes.append(episode)
        return episode

    def list_by_workflow_id(
        self,
        workflow_instance_id: UUID,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        matches = [
            episode
            for episode in self._episodes
            if episode.workflow_instance_id == workflow_instance_id
        ]
        matches.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(matches[:limit])


class InMemoryMemoryItemRepository:
    """Simple append-only in-memory semantic/procedural memory repository."""

    def __init__(self) -> None:
        self._memory_items: list[MemoryItemRecord] = []

    @property
    def memory_items(self) -> tuple[MemoryItemRecord, ...]:
        return tuple(self._memory_items)

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        self._memory_items.append(memory_item)
        return memory_item

    def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
        for memory_item in self._memory_items:
            if memory_item.memory_id == memory_id:
                return memory_item
        return None

    def list_by_memory_ids(
        self,
        memory_ids: tuple[UUID, ...],
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        if limit <= 0 or not memory_ids:
            return ()

        memory_id_set = set(memory_ids)
        matches = [
            memory_item
            for memory_item in self._memory_items
            if memory_item.memory_id in memory_id_set
        ]
        matches.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_by_episode_ids(
        self,
        episode_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]:
        if not episode_ids:
            return ()

        episode_id_set = set(episode_ids)
        matches = [
            memory_item
            for memory_item in self._memory_items
            if memory_item.episode_id in episode_id_set
        ]
        matches.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(matches)

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        matches = [
            memory_item
            for memory_item in self._memory_items
            if memory_item.workspace_id == workspace_id
        ]
        matches.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_workspace_root_items(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        matches = [
            memory_item
            for memory_item in self._memory_items
            if memory_item.workspace_id == workspace_id and memory_item.episode_id is None
        ]
        matches.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        matches = [
            memory_item
            for memory_item in self._memory_items
            if memory_item.episode_id == episode_id
        ]
        matches.sort(key=lambda memory_item: memory_item.created_at, reverse=True)
        return tuple(matches[:limit])


class InMemoryMemoryEmbeddingRepository:
    """Simple append-only in-memory embedding repository."""

    def __init__(self) -> None:
        self._embeddings: list[MemoryEmbeddingRecord] = []

    @property
    def embeddings(self) -> tuple[MemoryEmbeddingRecord, ...]:
        return tuple(self._embeddings)

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        self._embeddings.append(embedding)
        return embedding

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        matches = [embedding for embedding in self._embeddings if embedding.memory_id == memory_id]
        matches.sort(key=lambda embedding: embedding.created_at, reverse=True)
        return tuple(matches[:limit])

    def find_similar(
        self,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
        workspace_id: UUID | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        if not query_embedding:
            return ()

        scored_embeddings: list[tuple[float, MemoryEmbeddingRecord]] = []
        for embedding in self._embeddings:
            if len(embedding.embedding) != len(query_embedding):
                continue
            score = sum(
                left * right
                for left, right in zip(embedding.embedding, query_embedding, strict=False)
            )
            scored_embeddings.append((score, embedding))

        scored_embeddings.sort(
            key=lambda item: (item[0], item[1].created_at),
            reverse=True,
        )
        return tuple(embedding for _, embedding in scored_embeddings[:limit])


class InMemoryMemorySummaryRepository:
    """Simple append-only in-memory summary repository."""

    def __init__(self) -> None:
        self._summaries: list[MemorySummaryRecord] = []

    @property
    def summaries(self) -> tuple[MemorySummaryRecord, ...]:
        return tuple(self._summaries)

    def create(self, summary: MemorySummaryRecord) -> MemorySummaryRecord:
        self._summaries.append(summary)
        return summary

    def delete_by_summary_id(
        self,
        memory_summary_id: UUID,
    ) -> None:
        self._summaries = [
            summary for summary in self._summaries if summary.memory_summary_id != memory_summary_id
        ]

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        matches = [summary for summary in self._summaries if summary.workspace_id == workspace_id]
        matches.sort(key=lambda summary: summary.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        matches = [summary for summary in self._summaries if summary.episode_id == episode_id]
        matches.sort(key=lambda summary: summary.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_by_summary_ids(
        self,
        summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryRecord, ...]:
        if not summary_ids:
            return ()

        summary_id_set = set(summary_ids)
        matches = [
            summary for summary in self._summaries if summary.memory_summary_id in summary_id_set
        ]
        matches.sort(key=lambda summary: summary.created_at, reverse=True)
        return tuple(matches)


class InMemoryMemorySummaryMembershipRepository:
    """Simple append-only in-memory summary membership repository."""

    def __init__(self) -> None:
        self._memberships: list[MemorySummaryMembershipRecord] = []

    @property
    def memberships(self) -> tuple[MemorySummaryMembershipRecord, ...]:
        return tuple(self._memberships)

    def create(
        self,
        membership: MemorySummaryMembershipRecord,
    ) -> MemorySummaryMembershipRecord:
        self._memberships.append(membership)
        return membership

    def delete_by_summary_id(
        self,
        memory_summary_id: UUID,
    ) -> None:
        self._memberships = [
            membership
            for membership in self._memberships
            if membership.memory_summary_id != memory_summary_id
        ]

    def list_by_summary_id(
        self,
        memory_summary_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        matches = [
            membership
            for membership in self._memberships
            if membership.memory_summary_id == memory_summary_id
        ]
        matches.sort(
            key=lambda membership: (
                membership.membership_order is None,
                membership.membership_order if membership.membership_order is not None else 0,
                membership.created_at,
                membership.memory_summary_membership_id,
            )
        )
        return tuple(matches[:limit])

    def list_by_summary_ids(
        self,
        memory_summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        if not memory_summary_ids:
            return ()

        summary_id_set = set(memory_summary_ids)
        matches = [
            membership
            for membership in self._memberships
            if membership.memory_summary_id in summary_id_set
        ]
        matches.sort(
            key=lambda membership: (
                membership.memory_summary_id,
                membership.membership_order is None,
                membership.membership_order if membership.membership_order is not None else 0,
                membership.created_at,
                membership.memory_summary_membership_id,
            )
        )
        return tuple(matches)


class UnitOfWorkMemoryItemRepository:
    """Memory item repository backed by PostgreSQL tables through the unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_items") or uow.memory_items is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.REMEMBER_EPISODE,
                    message="Memory item repository is not configured.",
                    details={},
                )
            created = uow.memory_items.create(memory_item)
            uow.commit()
            return created

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_items") or uow.memory_items is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.SEARCH,
                    message="Memory item repository is not configured.",
                    details={},
                )
            return uow.memory_items.list_by_workspace_id(
                workspace_id,
                limit=limit,
            )

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_items") or uow.memory_items is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory item repository is not configured.",
                    details={},
                )
            return uow.memory_items.list_by_episode_id(
                episode_id,
                limit=limit,
            )

    def list_by_episode_ids(
        self,
        episode_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_items") or uow.memory_items is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory item repository is not configured.",
                    details={},
                )
            return uow.memory_items.list_by_episode_ids(episode_ids)


class UnitOfWorkMemorySummaryRepository:
    """Memory summary repository backed by PostgreSQL tables through the unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, summary: MemorySummaryRecord) -> MemorySummaryRecord:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_summaries") or uow.memory_summaries is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary repository is not configured.",
                    details={},
                )
            created = uow.memory_summaries.create(summary)
            uow.commit()
            return created

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_summaries") or uow.memory_summaries is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary repository is not configured.",
                    details={},
                )
            return uow.memory_summaries.list_by_workspace_id(
                workspace_id,
                limit=limit,
            )

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_summaries") or uow.memory_summaries is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary repository is not configured.",
                    details={},
                )
            return uow.memory_summaries.list_by_episode_id(
                episode_id,
                limit=limit,
            )

    def list_by_summary_ids(
        self,
        summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_summaries") or uow.memory_summaries is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary repository is not configured.",
                    details={},
                )
            return uow.memory_summaries.list_by_summary_ids(summary_ids)


class UnitOfWorkMemorySummaryMembershipRepository:
    """Memory summary membership repository backed by PostgreSQL tables through the unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(
        self,
        membership: MemorySummaryMembershipRecord,
    ) -> MemorySummaryMembershipRecord:
        with self._uow_factory() as uow:
            if (
                not hasattr(uow, "memory_summary_memberships")
                or uow.memory_summary_memberships is None
            ):
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary membership repository is not configured.",
                    details={},
                )
            created = uow.memory_summary_memberships.create(membership)
            uow.commit()
            return created

    def list_by_summary_id(
        self,
        memory_summary_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        with self._uow_factory() as uow:
            if (
                not hasattr(uow, "memory_summary_memberships")
                or uow.memory_summary_memberships is None
            ):
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary membership repository is not configured.",
                    details={},
                )
            return uow.memory_summary_memberships.list_by_summary_id(
                memory_summary_id,
                limit=limit,
            )

    def list_by_summary_ids(
        self,
        memory_summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        with self._uow_factory() as uow:
            if (
                not hasattr(uow, "memory_summary_memberships")
                or uow.memory_summary_memberships is None
            ):
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="Memory summary membership repository is not configured.",
                    details={},
                )
            return uow.memory_summary_memberships.list_by_summary_ids(memory_summary_ids)


class UnitOfWorkWorkspaceLookupRepository:
    """Workspace lookup backed by the application's unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def workspace_id_by_workflow_id(self, workflow_instance_id: UUID) -> UUID | None:
        with self._uow_factory() as uow:
            workflow = uow.workflow_instances.get_by_id(workflow_instance_id)
            if workflow is None:
                return None
            return workflow.workspace_id


class UnitOfWorkMemoryEmbeddingRepository:
    """Memory embedding repository backed by PostgreSQL tables through the unit of work."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_embeddings") or uow.memory_embeddings is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.REMEMBER_EPISODE,
                    message="Memory embedding repository is not configured.",
                    details={},
                )
            created = uow.memory_embeddings.create(embedding)
            uow.commit()
            return created

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_embeddings") or uow.memory_embeddings is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.SEARCH,
                    message="Memory embedding repository is not configured.",
                    details={},
                )
            return uow.memory_embeddings.list_by_memory_id(
                memory_id,
                limit=limit,
            )

    def find_similar(
        self,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
        workspace_id: UUID | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        with self._uow_factory() as uow:
            if not hasattr(uow, "memory_embeddings") or uow.memory_embeddings is None:
                raise MemoryServiceError(
                    code=MemoryErrorCode.NOT_IMPLEMENTED,
                    feature=MemoryFeature.SEARCH,
                    message="Memory embedding repository is not configured.",
                    details={},
                )
            return uow.memory_embeddings.find_similar(
                query_embedding,
                limit=limit,
                workspace_id=workspace_id,
            )


class InMemoryMemoryRelationRepository:
    """Simple append-only in-memory relation repository."""

    def __init__(self) -> None:
        self._relations: list[MemoryRelationRecord] = []

    @property
    def relations(self) -> tuple[MemoryRelationRecord, ...]:
        return tuple(self._relations)

    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord:
        self._relations.append(relation)
        return relation

    def list_by_source_memory_id(
        self,
        source_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        matches = [
            relation
            for relation in self._relations
            if relation.source_memory_id == source_memory_id
        ]
        matches.sort(key=lambda relation: relation.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryRelationRecord, ...]:
        if not source_memory_ids:
            return ()

        source_memory_id_set = set(source_memory_ids)
        matches = [
            relation
            for relation in self._relations
            if relation.source_memory_id in source_memory_id_set
        ]
        matches.sort(key=lambda relation: relation.created_at, reverse=True)
        return tuple(matches)

    def list_distinct_support_target_memory_ids_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[UUID, ...]:
        if not source_memory_ids:
            return ()

        distinct_target_memory_ids: list[UUID] = []
        seen_target_memory_ids: set[UUID] = set()

        relations_by_source_memory_id: dict[UUID, list[MemoryRelationRecord]] = {
            source_memory_id: [] for source_memory_id in source_memory_ids
        }
        for relation in self._relations:
            if relation.relation_type != "supports":
                continue
            if relation.source_memory_id not in relations_by_source_memory_id:
                continue
            relations_by_source_memory_id[relation.source_memory_id].append(relation)

        for source_memory_id in source_memory_ids:
            matches = relations_by_source_memory_id[source_memory_id]
            matches.sort(key=lambda relation: relation.created_at, reverse=True)

            for relation in matches:
                if relation.target_memory_id in seen_target_memory_ids:
                    continue
                seen_target_memory_ids.add(relation.target_memory_id)
                distinct_target_memory_ids.append(relation.target_memory_id)

        return tuple(distinct_target_memory_ids)

    def list_by_target_memory_id(
        self,
        target_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        matches = [
            relation
            for relation in self._relations
            if relation.target_memory_id == target_memory_id
        ]
        matches.sort(key=lambda relation: relation.created_at, reverse=True)
        return tuple(matches[:limit])
