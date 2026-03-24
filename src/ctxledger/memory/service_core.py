"""Core orchestration module for the memory subsystem.

This module holds the high-level ``MemoryService`` orchestration logic while
keeping request/response shapes, protocol contracts, helper functions, and
repository implementations in their dedicated modules.

The goal of this split is structural only: preserve existing behavior and keep
the compatibility import surface in ``ctxledger.memory.service`` free to
re-export ``MemoryService`` during the transition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from . import service as service_module
from .embeddings import (
    EmbeddingGenerationError,
    EmbeddingGenerator,
    EmbeddingRequest,
)
from .helpers import (
    embedding_dot_product,
    metadata_query_strings,
    normalize_query_text,
    query_tokens,
    text_matches_query,
)
from .protocols import (
    EpisodeRepository,
    MemoryEmbeddingRepository,
    MemoryItemRepository,
    MemoryRelationMemoryItemLookupRepository,
    MemoryRelationRepository,
    MemoryRelationSupportsTargetLookupRepository,
    MemorySummaryMembershipRepository,
    MemorySummaryRepository,
    WorkflowLookupRepository,
    WorkspaceLookupRepository,
)
from .repositories import (
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from .types import (
    EpisodeRecord,
    GetContextResponse,
    GetMemoryContextRequest,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)

__all__ = [
    "EpisodeRecord",
    "GetContextResponse",
    "GetMemoryContextRequest",
    "InMemoryEpisodeRepository",
    "InMemoryMemoryEmbeddingRepository",
    "InMemoryMemoryItemRepository",
    "InMemoryMemoryRelationRepository",
    "InMemoryWorkflowLookupRepository",
    "MemoryEmbeddingRecord",
    "MemoryErrorCode",
    "MemoryFeature",
    "MemoryItemRecord",
    "MemoryRelationRecord",
    "MemoryService",
    "MemoryServiceError",
    "RememberEpisodeRequest",
    "RememberEpisodeResponse",
    "SearchMemoryRequest",
    "SearchMemoryResponse",
    "SearchResultRecord",
    "StubResponse",
    "UnitOfWorkEpisodeRepository",
    "UnitOfWorkMemoryEmbeddingRepository",
    "UnitOfWorkMemoryItemRepository",
    "UnitOfWorkWorkflowLookupRepository",
    "UnitOfWorkWorkspaceLookupRepository",
    "WorkflowLookupRepository",
    "WorkspaceLookupRepository",
    "EpisodeRepository",
    "MemoryEmbeddingRepository",
    "MemoryItemRepository",
    "MemoryRelationMemoryItemLookupRepository",
    "MemoryRelationRepository",
]


class MemoryService:
    """Memory subsystem service.

    Episodic persistence is implemented as append-only episode creation.
    Retrieval-oriented operations remain stubbed until later stages.
    """

    def __init__(
        self,
        *,
        episode_repository: EpisodeRepository | None = None,
        memory_item_repository: MemoryItemRepository | None = None,
        memory_summary_repository: MemorySummaryRepository | None = None,
        memory_summary_membership_repository: MemorySummaryMembershipRepository | None = None,
        memory_embedding_repository: MemoryEmbeddingRepository | None = None,
        memory_relation_repository: MemoryRelationRepository | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        workflow_lookup: WorkflowLookupRepository | None = None,
        workspace_lookup: WorkspaceLookupRepository | None = None,
    ) -> None:
        self._episode_repository = episode_repository or InMemoryEpisodeRepository()
        self._memory_item_repository = memory_item_repository or InMemoryMemoryItemRepository()
        self._memory_summary_repository = (
            memory_summary_repository or InMemoryMemorySummaryRepository()
        )
        self._memory_summary_membership_repository = (
            memory_summary_membership_repository or InMemoryMemorySummaryMembershipRepository()
        )
        self._memory_embedding_repository = memory_embedding_repository
        self._memory_relation_repository = (
            memory_relation_repository or InMemoryMemoryRelationRepository()
        )
        if embedding_generator is None:
            try:
                embedding_generator = service_module.build_embedding_generator(
                    service_module.get_settings().embedding
                )
            except Exception:
                embedding_generator = None
        self._embedding_generator = embedding_generator
        self._workflow_lookup = workflow_lookup
        self._workspace_lookup = workspace_lookup

    def remember_episode(self, request: RememberEpisodeRequest) -> RememberEpisodeResponse:
        """Persist a new episode associated with a workflow."""
        self._require_non_empty(
            request.workflow_instance_id,
            field_name="workflow_instance_id",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        self._require_non_empty(
            request.summary,
            field_name="summary",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )

        workflow_instance_id = self._parse_uuid(
            request.workflow_instance_id,
            field_name="workflow_instance_id",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        attempt_id = (
            self._parse_uuid(
                request.attempt_id,
                field_name="attempt_id",
                feature=MemoryFeature.REMEMBER_EPISODE,
            )
            if request.attempt_id is not None and self._has_text(request.attempt_id)
            else None
        )

        if self._workflow_lookup is not None and not self._workflow_lookup.workflow_exists(
            workflow_instance_id
        ):
            raise MemoryServiceError(
                code=MemoryErrorCode.WORKFLOW_NOT_FOUND,
                feature=MemoryFeature.REMEMBER_EPISODE,
                message="workflow_instance_id was not found.",
                details={"workflow_instance_id": str(workflow_instance_id)},
            )

        episode = self._episode_repository.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_instance_id,
                summary=request.summary.strip(),
                attempt_id=attempt_id,
                metadata=dict(request.metadata),
            )
        )
        memory_item = self._memory_item_repository.create(
            MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=self._resolve_workspace_id(workflow_instance_id),
                episode_id=episode.episode_id,
                type="episode_note",
                provenance="episode",
                content=episode.summary,
                metadata=dict(episode.metadata),
                created_at=episode.created_at,
                updated_at=episode.updated_at,
            )
        )
        embedding_outcome = self._maybe_store_embedding(memory_item)

        return RememberEpisodeResponse(
            feature=MemoryFeature.REMEMBER_EPISODE,
            implemented=True,
            message="Episode recorded successfully.",
            status="recorded",
            available_in_version="0.2.0",
            episode=episode,
            details={
                "workflow_instance_id": str(episode.workflow_instance_id),
                "attempt_id": (str(episode.attempt_id) if episode.attempt_id is not None else None),
                **embedding_outcome,
            },
        )

    def search(self, request: SearchMemoryRequest) -> SearchMemoryResponse:
        """Return hybrid lexical + semantic memory-item search results."""
        self._require_non_empty(
            request.query,
            field_name="query",
            feature=MemoryFeature.SEARCH,
        )
        self._require_positive_limit(
            request.limit,
            feature=MemoryFeature.SEARCH,
        )

        normalized_query = normalize_query_text(request.query)
        assert normalized_query is not None

        workspace_id: UUID | None = None
        if self._has_text(request.workspace_id):
            workspace_id = self._parse_uuid(
                request.workspace_id or "",
                field_name="workspace_id",
                feature=MemoryFeature.SEARCH,
            )

        memory_items: tuple[MemoryItemRecord, ...] = ()
        if workspace_id is not None:
            memory_items = self._memory_item_repository.list_by_workspace_id(
                workspace_id,
                limit=request.limit,
            )

        semantic_matches: tuple[MemoryEmbeddingRecord, ...] = ()
        semantic_query_generated = False
        semantic_generation_skipped_reason: str | None = None

        if self._embedding_generator is None or self._memory_embedding_repository is None:
            semantic_generation_skipped_reason = "embedding_search_not_configured"
        else:
            try:
                semantic_query = self._embedding_generator.generate(
                    EmbeddingRequest(text=request.query)
                )
            except EmbeddingGenerationError as exc:
                semantic_generation_skipped_reason = f"embedding_generation_failed:{exc.provider}"
            else:
                semantic_query_generated = True
                semantic_matches = self._memory_embedding_repository.find_similar(
                    semantic_query.vector,
                    limit=request.limit,
                    workspace_id=workspace_id,
                )

        semantic_score_by_memory_id: dict[UUID, float] = {}
        semantic_matched_fields_by_memory_id: dict[UUID, tuple[str, ...]] = {}
        semantic_result_count = len(semantic_matches)

        if semantic_matches:
            semantic_rank_floor = 0.25
            semantic_rank_denominator = max(len(semantic_matches) - 1, 1)
            top_similarity = embedding_dot_product(
                semantic_matches[0].embedding,
                semantic_query.vector,
            )
            bottom_similarity = top_similarity
            if len(semantic_matches) > 1:
                bottom_similarity = embedding_dot_product(
                    semantic_matches[-1].embedding,
                    semantic_query.vector,
                )
            similarity_range = max(top_similarity - bottom_similarity, 0.0)

            for index, embedding_match in enumerate(semantic_matches):
                raw_similarity = embedding_dot_product(
                    embedding_match.embedding,
                    semantic_query.vector,
                )
                rank_component = semantic_rank_floor + (
                    (1.0 - semantic_rank_floor)
                    * (float(semantic_rank_denominator - index) / float(semantic_rank_denominator))
                )
                similarity_component = 1.0
                if similarity_range > 0:
                    normalized_similarity = max(
                        0.0,
                        min(
                            1.0,
                            (raw_similarity - bottom_similarity) / similarity_range,
                        ),
                    )
                    if raw_similarity >= top_similarity:
                        similarity_component = 1.0
                    elif raw_similarity <= bottom_similarity:
                        similarity_component = 0.0
                    else:
                        similarity_component = semantic_rank_floor + (
                            (1.0 - semantic_rank_floor) * normalized_similarity
                        )
                semantic_score = rank_component * similarity_component
                current_best = semantic_score_by_memory_id.get(
                    embedding_match.memory_id,
                    0.0,
                )
                if semantic_score > current_best:
                    semantic_score_by_memory_id[embedding_match.memory_id] = semantic_score
                    semantic_matched_fields_by_memory_id[embedding_match.memory_id] = (
                        "embedding_similarity",
                    )

        scored_results: list[SearchResultRecord] = []
        lexical_weight = 1.0
        semantic_weight = 1.0
        semantic_only_discount = 0.75

        for memory_item in memory_items:
            lexical_score, matched_fields = self._score_memory_item_for_query(
                memory_item=memory_item,
                normalized_query=normalized_query,
            )
            semantic_score = semantic_score_by_memory_id.get(memory_item.memory_id, 0.0)
            semantic_fields = semantic_matched_fields_by_memory_id.get(
                memory_item.memory_id,
                (),
            )

            combined_fields = tuple(dict.fromkeys((*matched_fields, *semantic_fields)))
            lexical_component = lexical_score * lexical_weight
            semantic_component = semantic_score * semantic_weight
            score_mode = "hybrid"

            hybrid_score = lexical_component + semantic_component
            if lexical_score <= 0 and semantic_score > 0:
                hybrid_score = semantic_component * semantic_only_discount
                score_mode = "semantic_only_discounted"
            elif lexical_score > 0 and semantic_score <= 0:
                score_mode = "lexical_only"

            if hybrid_score <= 0:
                continue

            scored_results.append(
                SearchResultRecord(
                    memory_id=memory_item.memory_id,
                    workspace_id=memory_item.workspace_id,
                    episode_id=memory_item.episode_id,
                    workflow_instance_id=None,
                    summary=memory_item.content,
                    attempt_id=None,
                    metadata=dict(memory_item.metadata),
                    score=hybrid_score,
                    matched_fields=combined_fields,
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                    ranking_details={
                        "lexical_component": lexical_component,
                        "semantic_component": semantic_component,
                        "score_mode": score_mode,
                        "semantic_only_discount_applied": (
                            lexical_score <= 0 and semantic_score > 0
                        ),
                    },
                    created_at=memory_item.created_at,
                    updated_at=memory_item.updated_at,
                )
            )

        scored_results.sort(
            key=lambda result: (
                result.score,
                result.semantic_score,
                result.lexical_score,
                result.created_at,
            ),
            reverse=True,
        )
        limited_results = tuple(scored_results[: request.limit])

        search_mode = (
            "hybrid_memory_item_search" if semantic_query_generated else "memory_item_lexical"
        )
        message = (
            "Hybrid lexical and semantic memory search completed successfully."
            if semantic_query_generated
            else "Memory-item-based lexical search completed successfully."
        )

        result_mode_counts = {
            "hybrid": 0,
            "lexical_only": 0,
            "semantic_only_discounted": 0,
        }
        result_composition = {
            "with_lexical_signal": 0,
            "with_semantic_signal": 0,
            "with_both_signals": 0,
        }
        for result in limited_results:
            score_mode = str(result.ranking_details.get("score_mode", "hybrid"))
            if score_mode in result_mode_counts:
                result_mode_counts[score_mode] += 1
            has_lexical_signal = result.lexical_score > 0.0
            has_semantic_signal = result.semantic_score > 0.0
            if has_lexical_signal:
                result_composition["with_lexical_signal"] += 1
            if has_semantic_signal:
                result_composition["with_semantic_signal"] += 1
            if has_lexical_signal and has_semantic_signal:
                result_composition["with_both_signals"] += 1

        details = {
            "query": request.query,
            "normalized_query": normalized_query,
            "workspace_id": request.workspace_id,
            "limit": request.limit,
            "filters": request.filters,
            "search_mode": search_mode,
            "memory_items_considered": len(memory_items),
            "semantic_candidates_considered": semantic_result_count,
            "semantic_query_generated": semantic_query_generated,
            "hybrid_scoring": {
                "lexical_weight": lexical_weight,
                "semantic_weight": semantic_weight,
                "semantic_only_discount": semantic_only_discount,
            },
            "result_mode_counts": result_mode_counts,
            "result_composition": result_composition,
            "results_returned": len(limited_results),
        }
        if semantic_generation_skipped_reason is not None:
            details["semantic_generation_skipped_reason"] = semantic_generation_skipped_reason

        return SearchMemoryResponse(
            feature=MemoryFeature.SEARCH,
            implemented=True,
            message=message,
            status="ok",
            available_in_version="0.4.0",
            results=limited_results,
            details=details,
        )

    def get_context(self, request: GetMemoryContextRequest) -> GetContextResponse:
        """Return episode-oriented auxiliary context.

        This operation remains intentionally separate from workflow resume. It
        returns support context rather than canonical operational state.

        In the current implementation stage, retrieval is episode-oriented and
        keyed primarily by workflow_instance_id.
        """
        if not any(
            [
                self._has_text(request.query),
                self._has_text(request.workspace_id),
                self._has_text(request.workflow_instance_id),
                self._has_text(request.ticket_id),
            ]
        ):
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=MemoryFeature.GET_CONTEXT,
                message=(
                    "At least one of query, workspace_id, workflow_instance_id, "
                    "or ticket_id must be provided."
                ),
                details={},
            )

        self._require_positive_limit(
            request.limit,
            feature=MemoryFeature.GET_CONTEXT,
        )

        lookup_scope = "query"
        resolved_workflow_ids: tuple[UUID, ...] = ()
        resolved_workflow_instance_id: str | None = None
        normalized_query = normalize_query_text(request.query)
        query_token_values = query_tokens(normalized_query)
        workspace_workflow_ids: tuple[UUID, ...] = ()
        ticket_workflow_ids: tuple[UUID, ...] = ()
        resolver_ordered_workflow_ids: tuple[UUID, ...] = ()
        ordering_signals: dict[str, dict[str, str | None]] = {}

        if self._has_text(request.workflow_instance_id):
            lookup_scope = "workflow_instance"
            workflow_instance_id = self._parse_uuid(
                request.workflow_instance_id or "",
                field_name="workflow_instance_id",
                feature=MemoryFeature.GET_CONTEXT,
            )
            if self._workflow_lookup is not None and not self._workflow_lookup.workflow_exists(
                workflow_instance_id
            ):
                raise MemoryServiceError(
                    code=MemoryErrorCode.WORKFLOW_NOT_FOUND,
                    feature=MemoryFeature.GET_CONTEXT,
                    message="workflow_instance_id was not found.",
                    details={"workflow_instance_id": str(workflow_instance_id)},
                )
            resolved_workflow_ids = (workflow_instance_id,)
            resolved_workflow_instance_id = str(workflow_instance_id)
        elif self._workflow_lookup is not None:
            if self._has_text(request.workspace_id):
                workspace_workflow_ids = self._workflow_lookup.workflow_ids_by_workspace_id(
                    request.workspace_id or "",
                    limit=request.limit,
                )

            if self._has_text(request.ticket_id):
                ticket_workflow_ids = self._workflow_lookup.workflow_ids_by_ticket_id(
                    request.ticket_id or "",
                    limit=request.limit,
                )

            if workspace_workflow_ids and ticket_workflow_ids:
                lookup_scope = "workspace_and_ticket"
                ticket_workflow_id_set = set(ticket_workflow_ids)
                resolver_ordered_workflow_ids = tuple(
                    workflow_id
                    for workflow_id in workspace_workflow_ids
                    if workflow_id in ticket_workflow_id_set
                )[: request.limit]
            elif workspace_workflow_ids:
                lookup_scope = "workspace"
                resolver_ordered_workflow_ids = workspace_workflow_ids
            elif ticket_workflow_ids:
                lookup_scope = "ticket"
                resolver_ordered_workflow_ids = ticket_workflow_ids

        signal_ordered_workflow_ids = (
            self._order_workflow_ids_by_freshness_signals(
                workflow_ids=resolver_ordered_workflow_ids,
                limit=request.limit,
            )
            if resolved_workflow_instance_id is None
            else resolved_workflow_ids
        )
        if resolved_workflow_instance_id is None:
            resolved_workflow_ids = signal_ordered_workflow_ids
            ordering_signals = self._workflow_ordering_signals(workflow_ids=resolved_workflow_ids)
        elif resolved_workflow_ids:
            ordering_signals = self._workflow_ordering_signals(workflow_ids=resolved_workflow_ids)

        inherited_workspace_items: tuple[MemoryItemRecord, ...] = ()
        resolved_workspace_id = request.workspace_id
        if (
            self._has_text(resolved_workflow_instance_id)
            and self._workflow_lookup is not None
            and request.include_memory_items
        ):
            raw_workspace_id = self._workflow_lookup.workspace_id_by_workflow_id(
                UUID(resolved_workflow_instance_id or "")
            )
            if raw_workspace_id is not None:
                resolved_workspace_id = str(raw_workspace_id)
                inherited_workspace_items = self._memory_item_repository.list_workspace_root_items(
                    raw_workspace_id,
                    limit=request.limit,
                )

        details = {
            "query": request.query,
            "normalized_query": normalized_query,
            "query_tokens": list(query_token_values),
            "lookup_scope": lookup_scope,
            "workspace_id": resolved_workspace_id,
            "workflow_instance_id": resolved_workflow_instance_id,
            "ticket_id": request.ticket_id,
            "limit": request.limit,
            "include_episodes": request.include_episodes,
            "include_memory_items": request.include_memory_items,
            "include_summaries": request.include_summaries,
            "workflow_candidate_ordering": {
                "ordering_basis": (
                    "workflow_instance_id_priority"
                    if resolved_workflow_instance_id is not None
                    else "workflow_freshness_signals"
                ),
                "workflow_instance_id_priority_applied": (
                    resolved_workflow_instance_id is not None
                ),
                "signal_priority": [
                    "workflow_is_terminal",
                    "latest_attempt_is_terminal",
                    "has_latest_attempt",
                    "has_latest_checkpoint",
                    "latest_checkpoint_created_at",
                    "latest_verify_report_created_at",
                    "latest_episode_created_at",
                    "latest_attempt_started_at",
                    "workflow_updated_at",
                    "resolver_order",
                ],
                "workspace_candidate_ids": [
                    str(workflow_id) for workflow_id in workspace_workflow_ids
                ],
                "ticket_candidate_ids": [str(workflow_id) for workflow_id in ticket_workflow_ids],
                "resolver_candidate_ids": [
                    str(workflow_id) for workflow_id in resolver_ordered_workflow_ids
                ],
                "final_candidate_ids": [str(workflow_id) for workflow_id in resolved_workflow_ids],
                "candidate_signals": ordering_signals,
            },
            "resolved_workflow_count": len(resolved_workflow_ids),
            "resolved_workflow_ids": [str(workflow_id) for workflow_id in resolved_workflow_ids],
        }

        if not request.include_episodes:
            return GetContextResponse(
                feature=MemoryFeature.GET_CONTEXT,
                implemented=True,
                message="Episode-oriented memory context retrieved successfully.",
                status="ok",
                available_in_version="0.2.0",
                episodes=(),
                details={
                    **details,
                    "query_filter_applied": False,
                    "episodes_before_query_filter": 0,
                    "matched_episode_count": 0,
                    "episodes_returned": 0,
                    "episode_explanations": [],
                    "memory_items": [],
                    "memory_item_counts_by_episode": {},
                    "summaries": [],
                    "summary_selection_applied": False,
                    "summary_selection_kind": None,
                    "hierarchy_applied": bool(inherited_workspace_items),
                    "inherited_context_is_auxiliary": bool(inherited_workspace_items),
                    "inherited_context_returned_without_episode_matches": False,
                    "inherited_context_returned_as_auxiliary_without_episode_matches": False,
                    "related_context_is_auxiliary": False,
                    "related_context_relation_types": [],
                    "related_context_returned_without_episode_matches": False,
                    "all_episodes_filtered_out_by_query": False,
                    "flat_related_memory_items_is_compatibility_field": False,
                    "flat_related_memory_items_matches_grouped_episode_related_items": False,
                    "related_memory_items_by_episode_is_primary_structured_output": False,
                    "related_memory_items_by_episode_are_compatibility_output": False,
                    "relation_memory_context_groups_are_primary_output": False,
                    "group_related_memory_items_are_convenience_output": False,
                    "retrieval_routes_present": (
                        ["workspace_inherited_auxiliary"]
                        if inherited_workspace_items and resolved_workspace_id is not None
                        else []
                    ),
                    "primary_retrieval_routes_present": [],
                    "auxiliary_retrieval_routes_present": (
                        ["workspace_inherited_auxiliary"]
                        if inherited_workspace_items and resolved_workspace_id is not None
                        else []
                    ),
                    "retrieval_route_group_counts": {
                        "summary_first": 0,
                        "episode_direct": 0,
                        "workspace_inherited_auxiliary": (
                            1
                            if inherited_workspace_items and resolved_workspace_id is not None
                            else 0
                        ),
                        "relation_supports_auxiliary": 0,
                    },
                    "retrieval_route_item_counts": {
                        "summary_first": 0,
                        "episode_direct": 0,
                        "workspace_inherited_auxiliary": len(inherited_workspace_items),
                        "relation_supports_auxiliary": 0,
                    },
                    "retrieval_route_presence": {
                        "summary_first": {
                            "group_present": False,
                            "item_present": False,
                        },
                        "episode_direct": {
                            "group_present": False,
                            "item_present": False,
                        },
                        "workspace_inherited_auxiliary": {
                            "group_present": bool(
                                inherited_workspace_items and resolved_workspace_id is not None
                            ),
                            "item_present": bool(inherited_workspace_items),
                        },
                        "relation_supports_auxiliary": {
                            "group_present": False,
                            "item_present": False,
                        },
                    },
                    "retrieval_route_scope_counts": {
                        "summary_first": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": 0,
                            "relation": 0,
                        },
                        "episode_direct": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": 0,
                            "relation": 0,
                        },
                        "workspace_inherited_auxiliary": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": (
                                1
                                if inherited_workspace_items and resolved_workspace_id is not None
                                else 0
                            ),
                            "relation": 0,
                        },
                        "relation_supports_auxiliary": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": 0,
                            "relation": 0,
                        },
                    },
                    "retrieval_route_scope_item_counts": {
                        "summary_first": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": 0,
                            "relation": 0,
                        },
                        "episode_direct": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": 0,
                            "relation": 0,
                        },
                        "workspace_inherited_auxiliary": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": len(inherited_workspace_items),
                            "relation": 0,
                        },
                        "relation_supports_auxiliary": {
                            "summary": 0,
                            "episode": 0,
                            "workspace": 0,
                            "relation": 0,
                        },
                    },
                    "retrieval_route_scopes_present": {
                        "summary_first": [],
                        "episode_direct": [],
                        "workspace_inherited_auxiliary": (
                            ["workspace"]
                            if inherited_workspace_items and resolved_workspace_id is not None
                            else []
                        ),
                        "relation_supports_auxiliary": [],
                    },
                    "memory_context_groups": (
                        [
                            {
                                "scope": "workspace",
                                "scope_id": resolved_workspace_id,
                                "parent_scope": None,
                                "parent_scope_id": None,
                                "selection_kind": "inherited_workspace",
                                "selection_route": "workspace_inherited_auxiliary",
                                "memory_items": [
                                    self._serialize_memory_item(memory_item)
                                    for memory_item in inherited_workspace_items
                                ],
                            }
                        ]
                        if resolved_workspace_id is not None
                        else []
                    ),
                    "inherited_memory_items": [
                        self._serialize_memory_item(memory_item)
                        for memory_item in inherited_workspace_items
                    ],
                },
            )

        episodes = self._collect_episode_context(
            workflow_ids=resolved_workflow_ids,
            limit=request.limit,
        )
        episodes_before_query_filter = len(episodes)
        episode_explanations_before_query_filter = self._build_episode_explanations(
            episodes=episodes,
            normalized_query=normalized_query,
            query_tokens=query_token_values,
        )
        memory_item_details_before_query_filter = self._build_memory_item_details_for_episodes(
            episodes=episodes,
            include_memory_items=request.include_memory_items,
            include_summaries=request.include_summaries,
        )

        if normalized_query is not None:
            filtered_episodes: list[EpisodeRecord] = []
            filtered_episode_explanations: list[dict[str, Any]] = []
            filtered_memory_item_details: list[dict[str, Any]] = []

            for episode, explanation, memory_item_detail in zip(
                episodes,
                episode_explanations_before_query_filter,
                memory_item_details_before_query_filter,
                strict=False,
            ):
                if bool(explanation["matched"]):
                    filtered_episodes.append(episode)
                    filtered_episode_explanations.append(explanation)
                    filtered_memory_item_details.append(memory_item_detail)

            episodes = tuple(filtered_episodes)
            all_episodes_filtered_out_by_query = (
                bool(episode_explanations_before_query_filter) and not filtered_episode_explanations
            )
            if filtered_episode_explanations:
                episode_explanations = tuple(filtered_episode_explanations)
            else:
                episode_explanations = tuple(
                    {
                        **explanation,
                        "explanation_basis": "query_filtered_out",
                    }
                    for explanation in episode_explanations_before_query_filter
                )
            memory_item_details = tuple(filtered_memory_item_details)
        else:
            all_episodes_filtered_out_by_query = False
            episode_explanations = tuple(episode_explanations_before_query_filter)
            memory_item_details = tuple(memory_item_details_before_query_filter)

        matched_episode_count = len(episodes)
        summary_details = (
            self._build_summary_details_for_episodes(episodes=episodes)
            if request.include_summaries
            else ()
        )
        summaries, summary_selection_applied, summary_selection_kind = (
            self._build_summary_selection_details(
                memory_item_details=memory_item_details,
                summary_details=summary_details,
            )
        )
        inherited_memory_items = inherited_workspace_items

        related_memory_items = self._collect_supports_related_memory_items(
            memory_item_details=memory_item_details,
            limit=request.limit,
        )
        memory_context_groups = self._build_memory_context_groups(
            episodes=episodes,
            memory_item_details=memory_item_details,
            summaries=summaries,
            summary_selection_applied=summary_selection_applied,
            summary_selection_kind=summary_selection_kind,
            resolved_workflow_ids=resolved_workflow_ids,
            resolved_workflow_instance_id=resolved_workflow_instance_id,
            resolved_workspace_id=resolved_workspace_id,
            inherited_memory_items=inherited_memory_items,
            related_memory_items=related_memory_items,
            include_memory_items=request.include_memory_items,
        )

        return GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            episodes=episodes,
            details={
                **details,
                "query_filter_applied": normalized_query is not None,
                "episodes_before_query_filter": episodes_before_query_filter,
                "matched_episode_count": matched_episode_count,
                "episodes_returned": len(episodes),
                "episode_explanations": list(episode_explanations),
                "memory_items": [
                    detail["memory_items"]
                    for detail in memory_item_details
                    if isinstance(detail.get("memory_items"), list)
                ],
                "related_memory_items_by_episode": {
                    detail["episode_id"]: detail.get("related_memory_items", [])
                    for detail in memory_item_details
                    if isinstance(detail.get("related_memory_items"), list)
                },
                "memory_item_counts_by_episode": {
                    detail["episode_id"]: detail["memory_item_count"]
                    for detail in memory_item_details
                },
                "summaries": list(summaries),
                "summary_selection_applied": summary_selection_applied,
                "summary_selection_kind": summary_selection_kind,
                "hierarchy_applied": bool(inherited_memory_items),
                "inherited_context_is_auxiliary": bool(inherited_memory_items),
                "inherited_context_returned_without_episode_matches": bool(
                    inherited_memory_items and matched_episode_count == 0
                ),
                "inherited_context_returned_as_auxiliary_without_episode_matches": bool(
                    inherited_memory_items and matched_episode_count == 0
                ),
                "related_context_is_auxiliary": bool(related_memory_items),
                "related_context_relation_types": (["supports"] if related_memory_items else []),
                "related_context_selection_route": (
                    "relation_supports_auxiliary" if related_memory_items else None
                ),
                **self._build_retrieval_route_details(
                    memory_item_details=memory_item_details,
                    summaries=summaries,
                    summary_selection_applied=summary_selection_applied,
                    matched_episode_count=matched_episode_count,
                    include_memory_items=request.include_memory_items,
                    inherited_memory_items=inherited_memory_items,
                    related_memory_items=related_memory_items,
                ),
                "related_context_returned_without_episode_matches": False,
                "all_episodes_filtered_out_by_query": (all_episodes_filtered_out_by_query),
                "flat_related_memory_items_is_compatibility_field": bool(related_memory_items),
                "flat_related_memory_items_matches_grouped_episode_related_items": bool(
                    related_memory_items
                ),
                "related_memory_items_by_episode_is_primary_structured_output": False,
                "related_memory_items_by_episode_are_compatibility_output": bool(
                    related_memory_items
                ),
                "relation_memory_context_groups_are_primary_output": bool(related_memory_items),
                "group_related_memory_items_are_convenience_output": bool(related_memory_items),
                "memory_context_groups": memory_context_groups,
                "inherited_memory_items": [
                    self._serialize_memory_item(memory_item)
                    for memory_item in inherited_memory_items
                ],
                "related_memory_items": [
                    self._serialize_memory_item(memory_item) for memory_item in related_memory_items
                ],
            },
        )

    def _not_implemented(
        self,
        *,
        feature: MemoryFeature,
        message: str,
        details: dict[str, Any],
    ) -> StubResponse:
        return StubResponse(
            feature=feature,
            implemented=False,
            message=message,
            available_in_version=None,
            details=details,
        )

    def _require_non_empty(
        self,
        value: str,
        *,
        field_name: str,
        feature: MemoryFeature,
    ) -> None:
        if not self._has_text(value):
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message=f"{field_name} must be a non-empty string.",
                details={"field": field_name},
            )

    def _require_positive_limit(
        self,
        value: int,
        *,
        feature: MemoryFeature,
    ) -> None:
        if value <= 0:
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message="limit must be a positive integer.",
                details={"field": "limit", "value": value},
            )

    def _collect_episode_context(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        if not workflow_ids:
            return ()

        workflow_episode_lists = [
            self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=limit,
            )
            for workflow_id in workflow_ids
        ]

        episodes: list[EpisodeRecord] = []
        seen_episode_ids: set[UUID] = set()
        round_index = 0

        while len(episodes) < limit:
            added_in_round = False

            for workflow_episodes in workflow_episode_lists:
                if round_index >= len(workflow_episodes):
                    continue

                episode = workflow_episodes[round_index]
                if episode.episode_id in seen_episode_ids:
                    continue

                seen_episode_ids.add(episode.episode_id)
                episodes.append(episode)
                added_in_round = True

                if len(episodes) >= limit:
                    break

            if not added_in_round:
                break

            round_index += 1

        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])

    def _order_workflow_ids_by_freshness_signals(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
        limit: int,
    ) -> tuple[UUID, ...]:
        if not workflow_ids:
            return ()

        workflow_recencies: list[
            tuple[
                bool,
                bool,
                bool,
                bool,
                datetime,
                datetime,
                datetime,
                datetime,
                int,
                UUID,
            ]
        ] = []

        for index, workflow_id in enumerate(workflow_ids):
            freshness = (
                self._workflow_lookup.workflow_freshness_by_id(workflow_id)
                if self._workflow_lookup is not None
                else {}
            )
            latest_episode = self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=1,
            )
            workflow_is_terminal = bool(freshness.get("workflow_is_terminal") or False)
            latest_attempt_is_terminal = bool(freshness.get("latest_attempt_is_terminal") or False)
            has_latest_attempt = bool(freshness.get("has_latest_attempt") or False)
            has_latest_checkpoint = bool(freshness.get("has_latest_checkpoint") or False)
            latest_checkpoint_created_at = freshness.get(
                "latest_checkpoint_created_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_verify_report_created_at = freshness.get(
                "latest_verify_report_created_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_episode_created_at = (
                latest_episode[0].created_at
                if latest_episode
                else datetime.min.replace(tzinfo=timezone.utc)
            )
            latest_attempt_started_at = freshness.get(
                "latest_attempt_started_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            workflow_recencies.append(
                (
                    not workflow_is_terminal,
                    not latest_attempt_is_terminal,
                    has_latest_attempt,
                    has_latest_checkpoint,
                    latest_checkpoint_created_at,
                    latest_verify_report_created_at,
                    latest_episode_created_at,
                    latest_attempt_started_at,
                    -index,
                    workflow_id,
                )
            )

        workflow_recencies.sort(reverse=True)
        return tuple(workflow_id for *_, workflow_id in workflow_recencies[:limit])

    def _workflow_ordering_signals(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
    ) -> dict[str, dict[str, str | None]]:
        signals: dict[str, dict[str, str | None]] = {}

        for workflow_id in workflow_ids:
            freshness = (
                self._workflow_lookup.workflow_freshness_by_id(workflow_id)
                if self._workflow_lookup is not None
                else {}
            )
            latest_episode = self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=1,
            )
            signals[str(workflow_id)] = {
                "workflow_status": (
                    str(freshness.get("workflow_status"))
                    if freshness.get("workflow_status") is not None
                    else None
                ),
                "workflow_is_terminal": (
                    bool(freshness.get("workflow_is_terminal"))
                    if freshness.get("workflow_is_terminal") is not None
                    else None
                ),
                "latest_attempt_status": (
                    str(freshness.get("latest_attempt_status"))
                    if freshness.get("latest_attempt_status") is not None
                    else None
                ),
                "latest_attempt_is_terminal": (
                    bool(freshness.get("latest_attempt_is_terminal"))
                    if freshness.get("latest_attempt_is_terminal") is not None
                    else None
                ),
                "has_latest_attempt": (
                    bool(freshness.get("has_latest_attempt"))
                    if freshness.get("has_latest_attempt") is not None
                    else None
                ),
                "latest_attempt_verify_status": (
                    str(freshness.get("latest_attempt_verify_status"))
                    if freshness.get("latest_attempt_verify_status") is not None
                    else None
                ),
                "has_latest_checkpoint": (
                    bool(freshness.get("has_latest_checkpoint"))
                    if freshness.get("has_latest_checkpoint") is not None
                    else None
                ),
                "latest_checkpoint_created_at": (
                    freshness.get("latest_checkpoint_created_at").isoformat()
                    if freshness.get("latest_checkpoint_created_at") is not None
                    else None
                ),
                "latest_verify_report_created_at": (
                    freshness.get("latest_verify_report_created_at").isoformat()
                    if freshness.get("latest_verify_report_created_at") is not None
                    else None
                ),
                "latest_episode_created_at": (
                    latest_episode[0].created_at.isoformat() if latest_episode else None
                ),
                "latest_attempt_started_at": (
                    freshness.get("latest_attempt_started_at").isoformat()
                    if freshness.get("latest_attempt_started_at") is not None
                    else None
                ),
                "workflow_updated_at": (
                    freshness.get("workflow_updated_at").isoformat()
                    if freshness.get("workflow_updated_at") is not None
                    else None
                ),
            }

        return signals

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

            if include_summaries:
                detail["summary"] = {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(episode.workflow_instance_id),
                    "memory_item_count": memory_item_count,
                    "memory_item_types": [memory_item.type for memory_item in memory_items],
                    "memory_item_provenance": [
                        memory_item.provenance for memory_item in memory_items
                    ],
                }

            details.append(detail)

        return tuple(details)

    def _collect_supports_related_memory_items(
        self,
        *,
        memory_item_details: tuple[dict[str, Any], ...],
        limit: int,
        include_relation_metadata: bool = False,
    ) -> (
        tuple[MemoryItemRecord, ...]
        | tuple[tuple[MemoryItemRecord, ...], tuple[MemoryRelationRecord, ...]]
    ):
        if limit <= 0:
            if include_relation_metadata:
                return (), ()
            return ()

        if not isinstance(self._memory_item_repository, MemoryRelationMemoryItemLookupRepository):
            if include_relation_metadata:
                return (), ()
            return ()

        related_memory_items: list[MemoryItemRecord] = []
        related_relations: list[MemoryRelationRecord] = []
        seen_memory_ids: set[UUID] = set()
        source_memory_ids: list[UUID] = []

        for detail in memory_item_details:
            raw_memory_items = detail.get("memory_items")
            if not isinstance(raw_memory_items, list):
                continue

            for raw_memory_item in raw_memory_items:
                if not isinstance(raw_memory_item, dict):
                    continue

                raw_memory_id = raw_memory_item.get("memory_id")
                if not isinstance(raw_memory_id, str):
                    continue

                try:
                    source_memory_id = UUID(raw_memory_id)
                except ValueError:
                    continue

                source_memory_ids.append(source_memory_id)

        relations_by_source_memory_id: dict[UUID, tuple[MemoryRelationRecord, ...]] = {
            source_memory_id: () for source_memory_id in source_memory_ids
        }
        bulk_relations = self._memory_relation_repository.list_by_source_memory_ids(
            tuple(source_memory_ids)
        )
        for relation in bulk_relations:
            source_memory_id = relation.source_memory_id
            if source_memory_id not in relations_by_source_memory_id:
                continue
            relations_by_source_memory_id[source_memory_id] = relations_by_source_memory_id[
                source_memory_id
            ] + (relation,)

        supports_target_memory_ids: tuple[UUID, ...] = ()
        if isinstance(
            self._memory_relation_repository,
            MemoryRelationSupportsTargetLookupRepository,
        ):
            supports_target_memory_ids = self._memory_relation_repository.list_distinct_support_target_memory_ids_by_source_memory_ids(
                tuple(source_memory_ids)
            )

        if supports_target_memory_ids:
            for target_memory_id in supports_target_memory_ids:
                if target_memory_id in seen_memory_ids:
                    continue

                target_memory_items = self._memory_item_repository.list_by_memory_ids(
                    (target_memory_id,),
                    limit=limit,
                )
                if not target_memory_items:
                    continue

                target_memory_item = target_memory_items[0]
                seen_memory_ids.add(target_memory_item.memory_id)
                related_memory_items.append(target_memory_item)

                if include_relation_metadata:
                    matched_relation: MemoryRelationRecord | None = None
                    for source_memory_id in source_memory_ids:
                        relations = relations_by_source_memory_id.get(source_memory_id, ())
                        for relation in relations:
                            if relation.relation_type != "supports":
                                continue
                            if relation.target_memory_id != target_memory_item.memory_id:
                                continue
                            matched_relation = relation
                            break
                        if matched_relation is not None:
                            break

                    if matched_relation is not None:
                        related_relations.append(matched_relation)

                if len(related_memory_items) >= limit:
                    if include_relation_metadata:
                        return (
                            tuple(related_memory_items),
                            tuple(related_relations),
                        )
                    return tuple(related_memory_items)

            if include_relation_metadata:
                return tuple(related_memory_items), tuple(related_relations)
            return tuple(related_memory_items)
        for source_memory_id in source_memory_ids:
            relations = relations_by_source_memory_id.get(source_memory_id, ())

            for relation in relations:
                if relation.relation_type != "supports":
                    continue
                if relation.target_memory_id in seen_memory_ids:
                    continue

                target_memory_items = self._memory_item_repository.list_by_memory_ids(
                    (relation.target_memory_id,),
                    limit=limit,
                )
                if not target_memory_items:
                    continue

                target_memory_item = target_memory_items[0]

                seen_memory_ids.add(target_memory_item.memory_id)
                related_memory_items.append(target_memory_item)
                related_relations.append(relation)

                if len(related_memory_items) >= limit:
                    if include_relation_metadata:
                        return (
                            tuple(related_memory_items),
                            tuple(related_relations),
                        )
                    return tuple(related_memory_items)

        if include_relation_metadata:
            return tuple(related_memory_items), tuple(related_relations)
        return tuple(related_memory_items)

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
    ) -> dict[str, Any]:
        episode_direct_group_present = bool(
            include_memory_items and matched_episode_count > 0 and not summary_selection_applied
        )
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
            and (inherited_memory_items or related_memory_items)
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
                }
            )

        if include_memory_items:
            for episode, detail in zip(episodes, memory_item_details, strict=False):
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
                        "memory_items": detail.get("memory_items", []),
                        "related_memory_items": detail.get("related_memory_items", []),
                        "related_memory_item_provenance": detail.get(
                            "related_memory_item_provenance", []
                        ),
                        "related_memory_relation_edges": detail.get(
                            "related_memory_relation_edges", []
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
            "content": memory_item.content,
            "metadata": dict(memory_item.metadata),
            "created_at": memory_item.created_at.isoformat(),
            "updated_at": memory_item.updated_at.isoformat(),
        }

    def _score_memory_item_for_query(
        self,
        *,
        memory_item: MemoryItemRecord,
        normalized_query: str,
    ) -> tuple[float, tuple[str, ...]]:
        score = 0.0
        matched_fields: list[str] = []

        content_text = memory_item.content.casefold()
        if normalized_query in content_text:
            score += 3.0
            matched_fields.append("content")

        metadata_strings = metadata_query_strings(memory_item.metadata)
        metadata_key_match = False
        metadata_value_match = False

        for index, metadata_query_string in enumerate(metadata_strings):
            if normalized_query not in metadata_query_string:
                continue
            if index % 2 == 0:
                metadata_key_match = True
            else:
                metadata_value_match = True

        if metadata_key_match:
            score += 1.5
            matched_fields.append("metadata_keys")
        if metadata_value_match:
            score += 1.5
            matched_fields.append("metadata_values")

        return score, tuple(matched_fields)

    def _parse_uuid(
        self,
        value: str,
        *,
        field_name: str,
        feature: MemoryFeature,
    ) -> UUID:
        try:
            return UUID(value.strip())
        except AttributeError, ValueError:
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message=f"{field_name} must be a valid UUID string.",
                details={"field": field_name},
            ) from None

    def _maybe_store_embedding(self, memory_item: MemoryItemRecord) -> dict[str, Any]:
        if self._embedding_generator is None or self._memory_embedding_repository is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": ("embedding_persistence_not_configured"),
            }

        try:
            result = self._embedding_generator.generate(
                EmbeddingRequest(
                    text=memory_item.content,
                    metadata=memory_item.metadata,
                )
            )
        except EmbeddingGenerationError as exc:
            failure_reason = f"embedding_generation_failed:{exc.provider}"
            details: dict[str, Any] = {
                "embedding_persistence_status": "failed",
                "embedding_generation_skipped_reason": failure_reason,
                "embedding_generation_failure": {
                    "provider": exc.provider,
                    "message": str(exc),
                    "details": dict(exc.details),
                },
            }
            return details

        self._memory_embedding_repository.create(
            MemoryEmbeddingRecord(
                memory_embedding_id=uuid4(),
                memory_id=memory_item.memory_id,
                embedding_model=result.model,
                embedding=result.vector,
                content_hash=result.content_hash,
                created_at=memory_item.updated_at,
            )
        )
        return {
            "embedding_persistence_status": "stored",
            "embedding_generation_skipped_reason": None,
            "embedding_provider": result.provider,
            "embedding_model": result.model,
            "embedding_vector_dimensions": len(result.vector),
            "embedding_content_hash": result.content_hash,
        }

    def _resolve_workspace_id(self, workflow_instance_id: UUID) -> UUID | None:
        if self._workspace_lookup is None:
            return None
        return self._workspace_lookup.workspace_id_by_workflow_id(workflow_instance_id)

    @staticmethod
    def _has_text(value: object | None) -> bool:
        return isinstance(value, str) and bool(value.strip())
