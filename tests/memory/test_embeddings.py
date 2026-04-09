from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.config import (
    AzureOpenAIAuthMode,
    EmbeddingExecutionMode,
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
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryFeature,
    MemoryService,
    RememberEpisodeRequest,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)
from ctxledger.runtime.introspection import RuntimeIntrospection
from ctxledger.runtime.serializers import (
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
    serialize_search_memory_response,
    serialize_stub_response,
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


@pytest.fixture(autouse=True)
def patch_embedding_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        embedding=SimpleNamespace(
            enabled=True,
            provider=EmbeddingProvider.LOCAL_STUB,
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            azure_openai_embedding_deployment=None,
            dimensions=8,
            model="local-stub-v1",
            azure_openai_auth_mode=SimpleNamespace(value="auto"),
        )
    )
    monkeypatch.setattr(
        "ctxledger.memory.service_core_search.SearchHelperMixin._load_embedding_settings",
        lambda self: settings.embedding,
    )
    monkeypatch.setattr(
        "ctxledger.memory.service_core.service_module.get_settings",
        lambda: settings,
    )


def test_build_embedding_generator_returns_disabled_generator_when_disabled() -> None:
    generator = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="unused",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
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
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="local-stub-v1",
            api_key=None,
            base_url=None,
            dimensions=8,
            enabled=True,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
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
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="text-embedding-3-small",
            api_key="secret",
            base_url=None,
            dimensions=1536,
            enabled=True,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
        )
    )

    assert isinstance(generator, ExternalAPIEmbeddingGenerator)
    assert generator.provider is EmbeddingProvider.OPENAI
    assert generator.model == "text-embedding-3-small"
    assert generator.base_url == "https://api.openai.com/v1/embeddings"


def test_build_embedding_generator_returns_default_external_generators_for_other_providers() -> (
    None
):
    voyage = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.VOYAGEAI,
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="voyage-3",
            api_key="secret",
            base_url=None,
            dimensions=1024,
            enabled=True,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
        )
    )
    cohere = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.COHERE,
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="embed-english-v3.0",
            api_key="secret",
            base_url=None,
            dimensions=1024,
            enabled=True,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
        )
    )
    custom = build_embedding_generator(
        EmbeddingSettings(
            provider=EmbeddingProvider.CUSTOM_HTTP,
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="custom-model",
            api_key="secret",
            base_url=None,
            dimensions=1024,
            enabled=True,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
        )
    )

    assert isinstance(voyage, ExternalAPIEmbeddingGenerator)
    assert voyage.provider is EmbeddingProvider.VOYAGEAI
    assert voyage.base_url == "https://api.voyageai.com/v1"

    assert isinstance(cohere, ExternalAPIEmbeddingGenerator)
    assert cohere.provider is EmbeddingProvider.COHERE
    assert cohere.base_url == "https://api.cohere.com/v1"

    assert isinstance(custom, ExternalAPIEmbeddingGenerator)
    assert custom.provider is EmbeddingProvider.CUSTOM_HTTP
    assert custom.base_url == ""


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


def test_external_embedding_generator_rejects_empty_text_before_api_key_validation() -> (
    None
):
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model="text-embedding-3-small",
        api_key=None,
        base_url="https://api.openai.com/v1",
    )

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="   "))

    assert exc_info.value.provider == "openai"
    assert exc_info.value.details == {"field": "text"}


def test_external_embedding_generator_reports_unimplemented_provider_details() -> None:
    generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.VOYAGEAI,
        model="voyage-3",
        api_key="secret",
        base_url="https://api.voyageai.com/v1",
    )

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world", model="voyage-3-lite"))

    assert exc_info.value.provider == "voyageai"
    assert exc_info.value.details == {
        "provider": "voyageai",
        "model": "voyage-3-lite",
        "base_url": "https://api.voyageai.com/v1",
    }


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

    class FakeHTTPErrorBody:
        def read(self) -> bytes:
            return b'{"error":"temporary outage"}'

        def close(self) -> None:
            return None

    def fake_urlopen(_request: object) -> object:
        from urllib import error as urllib_error

        raise urllib_error.HTTPError(
            url="https://embeddings.example.com/v1",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=FakeHTTPErrorBody(),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details["status_code"] == 503
    assert exc_info.value.details["base_url"] == "https://embeddings.example.com/v1"
    assert exc_info.value.details["response_body"] == '{"error":"temporary outage"}'


def test_custom_http_embedding_generator_reports_url_error_details(
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

        raise urllib_error.URLError("connection reset")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(EmbeddingGenerationError) as exc_info:
        generator.generate(EmbeddingRequest(text="hello world"))

    assert exc_info.value.provider == "custom_http"
    assert exc_info.value.details == {
        "base_url": "https://embeddings.example.com/v1",
        "reason": "connection reset",
    }


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


def test_compute_content_hash_normalizes_text_and_defaults_metadata() -> None:
    normalized = compute_content_hash("  same text  ", None)
    explicit = compute_content_hash("same text", {})

    assert normalized == explicit


def test_embedding_result_supports_request_model_override_for_local_stub() -> None:
    generator = LocalStubEmbeddingGenerator(model="local-stub-v1", dimensions=4)

    result = generator.generate(
        EmbeddingRequest(
            text="hello world",
            model="override-model",
            metadata={"kind": "episode"},
        )
    )

    assert result.model == "override-model"
    assert len(result.vector) == 4
