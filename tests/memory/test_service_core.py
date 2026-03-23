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
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    MemoryServiceError,
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
    assert search_response.available_in_version == "0.4.0"
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
    assert search_response.results[0].ranking_details == {
        "lexical_component": search_response.results[0].lexical_score,
        "semantic_component": 0.0,
        "score_mode": "lexical_only",
        "semantic_only_discount_applied": False,
    }
    assert search_response.results[0].score > search_response.results[1].score
    assert search_response.results[1].lexical_score == 0.0
    assert search_response.results[1].ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": search_response.results[1].semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert search_response.results[1].semantic_score == 1.0


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
    assert search_response.results[0].ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": search_response.results[0].semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert search_response.results[1].ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": search_response.results[1].semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert search_response.results[0].score == pytest.approx(0.75)
    assert search_response.results[1].score == pytest.approx(0.29296875)


def test_memory_service_resolve_workspace_id_and_has_text_helpers() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()
    service = MemoryService(
        workspace_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                }
            }
        )
    )

    assert service._resolve_workspace_id(workflow_id) == workspace_id
    assert service._has_text(" value ") is True
    assert service._has_text("   ") is False
    assert service._has_text(None) is False


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

        def workflow_ids_by_ticket_id(
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


def test_memory_service_constructor_swallowing_embedding_builder_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.memory.service.get_settings",
        lambda: SimpleNamespace(embedding=SimpleNamespace()),
    )
    monkeypatch.setattr(
        "ctxledger.memory.service.build_embedding_generator",
        lambda settings: (_ for _ in ()).throw(RuntimeError("builder exploded")),
    )

    service = MemoryService(embedding_generator=None)

    assert service._embedding_generator is None


def test_memory_service_constructor_uses_built_embedding_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_generator = object()

    monkeypatch.setattr(
        "ctxledger.memory.service.get_settings",
        lambda: SimpleNamespace(embedding=SimpleNamespace(provider="openai")),
    )
    monkeypatch.setattr(
        "ctxledger.memory.service.build_embedding_generator",
        lambda settings: sentinel_generator,
    )

    service = MemoryService(embedding_generator=None)

    assert service._embedding_generator is sentinel_generator


def test_memory_service_order_workflow_ids_by_freshness_with_empty_input() -> None:
    service = MemoryService()

    assert service._order_workflow_ids_by_freshness_signals(workflow_ids=(), limit=5) == ()


def test_memory_service_workflow_ordering_signals_without_lookup() -> None:
    workflow_id = uuid4()
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary",
        created_at=datetime(2024, 1, 4, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, tzinfo=UTC),
    )
    service = MemoryService(
        episode_repository=SimpleNamespace(
            list_by_workflow_id=lambda workflow_id_arg, limit: (episode,)
        )
    )

    signals = service._workflow_ordering_signals(workflow_ids=(workflow_id,))

    assert signals == {
        str(workflow_id): {
            "workflow_status": None,
            "workflow_is_terminal": None,
            "latest_attempt_status": None,
            "latest_attempt_is_terminal": None,
            "has_latest_attempt": None,
            "latest_attempt_verify_status": None,
            "has_latest_checkpoint": None,
            "latest_checkpoint_created_at": None,
            "latest_verify_report_created_at": None,
            "latest_episode_created_at": episode.created_at.isoformat(),
            "latest_attempt_started_at": None,
            "workflow_updated_at": None,
        }
    }


def test_memory_service_build_memory_item_details_without_optional_outputs() -> None:
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="Episode summary",
    )
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=episode.episode_id,
        content="content",
    )
    service = MemoryService(
        memory_item_repository=SimpleNamespace(
            list_by_episode_ids=lambda episode_ids: (memory_item,)
        )
    )

    details = service._build_memory_item_details_for_episodes(
        episodes=(episode,),
        include_memory_items=False,
        include_summaries=False,
    )

    assert details == (
        {
            "episode_id": str(episode.episode_id),
            "memory_item_count": 1,
        },
    )


def test_memory_service_build_episode_explanations_for_unfiltered_context() -> None:
    service = MemoryService()
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="Episode summary",
        metadata={"kind": "note"},
    )

    explanations = service._build_episode_explanations(
        episodes=(episode,),
        normalized_query=None,
        query_tokens=(),
    )

    assert explanations == (
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(episode.workflow_instance_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    )


def test_memory_service_build_memory_item_details_with_summary_output() -> None:
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="Episode summary",
    )
    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="first",
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=first_memory_item.workspace_id,
        episode_id=episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="second",
    )
    service = MemoryService(
        memory_item_repository=SimpleNamespace(
            list_by_episode_ids=lambda episode_ids: (
                second_memory_item,
                first_memory_item,
            )
        )
    )

    details = service._build_memory_item_details_for_episodes(
        episodes=(episode,),
        include_memory_items=False,
        include_summaries=True,
    )

    assert details == (
        {
            "episode_id": str(episode.episode_id),
            "memory_item_count": 2,
            "summary": {
                "episode_id": str(episode.episode_id),
                "workflow_instance_id": str(episode.workflow_instance_id),
                "memory_item_count": 2,
                "memory_item_types": ["checkpoint_note", "episode_note"],
                "memory_item_provenance": ["checkpoint", "episode"],
            },
        },
    )


