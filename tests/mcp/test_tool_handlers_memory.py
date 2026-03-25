from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.mcp.tool_handlers import (
    build_memory_get_context_tool_handler,
    build_memory_remember_episode_tool_handler,
    build_memory_search_tool_handler,
)
from ctxledger.memory.service import (
    GetContextResponse,
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


def test_build_memory_search_tool_handler_uses_defaults_for_invalid_optional_values() -> None:
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
    assert result["message"] == "Hybrid lexical and semantic memory search completed successfully."
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
        "reason_list": [
            {
                "code": "lexical_signal_present",
                "message": "lexical overlap contributed to the ranking score",
                "value": 3.0,
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
        ],
        "task_recall_detail": {
            "matched_fields": ["content"],
            "memory_item_type": "episode_note",
            "memory_item_provenance": "episode",
            "metadata_match_candidates": ["kind checkpoint", "checkpoint"],
            "workspace_constrained": True,
        },
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


def test_build_memory_get_context_tool_handler_uses_defaults_for_optional_values() -> None:
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
    assert result["message"] == "Episode-oriented memory context retrieved successfully."
    assert result["status"] == "ok"
    assert result["available_in_version"] == "0.2.0"
    assert result["details"] == {
        "episodes_returned": 0,
        "memory_items": [],
        "memory_item_counts_by_episode": {},
        "summaries": [],
        "task_recall_selection_present": False,
        "task_recall_selected_workflow_instance_id": None,
        "task_recall_latest_workflow_instance_id": None,
        "task_recall_running_workflow_instance_id": None,
        "task_recall_selected_equals_latest": False,
        "task_recall_selected_equals_running": False,
        "task_recall_latest_workflow_terminal": False,
        "task_recall_latest_ticket_detour_like": False,
        "task_recall_latest_checkpoint_detour_like": False,
        "task_recall_selected_ticket_detour_like": False,
        "task_recall_selected_checkpoint_detour_like": False,
        "task_recall_detour_override_applied": False,
        "task_recall_explanations_present": False,
        "task_recall_explanations": [],
        "task_recall_ranking_details_present": False,
        "task_recall_ranking_details": [],
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


def test_build_memory_get_context_tool_handler_serializes_canonical_summary_first_payload() -> None:
    workflow_id = uuid4()
    episode_id = uuid4()
    memory_summary_id = uuid4()
    member_memory_id = uuid4()
    created_at = datetime(2024, 10, 12, 4, 5, 6, tzinfo=UTC)

    service = FakeMemoryService(
        context_result=GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            timestamp=created_at,
            episodes=(),
            details={
                "episodes_returned": 0,
                "summary_selection_applied": True,
                "summary_selection_kind": "memory_summary_first",
                "retrieval_routes_present": ["summary_first"],
                "primary_retrieval_routes_present": ["summary_first"],
                "memory_context_groups": [
                    {
                        "scope": "summary",
                        "scope_id": None,
                        "group_id": "summary:memory_summary_first",
                        "parent_scope": "workflow_instance",
                        "parent_scope_id": str(workflow_id),
                        "selection_kind": "memory_summary_first",
                        "selection_route": "summary_first",
                        "child_episode_ids": [str(episode_id)],
                        "child_episode_count": 1,
                        "child_episode_ordering": "returned_episode_order",
                        "child_episode_groups_emitted": True,
                        "child_episode_groups_emission_reason": "memory_items_enabled",
                        "summaries": [
                            {
                                "memory_summary_id": str(memory_summary_id),
                                "episode_id": str(episode_id),
                                "workflow_instance_id": str(workflow_id),
                                "summary_text": "Canonical summary selected first",
                                "summary_kind": "episode_summary",
                                "metadata": {"kind": "canonical"},
                                "member_memory_count": 1,
                                "member_memory_ids": [str(member_memory_id)],
                                "member_memory_items": [
                                    {
                                        "memory_id": str(member_memory_id),
                                        "workspace_id": str(workflow_id),
                                        "episode_id": str(episode_id),
                                        "type": "episode_note",
                                        "provenance": "episode",
                                        "content": "Expanded member memory item",
                                        "metadata": {"kind": "member"},
                                        "created_at": created_at.isoformat(),
                                        "updated_at": created_at.isoformat(),
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "summaries": [
                    {
                        "memory_summary_id": str(memory_summary_id),
                        "episode_id": str(episode_id),
                        "workflow_instance_id": str(workflow_id),
                        "summary_text": "Canonical summary selected first",
                        "summary_kind": "episode_summary",
                        "metadata": {"kind": "canonical"},
                        "member_memory_count": 1,
                        "member_memory_ids": [str(member_memory_id)],
                        "member_memory_items": [
                            {
                                "memory_id": str(member_memory_id),
                                "workspace_id": str(workflow_id),
                                "episode_id": str(episode_id),
                                "type": "episode_note",
                                "provenance": "episode",
                                "content": "Expanded member memory item",
                                "metadata": {"kind": "member"},
                                "created_at": created_at.isoformat(),
                                "updated_at": created_at.isoformat(),
                            }
                        ],
                    }
                ],
            },
        )
    )
    handler = build_memory_get_context_tool_handler(service)

    response = handler(
        {
            "workflow_instance_id": str(workflow_id),
            "limit": 10,
            "include_episodes": True,
            "include_memory_items": True,
            "include_summaries": True,
        }
    )

    assert response.payload["ok"] is True
    result = response.payload["result"]
    assert result["feature"] == "memory_get_context"
    assert result["implemented"] is True
    assert result["status"] == "ok"
    assert result["available_in_version"] == "0.2.0"
    assert result["details"]["summary_selection_applied"] is True
    assert result["details"]["summary_selection_kind"] == "memory_summary_first"
    assert result["details"]["retrieval_routes_present"] == ["summary_first"]
    assert result["details"]["primary_retrieval_routes_present"] == ["summary_first"]
    assert result["details"]["summaries"] == [
        {
            "memory_summary_id": str(memory_summary_id),
            "episode_id": str(episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": "Canonical summary selected first",
            "summary_kind": "episode_summary",
            "metadata": {"kind": "canonical"},
            "member_memory_count": 1,
            "member_memory_ids": [str(member_memory_id)],
            "member_memory_items": [
                {
                    "memory_id": str(member_memory_id),
                    "workspace_id": str(workflow_id),
                    "episode_id": str(episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Expanded member memory item",
                    "metadata": {"kind": "member"},
                    "created_at": created_at.isoformat(),
                    "updated_at": created_at.isoformat(),
                }
            ],
        }
    ]
    assert result["details"]["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:memory_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "memory_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "memory_summary_id": str(memory_summary_id),
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "summary_text": "Canonical summary selected first",
                    "summary_kind": "episode_summary",
                    "metadata": {"kind": "canonical"},
                    "member_memory_count": 1,
                    "member_memory_ids": [str(member_memory_id)],
                    "member_memory_items": [
                        {
                            "memory_id": str(member_memory_id),
                            "workspace_id": str(workflow_id),
                            "episode_id": str(episode_id),
                            "type": "episode_note",
                            "provenance": "episode",
                            "content": "Expanded member memory item",
                            "metadata": {"kind": "member"},
                            "created_at": created_at.isoformat(),
                            "updated_at": created_at.isoformat(),
                        }
                    ],
                }
            ],
        }
    ]

    assert service.context_calls is not None
    call = service.context_calls[0]
    assert call.workflow_instance_id == str(workflow_id)
    assert call.limit == 10
    assert call.include_episodes is True
    assert call.include_memory_items is True
    assert call.include_summaries is True


def test_build_memory_get_context_tool_handler_serializes_summary_only_primary_contract_details() -> (
    None
):
    workflow_id = uuid4()
    episode_id = uuid4()
    created_at = datetime(2024, 10, 13, 4, 5, 6, tzinfo=UTC)

    service = FakeMemoryService(
        context_result=GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            timestamp=created_at,
            episodes=(),
            details={
                "episodes_returned": 1,
                "summary_selection_applied": True,
                "summary_selection_kind": "episode_summary_first",
                "summary_first_has_episode_groups": False,
                "summary_first_is_summary_only": True,
                "summary_first_child_episode_count": 1,
                "summary_first_child_episode_ids": [str(episode_id)],
                "primary_episode_groups_present_after_query_filter": False,
                "auxiliary_only_after_query_filter": False,
                "retrieval_routes_present": ["summary_first"],
                "primary_retrieval_routes_present": ["summary_first"],
                "auxiliary_retrieval_routes_present": [],
                "memory_context_groups": [
                    {
                        "scope": "summary",
                        "scope_id": None,
                        "group_id": "summary:episode_summary_first",
                        "parent_scope": "workflow_instance",
                        "parent_scope_id": str(workflow_id),
                        "selection_kind": "episode_summary_first",
                        "selection_route": "summary_first",
                        "child_episode_ids": [str(episode_id)],
                        "child_episode_count": 1,
                        "child_episode_ordering": "returned_episode_order",
                        "child_episode_groups_emitted": False,
                        "child_episode_groups_emission_reason": "memory_items_disabled",
                        "summaries": [
                            {
                                "episode_id": str(episode_id),
                                "workflow_instance_id": str(workflow_id),
                                "memory_item_count": 1,
                                "memory_item_types": ["episode_note"],
                                "memory_item_provenance": ["episode"],
                            }
                        ],
                    }
                ],
            },
        )
    )
    handler = build_memory_get_context_tool_handler(service)

    response = handler(
        {
            "workflow_instance_id": str(workflow_id),
            "query": "summary-only primary path",
            "limit": 10,
            "include_episodes": True,
            "include_memory_items": False,
            "include_summaries": True,
        }
    )

    assert response.payload["ok"] is True
    result = response.payload["result"]
    assert result["details"]["summary_selection_applied"] is True
    assert result["details"]["summary_selection_kind"] == "episode_summary_first"
    assert result["details"]["summary_first_has_episode_groups"] is False
    assert result["details"]["summary_first_is_summary_only"] is True
    assert result["details"]["summary_first_child_episode_count"] == 1
    assert result["details"]["summary_first_child_episode_ids"] == [str(episode_id)]
    assert result["details"]["primary_episode_groups_present_after_query_filter"] is False
    assert result["details"]["auxiliary_only_after_query_filter"] is False
    assert result["details"]["retrieval_routes_present"] == ["summary_first"]
    assert result["details"]["primary_retrieval_routes_present"] == ["summary_first"]
    assert result["details"]["auxiliary_retrieval_routes_present"] == []
    assert result["details"]["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        }
    ]

    assert service.context_calls is not None
    call = service.context_calls[0]
    assert call.workflow_instance_id == str(workflow_id)
    assert call.query == "summary-only primary path"
    assert call.limit == 10
    assert call.include_episodes is True
    assert call.include_memory_items is False
    assert call.include_summaries is True


def test_build_memory_get_context_tool_handler_serializes_episode_less_narrow_contract_without_summary_first_details() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = str(uuid4())
    inherited_memory_id = uuid4()
    created_at = datetime(2024, 10, 14, 4, 5, 6, tzinfo=UTC)

    service = FakeMemoryService(
        context_result=GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            timestamp=created_at,
            episodes=(),
            details={
                "episodes_returned": 0,
                "summary_selection_applied": False,
                "summary_selection_kind": None,
                "retrieval_routes_present": ["workspace_inherited_auxiliary"],
                "primary_retrieval_routes_present": [],
                "auxiliary_retrieval_routes_present": ["workspace_inherited_auxiliary"],
                "memory_context_groups": [
                    {
                        "scope": "workspace",
                        "scope_id": workspace_id,
                        "parent_scope": None,
                        "parent_scope_id": None,
                        "selection_kind": "inherited_workspace",
                        "selection_route": "workspace_inherited_auxiliary",
                        "memory_items": [
                            {
                                "memory_id": str(inherited_memory_id),
                                "workspace_id": workspace_id,
                                "episode_id": None,
                                "type": "workspace_note",
                                "provenance": "workspace",
                                "content": "Inherited workspace item still visible with include_episodes false",
                                "metadata": {"kind": "workspace-item"},
                                "created_at": created_at.isoformat(),
                                "updated_at": created_at.isoformat(),
                            }
                        ],
                    }
                ],
            },
        )
    )
    handler = build_memory_get_context_tool_handler(service)

    response = handler(
        {
            "workflow_instance_id": str(workflow_id),
            "query": "hidden shaping",
            "limit": 10,
            "include_episodes": False,
            "include_memory_items": True,
            "include_summaries": True,
        }
    )

    assert response.payload["ok"] is True
    result = response.payload["result"]
    assert result["details"]["summary_selection_applied"] is False
    assert result["details"]["summary_selection_kind"] is None
    assert result["details"]["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert result["details"]["primary_retrieval_routes_present"] == []
    assert result["details"]["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert result["details"]["memory_context_groups"] == [
        {
            "scope": "workspace",
            "scope_id": workspace_id,
            "parent_scope": None,
            "parent_scope_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(inherited_memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Inherited workspace item still visible with include_episodes false",
                    "metadata": {"kind": "workspace-item"},
                    "created_at": created_at.isoformat(),
                    "updated_at": created_at.isoformat(),
                }
            ],
        }
    ]

    assert "summary_first_has_episode_groups" not in result["details"]
    assert "summary_first_is_summary_only" not in result["details"]
    assert "summary_first_child_episode_count" not in result["details"]
    assert "summary_first_child_episode_ids" not in result["details"]
    assert "primary_episode_groups_present_after_query_filter" not in result["details"]
    assert "auxiliary_only_after_query_filter" not in result["details"]

    assert service.context_calls is not None
    call = service.context_calls[0]
    assert call.workflow_instance_id == str(workflow_id)
    assert call.query == "hidden shaping"
    assert call.limit == 10
    assert call.include_episodes is False
    assert call.include_memory_items is True
    assert call.include_summaries is True
