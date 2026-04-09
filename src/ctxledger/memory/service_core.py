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
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from ..runtime.task_recall import (
    build_detour_override_explanations,
    build_latest_candidate_retained_explanations,
    build_memory_context_task_recall_details,
    build_resumability_explanations,
    build_task_recall_detour_override_applied,
    build_task_recall_ranking_entry,
    build_terminal_override_explanations,
)
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
from .service_core_context import ContextShapingMixin
from .service_core_relations import RelationContextMixin
from .service_core_search import SearchHelperMixin
from .service_core_search_task_recall import (
    apply_semantic_only_discount,
    build_latest_vs_selected_search_comparison_summary_explanations,
    build_latest_vs_selected_search_context,
    build_search_ranking_reasons,
    build_search_response_details,
    build_search_task_recall_detail,
    completion_memory_tiebreak_priority,
    selected_task_recall_bonus_enabled,
)
from .service_core_summary import EpisodeSummaryBuilder
from .service_core_task_recall import TaskRecallMixin
from .service_core_workflow import WorkflowResolutionMixin
from .types import (
    BuildEpisodeSummaryRequest,
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


class MemoryService(
    WorkflowResolutionMixin,
    RelationContextMixin,
    TaskRecallMixin,
    SearchHelperMixin,
    ContextShapingMixin,
):
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
        self._episode_summary_builder = EpisodeSummaryBuilder(
            episode_repository=self._episode_repository,
            memory_item_repository=self._memory_item_repository,
            memory_summary_repository=self._memory_summary_repository,
            memory_summary_membership_repository=self._memory_summary_membership_repository,
            workspace_lookup=workspace_lookup,
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

    def _coerce_interaction_metadata(
        self,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}

        normalized = dict(metadata)

        file_name = normalized.get("file_name")
        if isinstance(file_name, str) and file_name.strip():
            normalized["file_name"] = file_name.strip()

        file_path = normalized.get("file_path")
        if isinstance(file_path, str) and file_path.strip():
            normalized["file_path"] = file_path.strip()

        file_operation = normalized.get("file_operation")
        if isinstance(file_operation, str) and file_operation.strip():
            normalized["file_operation"] = file_operation.strip()

        purpose = normalized.get("purpose")
        if isinstance(purpose, str) and purpose.strip():
            normalized["purpose"] = purpose.strip()

        interaction_role = normalized.get("interaction_role")
        if isinstance(interaction_role, str) and interaction_role.strip():
            normalized["interaction_role"] = interaction_role.strip()

        interaction_kind = normalized.get("interaction_kind")
        if isinstance(interaction_kind, str) and interaction_kind.strip():
            normalized["interaction_kind"] = interaction_kind.strip()

        return normalized

    def _metadata_matches_search_filters(
        self,
        *,
        memory_item: MemoryItemRecord,
        filters: dict[str, Any],
    ) -> bool:
        if not filters:
            return True

        normalized_filters = dict(filters)

        provenance_filter = normalized_filters.get("provenance")
        if isinstance(provenance_filter, list) and provenance_filter:
            if memory_item.provenance not in {str(value) for value in provenance_filter}:
                return False
        elif isinstance(provenance_filter, str) and provenance_filter.strip():
            if memory_item.provenance != provenance_filter.strip():
                return False

        provenance_kind_filter = normalized_filters.get("provenance_kind")
        provenance_kind = (
            "interaction"
            if memory_item.provenance == "interaction"
            else "workflow_memory"
            if memory_item.provenance in {"workflow_checkpoint_auto", "workflow_complete_auto"}
            else "episode_memory"
            if memory_item.provenance == "episode"
            else "other"
        )
        if isinstance(provenance_kind_filter, list) and provenance_kind_filter:
            if provenance_kind not in {str(value) for value in provenance_kind_filter}:
                return False
        elif isinstance(provenance_kind_filter, str) and provenance_kind_filter.strip():
            if provenance_kind != provenance_kind_filter.strip():
                return False

        memory_types_filter = normalized_filters.get("memory_types")
        if isinstance(memory_types_filter, list) and memory_types_filter:
            if memory_item.type not in {str(value) for value in memory_types_filter}:
                return False
        elif isinstance(memory_types_filter, str) and memory_types_filter.strip():
            if memory_item.type != memory_types_filter.strip():
                return False

        interaction_roles_filter = normalized_filters.get("interaction_roles")
        interaction_role = memory_item.metadata.get("interaction_role")
        if isinstance(interaction_roles_filter, list) and interaction_roles_filter:
            if str(interaction_role) not in {str(value) for value in interaction_roles_filter}:
                return False
        elif isinstance(interaction_roles_filter, str) and interaction_roles_filter.strip():
            if str(interaction_role) != interaction_roles_filter.strip():
                return False

        interaction_kind_filter = normalized_filters.get("interaction_kind")
        stored_interaction_kind = memory_item.metadata.get("interaction_kind")
        if isinstance(interaction_kind_filter, list) and interaction_kind_filter:
            if str(stored_interaction_kind) not in {
                str(value) for value in interaction_kind_filter
            }:
                return False
        elif isinstance(interaction_kind_filter, str) and interaction_kind_filter.strip():
            if str(stored_interaction_kind) != interaction_kind_filter.strip():
                return False

        file_name_filter = normalized_filters.get("file_name")
        stored_file_name = memory_item.metadata.get("file_name")
        if isinstance(file_name_filter, str) and file_name_filter.strip():
            if str(stored_file_name) != file_name_filter.strip():
                return False

        file_names_filter = normalized_filters.get("file_names")
        if isinstance(file_names_filter, list) and file_names_filter:
            if str(stored_file_name) not in {str(value) for value in file_names_filter}:
                return False

        file_path_filter = normalized_filters.get("file_path")
        stored_file_path = memory_item.metadata.get("file_path")
        if isinstance(file_path_filter, str) and file_path_filter.strip():
            if str(stored_file_path) != file_path_filter.strip():
                return False

        file_paths_filter = normalized_filters.get("file_paths")
        if isinstance(file_paths_filter, list) and file_paths_filter:
            if str(stored_file_path) not in {str(value) for value in file_paths_filter}:
                return False

        file_operation_filter = normalized_filters.get("file_operation")
        stored_file_operation = memory_item.metadata.get("file_operation")
        if isinstance(file_operation_filter, str) and file_operation_filter.strip():
            if str(stored_file_operation) != file_operation_filter.strip():
                return False

        purpose_filter = normalized_filters.get("purpose")
        stored_purpose = memory_item.metadata.get("purpose")
        if isinstance(purpose_filter, str) and purpose_filter.strip():
            normalized_purpose_filter = normalize_query_text(purpose_filter)
            normalized_stored_purpose = (
                normalize_query_text(str(stored_purpose))
                if isinstance(stored_purpose, str) and stored_purpose.strip()
                else None
            )
            if (
                normalized_purpose_filter is None
                or normalized_stored_purpose is None
                or normalized_purpose_filter not in normalized_stored_purpose
            ):
                return False

        return True

    def _interaction_priority_bonus(
        self,
        *,
        memory_item: MemoryItemRecord,
        filters: dict[str, Any],
    ) -> tuple[float, bool]:
        provenance_kind_filter = filters.get("provenance_kind")
        provenance_filter = filters.get("provenance")
        interaction_roles_filter = filters.get("interaction_roles")
        interaction_kind_filter = filters.get("interaction_kind")
        file_name_filter = filters.get("file_name")
        file_names_filter = filters.get("file_names")
        file_path_filter = filters.get("file_path")
        file_paths_filter = filters.get("file_paths")
        file_operation_filter = filters.get("file_operation")
        purpose_filter = filters.get("purpose")

        interaction_context_requested = any(
            (
                provenance_kind_filter is not None,
                provenance_filter is not None,
                interaction_roles_filter is not None,
                interaction_kind_filter is not None,
                file_name_filter is not None,
                file_names_filter is not None,
                file_path_filter is not None,
                file_paths_filter is not None,
                file_operation_filter is not None,
                purpose_filter is not None,
            )
        )

        if memory_item.provenance != "interaction":
            return 0.0, interaction_context_requested

        if interaction_context_requested:
            return 1.5, True

        if memory_item.type in {"interaction_request", "interaction_response"}:
            return 0.5, False

        return 0.0, False

    def _failure_reuse_detail(
        self,
        *,
        memory_item: MemoryItemRecord,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        interaction_role = memory_item.metadata.get("interaction_role")
        interaction_kind = memory_item.metadata.get("interaction_kind")
        file_name = memory_item.metadata.get("file_name")
        file_path = memory_item.metadata.get("file_path")
        file_operation = memory_item.metadata.get("file_operation")
        purpose = memory_item.metadata.get("purpose")

        failure_related_filter_requested = any(
            (
                filters.get("file_name") is not None,
                filters.get("file_names") is not None,
                filters.get("file_path") is not None,
                filters.get("file_paths") is not None,
                filters.get("file_operation") is not None,
                filters.get("purpose") is not None,
                filters.get("interaction_roles") is not None,
                filters.get("interaction_kind") is not None,
                filters.get("provenance") is not None,
                filters.get("provenance_kind") is not None,
            )
        )
        file_work_present = any(
            (
                isinstance(file_name, str) and file_name.strip(),
                isinstance(file_path, str) and file_path.strip(),
                isinstance(file_operation, str) and file_operation.strip(),
                isinstance(purpose, str) and purpose.strip(),
            )
        )
        interaction_present = memory_item.provenance == "interaction"
        likely_failure_reuse_signal = failure_related_filter_requested and (
            file_work_present or interaction_present
        )

        return {
            "failure_reuse_candidate": likely_failure_reuse_signal,
            "failure_reuse_reason": (
                "interaction and file-work metadata can support bounded failure reuse lookup"
                if likely_failure_reuse_signal
                else None
            ),
            "interaction_present": interaction_present,
            "interaction_role": interaction_role,
            "interaction_kind": interaction_kind,
            "file_work_present": file_work_present,
            "file_name": file_name,
            "file_path": file_path,
            "file_operation": file_operation,
            "purpose": purpose,
        }

    def persist_interaction_memory(
        self,
        *,
        content: str,
        interaction_role: str,
        interaction_kind: str,
        workspace_id: str | None = None,
        workflow_instance_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItemRecord:
        self._require_non_empty(
            content,
            field_name="content",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        self._require_non_empty(
            interaction_role,
            field_name="interaction_role",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        self._require_non_empty(
            interaction_kind,
            field_name="interaction_kind",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )

        resolved_workspace_id: UUID | None = None
        if self._has_text(workspace_id):
            resolved_workspace_id = self._parse_uuid(
                workspace_id or "",
                field_name="workspace_id",
                feature=MemoryFeature.REMEMBER_EPISODE,
            )

        resolved_workflow_instance_id: UUID | None = None
        if self._has_text(workflow_instance_id):
            resolved_workflow_instance_id = self._parse_uuid(
                workflow_instance_id or "",
                field_name="workflow_instance_id",
                feature=MemoryFeature.REMEMBER_EPISODE,
            )

        if resolved_workspace_id is None and resolved_workflow_instance_id is not None:
            resolved_workspace_id = self._resolve_workspace_id(resolved_workflow_instance_id)

        created_at = datetime.now(timezone.utc)
        memory_item = self._memory_item_repository.create(
            MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=resolved_workspace_id,
                episode_id=None,
                type=interaction_kind.strip(),
                provenance="interaction",
                content=content.strip(),
                metadata=self._coerce_interaction_metadata(
                    {
                        "interaction_role": interaction_role.strip(),
                        "interaction_kind": interaction_kind.strip(),
                        **dict(metadata or {}),
                    }
                ),
                created_at=created_at,
                updated_at=created_at,
            )
        )
        self._maybe_store_embedding(memory_item)
        return memory_item

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

    def build_episode_summary(
        self,
        request: BuildEpisodeSummaryRequest,
    ) -> BuildEpisodeSummaryResult:
        """Build one explicit canonical summary for a selected episode."""

        return self._episode_summary_builder.build(
            request,
            parse_uuid=self._parse_uuid,
            require_non_empty=self._require_non_empty,
            build_summary_text=self._build_episode_summary_text,
            feature=MemoryFeature.GET_CONTEXT,
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
            workspace_memory_items = self._memory_item_repository.list_by_workspace_id(
                workspace_id,
                limit=request.limit,
            )
            filtered_workspace_items = tuple(
                memory_item
                for memory_item in workspace_memory_items
                if self._metadata_matches_search_filters(
                    memory_item=memory_item,
                    filters=request.filters,
                )
            )
            if filtered_workspace_items:
                memory_items = filtered_workspace_items
            elif request.filters:
                memory_items = ()
            else:
                memory_items = workspace_memory_items

        (
            latest_task_recall_workflow_id,
            selected_task_recall_workflow_id,
            latest_task_recall_signals,
            selected_task_recall_signals,
            task_recall_selected_equals_latest,
        ) = self._task_recall_search_context(
            workspace_id=workspace_id,
            limit=request.limit,
        )

        (
            semantic_matches,
            semantic_query_generated,
            semantic_generation_skipped_reason,
            semantic_score_by_memory_id,
            semantic_matched_fields_by_memory_id,
        ) = self._build_semantic_match_details(
            request_query=request.query,
            workspace_id=workspace_id,
            limit=request.limit,
        )
        semantic_result_count = len(semantic_matches)

        scored_results: list[SearchResultRecord] = []
        lexical_weight = 1.0
        semantic_weight = 1.0
        semantic_only_discount = 0.75
        selected_task_recall_memory_bonus = 0.5
        selected_task_recall_bonus_enabled_flag = selected_task_recall_bonus_enabled(
            selected_task_recall_workflow_id=selected_task_recall_workflow_id,
            latest_task_recall_workflow_id=latest_task_recall_workflow_id,
        )
        latest_task_recall_ticket_detour_like = False
        latest_task_recall_checkpoint_detour_like = False
        selected_task_recall_ticket_detour_like = False
        selected_task_recall_checkpoint_detour_like = False

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
            hybrid_score, score_mode, semantic_only_discount_applied = apply_semantic_only_discount(
                lexical_score=lexical_score,
                semantic_score=semantic_score,
                lexical_component=lexical_component,
                semantic_component=semantic_component,
                semantic_only_discount=semantic_only_discount,
            )
            completion_tiebreak_priority = completion_memory_tiebreak_priority(memory_item)

            selected_continuation_target_bonus_applied = False
            (
                selected_task_recall_memory_ids,
                selected_task_recall_episode_id,
            ) = self._selected_continuation_target_details(
                selected_task_recall_bonus_enabled=selected_task_recall_bonus_enabled_flag,
                selected_task_recall_workflow_id=selected_task_recall_workflow_id,
                limit=request.limit,
            )

            if selected_task_recall_bonus_enabled_flag and (
                memory_item.memory_id in selected_task_recall_memory_ids
                or (
                    selected_task_recall_episode_id is not None
                    and memory_item.episode_id == selected_task_recall_episode_id
                )
            ):
                hybrid_score += selected_task_recall_memory_bonus
                selected_continuation_target_bonus_applied = True

            interaction_priority_bonus, interaction_context_requested = (
                self._interaction_priority_bonus(
                    memory_item=memory_item,
                    filters=request.filters,
                )
            )
            interaction_priority_bonus_applied = interaction_priority_bonus > 0
            if interaction_priority_bonus_applied:
                hybrid_score += interaction_priority_bonus

            if hybrid_score <= 0:
                continue

            ranking_reasons = build_search_ranking_reasons(
                lexical_score=lexical_score,
                semantic_score=semantic_score,
                score_mode=score_mode,
                semantic_only_discount_applied=semantic_only_discount_applied,
                semantic_only_discount=semantic_only_discount,
                selected_continuation_target_bonus_applied=(
                    selected_continuation_target_bonus_applied
                ),
                selected_task_recall_memory_bonus=selected_task_recall_memory_bonus,
                completion_tiebreak_applied=completion_tiebreak_priority > 0,
            )
            if interaction_priority_bonus_applied:
                ranking_reasons.append(
                    {
                        "code": (
                            "interaction_context_priority_bonus"
                            if interaction_context_requested
                            else "interaction_priority_bonus"
                        ),
                        "message": (
                            "interaction memory was prioritized because the bounded search filters requested interaction or file-work context"
                            if interaction_context_requested
                            else "interaction memory received a bounded ranking preference"
                        ),
                        "value": interaction_priority_bonus,
                    }
                )

            failure_reuse_detail = self._failure_reuse_detail(
                memory_item=memory_item,
                filters=request.filters,
            )
            if failure_reuse_detail["failure_reuse_candidate"]:
                ranking_reasons.append(
                    {
                        "code": "failure_reuse_file_work_signal",
                        "message": (
                            "file-work and interaction metadata made this result a stronger bounded failure-reuse candidate"
                        ),
                    }
                )

            latest_task_recall_ticket_detour_like, latest_task_recall_checkpoint_detour_like, _ = (
                self._task_recall_search_detour_details(latest_task_recall_signals)
            )
            (
                selected_task_recall_ticket_detour_like,
                selected_task_recall_checkpoint_detour_like,
                _,
            ) = self._task_recall_search_detour_details(selected_task_recall_signals)

            task_recall_detail = build_search_task_recall_detail(
                memory_item=memory_item,
                combined_fields=combined_fields,
                workspace_id=workspace_id,
                latest_task_recall_workflow_id=latest_task_recall_workflow_id,
                selected_task_recall_workflow_id=selected_task_recall_workflow_id,
                task_recall_selected_equals_latest=task_recall_selected_equals_latest,
                latest_task_recall_signals=latest_task_recall_signals,
                selected_task_recall_signals=selected_task_recall_signals,
                latest_task_recall_ticket_detour_like=latest_task_recall_ticket_detour_like,
                latest_task_recall_checkpoint_detour_like=(
                    latest_task_recall_checkpoint_detour_like
                ),
                selected_task_recall_ticket_detour_like=selected_task_recall_ticket_detour_like,
                selected_task_recall_checkpoint_detour_like=(
                    selected_task_recall_checkpoint_detour_like
                ),
                selected_continuation_target_bonus_applied=(
                    selected_continuation_target_bonus_applied
                ),
                selected_task_recall_memory_bonus=selected_task_recall_memory_bonus,
            )

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
                        "semantic_only_discount_applied": semantic_only_discount_applied,
                        "reason_list": ranking_reasons,
                        "task_recall_detail": task_recall_detail,
                        "remember_path_detail": {
                            "memory_origin": memory_item.metadata.get("memory_origin"),
                            "promotion_field": memory_item.metadata.get("promotion_field"),
                            "promotion_source": memory_item.metadata.get("promotion_source"),
                            "checkpoint_id": memory_item.metadata.get("checkpoint_id"),
                            "step_name": memory_item.metadata.get("step_name"),
                            "workflow_status": memory_item.metadata.get("workflow_status"),
                            "attempt_status": memory_item.metadata.get("attempt_status"),
                            "supports_relation_present": bool(
                                self._memory_relation_repository is not None
                                and any(
                                    relation.source_memory_id == memory_item.memory_id
                                    or relation.target_memory_id == memory_item.memory_id
                                    for relation in self._memory_relation_repository.list_by_source_memory_ids(
                                        (memory_item.memory_id,)
                                    )
                                )
                            ),
                            "supports_relation_reasons": (
                                [
                                    relation.metadata.get("relation_reason")
                                    for relation in self._memory_relation_repository.list_by_source_memory_ids(
                                        (memory_item.memory_id,)
                                    )
                                    if isinstance(relation.metadata.get("relation_reason"), str)
                                    and str(relation.metadata.get("relation_reason")).strip()
                                ]
                                if self._memory_relation_repository is not None
                                else []
                            ),
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
                            "failure_reuse_detail": failure_reuse_detail,
                        },
                    },
                    created_at=memory_item.created_at,
                    updated_at=memory_item.updated_at,
                )
            )

        scored_results.sort(
            key=lambda result: (
                result.score,
                completion_memory_tiebreak_priority(result),
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

        (
            latest_vs_selected_search_context_present,
            latest_vs_selected_search_context,
        ) = build_latest_vs_selected_search_context(
            latest_task_recall_workflow_id=latest_task_recall_workflow_id,
            selected_task_recall_workflow_id=selected_task_recall_workflow_id,
            latest_task_recall_signals=latest_task_recall_signals,
            selected_task_recall_signals=selected_task_recall_signals,
            latest_task_recall_ticket_detour_like=latest_task_recall_ticket_detour_like,
            latest_task_recall_checkpoint_detour_like=latest_task_recall_checkpoint_detour_like,
            selected_task_recall_ticket_detour_like=selected_task_recall_ticket_detour_like,
            selected_task_recall_checkpoint_detour_like=selected_task_recall_checkpoint_detour_like,
            task_recall_selected_equals_latest=task_recall_selected_equals_latest,
        )
        latest_vs_selected_search_comparison_summary_explanations = (
            build_latest_vs_selected_search_comparison_summary_explanations(
                latest_vs_selected_search_context_present=(
                    latest_vs_selected_search_context_present
                ),
                latest_task_recall_signals=latest_task_recall_signals,
                selected_task_recall_signals=selected_task_recall_signals,
                latest_task_recall_ticket_detour_like=latest_task_recall_ticket_detour_like,
                latest_task_recall_checkpoint_detour_like=(
                    latest_task_recall_checkpoint_detour_like
                ),
                selected_task_recall_ticket_detour_like=selected_task_recall_ticket_detour_like,
                selected_task_recall_checkpoint_detour_like=(
                    selected_task_recall_checkpoint_detour_like
                ),
            )
        )

        details = build_search_response_details(
            request=request,
            normalized_query=normalized_query,
            search_mode=search_mode,
            memory_items_considered=len(memory_items),
            semantic_result_count=semantic_result_count,
            semantic_query_generated=semantic_query_generated,
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
            semantic_only_discount=semantic_only_discount,
            result_mode_counts=result_mode_counts,
            result_composition=result_composition,
            results_returned=len(limited_results),
            semantic_generation_skipped_reason=semantic_generation_skipped_reason,
            workspace_id=workspace_id,
            latest_task_recall_workflow_id=latest_task_recall_workflow_id,
            selected_task_recall_workflow_id=selected_task_recall_workflow_id,
            task_recall_selected_equals_latest=task_recall_selected_equals_latest,
            latest_vs_selected_search_context_present=(latest_vs_selected_search_context_present),
            latest_vs_selected_search_context=latest_vs_selected_search_context,
            latest_vs_selected_search_comparison_summary_explanations=(
                latest_vs_selected_search_comparison_summary_explanations
            ),
        )

        return SearchMemoryResponse(
            feature=MemoryFeature.SEARCH,
            implemented=True,
            message=message,
            status="ok",
            available_in_version="0.9.0",
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
                raw_workspace_lookup = getattr(
                    self._workflow_lookup,
                    "workflow_ids_by_workspace_id_raw_order",
                    None,
                )
                if callable(raw_workspace_lookup):
                    workspace_workflow_ids = raw_workspace_lookup(
                        request.workspace_id or "",
                        limit=request.limit,
                    )
                else:
                    workspace_workflow_ids = self._workflow_lookup.workflow_ids_by_workspace_id(
                        request.workspace_id or "",
                        limit=request.limit,
                    )

            if self._has_text(request.ticket_id):
                raw_ticket_lookup = getattr(
                    self._workflow_lookup,
                    "workflow_ids_by_ticket_id_raw_order",
                    None,
                )
                if callable(raw_ticket_lookup):
                    ticket_workflow_ids = raw_ticket_lookup(
                        request.ticket_id or "",
                        limit=request.limit,
                    )
                else:
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
        raw_ordering_signals: dict[str, dict[str, str | bool | None]] = {}
        if resolved_workflow_instance_id is None:
            resolved_workflow_ids = signal_ordered_workflow_ids
            if resolver_ordered_workflow_ids:
                raw_ordering_signals = self._workflow_ordering_signals(
                    workflow_ids=resolver_ordered_workflow_ids
                )
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

        selected_task_recall_workflow_id = (
            str(resolved_workflow_ids[0]) if resolved_workflow_ids else None
        )
        latest_task_recall_workflow_id = (
            str(resolver_ordered_workflow_ids[0]) if resolver_ordered_workflow_ids else None
        )
        task_recall_selected_equals_latest = (
            selected_task_recall_workflow_id is not None
            and selected_task_recall_workflow_id == latest_task_recall_workflow_id
        )
        latest_task_recall_signals = (
            (
                raw_ordering_signals.get(latest_task_recall_workflow_id, {})
                if raw_ordering_signals
                else ordering_signals.get(latest_task_recall_workflow_id, {})
            )
            if latest_task_recall_workflow_id is not None
            else {}
        )
        selected_task_recall_signals = (
            ordering_signals.get(selected_task_recall_workflow_id, {})
            if selected_task_recall_workflow_id is not None
            else {}
        )
        latest_task_recall_checkpoint_json = {
            "current_objective": latest_task_recall_signals.get(
                "latest_checkpoint_current_objective"
            ),
            "next_intended_action": latest_task_recall_signals.get(
                "latest_checkpoint_next_intended_action"
            ),
            "verify_target": latest_task_recall_signals.get("latest_checkpoint_verify_target"),
            "resume_hint": latest_task_recall_signals.get("latest_checkpoint_resume_hint"),
            "blocker_or_risk": latest_task_recall_signals.get("latest_checkpoint_blocker_or_risk"),
            "failure_guard": latest_task_recall_signals.get("latest_checkpoint_failure_guard"),
        }
        selected_task_recall_checkpoint_json = {
            "current_objective": selected_task_recall_signals.get(
                "latest_checkpoint_current_objective"
            ),
            "next_intended_action": selected_task_recall_signals.get(
                "latest_checkpoint_next_intended_action"
            ),
            "verify_target": selected_task_recall_signals.get("latest_checkpoint_verify_target"),
            "resume_hint": selected_task_recall_signals.get("latest_checkpoint_resume_hint"),
            "blocker_or_risk": selected_task_recall_signals.get(
                "latest_checkpoint_blocker_or_risk"
            ),
            "failure_guard": selected_task_recall_signals.get("latest_checkpoint_failure_guard"),
        }
        task_recall_latest_workflow_terminal = bool(
            latest_task_recall_signals.get("workflow_is_terminal", False)
        )
        task_recall_selected_workflow_terminal = bool(
            selected_task_recall_signals.get("workflow_is_terminal", False)
        )

        task_recall_explanations: list[dict[str, str]] = []
        task_recall_ranking_details = []

        (
            task_recall_latest_ticket_detour_like,
            task_recall_latest_checkpoint_detour_like,
            _,
        ) = self._task_recall_search_detour_details(latest_task_recall_signals)
        (
            task_recall_selected_ticket_detour_like,
            task_recall_selected_checkpoint_detour_like,
            _,
        ) = self._task_recall_search_detour_details(selected_task_recall_signals)
        task_recall_selected_primary_objective_text = (
            str(selected_task_recall_signals.get("latest_checkpoint_current_objective")).strip()
            if selected_task_recall_signals.get("latest_checkpoint_current_objective") is not None
            and str(selected_task_recall_signals.get("latest_checkpoint_current_objective")).strip()
            else None
        )
        latest_detour_task_recall_workflow_id = (
            latest_task_recall_workflow_id
            if latest_task_recall_workflow_id is not None
            and (task_recall_latest_ticket_detour_like or task_recall_latest_checkpoint_detour_like)
            else None
        )
        latest_detour_task_recall_signals = (
            latest_task_recall_signals if latest_detour_task_recall_workflow_id is not None else {}
        )
        latest_detour_task_recall_checkpoint_json = {
            "current_objective": latest_detour_task_recall_signals.get(
                "latest_checkpoint_current_objective"
            ),
            "next_intended_action": latest_detour_task_recall_signals.get(
                "latest_checkpoint_next_intended_action"
            ),
            "verify_target": latest_detour_task_recall_signals.get(
                "latest_checkpoint_verify_target"
            ),
            "resume_hint": latest_detour_task_recall_signals.get("latest_checkpoint_resume_hint"),
            "blocker_or_risk": latest_detour_task_recall_signals.get(
                "latest_checkpoint_blocker_or_risk"
            ),
            "failure_guard": latest_detour_task_recall_signals.get(
                "latest_checkpoint_failure_guard"
            ),
        }
        task_recall_prior_mainline_workflow_id = None
        task_recall_prior_mainline_signals: dict[str, str | bool | None] = {}
        task_recall_prior_mainline_checkpoint_json = {
            "current_objective": None,
            "next_intended_action": None,
            "verify_target": None,
            "resume_hint": None,
            "blocker_or_risk": None,
            "failure_guard": None,
        }

        if latest_detour_task_recall_workflow_id is not None:
            for workflow_id in [str(workflow_id) for workflow_id in resolved_workflow_ids]:
                if workflow_id == latest_detour_task_recall_workflow_id:
                    continue
                candidate_signal_map = ordering_signals.get(workflow_id, {})
                (
                    candidate_ticket_detour_like,
                    candidate_checkpoint_detour_like,
                    _,
                ) = self._task_recall_search_detour_details(candidate_signal_map)
                if candidate_ticket_detour_like or candidate_checkpoint_detour_like:
                    continue
                task_recall_prior_mainline_workflow_id = workflow_id
                task_recall_prior_mainline_signals = candidate_signal_map
                task_recall_prior_mainline_checkpoint_json = {
                    "current_objective": candidate_signal_map.get(
                        "latest_checkpoint_current_objective"
                    ),
                    "next_intended_action": candidate_signal_map.get(
                        "latest_checkpoint_next_intended_action"
                    ),
                }
                break
        elif (
            selected_task_recall_workflow_id is not None
            and latest_task_recall_workflow_id is not None
            and selected_task_recall_workflow_id != latest_task_recall_workflow_id
        ):
            task_recall_prior_mainline_workflow_id = selected_task_recall_workflow_id
            task_recall_prior_mainline_signals = selected_task_recall_signals
            task_recall_prior_mainline_checkpoint_json = selected_task_recall_checkpoint_json

        for index, workflow_id in enumerate(
            [str(workflow_id) for workflow_id in resolved_workflow_ids]
        ):
            signal_map = ordering_signals.get(workflow_id, {})
            workflow_terminal = bool(signal_map.get("workflow_is_terminal", False))
            has_latest_attempt = bool(signal_map.get("has_latest_attempt", False))
            latest_attempt_terminal = bool(signal_map.get("latest_attempt_is_terminal", False))
            has_latest_checkpoint = bool(signal_map.get("has_latest_checkpoint", False))
            is_latest = workflow_id == latest_task_recall_workflow_id
            selected = workflow_id == selected_task_recall_workflow_id

            (
                ticket_detour_like,
                checkpoint_detour_like,
                _,
            ) = self._task_recall_search_detour_details(signal_map)
            checkpoint_has_current_objective = bool(
                signal_map.get("latest_checkpoint_has_current_objective", False)
            )
            checkpoint_has_next_intended_action = bool(
                signal_map.get("latest_checkpoint_has_next_intended_action", False)
            )

            task_recall_ranking_details.append(
                build_task_recall_ranking_entry(
                    workflow_id=workflow_id,
                    resolver_order=index,
                    is_latest=is_latest,
                    selected=selected,
                    workflow_terminal=workflow_terminal,
                    has_latest_attempt=has_latest_attempt,
                    latest_attempt_terminal=latest_attempt_terminal,
                    has_latest_checkpoint=has_latest_checkpoint,
                    ticket_detour_like=ticket_detour_like,
                    checkpoint_detour_like=checkpoint_detour_like,
                    checkpoint_has_current_objective=checkpoint_has_current_objective,
                    checkpoint_has_next_intended_action=checkpoint_has_next_intended_action,
                )
            )

        task_recall_detour_override_applied = build_task_recall_detour_override_applied(
            selected_workflow_id=selected_task_recall_workflow_id,
            latest_workflow_id=latest_task_recall_workflow_id,
            latest_ticket_detour_like=task_recall_latest_ticket_detour_like,
            latest_checkpoint_detour_like=task_recall_latest_checkpoint_detour_like,
            selected_ticket_detour_like=task_recall_selected_ticket_detour_like,
            selected_checkpoint_detour_like=task_recall_selected_checkpoint_detour_like,
        )

        if (
            selected_task_recall_workflow_id is not None
            and latest_task_recall_workflow_id is not None
            and selected_task_recall_workflow_id != latest_task_recall_workflow_id
            and task_recall_latest_workflow_terminal
        ):
            task_recall_explanations.extend(build_terminal_override_explanations())
        if task_recall_detour_override_applied:
            task_recall_explanations.extend(
                build_detour_override_explanations(
                    latest_ticket_detour_like=task_recall_latest_ticket_detour_like,
                    latest_checkpoint_detour_like=task_recall_latest_checkpoint_detour_like,
                    include_candidate_reason_details=True,
                )
            )
        if (
            selected_task_recall_workflow_id is not None
            and selected_task_recall_workflow_id == latest_task_recall_workflow_id
        ):
            task_recall_explanations.extend(
                build_resumability_explanations(
                    has_latest_attempt=bool(
                        selected_task_recall_signals.get("has_latest_attempt", False)
                    ),
                    latest_attempt_terminal=bool(
                        selected_task_recall_signals.get("latest_attempt_is_terminal", False)
                    ),
                    has_latest_checkpoint=bool(
                        selected_task_recall_signals.get("has_latest_checkpoint", False)
                    ),
                )
            )
        if (
            selected_task_recall_workflow_id is not None
            and not task_recall_explanations
            and (task_recall_selected_equals_latest or len(resolved_workflow_ids) == 1)
        ):
            task_recall_explanations.extend(build_latest_candidate_retained_explanations())

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
            **build_memory_context_task_recall_details(
                selected_workflow=(
                    SimpleNamespace(
                        workflow_instance_id=selected_task_recall_workflow_id,
                        checkpoint_json=selected_task_recall_checkpoint_json,
                    )
                    if selected_task_recall_workflow_id is not None
                    else None
                ),
                latest_workflow=(
                    SimpleNamespace(
                        workflow_instance_id=latest_task_recall_workflow_id,
                        checkpoint_json=latest_task_recall_checkpoint_json,
                    )
                    if latest_task_recall_workflow_id is not None
                    else None
                ),
                running_workflow=None,
                selection_signals={
                    "selected_equals_latest": task_recall_selected_equals_latest,
                    "selected_equals_running": False,
                    "latest_workflow_terminal": task_recall_latest_workflow_terminal,
                    "latest_ticket_detour_like": task_recall_latest_ticket_detour_like,
                    "latest_checkpoint_detour_like": task_recall_latest_checkpoint_detour_like,
                    "selected_ticket_detour_like": task_recall_selected_ticket_detour_like,
                    "selected_checkpoint_detour_like": task_recall_selected_checkpoint_detour_like,
                    "latest_has_attempt_signal": bool(
                        latest_task_recall_signals.get("has_latest_attempt", False)
                    ),
                    "selected_has_attempt_signal": bool(
                        selected_task_recall_signals.get("has_latest_attempt", False)
                    ),
                    "latest_attempt_terminal": bool(
                        latest_task_recall_signals.get("latest_attempt_is_terminal", False)
                    ),
                    "selected_attempt_terminal": bool(
                        selected_task_recall_signals.get("latest_attempt_is_terminal", False)
                    ),
                    "latest_has_checkpoint_signal": bool(
                        latest_task_recall_signals.get("has_latest_checkpoint", False)
                    ),
                    "selected_has_checkpoint_signal": bool(
                        selected_task_recall_signals.get("has_latest_checkpoint", False)
                    ),
                    "detour_override_applied": task_recall_detour_override_applied,
                    "return_target_basis": (
                        "checkpoint_current_objective"
                        if bool(
                            selected_task_recall_signals.get(
                                "latest_checkpoint_has_current_objective",
                                False,
                            )
                        )
                        else (
                            "checkpoint_next_intended_action"
                            if bool(
                                selected_task_recall_signals.get(
                                    "latest_checkpoint_has_next_intended_action",
                                    False,
                                )
                            )
                            else (
                                "terminal_override"
                                if (
                                    selected_task_recall_workflow_id is not None
                                    and latest_task_recall_workflow_id is not None
                                    and selected_task_recall_workflow_id
                                    != latest_task_recall_workflow_id
                                    and task_recall_latest_workflow_terminal
                                )
                                else (
                                    "detour_override"
                                    if task_recall_detour_override_applied
                                    else (
                                        "latest_candidate"
                                        if task_recall_selected_equals_latest
                                        else "ranked_candidate"
                                    )
                                )
                            )
                        )
                    ),
                    "return_target_source": (
                        "latest_checkpoint.current_objective"
                        if bool(
                            selected_task_recall_signals.get(
                                "latest_checkpoint_has_current_objective",
                                False,
                            )
                        )
                        else (
                            "latest_checkpoint.next_intended_action"
                            if bool(
                                selected_task_recall_signals.get(
                                    "latest_checkpoint_has_next_intended_action",
                                    False,
                                )
                            )
                            else (
                                "workflow_selection.detour_override"
                                if task_recall_detour_override_applied
                                else (
                                    "workflow_selection.terminal_override"
                                    if (
                                        selected_task_recall_workflow_id is not None
                                        and latest_task_recall_workflow_id is not None
                                        and selected_task_recall_workflow_id
                                        != latest_task_recall_workflow_id
                                        and task_recall_latest_workflow_terminal
                                    )
                                    else "workflow_selection.ranking"
                                )
                            )
                        )
                    ),
                    "task_thread_present": bool(
                        selected_task_recall_signals.get("task_thread_candidate", False)
                    )
                    or selected_task_recall_workflow_id is not None,
                    "task_thread_basis": selected_task_recall_signals.get("task_thread_basis"),
                    "task_thread_source": (
                        "selected_task_recall_ranking"
                        if bool(
                            selected_task_recall_signals.get(
                                "task_thread_candidate",
                                False,
                            )
                        )
                        else None
                    ),
                    "selected_checkpoint_step_name": selected_task_recall_signals.get(
                        "latest_checkpoint_step_name"
                    ),
                    "selected_checkpoint_summary": selected_task_recall_signals.get(
                        "latest_checkpoint_summary"
                    ),
                },
                explanations=task_recall_explanations,
                ranking_details=task_recall_ranking_details,
                selected_workflow_terminal=task_recall_selected_workflow_terminal,
                selected_primary_objective_text=task_recall_selected_primary_objective_text,
                prior_mainline_workflow=(
                    SimpleNamespace(
                        workflow_instance_id=task_recall_prior_mainline_workflow_id,
                        checkpoint_json=task_recall_prior_mainline_checkpoint_json,
                    )
                    if task_recall_prior_mainline_workflow_id is not None
                    else None
                ),
                latest_checkpoint_step_name=(
                    str(latest_task_recall_signals.get("latest_checkpoint_step_name")).strip()
                    if latest_task_recall_signals.get("latest_checkpoint_step_name") is not None
                    and str(latest_task_recall_signals.get("latest_checkpoint_step_name")).strip()
                    else None
                ),
                latest_checkpoint_summary=(
                    str(latest_task_recall_signals.get("latest_checkpoint_summary")).strip()
                    if latest_task_recall_signals.get("latest_checkpoint_summary") is not None
                    and str(latest_task_recall_signals.get("latest_checkpoint_summary")).strip()
                    else None
                ),
            ),
            "task_recall_latest_detour_candidate_present": latest_detour_task_recall_workflow_id
            is not None,
            "task_recall_latest_detour_candidate_workflow_instance_id": (
                latest_detour_task_recall_workflow_id
            ),
            "task_recall_latest_detour_candidate_details_present": (
                latest_detour_task_recall_workflow_id is not None
            ),
            "task_recall_latest_detour_candidate_details": (
                {
                    "workflow_instance_id": latest_detour_task_recall_workflow_id,
                    "checkpoint_step_name": latest_task_recall_signals.get(
                        "latest_checkpoint_step_name"
                    ),
                    "checkpoint_summary": latest_task_recall_signals.get(
                        "latest_checkpoint_summary"
                    ),
                    "primary_objective_text": latest_task_recall_signals.get(
                        "latest_checkpoint_current_objective"
                    ),
                    "next_intended_action_text": latest_task_recall_signals.get(
                        "latest_checkpoint_next_intended_action"
                    ),
                    "ticket_detour_like": task_recall_latest_ticket_detour_like,
                    "checkpoint_detour_like": task_recall_latest_checkpoint_detour_like,
                    "detour_like": (
                        task_recall_latest_ticket_detour_like
                        or task_recall_latest_checkpoint_detour_like
                    ),
                    "workflow_terminal": bool(
                        latest_task_recall_signals.get("workflow_is_terminal", False)
                    ),
                    "has_attempt_signal": bool(
                        latest_task_recall_signals.get("has_latest_attempt", False)
                    ),
                    "attempt_terminal": bool(
                        latest_task_recall_signals.get("latest_attempt_is_terminal", False)
                    ),
                    "has_checkpoint_signal": bool(
                        latest_task_recall_signals.get("has_latest_checkpoint", False)
                    ),
                    "return_target_basis": (
                        "latest_candidate" if task_recall_selected_equals_latest else None
                    ),
                    "task_thread_basis": latest_task_recall_signals.get("task_thread_basis"),
                }
                if latest_detour_task_recall_workflow_id is not None
                else None
            ),
            "task_recall_prior_mainline_candidate_details_present": (
                task_recall_prior_mainline_workflow_id is not None
            ),
            "task_recall_prior_mainline_candidate_details": (
                {
                    "workflow_instance_id": task_recall_prior_mainline_workflow_id,
                    "checkpoint_step_name": task_recall_prior_mainline_signals.get(
                        "latest_checkpoint_step_name"
                    ),
                    "checkpoint_summary": task_recall_prior_mainline_signals.get(
                        "latest_checkpoint_summary"
                    ),
                    "primary_objective_text": task_recall_prior_mainline_signals.get(
                        "latest_checkpoint_current_objective"
                    ),
                    "next_intended_action_text": task_recall_prior_mainline_signals.get(
                        "latest_checkpoint_next_intended_action"
                    ),
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "workflow_terminal": bool(
                        task_recall_prior_mainline_signals.get("workflow_is_terminal", False)
                    ),
                    "has_attempt_signal": bool(
                        task_recall_prior_mainline_signals.get("has_latest_attempt", False)
                    ),
                    "attempt_terminal": bool(
                        task_recall_prior_mainline_signals.get(
                            "latest_attempt_is_terminal",
                            False,
                        )
                    ),
                    "has_checkpoint_signal": bool(
                        task_recall_prior_mainline_signals.get("has_latest_checkpoint", False)
                    ),
                    "return_target_basis": (
                        "checkpoint_current_objective"
                        if bool(
                            task_recall_prior_mainline_signals.get(
                                "latest_checkpoint_has_current_objective",
                                False,
                            )
                        )
                        else (
                            "checkpoint_next_intended_action"
                            if bool(
                                task_recall_prior_mainline_signals.get(
                                    "latest_checkpoint_has_next_intended_action",
                                    False,
                                )
                            )
                            else "non_detour_candidate"
                        )
                    ),
                    "task_thread_basis": (
                        "checkpoint_current_objective"
                        if bool(
                            task_recall_prior_mainline_signals.get(
                                "latest_checkpoint_has_current_objective",
                                False,
                            )
                        )
                        else (
                            "checkpoint_next_intended_action"
                            if bool(
                                task_recall_prior_mainline_signals.get(
                                    "latest_checkpoint_has_next_intended_action",
                                    False,
                                )
                            )
                            else "non_detour_candidate"
                        )
                    ),
                }
                if task_recall_prior_mainline_workflow_id is not None
                else None
            ),
        }

        if not request.include_episodes:
            base_details = {
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
                "memory_context_groups_are_primary_output": True,
                "memory_context_groups_are_primary_explainability_surface": True,
                "top_level_explainability_prefers_grouped_routes": True,
                "flat_related_memory_items_is_compatibility_field": False,
                "flat_related_memory_items_matches_grouped_episode_related_items": False,
                "related_memory_items_by_episode_is_primary_structured_output": False,
                "related_memory_items_by_episode_are_compatibility_output": False,
                "relation_memory_context_groups_are_primary_output": False,
                "group_related_memory_items_are_convenience_output": False,
                "readiness_explainability_is_compatibility_output": False,
                "remember_path_explainability_by_episode_is_compatibility_output": False,
                "remember_path_relation_reasons_is_compatibility_output": False,
                "remember_path_relation_reason_primary_is_compatibility_output": False,
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
                        1 if inherited_workspace_items and resolved_workspace_id is not None else 0
                    ),
                    "relation_supports_auxiliary": 0,
                    "graph_summary_auxiliary": 0,
                },
                "retrieval_route_item_counts": {
                    "summary_first": 0,
                    "episode_direct": 0,
                    "workspace_inherited_auxiliary": len(inherited_workspace_items),
                    "relation_supports_auxiliary": 0,
                    "graph_summary_auxiliary": 0,
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
                    "graph_summary_auxiliary": {
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
                    "graph_summary_auxiliary": {
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
                    "graph_summary_auxiliary": {
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
                    "graph_summary_auxiliary": [],
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
            }
            if request.primary_only:
                base_details = {
                    key: value
                    for key, value in base_details.items()
                    if key
                    not in {
                        "memory_items",
                        "related_memory_items_by_episode",
                        "remember_path_explainability_by_episode",
                        "remember_path_relation_reasons",
                        "remember_path_relation_reason_primary",
                        "remember_path_origin_counts",
                        "remember_path_promotion_field_counts",
                        "remember_path_relation_reason_counts",
                        "readiness_explainability",
                        "inherited_memory_items",
                        "related_memory_items",
                        "flat_related_memory_items_is_compatibility_field",
                        "flat_related_memory_items_matches_grouped_episode_related_items",
                        "related_memory_items_by_episode_is_primary_structured_output",
                        "related_memory_items_by_episode_are_compatibility_output",
                        "group_related_memory_items_are_convenience_output",
                        "readiness_explainability_is_compatibility_output",
                        "remember_path_explainability_by_episode_is_compatibility_output",
                        "remember_path_relation_reasons_is_compatibility_output",
                        "remember_path_relation_reason_primary_is_compatibility_output",
                    }
                }

            return GetContextResponse(
                feature=MemoryFeature.GET_CONTEXT,
                implemented=True,
                message="Episode-oriented memory context retrieved successfully.",
                status="ok",
                available_in_version="0.2.0",
                episodes=(),
                details=base_details,
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
        graph_summary_related_memory_items = self._collect_graph_summary_related_memory_items(
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
            graph_summary_related_memory_items=graph_summary_related_memory_items,
            include_memory_items=request.include_memory_items,
        )

        response_details = {
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
            "remember_path_explainability_by_episode": {
                detail["episode_id"]: {
                    "memory_items": detail.get("remember_path_memory_items", []),
                    "memory_summary": detail.get("remember_path_memory_summary", {}),
                    "relation_explanations": detail.get(
                        "remember_path_relation_explanations",
                        [],
                    ),
                    "relation_summary": detail.get("remember_path_relation_summary", {}),
                }
                for detail in memory_item_details
            },
            "remember_path_explainability_present": any(
                bool(detail.get("remember_path_memory_items"))
                or bool(detail.get("remember_path_relation_explanations"))
                for detail in memory_item_details
            ),
            "remember_path_relation_reasons": sorted(
                {
                    relation_reason
                    for detail in memory_item_details
                    for relation_reason in detail.get("remember_path_relation_summary", {})
                    .get("relation_reason_counts", {})
                    .keys()
                    if isinstance(relation_reason, str) and relation_reason.strip()
                }
            ),
            "remember_path_relation_reason_primary": (
                sorted(
                    {
                        relation_reason
                        for detail in memory_item_details
                        for relation_reason in detail.get("remember_path_relation_summary", {})
                        .get("relation_reason_counts", {})
                        .keys()
                        if isinstance(relation_reason, str) and relation_reason.strip()
                    }
                )[0]
                if any(
                    detail.get("remember_path_relation_summary", {}).get(
                        "relation_reason_counts",
                        {},
                    )
                    for detail in memory_item_details
                )
                else None
            ),
            "remember_path_origin_counts": {
                origin: sum(
                    detail.get("remember_path_memory_summary", {})
                    .get("memory_origin_counts", {})
                    .get(origin, 0)
                    for detail in memory_item_details
                )
                for origin in sorted(
                    {
                        origin
                        for detail in memory_item_details
                        for origin in detail.get("remember_path_memory_summary", {})
                        .get("memory_origin_counts", {})
                        .keys()
                        if isinstance(origin, str) and origin.strip()
                    }
                )
            },
            "remember_path_promotion_field_counts": {
                promotion_field: sum(
                    detail.get("remember_path_memory_summary", {})
                    .get("promotion_field_counts", {})
                    .get(promotion_field, 0)
                    for detail in memory_item_details
                )
                for promotion_field in sorted(
                    {
                        promotion_field
                        for detail in memory_item_details
                        for promotion_field in detail.get("remember_path_memory_summary", {})
                        .get("promotion_field_counts", {})
                        .keys()
                        if isinstance(promotion_field, str) and promotion_field.strip()
                    }
                )
            },
            "remember_path_relation_reason_counts": {
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
                        for relation_reason in detail.get("remember_path_relation_summary", {})
                        .get("relation_reason_counts", {})
                        .keys()
                        if isinstance(relation_reason, str) and relation_reason.strip()
                    }
                )
            },
            "memory_item_counts_by_episode": {
                detail["episode_id"]: detail["memory_item_count"] for detail in memory_item_details
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
            "related_context_is_auxiliary": bool(
                related_memory_items or graph_summary_related_memory_items
            ),
            "related_context_relation_types": (["supports"] if related_memory_items else [])
            + (["summarizes"] if graph_summary_related_memory_items else []),
            "related_context_selection_route": (
                "graph_summary_auxiliary"
                if graph_summary_related_memory_items
                else ("relation_supports_auxiliary" if related_memory_items else None)
            ),
            **self._build_retrieval_route_details(
                memory_item_details=memory_item_details,
                summaries=summaries,
                summary_selection_applied=summary_selection_applied,
                matched_episode_count=matched_episode_count,
                include_memory_items=request.include_memory_items,
                inherited_memory_items=inherited_memory_items,
                related_memory_items=related_memory_items,
                graph_summary_related_memory_items=graph_summary_related_memory_items,
            ),
            "related_context_returned_without_episode_matches": False,
            "all_episodes_filtered_out_by_query": (all_episodes_filtered_out_by_query),
            "memory_context_groups_are_primary_output": True,
            "memory_context_groups_are_primary_explainability_surface": True,
            "top_level_explainability_prefers_grouped_routes": True,
            "flat_related_memory_items_is_compatibility_field": bool(
                related_memory_items or graph_summary_related_memory_items
            ),
            "flat_related_memory_items_matches_grouped_episode_related_items": bool(
                related_memory_items or graph_summary_related_memory_items
            ),
            "related_memory_items_by_episode_is_primary_structured_output": False,
            "related_memory_items_by_episode_are_compatibility_output": bool(
                related_memory_items or graph_summary_related_memory_items
            ),
            "relation_memory_context_groups_are_primary_output": bool(
                related_memory_items or graph_summary_related_memory_items
            ),
            "group_related_memory_items_are_convenience_output": bool(
                related_memory_items or graph_summary_related_memory_items
            ),
            "readiness_explainability_is_compatibility_output": True,
            "remember_path_explainability_by_episode_is_compatibility_output": True,
            "remember_path_relation_reasons_is_compatibility_output": True,
            "remember_path_relation_reason_primary_is_compatibility_output": True,
            "readiness_explainability": {
                "graph_summary_auxiliary": next(
                    (
                        group.get("readiness_explainability", {})
                        for group in memory_context_groups
                        if group.get("selection_route") == "graph_summary_auxiliary"
                    ),
                    {},
                ),
                "summary_graph_mirroring": next(
                    (
                        group.get("readiness_explainability", {})
                        for group in memory_context_groups
                        if group.get("selection_route") == "graph_summary_auxiliary"
                    ),
                    {},
                ),
            },
            "memory_context_groups": memory_context_groups,
            "inherited_memory_items": [
                self._serialize_memory_item(memory_item) for memory_item in inherited_memory_items
            ],
            "related_memory_items": [
                self._serialize_memory_item(memory_item)
                for memory_item in (related_memory_items or graph_summary_related_memory_items)
            ],
        }

        if request.primary_only:
            response_details = {
                key: value
                for key, value in response_details.items()
                if key
                not in {
                    "memory_items",
                    "related_memory_items_by_episode",
                    "remember_path_explainability_by_episode",
                    "remember_path_relation_reasons",
                    "remember_path_relation_reason_primary",
                    "remember_path_origin_counts",
                    "remember_path_promotion_field_counts",
                    "remember_path_relation_reason_counts",
                    "readiness_explainability",
                    "inherited_memory_items",
                    "related_memory_items",
                    "flat_related_memory_items_is_compatibility_field",
                    "flat_related_memory_items_matches_grouped_episode_related_items",
                    "related_memory_items_by_episode_is_primary_structured_output",
                    "related_memory_items_by_episode_are_compatibility_output",
                    "group_related_memory_items_are_convenience_output",
                    "readiness_explainability_is_compatibility_output",
                    "remember_path_explainability_by_episode_is_compatibility_output",
                    "remember_path_relation_reasons_is_compatibility_output",
                    "remember_path_relation_reason_primary_is_compatibility_output",
                }
            }

        return GetContextResponse(
            feature=MemoryFeature.GET_CONTEXT,
            implemented=True,
            message="Episode-oriented memory context retrieved successfully.",
            status="ok",
            available_in_version="0.2.0",
            episodes=episodes,
            details=response_details,
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

        return self._interleave_workflow_episodes(
            workflow_ids=workflow_ids,
            limit=limit,
        )

    def _build_episode_summary_text(
        self,
        *,
        episode: EpisodeRecord,
        memory_items: tuple[MemoryItemRecord, ...],
    ) -> str | None:
        normalized_episode_summary = episode.summary.strip()
        normalized_memory_contents = [
            memory_item.content.strip()
            for memory_item in memory_items
            if memory_item.content.strip()
        ]
        if normalized_episode_summary and normalized_memory_contents:
            return f"{normalized_episode_summary}\n\nIncluded memory items:\n- " + "\n- ".join(
                normalized_memory_contents
            )
        if normalized_episode_summary:
            return normalized_episode_summary
        if normalized_memory_contents:
            return "\n".join(normalized_memory_contents)
        return None

    @staticmethod
    def _has_text(value: object | None) -> bool:
        return isinstance(value, str) and bool(value.strip())
