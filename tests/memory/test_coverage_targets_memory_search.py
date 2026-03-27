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
    primary_only_context_response = service.get_context(
        GetMemoryContextRequest(
            query="relevant context",
            workspace_id="ws-1",
            workflow_instance_id=str(workflow_id),
            ticket_id="TICKET-1",
            limit=3,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=False,
            primary_only=True,
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
    assert search_response.results[0].score >= search_response.results[0].lexical_score

    assert context_response.feature == MemoryFeature.GET_CONTEXT
    assert primary_only_context_response.feature == MemoryFeature.GET_CONTEXT
    assert primary_only_context_response.details["memory_context_groups_are_primary_output"] is True
    assert (
        primary_only_context_response.details[
            "memory_context_groups_are_primary_explainability_surface"
        ]
        is True
    )
    assert (
        primary_only_context_response.details["top_level_explainability_prefers_grouped_routes"]
        is True
    )
    assert "memory_items" not in primary_only_context_response.details
    assert "readiness_explainability" not in primary_only_context_response.details
    assert "related_memory_items" not in primary_only_context_response.details
    assert "inherited_memory_items" not in primary_only_context_response.details


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
    assert search_response.details["task_recall_context_present"] is True
    assert search_response.details["task_recall_latest_considered_workflow_instance_id"] == str(
        workflow_id
    )
    assert search_response.details["task_recall_selected_workflow_instance_id"] == str(workflow_id)
    assert search_response.details["task_recall_selected_equals_latest"] is True
    assert search_response.details["task_recall_latest_vs_selected_comparison_present"] is False
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "task_recall_context_present"
        ]
        is True
    )
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "latest_considered_workflow_instance_id"
    ] == str(workflow_id)
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "selected_workflow_instance_id"
    ] == str(workflow_id)
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["selected_equals_latest"]
        is True
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_step_name"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_summary"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_step_name"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_summary"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_ticket_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_ticket_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_workflow_terminal"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_workflow_terminal"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_vs_selected_comparison_present"
        ]
        is False
    )
    assert search_response.results[0].score > search_response.results[1].score
    assert search_response.results[1].lexical_score == 0.0
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
        "background"
        in search_response.results[1].ranking_details["task_recall_detail"][
            "metadata_match_candidates"
        ]
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"]["workspace_constrained"]
        is True
    )
    assert search_response.details["task_recall_context_present"] is True
    assert search_response.details["task_recall_latest_considered_workflow_instance_id"] == str(
        workflow_id
    )
    assert search_response.details["task_recall_selected_workflow_instance_id"] == str(workflow_id)
    assert search_response.details["task_recall_selected_equals_latest"] is True
    assert search_response.details["task_recall_latest_vs_selected_comparison_present"] is False
    assert search_response.details["task_recall_comparison_summary_explanations_present"] is False
    assert search_response.details["task_recall_comparison_summary_explanations"] == []
    assert search_response.details["task_recall_comparison_summary_explanations_present"] is False
    assert search_response.details["task_recall_comparison_summary_explanations"] == []
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "task_recall_context_present"
        ]
        is True
    )
    assert search_response.results[1].ranking_details["task_recall_detail"][
        "latest_considered_workflow_instance_id"
    ] == str(workflow_id)
    assert search_response.results[1].ranking_details["task_recall_detail"][
        "selected_workflow_instance_id"
    ] == str(workflow_id)
    assert (
        search_response.results[1].ranking_details["task_recall_detail"]["selected_equals_latest"]
        is True
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_step_name"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_summary"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "latest_considered_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "latest_considered_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_checkpoint_step_name"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_checkpoint_summary"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_workflow_terminal"
        ]
        is False
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "latest_vs_selected_comparison_present"
        ]
        is False
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_continuation_target_bonus_applied"
        ]
        is False
    )
    assert (
        search_response.results[1].ranking_details["task_recall_detail"][
            "selected_continuation_target_bonus"
        ]
        == 0.0
    )
    assert search_response.results[1].semantic_score == 1.0


