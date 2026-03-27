from __future__ import annotations

from typing import Any
from uuid import UUID

from ..runtime.age_explainability import build_age_summary_graph_mirroring_details
from .helpers import metadata_query_strings, text_matches_query
from .types import (
    EpisodeRecord,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)


class ContextShapingMixin:
    """Context-shaping helper methods for ``MemoryService``.

    This mixin extracts response-shaping helpers used by ``get_context`` without
    changing the existing ``MemoryService`` state contract.

    The consuming class is expected to provide:

    - ``self._memory_item_repository``
    - ``self._memory_summary_repository``
    - ``self._memory_summary_membership_repository``
    - ``self._collect_supports_related_memory_items``
    - ``self._serialize_memory_item``
    """

    def _build_episode_explanations(
        self,
        *,
        episodes: tuple[EpisodeRecord, ...],
        normalized_query: str | None,
        query_tokens: tuple[str, ...],
    ) -> tuple[dict[str, Any], ...]:
        explanations: list[dict[str, Any]] = []

        for episode in episodes:
            summary_match = False
            metadata_matches: list[str] = []

            if normalized_query is None:
                explanation_basis = "unfiltered_episode_context"
            else:
                summary_match = text_matches_query(
                    text=episode.summary,
                    normalized_query=normalized_query,
                    query_tokens_value=query_tokens,
                )
                metadata_matches = [
                    metadata_query_string
                    for metadata_query_string in metadata_query_strings(episode.metadata)
                    if text_matches_query(
                        text=metadata_query_string,
                        normalized_query=normalized_query,
                        query_tokens_value=query_tokens,
                    )
                ]
                explanation_basis = "query_match_evaluation"

            explanations.append(
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(episode.workflow_instance_id),
                    "matched": (
                        True
                        if normalized_query is None
                        else summary_match or bool(metadata_matches)
                    ),
                    "explanation_basis": explanation_basis,
                    "matched_summary": summary_match,
                    "matched_metadata_values": metadata_matches,
                }
            )

        return tuple(explanations)

    def _build_summary_details_for_episodes(
        self,
        *,
        episodes: tuple[EpisodeRecord, ...],
    ) -> tuple[dict[str, Any], ...]:
        if not episodes:
            return ()

        summary_details: list[dict[str, Any]] = []
        summary_lookup_by_episode_id: dict[UUID, tuple[MemorySummaryRecord, ...]] = {}

        for episode in episodes:
            summaries = self._memory_summary_repository.list_by_episode_id(
                episode.episode_id,
                limit=100,
            )
            summary_lookup_by_episode_id[episode.episode_id] = summaries

        for episode in episodes:
            summaries = summary_lookup_by_episode_id.get(episode.episode_id, ())
            if not summaries:
                continue

            summary_ids = tuple(summary.memory_summary_id for summary in summaries)
            memberships = self._memory_summary_membership_repository.list_by_summary_ids(
                summary_ids
            )
            memberships_by_summary_id: dict[UUID, list[MemorySummaryMembershipRecord]] = {}
            for membership in memberships:
                memberships_by_summary_id.setdefault(membership.memory_summary_id, []).append(
                    membership
                )

            for summary in summaries:
                summary_memberships = tuple(
                    memberships_by_summary_id.get(summary.memory_summary_id, [])
                )
                member_memory_ids = tuple(
                    membership.memory_id for membership in summary_memberships
                )
                member_memory_items = self._memory_item_repository.list_by_memory_ids(
                    member_memory_ids,
                    limit=100,
                )

                summary_details.append(
                    {
                        "memory_summary_id": str(summary.memory_summary_id),
                        "episode_id": str(episode.episode_id),
                        "workflow_instance_id": str(episode.workflow_instance_id),
                        "summary_text": summary.summary_text,
                        "summary_kind": summary.summary_kind,
                        "metadata": dict(summary.metadata),
                        "member_memory_count": len(member_memory_items),
                        "member_memory_ids": [
                            str(memory_item.memory_id) for memory_item in member_memory_items
                        ],
                        "member_memory_items": [
                            self._serialize_memory_item(memory_item)
                            for memory_item in member_memory_items
                        ],
                    }
                )

        return tuple(summary_details)

    def _build_memory_item_details_for_episodes(
        self,
        *,
        episodes: tuple[EpisodeRecord, ...],
        include_memory_items: bool,
        include_summaries: bool,
    ) -> tuple[dict[str, Any], ...]:
        details: list[dict[str, Any]] = []
        memory_items_by_episode_id: dict[UUID, tuple[MemoryItemRecord, ...]] = {}

        episode_ids = tuple(episode.episode_id for episode in episodes)
        bulk_memory_items = self._memory_item_repository.list_by_episode_ids(episode_ids)
        for episode in episodes:
            episode_memory_items = tuple(
                memory_item
                for memory_item in bulk_memory_items
                if memory_item.episode_id == episode.episode_id
            )
            memory_items_by_episode_id[episode.episode_id] = episode_memory_items

        for episode in episodes:
            memory_items = memory_items_by_episode_id.get(episode.episode_id, ())
            memory_item_count = len(memory_items)
            detail: dict[str, Any] = {
                "episode_id": str(episode.episode_id),
                "memory_item_count": memory_item_count,
            }

            if include_memory_items:
                detail["memory_items"] = [
                    self._serialize_memory_item(memory_item) for memory_item in memory_items
                ]
                detail["remember_path_memory_items"] = [
                    {
                        "memory_id": str(memory_item.memory_id),
                        "memory_type": memory_item.type,
                        "provenance": memory_item.provenance,
                        "provenance_kind": (
                            "interaction"
                            if memory_item.provenance == "interaction"
                            else "workflow_memory"
                            if memory_item.provenance
                            in {
                                "workflow_checkpoint_auto",
                                "workflow_complete_auto",
                            }
                            else "episode_memory"
                            if memory_item.provenance == "episode"
                            else "other"
                        ),
                        "interaction_role": memory_item.metadata.get("interaction_role"),
                        "interaction_kind": memory_item.metadata.get("interaction_kind"),
                        "file_name": memory_item.metadata.get("file_name"),
                        "file_path": memory_item.metadata.get("file_path"),
                        "file_operation": memory_item.metadata.get("file_operation"),
                        "purpose": memory_item.metadata.get("purpose"),
                        "memory_origin": memory_item.metadata.get("memory_origin"),
                        "promotion_field": memory_item.metadata.get("promotion_field"),
                        "promotion_source": memory_item.metadata.get("promotion_source"),
                        "checkpoint_id": memory_item.metadata.get("checkpoint_id"),
                        "step_name": memory_item.metadata.get("step_name"),
                        "workflow_status": memory_item.metadata.get("workflow_status"),
                        "attempt_status": memory_item.metadata.get("attempt_status"),
                    }
                    for memory_item in memory_items
                ]
                remember_path_origin_counts: dict[str, int] = {}
                remember_path_promotion_field_counts: dict[str, int] = {}
                for memory_item in memory_items:
                    memory_origin = memory_item.metadata.get("memory_origin")
                    if isinstance(memory_origin, str) and memory_origin.strip():
                        remember_path_origin_counts[memory_origin] = (
                            remember_path_origin_counts.get(memory_origin, 0) + 1
                        )

                    promotion_field = memory_item.metadata.get("promotion_field")
                    if isinstance(promotion_field, str) and promotion_field.strip():
                        remember_path_promotion_field_counts[promotion_field] = (
                            remember_path_promotion_field_counts.get(promotion_field, 0) + 1
                        )

                detail["remember_path_memory_summary"] = {
                    "memory_origin_counts": remember_path_origin_counts,
                    "promotion_field_counts": remember_path_promotion_field_counts,
                    "checkpoint_origin_present": bool(
                        remember_path_origin_counts.get("workflow_checkpoint_auto", 0)
                    ),
                    "completion_origin_present": bool(
                        remember_path_origin_counts.get("workflow_complete_auto", 0)
                    ),
                }

                related_memory_items, related_memory_relations = (
                    self._collect_supports_related_memory_items(
                        memory_item_details=(detail,),
                        limit=100,
                        include_relation_metadata=True,
                    )
                )
                detail["related_memory_items"] = [
                    self._serialize_memory_item(memory_item) for memory_item in related_memory_items
                ]
                detail["related_memory_item_provenance"] = [
                    {
                        "memory_id": str(memory_item.memory_id),
                        "relation_type": relation.relation_type,
                        "source_memory_id": str(relation.source_memory_id),
                        "target_memory_id": str(relation.target_memory_id),
                        "source_group_scope": "episode",
                        "target_group_scope": (
                            "episode" if memory_item.episode_id is not None else "workspace"
                        ),
                        "target_group_selection_kind": "supports_related_auxiliary",
                        "target_provenance": memory_item.provenance,
                        "target_provenance_kind": (
                            "interaction"
                            if memory_item.provenance == "interaction"
                            else "workflow_memory"
                            if memory_item.provenance
                            in {
                                "workflow_checkpoint_auto",
                                "workflow_complete_auto",
                            }
                            else "episode_memory"
                            if memory_item.provenance == "episode"
                            else "other"
                        ),
                        "target_interaction_role": memory_item.metadata.get("interaction_role"),
                        "target_interaction_kind": memory_item.metadata.get("interaction_kind"),
                        "target_file_name": memory_item.metadata.get("file_name"),
                        "target_file_path": memory_item.metadata.get("file_path"),
                        "target_file_operation": memory_item.metadata.get("file_operation"),
                        "target_purpose": memory_item.metadata.get("purpose"),
                        "source_memory_origin": relation.metadata.get("memory_origin"),
                        "relation_reason": relation.metadata.get("relation_reason"),
                        "source_memory_type": relation.metadata.get("source_memory_type"),
                        "target_memory_type": relation.metadata.get("target_memory_type"),
                    }
                    for memory_item, relation in zip(
                        related_memory_items,
                        related_memory_relations,
                        strict=False,
                    )
                ]
                detail["related_memory_relation_edges"] = [
                    {
                        "memory_relation_id": str(relation.memory_relation_id),
                        "relation_type": relation.relation_type,
                        "source_memory_id": str(relation.source_memory_id),
                        "target_memory_id": str(relation.target_memory_id),
                        "metadata": dict(relation.metadata),
                        "created_at": relation.created_at.isoformat(),
                    }
                    for relation in related_memory_relations
                ]
                detail["remember_path_relation_explanations"] = [
                    {
                        "memory_relation_id": str(relation.memory_relation_id),
                        "relation_type": relation.relation_type,
                        "relation_reason": relation.metadata.get("relation_reason"),
                        "relation_description": relation.metadata.get("relation_description"),
                        "memory_origin": relation.metadata.get("memory_origin"),
                        "source_memory_type": relation.metadata.get("source_memory_type"),
                        "target_memory_type": relation.metadata.get("target_memory_type"),
                        "source_memory_id": str(relation.source_memory_id),
                        "target_memory_id": str(relation.target_memory_id),
                    }
                    for relation in related_memory_relations
                ]
                detail["remember_path_relation_summary"] = {
                    "relation_reason_counts": {
                        relation_reason: sum(
                            1
                            for relation in related_memory_relations
                            if relation.metadata.get("relation_reason") == relation_reason
                        )
                        for relation_reason in sorted(
                            {
                                str(relation.metadata.get("relation_reason"))
                                for relation in related_memory_relations
                                if isinstance(relation.metadata.get("relation_reason"), str)
                                and str(relation.metadata.get("relation_reason")).strip()
                            }
                        )
                    },
                    "checkpoint_origin_present": any(
                        relation.metadata.get("memory_origin") == "workflow_checkpoint_auto"
                        for relation in related_memory_relations
                    ),
                    "completion_origin_present": any(
                        relation.metadata.get("memory_origin") == "workflow_complete_auto"
                        for relation in related_memory_relations
                    ),
                }

            remember_path_relation_reasons = (
                sorted(
                    {
                        str(relation.metadata.get("relation_reason"))
                        for relation in related_memory_relations
                        if isinstance(relation.metadata.get("relation_reason"), str)
                        and str(relation.metadata.get("relation_reason")).strip()
                    }
                )
                if include_memory_items
                else []
            )
            remember_path_summary_explainability = (
                {
                    "memory_origins": sorted(
                        {
                            str(memory_item.metadata.get("memory_origin"))
                            for memory_item in memory_items
                            if isinstance(memory_item.metadata.get("memory_origin"), str)
                            and str(memory_item.metadata.get("memory_origin")).strip()
                        }
                    ),
                    "promotion_fields": sorted(
                        {
                            str(memory_item.metadata.get("promotion_field"))
                            for memory_item in memory_items
                            if isinstance(memory_item.metadata.get("promotion_field"), str)
                            and str(memory_item.metadata.get("promotion_field")).strip()
                        }
                    ),
                    "promotion_sources": sorted(
                        {
                            str(memory_item.metadata.get("promotion_source"))
                            for memory_item in memory_items
                            if isinstance(memory_item.metadata.get("promotion_source"), str)
                            and str(memory_item.metadata.get("promotion_source")).strip()
                        }
                    ),
                    "relation_reasons": remember_path_relation_reasons,
                    "relation_reason_primary": (
                        remember_path_relation_reasons[0]
                        if remember_path_relation_reasons
                        else None
                    ),
                    "relation_reasons_frontloaded": bool(remember_path_relation_reasons),
                    "relation_reason_count": len(remember_path_relation_reasons),
                    "relation_reason_counts": detail.get(
                        "remember_path_relation_summary",
                        {},
                    ).get("relation_reason_counts", {}),
                    "relation_origins": sorted(
                        {
                            str(relation.metadata.get("memory_origin"))
                            for relation in related_memory_relations
                            if isinstance(relation.metadata.get("memory_origin"), str)
                            and str(relation.metadata.get("memory_origin")).strip()
                        }
                    ),
                }
                if include_memory_items
                else {}
            )

            if include_summaries:
                detail["summary"] = {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(episode.workflow_instance_id),
                    "memory_item_count": memory_item_count,
                    "memory_item_types": [memory_item.type for memory_item in memory_items],
                    "memory_item_provenance": [
                        memory_item.provenance for memory_item in memory_items
                    ],
                    "memory_item_provenance_counts": {
                        provenance: sum(
                            1
                            for memory_item in memory_items
                            if memory_item.provenance == provenance
                        )
                        for provenance in sorted(
                            {memory_item.provenance for memory_item in memory_items}
                        )
                    },
                    "interaction_memory_count": sum(
                        1 for memory_item in memory_items if memory_item.provenance == "interaction"
                    ),
                    "interaction_memory_present": any(
                        memory_item.provenance == "interaction" for memory_item in memory_items
                    ),
                    "interaction_roles_present": sorted(
                        {
                            str(memory_item.metadata.get("interaction_role"))
                            for memory_item in memory_items
                            if memory_item.provenance == "interaction"
                            and isinstance(memory_item.metadata.get("interaction_role"), str)
                            and str(memory_item.metadata.get("interaction_role")).strip()
                        }
                    ),
                    "interaction_kinds_present": sorted(
                        {
                            str(memory_item.metadata.get("interaction_kind"))
                            for memory_item in memory_items
                            if memory_item.provenance == "interaction"
                            and isinstance(memory_item.metadata.get("interaction_kind"), str)
                            and str(memory_item.metadata.get("interaction_kind")).strip()
                        }
                    ),
                    "remember_path_explainability": remember_path_summary_explainability,
                }

            details.append(detail)

        return tuple(details)

    def _build_summary_selection_details(
        self,
        memory_item_details: tuple[dict[str, Any], ...],
        summary_details: tuple[dict[str, Any], ...] = (),
    ) -> tuple[tuple[dict[str, Any], ...], bool, str | None]:
        if summary_details:
            summaries = summary_details
            summary_selection_kind = "memory_summary_first"
        else:
            summaries = tuple(
                detail["summary"]
                for detail in memory_item_details
                if isinstance(detail.get("summary"), dict)
            )
            summary_selection_kind = "episode_summary_first" if summaries else None

        summary_selection_applied = bool(summaries)
        return summaries, summary_selection_applied, summary_selection_kind

    def _build_retrieval_route_details(
        self,
        *,
        memory_item_details: tuple[dict[str, Any], ...],
        summaries: tuple[dict[str, Any], ...],
        summary_selection_applied: bool,
        matched_episode_count: int,
        include_memory_items: bool,
        inherited_memory_items: tuple[MemoryItemRecord, ...],
        related_memory_items: tuple[MemoryItemRecord, ...],
        graph_summary_related_memory_items: tuple[MemoryItemRecord, ...],
    ) -> dict[str, Any]:
        episode_direct_group_present = bool(
            include_memory_items and matched_episode_count > 0 and not summary_selection_applied
        )
        graph_summary_group_present = bool(graph_summary_related_memory_items)
        episode_direct_item_count = (
            sum(len(detail.get("memory_items", [])) for detail in memory_item_details)
            if episode_direct_group_present
            else 0
        )
        summary_episode_scope_count = (
            matched_episode_count
            if include_memory_items and matched_episode_count > 0 and summary_selection_applied
            else 0
        )
        summary_episode_scope_item_count = (
            sum(len(detail.get("memory_items", [])) for detail in memory_item_details)
            if include_memory_items and matched_episode_count > 0 and summary_selection_applied
            else 0
        )
        summary_first_has_episode_groups = summary_episode_scope_count > 0
        summary_first_is_summary_only = bool(
            summary_selection_applied and not summary_first_has_episode_groups
        )
        summary_first_child_episode_count = (
            matched_episode_count if summary_selection_applied else 0
        )
        summary_first_child_episode_ids = (
            [detail["episode_id"] for detail in memory_item_details]
            if summary_selection_applied
            else []
        )
        primary_episode_groups_present_after_query_filter = bool(
            episode_direct_group_present or summary_first_has_episode_groups
        )
        auxiliary_only_after_query_filter = bool(
            not primary_episode_groups_present_after_query_filter
            and (
                inherited_memory_items or related_memory_items or graph_summary_related_memory_items
            )
        )
        relation_supports_source_episode_count = len(
            {
                detail["episode_id"]
                for detail in memory_item_details
                if detail.get("related_memory_items") and isinstance(detail.get("episode_id"), str)
            }
        )

        return {
            "retrieval_routes_present": [
                route
                for route in [
                    "summary_first" if summary_selection_applied else None,
                    "episode_direct" if episode_direct_group_present else None,
                    ("workspace_inherited_auxiliary" if inherited_memory_items else None),
                    ("relation_supports_auxiliary" if related_memory_items else None),
                    ("graph_summary_auxiliary" if graph_summary_group_present else None),
                ]
                if route is not None
            ],
            "primary_retrieval_routes_present": [
                route
                for route in [
                    "summary_first" if summary_selection_applied else None,
                    "episode_direct" if episode_direct_group_present else None,
                ]
                if route is not None
            ],
            "auxiliary_retrieval_routes_present": [
                route
                for route in [
                    ("workspace_inherited_auxiliary" if inherited_memory_items else None),
                    ("relation_supports_auxiliary" if related_memory_items else None),
                    ("graph_summary_auxiliary" if graph_summary_group_present else None),
                ]
                if route is not None
            ],
            "retrieval_route_group_counts": {
                "summary_first": 1 if summary_selection_applied else 0,
                "episode_direct": matched_episode_count if episode_direct_group_present else 0,
                "workspace_inherited_auxiliary": 1 if inherited_memory_items else 0,
                "relation_supports_auxiliary": (
                    matched_episode_count if related_memory_items else 0
                ),
                "graph_summary_auxiliary": 1 if graph_summary_group_present else 0,
            },
            "summary_first_has_episode_groups": summary_first_has_episode_groups,
            "summary_first_is_summary_only": summary_first_is_summary_only,
            "summary_first_child_episode_count": summary_first_child_episode_count,
            "summary_first_child_episode_ids": summary_first_child_episode_ids,
            "primary_episode_groups_present_after_query_filter": (
                primary_episode_groups_present_after_query_filter
            ),
            "auxiliary_only_after_query_filter": auxiliary_only_after_query_filter,
            "relation_supports_source_episode_count": (
                relation_supports_source_episode_count if related_memory_items else 0
            ),
            "retrieval_route_item_counts": {
                "summary_first": len(summaries) if summary_selection_applied else 0,
                "episode_direct": episode_direct_item_count,
                "workspace_inherited_auxiliary": (
                    len(inherited_memory_items) if inherited_memory_items else 0
                ),
                "relation_supports_auxiliary": (
                    len(related_memory_items) if related_memory_items else 0
                ),
                "graph_summary_auxiliary": (
                    len(graph_summary_related_memory_items)
                    if graph_summary_related_memory_items
                    else 0
                ),
            },
            "retrieval_route_presence": {
                "summary_first": {
                    "group_present": summary_selection_applied,
                    "item_present": bool(summaries),
                },
                "episode_direct": {
                    "group_present": episode_direct_group_present,
                    "item_present": bool(
                        episode_direct_group_present
                        and any(detail.get("memory_items", []) for detail in memory_item_details)
                    ),
                },
                "workspace_inherited_auxiliary": {
                    "group_present": bool(inherited_memory_items),
                    "item_present": bool(inherited_memory_items),
                },
                "relation_supports_auxiliary": {
                    "group_present": bool(related_memory_items),
                    "item_present": bool(related_memory_items),
                },
                "graph_summary_auxiliary": {
                    "group_present": graph_summary_group_present,
                    "item_present": bool(graph_summary_related_memory_items),
                },
            },
            "retrieval_route_scope_counts": {
                "summary_first": {
                    "summary": (1 if summary_selection_applied else 0),
                    "episode": summary_episode_scope_count,
                    "workspace": 0,
                    "relation": 0,
                },
                "episode_direct": {
                    "summary": 0,
                    "episode": (matched_episode_count if episode_direct_group_present else 0),
                    "workspace": 0,
                    "relation": 0,
                },
                "workspace_inherited_auxiliary": {
                    "summary": 0,
                    "episode": 0,
                    "workspace": (1 if inherited_memory_items else 0),
                    "relation": 0,
                },
                "relation_supports_auxiliary": {
                    "summary": 0,
                    "episode": 0,
                    "workspace": 0,
                    "relation": (1 if related_memory_items else 0),
                },
                "graph_summary_auxiliary": {
                    "summary": 0,
                    "episode": 0,
                    "workspace": 0,
                    "relation": (1 if graph_summary_group_present else 0),
                },
            },
            "retrieval_route_scope_item_counts": {
                "summary_first": {
                    "summary": (len(summaries) if summary_selection_applied else 0),
                    "episode": summary_episode_scope_item_count,
                    "workspace": 0,
                    "relation": 0,
                },
                "episode_direct": {
                    "summary": 0,
                    "episode": episode_direct_item_count,
                    "workspace": 0,
                    "relation": 0,
                },
                "workspace_inherited_auxiliary": {
                    "summary": 0,
                    "episode": 0,
                    "workspace": (len(inherited_memory_items) if inherited_memory_items else 0),
                    "relation": 0,
                },
                "relation_supports_auxiliary": {
                    "summary": 0,
                    "episode": 0,
                    "workspace": 0,
                    "relation": (len(related_memory_items) if related_memory_items else 0),
                },
                "graph_summary_auxiliary": {
                    "summary": 0,
                    "episode": 0,
                    "workspace": 0,
                    "relation": (
                        len(graph_summary_related_memory_items)
                        if graph_summary_related_memory_items
                        else 0
                    ),
                },
            },
            "retrieval_route_scopes_present": {
                "summary_first": [
                    scope
                    for scope in [
                        "summary" if summary_selection_applied else None,
                        "episode" if summary_episode_scope_count > 0 else None,
                    ]
                    if scope is not None
                ],
                "episode_direct": [
                    scope
                    for scope in [
                        "episode" if episode_direct_group_present else None,
                    ]
                    if scope is not None
                ],
                "workspace_inherited_auxiliary": [
                    scope
                    for scope in [
                        ("workspace" if inherited_memory_items else None),
                    ]
                    if scope is not None
                ],
                "relation_supports_auxiliary": [
                    scope
                    for scope in [
                        ("relation" if related_memory_items else None),
                    ]
                    if scope is not None
                ],
                "graph_summary_auxiliary": [
                    scope
                    for scope in [
                        ("relation" if graph_summary_group_present else None),
                    ]
                    if scope is not None
                ],
            },
        }

    def _build_memory_context_groups(
        self,
        *,
        episodes: tuple[EpisodeRecord, ...],
        memory_item_details: tuple[dict[str, Any], ...],
        summaries: tuple[dict[str, Any], ...],
        summary_selection_applied: bool,
        summary_selection_kind: str | None,
        resolved_workflow_ids: tuple[UUID, ...],
        resolved_workflow_instance_id: str | None,
        resolved_workspace_id: str | None,
        inherited_memory_items: tuple[MemoryItemRecord, ...],
        related_memory_items: tuple[MemoryItemRecord, ...],
        graph_summary_related_memory_items: tuple[MemoryItemRecord, ...],
        include_memory_items: bool,
    ) -> list[dict[str, Any]]:
        memory_context_groups: list[dict[str, Any]] = []
        summary_group_id: str | None = None

        if summary_selection_applied:
            summary_parent_scope_id = (
                resolved_workflow_instance_id if len(resolved_workflow_ids) == 1 else None
            )
            summary_group_id = "summary:episode_summary_first"
            memory_context_groups.append(
                {
                    "scope": "summary",
                    "scope_id": None,
                    "group_id": summary_group_id,
                    "parent_scope": "workflow_instance",
                    "parent_scope_id": summary_parent_scope_id,
                    "selection_kind": summary_selection_kind,
                    "selection_route": "summary_first",
                    "child_episode_ids": [detail["episode_id"] for detail in memory_item_details],
                    "child_episode_count": len(memory_item_details),
                    "child_episode_ordering": "returned_episode_order",
                    "child_episode_groups_emitted": bool(
                        include_memory_items and memory_item_details
                    ),
                    "child_episode_groups_emission_reason": (
                        "memory_items_enabled"
                        if include_memory_items and memory_item_details
                        else "memory_items_disabled"
                    ),
                    "summaries": list(summaries),
                    **(
                        {
                            "remember_path_summary_relation_reasons": sorted(
                                {
                                    relation_reason
                                    for summary in summaries
                                    for relation_reason in (
                                        summary.get("remember_path_explainability", {}).get(
                                            "relation_reasons", []
                                        )
                                    )
                                    if isinstance(relation_reason, str) and relation_reason.strip()
                                }
                            ),
                            "remember_path_summary_relation_reason_primary": (
                                sorted(
                                    {
                                        relation_reason
                                        for summary in summaries
                                        for relation_reason in (
                                            summary.get("remember_path_explainability", {}).get(
                                                "relation_reasons", []
                                            )
                                        )
                                        if isinstance(relation_reason, str)
                                        and relation_reason.strip()
                                    }
                                )[0]
                                if any(
                                    summary.get("remember_path_explainability", {}).get(
                                        "relation_reasons",
                                        [],
                                    )
                                    for summary in summaries
                                )
                                else None
                            ),
                            "remember_path_summary_relation_reason_counts": {
                                relation_reason: sum(
                                    summary.get("remember_path_explainability", {})
                                    .get("relation_reason_counts", {})
                                    .get(relation_reason, 0)
                                    for summary in summaries
                                )
                                for relation_reason in sorted(
                                    {
                                        relation_reason
                                        for summary in summaries
                                        for relation_reason in (
                                            summary.get("remember_path_explainability", {}).get(
                                                "relation_reason_counts",
                                                {},
                                            )
                                        ).keys()
                                        if isinstance(relation_reason, str)
                                        and relation_reason.strip()
                                    }
                                )
                            },
                        }
                        if include_memory_items
                        else {}
                    ),
                }
            )

        if include_memory_items:
            for episode, detail in zip(episodes, memory_item_details, strict=False):
                memory_items = detail.get("memory_items", [])
                interaction_memory_items = [
                    memory_item
                    for memory_item in memory_items
                    if isinstance(memory_item, dict)
                    and memory_item.get("provenance") == "interaction"
                ]
                non_interaction_memory_items = [
                    memory_item
                    for memory_item in memory_items
                    if not (
                        isinstance(memory_item, dict)
                        and memory_item.get("provenance") == "interaction"
                    )
                ]
                interaction_roles_present = sorted(
                    {
                        str(memory_item.get("interaction_role"))
                        for memory_item in interaction_memory_items
                        if isinstance(memory_item.get("interaction_role"), str)
                        and str(memory_item.get("interaction_role")).strip()
                    }
                )
                interaction_kinds_present = sorted(
                    {
                        str(memory_item.get("interaction_kind"))
                        for memory_item in interaction_memory_items
                        if isinstance(memory_item.get("interaction_kind"), str)
                        and str(memory_item.get("interaction_kind")).strip()
                    }
                )

                memory_context_groups.append(
                    {
                        "scope": "episode",
                        "scope_id": str(episode.episode_id),
                        "parent_scope": "workflow_instance",
                        "parent_scope_id": str(episode.workflow_instance_id),
                        "parent_group_scope": ("summary" if summary_selection_applied else None),
                        "parent_group_id": (
                            summary_group_id if summary_selection_applied else None
                        ),
                        "selection_kind": "direct_episode",
                        "selection_route": (
                            "summary_first" if summary_selection_applied else "episode_direct"
                        ),
                        "selected_via_summary_first": summary_selection_applied,
                        "memory_items": non_interaction_memory_items,
                        "related_memory_items": detail.get("related_memory_items", []),
                        "related_memory_item_provenance": detail.get(
                            "related_memory_item_provenance", []
                        ),
                        "related_memory_relation_edges": detail.get(
                            "related_memory_relation_edges", []
                        ),
                        "remember_path_memory_items": detail.get(
                            "remember_path_memory_items",
                            [],
                        ),
                        "remember_path_memory_summary": detail.get(
                            "remember_path_memory_summary",
                            {},
                        ),
                        "remember_path_relation_explanations": detail.get(
                            "remember_path_relation_explanations",
                            [],
                        ),
                        "remember_path_relation_summary": detail.get(
                            "remember_path_relation_summary",
                            {},
                        ),
                        "interaction_memory_present": bool(interaction_memory_items),
                        "interaction_memory_count": len(interaction_memory_items),
                    }
                )

                if interaction_memory_items:
                    memory_context_groups.append(
                        {
                            "scope": "interaction",
                            "scope_id": str(episode.episode_id),
                            "parent_scope": "episode",
                            "parent_scope_id": str(episode.episode_id),
                            "parent_group_scope": "workflow_instance",
                            "parent_group_id": str(episode.workflow_instance_id),
                            "selection_kind": "episode_interaction_memory",
                            "selection_route": (
                                "summary_first_interaction"
                                if summary_selection_applied
                                else "episode_interaction_direct"
                            ),
                            "selected_via_summary_first": summary_selection_applied,
                            "memory_items": interaction_memory_items,
                            "interaction_memory_present": True,
                            "interaction_memory_count": len(interaction_memory_items),
                            "interaction_roles_present": interaction_roles_present,
                            "interaction_kinds_present": interaction_kinds_present,
                            "file_work_memory_present": any(
                                isinstance(memory_item.get("file_path"), str)
                                and memory_item.get("file_path", "").strip()
                                for memory_item in interaction_memory_items
                                if isinstance(memory_item, dict)
                            ),
                            "file_work_memory_count": sum(
                                1
                                for memory_item in interaction_memory_items
                                if isinstance(memory_item, dict)
                                and isinstance(memory_item.get("file_path"), str)
                                and memory_item.get("file_path", "").strip()
                            ),
                        }
                    )

            if inherited_memory_items and resolved_workspace_id is not None:
                memory_context_groups.append(
                    {
                        "scope": "workspace",
                        "scope_id": resolved_workspace_id,
                        "parent_scope": None,
                        "parent_scope_id": None,
                        "parent_group_scope": None,
                        "parent_group_id": None,
                        "selection_kind": "inherited_workspace",
                        "selection_route": "workspace_inherited_auxiliary",
                        "memory_items": [
                            self._serialize_memory_item(memory_item)
                            for memory_item in inherited_memory_items
                        ],
                    }
                )

        if related_memory_items:
            relation_group_parent_scope = (
                "workflow_instance" if len(resolved_workflow_ids) == 1 else None
            )
            relation_group_parent_scope_id = (
                resolved_workflow_instance_id
                if relation_group_parent_scope == "workflow_instance"
                else None
            )
            memory_context_groups.append(
                {
                    "scope": "relation",
                    "scope_id": "supports",
                    "group_id": "relation:supports_auxiliary",
                    "parent_scope": relation_group_parent_scope,
                    "parent_scope_id": relation_group_parent_scope_id,
                    "parent_group_scope": None,
                    "parent_group_id": None,
                    "selection_kind": "supports_related_auxiliary",
                    "selection_route": "relation_supports_auxiliary",
                    "relation_type": "supports",
                    "source_memory_ids": sorted(
                        {
                            detail["source_memory_id"]
                            for detail in memory_item_details
                            for detail in detail.get("related_memory_item_provenance", [])
                            if detail.get("relation_type") == "supports"
                            and isinstance(detail.get("source_memory_id"), str)
                        }
                    ),
                    "source_episode_ids": sorted(
                        {
                            detail["episode_id"]
                            for detail in memory_item_details
                            if detail.get("related_memory_items")
                            and isinstance(detail.get("episode_id"), str)
                        }
                    ),
                    "memory_items": [
                        self._serialize_memory_item(memory_item)
                        for memory_item in related_memory_items
                    ],
                    "remember_path_relation_explanations": [
                        relation_explanation
                        for detail in memory_item_details
                        for relation_explanation in detail.get(
                            "remember_path_relation_explanations",
                            [],
                        )
                    ],
                    "remember_path_relation_summary": {
                        **(
                            {
                                "relation_reasons": sorted(
                                    {
                                        relation_reason
                                        for detail in memory_item_details
                                        for relation_reason in detail.get(
                                            "remember_path_relation_summary",
                                            {},
                                        )
                                        .get("relation_reason_counts", {})
                                        .keys()
                                        if isinstance(relation_reason, str)
                                        and relation_reason.strip()
                                    }
                                ),
                                "relation_reason_primary": (
                                    sorted(
                                        {
                                            relation_reason
                                            for detail in memory_item_details
                                            for relation_reason in detail.get(
                                                "remember_path_relation_summary",
                                                {},
                                            )
                                            .get("relation_reason_counts", {})
                                            .keys()
                                            if isinstance(relation_reason, str)
                                            and relation_reason.strip()
                                        }
                                    )[0]
                                ),
                            }
                            if any(
                                detail.get("remember_path_relation_summary", {}).get(
                                    "relation_reason_counts",
                                    {},
                                )
                                for detail in memory_item_details
                            )
                            else {}
                        ),
                        "relation_reason_counts": {
                            relation_reason: sum(
                                detail.get("remember_path_relation_summary", {})
                                .get("relation_reason_counts", {})
                                .get(relation_reason, 0)
                                for detail in memory_item_details
                            )
                            for relation_reason in sorted(
                                {
                                    relation_reason
                                    for detail in memory_item_details
                                    for relation_reason in detail.get(
                                        "remember_path_relation_summary",
                                        {},
                                    )
                                    .get("relation_reason_counts", {})
                                    .keys()
                                    if isinstance(relation_reason, str) and relation_reason.strip()
                                }
                            )
                        },
                        "checkpoint_origin_present": any(
                            detail.get("remember_path_relation_summary", {}).get(
                                "checkpoint_origin_present",
                                False,
                            )
                            for detail in memory_item_details
                        ),
                        "completion_origin_present": any(
                            detail.get("remember_path_relation_summary", {}).get(
                                "completion_origin_present",
                                False,
                            )
                            for detail in memory_item_details
                        ),
                    },
                }
            )

        if graph_summary_related_memory_items:
            relation_group_parent_scope = (
                "workflow_instance" if len(resolved_workflow_ids) == 1 else None
            )
            relation_group_parent_scope_id = (
                resolved_workflow_instance_id
                if relation_group_parent_scope == "workflow_instance"
                else None
            )
            memory_context_groups.append(
                {
                    "scope": "relation",
                    "scope_id": "summarizes",
                    "group_id": "relation:graph_summary_auxiliary",
                    "parent_scope": relation_group_parent_scope,
                    "parent_scope_id": relation_group_parent_scope_id,
                    "parent_group_scope": None,
                    "parent_group_id": None,
                    "selection_kind": "graph_summary_related_auxiliary",
                    "selection_route": "graph_summary_auxiliary",
                    "relation_type": "summarizes",
                    "source_memory_ids": sorted(
                        {
                            str(memory_item.memory_id)
                            for detail in memory_item_details
                            for memory_item in detail.get("memory_items", [])
                            if getattr(memory_item, "memory_id", None) is not None
                        }
                    ),
                    "source_episode_ids": sorted(
                        {
                            detail["episode_id"]
                            for detail in memory_item_details
                            if isinstance(detail.get("episode_id"), str)
                        }
                    ),
                    "memory_items": [
                        self._serialize_memory_item(memory_item)
                        for memory_item in graph_summary_related_memory_items
                    ],
                    "readiness_explainability": {
                        **build_age_summary_graph_mirroring_details(
                            age_enabled=True,
                            graph_status="graph_ready",
                            ready=True,
                        ),
                        "selection_route": "graph_summary_auxiliary",
                        "relation_type": "summarizes",
                        "source_episode_count": len(
                            {
                                detail["episode_id"]
                                for detail in memory_item_details
                                if isinstance(detail.get("episode_id"), str)
                            }
                        ),
                        "source_memory_count": len(
                            {
                                str(memory_item.memory_id)
                                for detail in memory_item_details
                                for memory_item in detail.get("memory_items", [])
                                if getattr(memory_item, "memory_id", None) is not None
                            }
                        ),
                        "derived_memory_count": len(graph_summary_related_memory_items),
                    },
                }
            )

        return memory_context_groups

    def _serialize_memory_item(self, memory_item: MemoryItemRecord) -> dict[str, Any]:
        return {
            "memory_id": str(memory_item.memory_id),
            "workspace_id": (
                str(memory_item.workspace_id) if memory_item.workspace_id is not None else None
            ),
            "episode_id": (
                str(memory_item.episode_id) if memory_item.episode_id is not None else None
            ),
            "type": memory_item.type,
            "provenance": memory_item.provenance,
            "provenance_kind": (
                "interaction"
                if memory_item.provenance == "interaction"
                else "workflow_memory"
                if memory_item.provenance in {"workflow_checkpoint_auto", "workflow_complete_auto"}
                else "episode_memory"
                if memory_item.provenance == "episode"
                else "other"
            ),
            "interaction_role": memory_item.metadata.get("interaction_role"),
            "interaction_kind": memory_item.metadata.get("interaction_kind"),
            "file_name": memory_item.metadata.get("file_name"),
            "file_path": memory_item.metadata.get("file_path"),
            "file_operation": memory_item.metadata.get("file_operation"),
            "purpose": memory_item.metadata.get("purpose"),
            "content": memory_item.content,
            "metadata": dict(memory_item.metadata),
            "created_at": memory_item.created_at.isoformat(),
            "updated_at": memory_item.updated_at.isoformat(),
        }
