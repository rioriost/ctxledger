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
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryFeature,
    MemoryItemRecord,
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
    assert (
        payload["message"]
        == "Hybrid lexical and semantic memory search completed successfully."
    )
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
            },
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]


def test_build_embedding_generator_returns_disabled_generator_when_disabled() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            model="unused",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
        )
    )

    assert isinstance(generator, DisabledEmbeddingGenerator)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello"))

    assert exc_info.value.provider == "disabled"


def test_memory_service_persists_local_stub_embedding_after_memory_item_ingest() -> (
    None
):
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-EMBED-1",
            }
        }
    )
    embedding_generator = LocalStubEmbeddingGenerator(
        model="local-stub-v1",
        dimensions=8,
    )
    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=embedding_generator,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    response = service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(workflow_id),
            summary="Persist embedding for this memory item",
            metadata={"kind": "checkpoint", "component": "memory"},
        )
    )

    assert response.feature == MemoryFeature.REMEMBER_EPISODE
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 1
    assert (
        memory_embedding_repository.embeddings[0].memory_id
        == memory_item_repository.memory_items[0].memory_id
    )
    assert memory_embedding_repository.embeddings[0].embedding_model == "local-stub-v1"
    assert len(memory_embedding_repository.embeddings[0].embedding) == 8
    assert memory_embedding_repository.embeddings[
        0
    ].content_hash == compute_content_hash(
        "Persist embedding for this memory item",
        {"kind": "checkpoint", "component": "memory"},
    )


def test_memory_service_persists_openai_embedding_after_memory_item_ingest() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "ticket_id": "TICKET-EMBED-2",
            }
        }
    )

    class FixedOpenAIEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            assert request.text == "External embedding provider remains optional"
            assert request.metadata == {"kind": "checkpoint", "component": "memory"}
            return EmbeddingResult(
                provider="openai",
                model="text-embedding-3-small",
                vector=(0.25, -0.5, 1.0),
                content_hash=compute_content_hash(
                    "External embedding provider remains optional",
                    {"kind": "checkpoint", "component": "memory"},
                ),
            )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=FixedOpenAIEmbeddingGenerator(),
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    response = service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(workflow_id),
            summary="External embedding provider remains optional",
            metadata={"kind": "checkpoint", "component": "memory"},
        )
    )

    assert response.feature == MemoryFeature.REMEMBER_EPISODE
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 1
    assert (
        memory_embedding_repository.embeddings[0].memory_id
        == memory_item_repository.memory_items[0].memory_id
    )
    assert memory_embedding_repository.embeddings[0].embedding_model == (
        "text-embedding-3-small"
    )
    assert memory_embedding_repository.embeddings[0].embedding == (0.25, -0.5, 1.0)
    assert memory_embedding_repository.embeddings[
        0
    ].content_hash == compute_content_hash(
        "External embedding provider remains optional",
        {"kind": "checkpoint", "component": "memory"},
    )


def test_build_embedding_generator_returns_local_stub_generator() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.LOCAL_STUB,
            model="local-stub-v1",
            api_key=None,
            base_url=None,
            dimensions=8,
            enabled=True,
        )
    )

    assert isinstance(generator, LocalStubEmbeddingGenerator)

    result = generator.generate(
        EmbeddingRequest(
            text="hello world",
            metadata={"kind": "checkpoint"},
        )
    )

    assert result.provider == "local_stub"
    assert result.model == "local-stub-v1"
    assert len(result.vector) == 8
    assert result.content_hash == compute_content_hash(
        "hello world",
        {"kind": "checkpoint"},
    )
    assert all(-1.0 <= value <= 1.0 for value in result.vector)


def test_local_stub_embedding_generator_is_deterministic() -> None:
    generator = LocalStubEmbeddingGenerator(model="local-stub-v1", dimensions=6)

    first = generator.generate(
        EmbeddingRequest(
            text="deterministic text",
            metadata={"kind": "episode"},
        )
    )
    second = generator.generate(
        EmbeddingRequest(
            text="deterministic text",
            metadata={"kind": "episode"},
        )
    )

    assert first == second
    assert len(first.vector) == 6


