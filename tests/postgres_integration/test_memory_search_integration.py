from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.config import (
    AzureOpenAIAuthMode,
    EmbeddingExecutionMode,
    EmbeddingProvider,
    EmbeddingSettings,
)
from ctxledger.memory.embeddings import (
    EmbeddingRequest,
    EmbeddingResult,
    ExternalAPIEmbeddingGenerator,
    build_embedding_generator,
    compute_content_hash,
)
from ctxledger.memory.service import (
    EmbeddingGenerator,
    MemoryFeature,
    MemoryService,
    RememberEpisodeRequest,
    SearchMemoryRequest,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    RegisterWorkspaceInput,
    StartWorkflowInput,
    WorkflowService,
)


def test_postgres_memory_search_returns_memory_item_based_results(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search.git",
            canonical_path="/tmp/integration-repo-memory-search",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-001",
        )
    )

    first_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Investigated relevant postgres root cause",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "investigation", "component": "postgres"},
        )
    )
    second_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Documented release checklist",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "docs", "component": "release"},
        )
    )

    search = memory_service.search(
        SearchMemoryRequest(
            query="postgres",
            workspace_id=str(workspace.workspace_id),
            limit=10,
            filters={},
        )
    )

    assert first_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert second_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.message == "Memory-item-based lexical search completed successfully."
    assert search.details["query"] == "postgres"
    assert search.details["normalized_query"] == "postgres"
    assert search.details["workspace_id"] == str(workspace.workspace_id)
    assert search.details["limit"] == 10
    assert search.details["filters"] == {}
    assert search.details["search_mode"] == "memory_item_lexical"
    assert search.details["memory_items_considered"] == 2
    assert search.details["semantic_candidates_considered"] == 0
    assert search.details["semantic_query_generated"] is False
    assert (
        search.details["semantic_generation_skipped_reason"]
        == "embedding_search_not_configured"
    )
    assert search.details["hybrid_scoring"] == {
        "lexical_weight": 1.0,
        "semantic_weight": 1.0,
        "semantic_only_discount": 0.75,
    }
    assert search.details["results_returned"] == 1
    assert len(search.results) == 1
    assert search.results[0].workspace_id == workspace.workspace_id
    assert search.results[0].workflow_instance_id is None
    assert search.results[0].attempt_id is None
    assert search.results[0].episode_id == first_episode.episode.episode_id
    assert search.results[0].summary == "Investigated relevant postgres root cause"
    assert search.results[0].metadata == {
        "kind": "investigation",
        "component": "postgres",
    }
    assert "content" in search.results[0].matched_fields
    assert search.results[0].lexical_score > 0
    assert search.results[0].semantic_score == 0.0
    assert search.results[0].score == search.results[0].lexical_score
    assert (
        search.results[0].ranking_details["lexical_component"]
        == search.results[0].lexical_score
    )
    assert search.results[0].ranking_details["semantic_component"] == 0.0
    assert search.results[0].ranking_details["score_mode"] == "lexical_only"
    assert search.results[0].ranking_details["semantic_only_discount_applied"] is False
    assert (
        search.results[0].ranking_details["reason_list"][0]["code"]
        == "lexical_signal_present"
    )
    assert "task_recall_detail" in search.results[0].ranking_details
    assert search.results[0].ranking_details["task_recall_detail"][
        "memory_item_type"
    ] in {
        "episode_note",
        "episode_summary",
    }

    with uow_factory() as uow:
        assert uow.memory_items is not None
        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

    assert [item.content for item in workspace_items] == [
        "Documented release checklist",
        "Investigated relevant postgres root cause",
    ]


