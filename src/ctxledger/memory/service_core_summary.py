from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .protocols import (
    EpisodeRepository,
    MemoryItemRepository,
    MemorySummaryMembershipRepository,
    MemorySummaryRepository,
    WorkspaceLookupRepository,
)
from .types import (
    BuildEpisodeSummaryRequest,
    BuildEpisodeSummaryResult,
    MemoryErrorCode,
    MemoryFeature,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)


@dataclass(slots=True)
class EpisodeSummaryBuilder:
    """Narrow orchestration helper for explicit episode summary building."""

    episode_repository: EpisodeRepository
    memory_item_repository: MemoryItemRepository
    memory_summary_repository: MemorySummaryRepository
    memory_summary_membership_repository: MemorySummaryMembershipRepository
    workspace_lookup: WorkspaceLookupRepository | None = None

    def build(
        self,
        request: BuildEpisodeSummaryRequest,
        *,
        parse_uuid: Any,
        require_non_empty: Any,
        build_summary_text: Any,
        feature: MemoryFeature,
    ) -> BuildEpisodeSummaryResult:
        require_non_empty(
            request.episode_id,
            field_name="episode_id",
            feature=feature,
        )

        episode_id = parse_uuid(
            request.episode_id,
            field_name="episode_id",
            feature=feature,
        )

        episode = self.episode_repository.get_by_episode_id(episode_id)
        if episode is None:
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message="episode_id was not found.",
                details={"episode_id": str(episode_id)},
            )

        memory_items = self.memory_item_repository.list_by_episode_id(
            episode_id,
            limit=100,
        )
        if not memory_items:
            return BuildEpisodeSummaryResult(
                feature=feature,
                implemented=True,
                message="Episode summary build skipped.",
                status="skipped",
                available_in_version="0.6.0",
                summary=None,
                memberships=(),
                summary_built=False,
                skipped_reason="no_episode_memory_items",
                replaced_existing_summary=False,
                details={
                    "episode_id": str(episode_id),
                    "summary_kind": request.summary_kind,
                    "member_memory_count": 0,
                },
            )

        summary_text = build_summary_text(
            episode=episode,
            memory_items=memory_items,
        )
        if summary_text is None:
            return BuildEpisodeSummaryResult(
                feature=feature,
                implemented=True,
                message="Episode summary build skipped.",
                status="skipped",
                available_in_version="0.6.0",
                summary=None,
                memberships=(),
                summary_built=False,
                skipped_reason="summary_text_unavailable",
                replaced_existing_summary=False,
                details={
                    "episode_id": str(episode_id),
                    "summary_kind": request.summary_kind,
                    "member_memory_count": len(memory_items),
                },
            )

        existing_summaries = self.memory_summary_repository.list_by_episode_id(
            episode_id,
            limit=100,
        )
        existing_matching_summaries = tuple(
            summary
            for summary in existing_summaries
            if summary.summary_kind == request.summary_kind
        )
        replaced_existing_summary = bool(request.replace_existing and existing_matching_summaries)

        if request.replace_existing:
            for existing_summary in existing_matching_summaries:
                self.memory_summary_membership_repository.delete_by_summary_id(
                    existing_summary.memory_summary_id
                )
                self.memory_summary_repository.delete_by_summary_id(
                    existing_summary.memory_summary_id
                )

        workspace_id = (
            self.workspace_lookup.workspace_id_by_workflow_id(episode.workflow_instance_id)
            if self.workspace_lookup is not None
            else None
        )
        if workspace_id is None and memory_items[0].workspace_id is not None:
            workspace_id = memory_items[0].workspace_id
        if workspace_id is None:
            workspace_id = UUID(int=0)

        remember_path_memory_origins = sorted(
            {
                str(memory_item.metadata.get("memory_origin"))
                for memory_item in memory_items
                if isinstance(memory_item.metadata.get("memory_origin"), str)
                and str(memory_item.metadata.get("memory_origin")).strip()
            }
        )
        remember_path_promotion_fields = sorted(
            {
                str(memory_item.metadata.get("promotion_field"))
                for memory_item in memory_items
                if isinstance(memory_item.metadata.get("promotion_field"), str)
                and str(memory_item.metadata.get("promotion_field")).strip()
            }
        )
        remember_path_promotion_sources = sorted(
            {
                str(memory_item.metadata.get("promotion_source"))
                for memory_item in memory_items
                if isinstance(memory_item.metadata.get("promotion_source"), str)
                and str(memory_item.metadata.get("promotion_source")).strip()
            }
        )

        summary_metadata = {
            "builder": "minimal_episode_summary_builder",
            "build_scope": "episode",
            "source_episode_id": str(episode_id),
            "source_memory_item_count": len(memory_items),
            "build_version": "0.6.0-first-slice",
            "remember_path_memory_origins": remember_path_memory_origins,
            "remember_path_promotion_fields": remember_path_promotion_fields,
            "remember_path_promotion_sources": remember_path_promotion_sources,
            **dict(request.metadata),
        }

        now = datetime.now(timezone.utc)
        summary = self.memory_summary_repository.create(
            MemorySummaryRecord(
                memory_summary_id=uuid4(),
                workspace_id=workspace_id,
                episode_id=episode_id,
                summary_text=summary_text,
                summary_kind=request.summary_kind,
                metadata=summary_metadata,
                created_at=now,
                updated_at=now,
            )
        )

        memberships: list[MemorySummaryMembershipRecord] = []
        for index, memory_item in enumerate(memory_items, start=1):
            memberships.append(
                self.memory_summary_membership_repository.create(
                    MemorySummaryMembershipRecord(
                        memory_summary_membership_id=uuid4(),
                        memory_summary_id=summary.memory_summary_id,
                        memory_id=memory_item.memory_id,
                        membership_order=index,
                        metadata={
                            "builder": "minimal_episode_summary_builder",
                            "build_scope": "episode",
                        },
                        created_at=now,
                    )
                )
            )

        return BuildEpisodeSummaryResult(
            feature=feature,
            implemented=True,
            message="Episode summary built successfully.",
            status="built",
            available_in_version="0.6.0",
            summary=summary,
            memberships=tuple(memberships),
            summary_built=True,
            skipped_reason=None,
            replaced_existing_summary=replaced_existing_summary,
            details={
                "episode_id": str(episode_id),
                "summary_kind": request.summary_kind,
                "member_memory_count": len(memory_items),
                "member_memory_ids": [str(memory_item.memory_id) for memory_item in memory_items],
                "remember_path_memory_origins": remember_path_memory_origins,
                "remember_path_promotion_fields": remember_path_promotion_fields,
                "remember_path_promotion_sources": remember_path_promotion_sources,
                "member_memory_explainability": [
                    {
                        "memory_id": str(memory_item.memory_id),
                        "memory_type": memory_item.type,
                        "provenance": memory_item.provenance,
                        "memory_origin": memory_item.metadata.get("memory_origin"),
                        "promotion_field": memory_item.metadata.get("promotion_field"),
                        "promotion_source": memory_item.metadata.get("promotion_source"),
                        "checkpoint_id": memory_item.metadata.get("checkpoint_id"),
                        "step_name": memory_item.metadata.get("step_name"),
                        "workflow_status": memory_item.metadata.get("workflow_status"),
                        "attempt_status": memory_item.metadata.get("attempt_status"),
                    }
                    for memory_item in memory_items
                ],
            },
        )


__all__ = ["EpisodeSummaryBuilder"]