def test_memory_service_search_applies_selected_continuation_target_bonus() -> None:
    selected_workflow_id = uuid4()
    other_workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)
    selected_episode_id = uuid4()
    other_episode_id = uuid4()
    selected_memory_id = uuid4()
    other_memory_id = uuid4()

    episode_repository.create(
        EpisodeRecord(
            episode_id=selected_episode_id,
            workflow_instance_id=selected_workflow_id,
            summary="Selected continuation episode",
            metadata={"kind": "feature"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=other_episode_id,
            workflow_instance_id=other_workflow_id,
            summary="Secondary episode",
            metadata={"kind": "feature"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=selected_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=selected_episode_id,
            type="episode_note",
            provenance="episode",
            content="selected continuation target memory",
            metadata={"kind": "selected"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=other_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=other_episode_id,
            type="episode_note",
            provenance="episode",
            content="secondary continuation memory selected",
            metadata={"kind": "secondary"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )

    class RawOrderWorkflowLookup(InMemoryWorkflowLookupRepository):
        def workflow_ids_by_workspace_id_raw_order(
            self,
            workspace_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            assert workspace_id == "00000000-0000-0000-0000-000000000001"
            return (
                other_workflow_id,
                selected_workflow_id,
            )[:limit]

    workflow_lookup = RawOrderWorkflowLookup(
        workflows_by_id={
            selected_workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TASK-SEARCH-BONUS",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "resume_selected_target",
                "latest_checkpoint_summary": "Continue selected target",
                "latest_checkpoint_current_objective": "Finish the selected continuation path",
                "latest_checkpoint_next_intended_action": "Apply the selected target bonus",
            },
            other_workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TASK-SEARCH-COVERAGE",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=2),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=2),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=2),
                "latest_checkpoint_step_name": "coverage_followup",
                "latest_checkpoint_summary": "Improve coverage for recent task recall changes",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=workflow_lookup,
    )

    search_response = service.search(
        SearchMemoryRequest(
            query="selected continuation",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={},
        )
    )

    assert search_response.results
    assert search_response.results[0].memory_id == selected_memory_id
    if len(search_response.results) > 1:
        assert search_response.results[0].score > search_response.results[1].score
        assert search_response.results[1].memory_id == other_memory_id
    assert search_response.details["task_recall_context_present"] is True
    assert search_response.details["task_recall_latest_considered_workflow_instance_id"] == str(
        other_workflow_id
    )
    assert search_response.details["task_recall_selected_workflow_instance_id"] == str(
        selected_workflow_id
    )
    assert search_response.details["task_recall_selected_equals_latest"] is False
    assert search_response.details["task_recall_latest_vs_selected_comparison_present"] is True
    assert search_response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(other_workflow_id),
        "selected_workflow_instance_id": str(selected_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(other_workflow_id),
            "checkpoint_step_name": "coverage_followup",
            "checkpoint_summary": "Improve coverage for recent task recall changes",
            "primary_objective_text": None,
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
        },
        "selected": {
            "workflow_instance_id": str(selected_workflow_id),
            "checkpoint_step_name": "resume_selected_target",
            "checkpoint_summary": "Continue selected target",
            "primary_objective_text": "Finish the selected continuation path",
            "next_intended_action_text": "Apply the selected target bonus",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
        },
        "same_workflow": False,
        "same_checkpoint_details": False,
        "comparison_source": "memory_search_task_recall_context",
    }
    assert search_response.details["task_recall_latest_vs_selected_primary_block"] == (
        "candidate_details"
    )
    assert (
        search_response.details[
            "task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"
        ]
        is True
    )
    assert (
        search_response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    )
    assert search_response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(other_workflow_id),
        "selected_workflow_instance_id": str(selected_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(other_workflow_id),
            "checkpoint_step_name": "coverage_followup",
            "checkpoint_summary": "Improve coverage for recent task recall changes",
            "primary_objective_text": None,
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
        },
        "selected": {
            "workflow_instance_id": str(selected_workflow_id),
            "checkpoint_step_name": "resume_selected_target",
            "checkpoint_summary": "Continue selected target",
            "primary_objective_text": "Finish the selected continuation path",
            "next_intended_action_text": "Apply the selected target bonus",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
        },
        "same_workflow": False,
        "same_checkpoint_details": False,
        "comparison_source": "memory_search_task_recall_context",
    }
    assert search_response.details["task_recall_comparison_summary_explanations_present"] is True
    assert search_response.details["task_recall_comparison_summary_explanations"] == [
        {
            "code": "search_selected_differs_from_latest",
            "message": "search task-recall context recorded that the selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "search_latest_and_selected_checkpoints_differ",
            "message": "search task-recall context recorded that the latest considered checkpoint differed from the selected continuation checkpoint",
        },
        {
            "code": "search_latest_and_selected_detour_classification_differs",
            "message": "search task-recall context recorded that the latest considered candidate and selected continuation target differed in detour classification",
        },
        {
            "code": "search_latest_and_selected_return_target_basis_differs",
            "message": "search task-recall context recorded that the latest considered candidate and selected continuation target differed in return-target basis",
        },
        {
            "code": "search_latest_and_selected_task_thread_basis_differs",
            "message": "search task-recall context recorded that the latest considered candidate and selected continuation target differed in task-thread basis",
        },
    ]
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_continuation_target_bonus_applied"
        ]
        is True
    )

    assert search_response.results[0].ranking_details["task_recall_detail"][
        "latest_considered_workflow_instance_id"
    ] == str(other_workflow_id)
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "selected_workflow_instance_id"
    ] == str(selected_workflow_id)
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["selected_equals_latest"]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_step_name"
        ]
        == "coverage_followup"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_summary"
        ]
        == "Improve coverage for recent task recall changes"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_step_name"
        ]
        == "resume_selected_target"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_summary"
        ]
        == "Continue selected target"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_primary_objective_text"
        ]
        == "Finish the selected continuation path"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_next_intended_action_text"
        ]
        == "Apply the selected target bonus"
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_ticket_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_detour_like"
        ]
        is True
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_ticket_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_workflow_terminal"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_workflow_terminal"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_vs_selected_comparison_present"
        ]
        is True
    )
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "latest_vs_selected_candidate_details"
    ] == {
        "latest_workflow_instance_id": str(other_workflow_id),
        "selected_workflow_instance_id": str(selected_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(other_workflow_id),
            "checkpoint_step_name": "coverage_followup",
            "checkpoint_summary": "Improve coverage for recent task recall changes",
            "primary_objective_text": None,
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
        },
        "selected": {
            "workflow_instance_id": str(selected_workflow_id),
            "checkpoint_step_name": "resume_selected_target",
            "checkpoint_summary": "Continue selected target",
            "primary_objective_text": "Finish the selected continuation path",
            "next_intended_action_text": "Apply the selected target bonus",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
        },
        "same_workflow": False,
        "same_checkpoint_details": False,
        "comparison_source": "memory_search_task_recall_context",
    }
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_continuation_target_bonus_applied"
        ]
        is True
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_continuation_target_bonus"
        ]
        == 0.5
    )
    assert {
        reason["code"] for reason in search_response.results[0].ranking_details["reason_list"]
    } >= {
        "lexical_signal_present",
        "semantic_signal_absent",
        "lexical_only_score_mode",
        "selected_continuation_target_bonus",
    }
    if len(search_response.results) > 1:
        assert (
            search_response.results[1].ranking_details["task_recall_detail"][
                "selected_continuation_target_bonus_applied"
            ]
            is False
        )
        assert (
            search_response.results[1].ranking_details["task_recall_detail"][
                "selected_continuation_target_bonus"
            ]
            == 0.0
        )


