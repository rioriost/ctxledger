"""Memory service support for episodic persistence and future retrieval layers.

The workflow subsystem remains the canonical operational truth source.
The memory subsystem stores reusable knowledge derived from or related to
workflow execution.

For the current implementation stage, episodic persistence is supported while
semantic and hierarchical retrieval remain intentionally stubbed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Protocol
from uuid import UUID, uuid4

from ..config import get_settings
from ..workflow.service import UnitOfWork
from .embeddings import (
    EmbeddingGenerationError,
    EmbeddingGenerator,
    EmbeddingRequest,
    build_embedding_generator,
)


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

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
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


class WorkspaceLookupRepository(Protocol):
    """Minimal workspace lookup contract needed by the memory service."""

    def workspace_id_by_workflow_id(
        self, workflow_instance_id: UUID
    ) -> UUID | None: ...


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
                    "latest_projection_canonical_update_at": None,
                    "latest_projection_successful_write_at": None,
                    "projection_open_failure_count": 0,
                }

            latest_attempt = uow.workflow_attempts.get_latest_by_workflow_id(
                workflow_instance_id
            )
            latest_checkpoint = uow.workflow_checkpoints.get_latest_by_workflow_id(
                workflow_instance_id
            )
            latest_verify_report = (
                uow.verify_reports.get_latest_by_attempt_id(latest_attempt.attempt_id)
                if latest_attempt is not None
                else None
            )

            projections = ()
            if getattr(uow, "projection_states", None) is not None:
                projections = uow.projection_states.get_resume_projections(
                    workflow.workspace_id,
                    workflow.workflow_instance_id,
                )

            latest_projection_canonical_update_at = None
            latest_projection_successful_write_at = None
            projection_open_failure_count = 0

            if projections:
                canonical_updates = tuple(
                    projection.last_canonical_update_at
                    for projection in projections
                    if projection.last_canonical_update_at is not None
                )
                successful_writes = tuple(
                    projection.last_successful_write_at
                    for projection in projections
                    if projection.last_successful_write_at is not None
                )
                latest_projection_canonical_update_at = (
                    max(canonical_updates) if canonical_updates else None
                )
                latest_projection_successful_write_at = (
                    max(successful_writes) if successful_writes else None
                )
                projection_open_failure_count = sum(
                    projection.open_failure_count for projection in projections
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
                    if latest_attempt is not None
                    and latest_attempt.verify_status is not None
                    else None
                ),
                "latest_attempt_started_at": (
                    latest_attempt.started_at if latest_attempt is not None else None
                ),
                "has_latest_checkpoint": latest_checkpoint is not None,
                "latest_checkpoint_created_at": (
                    latest_checkpoint.created_at
                    if latest_checkpoint is not None
                    else None
                ),
                "latest_verify_report_created_at": (
                    latest_verify_report.created_at
                    if latest_verify_report is not None
                    else None
                ),
                "latest_projection_canonical_update_at": (
                    latest_projection_canonical_update_at
                ),
                "latest_projection_successful_write_at": (
                    latest_projection_successful_write_at
                ),
                "projection_open_failure_count": projection_open_failure_count,
            }


def _normalize_query_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized.casefold() if normalized else None


def _query_tokens(normalized_query: str | None) -> tuple[str, ...]:
    if normalized_query is None:
        return ()

    return tuple(token for token in normalized_query.split() if token)


def _text_matches_query(
    *,
    text: str,
    normalized_query: str,
    query_tokens: tuple[str, ...],
) -> bool:
    normalized_text = text.casefold()
    if normalized_query in normalized_text:
        return True
    return bool(query_tokens) and all(
        token in normalized_text for token in query_tokens
    )


def _metadata_query_strings(metadata: dict[str, Any]) -> tuple[str, ...]:
    query_strings: list[str] = []

    for key, value in metadata.items():
        query_strings.append(str(key).casefold())
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value:
                query_strings.append(normalized_value.casefold())
        else:
            query_strings.append(str(value).casefold())

    return tuple(query_strings)


def _embedding_dot_product(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    if len(left) != len(right):
        return 0.0

    return sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=False)
    )


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
            "latest_attempt_is_terminal": workflow_info.get(
                "latest_attempt_is_terminal"
            ),
            "has_latest_attempt": workflow_info.get(
                "has_latest_attempt",
                workflow_info.get("latest_attempt_status") is not None
                or workflow_info.get("latest_attempt_is_terminal") is not None
                or workflow_info.get("latest_attempt_verify_status") is not None
                or workflow_info.get("latest_attempt_started_at") is not None,
            ),
            "latest_attempt_verify_status": workflow_info.get(
                "latest_attempt_verify_status"
            ),
            "latest_attempt_started_at": workflow_info.get("latest_attempt_started_at"),
            "has_latest_checkpoint": workflow_info.get(
                "has_latest_checkpoint",
                workflow_info.get("latest_checkpoint_created_at") is not None,
            ),
            "latest_checkpoint_created_at": workflow_info.get(
                "latest_checkpoint_created_at"
            ),
            "latest_verify_report_created_at": workflow_info.get(
                "latest_verify_report_created_at"
            ),
            "latest_projection_canonical_update_at": workflow_info.get(
                "latest_projection_canonical_update_at"
            ),
            "latest_projection_successful_write_at": workflow_info.get(
                "latest_projection_successful_write_at"
            ),
            "projection_open_failure_count": workflow_info.get(
                "projection_open_failure_count",
                0,
            ),
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
        matches = [
            embedding
            for embedding in self._embeddings
            if embedding.memory_id == memory_id
        ]
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
                for left, right in zip(
                    embedding.embedding, query_embedding, strict=False
                )
            )
            scored_embeddings.append((score, embedding))

        scored_embeddings.sort(
            key=lambda item: (item[0], item[1].created_at),
            reverse=True,
        )
        return tuple(embedding for _, embedding in scored_embeddings[:limit])


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


class MemoryService:
    """Memory subsystem service.

    Episodic persistence is implemented as append-only episode creation.
    Retrieval-oriented operations remain stubbed until later stages.
    """

    def __init__(
        self,
        *,
        episode_repository: EpisodeRepository | None = None,
        memory_item_repository: MemoryItemRepository | None = None,
        memory_embedding_repository: MemoryEmbeddingRepository | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        workflow_lookup: WorkflowLookupRepository | None = None,
        workspace_lookup: WorkspaceLookupRepository | None = None,
    ) -> None:
        self._episode_repository = episode_repository or InMemoryEpisodeRepository()
        self._memory_item_repository = (
            memory_item_repository or InMemoryMemoryItemRepository()
        )
        self._memory_embedding_repository = memory_embedding_repository
        if embedding_generator is None:
            try:
                embedding_generator = build_embedding_generator(
                    get_settings().embedding
                )
            except Exception:
                embedding_generator = None
        self._embedding_generator = embedding_generator
        self._workflow_lookup = workflow_lookup
        self._workspace_lookup = workspace_lookup

    def remember_episode(
        self, request: RememberEpisodeRequest
    ) -> RememberEpisodeResponse:
        """Persist a new episode associated with a workflow."""
        self._require_non_empty(
            request.workflow_instance_id,
            field_name="workflow_instance_id",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        self._require_non_empty(
            request.summary,
            field_name="summary",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )

        workflow_instance_id = self._parse_uuid(
            request.workflow_instance_id,
            field_name="workflow_instance_id",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        attempt_id = (
            self._parse_uuid(
                request.attempt_id,
                field_name="attempt_id",
                feature=MemoryFeature.REMEMBER_EPISODE,
            )
            if request.attempt_id is not None and self._has_text(request.attempt_id)
            else None
        )

        if (
            self._workflow_lookup is not None
            and not self._workflow_lookup.workflow_exists(workflow_instance_id)
        ):
            raise MemoryServiceError(
                code=MemoryErrorCode.WORKFLOW_NOT_FOUND,
                feature=MemoryFeature.REMEMBER_EPISODE,
                message="workflow_instance_id was not found.",
                details={"workflow_instance_id": str(workflow_instance_id)},
            )

        episode = self._episode_repository.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_instance_id,
                summary=request.summary.strip(),
                attempt_id=attempt_id,
                metadata=dict(request.metadata),
            )
        )
        memory_item = self._memory_item_repository.create(
            MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=self._resolve_workspace_id(workflow_instance_id),
                episode_id=episode.episode_id,
                type="episode_note",
                provenance="episode",
                content=episode.summary,
                metadata=dict(episode.metadata),
                created_at=episode.created_at,
                updated_at=episode.updated_at,
            )
        )
        embedding_outcome = self._maybe_store_embedding(memory_item)

        return RememberEpisodeResponse(
            feature=MemoryFeature.REMEMBER_EPISODE,
            implemented=True,
            message="Episode recorded successfully.",
            status="recorded",
            available_in_version="0.2.0",
            episode=episode,
            details={
                "workflow_instance_id": str(episode.workflow_instance_id),
                "attempt_id": (
                    str(episode.attempt_id) if episode.attempt_id is not None else None
                ),
                **embedding_outcome,
            },
        )

    def search(self, request: SearchMemoryRequest) -> SearchMemoryResponse:
        """Return hybrid lexical + semantic memory-item search results."""
        self._require_non_empty(
            request.query,
            field_name="query",
            feature=MemoryFeature.SEARCH,
        )
        self._require_positive_limit(
            request.limit,
            feature=MemoryFeature.SEARCH,
        )

        normalized_query = _normalize_query_text(request.query)
        assert normalized_query is not None

        workspace_id: UUID | None = None
        if self._has_text(request.workspace_id):
            workspace_id = self._parse_uuid(
                request.workspace_id or "",
                field_name="workspace_id",
                feature=MemoryFeature.SEARCH,
            )

        memory_items: tuple[MemoryItemRecord, ...] = ()
        if workspace_id is not None:
            memory_items = self._memory_item_repository.list_by_workspace_id(
                workspace_id,
                limit=request.limit,
            )

        semantic_matches: tuple[MemoryEmbeddingRecord, ...] = ()
        semantic_query_generated = False
        semantic_generation_skipped_reason: str | None = None

        if (
            self._embedding_generator is None
            or self._memory_embedding_repository is None
        ):
            semantic_generation_skipped_reason = "embedding_search_not_configured"
        else:
            try:
                semantic_query = self._embedding_generator.generate(
                    EmbeddingRequest(text=request.query)
                )
            except EmbeddingGenerationError as exc:
                semantic_generation_skipped_reason = (
                    f"embedding_generation_failed:{exc.provider}"
                )
            else:
                semantic_query_generated = True
                semantic_matches = self._memory_embedding_repository.find_similar(
                    semantic_query.vector,
                    limit=request.limit,
                    workspace_id=workspace_id,
                )

        semantic_score_by_memory_id: dict[UUID, float] = {}
        semantic_matched_fields_by_memory_id: dict[UUID, tuple[str, ...]] = {}
        semantic_result_count = len(semantic_matches)

        if semantic_matches:
            semantic_rank_floor = 0.25
            semantic_rank_denominator = max(len(semantic_matches) - 1, 1)
            top_similarity = _embedding_dot_product(
                semantic_matches[0].embedding,
                semantic_query.vector,
            )
            bottom_similarity = top_similarity
            if len(semantic_matches) > 1:
                bottom_similarity = _embedding_dot_product(
                    semantic_matches[-1].embedding,
                    semantic_query.vector,
                )
            similarity_range = max(top_similarity - bottom_similarity, 0.0)

            for index, embedding_match in enumerate(semantic_matches):
                raw_similarity = _embedding_dot_product(
                    embedding_match.embedding,
                    semantic_query.vector,
                )
                rank_component = semantic_rank_floor + (
                    (1.0 - semantic_rank_floor)
                    * (
                        float(semantic_rank_denominator - index)
                        / float(semantic_rank_denominator)
                    )
                )
                similarity_component = 1.0
                if similarity_range > 0:
                    normalized_similarity = max(
                        0.0,
                        min(
                            1.0,
                            (raw_similarity - bottom_similarity) / similarity_range,
                        ),
                    )
                    if raw_similarity >= top_similarity:
                        similarity_component = 1.0
                    elif raw_similarity <= bottom_similarity:
                        similarity_component = 0.0
                    else:
                        similarity_component = semantic_rank_floor + (
                            (1.0 - semantic_rank_floor) * normalized_similarity
                        )
                semantic_score = rank_component * similarity_component
                current_best = semantic_score_by_memory_id.get(
                    embedding_match.memory_id,
                    0.0,
                )
                if semantic_score > current_best:
                    semantic_score_by_memory_id[embedding_match.memory_id] = (
                        semantic_score
                    )
                    semantic_matched_fields_by_memory_id[embedding_match.memory_id] = (
                        "embedding_similarity",
                    )

        scored_results: list[SearchResultRecord] = []
        lexical_weight = 1.0
        semantic_weight = 1.0
        semantic_only_discount = 0.75

        for memory_item in memory_items:
            lexical_score, matched_fields = self._score_memory_item_for_query(
                memory_item=memory_item,
                normalized_query=normalized_query,
            )
            semantic_score = semantic_score_by_memory_id.get(memory_item.memory_id, 0.0)
            semantic_fields = semantic_matched_fields_by_memory_id.get(
                memory_item.memory_id,
                (),
            )

            combined_fields = tuple(dict.fromkeys((*matched_fields, *semantic_fields)))
            lexical_component = lexical_score * lexical_weight
            semantic_component = semantic_score * semantic_weight
            score_mode = "hybrid"

            hybrid_score = lexical_component + semantic_component
            if lexical_score <= 0 and semantic_score > 0:
                hybrid_score = semantic_component * semantic_only_discount
                score_mode = "semantic_only_discounted"
            elif lexical_score > 0 and semantic_score <= 0:
                score_mode = "lexical_only"

            if hybrid_score <= 0:
                continue

            scored_results.append(
                SearchResultRecord(
                    memory_id=memory_item.memory_id,
                    workspace_id=memory_item.workspace_id,
                    episode_id=memory_item.episode_id,
                    workflow_instance_id=None,
                    summary=memory_item.content,
                    attempt_id=None,
                    metadata=dict(memory_item.metadata),
                    score=hybrid_score,
                    matched_fields=combined_fields,
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                    ranking_details={
                        "lexical_component": lexical_component,
                        "semantic_component": semantic_component,
                        "score_mode": score_mode,
                        "semantic_only_discount_applied": (
                            lexical_score <= 0 and semantic_score > 0
                        ),
                    },
                    created_at=memory_item.created_at,
                    updated_at=memory_item.updated_at,
                )
            )

        scored_results.sort(
            key=lambda result: (
                result.score,
                result.semantic_score,
                result.lexical_score,
                result.created_at,
            ),
            reverse=True,
        )
        limited_results = tuple(scored_results[: request.limit])

        search_mode = (
            "hybrid_memory_item_search"
            if semantic_query_generated
            else "memory_item_lexical"
        )
        message = (
            "Hybrid lexical and semantic memory search completed successfully."
            if semantic_query_generated
            else "Memory-item-based lexical search completed successfully."
        )

        result_mode_counts = {
            "hybrid": 0,
            "lexical_only": 0,
            "semantic_only_discounted": 0,
        }
        result_composition = {
            "with_lexical_signal": 0,
            "with_semantic_signal": 0,
            "with_both_signals": 0,
        }
        for result in limited_results:
            score_mode = str(result.ranking_details.get("score_mode", "hybrid"))
            if score_mode in result_mode_counts:
                result_mode_counts[score_mode] += 1
            has_lexical_signal = result.lexical_score > 0.0
            has_semantic_signal = result.semantic_score > 0.0
            if has_lexical_signal:
                result_composition["with_lexical_signal"] += 1
            if has_semantic_signal:
                result_composition["with_semantic_signal"] += 1
            if has_lexical_signal and has_semantic_signal:
                result_composition["with_both_signals"] += 1

        details = {
            "query": request.query,
            "normalized_query": normalized_query,
            "workspace_id": request.workspace_id,
            "limit": request.limit,
            "filters": request.filters,
            "search_mode": search_mode,
            "memory_items_considered": len(memory_items),
            "semantic_candidates_considered": semantic_result_count,
            "semantic_query_generated": semantic_query_generated,
            "hybrid_scoring": {
                "lexical_weight": lexical_weight,
                "semantic_weight": semantic_weight,
                "semantic_only_discount": semantic_only_discount,
            },
            "result_mode_counts": result_mode_counts,
            "result_composition": result_composition,
            "results_returned": len(limited_results),
        }
        if semantic_generation_skipped_reason is not None:
            details["semantic_generation_skipped_reason"] = (
                semantic_generation_skipped_reason
            )

        return SearchMemoryResponse(
            feature=MemoryFeature.SEARCH,
            implemented=True,
            message=message,
            status="ok",
            available_in_version="0.3.0",
            results=limited_results,
            details=details,
        )

    def get_context(self, request: GetMemoryContextRequest) -> GetContextResponse:
        """Return episode-oriented auxiliary context.

        This operation remains intentionally separate from workflow resume. It
        returns support context rather than canonical operational state.

        In the current implementation stage, retrieval is episode-oriented and
        keyed primarily by workflow_instance_id.
        """
        if not any(
            [
                self._has_text(request.query),
                self._has_text(request.workspace_id),
                self._has_text(request.workflow_instance_id),
                self._has_text(request.ticket_id),
            ]
        ):
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=MemoryFeature.GET_CONTEXT,
                message=(
                    "At least one of query, workspace_id, workflow_instance_id, "
                    "or ticket_id must be provided."
                ),
                details={},
            )

        self._require_positive_limit(
            request.limit,
            feature=MemoryFeature.GET_CONTEXT,
        )

        lookup_scope = "query"
        resolved_workflow_ids: tuple[UUID, ...] = ()
        resolved_workflow_instance_id: str | None = None
        normalized_query = _normalize_query_text(request.query)
        query_tokens = _query_tokens(normalized_query)
        workspace_workflow_ids: tuple[UUID, ...] = ()
        ticket_workflow_ids: tuple[UUID, ...] = ()
        resolver_ordered_workflow_ids: tuple[UUID, ...] = ()
        ordering_signals: dict[str, dict[str, str | None]] = {}

        if self._has_text(request.workflow_instance_id):
            lookup_scope = "workflow_instance"
            workflow_instance_id = self._parse_uuid(
                request.workflow_instance_id or "",
                field_name="workflow_instance_id",
                feature=MemoryFeature.GET_CONTEXT,
            )
            if (
                self._workflow_lookup is not None
                and not self._workflow_lookup.workflow_exists(workflow_instance_id)
            ):
                raise MemoryServiceError(
                    code=MemoryErrorCode.WORKFLOW_NOT_FOUND,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="workflow_instance_id was not found.",
                    details={"workflow_instance_id": str(workflow_instance_id)},
                )
            resolved_workflow_ids = (workflow_instance_id,)
            resolved_workflow_instance_id = str(workflow_instance_id)
        elif self._workflow_lookup is not None:
            if self._has_text(request.workspace_id):
                workspace_workflow_ids = (
                    self._workflow_lookup.workflow_ids_by_workspace_id(
                        request.workspace_id or "",
                        limit=request.limit,
                    )
                )

            if self._has_text(request.ticket_id):
                ticket_workflow_ids = self._workflow_lookup.workflow_ids_by_ticket_id(
                    request.ticket_id or "",
                    limit=request.limit,
                )

            if workspace_workflow_ids and ticket_workflow_ids:
                lookup_scope = "workspace_and_ticket"
                ticket_workflow_id_set = set(ticket_workflow_ids)
                resolver_ordered_workflow_ids = tuple(
                    workflow_id
                    for workflow_id in workspace_workflow_ids
                    if workflow_id in ticket_workflow_id_set
                )[: request.limit]
            elif workspace_workflow_ids:
                lookup_scope = "workspace"
                resolver_ordered_workflow_ids = workspace_workflow_ids
            elif ticket_workflow_ids:
                lookup_scope = "ticket"
                resolver_ordered_workflow_ids = ticket_workflow_ids

        signal_ordered_workflow_ids = (
            self._order_workflow_ids_by_freshness_signals(
                workflow_ids=resolver_ordered_workflow_ids,
                limit=request.limit,
            )
            if resolved_workflow_instance_id is None
            else resolved_workflow_ids
        )
        if resolved_workflow_instance_id is None:
            resolved_workflow_ids = signal_ordered_workflow_ids
            ordering_signals = self._workflow_ordering_signals(
                workflow_ids=resolved_workflow_ids
            )
        elif resolved_workflow_ids:
            ordering_signals = self._workflow_ordering_signals(
                workflow_ids=resolved_workflow_ids
            )

        details = {
            "query": request.query,
            "normalized_query": normalized_query,
            "query_tokens": list(query_tokens),
            "lookup_scope": lookup_scope,
            "workspace_id": request.workspace_id,
            "workflow_instance_id": resolved_workflow_instance_id,
            "ticket_id": request.ticket_id,
            "limit": request.limit,
            "include_episodes": request.include_episodes,
            "include_memory_items": request.include_memory_items,
            "include_summaries": request.include_summaries,
            "workflow_candidate_ordering": {
                "ordering_basis": (
                    "workflow_instance_id_priority"
                    if resolved_workflow_instance_id is not None
                    else "workflow_freshness_signals"
                ),
                "workflow_instance_id_priority_applied": (
                    resolved_workflow_instance_id is not None
                ),
                "signal_priority": [
                    "workflow_is_terminal",
                    "latest_attempt_is_terminal",
                    "has_latest_attempt",
                    "has_latest_checkpoint",
                    "latest_checkpoint_created_at",
                    "latest_verify_report_created_at",
                    "latest_projection_canonical_update_at",
                    "latest_projection_successful_write_at",
                    "projection_open_failure_count",
                    "latest_episode_created_at",
                    "latest_attempt_started_at",
                    "workflow_updated_at",
                    "resolver_order",
                ],
                "workspace_candidate_ids": [
                    str(workflow_id) for workflow_id in workspace_workflow_ids
                ],
                "ticket_candidate_ids": [
                    str(workflow_id) for workflow_id in ticket_workflow_ids
                ],
                "resolver_candidate_ids": [
                    str(workflow_id) for workflow_id in resolver_ordered_workflow_ids
                ],
                "final_candidate_ids": [
                    str(workflow_id) for workflow_id in resolved_workflow_ids
                ],
                "candidate_signals": ordering_signals,
            },
            "resolved_workflow_count": len(resolved_workflow_ids),
            "resolved_workflow_ids": [
                str(workflow_id) for workflow_id in resolved_workflow_ids
            ],
        }

        if not request.include_episodes:
            return GetContextResponse(
                feature=MemoryFeature.GET_CONTEXT,
                implemented=True,
                message="Episode-oriented memory context retrieved successfully.",
                status="ok",
                available_in_version="0.2.0",
                episodes=(),
                details={
                    **details,
                    "query_filter_applied": False,
                    "episodes_before_query_filter": 0,
                    "matched_episode_count": 0,
                    "episodes_returned": 0,
                    "episode_explanations": [],
                    "memory_items": [],
                    "memory_item_counts_by_episode": {},
                    "summaries": [],
                },
            )

        episodes = self._collect_episode_context(
            workflow_ids=resolved_workflow_ids,
            limit=request.limit,
        )
        episodes_before_query_filter = len(episodes)
        episode_explanations_before_query_filter = self._build_episode_explanations(
            episodes=episodes,
            normalized_query=normalized_query,
            query_tokens=query_tokens,
        )
        memory_item_details_before_query_filter = (
            self._build_memory_item_details_for_episodes(
                episodes=episodes,
                include_memory_items=request.include_memory_items,
                include_summaries=request.include_summaries,
            )
        )

        if normalized_query is not None:
            filtered_episodes: list[EpisodeRecord] = []
            filtered_episode_explanations: list[dict[str, Any]] = []
            filtered_memory_item_details: list[dict[str, Any]] = []

            for episode, explanation, memory_item_detail in zip(
                episodes,
                episode_explanations_before_query_filter,
                memory_item_details_before_query_filter,
                strict=False,
            ):
                if bool(explanation["matched"]):
                    filtered_episodes.append(episode)
                    filtered_episode_explanations.append(explanation)
                    filtered_memory_item_details.append(memory_item_detail)

            episodes = tuple(filtered_episodes)
            episode_explanations = tuple(filtered_episode_explanations)
            memory_item_details = tuple(filtered_memory_item_details)
        else:
            episode_explanations = tuple(episode_explanations_before_query_filter)
            memory_item_details = tuple(memory_item_details_before_query_filter)

        matched_episode_count = len(episodes)
        summaries = tuple(
            detail["summary"]
            for detail in memory_item_details
            if isinstance(detail.get("summary"), dict)
        )

        return GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            episodes=episodes,
            details={
                **details,
                "query_filter_applied": normalized_query is not None,
                "episodes_before_query_filter": episodes_before_query_filter,
                "matched_episode_count": matched_episode_count,
                "episodes_returned": len(episodes),
                "episode_explanations": list(episode_explanations),
                "memory_items": [
                    detail["memory_items"]
                    for detail in memory_item_details
                    if isinstance(detail.get("memory_items"), list)
                ],
                "memory_item_counts_by_episode": {
                    detail["episode_id"]: detail["memory_item_count"]
                    for detail in memory_item_details
                },
                "summaries": list(summaries),
            },
        )

    def _not_implemented(
        self,
        *,
        feature: MemoryFeature,
        message: str,
        details: dict[str, Any],
    ) -> StubResponse:
        return StubResponse(
            feature=feature,
            implemented=False,
            message=message,
            available_in_version=None,
            details=details,
        )

    def _require_non_empty(
        self,
        value: str,
        *,
        field_name: str,
        feature: MemoryFeature,
    ) -> None:
        if not self._has_text(value):
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message=f"{field_name} must be a non-empty string.",
                details={"field": field_name},
            )

    def _require_positive_limit(
        self,
        value: int,
        *,
        feature: MemoryFeature,
    ) -> None:
        if value <= 0:
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message="limit must be a positive integer.",
                details={"field": "limit", "value": value},
            )

    def _collect_episode_context(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        if not workflow_ids:
            return ()

        workflow_episode_lists = [
            self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=limit,
            )
            for workflow_id in workflow_ids
        ]

        episodes: list[EpisodeRecord] = []
        seen_episode_ids: set[UUID] = set()
        round_index = 0

        while len(episodes) < limit:
            added_in_round = False

            for workflow_episodes in workflow_episode_lists:
                if round_index >= len(workflow_episodes):
                    continue

                episode = workflow_episodes[round_index]
                if episode.episode_id in seen_episode_ids:
                    continue

                seen_episode_ids.add(episode.episode_id)
                episodes.append(episode)
                added_in_round = True

                if len(episodes) >= limit:
                    break

            if not added_in_round:
                break

            round_index += 1

        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])

    def _order_workflow_ids_by_freshness_signals(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
        limit: int,
    ) -> tuple[UUID, ...]:
        if not workflow_ids:
            return ()

        workflow_recencies: list[
            tuple[
                bool,
                bool,
                bool,
                bool,
                datetime,
                datetime,
                datetime,
                datetime,
                int,
                datetime,
                datetime,
                datetime,
                int,
                UUID,
            ]
        ] = []

        for index, workflow_id in enumerate(workflow_ids):
            freshness = (
                self._workflow_lookup.workflow_freshness_by_id(workflow_id)
                if self._workflow_lookup is not None
                else {}
            )
            latest_episode = self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=1,
            )
            workflow_is_terminal = bool(freshness.get("workflow_is_terminal") or False)
            latest_attempt_is_terminal = bool(
                freshness.get("latest_attempt_is_terminal") or False
            )
            has_latest_attempt = bool(freshness.get("has_latest_attempt") or False)
            has_latest_checkpoint = bool(
                freshness.get("has_latest_checkpoint") or False
            )
            latest_checkpoint_created_at = freshness.get(
                "latest_checkpoint_created_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_verify_report_created_at = freshness.get(
                "latest_verify_report_created_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_projection_canonical_update_at = freshness.get(
                "latest_projection_canonical_update_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_projection_successful_write_at = freshness.get(
                "latest_projection_successful_write_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            projection_open_failure_count = int(
                freshness.get("projection_open_failure_count", 0) or 0
            )
            latest_episode_created_at = (
                latest_episode[0].created_at
                if latest_episode
                else datetime.min.replace(tzinfo=timezone.utc)
            )
            latest_attempt_started_at = freshness.get(
                "latest_attempt_started_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            workflow_updated_at = freshness.get(
                "workflow_updated_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            workflow_recencies.append(
                (
                    not workflow_is_terminal,
                    not latest_attempt_is_terminal,
                    has_latest_attempt,
                    has_latest_checkpoint,
                    latest_checkpoint_created_at,
                    latest_verify_report_created_at,
                    latest_projection_canonical_update_at,
                    latest_projection_successful_write_at,
                    -projection_open_failure_count,
                    latest_episode_created_at,
                    latest_attempt_started_at,
                    workflow_updated_at,
                    -index,
                    workflow_id,
                )
            )

        workflow_recencies.sort(reverse=True)
        return tuple(workflow_id for *_, workflow_id in workflow_recencies[:limit])

    def _workflow_ordering_signals(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
    ) -> dict[str, dict[str, str | None]]:
        signals: dict[str, dict[str, str | None]] = {}

        for workflow_id in workflow_ids:
            freshness = (
                self._workflow_lookup.workflow_freshness_by_id(workflow_id)
                if self._workflow_lookup is not None
                else {}
            )
            latest_episode = self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=1,
            )
            signals[str(workflow_id)] = {
                "workflow_status": (
                    str(freshness.get("workflow_status"))
                    if freshness.get("workflow_status") is not None
                    else None
                ),
                "workflow_is_terminal": (
                    bool(freshness.get("workflow_is_terminal"))
                    if freshness.get("workflow_is_terminal") is not None
                    else None
                ),
                "latest_attempt_status": (
                    str(freshness.get("latest_attempt_status"))
                    if freshness.get("latest_attempt_status") is not None
                    else None
                ),
                "latest_attempt_is_terminal": (
                    bool(freshness.get("latest_attempt_is_terminal"))
                    if freshness.get("latest_attempt_is_terminal") is not None
                    else None
                ),
                "has_latest_attempt": (
                    bool(freshness.get("has_latest_attempt"))
                    if freshness.get("has_latest_attempt") is not None
                    else None
                ),
                "latest_attempt_verify_status": (
                    str(freshness.get("latest_attempt_verify_status"))
                    if freshness.get("latest_attempt_verify_status") is not None
                    else None
                ),
                "has_latest_checkpoint": (
                    bool(freshness.get("has_latest_checkpoint"))
                    if freshness.get("has_latest_checkpoint") is not None
                    else None
                ),
                "latest_checkpoint_created_at": (
                    freshness.get("latest_checkpoint_created_at").isoformat()
                    if freshness.get("latest_checkpoint_created_at") is not None
                    else None
                ),
                "latest_verify_report_created_at": (
                    freshness.get("latest_verify_report_created_at").isoformat()
                    if freshness.get("latest_verify_report_created_at") is not None
                    else None
                ),
                "latest_projection_canonical_update_at": (
                    freshness.get("latest_projection_canonical_update_at").isoformat()
                    if freshness.get("latest_projection_canonical_update_at")
                    is not None
                    else None
                ),
                "latest_projection_successful_write_at": (
                    freshness.get("latest_projection_successful_write_at").isoformat()
                    if freshness.get("latest_projection_successful_write_at")
                    is not None
                    else None
                ),
                "projection_open_failure_count": int(
                    freshness.get("projection_open_failure_count", 0) or 0
                ),
                "latest_episode_created_at": (
                    latest_episode[0].created_at.isoformat() if latest_episode else None
                ),
                "latest_attempt_started_at": (
                    freshness.get("latest_attempt_started_at").isoformat()
                    if freshness.get("latest_attempt_started_at") is not None
                    else None
                ),
                "workflow_updated_at": (
                    freshness.get("workflow_updated_at").isoformat()
                    if freshness.get("workflow_updated_at") is not None
                    else None
                ),
            }

        return signals

    def _build_episode_explanations(
        self,
        *,
        episodes: tuple[EpisodeRecord, ...],
        normalized_query: str | None,
        query_tokens: tuple[str, ...],
    ) -> tuple[dict[str, Any], ...]:
        explanations: list[dict[str, Any]] = []

        for episode in episodes:
            summary_match = False
            metadata_matches: list[str] = []

            if normalized_query is None:
                explanation_basis = "unfiltered_episode_context"
            else:
                summary_match = _text_matches_query(
                    text=episode.summary,
                    normalized_query=normalized_query,
                    query_tokens=query_tokens,
                )
                metadata_matches = [
                    metadata_query_string
                    for metadata_query_string in _metadata_query_strings(
                        episode.metadata
                    )
                    if _text_matches_query(
                        text=metadata_query_string,
                        normalized_query=normalized_query,
                        query_tokens=query_tokens,
                    )
                ]
                explanation_basis = "query_match_evaluation"

            explanations.append(
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(episode.workflow_instance_id),
                    "matched": (
                        True
                        if normalized_query is None
                        else summary_match or bool(metadata_matches)
                    ),
                    "explanation_basis": explanation_basis,
                    "matched_summary": summary_match,
                    "matched_metadata_values": metadata_matches,
                }
            )

        return tuple(explanations)

    def _build_memory_item_details_for_episodes(
        self,
        *,
        episodes: tuple[EpisodeRecord, ...],
        include_memory_items: bool,
        include_summaries: bool,
    ) -> tuple[dict[str, Any], ...]:
        details: list[dict[str, Any]] = []

        for episode in episodes:
            memory_items = self._memory_item_repository.list_by_episode_id(
                episode.episode_id,
                limit=100,
            )
            memory_item_count = len(memory_items)
            detail: dict[str, Any] = {
                "episode_id": str(episode.episode_id),
                "memory_item_count": memory_item_count,
            }

            if include_memory_items:
                detail["memory_items"] = [
                    {
                        "memory_id": str(memory_item.memory_id),
                        "workspace_id": (
                            str(memory_item.workspace_id)
                            if memory_item.workspace_id is not None
                            else None
                        ),
                        "episode_id": (
                            str(memory_item.episode_id)
                            if memory_item.episode_id is not None
                            else None
                        ),
                        "type": memory_item.type,
                        "provenance": memory_item.provenance,
                        "content": memory_item.content,
                        "metadata": dict(memory_item.metadata),
                        "created_at": memory_item.created_at.isoformat(),
                        "updated_at": memory_item.updated_at.isoformat(),
                    }
                    for memory_item in memory_items
                ]

            if include_summaries:
                detail["summary"] = {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(episode.workflow_instance_id),
                    "memory_item_count": memory_item_count,
                    "memory_item_types": [
                        memory_item.type for memory_item in memory_items
                    ],
                    "memory_item_provenance": [
                        memory_item.provenance for memory_item in memory_items
                    ],
                }

            details.append(detail)

        return tuple(details)

    def _score_memory_item_for_query(
        self,
        *,
        memory_item: MemoryItemRecord,
        normalized_query: str,
    ) -> tuple[float, tuple[str, ...]]:
        score = 0.0
        matched_fields: list[str] = []

        content_text = memory_item.content.casefold()
        if normalized_query in content_text:
            score += 3.0
            matched_fields.append("content")

        metadata_strings = _metadata_query_strings(memory_item.metadata)
        metadata_key_match = False
        metadata_value_match = False

        for index, metadata_query_string in enumerate(metadata_strings):
            if normalized_query not in metadata_query_string:
                continue
            if index % 2 == 0:
                metadata_key_match = True
            else:
                metadata_value_match = True

        if metadata_key_match:
            score += 1.5
            matched_fields.append("metadata_keys")
        if metadata_value_match:
            score += 1.5
            matched_fields.append("metadata_values")

        return score, tuple(matched_fields)

    def _parse_uuid(
        self,
        value: str,
        *,
        field_name: str,
        feature: MemoryFeature,
    ) -> UUID:
        try:
            return UUID(value.strip())
        except AttributeError, ValueError:
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message=f"{field_name} must be a valid UUID string.",
                details={"field": field_name},
            ) from None

    def _maybe_store_embedding(self, memory_item: MemoryItemRecord) -> dict[str, Any]:
        if (
            self._embedding_generator is None
            or self._memory_embedding_repository is None
        ):
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": (
                    "embedding_persistence_not_configured"
                ),
            }

        try:
            result = self._embedding_generator.generate(
                EmbeddingRequest(
                    text=memory_item.content,
                    metadata=memory_item.metadata,
                )
            )
        except EmbeddingGenerationError as exc:
            failure_reason = f"embedding_generation_failed:{exc.provider}"
            details: dict[str, Any] = {
                "embedding_persistence_status": "failed",
                "embedding_generation_skipped_reason": failure_reason,
                "embedding_generation_failure": {
                    "provider": exc.provider,
                    "message": str(exc),
                    "details": dict(exc.details),
                },
            }
            return details

        self._memory_embedding_repository.create(
            MemoryEmbeddingRecord(
                memory_embedding_id=uuid4(),
                memory_id=memory_item.memory_id,
                embedding_model=result.model,
                embedding=result.vector,
                content_hash=result.content_hash,
                created_at=memory_item.updated_at,
            )
        )
        return {
            "embedding_persistence_status": "stored",
            "embedding_generation_skipped_reason": None,
            "embedding_provider": result.provider,
            "embedding_model": result.model,
            "embedding_vector_dimensions": len(result.vector),
            "embedding_content_hash": result.content_hash,
        }

    def _resolve_workspace_id(self, workflow_instance_id: UUID) -> UUID | None:
        if self._workspace_lookup is None:
            return None
        return self._workspace_lookup.workspace_id_by_workflow_id(workflow_instance_id)

    @staticmethod
    def _has_text(value: object | None) -> bool:
        return isinstance(value, str) and bool(value.strip())
