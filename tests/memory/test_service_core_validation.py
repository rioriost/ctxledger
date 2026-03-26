from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
)
from ctxledger.memory.service import (
    BuildEpisodeSummaryRequest,
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
)


def test_memory_service_raises_validation_errors_for_invalid_requests() -> None:
    workflow_id = uuid4()
    service = MemoryService(
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    with pytest.raises(MemoryServiceError) as remember_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id="   ",
                summary="Episode summary",
            )
        )
    assert remember_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert remember_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert remember_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as invalid_uuid_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id="not-a-uuid",
                summary="Episode summary",
            )
        )
    assert invalid_uuid_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert invalid_uuid_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert invalid_uuid_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as missing_workflow_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(uuid4()),
                summary="Episode summary",
            )
        )
    assert missing_workflow_error.value.code == MemoryErrorCode.WORKFLOW_NOT_FOUND
    assert missing_workflow_error.value.feature == MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as search_error:
        service.search(
            SearchMemoryRequest(
                query="valid query",
                limit=0,
            )
        )
    assert search_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert search_error.value.feature == MemoryFeature.SEARCH
    assert search_error.value.details == {"field": "limit", "value": 0}

    with pytest.raises(MemoryServiceError) as context_error:
        service.get_context(
            GetMemoryContextRequest(
                query=None,
                workspace_id=None,
                workflow_instance_id=None,
                ticket_id=None,
                limit=1,
            )
        )
    assert context_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert context_error.value.feature == MemoryFeature.GET_CONTEXT
    assert (
        context_error.value.message
        == "At least one of query, workspace_id, workflow_instance_id, or ticket_id must be provided."
    )
