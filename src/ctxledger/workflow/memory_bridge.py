from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from ..config import EmbeddingProvider, get_settings
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
    episode: EpisodeRecord | None = None
    memory_item: MemoryItemRecord | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AutoMemoryDuplicateCheckResult:
    should_record: bool
    skipped_reason: str | None = None


_NEAR_DUPLICATE_LOOKBACK_WINDOW = timedelta(hours=6)
_SUMMARY_SIMILARITY_THRESHOLD = 0.75
_FIELD_EXTRACTED_SIMILARITY_THRESHOLD = 0.7
_COMPLETION_SUMMARY_WEIGHT = 3.0
_CHECKPOINT_SUMMARY_WEIGHT = 1.5
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
        "of",
        "planned",
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
    "last planned next action": "next_intended_action",
    "next action": "next_intended_action",
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


@dataclass(slots=True)
class WorkflowMemoryBridge:
    episode_repository: EpisodeRepository
    memory_item_repository: MemoryItemRepository
    memory_embedding_repository: MemoryEmbeddingRepository | None = None
    embedding_generator: EmbeddingGenerator | None = None

    def __post_init__(self) -> None:
        if self.embedding_generator is None:
            try:
                settings = get_settings().embedding
                if (
                    settings.enabled
                    and settings.provider is not EmbeddingProvider.LOCAL_STUB
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
                "workflow_status": str(
                    getattr(workflow.status, "value", workflow.status)
                ),
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
        if not should_record:
            return WorkflowCompletionMemoryRecordResult(
                details={
                    "auto_memory_recorded": False,
                    "auto_memory_skipped_reason": skipped_reason,
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
        if not duplicate_check.should_record:
            return WorkflowCompletionMemoryRecordResult(
                details={
                    "auto_memory_recorded": False,
                    "auto_memory_skipped_reason": duplicate_check.skipped_reason,
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
        logger.info(
            "workflow completion auto-memory episode created",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
            },
        )
        logger.info(
            "workflow completion auto-memory creating memory item",
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
        logger.info(
            "workflow completion auto-memory memory item created",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
                "memory_id": str(memory_item.memory_id),
            },
        )
        details = self._maybe_store_embedding(memory_item)
        logger.info(
            "workflow completion auto-memory embedding persistence finished",
            extra={
                "workflow_instance_id": str(workflow.workflow_instance_id),
                "attempt_id": str(attempt.attempt_id),
                "episode_id": str(episode.episode_id),
                "memory_id": str(memory_item.memory_id),
                "embedding_details": details,
            },
        )
        return WorkflowCompletionMemoryRecordResult(
            episode=episode,
            memory_item=memory_item,
            details={
                "auto_memory_recorded": True,
                **details,
            },
        )

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
            isinstance(checkpoint_payload.get(key), str)
            and checkpoint_payload.get(key, "").strip()
            for key in heuristic_signals
        )
        if has_signal:
            return True, ""

        return False, "low_signal_checkpoint_closeout"

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
                and prior_episode.metadata.get("memory_origin")
                == "workflow_complete_auto"
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

        list_by_workflow_id = getattr(
            self.episode_repository, "list_by_workflow_id", None
        )
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

        comparison_left_tokens = (
            meaningful_left_tokens if meaningful_left_tokens else left_tokens
        )
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
                "next_intended_action",
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
            current_fields.get("next_intended_action")
            == prior_fields.get("next_intended_action")
            and current_fields.get("verify_status") == prior_fields.get("verify_status")
            and current_fields.get("workflow_status")
            == prior_fields.get("workflow_status")
            and current_fields.get("attempt_status")
            == prior_fields.get("attempt_status")
            and current_fields.get("failure_reason")
            == prior_fields.get("failure_reason")
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
            ("next_intended_action", _NEXT_ACTION_WEIGHT),
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
