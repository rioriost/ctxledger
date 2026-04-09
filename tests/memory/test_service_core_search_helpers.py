from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.config import EmbeddingExecutionMode
from ctxledger.memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
)
from ctxledger.memory.service import (
    EpisodeRecord,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    MemoryFeature,
    MemoryItemRecord,
    MemoryService,
)
from ctxledger.memory.types import (
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryServiceError,
)
from ctxledger.memory.types import (
    MemoryFeature as MemoryTypesFeature,
)


class _FixedEmbeddingGenerator:
    def __init__(self, result) -> None:
        self._result = result
        self.requests: list[EmbeddingRequest] = []

    def generate(self, request: EmbeddingRequest):
        self.requests.append(request)
        return self._result


class _FailingEmbeddingGenerator:
    def __init__(self, provider: str = "test-provider") -> None:
        self.provider = provider
        self.requests: list[EmbeddingRequest] = []

    def generate(self, request: EmbeddingRequest):
        self.requests.append(request)
        raise EmbeddingGenerationError(
            provider=self.provider,
            message="embedding generation failed",
            details={"reason": "boom"},
        )


class _RecordingAzureEmbeddingRepository(InMemoryMemoryEmbeddingRepository):
    def __init__(self) -> None:
        super().__init__()
        self.azure_calls: list[dict[str, object]] = []
        self.azure_result: MemoryEmbeddingRecord | None = None
        self.azure_error: Exception | None = None
        self.azure_find_calls: list[dict[str, object]] = []
        self.azure_find_result: tuple[MemoryEmbeddingRecord, ...] = ()

    def create_via_postgres_azure_ai(
        self,
        *,
        memory_id: UUID,
        content: str,
        embedding_model: str,
        content_hash: str,
        created_at: datetime,
        azure_openai_deployment: str,
        azure_openai_dimensions: int | None,
    ) -> MemoryEmbeddingRecord:
        self.azure_calls.append(
            {
                "memory_id": memory_id,
                "content": content,
                "embedding_model": embedding_model,
                "content_hash": content_hash,
                "created_at": created_at,
                "azure_openai_deployment": azure_openai_deployment,
                "azure_openai_dimensions": azure_openai_dimensions,
            }
        )
        if self.azure_error is not None:
            raise self.azure_error
        if self.azure_result is None:
            self.azure_result = MemoryEmbeddingRecord(
                memory_embedding_id=uuid4(),
                memory_id=memory_id,
                embedding_model=embedding_model,
                embedding=(0.1, 0.2, 0.3),
                content_hash=content_hash,
                created_at=created_at,
            )
        self.create(self.azure_result)
        return self.azure_result

    def find_similar_by_query_via_postgres_azure_ai(
        self,
        query: str,
        *,
        azure_openai_deployment: str,
        azure_openai_dimensions: int | None,
        limit: int,
        workspace_id: UUID | None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        self.azure_find_calls.append(
            {
                "query": query,
                "azure_openai_deployment": azure_openai_deployment,
                "azure_openai_dimensions": azure_openai_dimensions,
                "limit": limit,
                "workspace_id": workspace_id,
            }
        )
        return self.azure_find_result


def _build_service(
    *,
    embedding_repository=None,
    embedding_generator=None,
    episode_repository=None,
    memory_item_repository=None,
) -> MemoryService:
    return MemoryService(
        episode_repository=episode_repository or InMemoryEpisodeRepository(),
        memory_item_repository=memory_item_repository or InMemoryMemoryItemRepository(),
        memory_embedding_repository=embedding_repository,
        embedding_generator=embedding_generator,
    )


def _patch_embedding_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    execution_mode=EmbeddingExecutionMode.APP_GENERATED,
    azure_openai_embedding_deployment: str | None = None,
    dimensions: int | None = 8,
    model: str = "test-model",
    auth_mode_value: str = "auto",
) -> None:
    settings = SimpleNamespace(
        embedding=SimpleNamespace(
            enabled=enabled,
            execution_mode=execution_mode,
            azure_openai_embedding_deployment=azure_openai_embedding_deployment,
            dimensions=dimensions,
            model=model,
            azure_openai_auth_mode=SimpleNamespace(value=auth_mode_value),
        )
    )
    monkeypatch.setattr(
        "ctxledger.memory.service_core_search.SearchHelperMixin._load_embedding_settings",
        lambda self: settings.embedding,
    )