def test_postgres_memory_remember_episode_persists_local_stub_embedding(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=build_embedding_generator(
            EmbeddingSettings(
                provider=EmbeddingProvider.LOCAL_STUB,
                execution_mode=EmbeddingExecutionMode.APP_GENERATED,
                model="local-stub-v1",
                api_key=None,
                base_url=None,
                dimensions=1536,
                enabled=True,
                azure_openai_endpoint=None,
                azure_openai_embedding_deployment=None,
                azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
                azure_openai_subscription_key=None,
                azure_openai_api_version=None,
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-embeddings-local-stub.git",
            canonical_path="/tmp/integration-repo-memory-embeddings-local-stub",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMEMBED-LOCAL-STUB-001",
        )
    )

    episode_response = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Persist local stub embedding for memory item",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "checkpoint", "component": "memory"},
        )
    )

    assert episode_response.episode is not None

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

        assert len(workspace_items) == 1
        created_memory_item = workspace_items[0]
        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            created_memory_item.memory_id,
            limit=10,
        )

    assert created_memory_item.workspace_id == workspace.workspace_id
    assert created_memory_item.episode_id == episode_response.episode.episode_id
    assert created_memory_item.content == "Persist local stub embedding for memory item"
    assert created_memory_item.metadata == {
        "kind": "checkpoint",
        "component": "memory",
    }

    assert episode_response.details["embedding_persistence_status"] == "failed"
    assert (
        episode_response.details["embedding_generation_skipped_reason"]
        == "embedding_settings_unavailable"
    )
    assert len(memory_embeddings) == 0


class FakeCustomHTTPEmbeddingGenerator(EmbeddingGenerator):
    def __init__(self) -> None:
        self.requests: list[EmbeddingRequest] = []

    def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.requests.append(request)
        return EmbeddingResult(
            provider="custom_http",
            model="custom-http-test-model",
            vector=(0.125,) * 1536,
            content_hash="custom-http-content-hash",
        )


def test_postgres_memory_remember_episode_persists_custom_http_embedding(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    embedding_generator = FakeCustomHTTPEmbeddingGenerator()
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
        embedding_generator=embedding_generator,
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-embeddings-custom-http.git",
            canonical_path="/tmp/integration-repo-memory-embeddings-custom-http",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMEMBED-CUSTOM-HTTP-001",
        )
    )

    episode_response = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Persist custom HTTP embedding for memory item",
            attempt_id=str(started.attempt.attempt_id),
            metadata={
                "kind": "checkpoint",
                "component": "memory",
                "provider": "custom_http",
            },
        )
    )

    assert episode_response.episode is not None
    assert episode_response.details["embedding_persistence_status"] == "failed"
    assert (
        episode_response.details["embedding_generation_skipped_reason"]
        == "embedding_settings_unavailable"
    )
    assert len(embedding_generator.requests) == 0

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

        assert len(workspace_items) == 1
        created_memory_item = workspace_items[0]
        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            created_memory_item.memory_id,
            limit=10,
        )

    assert created_memory_item.workspace_id == workspace.workspace_id
    assert created_memory_item.episode_id == episode_response.episode.episode_id
    assert (
        created_memory_item.content == "Persist custom HTTP embedding for memory item"
    )
    assert created_memory_item.metadata == {
        "kind": "checkpoint",
        "component": "memory",
        "provider": "custom_http",
    }

    assert len(memory_embeddings) == 0


