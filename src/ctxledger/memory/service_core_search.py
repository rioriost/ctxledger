from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from .embeddings import EmbeddingGenerationError, EmbeddingRequest
from .helpers import embedding_dot_product, metadata_query_strings
from .types import (
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryServiceError,
)


class SearchHelperMixin:
    """Search-specific helper methods for ``MemoryService``.

    This mixin extracts narrow helpers used by lexical/semantic search without
    changing the existing ``MemoryService`` state contract. The consuming class
    is expected to provide:

    - ``self._embedding_generator``
    - ``self._memory_embedding_repository``
    - ``self._episode_repository``
    - ``self._memory_item_repository``
    """

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
        except AttributeError:
            pass
        except ValueError:
            pass

        raise MemoryServiceError(
            code=MemoryErrorCode.INVALID_REQUEST,
            feature=feature,
            message=f"{field_name} must be a valid UUID string.",
            details={"field": field_name},
        ) from None

    def _build_semantic_match_details(
        self,
        *,
        request_query: str,
        workspace_id: UUID | None,
        limit: int,
    ) -> tuple[
        tuple[MemoryEmbeddingRecord, ...],
        bool,
        str | None,
        dict[UUID, float],
        dict[UUID, tuple[str, ...]],
    ]:
        semantic_matches: tuple[MemoryEmbeddingRecord, ...] = ()
        semantic_query_generated = False
        semantic_generation_skipped_reason: str | None = None
        semantic_score_by_memory_id: dict[UUID, float] = {}
        semantic_matched_fields_by_memory_id: dict[UUID, tuple[str, ...]] = {}

        if self._embedding_generator is None or self._memory_embedding_repository is None:
            semantic_generation_skipped_reason = "embedding_search_not_configured"
            return (
                semantic_matches,
                semantic_query_generated,
                semantic_generation_skipped_reason,
                semantic_score_by_memory_id,
                semantic_matched_fields_by_memory_id,
            )

        try:
            semantic_query = self._embedding_generator.generate(
                EmbeddingRequest(text=request_query)
            )
        except EmbeddingGenerationError as exc:
            semantic_generation_skipped_reason = f"embedding_generation_failed:{exc.provider}"
            return (
                semantic_matches,
                semantic_query_generated,
                semantic_generation_skipped_reason,
                semantic_score_by_memory_id,
                semantic_matched_fields_by_memory_id,
            )

        semantic_query_generated = True
        semantic_matches = self._memory_embedding_repository.find_similar(
            semantic_query.vector,
            limit=limit,
            workspace_id=workspace_id,
        )

        if not semantic_matches:
            return (
                semantic_matches,
                semantic_query_generated,
                semantic_generation_skipped_reason,
                semantic_score_by_memory_id,
                semantic_matched_fields_by_memory_id,
            )

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

        return (
            semantic_matches,
            semantic_query_generated,
            semantic_generation_skipped_reason,
            semantic_score_by_memory_id,
            semantic_matched_fields_by_memory_id,
        )

    def _selected_continuation_target_details(
        self,
        *,
        selected_task_recall_bonus_enabled: bool,
        selected_task_recall_workflow_id: str | None,
        limit: int,
    ) -> tuple[set[UUID], UUID | None]:
        selected_task_recall_memory_ids: set[UUID] = set()
        selected_task_recall_episode_id: UUID | None = None

        if not selected_task_recall_bonus_enabled or selected_task_recall_workflow_id is None:
            return selected_task_recall_memory_ids, selected_task_recall_episode_id

        try:
            selected_task_recall_uuid = UUID(selected_task_recall_workflow_id)
        except ValueError:
            return selected_task_recall_memory_ids, selected_task_recall_episode_id

        selected_task_recall_episodes = self._episode_repository.list_by_workflow_id(
            selected_task_recall_uuid,
            limit=limit,
        )
        selected_task_recall_memory_ids = {
            candidate_memory_item.memory_id
            for selected_task_recall_episode in selected_task_recall_episodes
            for candidate_memory_item in self._memory_item_repository.list_by_episode_id(
                selected_task_recall_episode.episode_id,
                limit=limit,
            )
        }
        if selected_task_recall_episodes:
            selected_task_recall_episode_id = selected_task_recall_episodes[0].episode_id

        return selected_task_recall_memory_ids, selected_task_recall_episode_id

    def _maybe_store_embedding(self, memory_item: MemoryItemRecord) -> dict[str, Any]:
        if self._embedding_generator is None or self._memory_embedding_repository is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
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
            return {
                "embedding_persistence_status": "failed",
                "embedding_generation_skipped_reason": failure_reason,
                "embedding_generation_failure": {
                    "provider": exc.provider,
                    "message": str(exc),
                    "details": dict(exc.details),
                },
            }

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


__all__ = ["SearchHelperMixin"]
