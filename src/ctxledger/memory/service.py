"""Compatibility facade for the split memory service modules.

This module preserves the historical import surface of
``ctxledger.memory.service`` while delegating implementation ownership to the
smaller split modules.

The compatibility contract for existing callers is:

- request / response shapes and error types remain importable here
- repository protocol contracts remain importable here
- in-memory and UnitOfWork-backed repository implementations remain importable here
- ``MemoryService`` is re-exported from ``ctxledger.memory.service_core``

A few constructor-related symbols are also re-exported here so legacy tests and
callers that monkeypatch the old module surface can keep working during the
transition.
"""

from ..config import get_settings
from .embeddings import (
    EmbeddingGenerationError,
    EmbeddingGenerator,
    EmbeddingRequest,
    build_embedding_generator,
)
from .helpers import (
    embedding_dot_product,
    metadata_query_strings,
    normalize_query_text,
    query_tokens,
    text_matches_query,
)
from .protocols import (
    EpisodeRepository,
    MemoryEmbeddingRepository,
    MemoryItemRepository,
    MemoryRelationMemoryItemLookupRepository,
    MemoryRelationRepository,
    MemorySummaryMembershipRepository,
    MemorySummaryRepository,
    WorkflowLookupRepository,
    WorkspaceLookupRepository,
)
from .repositories import (
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkMemoryRelationRepository,
    UnitOfWorkMemorySummaryMembershipRepository,
    UnitOfWorkMemorySummaryRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from .service_core import MemoryService
from .types import (
    BuildEpisodeSummaryRequest,
    BuildEpisodeSummaryResult,
    EpisodeRecord,
    GetContextResponse,
    GetMemoryContextRequest,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)

__all__ = [
    "EpisodeRecord",
    "GetContextResponse",
    "GetMemoryContextRequest",
    "InMemoryEpisodeRepository",
    "InMemoryMemoryEmbeddingRepository",
    "InMemoryMemoryItemRepository",
    "InMemoryMemoryRelationRepository",
    "InMemoryWorkflowLookupRepository",
    "MemoryEmbeddingRecord",
    "MemoryErrorCode",
    "MemoryFeature",
    "MemoryItemRecord",
    "MemoryRelationRecord",
    "MemoryService",
    "MemoryServiceError",
    "BuildEpisodeSummaryRequest",
    "BuildEpisodeSummaryResult",
    "MemorySummaryMembershipRecord",
    "MemorySummaryRecord",
    "RememberEpisodeRequest",
    "RememberEpisodeResponse",
    "SearchMemoryRequest",
    "SearchMemoryResponse",
    "SearchResultRecord",
    "StubResponse",
    "UnitOfWorkEpisodeRepository",
    "UnitOfWorkMemoryEmbeddingRepository",
    "UnitOfWorkMemoryItemRepository",
    "UnitOfWorkMemoryRelationRepository",
    "UnitOfWorkMemorySummaryMembershipRepository",
    "UnitOfWorkMemorySummaryRepository",
    "UnitOfWorkWorkflowLookupRepository",
    "UnitOfWorkWorkspaceLookupRepository",
    "WorkflowLookupRepository",
    "WorkspaceLookupRepository",
    "EpisodeRepository",
    "MemoryEmbeddingRepository",
    "MemoryItemRepository",
    "MemoryRelationMemoryItemLookupRepository",
    "MemoryRelationRepository",
    "MemorySummaryMembershipRepository",
    "MemorySummaryRepository",
    "EmbeddingGenerationError",
    "EmbeddingGenerator",
    "EmbeddingRequest",
    "build_embedding_generator",
    "embedding_dot_product",
    "get_settings",
    "metadata_query_strings",
    "normalize_query_text",
    "query_tokens",
    "text_matches_query",
    "InMemoryMemorySummaryMembershipRepository",
    "InMemoryMemorySummaryRepository",
]