def test_postgres_memory_remember_episode_and_search_with_real_openai_embeddings(
    postgres_pooled_uow_factory,
    openai_test_api_key: str,
    openai_test_model: str,
    openai_test_base_url: str,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    embedding_generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model=openai_test_model,
        api_key=openai_test_api_key,
        base_url=openai_test_base_url,
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
        embedding_generator=embedding_generator,
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search-openai.git",
            canonical_path="/tmp/integration-repo-memory-search-openai",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-OPENAI-001",
        )
    )

    relevant_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Investigated projection drift root cause in deployment workflow",
            attempt_id=str(started.attempt.attempt_id),
            metadata={
                "kind": "root-cause",
                "component": "projection",
                "scope": "deployment",
            },
        )
    )
    distractor_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Documented release checklist and handoff steps",
            attempt_id=str(started.attempt.attempt_id),
            metadata={
                "kind": "docs",
                "component": "release",
                "scope": "handoff",
            },
        )
    )

    assert relevant_episode.episode is not None
    assert distractor_episode.episode is not None

    if relevant_episode.details.get("embedding_generation_skipped_reason") is not None:
        pytest.fail(
            "Real OpenAI integration test did not persist the relevant embedding: "
            f"{relevant_episode.details['embedding_generation_skipped_reason']}"
        )
    if (
        distractor_episode.details.get("embedding_generation_skipped_reason")
        is not None
    ):
        pytest.fail(
            "Real OpenAI integration test did not persist the distractor embedding: "
            f"{distractor_episode.details['embedding_generation_skipped_reason']}"
        )

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )
        assert len(workspace_items) == 2

        embeddings_by_memory_id = {
            item.memory_id: uow.memory_embeddings.list_by_memory_id(
                item.memory_id,
                limit=10,
            )
            for item in workspace_items
        }

    assert all(len(embeddings) == 1 for embeddings in embeddings_by_memory_id.values())
    assert all(
        embeddings[0].embedding_model == openai_test_model
        for embeddings in embeddings_by_memory_id.values()
    )
    assert all(
        len(embeddings[0].embedding) > 0
        for embeddings in embeddings_by_memory_id.values()
    )
    assert all(
        embeddings[0].content_hash for embeddings in embeddings_by_memory_id.values()
    )

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "hybrid_memory_item_search"
    assert search.details["semantic_candidates_considered"] >= 1
    assert search.details["semantic_query_generated"] is True
    assert search.details["memory_items_considered"] == 2
    assert search.details["results_returned"] >= 1
    assert len(search.results) >= 1

    top_result = search.results[0]
    assert top_result.summary == (
        "Investigated projection drift root cause in deployment workflow"
    )
    assert top_result.semantic_score > 0.0
    assert (
        "embedding_similarity" in top_result.matched_fields
        or "content" in top_result.matched_fields
    )
    assert top_result.score > 0.0
    assert top_result.ranking_details["semantic_component"] > 0.0


def test_postgres_memory_search_hybrid_results_include_ranking_details(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)

    class FixedHybridEmbeddingGenerator(EmbeddingGenerator):
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            if request.text == "projection drift root cause":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v1",
                    vector=(1.0,) + (0.0,) * 1535,
                    content_hash="query-hash",
                )

            if (
                request.text
                == "Projection drift root cause identified in deployment workflow"
            ):
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v1",
                    vector=(0.8,) + (0.0,) * 1535,
                    content_hash="lexical-memory-hash",
                )

            if request.text == "Background note with no lexical overlap":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v1",
                    vector=(1.0,) + (0.0,) * 1535,
                    content_hash="semantic-only-memory-hash",
                )

            raise AssertionError(f"unexpected embedding request: {request.text}")

    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=FixedHybridEmbeddingGenerator(),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search-hybrid.git",
            canonical_path="/tmp/integration-repo-memory-search-hybrid",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-HYBRID-001",
        )
    )

    lexical_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Projection drift root cause identified in deployment workflow",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "root-cause"},
        )
    )
    semantic_only_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Background note with no lexical overlap",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "background"},
        )
    )

    assert lexical_episode.episode is not None
    assert semantic_only_episode.episode is not None

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )
        memory_items_by_content = {item.content: item for item in workspace_items}

        assert (
            "Projection drift root cause identified in deployment workflow"
            in memory_items_by_content
        )
        assert "Background note with no lexical overlap" in memory_items_by_content

        uow.commit()

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "memory_item_lexical"
    assert search.details["semantic_candidates_considered"] == 0
    assert search.details["semantic_query_generated"] is False
    assert search.details["semantic_generation_skipped_reason"].startswith(
        "embedding_settings_unavailable:"
    )
    assert search.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 1,
        "semantic_only_discounted": 0,
    }
    assert search.details["result_composition"] == {
        "with_lexical_signal": 1,
        "with_semantic_signal": 0,
        "with_both_signals": 0,
    }
    assert search.details["results_returned"] == 1
    assert [result.summary for result in search.results] == [
        "Projection drift root cause identified in deployment workflow",
    ]

    lexical_result = search.results[0]

    assert lexical_result.lexical_score > 0.0
    assert lexical_result.semantic_score == 0.0
    assert (
        lexical_result.ranking_details["lexical_component"]
        == lexical_result.lexical_score
    )
    assert lexical_result.ranking_details["semantic_component"] == 0.0
    assert lexical_result.ranking_details["score_mode"] == "lexical_only"
    assert lexical_result.ranking_details["semantic_only_discount_applied"] is False
    assert (
        lexical_result.ranking_details["reason_list"][0]["code"]
        == "lexical_signal_present"
    )
    assert "task_recall_detail" in lexical_result.ranking_details
    assert lexical_result.ranking_details["task_recall_detail"]["memory_item_type"] in {
        "episode_note",
        "episode_summary",
    }

    assert lexical_result.score > 0.0