def test_score_memory_item_for_query_covers_content_and_metadata_matches() -> None:
    service = _build_service()
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Projection drift root cause",
        metadata={
            "kind": "root-cause",
            "component": "projection",
            "note": "drift found",
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    score, matched_fields = service._score_memory_item_for_query(
        memory_item=memory_item,
        normalized_query="drift",
    )

    assert score == 4.5
    assert matched_fields == ("content", "metadata_values")


def test_score_memory_item_for_query_handles_metadata_only_matches() -> None:
    service = _build_service()
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="No lexical overlap here",
        metadata={"drift_key": "stable", "kind": "background"},
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    key_score, key_fields = service._score_memory_item_for_query(
        memory_item=memory_item,
        normalized_query="drift",
    )
    value_score, value_fields = service._score_memory_item_for_query(
        memory_item=memory_item,
        normalized_query="background",
    )

    assert key_score == 1.5
    assert key_fields == ("metadata_keys",)
    assert value_score == 1.5
    assert value_fields == ("metadata_values",)


def test_parse_uuid_returns_uuid_and_raises_memory_service_error() -> None:
    service = _build_service()
    value = str(uuid4())

    assert service._parse_uuid(
        value,
        field_name="workflow_instance_id",
        feature=MemoryFeature.SEARCH,
    ) == UUID(value)

    with pytest.raises(MemoryServiceError) as exc_info:
        service._parse_uuid(
            "not-a-uuid",
            field_name="workflow_instance_id",
            feature=MemoryFeature.SEARCH,
        )

    assert exc_info.value.code == MemoryErrorCode.INVALID_REQUEST
    assert exc_info.value.feature == MemoryTypesFeature.SEARCH
    assert exc_info.value.details == {"field": "workflow_instance_id"}


def test_build_semantic_match_details_returns_not_configured_without_repository() -> (
    None
):
    service = _build_service(embedding_repository=None)

    result = service._build_semantic_match_details(
        request_query="projection drift",
        workspace_id=None,
        limit=5,
    )

    assert result == ((), False, "embedding_search_not_configured", {}, {})


def test_build_semantic_match_details_returns_settings_unavailable_when_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_service(embedding_repository=InMemoryMemoryEmbeddingRepository())
    monkeypatch.setattr(
        "ctxledger.memory.service_core_search.SearchHelperMixin._load_embedding_settings",
        lambda self: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
    )

    semantic_matches, generated, skipped_reason, score_by_id, matched_fields = (
        service._build_semantic_match_details(
            request_query="projection drift",
            workspace_id=None,
            limit=5,
        )
    )

    assert semantic_matches == ()
    assert generated is False
    assert skipped_reason == "embedding_settings_unavailable:settings unavailable"
    assert score_by_id == {}
    assert matched_fields == {}


def test_build_semantic_match_details_handles_postgres_azure_ai_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedding_repository = _RecordingAzureEmbeddingRepository()
    service = _build_service(embedding_repository=embedding_repository)

    _patch_embedding_settings(
        monkeypatch,
        execution_mode=EmbeddingExecutionMode.POSTGRES_AZURE_AI,
        azure_openai_embedding_deployment=None,
    )
    result = service._build_semantic_match_details(
        request_query="projection drift",
        workspace_id=None,
        limit=5,
    )
    assert result == (
        (),
        False,
        "postgres_azure_ai_deployment_not_configured",
        {},
        {},
    )

    _patch_embedding_settings(
        monkeypatch,
        execution_mode=EmbeddingExecutionMode.POSTGRES_AZURE_AI,
        azure_openai_embedding_deployment="embed-deploy",
        dimensions=16,
    )
    workspace_id = uuid4()
    result = service._build_semantic_match_details(
        request_query="projection drift",
        workspace_id=workspace_id,
        limit=7,
    )
    assert result == ((), True, None, {}, {})
    assert embedding_repository.azure_find_calls == [
        {
            "query": "projection drift",
            "azure_openai_deployment": "embed-deploy",
            "azure_openai_dimensions": 16,
            "limit": 7,
            "workspace_id": workspace_id,
        }
    ]


def test_build_semantic_match_details_handles_generator_missing_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedding_repository = InMemoryMemoryEmbeddingRepository()
    service = _build_service(
        embedding_repository=embedding_repository,
        embedding_generator=None,
    )
    _patch_embedding_settings(monkeypatch)

    result = service._build_semantic_match_details(
        request_query="projection drift",
        workspace_id=None,
        limit=5,
    )
    assert result == ((), False, "embedding_search_not_configured", {}, {})

    failing_generator = _FailingEmbeddingGenerator(provider="custom-http")
    service = _build_service(
        embedding_repository=embedding_repository,
        embedding_generator=failing_generator,
    )
    result = service._build_semantic_match_details(
        request_query="projection drift",
        workspace_id=None,
        limit=5,
    )
    assert result == ((), False, "embedding_generation_failed:custom-http", {}, {})


def test_build_semantic_match_details_scores_equal_similarity_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedding_repository = InMemoryMemoryEmbeddingRepository()
    generator = _FixedEmbeddingGenerator(
        EmbeddingResult(
            provider="test",
            model="test-model",
            vector=(1.0, 0.0),
            content_hash="query-hash",
        )
    )
    service = _build_service(
        embedding_repository=embedding_repository,
        embedding_generator=generator,
    )
    _patch_embedding_settings(monkeypatch)

    first_memory_id = uuid4()
    second_memory_id = uuid4()
    created_at = datetime(2024, 1, 2, tzinfo=UTC)
    embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=first_memory_id,
            embedding_model="test-model",
            embedding=(1.0, 0.0),
            content_hash="first-hash",
            created_at=created_at,
        )
    )
    embedding_repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=second_memory_id,
            embedding_model="test-model",
            embedding=(1.0, 0.0),
            content_hash="second-hash",
            created_at=created_at,
        )
    )

    semantic_matches, generated, skipped_reason, score_by_id, matched_fields = (
        service._build_semantic_match_details(
            request_query="projection drift",
            workspace_id=None,
            limit=5,
        )
    )

    assert generated is True
    assert skipped_reason is None
    assert len(semantic_matches) == 2
    assert score_by_id[first_memory_id] == 1.0
    assert score_by_id[second_memory_id] == 0.25
    assert matched_fields[first_memory_id] == ("embedding_similarity",)
    assert matched_fields[second_memory_id] == ("embedding_similarity",)