def test_memory_service_build_summary_selection_details_without_summaries() -> None:
    service = MemoryService()

    summaries, summary_selection_applied, summary_selection_kind = (
        service._build_summary_selection_details(
            (
                {
                    "episode_id": str(uuid4()),
                    "memory_item_count": 1,
                },
            )
        )
    )

    assert summaries == ()
    assert summary_selection_applied is False
    assert summary_selection_kind is None


def test_memory_service_build_summary_selection_details_with_summaries() -> None:
    service = MemoryService()
    episode_id = uuid4()
    workflow_instance_id = uuid4()

    summaries, summary_selection_applied, summary_selection_kind = (
        service._build_summary_selection_details(
            (
                {
                    "episode_id": str(episode_id),
                    "memory_item_count": 1,
                    "summary": {
                        "episode_id": str(episode_id),
                        "workflow_instance_id": str(workflow_instance_id),
                        "memory_item_count": 1,
                        "memory_item_types": ["episode_note"],
                        "memory_item_provenance": ["episode"],
                    },
                },
            )
        )
    )

    assert summaries == (
        {
            "episode_id": str(episode_id),
            "workflow_instance_id": str(workflow_instance_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        },
    )
    assert summary_selection_applied is True
    assert summary_selection_kind == "episode_summary_first"


def test_memory_service_collect_supports_related_memory_items_returns_empty_without_lookup_support() -> (
    None
):
    service = MemoryService(
        memory_item_repository=SimpleNamespace(),
        memory_relation_repository=SimpleNamespace(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(uuid4()),
                    }
                ],
            },
        ),
        limit=3,
        include_relation_metadata=True,
    )

    assert related_memory_items == ()
    assert related_relations == ()


def test_memory_service_collect_supports_related_memory_items_returns_empty_when_limit_is_zero() -> (
    None
):
    service = MemoryService(
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(uuid4()),
                    }
                ],
            },
        ),
        limit=0,
        include_relation_metadata=True,
    )

    assert related_memory_items == ()
    assert related_relations == ()


def test_memory_service_collect_supports_related_memory_items_falls_back_to_relation_scan() -> None:
    workspace_id = uuid4()
    episode_id = uuid4()
    source_memory_id = uuid4()
    related_memory_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    target_memory_item = MemoryItemRecord(
        memory_id=related_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="related memory item",
        metadata={"kind": "related"},
        created_at=created_at,
        updated_at=created_at,
    )
    relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=related_memory_id,
        relation_type="supports",
        metadata={"kind": "supports-edge"},
        created_at=created_at,
    )

    class RelationRepositoryWithoutBulkLookup:
        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (relation,)

    class MemoryItemLookupRepository:
        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            assert memory_id == related_memory_id
            return target_memory_item

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            assert memory_ids == (related_memory_id,)
            assert limit == 2
            return (target_memory_item,)

    service = MemoryService(
        memory_item_repository=MemoryItemLookupRepository(),
        memory_relation_repository=RelationRepositoryWithoutBulkLookup(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(episode_id),
                "memory_items": [
                    {
                        "memory_id": str(source_memory_id),
                    }
                ],
            },
        ),
        limit=2,
        include_relation_metadata=True,
    )

    assert related_memory_items == (target_memory_item,)
    assert related_relations == (relation,)


def test_memory_service_build_retrieval_route_details_marks_auxiliary_only_after_query_filter() -> (
    None
):
    service = MemoryService()
    episode_id = uuid4()
    workspace_id = uuid4()
    inherited_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="workspace inherited",
    )

    details = service._build_retrieval_route_details(
        memory_item_details=(
            {
                "episode_id": str(episode_id),
                "memory_item_count": 0,
            },
        ),
        summaries=(),
        summary_selection_applied=False,
        matched_episode_count=1,
        include_memory_items=False,
        inherited_memory_items=(inherited_memory_item,),
        related_memory_items=(),
    )

    assert details["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert details["primary_retrieval_routes_present"] == []
    assert details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert details["primary_episode_groups_present_after_query_filter"] is False
    assert details["auxiliary_only_after_query_filter"] is True
    assert details["summary_first_has_episode_groups"] is False
    assert details["summary_first_is_summary_only"] is False
    assert details["summary_first_child_episode_count"] == 0
    assert details["summary_first_child_episode_ids"] == []
    assert details["relation_supports_source_episode_count"] == 0


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
