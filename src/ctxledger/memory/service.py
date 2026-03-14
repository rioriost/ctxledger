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


def _normalize_query_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized.casefold() if normalized else None


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
        workflows_by_id: dict[UUID, dict[str, str]] | None = None,
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
        self._maybe_store_embedding(memory_item)

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
            },
        )

    def search(self, request: SearchMemoryRequest) -> SearchMemoryResponse:
        """Return initial memory-item-based lexical search results."""
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

        scored_results: list[SearchResultRecord] = []
        for memory_item in memory_items:
            score, matched_fields = self._score_memory_item_for_query(
                memory_item=memory_item,
                normalized_query=normalized_query,
            )
            if score <= 0:
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
                    score=score,
                    matched_fields=matched_fields,
                    created_at=memory_item.created_at,
                    updated_at=memory_item.updated_at,
                )
            )

        scored_results.sort(
            key=lambda result: (result.score, result.created_at),
            reverse=True,
        )
        limited_results = tuple(scored_results[: request.limit])

        return SearchMemoryResponse(
            feature=MemoryFeature.SEARCH,
            implemented=True,
            message="Memory-item-based lexical search completed successfully.",
            status="ok",
            available_in_version="0.3.0",
            results=limited_results,
            details={
                "query": request.query,
                "normalized_query": normalized_query,
                "workspace_id": request.workspace_id,
                "limit": request.limit,
                "filters": request.filters,
                "search_mode": "memory_item_lexical",
                "memory_items_considered": len(memory_items),
                "results_returned": len(limited_results),
            },
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
        elif self._has_text(request.workspace_id) and self._workflow_lookup is not None:
            lookup_scope = "workspace"
            resolved_workflow_ids = self._workflow_lookup.workflow_ids_by_workspace_id(
                request.workspace_id or "",
                limit=request.limit,
            )
        elif self._has_text(request.ticket_id) and self._workflow_lookup is not None:
            lookup_scope = "ticket"
            resolved_workflow_ids = self._workflow_lookup.workflow_ids_by_ticket_id(
                request.ticket_id or "",
                limit=request.limit,
            )

        details = {
            "query": request.query,
            "normalized_query": normalized_query,
            "lookup_scope": lookup_scope,
            "workspace_id": request.workspace_id,
            "workflow_instance_id": resolved_workflow_instance_id,
            "ticket_id": request.ticket_id,
            "limit": request.limit,
            "include_episodes": request.include_episodes,
            "include_memory_items": request.include_memory_items,
            "include_summaries": request.include_summaries,
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
                },
            )

        episodes = self._collect_episode_context(
            workflow_ids=resolved_workflow_ids,
            limit=request.limit,
        )
        episodes_before_query_filter = len(episodes)

        if normalized_query is not None:
            episodes = tuple(
                episode
                for episode in episodes
                if normalized_query in episode.summary.casefold()
                or any(
                    normalized_query in metadata_query_string
                    for metadata_query_string in _metadata_query_strings(
                        episode.metadata
                    )
                )
            )

        matched_episode_count = len(episodes)

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

        episodes: list[EpisodeRecord] = []
        seen_episode_ids: set[UUID] = set()

        for workflow_id in workflow_ids:
            for episode in self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=limit,
            ):
                if episode.episode_id in seen_episode_ids:
                    continue
                seen_episode_ids.add(episode.episode_id)
                episodes.append(episode)

        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])

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

    def _maybe_store_embedding(self, memory_item: MemoryItemRecord) -> None:
        if (
            self._embedding_generator is None
            or self._memory_embedding_repository is None
        ):
            return

        try:
            result = self._embedding_generator.generate(
                EmbeddingRequest(
                    text=memory_item.content,
                    metadata=memory_item.metadata,
                )
            )
        except EmbeddingGenerationError:
            return

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

    def _resolve_workspace_id(self, workflow_instance_id: UUID) -> UUID | None:
        if self._workspace_lookup is None:
            return None
        return self._workspace_lookup.workspace_id_by_workflow_id(workflow_instance_id)

    @staticmethod
    def _has_text(value: object | None) -> bool:
        return isinstance(value, str) and bool(value.strip())