def test_selected_continuation_target_details_covers_disabled_invalid_and_empty_paths() -> (
    None
):
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    service = _build_service(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
    )

    assert service._selected_continuation_target_details(
        selected_task_recall_bonus_enabled=False,
        selected_task_recall_workflow_id=str(uuid4()),
        limit=5,
    ) == (set(), None)

    assert service._selected_continuation_target_details(
        selected_task_recall_bonus_enabled=True,
        selected_task_recall_workflow_id="not-a-uuid",
        limit=5,
    ) == (set(), None)

    workflow_id = uuid4()
    assert service._selected_continuation_target_details(
        selected_task_recall_bonus_enabled=True,
        selected_task_recall_workflow_id=str(workflow_id),
        limit=5,
    ) == (set(), None)


def test_selected_continuation_target_details_returns_memory_ids_and_first_episode_id() -> (
    None
):
    workflow_id = uuid4()
    first_episode_id = uuid4()
    second_episode_id = uuid4()
    first_memory_id = uuid4()
    second_memory_id = uuid4()
    created_at = datetime(2024, 1, 3, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=first_episode_id,
            workflow_instance_id=workflow_id,
            summary="First episode",
            attempt_id=None,
            metadata={},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=second_episode_id,
            workflow_instance_id=workflow_id,
            summary="Second episode",
            attempt_id=None,
            metadata={},
            created_at=created_at.replace(day=4),
            updated_at=created_at.replace(day=4),
        )
    )

    memory_item_repository = InMemoryMemoryItemRepository()
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=first_memory_id,
            workspace_id=uuid4(),
            episode_id=first_episode_id,
            type="episode_note",
            provenance="episode",
            content="First memory",
            metadata={},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=second_memory_id,
            workspace_id=uuid4(),
            episode_id=second_episode_id,
            type="episode_note",
            provenance="episode",
            content="Second memory",
            metadata={},
            created_at=created_at.replace(day=4),
            updated_at=created_at.replace(day=4),
        )
    )

    service = _build_service(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
    )

    memory_ids, selected_episode_id = service._selected_continuation_target_details(
        selected_task_recall_bonus_enabled=True,
        selected_task_recall_workflow_id=str(workflow_id),
        limit=10,
    )

    assert memory_ids == {first_memory_id, second_memory_id}
    assert selected_episode_id == second_episode_id


