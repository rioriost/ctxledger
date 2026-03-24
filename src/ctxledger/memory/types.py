"""Core memory-layer types, requests, responses, and errors.

This module holds the stable shape definitions used by the memory subsystem.
It intentionally excludes repository implementations and service orchestration
logic so those concerns can evolve independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID


class MemoryFeature(StrEnum):
    """Memory capabilities exposed by the service layer."""

    REMEMBER_EPISODE = "memory_remember_episode"
    SEARCH = "memory_search"
    GET_CONTEXT = "memory_get_context"


class MemoryErrorCode(StrEnum):
    """Machine-readable error codes for memory service failures."""

    NOT_IMPLEMENTED = "memory_not_implemented"
    INVALID_REQUEST = "memory_invalid_request"
    WORKFLOW_NOT_FOUND = "memory_workflow_not_found"


@dataclass(slots=True, frozen=True)
class MemoryServiceError(Exception):
    """Typed exception used by the memory service.

    This is intended to be caught by the application / transport layer and
    mapped into protocol-visible errors.
    """

    code: MemoryErrorCode
    message: str
    feature: MemoryFeature
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True, frozen=True)
class RememberEpisodeRequest:
    """Request shape for episodic memory persistence."""

    workflow_instance_id: str
    summary: str
    attempt_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class EpisodeRecord:
    """Canonical episodic memory record."""

    episode_id: UUID
    workflow_instance_id: UUID
    summary: str
    attempt_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "recorded"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemoryItemRecord:
    """Canonical semantic/procedural memory item record."""

    memory_id: UUID
    workspace_id: UUID | None = None
    episode_id: UUID | None = None
    type: str = "episode_note"
    provenance: str = "episode"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemoryEmbeddingRecord:
    """Derived embedding index record for a memory item."""

    memory_embedding_id: UUID
    memory_id: UUID
    embedding_model: str
    embedding: tuple[float, ...] = ()
    content_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemoryRelationRecord:
    """Canonical relation record between memory items."""

    memory_relation_id: UUID
    source_memory_id: UUID
    target_memory_id: UUID
    relation_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemorySummaryRecord:
    """Canonical summary record for the first hierarchy layer."""

    memory_summary_id: UUID
    workspace_id: UUID
    episode_id: UUID | None = None
    summary_text: str = ""
    summary_kind: str = "episode_summary"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemorySummaryMembershipRecord:
    """Canonical membership record linking summaries to memory items."""

    memory_summary_membership_id: UUID
    memory_summary_id: UUID
    memory_id: UUID
    membership_order: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class RememberEpisodeResponse:
    """Response returned when an episode is persisted."""

    feature: MemoryFeature
    implemented: bool
    message: str
    status: str = "recorded"
    available_in_version: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    episode: EpisodeRecord | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class GetContextResponse:
    """Response returned when episode-oriented context is assembled."""

    feature: MemoryFeature
    implemented: bool
    message: str
    status: str = "ok"
    available_in_version: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    episodes: tuple[EpisodeRecord, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SearchResultRecord:
    """Result item returned by memory search."""

    memory_id: UUID
    workspace_id: UUID | None
    episode_id: UUID | None = None
    workflow_instance_id: UUID | None = None
    summary: str = ""
    attempt_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    matched_fields: tuple[str, ...] = ()
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    ranking_details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class SearchMemoryResponse:
    """Response returned when memory search results are assembled."""

    feature: MemoryFeature
    implemented: bool
    message: str
    status: str = "ok"
    available_in_version: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    results: tuple[SearchResultRecord, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SearchMemoryRequest:
    """Request shape for future semantic/procedural memory search."""

    query: str
    workspace_id: str | None = None
    limit: int = 10
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class GetMemoryContextRequest:
    """Request shape for future auxiliary memory context retrieval."""

    query: str | None = None
    workspace_id: str | None = None
    workflow_instance_id: str | None = None
    ticket_id: str | None = None
    limit: int = 10
    include_episodes: bool = True
    include_memory_items: bool = True
    include_summaries: bool = True


@dataclass(slots=True, frozen=True)
class StubResponse:
    """Standard response returned by stubbed memory operations.

    This shape is suitable for application-layer adaptation into MCP tool
    responses while keeping the service layer transport-agnostic.
    """

    feature: MemoryFeature
    implemented: bool
    message: str
    status: str = "not_implemented"
    available_in_version: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
