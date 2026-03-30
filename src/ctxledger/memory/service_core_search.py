from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

from ..config import EmbeddingExecutionMode
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
    changing the existing ``MemoryService`` state contract.

    Execution-boundary note:

    - persistence-oriented AI work is the path that enriches durable stored
      records, such as generating embeddings for memory items that are already
      stored and then persisting those derived vectors
    - interactive AI work is the path that would return model output directly to
      an MCP client without first materializing that output into PostgreSQL

    The helpers in this mixin are concerned with the persistence-oriented side
    of that boundary.

    In particular:

    - when embeddings are generated for stored memory items, PostgreSQL-side
      `azure_ai` execution is a reasonable fit for large Azure deployments
    - if a future feature needs to call an AI model only to return an immediate
      client-facing response, that should remain an application-side interactive
      path rather than being forced through database-side materialization logic

    The consuming class is expected to provide:

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
        # This helper still belongs to the persistence-oriented retrieval path.
        #
        # Even when the query embedding is generated on demand, the purpose here
        # is not to produce a direct model response for the MCP client. Instead,
        # the goal is to score against already materialized embedding rows and
        # retrieve durable memory records more effectively.
        #
        # Therefore:
        #
        # - small / app-generated mode may create the query embedding in the
        #   application process
        # - large / postgres_azure_ai mode may create the query embedding inside
        #   PostgreSQL through azure_ai
        #
        # In both cases, this remains retrieval support over stored memory, not a
        # general interactive AI-response path.
        semantic_matches: tuple[MemoryEmbeddingRecord, ...] = ()
        semantic_query_generated = False
        semantic_generation_skipped_reason: str | None = None
        semantic_score_by_memory_id: dict[UUID, float] = {}
        semantic_matched_fields_by_memory_id: dict[UUID, tuple[str, ...]] = {}

        if self._memory_embedding_repository is None:
            semantic_generation_skipped_reason = "embedding_search_not_configured"
            return (
                semantic_matches,
                semantic_query_generated,
                semantic_generation_skipped_reason,
                semantic_score_by_memory_id,
                semantic_matched_fields_by_memory_id,
            )

        try:
            settings = self._load_embedding_settings()
        except Exception as exc:
            semantic_generation_skipped_reason = f"embedding_settings_unavailable:{exc}"
            return (
                semantic_matches,
                semantic_query_generated,
                semantic_generation_skipped_reason,
                semantic_score_by_memory_id,
                semantic_matched_fields_by_memory_id,
            )

        if settings.execution_mode is EmbeddingExecutionMode.POSTGRES_AZURE_AI:
            # Large Azure posture:
            #
            # - the record already exists in canonical storage
            # - the embedding is a derived retrieval-support artifact
            # - PostgreSQL-side azure_ai is therefore a reasonable execution
            #   boundary because the result is immediately persisted
            #
            # This is intentionally different from an interactive model call whose
            # result would be returned directly to the client.
            if not settings.azure_openai_embedding_deployment:
                semantic_generation_skipped_reason = "postgres_azure_ai_deployment_not_configured"
                return (
                    semantic_matches,
                    semantic_query_generated,
                    semantic_generation_skipped_reason,
                    semantic_score_by_memory_id,
                    semantic_matched_fields_by_memory_id,
                )

            semantic_query_generated = True
            semantic_matches = (
                self._memory_embedding_repository.find_similar_by_query_via_postgres_azure_ai(
                    request_query,
                    azure_openai_deployment=settings.azure_openai_embedding_deployment,
                    azure_openai_dimensions=settings.dimensions,
                    limit=limit,
                    workspace_id=workspace_id,
                )
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

            for index, embedding_match in enumerate(semantic_matches):
                semantic_score = semantic_rank_floor + (
                    (1.0 - semantic_rank_floor)
                    * (float(semantic_rank_denominator - index) / float(semantic_rank_denominator))
                )
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

        if self._embedding_generator is None:
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
        # This helper is strictly for persistence-oriented AI work.
        #
        # The input is already a stored memory item, and the purpose of the call
        # is to materialize a derived embedding record into durable storage.
        #
        # That makes PostgreSQL-side azure_ai a good fit for the large Azure
        # deployment path. By contrast, if a future feature needs to invoke an AI
        # model only to return a direct response to the MCP client, that feature
        # should use an interactive application-side path instead of this helper.
        if self._memory_embedding_repository is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
            }

        try:
            settings = self._load_embedding_settings()
        except Exception as exc:
            return {
                "embedding_persistence_status": "failed",
                "embedding_generation_skipped_reason": "embedding_settings_unavailable",
                "embedding_generation_failure": {
                    "provider": "config",
                    "message": str(exc),
                    "details": {},
                },
            }

        if not settings.enabled:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": "embedding_generation_disabled",
            }

        if settings.execution_mode is EmbeddingExecutionMode.POSTGRES_AZURE_AI:
            if not settings.azure_openai_embedding_deployment:
                return {
                    "embedding_persistence_status": "failed",
                    "embedding_generation_skipped_reason": "postgres_azure_ai_deployment_not_configured",
                    "embedding_generation_failure": {
                        "provider": "postgres_azure_ai",
                        "message": (
                            "CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required when "
                            "CTXLEDGER_EMBEDDING_EXECUTION_MODE=postgres_azure_ai"
                        ),
                        "details": {},
                    },
                }

            content_hash = hashlib.sha256(memory_item.content.encode("utf-8")).hexdigest()
            try:
                stored = self._memory_embedding_repository.create_via_postgres_azure_ai(
                    memory_id=memory_item.memory_id,
                    content=memory_item.content,
                    embedding_model=settings.model,
                    content_hash=content_hash,
                    created_at=memory_item.updated_at,
                    azure_openai_deployment=settings.azure_openai_embedding_deployment,
                    azure_openai_dimensions=settings.dimensions,
                )
            except Exception as exc:
                return {
                    "embedding_persistence_status": "failed",
                    "embedding_generation_skipped_reason": "embedding_generation_failed:postgres_azure_ai",
                    "embedding_generation_failure": {
                        "provider": "postgres_azure_ai",
                        "message": str(exc),
                        "details": {
                            "deployment": settings.azure_openai_embedding_deployment,
                            "auth_mode": settings.azure_openai_auth_mode.value,
                        },
                    },
                }

            return {
                "embedding_persistence_status": "stored",
                "embedding_generation_skipped_reason": None,
                "embedding_provider": "postgres_azure_ai",
                "embedding_model": stored.embedding_model,
                "embedding_vector_dimensions": len(stored.embedding),
                "embedding_content_hash": stored.content_hash,
            }

        if self._embedding_generator is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": "embedding_generator_not_configured",
            }

        # Small / app-generated posture:
        #
        # The application process computes the embedding and then persists the
        # resulting vector. This remains acceptable for local or smaller
        # deployment shapes where the persistence and execution boundaries are
        # intentionally simpler than the large Azure path.

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

    def _load_embedding_settings(self):
        from . import service as service_module

        return service_module.get_settings().embedding


__all__ = ["SearchHelperMixin"]