def test_maybe_store_embedding_covers_missing_repo_settings_disabled_and_generator_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Persist embedding",
        metadata={"kind": "note"},
        created_at=datetime(2024, 1, 5, tzinfo=UTC),
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )

    service = _build_service(embedding_repository=None)
    assert service._maybe_store_embedding(memory_item) == {
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }

    service = _build_service(embedding_repository=InMemoryMemoryEmbeddingRepository())
    monkeypatch.setattr(
        "ctxledger.memory.service_core_search.SearchHelperMixin._load_embedding_settings",
        lambda self: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
    )
    result = service._maybe_store_embedding(memory_item)
    assert result["embedding_persistence_status"] == "failed"
    assert (
        result["embedding_generation_skipped_reason"]
        == "embedding_settings_unavailable"
    )
    assert result["embedding_generation_failure"] == {
        "provider": "config",
        "message": "settings unavailable",
        "details": {},
    }

    _patch_embedding_settings(monkeypatch, enabled=False)
    result = service._maybe_store_embedding(memory_item)
    assert result == {
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_generation_disabled",
    }

    _patch_embedding_settings(monkeypatch, enabled=True)
    service = _build_service(
        embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )
    result = service._maybe_store_embedding(memory_item)
    assert result == {
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_generator_not_configured",
    }


def test_maybe_store_embedding_covers_postgres_azure_ai_and_generator_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Persist embedding",
        metadata={"kind": "note"},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
        updated_at=datetime(2024, 1, 6, tzinfo=UTC),
    )

    embedding_repository = _RecordingAzureEmbeddingRepository()
    service = _build_service(embedding_repository=embedding_repository)

    _patch_embedding_settings(
        monkeypatch,
        execution_mode=EmbeddingExecutionMode.POSTGRES_AZURE_AI,
        azure_openai_embedding_deployment=None,
    )
    result = service._maybe_store_embedding(memory_item)
    assert result["embedding_persistence_status"] == "failed"
    assert (
        result["embedding_generation_skipped_reason"]
        == "postgres_azure_ai_deployment_not_configured"
    )

    _patch_embedding_settings(
        monkeypatch,
        execution_mode=EmbeddingExecutionMode.POSTGRES_AZURE_AI,
        azure_openai_embedding_deployment="embed-deploy",
        dimensions=32,
        model="azure-model",
        auth_mode_value="subscription_key",
    )
    embedding_repository.azure_error = RuntimeError("azure failed")
    result = service._maybe_store_embedding(memory_item)
    assert result["embedding_persistence_status"] == "failed"
    assert (
        result["embedding_generation_skipped_reason"]
        == "embedding_generation_failed:postgres_azure_ai"
    )
    assert result["embedding_generation_failure"] == {
        "provider": "postgres_azure_ai",
        "message": "azure failed",
        "details": {
            "deployment": "embed-deploy",
            "auth_mode": "subscription_key",
        },
    }

    embedding_repository.azure_error = None
    embedding_repository.azure_result = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_item.memory_id,
        embedding_model="azure-model",
        embedding=(0.1, 0.2, 0.3, 0.4),
        content_hash="azure-hash",
        created_at=memory_item.updated_at,
    )
    result = service._maybe_store_embedding(memory_item)
    assert result == {
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "postgres_azure_ai",
        "embedding_model": "azure-model",
        "embedding_vector_dimensions": 4,
        "embedding_content_hash": "azure-hash",
    }

    app_embedding_repository = InMemoryMemoryEmbeddingRepository()
    failing_generator = _FailingEmbeddingGenerator(provider="openai")
    service = _build_service(
        embedding_repository=app_embedding_repository,
        embedding_generator=failing_generator,
    )
    _patch_embedding_settings(monkeypatch)
    result = service._maybe_store_embedding(memory_item)
    assert result["embedding_persistence_status"] == "failed"
    assert (
        result["embedding_generation_skipped_reason"]
        == "embedding_generation_failed:openai"
    )
    assert result["embedding_generation_failure"] == {
        "provider": "openai",
        "message": "embedding generation failed",
        "details": {"reason": "boom"},
    }

    fixed_generator = _FixedEmbeddingGenerator(
        EmbeddingResult(
            provider="local-stub",
            model="stub-model",
            vector=(0.5, 0.25),
            content_hash="stub-hash",
        )
    )
    service = _build_service(
        embedding_repository=app_embedding_repository,
        embedding_generator=fixed_generator,
    )
    result = service._maybe_store_embedding(memory_item)
    assert result == {
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "local-stub",
        "embedding_model": "stub-model",
        "embedding_vector_dimensions": 2,
        "embedding_content_hash": "stub-hash",
    }
    stored_embeddings = app_embedding_repository.list_by_memory_id(
        memory_item.memory_id,
        limit=10,
    )
    assert len(stored_embeddings) == 1
    assert stored_embeddings[0].embedding_model == "stub-model"
    assert stored_embeddings[0].embedding == (0.5, 0.25)