def test_local_stub_embedding_generator_rejects_empty_text() -> None:
    generator = LocalStubEmbeddingGenerator(model="local-stub-v1", dimensions=4)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="   "))

    assert exc_info.value.provider == "local_stub"
    assert exc_info.value.details == {"field": "text"}


def test_build_embedding_generator_returns_openai_generator_by_default_shape() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            api_key="secret",
            base_url=None,
            dimensions=1536,
            enabled=True,
        )
    )

    assert isinstance(generator, ExternalAPIEmbeddingGenerator)
    assert generator.provider is EmbeddingProvider.OPENAI
    assert generator.model == "text-embedding-3-small"
    assert generator.base_url == "https://api.openai.com/v1/embeddings"


def test_external_embedding_generator_requires_api_key_at_runtime() -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model="text-embedding-3-small",
        api_key=None,
        base_url="https://api.openai.com/v1",
    )

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello"))

    assert exc_info.value.provider == "openai"
    assert exc_info.value.details == {"field": "api_key"}


def test_openai_embedding_generator_posts_expected_request_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model="text-embedding-3-small",
        api_key="secret",
        base_url="https://api.openai.com/v1/embeddings",
    )
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "data": [
                        {
                            "embedding": [0.125, -0.25, 0.5],
                        }
                    ],
                    "model": "text-embedding-3-small",
                }
            ).encode("utf-8")

    def fake_urlopen(request: object) -> FakeResponse:
        captured["full_url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["accept"] = request.get_header("Accept")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = generator.generate(
        EmbeddingRequest(
            text="hello world",
            metadata={"kind": "episode"},
        )
    )

    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.vector == (0.125, -0.25, 0.5)
    assert result.content_hash == compute_content_hash(
        "hello world",
        {"kind": "episode"},
    )
    assert captured == {
        "full_url": "https://api.openai.com/v1/embeddings",
        "method": "POST",
        "authorization": "Bearer secret",
        "content_type": "application/json",
        "accept": "application/json",
        "body": {
            "input": "hello world",
            "model": "text-embedding-3-small",
        },
    }


def test_custom_http_embedding_generator_returns_embedding_from_top_level_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "custom-model-v2",
                    "embedding": [0.25, -0.5, 1],
                }
            ).encode("utf-8")

    def fake_urlopen(request: object) -> FakeResponse:
        captured["full_url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["accept"] = request.get_header("Accept")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = generator.generate(
        EmbeddingRequest(
            text="hello world",
            metadata={"kind": "episode"},
        )
    )

    assert result.provider == "custom_http"
    assert result.model == "custom-model-v2"
    assert result.vector == (0.25, -0.5, 1.0)
    assert result.content_hash == compute_content_hash(
        "hello world",
        {"kind": "episode"},
    )
    assert captured == {
        "full_url": "https://embeddings.example.com/v1",
        "method": "POST",
        "authorization": "Bearer secret",
        "content_type": "application/json",
        "accept": "application/json",
        "body": {
            "text": "hello world",
            "model": "custom-model",
            "metadata": {"kind": "episode"},
        },
    }


def test_custom_http_embedding_generator_returns_embedding_from_nested_data_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "data": [
                        {
                            "model": "nested-model",
                            "embedding": [1, 2.5, -3],
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda _request: FakeResponse())

    result = generator.generate(EmbeddingRequest(text="hello world"))

    assert result.provider == "custom_http"
    assert result.model == "nested-model"
    assert result.vector == (1.0, 2.5, -3.0)


def test_custom_http_embedding_generator_reports_http_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    def fake_urlopen(_request: object) -> object:
        from urllib import error as urllib_error

        raise urllib_error.HTTPError(
            url="https://embeddings.example.com/v1",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details["status_code"] == 503
    assert exc_info.value.details["base_url"] == "https://embeddings.example.com/v1"


def test_custom_http_embedding_generator_rejects_invalid_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr("urllib.request.urlopen", lambda _request: FakeResponse())

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details["base_url"] == "https://embeddings.example.com/v1"
    assert exc_info.value.details["response_body"] == "not-json"


def test_custom_http_embedding_generator_rejects_missing_embedding_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.CUSTOM_HTTP,
        model="custom-model",
        api_key="secret",
        base_url="https://embeddings.example.com/v1",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"data": [{"model": "custom-model"}]}).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda _request: FakeResponse())

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details == {"field": "embedding"}