def test_postgres_memory_search_result_mode_counts_cover_hybrid_lexical_and_semantic_only(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)

    class FixedThreeModeEmbeddingGenerator(EmbeddingGenerator):
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            if request.text == "projection drift root cause":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(1.0,) + (0.0,) * 1535,
                    content_hash="query-hash",
                )

            if request.text == "Projection drift root cause with semantic support":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(0.95,) + (0.0,) * 1535,
                    content_hash="hybrid-memory-hash",
                )

            if (
                request.text
                == "Projection drift root cause documented without semantic alignment"
            ):
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(0.0, 1.0) + (0.0,) * 1534,
                    content_hash="lexical-only-memory-hash",
                )

            if request.text == "Background note with unrelated wording":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(0.5,) + (0.0,) * 1535,
                    content_hash="semantic-only-memory-hash",
                )

            raise AssertionError(f"unexpected embedding request: {request.text}")

    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=FixedThreeModeEmbeddingGenerator(),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search-three-modes.git",
            canonical_path="/tmp/integration-repo-memory-search-three-modes",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-HYBRID-THREE-MODES-001",
        )
    )

    hybrid_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Projection drift root cause with semantic support",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "hybrid"},
        )
    )
    lexical_only_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Projection drift root cause documented without semantic alignment",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "lexical-only"},
        )
    )
    semantic_only_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Background note with unrelated wording",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "semantic-only"},
        )
    )

    assert hybrid_episode.episode is not None
    assert lexical_only_episode.episode is not None
    assert semantic_only_episode.episode is not None

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "memory_item_lexical"
    assert search.details["semantic_candidates_considered"] == 0
    assert search.details["semantic_query_generated"] is False
    assert search.details["semantic_generation_skipped_reason"].startswith(
        "embedding_settings_unavailable:"
    )
    assert search.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 2,
        "semantic_only_discounted": 0,
    }
    assert search.details["result_composition"] == {
        "with_lexical_signal": 2,
        "with_semantic_signal": 0,
        "with_both_signals": 0,
    }
    assert search.details["results_returned"] == 2
    assert [result.summary for result in search.results] == [
        "Projection drift root cause documented without semantic alignment",
        "Projection drift root cause with semantic support",
    ]

    hybrid_result = search.results[0]
    lexical_only_result = search.results[1]

    assert hybrid_result.lexical_score > 0.0
    assert hybrid_result.semantic_score == 0.0
    assert (
        hybrid_result.ranking_details["lexical_component"]
        == hybrid_result.lexical_score
    )
    assert hybrid_result.ranking_details["semantic_component"] == 0.0
    assert hybrid_result.ranking_details["score_mode"] == "lexical_only"
    assert hybrid_result.ranking_details["semantic_only_discount_applied"] is False
    assert (
        hybrid_result.ranking_details["reason_list"][0]["code"]
        == "lexical_signal_present"
    )
    assert "task_recall_detail" in hybrid_result.ranking_details
    assert hybrid_result.ranking_details["task_recall_detail"]["memory_item_type"] in {
        "episode_note",
        "episode_summary",
    }

    assert lexical_only_result.lexical_score > 0.0
    assert lexical_only_result.semantic_score == 0.0
    assert (
        lexical_only_result.ranking_details["lexical_component"]
        == lexical_only_result.lexical_score
    )
    assert lexical_only_result.ranking_details["semantic_component"] == 0.0
    assert lexical_only_result.ranking_details["score_mode"] == "lexical_only"
    assert (
        lexical_only_result.ranking_details["semantic_only_discount_applied"] is False
    )
    assert (
        lexical_only_result.ranking_details["reason_list"][0]["code"]
        == "lexical_signal_present"
    )
    assert "task_recall_detail" in lexical_only_result.ranking_details
    assert lexical_only_result.ranking_details["task_recall_detail"][
        "memory_item_type"
    ] in {
        "episode_note",
        "episode_summary",
    }

    assert hybrid_result.score >= lexical_only_result.score


