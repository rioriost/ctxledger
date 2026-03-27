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


def test_memory_service_records_episodes_and_returns_search_results() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-1",
            }
        }
    )
    memory_item_repository = InMemoryMemoryItemRepository()
    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    remember_response = service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(workflow_id),
            summary="Episode summary with relevant context",
            attempt_id=str(attempt_id),
            metadata={"kind": "checkpoint", "topic": "relevant context"},
        )
    )
    search_response = service.search(
        SearchMemoryRequest(
            query="relevant context",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={"kind": "episode"},
        )
    )
    context_response = service.get_context(
        GetMemoryContextRequest(
            query="relevant context",
            workspace_id="ws-1",
            workflow_instance_id=str(workflow_id),
            ticket_id="TICKET-1",
            limit=3,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert isinstance(remember_response, RememberEpisodeResponse)
    assert remember_response.feature == MemoryFeature.REMEMBER_EPISODE
    assert remember_response.implemented is True
    assert remember_response.status == "recorded"
    assert remember_response.episode is not None
    assert remember_response.episode.workflow_instance_id == workflow_id
    assert remember_response.episode.attempt_id == attempt_id
    assert remember_response.episode.summary == "Episode summary with relevant context"
    assert remember_response.episode.metadata == {
        "kind": "checkpoint",
        "topic": "relevant context",
    }
    assert remember_response.details == {
        "workflow_instance_id": str(workflow_id),
        "attempt_id": str(attempt_id),
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert memory_item_repository.memory_items[0].workspace_id == UUID(
        "00000000-0000-0000-0000-000000000001"
    )
    assert memory_item_repository.memory_items[0].episode_id == remember_response.episode.episode_id
    assert memory_item_repository.memory_items[0].type == "episode_note"
    assert memory_item_repository.memory_items[0].provenance == "episode"
    assert memory_item_repository.memory_items[0].content == "Episode summary with relevant context"
    assert memory_item_repository.memory_items[0].metadata == {
        "kind": "checkpoint",
        "topic": "relevant context",
    }

    assert search_response.feature == MemoryFeature.SEARCH
    assert search_response.implemented is True
    assert search_response.status == "ok"
    assert search_response.available_in_version == "0.9.0"
    assert search_response.details["limit"] == 5
    assert search_response.details["filters"] == {"kind": "episode"}
    assert search_response.details["search_mode"] == "memory_item_lexical"
    assert search_response.details["memory_items_considered"] == 1
    assert search_response.details["semantic_candidates_considered"] == 0
    assert search_response.details["semantic_query_generated"] is False
    assert (
        search_response.details["semantic_generation_skipped_reason"]
        == "embedding_search_not_configured"
    )
    assert search_response.details["results_returned"] == 1
    assert len(search_response.results) == 1
    assert search_response.results[0].memory_id == memory_item_repository.memory_items[0].memory_id
    assert search_response.results[0].workspace_id == UUID("00000000-0000-0000-0000-000000000001")
    assert search_response.results[0].episode_id == remember_response.episode.episode_id
    assert search_response.results[0].workflow_instance_id is None
    assert search_response.results[0].attempt_id is None
    assert search_response.results[0].summary == "Episode summary with relevant context"
    assert search_response.results[0].metadata == {
        "kind": "checkpoint",
        "topic": "relevant context",
    }
    assert "content" in search_response.results[0].matched_fields
    assert search_response.results[0].lexical_score > 0
    assert search_response.results[0].semantic_score == 0.0
    assert search_response.results[0].score == search_response.results[0].lexical_score

    assert context_response.feature == MemoryFeature.GET_CONTEXT


def test_memory_service_hybrid_ranking_prefers_lexical_evidence() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-HYBRID-1",
            }
        }
    )

    lexical_and_semantic_memory_id = uuid4()
    semantic_only_memory_id = uuid4()
    lexical_and_semantic_episode_id = uuid4()
    semantic_only_episode_id = uuid4()
    created_at = datetime(2024, 1, 2, tzinfo=UTC)

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=lexical_and_semantic_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=lexical_and_semantic_episode_id,
            type="episode_note",
            provenance="episode",
            content="Projection drift root cause identified in deployment workflow",
            metadata={"kind": "root-cause"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=semantic_only_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=semantic_only_episode_id,
            type="episode_note",
            provenance="episode",
            content="Background note with no lexical overlap",
            metadata={"kind": "background"},
            created_at=datetime(2024, 1, 3, tzinfo=UTC),
            updated_at=datetime(2024, 1, 3, tzinfo=UTC),
        )
    )

    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=lexical_and_semantic_memory_id,
            embedding_model="test-hybrid-v1",
            embedding=(0.8, 0.0),
            content_hash="lexical-and-semantic-hash",
            created_at=created_at,
        )
    )
    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=semantic_only_memory_id,
            embedding_model="test-hybrid-v1",
            embedding=(1.0, 0.0),
            content_hash="semantic-only-hash",
            created_at=datetime(2024, 1, 3, tzinfo=UTC),
        )
    )

    class FixedEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            assert request.text == "projection drift root cause"
            return EmbeddingResult(
                provider="test",
                model="test-hybrid-v1",
                vector=(1.0, 0.0),
                content_hash="query-hash",
            )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=FixedEmbeddingGenerator(),
        workflow_lookup=workflow_lookup,
    )

    search_response = service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={},
        )
    )

    assert search_response.feature == MemoryFeature.SEARCH
    assert search_response.details["search_mode"] == "hybrid_memory_item_search"
    assert search_response.details["semantic_candidates_considered"] == 2
    assert search_response.details["semantic_query_generated"] is True
    assert search_response.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 1,
        "semantic_only_discounted": 1,
    }
    assert search_response.details["result_composition"] == {
        "with_lexical_signal": 1,
        "with_semantic_signal": 1,
        "with_both_signals": 0,
    }
    assert search_response.details["results_returned"] == 2
    assert [result.memory_id for result in search_response.results] == [
        lexical_and_semantic_memory_id,
        semantic_only_memory_id,
    ]
    assert "content" in search_response.results[0].matched_fields
    assert search_response.results[0].lexical_score > 0.0
    assert search_response.results[0].semantic_score == 0.0
    assert search_response.results[0].ranking_details["lexical_component"] == (
        search_response.results[0].lexical_score
    )
    assert search_response.results[0].ranking_details["semantic_component"] == 0.0
    assert search_response.results[0].ranking_details["score_mode"] == "lexical_only"
    assert search_response.results[0].ranking_details["semantic_only_discount_applied"] is False
    assert search_response.results[0].ranking_details["reason_list"] == [
        {
            "code": "lexical_signal_present",
            "message": "lexical overlap contributed to the ranking score",
            "value": search_response.results[0].lexical_score,
        },
        {
            "code": "semantic_signal_absent",
            "message": "no semantic similarity contributed to the ranking score",
            "value": 0.0,
        },
        {
            "code": "lexical_only_score_mode",
            "message": "the result ranked using lexical evidence only",
        },
    ]
    assert search_response.results[0].ranking_details["task_recall_detail"]["matched_fields"] == [
        "content"
    ]
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["memory_item_type"]
        == "episode_note"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["memory_item_provenance"]
        == "episode"
    )
    assert (
        "root-cause"
        in search_response.results[0].ranking_details["task_recall_detail"][
            "metadata_match_candidates"
        ]
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["workspace_constrained"]
        is True
    )
    assert search_response.results[0].score > search_response.results[1].score
    assert search_response.results[1].lexical_score == 0.0
    assert search_response.results[1].ranking_details["lexical_component"] == 0.0
    assert search_response.results[1].ranking_details["semantic_component"] == (
        search_response.results[1].semantic_score
    )