def test_in_memory_memory_embedding_repository_find_similar_orders_by_similarity() -> (
    None
):
    repository = InMemoryMemoryEmbeddingRepository()
    first_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="first-hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.5, 0.5, 0.0),
        content_hash="second-hash",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    third_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0, 0.0),
        content_hash="third-hash",
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )

    repository.create(first_embedding)
    repository.create(second_embedding)
    repository.create(third_embedding)

    matches = repository.find_similar((1.0, 0.0, 0.0), limit=2)

    assert matches == (first_embedding, second_embedding)


def test_in_memory_memory_embedding_repository_find_similar_ignores_dimension_mismatch() -> (
    None
):
    repository = InMemoryMemoryEmbeddingRepository()
    matching_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0),
        content_hash="matching-hash",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    mismatched_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="mismatched-hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    repository.create(matching_embedding)
    repository.create(mismatched_embedding)

    matches = repository.find_similar((0.0, 1.0), limit=5)

    assert matches == (matching_embedding,)


def test_in_memory_memory_embedding_repository_find_similar_returns_empty_for_empty_query() -> (
    None
):
    repository = InMemoryMemoryEmbeddingRepository()
    repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=uuid4(),
            embedding_model="local-stub-v1",
            embedding=(1.0, 0.0),
            content_hash="hash",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )

    matches = repository.find_similar((), limit=5)

    assert matches == ()


def test_compute_content_hash_uses_text_and_metadata() -> None:
    first = compute_content_hash("same text", {"kind": "episode"})
    second = compute_content_hash("same text", {"kind": "episode"})
    different_text = compute_content_hash("other text", {"kind": "episode"})
    different_metadata = compute_content_hash("same text", {"kind": "checkpoint"})

    assert first == second
    assert first != different_text
    assert first != different_metadata


def test_in_memory_workflow_lookup_repository_workspace_id_by_workflow_id() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()

    repository = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-REPO-1",
            }
        }
    )

    assert repository.workspace_id_by_workflow_id(workflow_id) == workspace_id
    assert repository.workspace_id_by_workflow_id(uuid4()) is None


def test_in_memory_workflow_lookup_repository_workspace_id_by_workflow_id_without_workspace() -> (
    None
):
    workflow_id = uuid4()
    repository = InMemoryWorkflowLookupRepository(
        workflows_by_id={workflow_id: {"ticket_id": "TICKET-REPO-2"}}
    )

    assert repository.workspace_id_by_workflow_id(workflow_id) is None


def test_in_memory_memory_item_repository_get_by_memory_id_returns_none_for_unknown_id() -> (
    None
):
    repository = InMemoryMemoryItemRepository()

    assert repository.get_by_memory_id(uuid4()) is None


def test_in_memory_memory_item_repository_lists_items_by_memory_ids_in_request_order() -> (
    None
):
    repository = InMemoryMemoryItemRepository()
    workspace_id = uuid4()
    missing_memory_id = uuid4()

    first_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First root item",
        metadata={"kind": "first"},
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    second_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Second episode item",
        metadata={"kind": "second"},
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )

    repository.create(first_item)
    repository.create(second_item)

    assert repository.list_by_memory_ids(
        (
            second_item.memory_id,
            missing_memory_id,
            first_item.memory_id,
        ),
        limit=5,
    ) == (
        second_item,
        first_item,
    )


