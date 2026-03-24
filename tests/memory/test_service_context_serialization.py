from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.memory.service import (
    EpisodeRecord,
    GetContextResponse,
    MemoryFeature,
)
from ctxledger.runtime.serializers import (
    serialize_get_context_response,
)


def test_serialize_get_context_response_serializes_episode_payloads() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 3, 4, 5, 6, 7, tzinfo=UTC)
    response = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_id,
                summary="Recovered context",
                attempt_id=attempt_id,
                metadata={"kind": "root-cause"},
                status="recorded",
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": "root cause",
            "normalized_query": "root cause",
            "lookup_scope": "workflow_instance",
            "workflow_instance_id": str(workflow_id),
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(workflow_id)],
            "query_filter_applied": True,
            "episodes_before_query_filter": 3,
            "matched_episode_count": 1,
            "episodes_returned": 1,
            "episode_explanations": [
                {
                    "episode_id": None,
                    "workflow_instance_id": str(workflow_id),
                    "matched": True,
                    "explanation_basis": "query_match_evaluation",
                    "matched_summary": False,
                    "matched_metadata_values": ["root-cause"],
                }
            ],
        },
    )

    payload = serialize_get_context_response(response)

    assert payload["feature"] == "memory_get_context"
    assert payload["implemented"] is True
    assert payload["message"] == "Episode-oriented memory context retrieved successfully."
    assert payload["status"] == "ok"
    assert payload["available_in_version"] == "0.2.0"
    assert payload["timestamp"] == created_at.isoformat()
    assert payload["details"] == {
        "query": "root cause",
        "normalized_query": "root cause",
        "lookup_scope": "workflow_instance",
        "workflow_instance_id": str(workflow_id),
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": True,
        "episodes_before_query_filter": 3,
        "matched_episode_count": 1,
        "episodes_returned": 1,
        "episode_explanations": [
            {
                "episode_id": None,
                "workflow_instance_id": str(workflow_id),
                "matched": True,
                "explanation_basis": "query_match_evaluation",
                "matched_summary": False,
                "matched_metadata_values": ["root-cause"],
            }
        ],
        "memory_items": [],
        "memory_item_counts_by_episode": {},
        "summaries": [],
    }
    assert payload["details"]["episode_explanations"][0]["matched"] is True
    assert (
        payload["details"]["episode_explanations"][0]["explanation_basis"]
        == "query_match_evaluation"
    )
    assert payload["details"]["episode_explanations"][0]["matched_summary"] is False
    assert payload["details"]["episode_explanations"][0]["matched_metadata_values"] == [
        "root-cause"
    ]
    assert payload["episodes"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary": "Recovered context",
            "attempt_id": str(attempt_id),
            "metadata": {"kind": "root-cause"},
            "status": "recorded",
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]


def test_serialize_get_context_response_preserves_memory_item_and_summary_details() -> None:
    workflow_id = uuid4()
    episode_id = uuid4()
    memory_id = uuid4()
    created_at = datetime(2024, 10, 7, 1, 2, 3, tzinfo=UTC)

    response = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(
            EpisodeRecord(
                episode_id=episode_id,
                workflow_instance_id=workflow_id,
                summary="Serializer detail episode",
                attempt_id=None,
                metadata={"kind": "serializer"},
                status="recorded",
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": None,
            "normalized_query": None,
            "lookup_scope": "workflow_instance",
            "workflow_instance_id": str(workflow_id),
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(workflow_id)],
            "query_filter_applied": False,
            "episodes_before_query_filter": 1,
            "matched_episode_count": 1,
            "episodes_returned": 1,
            "episode_explanations": [],
            "memory_items": [
                [
                    {
                        "memory_id": str(memory_id),
                        "workspace_id": str(workflow_id),
                        "episode_id": str(episode_id),
                        "type": "episode_note",
                        "provenance": "episode",
                        "content": "Serialized memory item",
                        "metadata": {"kind": "note"},
                        "created_at": created_at.isoformat(),
                        "updated_at": created_at.isoformat(),
                    }
                ]
            ],
            "memory_item_counts_by_episode": {
                str(episode_id): 1,
            },
            "summaries": [
                {
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        },
    )

    payload = serialize_get_context_response(response)

    assert payload["details"]["memory_items"] == [
        [
            {
                "memory_id": str(memory_id),
                "workspace_id": str(workflow_id),
                "episode_id": str(episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Serialized memory item",
                "metadata": {"kind": "note"},
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
            }
        ]
    ]
    assert payload["details"]["memory_item_counts_by_episode"] == {
        str(episode_id): 1,
    }
    assert payload["details"]["summaries"] == [
        {
            "episode_id": str(episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        }
    ]


def test_serialize_get_context_response_preserves_canonical_summary_first_details() -> None:
    workflow_id = uuid4()
    episode_id = uuid4()
    memory_summary_id = uuid4()
    member_memory_id = uuid4()
    created_at = datetime(2024, 10, 12, 4, 5, 6, tzinfo=UTC)

    response = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(
            EpisodeRecord(
                episode_id=episode_id,
                workflow_instance_id=workflow_id,
                summary="Canonical summary serializer episode",
                attempt_id=None,
                metadata={"kind": "serializer-summary"},
                status="recorded",
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": None,
            "normalized_query": None,
            "lookup_scope": "workflow_instance",
            "workflow_instance_id": str(workflow_id),
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(workflow_id)],
            "query_filter_applied": False,
            "episodes_before_query_filter": 1,
            "matched_episode_count": 1,
            "episodes_returned": 1,
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
            "memory_items": [],
            "memory_item_counts_by_episode": {},
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

    payload = serialize_get_context_response(response)

    assert payload["details"]["summary_selection_applied"] is True
    assert payload["details"]["summary_selection_kind"] == "memory_summary_first"
    assert payload["details"]["retrieval_routes_present"] == ["summary_first"]
    assert payload["details"]["primary_retrieval_routes_present"] == ["summary_first"]
    assert payload["details"]["summaries"] == [
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
    assert payload["details"]["memory_context_groups"] == [
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