def test_memory_search_ranking_details_include_remember_path_explainability_for_checkpoint_memory() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-0000000000aa")
    objective_memory_id = uuid4()
    next_action_memory_id = uuid4()
    relation_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    service = MemoryService(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-REMEMBER-PATH-1",
                }
            }
        ),
    )

    service._memory_item_repository.create(
        MemoryItemRecord(
            memory_id=objective_memory_id,
            workspace_id=workspace_id,
            episode_id=uuid4(),
            type="workflow_objective",
            provenance="workflow_checkpoint_auto",
            content="Strengthen checkpoint remember-path explainability",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "current_objective",
                "promotion_source": "checkpoint.current_objective",
                "checkpoint_id": str(uuid4()),
                "step_name": "checkpoint_explainability",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )
    service._memory_item_repository.create(
        MemoryItemRecord(
            memory_id=next_action_memory_id,
            workspace_id=workspace_id,
            episode_id=uuid4(),
            type="workflow_next_action",
            provenance="workflow_checkpoint_auto",
            content="Add explainability details to remember-path search ranking",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "next_intended_action",
                "promotion_source": "checkpoint.next_intended_action",
                "checkpoint_id": str(uuid4()),
                "step_name": "checkpoint_explainability",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            created_at=datetime(2024, 2, 2, tzinfo=UTC),
            updated_at=datetime(2024, 2, 2, tzinfo=UTC),
        )
    )
    service._memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=relation_id,
            source_memory_id=next_action_memory_id,
            target_memory_id=objective_memory_id,
            relation_type="supports",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "relation_reason": "next_action_supports_objective",
                "source_memory_type": "workflow_next_action",
                "target_memory_type": "workflow_objective",
            },
            created_at=datetime(2024, 2, 2, tzinfo=UTC),
        )
    )

    response = service.search(
        SearchMemoryRequest(
            query="Add explainability details to remember-path search ranking",
            workspace_id=str(workspace_id),
            limit=5,
            filters={},
        )
    )

    assert len(response.results) >= 1

    next_action_result = next(
        result for result in response.results if result.memory_id == next_action_memory_id
    )
    assert next_action_result.ranking_details["remember_path_detail"] == {
        "memory_origin": "workflow_checkpoint_auto",
        "promotion_field": "next_intended_action",
        "promotion_source": "checkpoint.next_intended_action",
        "checkpoint_id": next_action_result.metadata["checkpoint_id"],
        "step_name": "checkpoint_explainability",
        "workflow_status": "running",
        "attempt_status": "running",
        "supports_relation_present": True,
        "supports_relation_reasons": ["next_action_supports_objective"],
        "provenance": "workflow_checkpoint_auto",
        "provenance_kind": "workflow_memory",
        "interaction_role": None,
        "interaction_kind": None,
        "file_name": None,
        "file_path": None,
        "file_operation": None,
        "purpose": None,
        "failure_reuse_detail": {
            "failure_reuse_candidate": False,
            "failure_reuse_reason": None,
            "interaction_present": False,
            "interaction_role": None,
            "interaction_kind": None,
            "file_work_present": False,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
        },
    }