def test_in_memory_memory_relation_repository_lists_source_and_target_matches_in_recency_order() -> (
    None
):
    repository = MemoryService()._memory_relation_repository
    source_memory_id = uuid4()
    target_memory_id = uuid4()
    other_source_memory_id = uuid4()
    other_target_memory_id = uuid4()

    older_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=other_target_memory_id,
        relation_type="supports",
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    newer_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    target_match_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=other_source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        created_at=datetime(2024, 2, 3, tzinfo=UTC),
    )

    repository.create(older_relation)
    repository.create(newer_relation)
    repository.create(target_match_relation)

    assert repository.list_by_source_memory_id(source_memory_id, limit=5) == (
        newer_relation,
        older_relation,
    )
    assert repository.list_by_target_memory_id(target_memory_id, limit=5) == (
        target_match_relation,
        newer_relation,
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
    assert (
        memory_item_repository.memory_items[0].episode_id
        == remember_response.episode.episode_id
    )
    assert memory_item_repository.memory_items[0].type == "episode_note"
    assert memory_item_repository.memory_items[0].provenance == "episode"
    assert (
        memory_item_repository.memory_items[0].content
        == "Episode summary with relevant context"
    )
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
    assert (
        search_response.results[0].memory_id
        == memory_item_repository.memory_items[0].memory_id
    )
    assert search_response.results[0].workspace_id == UUID(
        "00000000-0000-0000-0000-000000000001"
    )
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


def test_memory_service_hybrid_ranking_uses_similarity_gap_for_semantic_scores() -> (
    None
):
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


def test_workflow_memory_bridge_records_completion_memory_with_embedding() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()

    workflow = WorkflowInstance(
        workflow_instance_id=workflow_id,
        workspace_id=workspace_id,
        ticket_id="TICKET-AUTO-MEM-1",
        status=WorkflowInstanceStatus.COMPLETED,
    )
    attempt = WorkflowAttempt(
        attempt_id=attempt_id,
        workflow_instance_id=workflow_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.SUCCEEDED,
        verify_status=VerifyStatus.PASSED,
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        workflow_instance_id=workflow_id,
        attempt_id=attempt_id,
        step_name="validate_openai",
        summary="Broader targeted regression is green",
        checkpoint_json={"next_intended_action": "Review diff and commit"},
    )
    verify_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        report_json={"checks": ["pytest"]},
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=workflow,
        attempt=attempt,
        latest_checkpoint=latest_checkpoint,
        verify_report=verify_report,
        summary="Validated OpenAI embedding integration end to end",
        failure_reason=None,
    )

    assert result is not None
    assert result.episode.workflow_instance_id == workflow_id
    assert result.episode.attempt_id == attempt_id
    assert result.episode.metadata == {
        "auto_generated": True,
        "memory_origin": "workflow_complete_auto",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "attempt_number": 1,
        "verify_status": "passed",
        "step_name": "validate_openai",
        "next_intended_action": "Review diff and commit",
    }
    assert "Completion summary: Validated OpenAI embedding integration end to end" in (
        result.episode.summary
    )
    assert "Latest checkpoint summary: Broader targeted regression is green" in (
        result.episode.summary
    )
    assert "Last planned next action: Review diff and commit" in result.episode.summary
    assert "Verify status: passed" in result.episode.summary

    assert result.memory_item.workspace_id == workspace_id
    assert result.memory_item.episode_id == result.episode.episode_id
    assert result.memory_item.type == "workflow_completion_note"
    assert result.memory_item.provenance == "workflow_complete_auto"
    assert result.memory_item.metadata == result.episode.metadata
    assert result.memory_item.content == result.episode.summary

    assert result.details["embedding_persistence_status"] == "stored"
    assert result.details["embedding_generation_skipped_reason"] is None
    assert result.details["embedding_provider"] == "local_stub"
    assert result.details["embedding_model"] == "local-stub-v1"
    assert result.details["embedding_vector_dimensions"] == 8
    assert result.details["embedding_content_hash"] == compute_content_hash(
        result.memory_item.content,
        result.memory_item.metadata,
    )

    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 1
    assert (
        memory_embedding_repository.embeddings[0].memory_id
        == result.memory_item.memory_id
    )


