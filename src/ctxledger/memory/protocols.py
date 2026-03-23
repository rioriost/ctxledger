"""Protocol contracts for the memory subsystem.

This module contains abstract repository and lookup contracts used by the
memory service layer. It intentionally excludes concrete implementations and
service orchestration so those concerns can evolve independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from .types import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    MemoryRelationRecord,
)


class WorkflowLookupRepository(Protocol):
    """Minimal workflow lookup contract needed by the memory service."""

    def workflow_exists(self, workflow_instance_id: UUID) -> bool: ...

    def workflow_ids_by_workspace_id(
        self,
        workspace_id: str,
        *,
        limit: int,
    ) -> tuple[UUID, ...]: ...

    def workflow_ids_by_ticket_id(
        self,
        ticket_id: str,
        *,
        limit: int,
    ) -> tuple[UUID, ...]: ...

    def workflow_freshness_by_id(
        self,
        workflow_instance_id: UUID,
    ) -> dict[str, datetime | int | str | bool | None]: ...


class EpisodeRepository(Protocol):
    """Persistence contract for episodic memory records."""

    def create(self, episode: EpisodeRecord) -> EpisodeRecord: ...

    def list_by_workflow_id(
        self,
        workflow_instance_id: UUID,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]: ...


class MemoryItemRepository(Protocol):
    """Persistence contract for semantic/procedural memory items."""

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord: ...

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]: ...

    def list_workspace_root_items(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]: ...

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]: ...

    def list_by_episode_ids(
        self,
        episode_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]: ...

    def list_by_memory_ids(
        self,
        memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]: ...


class MemoryEmbeddingRepository(Protocol):
    """Persistence contract for derived embedding index records."""

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord: ...

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]: ...

    def find_similar(
        self,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
        workspace_id: UUID | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]: ...


class MemoryRelationRepository(Protocol):
    """Persistence contract for directional relations between memory items."""

    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord: ...

    def list_by_source_memory_id(
        self,
        source_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]: ...

    def list_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryRelationRecord, ...]: ...

    def list_by_target_memory_id(
        self,
        target_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]: ...


@runtime_checkable
class MemoryRelationMemoryItemLookupRepository(Protocol):
    """Read-only lookup contract for resolving related memory item targets."""

    def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None: ...


class WorkspaceLookupRepository(Protocol):
    """Minimal workspace lookup contract needed by the memory service."""

    def workspace_id_by_workflow_id(
        self,
        workflow_instance_id: UUID,
    ) -> UUID | None: ...