def test_memory_search_ranking_details_include_completion_origin_explainability() -> None:
    workspace_id = UUID("00000000-0000-0000-0000-0000000000bb")
    memory_id = uuid4()
    created_at = datetime(2024, 3, 1, tzinfo=UTC)

    service = MemoryService(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
        workflow_lookup=InMemoryWorkflowLookupRepository(),
    )

    service._memory_item_repository.create(
        MemoryItemRecord(
            memory_id=memory_id,
            workspace_id=workspace_id,
            episode_id=uuid4(),
            type="workflow_completion_note",
            provenance="workflow_complete_auto",
            content="Completion note for remember-path ranking explainability",
            metadata={
                "memory_origin": "workflow_complete_auto",
                "step_name": "workflow_complete",
                "workflow_status": "completed",
                "attempt_status": "succeeded",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )

    response = service.search(
        SearchMemoryRequest(
            query="Completion note for remember-path ranking explainability",
            workspace_id=str(workspace_id),
            limit=5,
            filters={},
        )
    )

    assert len(response.results) == 1
    assert response.results[0].ranking_details["remember_path_detail"] == {
        "memory_origin": "workflow_complete_auto",
        "promotion_field": None,
        "promotion_source": None,
        "checkpoint_id": None,
        "step_name": "workflow_complete",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "supports_relation_present": False,
        "supports_relation_reasons": [],
        "provenance": "workflow_complete_auto",
        "provenance_kind": "workflow_memory",
        "interaction_role": None,
        "interaction_kind": None,
        "file_name": None,
        "file_path": None,
        "file_operation": None,
        "purpose": None,
        "failure_reuse_detail": {
            "failure_reuse_candidate": False,
            "failure_reuse_reason": None,
            "interaction_present": False,
            "interaction_role": None,
            "interaction_kind": None,
            "file_work_present": False,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
        },
    }


def test_memory_search_prefers_completion_memory_over_checkpoint_memory_when_lexical_scores_tie() -> (
    None
):
    workspace_id = UUID("00000000-0000-0000-0000-0000000000bc")
    checkpoint_memory_id = uuid4()
    completion_memory_id = uuid4()
    created_at = datetime(2024, 3, 2, tzinfo=UTC)

    service = MemoryService(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
        workflow_lookup=InMemoryWorkflowLookupRepository(),
    )

    shared_content = "Investigated projection drift root cause"

    service._memory_item_repository.create(
        MemoryItemRecord(
            memory_id=checkpoint_memory_id,
            workspace_id=workspace_id,
            episode_id=uuid4(),
            type="workflow_next_action",
            provenance="workflow_checkpoint_auto",
            content=shared_content,
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "next_intended_action",
                "promotion_source": "checkpoint.next_intended_action",
                "checkpoint_id": "checkpoint-tiebreak-1",
                "step_name": "checkpoint_tiebreak",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )
    service._memory_item_repository.create(
        MemoryItemRecord(
            memory_id=completion_memory_id,
            workspace_id=workspace_id,
            episode_id=uuid4(),
            type="workflow_completion_note",
            provenance="workflow_complete_auto",
            content=shared_content,
            metadata={
                "memory_origin": "workflow_complete_auto",
                "step_name": "workflow_complete",
                "workflow_status": "completed",
                "attempt_status": "succeeded",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )

    response = service.search(
        SearchMemoryRequest(
            query=shared_content,
            workspace_id=str(workspace_id),
            limit=5,
            filters={},
        )
    )

    assert [result.memory_id for result in response.results[:2]] == [
        completion_memory_id,
        checkpoint_memory_id,
    ]
    assert response.results[0].lexical_score == response.results[1].lexical_score
    assert response.results[0].semantic_score == response.results[1].semantic_score == 0.0
    assert response.results[0].ranking_details["score_mode"] == "lexical_only"
    assert response.results[1].ranking_details["score_mode"] == "lexical_only"
    assert response.results[0].ranking_details["reason_list"][-1] == {
        "code": "workflow_complete_auto_tiebreak",
        "message": "completion-origin memory was preferred over checkpoint-origin memory when lexical evidence tied",
    }
    assert response.results[0].ranking_details["remember_path_detail"]["memory_origin"] == (
        "workflow_complete_auto"
    )
    assert response.results[1].ranking_details["remember_path_detail"]["memory_origin"] == (
        "workflow_checkpoint_auto"
    )


def test_memory_service_hybrid_ranking_uses_similarity_gap_for_semantic_scores() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-HYBRID-2",
            }
        }
    )

    strongest_memory_id = uuid4()
    middle_memory_id = uuid4()
    weakest_memory_id = uuid4()
    created_at = datetime(2024, 1, 4, tzinfo=UTC)

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=strongest_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="Semantic strongest memory item",
            metadata={"kind": "semantic"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=middle_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="Semantic middle memory item",
            metadata={"kind": "semantic"},
            created_at=datetime(2024, 1, 5, tzinfo=UTC),
            updated_at=datetime(2024, 1, 5, tzinfo=UTC),
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=weakest_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="Semantic weakest memory item",
            metadata={"kind": "semantic"},
            created_at=datetime(2024, 1, 6, tzinfo=UTC),
            updated_at=datetime(2024, 1, 6, tzinfo=UTC),
        )
    )

    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=strongest_memory_id,
            embedding_model="test-hybrid-v2",
            embedding=(1.0, 0.0),
            content_hash="strongest-hash",
            created_at=created_at,
        )
    )
    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=middle_memory_id,
            embedding_model="test-hybrid-v2",
            embedding=(0.6, 0.0),
            content_hash="middle-hash",
            created_at=datetime(2024, 1, 5, tzinfo=UTC),
        )
    )
    memory_embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=weakest_memory_id,
            embedding_model="test-hybrid-v2",
            embedding=(0.2, 0.0),
            content_hash="weakest-hash",
            created_at=datetime(2024, 1, 6, tzinfo=UTC),
        )
    )

    class FixedEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            assert request.text == "semantic query"
            return EmbeddingResult(
                provider="test",
                model="test-hybrid-v2",
                vector=(1.0, 0.0),
                content_hash="query-hash",
            )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=FixedEmbeddingGenerator(),
        workflow_lookup=workflow_lookup,
    )

    search_response = service.search(
        SearchMemoryRequest(
            query="semantic query",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={},
        )
    )

    assert [result.memory_id for result in search_response.results] == [
        strongest_memory_id,
        middle_memory_id,
    ]
    assert search_response.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 0,
        "semantic_only_discounted": 2,
    }
    assert search_response.details["result_composition"] == {
        "with_lexical_signal": 0,
        "with_semantic_signal": 2,
        "with_both_signals": 0,
    }
    assert search_response.results[0].semantic_score == pytest.approx(1.0)
    assert search_response.results[1].semantic_score == pytest.approx(0.390625)
    assert search_response.results[0].ranking_details["lexical_component"] == 0.0
    assert search_response.results[0].ranking_details["semantic_component"] == (
        search_response.results[0].semantic_score
    )
    assert search_response.results[0].ranking_details["score_mode"] == ("semantic_only_discounted")
    assert search_response.results[0].ranking_details["semantic_only_discount_applied"] is True
    assert search_response.results[0].ranking_details["reason_list"] == [
        {
            "code": "lexical_signal_absent",
            "message": "no lexical overlap contributed to the ranking score",
            "value": 0.0,
        },
        {
            "code": "semantic_signal_present",
            "message": "semantic similarity contributed to the ranking score",
            "value": search_response.results[0].semantic_score,
        },
        {
            "code": "semantic_only_discounted_score_mode",
            "message": "semantic-only evidence was discounted to avoid outranking lexical matches too aggressively",
        },
        {
            "code": "semantic_only_discount_applied",
            "message": "semantic-only scoring discount was applied",
            "value": 0.75,
        },
    ]
    assert search_response.results[0].ranking_details["task_recall_detail"]["matched_fields"] == [
        "embedding_similarity"
    ]
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["memory_item_type"]
        == "episode_note"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["memory_item_provenance"]
        == "episode"
    )
    assert (
        "semantic"
        in search_response.results[0].ranking_details["task_recall_detail"][
            "metadata_match_candidates"
        ]
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["workspace_constrained"]
        is True
    )
    assert search_response.results[1].ranking_details["lexical_component"] == 0.0
    assert search_response.results[1].ranking_details["semantic_component"] == (
        search_response.results[1].semantic_score
    )
    assert search_response.results[1].ranking_details["score_mode"] == ("semantic_only_discounted")
    assert search_response.results[1].ranking_details["semantic_only_discount_applied"] is True
    assert search_response.results[1].ranking_details["reason_list"] == [
        {
            "code": "lexical_signal_absent",
            "message": "no lexical overlap contributed to the ranking score",
            "value": 0.0,
        },
        {
            "code": "semantic_signal_present",
            "message": "semantic similarity contributed to the ranking score",
            "value": search_response.results[1].semantic_score,
        },
        {
            "code": "semantic_only_discounted_score_mode",
            "message": "semantic-only evidence was discounted to avoid outranking lexical matches too aggressively",
        },
        {
            "code": "semantic_only_discount_applied",
            "message": "semantic-only scoring discount was applied",
            "value": 0.75,
        },
    ]
    assert search_response.results[1].ranking_details["task_recall_detail"]["matched_fields"] == [
        "embedding_similarity"
    ]
    assert (
        search_response.results[1].ranking_details["task_recall_detail"]["memory_item_type"]
        == "episode_note"
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"]["memory_item_provenance"]
        == "episode"
    )
    assert (
        "semantic"
        in search_response.results[1].ranking_details["task_recall_detail"][
            "metadata_match_candidates"
        ]
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"]["workspace_constrained"]
        is True
    )
    assert search_response.results[0].score == pytest.approx(0.75)
    assert search_response.results[1].score == pytest.approx(0.29296875)


