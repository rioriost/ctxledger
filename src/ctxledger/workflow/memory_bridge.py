from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from ..config import get_settings
from ..memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingGenerator,
    EmbeddingRequest,
    build_embedding_generator,
)

if TYPE_CHECKING:
    from ..memory.service import MemoryEmbeddingRepository, MemoryItemRepository
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
class WorkflowCompletionMemoryRecordResult:
    episode: EpisodeRecord
    memory_item: MemoryItemRecord
    details: dict[str, Any]


class EpisodeRepository(Protocol):
    def create(self, episode: EpisodeRecord) -> EpisodeRecord: ...


class MemoryItemRepository(Protocol):
    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord: ...


class MemoryEmbeddingRepository(Protocol):
    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord: ...


@dataclass(slots=True)
class WorkflowMemoryBridge:
    episode_repository: EpisodeRepository
    memory_item_repository: MemoryItemRepository
    memory_embedding_repository: MemoryEmbeddingRepository | None = None
    embedding_generator: EmbeddingGenerator | None = None

    def __post_init__(self) -> None:
        if self.embedding_generator is None:
            try:
                self.embedding_generator = build_embedding_generator(
                    get_settings().embedding
                )
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
        memory_summary = self._build_completion_summary(
            workflow=workflow,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
            summary=summary,
            failure_reason=failure_reason,
        )
        if memory_summary is None:
            return None

        episode_metadata = self._build_completion_metadata(
            workflow=workflow,
            attempt=attempt,
            latest_checkpoint=latest_checkpoint,
            verify_report=verify_report,
            failure_reason=failure_reason,
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
        details = self._maybe_store_embedding(memory_item)
        return WorkflowCompletionMemoryRecordResult(
            episode=episode,
            memory_item=memory_item,
            details=details,
        )

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

        if summary_text is None and checkpoint_summary is None:
            return None

        lines: list[str] = [
            f"Workflow completed with status `{workflow.status.value}`."
        ]

        if summary_text is not None:
            lines.append(f"Completion summary: {summary_text}")
        elif checkpoint_summary is not None:
            lines.append(f"Latest checkpoint summary: {checkpoint_summary}")

        if summary_text is not None and checkpoint_summary is not None:
            if summary_text != checkpoint_summary:
                lines.append(f"Latest checkpoint summary: {checkpoint_summary}")

        next_intended_action = self._checkpoint_next_intended_action(latest_checkpoint)
        if next_intended_action is not None:
            lines.append(f"Last planned next action: {next_intended_action}")

        verify_status = self._verify_status_value(verify_report)
        if verify_status is not None:
            lines.append(f"Verify status: {verify_status}")

        if failure_reason is not None and workflow.status in {
            WorkflowInstanceStatus.FAILED,
            WorkflowInstanceStatus.CANCELLED,
        }:
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
            next_intended_action = self._checkpoint_next_intended_action(
                latest_checkpoint
            )
            if next_intended_action is not None:
                metadata["next_intended_action"] = next_intended_action

        if failure_reason is not None:
            metadata["failure_reason"] = failure_reason

        return metadata

    def _maybe_store_embedding(self, memory_item: MemoryItemRecord) -> dict[str, Any]:
        if self.embedding_generator is None or self.memory_embedding_repository is None:
            return {
                "embedding_persistence_status": "skipped",
                "embedding_generation_skipped_reason": (
                    "embedding_persistence_not_configured"
                ),
            }

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
                "embedding_generation_skipped_reason": (
                    f"embedding_generation_failed:{exc.provider}"
                ),
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
    def _verify_status_value(report: VerifyReport | None) -> str | None:
        if report is None:
            return None
        status = report.status
        return str(getattr(status, "value", status))