def test_memory_service_search_surfaces_latest_vs_selected_task_recall_details() -> None:
    primary_workflow_id = uuid4()
    detour_workflow_id = uuid4()
    older_background_workflow_id = uuid4()
    primary_episode_id = uuid4()
    detour_episode_id = uuid4()
    selected_memory_id = uuid4()
    detour_memory_id = uuid4()
    created_at = datetime(2024, 4, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode_repository.create(
        EpisodeRecord(
            episode_id=primary_episode_id,
            workflow_instance_id=primary_workflow_id,
            summary="Primary implementation work before detour",
            metadata={"kind": "primary"},
            created_at=created_at.replace(day=18),
            updated_at=created_at.replace(day=18),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=detour_episode_id,
            workflow_instance_id=detour_workflow_id,
            summary="Latest coverage detour",
            metadata={"kind": "detour"},
            created_at=created_at.replace(day=20),
            updated_at=created_at.replace(day=20),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=older_background_workflow_id,
            summary="Older background investigation",
            metadata={"kind": "background"},
            created_at=created_at.replace(day=17),
            updated_at=created_at.replace(day=17),
        )
    )

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=selected_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=primary_episode_id,
            type="episode_note",
            provenance="episode",
            content="selected continuation target memory",
            metadata={"kind": "selected"},
            created_at=created_at.replace(day=18, hour=1),
            updated_at=created_at.replace(day=18, hour=1),
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=detour_memory_id,
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            episode_id=detour_episode_id,
            type="episode_note",
            provenance="episode",
            content="latest detour coverage memory",
            metadata={"kind": "detour"},
            created_at=created_at.replace(day=20, hour=1),
            updated_at=created_at.replace(day=20, hour=1),
        )
    )

    class RawOrderWorkflowLookup(InMemoryWorkflowLookupRepository):
        def workflow_ids_by_workspace_id_raw_order(
            self,
            workspace_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            assert workspace_id == "00000000-0000-0000-0000-000000000001"
            return (
                detour_workflow_id,
                primary_workflow_id,
                older_background_workflow_id,
            )[:limit]

    workflow_lookup = RawOrderWorkflowLookup(
        workflows_by_id={
            primary_workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TASK-PRIMARY",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=18),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=18),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=18),
                "latest_checkpoint_step_name": "resume_primary_work",
                "latest_checkpoint_summary": "Return to the primary implementation thread",
                "latest_checkpoint_current_objective": "Finish the hierarchical memory implementation",
                "latest_checkpoint_next_intended_action": "Resume the primary implementation work",
            },
            detour_workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TASK-COVERAGE",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=20),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=20),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=20),
                "latest_checkpoint_step_name": "coverage_followup",
                "latest_checkpoint_summary": "Increase coverage for the recent retrieval changes",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
            older_background_workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TASK-BACKGROUND",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=17),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=17),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=17),
                "latest_checkpoint_step_name": "background_investigation",
                "latest_checkpoint_summary": "Investigate related background issue",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=workflow_lookup,
    )

    search_response = service.search(
        SearchMemoryRequest(
            query="selected continuation",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            filters={},
        )
    )

    assert search_response.results
    assert search_response.results[0].memory_id == selected_memory_id
    assert search_response.details["task_recall_context_present"] is True
    assert search_response.details["task_recall_latest_considered_workflow_instance_id"] == str(
        detour_workflow_id
    )
    assert search_response.details["task_recall_selected_workflow_instance_id"] == str(
        primary_workflow_id
    )
    assert search_response.details["task_recall_selected_equals_latest"] is False
    assert search_response.details["task_recall_latest_vs_selected_comparison_present"] is True

    latest_vs_selected = search_response.details["task_recall_latest_vs_selected_candidate_details"]
    assert latest_vs_selected["latest_workflow_instance_id"] == str(detour_workflow_id)
    assert latest_vs_selected["selected_workflow_instance_id"] == str(primary_workflow_id)
    assert latest_vs_selected["comparison_source"] == "memory_search_task_recall_context"
    assert latest_vs_selected["latest_considered"]["workflow_instance_id"] == str(
        detour_workflow_id
    )
    assert latest_vs_selected["selected"]["workflow_instance_id"] == str(primary_workflow_id)

    assert search_response.details["task_recall_comparison_summary_explanations_present"] is True
    assert {
        explanation["code"]
        for explanation in search_response.details["task_recall_comparison_summary_explanations"]
    } == {
        "search_selected_differs_from_latest",
        "search_latest_and_selected_checkpoints_differ",
        "search_latest_and_selected_return_target_basis_differs",
        "search_latest_and_selected_task_thread_basis_differs",
    }

    assert search_response.results[0].ranking_details["task_recall_detail"][
        "latest_considered_workflow_instance_id"
    ] == str(detour_workflow_id)
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "selected_workflow_instance_id"
    ] == str(primary_workflow_id)
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["selected_equals_latest"]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_continuation_target_bonus_applied"
        ]
        is True
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
    assert search_response.details["task_recall_context_present"] is True
    assert search_response.details["task_recall_latest_considered_workflow_instance_id"] == str(
        workflow_id
    )
    assert search_response.details["task_recall_selected_workflow_instance_id"] == str(workflow_id)
    assert search_response.details["task_recall_selected_equals_latest"] is True
    assert search_response.details["task_recall_latest_vs_selected_comparison_present"] is False
    assert search_response.details["task_recall_comparison_summary_explanations_present"] is False
    assert search_response.details["task_recall_comparison_summary_explanations"] == []
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "task_recall_context_present"
        ]
        is True
    )
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "latest_considered_workflow_instance_id"
    ] == str(workflow_id)
    assert search_response.results[0].ranking_details["task_recall_detail"][
        "selected_workflow_instance_id"
    ] == str(workflow_id)
    assert (
        search_response.results[0].ranking_details["task_recall_detail"]["selected_equals_latest"]
        is True
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_step_name"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_summary"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_step_name"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_summary"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_primary_objective_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_next_intended_action_text"
        ]
        is None
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_ticket_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_checkpoint_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_ticket_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_checkpoint_detour_like"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "latest_considered_workflow_terminal"
        ]
        is False
    )
    assert (
        search_response.results[0].ranking_details["task_recall_detail"][
            "selected_workflow_terminal"
        ]
        is False
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