def test_memory_service_search_records_semantic_generation_skip_reason_after_failure() -> None:
    class FailingEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            raise EmbeddingGenerationError(
                "semantic search exploded",
                provider="openai",
                details={"status_code": 503},
            )

    memory_item_repository = InMemoryMemoryItemRepository()
    workspace_id = UUID("00000000-0000-0000-0000-000000000101")
    created_at = datetime(2024, 1, 7, tzinfo=UTC)
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=uuid4(),
            workspace_id=workspace_id,
            episode_id=uuid4(),
            type="episode_note",
            provenance="episode",
            content="lexical fallback still returns results",
            metadata={"kind": "search"},
            created_at=created_at,
            updated_at=created_at,
        )
    )

    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=FailingEmbeddingGenerator(),
    )

    response = service.search(
        SearchMemoryRequest(
            query="lexical fallback",
            workspace_id=str(workspace_id),
            limit=5,
            filters={},
        )
    )

    assert response.details["semantic_query_generated"] is False
    assert response.details["semantic_candidates_considered"] == 0
    assert (
        response.details["semantic_generation_skipped_reason"]
        == "embedding_generation_failed:openai"
    )
    assert len(response.results) == 1
    assert response.results[0].summary == "lexical fallback still returns results"


def test_memory_service_get_context_uses_workspace_and_ticket_lookup_paths() -> None:
    matching_workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=matching_workflow_id,
        summary="Workspace and ticket lookup match",
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    episode_repository.create(matching_episode)

    class RecordingLookup:
        def __init__(self) -> None:
            self.workspace_calls: list[tuple[str, int]] = []
            self.ticket_calls: list[tuple[str, int]] = []

        def workflow_exists(self, workflow_instance_id: UUID) -> bool:
            return workflow_instance_id == matching_workflow_id

        def workflow_ids_by_workspace_id(
            self,
            workspace_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.workspace_calls.append((workspace_id, limit))
            return (matching_workflow_id,)

        def workflow_ids_by_workspace_id_raw_order(
            self,
            workspace_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.workspace_calls.append((workspace_id, limit))
            return (matching_workflow_id,)

        def workflow_ids_by_ticket_id(
            self,
            ticket_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.ticket_calls.append((ticket_id, limit))
            return (matching_workflow_id,)

        def workflow_ids_by_ticket_id_raw_order(
            self,
            ticket_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.ticket_calls.append((ticket_id, limit))
            return (matching_workflow_id,)

        def workflow_freshness_by_id(
            self,
            workflow_instance_id: UUID,
        ) -> dict[str, datetime | int | str | bool | None]:
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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_verify_report_created_at": None,
            }

    lookup = RecordingLookup()
    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=lookup,
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="workspace-lookup",
            ticket_id="ticket-lookup",
            limit=3,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert lookup.workspace_calls == [("workspace-lookup", 3)]
    assert lookup.ticket_calls == [("ticket-lookup", 3)]
    assert response.details["lookup_scope"] == "workspace_and_ticket"
    assert response.details["resolved_workflow_ids"] == [str(matching_workflow_id)]
    assert [episode.summary for episode in response.episodes] == [
        "Workspace and ticket lookup match"
    ]
