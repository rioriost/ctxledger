from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.mcp.tool_handlers import (
    build_memory_get_context_tool_handler,
    build_memory_remember_episode_tool_handler,
    build_memory_search_tool_handler,
)
from ctxledger.memory.service import (
    MemoryFeature,
)

from .conftest import (
    FakeMemoryService,
    make_get_context_response,
    make_memory_error,
    make_remember_episode_response,
    make_search_memory_response,
)


def test_build_memory_remember_episode_tool_handler_returns_success() -> None:
    service = FakeMemoryService(remember_result=make_remember_episode_response())
    handler = build_memory_remember_episode_tool_handler(service)

    response = handler(
        {
            "workflow_instance_id": uuid4(),
            "summary": "remember this",
            "attempt_id": uuid4(),
            "metadata": {"kind": "checkpoint"},
        }
    )

    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_remember_episode"
    assert response.payload["result"]["implemented"] is True
    assert response.payload["result"]["message"] == "Episode recorded successfully."
    assert response.payload["result"]["status"] == "recorded"
    assert response.payload["result"]["available_in_version"] == "0.2.0"
    assert "timestamp" in response.payload["result"]
    assert response.payload["result"]["episode"]["summary"] == "remember this"
    assert response.payload["result"]["episode"]["metadata"] == {"kind": "checkpoint"}
    assert response.payload["result"]["episode"]["status"] == "recorded"
    assert response.payload["result"]["details"]["workflow_instance_id"]
    assert response.payload["result"]["details"]["attempt_id"]

    assert service.remember_calls is not None
    call = service.remember_calls[0]
    assert isinstance(call.workflow_instance_id, str)
    assert call.summary == "remember this"
    assert isinstance(call.attempt_id, str)
    assert call.metadata == {"kind": "checkpoint"}


def test_build_memory_remember_episode_tool_handler_maps_memory_error() -> None:
    service = FakeMemoryService(
        remember_exc=make_memory_error(
            "bad episode",
            feature="memory_remember_episode",
            details={"field": "summary"},
        )
    )
    handler = build_memory_remember_episode_tool_handler(service)

    response = handler({"summary": ""})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "memory_invalid_request",
            "message": "bad episode",
            "details": {"field": "summary"},
        },
    }


def test_build_memory_search_tool_handler_uses_defaults_for_invalid_optional_values() -> (
    None
):
    service = FakeMemoryService(search_result=make_search_memory_response())
    handler = build_memory_search_tool_handler(service)

    response = handler(
        {
            "query": "needle",
            "workspace_id": uuid4(),
            "limit": "bad",
            "filters": [],
        }
    )

    payload = response.payload
    result = payload["result"]

    assert payload["ok"] is True
    assert result["feature"] == "memory_search"
    assert result["implemented"] is True
    assert (
        result["message"]
        == "Hybrid lexical and semantic memory search completed successfully."
    )
    assert result["status"] == "ok"
    assert result["available_in_version"] == "0.3.0"
    assert result["details"]["query"] == "needle"
    assert result["details"]["normalized_query"] == "needle"
    assert result["details"]["limit"] == 10
    assert result["details"]["filters"] == {}
    assert result["details"]["search_mode"] == "hybrid_memory_item_search"
    assert result["details"]["memory_items_considered"] == 1
    assert result["details"]["semantic_candidates_considered"] == 1
    assert result["details"]["semantic_query_generated"] is True
    assert result["details"]["hybrid_scoring"] == {
        "lexical_weight": 1.0,
        "semantic_weight": 1.0,
        "semantic_only_discount": 0.75,
    }
    assert result["details"]["result_mode_counts"] == {
        "lexical_only": 1,
        "hybrid": 0,
        "semantic_only_discounted": 0,
    }
    assert result["details"]["result_composition"] == {
        "with_lexical_signal": 1,
        "with_semantic_signal": 0,
        "with_both_signals": 0,
    }
    assert result["details"]["results_returned"] == 1
    assert "timestamp" in result

    [search_result] = result["results"]
    assert search_result["summary"] == "needle found in summary"
    assert search_result["score"] == 3.0
    assert search_result["matched_fields"] == ["content"]
    assert search_result["lexical_score"] == 3.0
    assert search_result["semantic_score"] == 0.0
    assert search_result["ranking_details"] == {
        "lexical_component": 3.0,
        "semantic_component": 0.0,
        "score_mode": "lexical_only",
        "semantic_only_discount_applied": False,
    }

    assert service.search_calls is not None
    call = service.search_calls[0]
    assert call.query == "needle"
    assert isinstance(call.workspace_id, str)
    assert call.limit == 10
    assert call.filters == {}


def test_build_memory_search_tool_handler_maps_memory_error() -> None:
    service = FakeMemoryService(
        search_exc=make_memory_error(
            "not found",
            feature="memory_search",
            details={"query": "needle"},
        )
    )
    handler = build_memory_search_tool_handler(service)

    response = handler({"query": "needle"})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "memory_invalid_request",
            "message": "not found",
            "details": {"query": "needle"},
        },
    }


def test_build_memory_get_context_tool_handler_uses_defaults_for_optional_values() -> (
    None
):
    workflow_instance_id = uuid4()
    service = FakeMemoryService(context_result=make_get_context_response())
    handler = build_memory_get_context_tool_handler(service)

    response = handler(
        {
            "query": 123,
            "workspace_id": uuid4(),
            "workflow_instance_id": workflow_instance_id,
            "ticket_id": 999,
            "limit": "bad",
            "include_episodes": "bad",
            "include_memory_items": "bad",
            "include_summaries": "bad",
        }
    )

    payload = response.payload
    result = payload["result"]

    assert payload["ok"] is True
    assert result["feature"] == MemoryFeature.GET_CONTEXT.value
    assert result["implemented"] is True
    assert (
        result["message"] == "Episode-oriented memory context retrieved successfully."
    )
    assert result["status"] == "ok"
    assert result["available_in_version"] == "0.2.0"
    assert result["details"] == {
        "episodes_returned": 0,
        "memory_items": [],
        "memory_item_counts_by_episode": {},
        "summaries": [],
    }
    assert result["episodes"] == []

    timestamp = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert result["timestamp"] == timestamp.isoformat()

    assert service.context_calls is not None
    call = service.context_calls[0]
    assert call.query == "123"
    assert isinstance(call.workspace_id, str)
    assert isinstance(call.workflow_instance_id, str)
    assert call.ticket_id == "999"
    assert call.limit == 10
    assert call.include_episodes is True
    assert call.include_memory_items is True
    assert call.include_summaries is True


def test_build_memory_get_context_tool_handler_maps_memory_error() -> None:
    service = FakeMemoryService(
        context_exc=make_memory_error(
            "bad context request",
            feature="memory_get_context",
            details={"field": "workspace_id"},
        )
    )
    handler = build_memory_get_context_tool_handler(service)

    response = handler({"workspace_id": "bad"})

    assert response.payload == {
        "ok": False,
        "error": {
            "code": "memory_invalid_request",
            "message": "bad context request",
            "details": {"field": "workspace_id"},
        },
    }