def test_workflow_memory_bridge_skips_completion_memory_without_summary_sources() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-2",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="checkpointed",
            summary=None,
            checkpoint_json={},
        ),
        verify_report=None,
        summary=None,
        failure_reason=None,
    )

    assert result is not None
    assert result.episode is None
    assert result.memory_item is None
    assert result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "low_signal_checkpoint_closeout",
    }


def test_workflow_memory_bridge_returns_failed_embedding_details_when_generation_fails() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    class FailingEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            raise EmbeddingGenerationError(
                "embedding generation failed",
                provider="openai",
                details={"status_code": 500},
            )

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=FailingEmbeddingGenerator(),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-3",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.SUCCEEDED,
            verify_status=VerifyStatus.PASSED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="validate_openai",
            summary="Broader targeted regression is green",
            checkpoint_json={"next_intended_action": "Review diff and commit"},
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"]},
        ),
        summary="Validated OpenAI embedding integration end to end",
        failure_reason=None,
    )

    assert result is not None
    assert result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "failed",
        "embedding_generation_skipped_reason": "embedding_generation_failed:openai",
        "embedding_generation_failure": {
            "provider": "openai",
            "message": "embedding generation failed",
            "details": {"status_code": 500},
        },
    }


def test_workflow_memory_bridge_post_init_uses_external_generator_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    sentinel_generator = object()
    build_calls: list[object] = []

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: SimpleNamespace(
            embedding=SimpleNamespace(
                enabled=True,
                provider=EmbeddingProvider.OPENAI,
            )
        ),
    )

    def fake_build_embedding_generator(settings: object) -> object:
        build_calls.append(settings)
        return sentinel_generator

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.build_embedding_generator",
        fake_build_embedding_generator,
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    assert bridge.embedding_generator is sentinel_generator
    assert len(build_calls) == 1
    assert build_calls[0].provider is EmbeddingProvider.OPENAI


def test_workflow_memory_bridge_post_init_skips_local_stub_autobuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: SimpleNamespace(
            embedding=SimpleNamespace(
                enabled=True,
                provider=EmbeddingProvider.LOCAL_STUB,
            )
        ),
    )
    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.build_embedding_generator",
        lambda settings: (_ for _ in ()).throw(
            AssertionError("build_embedding_generator should not be called")
        ),
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    assert bridge.embedding_generator is None


def test_workflow_memory_bridge_post_init_swallows_settings_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: (_ for _ in ()).throw(RuntimeError("settings exploded")),
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    assert bridge.embedding_generator is None


def test_workflow_memory_bridge_returns_skip_result_when_summary_sources_are_absent() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-NO-SUMMARY",
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.FAILED,
        ),
        latest_checkpoint=None,
        verify_report=None,
        summary=None,
        failure_reason="failed before summary",
    )

    assert result is not None
    assert result.episode is None
    assert result.memory_item is None
    assert result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "no_completion_summary_source",
    }


def test_workflow_memory_bridge_gating_with_non_dict_checkpoint_payload() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        step_name="bad_payload",
        summary="checkpoint",
        checkpoint_json="not-a-dict",  # type: ignore[arg-type]
    )

    should_record, skipped_reason = bridge._auto_memory_gating_decision(
        workflow=WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="BAD-PAYLOAD",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        latest_checkpoint=checkpoint,
        verify_report=None,
    )

    assert should_record is False
    assert skipped_reason == "low_signal_checkpoint_closeout"


def test_workflow_memory_bridge_recent_memory_handles_missing_listing_support() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="NO-LIST",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()


def test_workflow_memory_bridge_recent_memory_handles_non_callable_listing() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(list_by_workflow_id=123),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="NON-CALLABLE-LIST",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()


def test_workflow_memory_bridge_recent_memory_handles_listing_error() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    def explode(*args: object, **kwargs: object) -> tuple[()]:
        raise RuntimeError("listing exploded")

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(list_by_workflow_id=explode),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="LISTING-ERROR",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()
