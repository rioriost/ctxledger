from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.config import (
    EmbeddingProvider,
    EmbeddingSettings,
)
from ctxledger.memory.embeddings import (
    DisabledEmbeddingGenerator,
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
    ExternalAPIEmbeddingGenerator,
    LocalStubEmbeddingGenerator,
    build_embedding_generator,
    compute_content_hash,
)
from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)
from ctxledger.memory.types import MemoryRelationRecord
from ctxledger.runtime.introspection import RuntimeIntrospection
from ctxledger.runtime.serializers import (
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
    serialize_search_memory_response,
    serialize_stub_response,
)
from ctxledger.workflow.service import (
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstance,
    WorkflowInstanceStatus,
)


def test_serialize_stub_response_and_runtime_introspection_helpers() -> None:
    stub_response = StubResponse(
        feature=MemoryFeature.SEARCH,
        implemented=False,
        message="Not implemented",
        details={"limit": 10},
    )
    introspection = RuntimeIntrospection(
        transport="http",
        routes=("route_a",),
        tools=("tool_a",),
        resources=("resource_a",),
    )

    serialized_stub = serialize_stub_response(stub_response)
    serialized_runtime = serialize_runtime_introspection(introspection)
    serialized_collection = serialize_runtime_introspection_collection((introspection,))

    assert serialized_stub["feature"] == "memory_search"
    assert serialized_stub["implemented"] is False
    assert serialized_runtime == {
        "transport": "http",
        "routes": ["route_a"],
        "tools": ["tool_a"],
        "resources": ["resource_a"],
    }
    assert serialized_collection == [serialized_runtime]


def test_serialize_search_memory_response_serializes_results() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 3, 4, 5, 6, 7, tzinfo=UTC)
    response = SearchMemoryResponse(
        feature=MemoryFeature.SEARCH,
        implemented=True,
        message="Hybrid lexical and semantic memory search completed successfully.",
        status="ok",
        available_in_version="0.3.0",
        timestamp=created_at,
        results=(
            SearchResultRecord(
                memory_id=uuid4(),
                workspace_id=workflow_id,
                episode_id=uuid4(),
                workflow_instance_id=None,
                summary="Recovered context",
                attempt_id=attempt_id,
                metadata={"kind": "root-cause"},
                score=4.5,
                matched_fields=("content", "embedding_similarity"),
                lexical_score=3.0,
                semantic_score=0.75,
                ranking_details={
                    "lexical_component": 3.0,
                    "semantic_component": 0.75,
                    "score_mode": "hybrid",
                    "semantic_only_discount_applied": False,
                    "reason_list": [
                        {
                            "code": "lexical_signal_present",
                            "message": "lexical overlap contributed to the ranking score",
                            "value": 3.0,
                        },
                        {
                            "code": "semantic_signal_present",
                            "message": "semantic similarity contributed to the ranking score",
                            "value": 0.75,
                        },
                        {
                            "code": "hybrid_score_mode",
                            "message": "both lexical and semantic components were combined",
                        },
                    ],
                    "task_recall_detail": {
                        "matched_fields": ["content", "embedding_similarity"],
                        "memory_item_type": "episode_note",
                        "memory_item_provenance": "episode",
                        "metadata_match_candidates": ["kind root-cause", "root-cause"],
                        "workspace_constrained": True,
                    },
                },
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": "root cause",
            "normalized_query": "root cause",
            "workspace_id": str(workflow_id),
            "limit": 3,
            "filters": {"kind": "episode"},
            "search_mode": "hybrid_memory_item_search",
            "memory_items_considered": 2,
            "semantic_candidates_considered": 2,
            "semantic_query_generated": True,
            "hybrid_scoring": {
                "lexical_weight": 1.0,
                "semantic_weight": 1.0,
                "semantic_only_discount": 0.75,
            },
            "result_mode_counts": {
                "hybrid": 1,
                "lexical_only": 0,
                "semantic_only_discounted": 0,
            },
            "result_composition": {
                "with_lexical_signal": 1,
                "with_semantic_signal": 1,
                "with_both_signals": 1,
            },
            "results_returned": 1,
        },
    )

    payload = serialize_search_memory_response(response)

    assert payload["feature"] == "memory_search"
    assert payload["implemented"] is True
    assert payload["message"] == "Hybrid lexical and semantic memory search completed successfully."
    assert payload["status"] == "ok"
    assert payload["available_in_version"] == "0.3.0"
    assert payload["timestamp"] == created_at.isoformat()
    assert payload["details"] == {
        "query": "root cause",
        "normalized_query": "root cause",
        "workspace_id": str(workflow_id),
        "limit": 3,
        "filters": {"kind": "episode"},
        "search_mode": "hybrid_memory_item_search",
        "memory_items_considered": 2,
        "semantic_candidates_considered": 2,
        "semantic_query_generated": True,
        "hybrid_scoring": {
            "lexical_weight": 1.0,
            "semantic_weight": 1.0,
            "semantic_only_discount": 0.75,
        },
        "result_mode_counts": {
            "hybrid": 1,
            "lexical_only": 0,
            "semantic_only_discounted": 0,
        },
        "result_composition": {
            "with_lexical_signal": 1,
            "with_semantic_signal": 1,
            "with_both_signals": 1,
        },
        "results_returned": 1,
    }
    assert payload["results"] == [
        {
            "memory_id": str(response.results[0].memory_id),
            "workspace_id": str(workflow_id),
            "episode_id": str(response.results[0].episode_id),
            "workflow_instance_id": None,
            "summary": "Recovered context",
            "attempt_id": str(attempt_id),
            "metadata": {"kind": "root-cause"},
            "score": 4.5,
            "matched_fields": ["content", "embedding_similarity"],
            "lexical_score": 3.0,
            "semantic_score": 0.75,
            "ranking_details": {
                "lexical_component": 3.0,
                "semantic_component": 0.75,
                "score_mode": "hybrid",
                "semantic_only_discount_applied": False,
                "reason_list": [
                    {
                        "code": "lexical_signal_present",
                        "message": "lexical overlap contributed to the ranking score",
                        "value": 3.0,
                    },
                    {
                        "code": "semantic_signal_present",
                        "message": "semantic similarity contributed to the ranking score",
                        "value": 0.75,
                    },
                    {
                        "code": "hybrid_score_mode",
                        "message": "both lexical and semantic components were combined",
                    },
                ],
                "task_recall_detail": {
                    "matched_fields": ["content", "embedding_similarity"],
                    "memory_item_type": "episode_note",
                    "memory_item_provenance": "episode",
                    "metadata_match_candidates": ["kind root-cause", "root-cause"],
                    "workspace_constrained": True,
                },
            },
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]