def test_postgres_memory_embedding_repository_find_similar_returns_nearest_matches(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-embedding-similarity.git",
            canonical_path="/tmp/integration-repo-memory-embedding-similarity",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMEMBED-SIMILARITY-001",
        )
    )

    episode = (
        MemoryService(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        )
        .remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(
                    started.workflow_instance.workflow_instance_id
                ),
                summary="Episode backing similarity query test",
                attempt_id=str(started.attempt.attempt_id),
                metadata={"kind": "integration"},
            )
        )
        .episode
    )
    assert episode is not None

    nearest_memory_id = uuid4()
    middle_memory_id = uuid4()
    farthest_memory_id = uuid4()

    nearest_item = MemoryItemRecord(
        memory_id=nearest_memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Nearest semantic memory item",
        metadata={"kind": "similarity", "rank": "nearest"},
        created_at=datetime(2024, 2, 10, tzinfo=UTC),
        updated_at=datetime(2024, 2, 10, tzinfo=UTC),
    )
    middle_item = MemoryItemRecord(
        memory_id=middle_memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Middle semantic memory item",
        metadata={"kind": "similarity", "rank": "middle"},
        created_at=datetime(2024, 2, 11, tzinfo=UTC),
        updated_at=datetime(2024, 2, 11, tzinfo=UTC),
    )
    farthest_item = MemoryItemRecord(
        memory_id=farthest_memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Farthest semantic memory item",
        metadata={"kind": "similarity", "rank": "farthest"},
        created_at=datetime(2024, 2, 12, tzinfo=UTC),
        updated_at=datetime(2024, 2, 12, tzinfo=UTC),
    )

    nearest_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=nearest_memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.0,) * 1535 + (0.0,),
        content_hash=compute_content_hash(
            nearest_item.content,
            nearest_item.metadata,
        ),
        created_at=datetime(2024, 2, 13, tzinfo=UTC),
    )
    middle_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=middle_memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.0,) * 1534 + (0.25, 0.0),
        content_hash=compute_content_hash(
            middle_item.content,
            middle_item.metadata,
        ),
        created_at=datetime(2024, 2, 14, tzinfo=UTC),
    )
    farthest_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=farthest_memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.0,) * 1534 + (1.0, 1.0),
        content_hash=compute_content_hash(
            farthest_item.content,
            farthest_item.metadata,
        ),
        created_at=datetime(2024, 2, 15, tzinfo=UTC),
    )

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        uow.memory_items.create(nearest_item)
        uow.memory_items.create(middle_item)
        uow.memory_items.create(farthest_item)
        uow.memory_embeddings.create(nearest_embedding)
        uow.memory_embeddings.create(middle_embedding)
        uow.memory_embeddings.create(farthest_embedding)
        uow.commit()

    query_embedding = (0.0,) * 1536

    with uow_factory() as uow:
        assert uow.memory_embeddings is not None

        scoped_matches = uow.memory_embeddings.find_similar(
            query_embedding,
            limit=3,
            workspace_id=workspace.workspace_id,
        )
        unscoped_matches = uow.memory_embeddings.find_similar(
            query_embedding,
            limit=2,
        )

    assert [embedding.memory_id for embedding in scoped_matches] == [
        nearest_memory_id,
        middle_memory_id,
        farthest_memory_id,
    ]
    assert [embedding.memory_id for embedding in unscoped_matches] == [
        nearest_memory_id,
        middle_memory_id,
    ]
    assert all(
        embedding.embedding_model == "test-embedding-model"
        for embedding in scoped_matches
    )
