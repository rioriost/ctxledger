from __future__ import annotations

"""Workflow-to-memory bridge helpers.

Execution-boundary note:
- This module is responsible for persistence-oriented memory creation paths.
- When workflow completion or checkpoint activity should leave behind durable
  memory state, this module can create:
  - episodes
  - memory items
  - embeddings
  - relations
- For large Azure deployments, persistence-oriented embedding generation may be
  delegated to PostgreSQL-side `azure_ai` execution.
- This module should not be treated as the home for interactive AI responses
  whose result is meant to be returned directly to an MCP client without first
  being materialized into durable storage.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from ..config import EmbeddingExecutionMode, EmbeddingProvider, get_settings
from ..memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingGenerator,
    EmbeddingRequest,
    build_embedding_generator,
)

if TYPE_CHECKING:
    from ..memory.service import (
        MemoryEmbeddingRepository,
        MemoryItemRepository,
        MemoryRelationRepository,
    )
    from .service import (
        VerifyReport,
        WorkflowAttempt,
        WorkflowCheckpoint,
        WorkflowInstance,
    )


@dataclass(slots=True, frozen=True)
class EpisodeRecord:
    episode_id: UUID
    workflow_instance_id: UUID
    summary: str
    attempt_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "recorded"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemoryItemRecord:
    memory_id: UUID
    workspace_id: UUID | None = None
    episode_id: UUID | None = None
    type: str = "episode_note"
    provenance: str = "episode"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemoryEmbeddingRecord:
    memory_embedding_id: UUID
    memory_id: UUID
    embedding_model: str
    embedding: tuple[float, ...] = ()
    content_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemoryRelationRecord:
    memory_relation_id: UUID
    source_memory_id: UUID
    target_memory_id: UUID
    relation_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class WorkflowCompletionMemoryRecordResult:
    episode: EpisodeRecord | None = None
    memory_item: MemoryItemRecord | None = None
    promoted_memory_items: tuple[MemoryItemRecord, ...] = ()
    relations: tuple[MemoryRelationRecord, ...] = ()
    summary_build: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class WorkflowCheckpointMemoryRecordResult:
    episode: EpisodeRecord | None = None
    memory_item: MemoryItemRecord | None = None
    promoted_memory_items: tuple[MemoryItemRecord, ...] = ()
    relations: tuple[MemoryRelationRecord, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AutoMemoryDuplicateCheckResult:
    should_record: bool
    skipped_reason: str | None = None


@dataclass(slots=True, frozen=True)
class CompletionPromotionCandidate:
    field_key: str
    memory_type: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


_NEAR_DUPLICATE_LOOKBACK_WINDOW = timedelta(hours=6)
_SUMMARY_SIMILARITY_THRESHOLD = 0.75
_FIELD_EXTRACTED_SIMILARITY_THRESHOLD = 0.7
_COMPLETION_SUMMARY_WEIGHT = 3.0
_CHECKPOINT_SUMMARY_WEIGHT = 1.5
_CURRENT_OBJECTIVE_WEIGHT = 1.5
_NEXT_ACTION_WEIGHT = 1.5
_VERIFY_STATUS_WEIGHT = 0.75
_WORKFLOW_STATUS_WEIGHT = 0.75
_ATTEMPT_STATUS_WEIGHT = 0.5
_FAILURE_REASON_WEIGHT = 1.0
_SUMMARY_SIMILARITY_IGNORED_TOKENS = frozenset(
    {
        "a",
        "action",
        "again",
        "and",
        "checkpoint",
        "completed",
        "completion",
        "current",
        "failure",
        "first",
        "for",
        "implemented",
        "investigated",
        "last",
        "latest",
        "line",
        "lines",
        "next",
        "objective",
        "of",
        "planned",
        "reason",
        "second",
        "status",
        "summary",
        "the",
        "verify",
        "with",
        "workflow",
    }
)
_FIELD_LABEL_TO_KEY = {
    "completion summary": "completion_summary",
    "latest checkpoint summary": "latest_checkpoint_summary",
    "checkpoint summary": "latest_checkpoint_summary",
    "current objective": "current_objective",
    "last planned next action": "next_intended_action",
    "next action": "next_intended_action",
    "verify target": "verify_target",
    "resume hint": "resume_hint",
    "blocker or risk": "blocker_or_risk",
    "failure guard": "failure_guard",
    "root cause": "root_cause",
    "recovery pattern": "recovery_pattern",
    "what remains": "what_remains",
    "verify status": "verify_status",
    "workflow status": "workflow_status",
    "attempt status": "attempt_status",
    "failure reason": "failure_reason",
}

logger = logging.getLogger(__name__)


class EpisodeRepository(Protocol):
    def create(self, episode: EpisodeRecord) -> EpisodeRecord: ...


class MemoryItemRepository(Protocol):
    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord: ...


class MemoryEmbeddingRepository(Protocol):
    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord: ...


class MemoryRelationRepository(Protocol):
    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord: ...


@dataclass(slots=True)
class WorkflowMemoryBridge:
    episode_repository: EpisodeRepository
    memory_item_repository: MemoryItemRepository
    memory_embedding_repository: MemoryEmbeddingRepository | None = None
    memory_relation_repository: MemoryRelationRepository | None = None
    summary_builder: Any | None = None
    embedding_generator: EmbeddingGenerator | None = None

    def __post_init__(self) -> None:
        if self.embedding_generator is None:
            try:
                settings = get_settings().embedding
                # Execution boundary:
                # - app_generated:
                #   build an application-side generator because the process is
                #   responsible for producing the embedding vector directly.
                # - postgres_azure_ai:
                #   do not build an application-side generator here. In that
                #   mode, this workflow-memory bridge is still persistence-
                #   oriented, but it delegates the actual embedding generation
                #   to PostgreSQL so the resulting vector is materialized as
                #   durable database state.
                if (
                    settings.enabled
                    and settings.execution_mode is not EmbeddingExecutionMode.POSTGRES_AZURE_AI
                ):
                    self.embedding_generator = build_embedding_generator(settings)
                else:
                    self.embedding_generator = None
            except Exception:
                self.embedding_generator = None

    def record_workflow_completion_memory(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        latest_checkpoint: WorkflowCheckpoint | None,
        verify_report: VerifyReport | None,
        summary: str | None,
        failure_reason: str | None,
    ) -> WorkflowCompletionMemoryRecordResult | None:
        logger.info(
            "workflow completion auto-memory evaluation started",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "workflow_status": str(getattr(workflow.status, "value", workflow.status)),
                "attempt_status": str(getattr(attempt.status, "value", attempt.status)),
                "has_latest_checkpoint": latest_checkpoint is not None,
                "has_completion_summary": self._normalize_text(summary) is not None,
                "has_failure_reason": self._normalize_text(failure_reason) is not None,
            },
        )
        should_record, skipped_reason = self._auto_memory_gating_decision(
            workflow=workflow,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
        )
        logger.info(
            "workflow completion auto-memory gating decided",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "should_record": should_record,
                "skipped_reason": skipped_reason,
            },
        )
        stage_details = self._initial_stage_details(
            should_record=should_record,
            skipped_reason=skipped_reason,
        )
        if not should_record:
            return WorkflowCompletionMemoryRecordResult(
                details={
                    "auto_memory_recorded": False,
                    "auto_memory_skipped_reason": skipped_reason,
                    "stage_details": stage_details,
                }
            )

        memory_summary = self._build_completion_summary(
            workflow=workflow,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
            summary=summary,
            failure_reason=failure_reason,
        )
        logger.info(
            "workflow completion auto-memory summary built",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "has_memory_summary": memory_summary is not None,
                "memory_summary_preview": (
                    memory_summary[:240] if memory_summary is not None else None
                ),
            },
        )
        stage_details["summary_selection"] = {
            "attempted": True,
            "status": "built" if memory_summary is not None else "skipped",
            "skipped_reason": None
            if memory_summary is not None
            else "no_completion_summary_source",
        }
        if memory_summary is None:
            return None

        episode_metadata = self._build_completion_metadata(
            workflow=workflow,
            attempt=attempt,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
            failure_reason=failure_reason,
        )
        logger.info(
            "workflow completion auto-memory metadata built",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_metadata": episode_metadata,
            },
        )

        duplicate_check = self._duplicate_closeout_memory_decision(
            workflow=workflow,
            latest_checkpoint=latest_checkpoint,
            memory_summary=memory_summary,
            episode_metadata=episode_metadata,
        )
        logger.info(
            "workflow completion auto-memory duplicate check decided",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "should_record": duplicate_check.should_record,
                "skipped_reason": duplicate_check.skipped_reason,
            },
        )
        stage_details["duplicate_check"] = {
            "attempted": True,
            "status": "passed" if duplicate_check.should_record else "skipped",
            "skipped_reason": duplicate_check.skipped_reason,
        }
        if not duplicate_check.should_record:
            return WorkflowCompletionMemoryRecordResult(
                details={
                    "auto_memory_recorded": False,
                    "auto_memory_skipped_reason": duplicate_check.skipped_reason,
                    "stage_details": stage_details,
                }
            )

        now = datetime.now(timezone.utc)
        logger.info(
            "workflow completion auto-memory creating episode",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
            },
        )
        episode = self.episode_repository.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow.workflow_instance_id,
                summary=memory_summary,
                attempt_id=attempt.attempt_id,
                metadata=episode_metadata,
                created_at=now,
                updated_at=now,
            )
        )
        stage_details["episode"] = {
            "attempted": True,
            "status": "recorded",
            "episode_id": str(episode.episode_id),
            "skipped_reason": None,
        }
        logger.info(
            "workflow completion auto-memory episode created",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
            },
        )

        logger.info(
            "workflow completion auto-memory creating primary memory item",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
            },
        )
        memory_item = self.memory_item_repository.create(
            MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=workflow.workspace_id,
                episode_id=episode.episode_id,
                type="workflow_completion_note",
                provenance="workflow_complete_auto",
                content=episode.summary,
                metadata=dict(episode.metadata),
                created_at=episode.created_at,
                updated_at=episode.updated_at,
            )
        )
        stage_details["primary_memory_item"] = {
            "attempted": True,
            "status": "recorded",
            "memory_id": str(memory_item.memory_id),
            "memory_type": memory_item.type,
            "skipped_reason": None,
        }
        logger.info(
            "workflow completion auto-memory primary memory item created",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
                "memory_id": str(memory_item.memory_id),
            },
        )

        promoted_memory_items = self._create_promoted_memory_items(
            workflow=workflow,
            attempt=attempt,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
            failure_reason=failure_reason,
            episode=episode,
            now=episode.created_at,
        )
        stage_details["promoted_memory_items"] = {
            "attempted": True,
            "status": "recorded" if promoted_memory_items else "skipped",
            "created_count": len(promoted_memory_items),
            "created_memory_ids": [str(item.memory_id) for item in promoted_memory_items],
            "created_types": [item.type for item in promoted_memory_items],
            "skipped_reason": None if promoted_memory_items else "no_promotable_completion_fields",
        }

        relation_records = self._create_supports_relations(
            workflow=workflow,
            attempt=attempt,
            primary_memory_item=memory_item,
            promoted_memory_items=promoted_memory_items,
            now=episode.created_at,
        )
        stage_details["relations"] = {
            "attempted": self.memory_relation_repository is not None,
            "status": (
                "recorded"
                if relation_records
                else (
                    "skipped" if self.memory_relation_repository is not None else "not_configured"
                )
            ),
            "created_count": len(relation_records),
            "created_relation_ids": [
                str(relation.memory_relation_id) for relation in relation_records
            ],
            "relation_type_counts": self._relation_type_counts(relation_records),
            "skipped_reason": self._relation_skipped_reason(
                relation_records=relation_records,
                promoted_memory_items=promoted_memory_items,
            ),
        }

        embedding_details = self._maybe_store_embedding(memory_item)
        logger.info(
            "workflow completion auto-memory embedding persistence finished",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
                "memory_id": str(memory_item.memory_id),
                "embedding_details": embedding_details,
            },
        )
        stage_details["embedding"] = {
            "attempted": True,
            "status": embedding_details.get("embedding_persistence_status"),
            "skipped_reason": embedding_details.get("embedding_generation_skipped_reason"),
            "provider": embedding_details.get("embedding_provider"),
            "model": embedding_details.get("embedding_model"),
        }

        summary_build = self._maybe_build_completion_summary(
            workflow=workflow,
            episode=episode,
            memory_item=memory_item,
            promoted_memory_items=tuple(promoted_memory_items),
            latest_checkpoint=latest_checkpoint,
        )
        stage_details["summary_build"] = (
            dict(summary_build)
            if summary_build is not None
            else {
                "summary_build_attempted": False,
                "summary_build_succeeded": False,
                "summary_build_requested": False,
                "summary_build_status": None,
                "summary_build_skipped_reason": "summary_builder_not_configured",
            }
        )

        completion_metadata = self._merge_summary_build_outcome_metadata(
            episode.metadata,
            summary_build,
        )
        if completion_metadata != episode.metadata:
            episode = EpisodeRecord(
                episode_id=episode.episode_id,
                workflow_instance_id=episode.workflow_instance_id,
                summary=episode.summary,
                attempt_id=episode.attempt_id,
                metadata=completion_metadata,
                status=episode.status,
                created_at=episode.created_at,
                updated_at=episode.updated_at,
            )
        if completion_metadata != memory_item.metadata:
            memory_item = MemoryItemRecord(
                memory_id=memory_item.memory_id,
                workspace_id=memory_item.workspace_id,
                episode_id=memory_item.episode_id,
                type=memory_item.type,
                provenance=memory_item.provenance,
                content=memory_item.content,
                metadata=completion_metadata,
                created_at=memory_item.created_at,
                updated_at=memory_item.updated_at,
            )

        details = {
            "auto_memory_recorded": True,
            "episode_id": str(episode.episode_id),
            "memory_item_id": str(memory_item.memory_id),
            "promoted_memory_item_ids": [str(item.memory_id) for item in promoted_memory_items],
            "promoted_memory_item_count": len(promoted_memory_items),
            "memory_relation_count": len(relation_records),
            "stage_details": stage_details,
            **embedding_details,
            **({"summary_build": summary_build} if summary_build is not None else {}),
        }

        return WorkflowCompletionMemoryRecordResult(
            episode=episode,
            memory_item=memory_item,
            promoted_memory_items=tuple(promoted_memory_items),
            relations=tuple(relation_records),
            summary_build=summary_build,
            details=details,
        )

    def record_checkpoint_memory(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        checkpoint: WorkflowCheckpoint,
        verify_report: VerifyReport | None,
    ) -> WorkflowCheckpointMemoryRecordResult | None:
        logger.info(
            "workflow checkpoint auto-memory evaluation started",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "checkpoint_id": str(checkpoint.checkpoint_id),
                "step_name": checkpoint.step_name,
                "has_checkpoint_summary": self._normalize_text(checkpoint.summary) is not None,
            },
        )
        should_record, skipped_reason = self._checkpoint_auto_memory_gating_decision(
            checkpoint=checkpoint,
            verify_report=verify_report,
        )
        stage_details = self._initial_stage_details(
            should_record=should_record,
            skipped_reason=skipped_reason,
        )
        if not should_record:
            return WorkflowCheckpointMemoryRecordResult(
                details={
                    "auto_memory_recorded": False,
                    "auto_memory_skipped_reason": skipped_reason,
                    "stage_details": stage_details,
                }
            )

        memory_summary = self._build_checkpoint_summary(
            workflow=workflow,
            checkpoint=checkpoint,
            verify_report=verify_report,
        )
        stage_details["summary_selection"] = {
            "attempted": True,
            "status": "built" if memory_summary is not None else "skipped",
            "skipped_reason": None if memory_summary is not None else "no_checkpoint_memory_source",
        }
        if memory_summary is None:
            return None

        episode_metadata = self._build_checkpoint_metadata(
            workflow=workflow,
            attempt=attempt,
            checkpoint=checkpoint,
            verify_report=verify_report,
        )

        duplicate_check = self._duplicate_checkpoint_memory_decision(
            workflow=workflow,
            checkpoint=checkpoint,
            memory_summary=memory_summary,
            episode_metadata=episode_metadata,
        )
        stage_details["duplicate_check"] = {
            "attempted": True,
            "status": "passed" if duplicate_check.should_record else "skipped",
            "skipped_reason": duplicate_check.skipped_reason,
        }
        if not duplicate_check.should_record:
            return WorkflowCheckpointMemoryRecordResult(
                details={
                    "auto_memory_recorded": False,
                    "auto_memory_skipped_reason": duplicate_check.skipped_reason,
                    "stage_details": stage_details,
                }
            )

        now = datetime.now(timezone.utc)
        episode = self.episode_repository.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow.workflow_instance_id,
                summary=memory_summary,
                attempt_id=attempt.attempt_id,
                metadata=episode_metadata,
                created_at=now,
                updated_at=now,
            )
        )
        stage_details["episode"] = {
            "attempted": True,
            "status": "recorded",
            "episode_id": str(episode.episode_id),
            "skipped_reason": None,
        }

        memory_item = self.memory_item_repository.create(
            MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=workflow.workspace_id,
                episode_id=episode.episode_id,
                type="workflow_checkpoint_note",
                provenance="workflow_checkpoint_auto",
                content=episode.summary,
                metadata=dict(episode.metadata),
                created_at=episode.created_at,
                updated_at=episode.updated_at,
            )
        )
        stage_details["primary_memory_item"] = {
            "attempted": True,
            "status": "recorded",
            "memory_id": str(memory_item.memory_id),
            "memory_type": memory_item.type,
            "skipped_reason": None,
        }

        promoted_memory_items = self._create_checkpoint_promoted_memory_items(
            workflow=workflow,
            attempt=attempt,
            checkpoint=checkpoint,
            verify_report=verify_report,
            episode=episode,
            now=episode.created_at,
        )
        stage_details["promoted_memory_items"] = {
            "attempted": True,
            "status": "recorded" if promoted_memory_items else "skipped",
            "created_count": len(promoted_memory_items),
            "created_memory_ids": [str(item.memory_id) for item in promoted_memory_items],
            "created_types": [item.type for item in promoted_memory_items],
            "skipped_reason": None if promoted_memory_items else "no_promotable_checkpoint_fields",
        }

        relation_records = self._create_supports_relations(
            workflow=workflow,
            attempt=attempt,
            primary_memory_item=memory_item,
            promoted_memory_items=promoted_memory_items,
            now=episode.created_at,
        )
        stage_details["relations"] = {
            "attempted": self.memory_relation_repository is not None,
            "status": (
                "recorded"
                if relation_records
                else (
                    "skipped" if self.memory_relation_repository is not None else "not_configured"
                )
            ),
            "created_count": len(relation_records),
            "created_relation_ids": [
                str(relation.memory_relation_id) for relation in relation_records
            ],
            "relation_type_counts": self._relation_type_counts(relation_records),
            "skipped_reason": self._relation_skipped_reason(
                relation_records=relation_records,
                promoted_memory_items=promoted_memory_items,
            ),
        }

        embedding_details = self._maybe_store_embedding(memory_item)
        stage_details["embedding"] = {
            "attempted": True,
            "status": embedding_details.get("embedding_persistence_status"),
            "skipped_reason": embedding_details.get("embedding_generation_skipped_reason"),
            "provider": embedding_details.get("embedding_provider"),
            "model": embedding_details.get("embedding_model"),
        }

        details = {
            "auto_memory_recorded": True,
            "episode_id": str(episode.episode_id),
            "memory_item_id": str(memory_item.memory_id),
            "promoted_memory_item_ids": [str(item.memory_id) for item in promoted_memory_items],
            "promoted_memory_item_count": len(promoted_memory_items),
            "memory_relation_count": len(relation_records),
            "stage_details": stage_details,
            **embedding_details,
        }

        return WorkflowCheckpointMemoryRecordResult(
            episode=episode,
            memory_item=memory_item,
            promoted_memory_items=tuple(promoted_memory_items),
            relations=tuple(relation_records),
            details=details,
        )

    def _initial_stage_details(
        self,
        *,
        should_record: bool,
        skipped_reason: str,
    ) -> dict[str, Any]:
        return {
            "gating": {
                "attempted": True,
                "status": "passed" if should_record else "skipped",
                "skipped_reason": None if should_record else skipped_reason,
            }
        }

    def _auto_memory_gating_decision(
        self,
        *,
        workflow: WorkflowInstance,
        latest_checkpoint: WorkflowCheckpoint | None,
        verify_report: VerifyReport | None,
    ) -> tuple[bool, str]:
        if latest_checkpoint is None:
            return False, "no_completion_summary_source"

        workflow_status = str(getattr(workflow.status, "value", workflow.status))
        if workflow_status in {"failed", "cancelled"}:
            return True, ""

        verify_status = self._verify_status_value(verify_report)
        if verify_status == "failed":
            return True, ""

        checkpoint_payload = latest_checkpoint.checkpoint_json
        if not isinstance(checkpoint_payload, dict):
            return False, "low_signal_checkpoint_closeout"

        if checkpoint_payload.get("auto_memory") is True:
            return True, ""

        heuristic_signals = (
            "next_intended_action",
            "current_objective",
            "decision",
            "risk",
            "blocker",
            "open_question",
        )
        has_signal = any(
            isinstance(checkpoint_payload.get(key), str) and checkpoint_payload.get(key, "").strip()
            for key in heuristic_signals
        )
        if has_signal:
            return True, ""

        return False, "low_signal_checkpoint_closeout"

    def _checkpoint_auto_memory_gating_decision(
        self,
        *,
        checkpoint: WorkflowCheckpoint,
        verify_report: VerifyReport | None,
    ) -> tuple[bool, str]:
        checkpoint_payload = checkpoint.checkpoint_json
        if not isinstance(checkpoint_payload, dict):
            return False, "low_signal_checkpoint_memory"

        if self._normalize_text(checkpoint.summary) is not None:
            return True, ""

        heuristic_signals = (
            "current_objective",
            "next_intended_action",
            "root_cause",
            "recovery_pattern",
            "what_remains",
            "decision",
            "risk",
            "blocker",
            "open_question",
        )
        has_signal = any(
            isinstance(checkpoint_payload.get(key), str) and checkpoint_payload.get(key, "").strip()
            for key in heuristic_signals
        )
        if has_signal:
            return True, ""

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            return True, ""

        return False, "low_signal_checkpoint_memory"

    def _duplicate_checkpoint_memory_decision(
        self,
        *,
        workflow: WorkflowInstance,
        checkpoint: WorkflowCheckpoint,
        memory_summary: str,
        episode_metadata: dict[str, Any],
    ) -> AutoMemoryDuplicateCheckResult:
        step_name = checkpoint.step_name.strip()
        normalized_summary = self._normalize_text(memory_summary)
        current_fields = self._extract_closeout_fields(
            memory_summary,
            fallback_metadata=episode_metadata,
        )

        recent_checkpoint_memory = self._recent_checkpoint_memory(workflow)
        for prior_episode in recent_checkpoint_memory:
            prior_summary = self._normalize_text(prior_episode.summary)
            if normalized_summary is not None and prior_summary == normalized_summary:
                return AutoMemoryDuplicateCheckResult(
                    should_record=False,
                    skipped_reason="duplicate_checkpoint_auto_memory",
                )

            if not self._is_within_near_duplicate_window(prior_episode):
                continue

            prior_step_name = prior_episode.metadata.get("step_name")
            if not (
                isinstance(prior_step_name, str)
                and prior_step_name.strip() == step_name
                and prior_episode.metadata.get("memory_origin") == "workflow_checkpoint_auto"
            ):
                continue

            prior_fields = self._extract_closeout_fields(
                prior_episode.summary,
                fallback_metadata=prior_episode.metadata,
            )
            metadata_matches = self._metadata_aware_closeout_match(
                current_fields=current_fields,
                prior_fields=prior_fields,
            )
            field_similarity = self._weighted_closeout_similarity(
                current_fields=current_fields,
                prior_fields=prior_fields,
            )
            summary_similarity = self._summary_token_similarity(
                current_fields.get("latest_checkpoint_summary") or memory_summary,
                prior_fields.get("latest_checkpoint_summary") or prior_episode.summary,
            )

            if metadata_matches and (
                field_similarity >= _FIELD_EXTRACTED_SIMILARITY_THRESHOLD
                or summary_similarity is None
                or summary_similarity >= _SUMMARY_SIMILARITY_THRESHOLD
            ):
                return AutoMemoryDuplicateCheckResult(
                    should_record=False,
                    skipped_reason="near_duplicate_checkpoint_memory",
                )

        return AutoMemoryDuplicateCheckResult(should_record=True)

    def _duplicate_closeout_memory_decision(
        self,
        *,
        workflow: WorkflowInstance,
        latest_checkpoint: WorkflowCheckpoint | None,
        memory_summary: str,
        episode_metadata: dict[str, Any],
    ) -> AutoMemoryDuplicateCheckResult:
        if latest_checkpoint is None:
            return AutoMemoryDuplicateCheckResult(should_record=True)

        step_name = latest_checkpoint.step_name.strip()
        normalized_summary = self._normalize_text(memory_summary)
        current_fields = self._extract_closeout_fields(
            memory_summary,
            fallback_metadata=episode_metadata,
        )

        recent_auto_memory = self._recent_workflow_completion_memory(workflow)
        for prior_episode in recent_auto_memory:
            prior_summary = self._normalize_text(prior_episode.summary)
            if normalized_summary is not None and prior_summary == normalized_summary:
                return AutoMemoryDuplicateCheckResult(
                    should_record=False,
                    skipped_reason="duplicate_closeout_auto_memory",
                )

            if not self._is_within_near_duplicate_window(prior_episode):
                continue

            prior_step_name = prior_episode.metadata.get("step_name")
            if not (
                isinstance(prior_step_name, str)
                and prior_step_name.strip() == step_name
                and prior_episode.metadata.get("memory_origin") == "workflow_complete_auto"
            ):
                continue

            prior_fields = self._extract_closeout_fields(
                prior_episode.summary,
                fallback_metadata=prior_episode.metadata,
            )
            metadata_matches = self._metadata_aware_closeout_match(
                current_fields=current_fields,
                prior_fields=prior_fields,
            )
            field_similarity = self._weighted_closeout_similarity(
                current_fields=current_fields,
                prior_fields=prior_fields,
            )
            summary_similarity = self._summary_token_similarity(
                current_fields.get("completion_summary") or memory_summary,
                prior_fields.get("completion_summary") or prior_episode.summary,
            )

            if metadata_matches and (
                field_similarity >= _FIELD_EXTRACTED_SIMILARITY_THRESHOLD
                or summary_similarity is None
                or summary_similarity >= _SUMMARY_SIMILARITY_THRESHOLD
            ):
                return AutoMemoryDuplicateCheckResult(
                    should_record=False,
                    skipped_reason="near_duplicate_checkpoint_closeout",
                )

        return AutoMemoryDuplicateCheckResult(should_record=True)

    def _recent_workflow_completion_memory(
        self,
        workflow: WorkflowInstance,
    ) -> tuple[EpisodeRecord, ...]:
        if not hasattr(self.episode_repository, "list_by_workflow_id"):
            return ()

        list_by_workflow_id = getattr(self.episode_repository, "list_by_workflow_id", None)
        if not callable(list_by_workflow_id):
            return ()

        try:
            episodes = list_by_workflow_id(
                workflow.workflow_instance_id,
                limit=5,
            )
        except Exception:
            return ()

        if not isinstance(episodes, tuple):
            return ()

        return tuple(
            episode
            for episode in episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        )

    def _recent_checkpoint_memory(
        self,
        workflow: WorkflowInstance,
    ) -> tuple[EpisodeRecord, ...]:
        if not hasattr(self.episode_repository, "list_by_workflow_id"):
            return ()

        list_by_workflow_id = getattr(self.episode_repository, "list_by_workflow_id", None)
        if not callable(list_by_workflow_id):
            return ()

        try:
            episodes = list_by_workflow_id(
                workflow.workflow_instance_id,
                limit=5,
            )
        except Exception:
            return ()

        if not isinstance(episodes, tuple):
            return ()

        return tuple(
            episode
            for episode in episodes
            if episode.metadata.get("memory_origin") == "workflow_checkpoint_auto"
        )

    def _is_within_near_duplicate_window(self, episode: EpisodeRecord) -> bool:
        now = datetime.now(timezone.utc)
        return (now - episode.created_at) <= _NEAR_DUPLICATE_LOOKBACK_WINDOW

    def _summary_token_similarity(
        self,
        left: str | None,
        right: str | None,
    ) -> float | None:
        left_tokens = self._normalized_token_set(left)
        right_tokens = self._normalized_token_set(right)
        if left_tokens is None or right_tokens is None:
            return None
        if not left_tokens or not right_tokens:
            return None

        meaningful_left_tokens = left_tokens - _SUMMARY_SIMILARITY_IGNORED_TOKENS
        meaningful_right_tokens = right_tokens - _SUMMARY_SIMILARITY_IGNORED_TOKENS

        comparison_left_tokens = meaningful_left_tokens if meaningful_left_tokens else left_tokens
        comparison_right_tokens = (
            meaningful_right_tokens if meaningful_right_tokens else right_tokens
        )

        union = comparison_left_tokens | comparison_right_tokens
        if not union:
            return None

        intersection = comparison_left_tokens & comparison_right_tokens
        return len(intersection) / len(union)

    def _extract_closeout_fields(
        self,
        summary: str | None,
        *,
        fallback_metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        extracted: dict[str, str] = {}
        normalized_summary = self._normalize_text(summary)
        if normalized_summary is not None:
            for raw_line in normalized_summary.splitlines():
                line = raw_line.strip()
                if not line or ":" not in line:
                    continue
                label, value = line.split(":", 1)
                key = _FIELD_LABEL_TO_KEY.get(label.strip().lower())
                normalized_value = self._normalize_text(value)
                if key is not None and normalized_value is not None:
                    extracted[key] = normalized_value

        if fallback_metadata is not None:
            for key in (
                "current_objective",
                "next_intended_action",
                "verify_target",
                "resume_hint",
                "blocker_or_risk",
                "failure_guard",
                "root_cause",
                "recovery_pattern",
                "what_remains",
                "verify_status",
                "workflow_status",
                "attempt_status",
                "failure_reason",
            ):
                normalized_value = self._normalize_text(fallback_metadata.get(key))
                if normalized_value is not None:
                    extracted.setdefault(key, normalized_value)

        return extracted

    def _metadata_aware_closeout_match(
        self,
        *,
        current_fields: dict[str, str],
        prior_fields: dict[str, str],
    ) -> bool:
        return (
            current_fields.get("current_objective") == prior_fields.get("current_objective")
            and current_fields.get("next_intended_action")
            == prior_fields.get("next_intended_action")
            and current_fields.get("root_cause") == prior_fields.get("root_cause")
            and current_fields.get("recovery_pattern") == prior_fields.get("recovery_pattern")
            and current_fields.get("what_remains") == prior_fields.get("what_remains")
            and current_fields.get("verify_status") == prior_fields.get("verify_status")
            and current_fields.get("workflow_status") == prior_fields.get("workflow_status")
            and current_fields.get("attempt_status") == prior_fields.get("attempt_status")
            and current_fields.get("failure_reason") == prior_fields.get("failure_reason")
        )

    def _weighted_closeout_similarity(
        self,
        *,
        current_fields: dict[str, str],
        prior_fields: dict[str, str],
    ) -> float:
        weighted_score = 0.0
        total_weight = 0.0

        for key, weight in (
            ("completion_summary", _COMPLETION_SUMMARY_WEIGHT),
            ("latest_checkpoint_summary", _CHECKPOINT_SUMMARY_WEIGHT),
            ("current_objective", _CURRENT_OBJECTIVE_WEIGHT),
            ("next_intended_action", _NEXT_ACTION_WEIGHT),
            ("root_cause", _FAILURE_REASON_WEIGHT),
            ("recovery_pattern", _NEXT_ACTION_WEIGHT),
            ("what_remains", _CHECKPOINT_SUMMARY_WEIGHT),
            ("verify_status", _VERIFY_STATUS_WEIGHT),
            ("workflow_status", _WORKFLOW_STATUS_WEIGHT),
            ("attempt_status", _ATTEMPT_STATUS_WEIGHT),
            ("failure_reason", _FAILURE_REASON_WEIGHT),
        ):
            current_value = current_fields.get(key)
            prior_value = prior_fields.get(key)
            if current_value is None or prior_value is None:
                continue

            total_weight += weight
            similarity = self._summary_token_similarity(current_value, prior_value)
            if similarity is None:
                similarity = 1.0 if current_value == prior_value else 0.0
            weighted_score += similarity * weight

        if total_weight == 0.0:
            return 0.0

        return weighted_score / total_weight

    def _normalized_token_set(self, value: str | None) -> set[str] | None:
        normalized = self._normalize_text(value)
        if normalized is None:
            return None

        translation_table = str.maketrans(
            {
                ".": " ",
                ",": " ",
                ":": " ",
                ";": " ",
                "!": " ",
                "?": " ",
                "(": " ",
                ")": " ",
                "[": " ",
                "]": " ",
                "{": " ",
                "}": " ",
                "`": " ",
                "'": " ",
                '"': " ",
                "/": " ",
                "\\": " ",
                "-": " ",
                "_": " ",
            }
        )
        tokenized = normalized.lower().translate(translation_table)
        return {token for token in tokenized.split() if token}

    def _build_completion_summary(
        self,
        *,
        workflow: WorkflowInstance,
        latest_checkpoint: WorkflowCheckpoint | None,
        verify_report: VerifyReport | None,
        summary: str | None,
        failure_reason: str | None,
    ) -> str | None:
        summary_text = self._normalize_text(summary)
        checkpoint_summary = (
            self._normalize_text(latest_checkpoint.summary)
            if latest_checkpoint is not None
            else None
        )
        current_objective = self._checkpoint_current_objective(latest_checkpoint)
        next_intended_action = self._checkpoint_next_intended_action(latest_checkpoint)

        if (
            summary_text is None
            and checkpoint_summary is None
            and current_objective is None
            and next_intended_action is None
        ):
            return None

        lines: list[str] = [f"Workflow completed with status `{workflow.status.value}`."]

        if summary_text is not None:
            lines.append(f"Completion summary: {summary_text}")
        elif checkpoint_summary is not None:
            lines.append(f"Latest checkpoint summary: {checkpoint_summary}")

        if (
            summary_text is not None
            and checkpoint_summary is not None
            and summary_text != checkpoint_summary
        ):
            lines.append(f"Latest checkpoint summary: {checkpoint_summary}")

        if current_objective is not None:
            lines.append(f"Current objective: {current_objective}")

        if next_intended_action is not None:
            lines.append(f"Last planned next action: {next_intended_action}")

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            lines.append(f"Verify status: {verify_status}")

        lines.append(f"Workflow status: {workflow.status.value}")

        workflow_status = str(getattr(workflow.status, "value", workflow.status))
        if failure_reason is not None and workflow_status in {"failed", "cancelled"}:
            lines.append(f"Failure reason: {failure_reason}")

        return "\n".join(lines)

    def _build_completion_metadata(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        latest_checkpoint: WorkflowCheckpoint | None,
        verify_report: VerifyReport | None,
        failure_reason: str | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "auto_generated": True,
            "memory_origin": "workflow_complete_auto",
            "workflow_status": workflow.status.value,
            "attempt_status": attempt.status.value,
            "attempt_number": attempt.attempt_number,
        }

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            metadata["verify_status"] = verify_status

        if latest_checkpoint is not None:
            metadata["step_name"] = latest_checkpoint.step_name
            current_objective = self._checkpoint_current_objective(latest_checkpoint)
            if current_objective is not None:
                metadata["current_objective"] = current_objective
            next_intended_action = self._checkpoint_next_intended_action(latest_checkpoint)
            if next_intended_action is not None:
                metadata["next_intended_action"] = next_intended_action
            root_cause = self._checkpoint_root_cause(latest_checkpoint)
            if root_cause is not None:
                metadata["root_cause"] = root_cause
            recovery_pattern = self._checkpoint_recovery_pattern(latest_checkpoint)
            if recovery_pattern is not None:
                metadata["recovery_pattern"] = recovery_pattern

        if failure_reason is not None:
            metadata["failure_reason"] = failure_reason

        return metadata

    def _build_checkpoint_summary(
        self,
        *,
        workflow: WorkflowInstance,
        checkpoint: WorkflowCheckpoint,
        verify_report: VerifyReport | None,
    ) -> str | None:
        checkpoint_summary = self._normalize_text(checkpoint.summary)
        current_objective = self._checkpoint_current_objective(checkpoint)
        next_intended_action = self._checkpoint_next_intended_action(checkpoint)
        verify_target = self._checkpoint_verify_target(checkpoint)
        resume_hint = self._checkpoint_resume_hint(checkpoint)
        blocker_or_risk = self._checkpoint_blocker_or_risk(checkpoint)
        failure_guard = self._checkpoint_failure_guard(checkpoint)
        root_cause = self._checkpoint_root_cause(checkpoint)
        recovery_pattern = self._checkpoint_recovery_pattern(checkpoint)
        what_remains = self._checkpoint_what_remains(checkpoint)
        verify_status = self._verify_status_value(verify_report)

        if (
            checkpoint_summary is None
            and current_objective is None
            and next_intended_action is None
            and verify_target is None
            and resume_hint is None
            and blocker_or_risk is None
            and failure_guard is None
            and root_cause is None
            and recovery_pattern is None
            and what_remains is None
            and verify_status is None
        ):
            return None

        lines = [f"Checkpoint recorded for workflow status `{workflow.status.value}`."]
        if checkpoint_summary is not None:
            lines.append(f"Checkpoint summary: {checkpoint_summary}")
        if current_objective is not None:
            lines.append(f"Current objective: {current_objective}")
        if next_intended_action is not None:
            lines.append(f"Next action: {next_intended_action}")
        if verify_target is not None:
            lines.append(f"Verify target: {verify_target}")
        if resume_hint is not None:
            lines.append(f"Resume hint: {resume_hint}")
        if blocker_or_risk is not None:
            lines.append(f"Blocker or risk: {blocker_or_risk}")
        if failure_guard is not None:
            lines.append(f"Failure guard: {failure_guard}")
        if root_cause is not None:
            lines.append(f"Root cause: {root_cause}")
        if recovery_pattern is not None:
            lines.append(f"Recovery pattern: {recovery_pattern}")
        if what_remains is not None:
            lines.append(f"What remains: {what_remains}")
        if verify_status is not None:
            lines.append(f"Verify status: {verify_status}")

        return "\n".join(lines)

    def _build_checkpoint_metadata(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        checkpoint: WorkflowCheckpoint,
        verify_report: VerifyReport | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "auto_generated": True,
            "memory_origin": "workflow_checkpoint_auto",
            "workflow_status": workflow.status.value,
            "attempt_status": attempt.status.value,
            "attempt_number": attempt.attempt_number,
            "step_name": checkpoint.step_name,
            "checkpoint_id": str(checkpoint.checkpoint_id),
        }

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            metadata["verify_status"] = verify_status

        current_objective = self._checkpoint_current_objective(checkpoint)
        if current_objective is not None:
            metadata["current_objective"] = current_objective

        next_intended_action = self._checkpoint_next_intended_action(checkpoint)
        if next_intended_action is not None:
            metadata["next_intended_action"] = next_intended_action

        verify_target = self._checkpoint_verify_target(checkpoint)
        if verify_target is not None:
            metadata["verify_target"] = verify_target

        resume_hint = self._checkpoint_resume_hint(checkpoint)
        if resume_hint is not None:
            metadata["resume_hint"] = resume_hint

        blocker_or_risk = self._checkpoint_blocker_or_risk(checkpoint)
        if blocker_or_risk is not None:
            metadata["blocker_or_risk"] = blocker_or_risk

        failure_guard = self._checkpoint_failure_guard(checkpoint)
        if failure_guard is not None:
            metadata["failure_guard"] = failure_guard

        root_cause = self._checkpoint_root_cause(checkpoint)
        if root_cause is not None:
            metadata["root_cause"] = root_cause

        recovery_pattern = self._checkpoint_recovery_pattern(checkpoint)
        if recovery_pattern is not None:
            metadata["recovery_pattern"] = recovery_pattern

        what_remains = self._checkpoint_what_remains(checkpoint)
        if what_remains is not None:
            metadata["what_remains"] = what_remains

        return metadata

    def _collect_promotion_candidates(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        latest_checkpoint: WorkflowCheckpoint | None,
        verify_report: VerifyReport | None,
        failure_reason: str | None,
    ) -> tuple[CompletionPromotionCandidate, ...]:
        candidates: list[CompletionPromotionCandidate] = []

        current_objective = self._checkpoint_current_objective(latest_checkpoint)
        if current_objective is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="current_objective",
                    memory_type="workflow_objective",
                    content=current_objective,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.current_objective",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        next_intended_action = self._checkpoint_next_intended_action(latest_checkpoint)
        if next_intended_action is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="next_intended_action",
                    memory_type="workflow_next_action",
                    content=next_intended_action,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.next_intended_action",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        verify_target = self._checkpoint_verify_target(latest_checkpoint)
        if verify_target is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="verify_target",
                    memory_type="workflow_verify_target",
                    content=verify_target,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.verify_target",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        resume_hint = self._checkpoint_resume_hint(latest_checkpoint)
        if resume_hint is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="resume_hint",
                    memory_type="workflow_resume_hint",
                    content=resume_hint,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.resume_hint",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        blocker_or_risk = self._checkpoint_blocker_or_risk(latest_checkpoint)
        if blocker_or_risk is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="blocker_or_risk",
                    memory_type="workflow_blocker_or_risk",
                    content=blocker_or_risk,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.blocker_or_risk",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        failure_guard = self._checkpoint_failure_guard(latest_checkpoint)
        if failure_guard is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="failure_guard",
                    memory_type="workflow_failure_guard",
                    content=failure_guard,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.failure_guard",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="verify_status",
                    memory_type="workflow_verification_outcome",
                    content=f"Workflow verification outcome: {verify_status}",
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "verify_report.status",
                        "verify_status": verify_status,
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        root_cause = self._checkpoint_root_cause(latest_checkpoint)
        if root_cause is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="root_cause",
                    memory_type="workflow_root_cause",
                    content=root_cause,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.root_cause",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        recovery_pattern = self._checkpoint_recovery_pattern(latest_checkpoint)
        if recovery_pattern is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="recovery_pattern",
                    memory_type="workflow_recovery_pattern",
                    content=recovery_pattern,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "latest_checkpoint.recovery_pattern",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        normalized_failure_reason = self._normalize_text(failure_reason)
        if normalized_failure_reason is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="failure_reason",
                    memory_type="workflow_failure_reason",
                    content=normalized_failure_reason,
                    metadata={
                        "memory_origin": "workflow_complete_auto",
                        "promotion_source": "workflow_complete.failure_reason",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        return tuple(candidates)

    def _collect_checkpoint_promotion_candidates(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        checkpoint: WorkflowCheckpoint,
        verify_report: VerifyReport | None,
    ) -> tuple[CompletionPromotionCandidate, ...]:
        candidates: list[CompletionPromotionCandidate] = []

        current_objective = self._checkpoint_current_objective(checkpoint)
        if current_objective is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="current_objective",
                    memory_type="workflow_objective",
                    content=current_objective,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.current_objective",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        next_intended_action = self._checkpoint_next_intended_action(checkpoint)
        if next_intended_action is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="next_intended_action",
                    memory_type="workflow_next_action",
                    content=next_intended_action,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.next_intended_action",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        verify_target = self._checkpoint_verify_target(checkpoint)
        if verify_target is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="verify_target",
                    memory_type="workflow_verify_target",
                    content=verify_target,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.verify_target",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        resume_hint = self._checkpoint_resume_hint(checkpoint)
        if resume_hint is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="resume_hint",
                    memory_type="workflow_resume_hint",
                    content=resume_hint,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.resume_hint",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        blocker_or_risk = self._checkpoint_blocker_or_risk(checkpoint)
        if blocker_or_risk is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="blocker_or_risk",
                    memory_type="workflow_blocker_or_risk",
                    content=blocker_or_risk,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.blocker_or_risk",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        failure_guard = self._checkpoint_failure_guard(checkpoint)
        if failure_guard is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="failure_guard",
                    memory_type="workflow_failure_guard",
                    content=failure_guard,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.failure_guard",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        root_cause = self._checkpoint_root_cause(checkpoint)
        if root_cause is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="root_cause",
                    memory_type="workflow_root_cause",
                    content=root_cause,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.root_cause",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        recovery_pattern = self._checkpoint_recovery_pattern(checkpoint)
        if recovery_pattern is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="recovery_pattern",
                    memory_type="workflow_recovery_pattern",
                    content=recovery_pattern,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.recovery_pattern",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        what_remains = self._checkpoint_what_remains(checkpoint)
        if what_remains is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="what_remains",
                    memory_type="workflow_what_remains",
                    content=what_remains,
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "checkpoint.what_remains",
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            candidates.append(
                CompletionPromotionCandidate(
                    field_key="verify_status",
                    memory_type="workflow_verification_outcome",
                    content=f"Workflow verification outcome: {verify_status}",
                    metadata={
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_source": "verify_report.status",
                        "verify_status": verify_status,
                        "workflow_status": workflow.status.value,
                        "attempt_status": attempt.status.value,
                    },
                )
            )

        return tuple(candidates)

    def _create_promoted_memory_items(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        latest_checkpoint: WorkflowCheckpoint | None,
        verify_report: VerifyReport | None,
        failure_reason: str | None,
        episode: EpisodeRecord,
        now: datetime,
    ) -> tuple[MemoryItemRecord, ...]:
        created_items: list[MemoryItemRecord] = []
        for candidate in self._collect_promotion_candidates(
            workflow=workflow,
            attempt=attempt,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
            failure_reason=failure_reason,
        ):
            memory_item = self.memory_item_repository.create(
                MemoryItemRecord(
                    memory_id=uuid4(),
                    workspace_id=workflow.workspace_id,
                    episode_id=episode.episode_id,
                    type=candidate.memory_type,
                    provenance="workflow_complete_auto",
                    content=candidate.content,
                    metadata={
                        **dict(episode.metadata),
                        **dict(candidate.metadata),
                        "promotion_field": candidate.field_key,
                    },
                    created_at=now,
                    updated_at=now,
                )
            )
            logger.info(
                "workflow completion auto-memory promoted memory item created",
                extra={
                    "workflow_instance_id": str(workflow.workflow_instance_id),
                    "attempt_id": str(attempt.attempt_id),
                    "episode_id": str(episode.episode_id),
                    "memory_id": str(memory_item.memory_id),
                    "memory_type": memory_item.type,
                    "promotion_field": candidate.field_key,
                },
            )
            created_items.append(memory_item)
        return tuple(created_items)

    def _create_checkpoint_promoted_memory_items(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        checkpoint: WorkflowCheckpoint,
        verify_report: VerifyReport | None,
        episode: EpisodeRecord,
        now: datetime,
    ) -> tuple[MemoryItemRecord, ...]:
        created_items: list[MemoryItemRecord] = []
        for candidate in self._collect_checkpoint_promotion_candidates(
            workflow=workflow,
            attempt=attempt,
            checkpoint=checkpoint,
            verify_report=verify_report,
        ):
            memory_item = self.memory_item_repository.create(
                MemoryItemRecord(
                    memory_id=uuid4(),
                    workspace_id=workflow.workspace_id,
                    episode_id=episode.episode_id,
                    type=candidate.memory_type,
                    provenance="workflow_checkpoint_auto",
                    content=candidate.content,
                    metadata={
                        **dict(episode.metadata),
                        **dict(candidate.metadata),
                        "promotion_field": candidate.field_key,
                    },
                    created_at=now,
                    updated_at=now,
                )
            )
            logger.info(
                "workflow checkpoint auto-memory promoted memory item created",
                extra={
                    "workflow_instance_id": str(workflow.workflow_instance_id),
                    "attempt_id": str(attempt.attempt_id),
                    "checkpoint_id": str(checkpoint.checkpoint_id),
                    "episode_id": str(episode.episode_id),
                    "memory_id": str(memory_item.memory_id),
                    "memory_type": memory_item.type,
                    "promotion_field": candidate.field_key,
                },
            )
            created_items.append(memory_item)
        return tuple(created_items)

    def _create_supports_relations(
        self,
        *,
        workflow: WorkflowInstance,
        attempt: WorkflowAttempt,
        primary_memory_item: MemoryItemRecord,
        promoted_memory_items: tuple[MemoryItemRecord, ...],
        now: datetime,
    ) -> tuple[MemoryRelationRecord, ...]:
        if self.memory_relation_repository is None:
            return ()

        promoted_by_field = {
            item.metadata.get("promotion_field"): item
            for item in promoted_memory_items
            if isinstance(item.metadata.get("promotion_field"), str)
        }

        relation_specs: list[tuple[str, MemoryItemRecord, MemoryItemRecord, str]] = []

        objective_item = promoted_by_field.get("current_objective")
        next_action_item = promoted_by_field.get("next_intended_action")
        verify_item = promoted_by_field.get("verify_status")
        failure_item = promoted_by_field.get("failure_reason")

        if next_action_item is not None and objective_item is not None:
            relation_specs.append(
                (
                    "next_action_supports_objective",
                    next_action_item,
                    objective_item,
                    "next intended action supports the current objective",
                )
            )

        if verify_item is not None and primary_memory_item is not None:
            relation_specs.append(
                (
                    "verification_supports_completion_note",
                    verify_item,
                    primary_memory_item,
                    "verification outcome supports the completion note",
                )
            )

        if failure_item is not None and primary_memory_item is not None:
            relation_specs.append(
                (
                    "failure_reason_supports_completion_note",
                    failure_item,
                    primary_memory_item,
                    "failure reason supports the completion note",
                )
            )

        root_cause_item = promoted_by_field.get("root_cause")
        recovery_pattern_item = promoted_by_field.get("recovery_pattern")

        if recovery_pattern_item is not None and root_cause_item is not None:
            relation_specs.append(
                (
                    "recovery_pattern_supports_root_cause",
                    recovery_pattern_item,
                    root_cause_item,
                    "recovery pattern supports the root cause understanding",
                )
            )

        created_relations: list[MemoryRelationRecord] = []
        relation_memory_origin = self._relation_memory_origin(
            primary_memory_item=primary_memory_item,
            promoted_memory_items=promoted_memory_items,
        )

        for relation_reason, source_item, target_item, description in relation_specs:
            relation = self.memory_relation_repository.create(
                MemoryRelationRecord(
                    memory_relation_id=uuid4(),
                    source_memory_id=source_item.memory_id,
                    target_memory_id=target_item.memory_id,
                    relation_type="supports",
                    metadata={
                        "memory_origin": relation_memory_origin,
                        "relation_reason": relation_reason,
                        "relation_description": description,
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "attempt_id": str(attempt.attempt_id),
                        "source_memory_type": source_item.type,
                        "target_memory_type": target_item.type,
                    },
                    created_at=now,
                )
            )
            logger.info(
                "workflow completion auto-memory relation created",
                extra={
                    "workflow_instance_id": str(workflow.workflow_instance_id),
                    "attempt_id": str(attempt.attempt_id),
                    "memory_relation_id": str(relation.memory_relation_id),
                    "relation_type": relation.relation_type,
                    "source_memory_id": str(relation.source_memory_id),
                    "target_memory_id": str(relation.target_memory_id),
                    "relation_reason": relation_reason,
                },
            )
            created_relations.append(relation)

        return tuple(created_relations)

    def _relation_memory_origin(
        self,
        *,
        primary_memory_item: MemoryItemRecord,
        promoted_memory_items: tuple[MemoryItemRecord, ...],
    ) -> str | None:
        origins = {
            str(memory_origin).strip()
            for memory_item in (primary_memory_item, *promoted_memory_items)
            for memory_origin in [memory_item.metadata.get("memory_origin")]
            if isinstance(memory_origin, str) and str(memory_origin).strip()
        }
        if not origins:
            return None
        if "workflow_checkpoint_auto" in origins:
            return "workflow_checkpoint_auto"
        if "workflow_complete_auto" in origins:
            return "workflow_complete_auto"
        return sorted(origins)[0]

    def _relation_type_counts(
        self,
        relations: tuple[MemoryRelationRecord, ...],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for relation in relations:
            counts[relation.relation_type] = counts.get(relation.relation_type, 0) + 1
        return counts

    def _relation_skipped_reason(
        self,
        *,
        relation_records: tuple[MemoryRelationRecord, ...],
        promoted_memory_items: tuple[MemoryItemRecord, ...],
    ) -> str | None:
        if self.memory_relation_repository is None:
            return "memory_relations_not_configured"
        if relation_records:
            return None
        if not promoted_memory_items:
            return "no_relation_candidate_memory_items"
        return "no_supported_relation_pairs"

    def _maybe_build_completion_summary(
        self,
        *,
        workflow: WorkflowInstance,
        episode: EpisodeRecord,
        memory_item: MemoryItemRecord,
        promoted_memory_items: tuple[MemoryItemRecord, ...],
        latest_checkpoint: WorkflowCheckpoint | None,
    ) -> dict[str, Any] | None:
        builder = self.summary_builder
        if builder is None:
            return None

        if episode.episode_id is None:
            return {
                "summary_build_attempted": False,
                "summary_build_succeeded": False,
                "summary_build_requested": False,
                "summary_build_status": None,
                "summary_build_skipped_reason": "missing_episode_id",
                "summary_build_trigger": None,
                "summary_build_scope": "workflow_completion_auto_memory_episode",
                "summary_build_kind": "episode_summary",
                "summary_build_replace_existing": True,
                "summary_build_non_fatal": True,
                "summary_build_replaced_existing_summary": False,
                "built_memory_summary_id": None,
                "built_summary_kind": "episode_summary",
                "built_summary_membership_count": 0,
            }

        checkpoint_payload = (
            latest_checkpoint.checkpoint_json
            if latest_checkpoint is not None and isinstance(latest_checkpoint.checkpoint_json, dict)
            else {}
        )
        summary_build_requested = checkpoint_payload.get("build_episode_summary") is True
        summary_build_trigger = (
            "latest_checkpoint.build_episode_summary_true" if summary_build_requested else None
        )

        if not summary_build_requested:
            return {
                "summary_build_attempted": False,
                "summary_build_succeeded": False,
                "summary_build_requested": False,
                "summary_build_status": None,
                "summary_build_skipped_reason": "workflow_summary_build_not_requested",
                "summary_build_trigger": None,
                "summary_build_scope": "workflow_completion_auto_memory_episode",
                "summary_build_kind": "episode_summary",
                "summary_build_replace_existing": True,
                "summary_build_non_fatal": True,
                "summary_build_replaced_existing_summary": False,
                "built_memory_summary_id": None,
                "built_summary_kind": "episode_summary",
                "built_summary_membership_count": 0,
            }

        try:
            from ..memory.service import BuildEpisodeSummaryRequest

            result = builder.build_episode_summary(
                BuildEpisodeSummaryRequest(
                    episode_id=str(episode.episode_id),
                    summary_kind="episode_summary",
                    replace_existing=True,
                    metadata={
                        "source": "workflow_completion_auto_memory",
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "auto_memory_episode_id": str(episode.episode_id),
                        "auto_memory_memory_id": str(memory_item.memory_id),
                        "remember_path_memory_origins": sorted(
                            {
                                str(candidate_memory_item.metadata.get("memory_origin"))
                                for candidate_memory_item in (memory_item, *promoted_memory_items)
                                if isinstance(
                                    candidate_memory_item.metadata.get("memory_origin"),
                                    str,
                                )
                                and str(candidate_memory_item.metadata.get("memory_origin")).strip()
                            }
                        ),
                        "remember_path_promotion_fields": sorted(
                            {
                                str(candidate_memory_item.metadata.get("promotion_field"))
                                for candidate_memory_item in (memory_item, *promoted_memory_items)
                                if isinstance(
                                    candidate_memory_item.metadata.get("promotion_field"),
                                    str,
                                )
                                and str(
                                    candidate_memory_item.metadata.get("promotion_field")
                                ).strip()
                            }
                        ),
                        "summary_build_trigger": summary_build_trigger,
                    },
                )
            )
        except Exception as exc:
            return {
                "summary_build_attempted": True,
                "summary_build_succeeded": False,
                "summary_build_requested": True,
                "summary_build_status": None,
                "summary_build_skipped_reason": "summary_build_failed",
                "summary_build_trigger": summary_build_trigger,
                "summary_build_scope": "workflow_completion_auto_memory_episode",
                "summary_build_kind": "episode_summary",
                "summary_build_replace_existing": True,
                "summary_build_non_fatal": True,
                "summary_build_replaced_existing_summary": False,
                "built_memory_summary_id": None,
                "built_summary_kind": "episode_summary",
                "built_summary_membership_count": 0,
                "summary_build_error_type": type(exc).__name__,
                "summary_build_error_message": str(exc),
            }

        summary = getattr(result, "summary", None)
        memberships = getattr(result, "memberships", ())
        return {
            "summary_build_attempted": True,
            "summary_build_succeeded": bool(getattr(result, "summary_built", False)),
            "summary_build_requested": True,
            "summary_build_status": getattr(result, "status", None),
            "summary_build_skipped_reason": getattr(result, "skipped_reason", None),
            "summary_build_trigger": summary_build_trigger,
            "summary_build_scope": "workflow_completion_auto_memory_episode",
            "summary_build_kind": "episode_summary",
            "summary_build_replace_existing": True,
            "summary_build_non_fatal": True,
            "summary_build_replaced_existing_summary": getattr(
                result,
                "replaced_existing_summary",
                False,
            ),
            "built_memory_summary_id": (
                str(summary.memory_summary_id) if summary is not None else None
            ),
            "built_summary_kind": (
                summary.summary_kind if summary is not None else "episode_summary"
            ),
            "built_summary_membership_count": len(memberships),
        }

    @staticmethod
    def _merge_summary_build_outcome_metadata(
        metadata: dict[str, Any],
        summary_build: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(metadata)
        if summary_build is None:
            merged["summary_build_requested"] = False
            merged["summary_build_attempted"] = False
            merged["summary_build_succeeded"] = False
            merged["summary_build_skipped_reason"] = "summary_builder_not_configured"
            return merged

        merged["summary_build_requested"] = bool(
            summary_build.get("summary_build_requested", False)
        )
        merged["summary_build_attempted"] = bool(
            summary_build.get("summary_build_attempted", False)
        )
        merged["summary_build_succeeded"] = bool(
            summary_build.get("summary_build_succeeded", False)
        )
        merged["summary_build_skipped_reason"] = summary_build.get("summary_build_skipped_reason")
        return merged

    def _maybe_store_embedding(self, memory_item: MemoryItemRecord) -> dict[str, Any]:
        # This helper is intentionally persistence-oriented.
        #
        # It exists to decide whether a durable memory item should also leave
        # behind a durable embedding record. That makes it a good fit for:
        # - application-side embedding generation in small/local modes
        # - PostgreSQL-side `azure_ai` materialization in large Azure modes
        #
        # It is not the right abstraction for interactive AI response paths
        # whose result should be returned directly to an MCP client without first
        # being stored.
        if self.memory_embedding_repository is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
            }

        try:
            settings = get_settings().embedding
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
            # Large Azure persistence path:
            # the workflow bridge still owns the decision to persist an
            # embedding, but the embedding value itself is produced inside
            # PostgreSQL through `azure_ai` so it can be stored as part of the
            # database-oriented materialization path.
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
                stored = self.memory_embedding_repository.create_via_postgres_azure_ai(
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

        if self.embedding_generator is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": "embedding_generator_not_configured",
            }

        # Small / app-generated persistence path:
        # the application process computes the embedding vector first and then
        # stores it durably. This is still persistence-oriented work because the
        # output is being materialized into the memory embedding store rather
        # than returned directly to the client as an interactive AI response.

        try:
            result = self.embedding_generator.generate(
                EmbeddingRequest(
                    text=memory_item.content,
                    metadata=memory_item.metadata,
                )
            )
        except EmbeddingGenerationError as exc:
            return {
                "embedding_persistence_status": "failed",
                "embedding_generation_skipped_reason": f"embedding_generation_failed:{exc.provider}",
                "embedding_generation_failure": {
                    "provider": exc.provider,
                    "message": str(exc),
                    "details": dict(exc.details),
                },
            }

        self.memory_embedding_repository.create(
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

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_current_objective(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("current_objective")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_next_intended_action(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("next_intended_action")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_verify_target(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("verify_target")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_resume_hint(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("resume_hint")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_blocker_or_risk(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("blocker_or_risk")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_failure_guard(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("failure_guard")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_root_cause(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("root_cause")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_recovery_pattern(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("recovery_pattern")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _checkpoint_what_remains(
        checkpoint: WorkflowCheckpoint | None,
    ) -> str | None:
        if checkpoint is None:
            return None
        raw_value = checkpoint.checkpoint_json.get("what_remains")
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized if normalized else None

    @staticmethod
    def _verify_status_value(report: VerifyReport | None) -> str | None:
        if report is None:
            return None
        status = report.status
        return str(getattr(status, "value", status))
