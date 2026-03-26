from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.config import (
    EmbeddingProvider,
)
from ctxledger.memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
    LocalStubEmbeddingGenerator,
    compute_content_hash,
)
from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryWorkflowLookupRepository,
    MemoryItemRecord,
    MemoryService,
)
from ctxledger.workflow.service import (
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstance,
    WorkflowInstanceStatus,
)


def test_workflow_memory_bridge_records_completion_memory_with_embedding() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    workflow = WorkflowInstance(
        workflow_instance_id=workflow_id,
        workspace_id=workspace_id,
        ticket_id="TICKET-AUTO-MEM-1",
        status=WorkflowInstanceStatus.COMPLETED,
    )
    attempt = WorkflowAttempt(
        attempt_id=attempt_id,
        workflow_instance_id=workflow_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.SUCCEEDED,
        verify_status=VerifyStatus.PASSED,
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        workflow_instance_id=workflow_id,
        attempt_id=attempt_id,
        step_name="validate_openai",
        summary="Broader targeted regression is green",
        checkpoint_json={"next_intended_action": "Review diff and commit"},
    )
    verify_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        report_json={"checks": ["pytest"]},
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        memory_relation_repository=memory_relation_repository,
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=workflow,
        attempt=attempt,
        latest_checkpoint=latest_checkpoint,
        verify_report=verify_report,
        summary="Validated OpenAI embedding integration end to end",
        failure_reason=None,
    )

    assert result is not None
    assert result.episode.workflow_instance_id == workflow_id
    assert result.episode.attempt_id == attempt_id
    assert result.episode.metadata == {
        "auto_generated": True,
        "memory_origin": "workflow_complete_auto",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "attempt_number": 1,
        "verify_status": "passed",
        "step_name": "validate_openai",
        "next_intended_action": "Review diff and commit",
    }
    assert "Completion summary: Validated OpenAI embedding integration end to end" in (
        result.episode.summary
    )
    assert "Latest checkpoint summary: Broader targeted regression is green" in (
        result.episode.summary
    )
    assert "Last planned next action: Review diff and commit" in result.episode.summary
    assert "Verify status: passed" in result.episode.summary

    assert result.memory_item.workspace_id == workspace_id
    assert result.memory_item.episode_id == result.episode.episode_id
    assert result.memory_item.type == "workflow_completion_note"
    assert result.memory_item.provenance == "workflow_complete_auto"
    assert result.memory_item.metadata == result.episode.metadata
    assert result.memory_item.content == result.episode.summary

    assert result.details["embedding_persistence_status"] == "stored"
    assert result.details["embedding_generation_skipped_reason"] is None
    assert result.details["embedding_provider"] == "local_stub"
    assert result.details["embedding_model"] == "local-stub-v1"
    assert result.details["embedding_vector_dimensions"] == 8
    assert result.details["embedding_content_hash"] == compute_content_hash(
        result.memory_item.content,
        result.memory_item.metadata,
    )
    assert result.details["promoted_memory_item_count"] == 2
    assert result.details["memory_relation_count"] == 1
    assert result.details["stage_details"]["gating"]["status"] == "passed"
    assert result.details["stage_details"]["summary_selection"]["status"] == "built"
    assert result.details["stage_details"]["promoted_memory_items"]["status"] == "recorded"
    assert result.details["stage_details"]["promoted_memory_items"]["created_count"] == 2
    assert result.details["stage_details"]["relations"]["status"] == "recorded"
    assert result.details["stage_details"]["relations"]["created_count"] == 1
    assert result.details["stage_details"]["embedding"]["status"] == "stored"

    assert len(result.promoted_memory_items) == 2
    assert {item.type for item in result.promoted_memory_items} == {
        "workflow_next_action",
        "workflow_verification_outcome",
    }
    assert {item.metadata["promotion_field"] for item in result.promoted_memory_items} == {
        "next_intended_action",
        "verify_status",
    }

    assert len(result.relations) == 1
    assert {relation.relation_type for relation in result.relations} == {"supports"}
    assert (
        result.relations[0].metadata["relation_reason"] == "verification_supports_completion_note"
    )

    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 3
    assert len(memory_embedding_repository.embeddings) == 1
    assert len(memory_relation_repository.relations) == 1
    assert memory_embedding_repository.embeddings[0].memory_id == result.memory_item.memory_id


def test_workflow_memory_bridge_records_checkpoint_memory_with_promoted_items_and_relations() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()
    checkpoint_id = uuid4()

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_embedding_repository = InMemoryMemoryEmbeddingRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    workflow = WorkflowInstance(
        workflow_instance_id=workflow_id,
        workspace_id=workspace_id,
        ticket_id="TICKET-CHECKPOINT-AUTO-MEM-1",
        status=WorkflowInstanceStatus.RUNNING,
    )
    attempt = WorkflowAttempt(
        attempt_id=attempt_id,
        workflow_instance_id=workflow_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        verify_status=VerifyStatus.PASSED,
    )
    checkpoint = WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        workflow_instance_id=workflow_id,
        attempt_id=attempt_id,
        step_name="investigate_regression",
        summary="Validated the regression boundary and narrowed the fix path",
        checkpoint_json={
            "current_objective": "Restore the passing regression suite",
            "next_intended_action": "Patch the parser edge case",
            "root_cause": "Tokenizer accepted malformed separators",
            "recovery_pattern": "Normalize separators before validation",
            "what_remains": "Run focused regression tests after the parser fix",
        },
    )
    verify_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.PASSED,
        report_json={"checks": ["pytest -q tests/parser/test_regression.py"]},
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        memory_relation_repository=memory_relation_repository,
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_checkpoint_memory(
        workflow=workflow,
        attempt=attempt,
        checkpoint=checkpoint,
        verify_report=verify_report,
    )

    assert result is not None
    assert result.episode is not None
    assert result.memory_item is not None
    assert result.episode.workflow_instance_id == workflow_id
    assert result.episode.attempt_id == attempt_id
    assert result.episode.metadata == {
        "auto_generated": True,
        "memory_origin": "workflow_checkpoint_auto",
        "workflow_status": "running",
        "attempt_status": "running",
        "attempt_number": 1,
        "step_name": "investigate_regression",
        "checkpoint_id": str(checkpoint_id),
        "verify_status": "passed",
        "current_objective": "Restore the passing regression suite",
        "next_intended_action": "Patch the parser edge case",
        "root_cause": "Tokenizer accepted malformed separators",
        "recovery_pattern": "Normalize separators before validation",
        "what_remains": "Run focused regression tests after the parser fix",
    }
    assert "Checkpoint summary: Validated the regression boundary and narrowed the fix path" in (
        result.episode.summary
    )
    assert "Current objective: Restore the passing regression suite" in result.episode.summary
    assert "Next action: Patch the parser edge case" in result.episode.summary
    assert "Root cause: Tokenizer accepted malformed separators" in result.episode.summary
    assert "Recovery pattern: Normalize separators before validation" in result.episode.summary
    assert "What remains: Run focused regression tests after the parser fix" in (
        result.episode.summary
    )
    assert "Verify status: passed" in result.episode.summary

    assert result.memory_item.workspace_id == workspace_id
    assert result.memory_item.episode_id == result.episode.episode_id
    assert result.memory_item.type == "workflow_checkpoint_note"
    assert result.memory_item.provenance == "workflow_checkpoint_auto"
    assert result.memory_item.metadata == result.episode.metadata
    assert result.memory_item.content == result.episode.summary

    assert len(result.promoted_memory_items) == 6
    assert {item.type for item in result.promoted_memory_items} == {
        "workflow_objective",
        "workflow_next_action",
        "workflow_root_cause",
        "workflow_recovery_pattern",
        "workflow_what_remains",
        "workflow_verification_outcome",
    }
    assert {item.metadata["promotion_field"] for item in result.promoted_memory_items} == {
        "current_objective",
        "next_intended_action",
        "root_cause",
        "recovery_pattern",
        "what_remains",
        "verify_status",
    }

    objective_item = next(
        item for item in result.promoted_memory_items if item.type == "workflow_objective"
    )
    next_action_item = next(
        item for item in result.promoted_memory_items if item.type == "workflow_next_action"
    )
    assert objective_item.content == "Restore the passing regression suite"
    assert next_action_item.content == "Patch the parser edge case"

    assert len(result.relations) == 3
    assert {relation.relation_type for relation in result.relations} == {"supports"}
    assert {relation.metadata["relation_reason"] for relation in result.relations} == {
        "next_action_supports_objective",
        "recovery_pattern_supports_root_cause",
        "verification_supports_completion_note",
    }

    assert result.details["auto_memory_recorded"] is True
    assert result.details["promoted_memory_item_count"] == 6
    assert result.details["memory_relation_count"] == 3
    assert result.details["stage_details"]["gating"]["status"] == "passed"
    assert result.details["stage_details"]["summary_selection"]["status"] == "built"
    assert result.details["stage_details"]["promoted_memory_items"]["status"] == "recorded"
    assert result.details["stage_details"]["promoted_memory_items"]["created_count"] == 6
    assert result.details["stage_details"]["relations"]["status"] == "recorded"
    assert result.details["stage_details"]["relations"]["created_count"] == 3
    assert result.details["stage_details"]["embedding"]["status"] == "stored"

    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 7
    assert len(memory_embedding_repository.embeddings) == 1
    assert len(memory_relation_repository.relations) == 3


def test_workflow_memory_bridge_skips_completion_memory_without_summary_sources() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-2",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="checkpointed",
            summary=None,
            checkpoint_json={},
        ),
        verify_report=None,
        summary=None,
        failure_reason=None,
    )

    assert result is not None
    assert result.episode is None
    assert result.memory_item is None
    assert result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "low_signal_checkpoint_closeout",
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "low_signal_checkpoint_closeout",
            }
        },
    }


def test_workflow_memory_bridge_skips_checkpoint_auto_memory_without_signal() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_checkpoint_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-CHECKPOINT-AUTO-MEM-2",
            status=WorkflowInstanceStatus.RUNNING,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.RUNNING,
        ),
        checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="minor_note",
            summary=None,
            checkpoint_json={},
        ),
        verify_report=None,
    )

    assert result is not None
    assert result.episode is None
    assert result.memory_item is None
    assert result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "low_signal_checkpoint_memory",
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "low_signal_checkpoint_memory",
            }
        },
    }


def test_workflow_memory_bridge_returns_failed_embedding_details_when_generation_fails() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    class FailingEmbeddingGenerator:
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            raise EmbeddingGenerationError(
                "embedding generation failed",
                provider="openai",
                details={"status_code": 500},
            )

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
        embedding_generator=FailingEmbeddingGenerator(),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-3",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.SUCCEEDED,
            verify_status=VerifyStatus.PASSED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="validate_openai",
            summary="Broader targeted regression is green",
            checkpoint_json={"next_intended_action": "Review diff and commit"},
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"]},
        ),
        summary="Validated OpenAI embedding integration end to end",
        failure_reason=None,
    )

    assert result is not None
    assert result.details["auto_memory_recorded"] is True
    assert result.details["embedding_persistence_status"] == "failed"
    assert (
        result.details["embedding_generation_skipped_reason"]
        == "embedding_generation_failed:openai"
    )
    assert result.details["embedding_generation_failure"] == {
        "provider": "openai",
        "message": "embedding generation failed",
        "details": {"status_code": 500},
    }
    assert result.details["stage_details"]["embedding"]["status"] == "failed"
    assert result.details["stage_details"]["embedding"]["skipped_reason"] == (
        "embedding_generation_failed:openai"
    )


def test_workflow_memory_bridge_post_init_uses_external_generator_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    sentinel_generator = object()
    build_calls: list[object] = []

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: SimpleNamespace(
            embedding=SimpleNamespace(
                enabled=True,
                provider=EmbeddingProvider.OPENAI,
            )
        ),
    )

    def fake_build_embedding_generator(settings: object) -> object:
        build_calls.append(settings)
        return sentinel_generator

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.build_embedding_generator",
        fake_build_embedding_generator,
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    assert bridge.embedding_generator is sentinel_generator
    assert len(build_calls) == 1
    assert build_calls[0].provider is EmbeddingProvider.OPENAI


def test_workflow_memory_bridge_post_init_skips_local_stub_autobuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: SimpleNamespace(
            embedding=SimpleNamespace(
                enabled=True,
                provider=EmbeddingProvider.LOCAL_STUB,
            )
        ),
    )
    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.build_embedding_generator",
        lambda settings: (_ for _ in ()).throw(
            AssertionError("build_embedding_generator should not be called")
        ),
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    assert bridge.embedding_generator is None


def test_workflow_memory_bridge_post_init_swallows_settings_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: (_ for _ in ()).throw(RuntimeError("settings exploded")),
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    assert bridge.embedding_generator is None


def test_workflow_memory_bridge_returns_skip_result_when_summary_sources_are_absent() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-NO-SUMMARY",
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.FAILED,
        ),
        latest_checkpoint=None,
        verify_report=None,
        summary=None,
        failure_reason="failed before summary",
    )

    assert result is not None
    assert result.episode is None
    assert result.memory_item is None
    assert result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "no_completion_summary_source",
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "no_completion_summary_source",
            }
        },
    }


def test_workflow_memory_bridge_gating_with_non_dict_checkpoint_payload() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        step_name="bad_payload",
        summary="checkpoint",
        checkpoint_json="not-a-dict",  # type: ignore[arg-type]
    )

    should_record, skipped_reason = bridge._auto_memory_gating_decision(
        workflow=WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="BAD-PAYLOAD",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        latest_checkpoint=checkpoint,
        verify_report=None,
    )

    assert should_record is False
    assert skipped_reason == "low_signal_checkpoint_closeout"


def test_workflow_memory_bridge_recent_memory_handles_missing_listing_support() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="NO-LIST",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()


def test_workflow_memory_bridge_recent_memory_handles_non_callable_listing() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(list_by_workflow_id=123),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="NON-CALLABLE-LIST",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()


def test_workflow_memory_bridge_recent_memory_handles_non_tuple_listing_result() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(
            list_by_workflow_id=lambda workflow_instance_id, limit: []
        ),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="NON-TUPLE-LIST",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()


def test_workflow_memory_bridge_summary_similarity_falls_back_to_full_tokens_when_meaningless_tokens_only() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    assert bridge._summary_token_similarity(
        "workflow status",
        "latest workflow status",
    ) == pytest.approx(2 / 3)


def test_workflow_memory_bridge_extract_closeout_fields_without_summary_uses_fallback_metadata() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    extracted = bridge._extract_closeout_fields(
        None,
        fallback_metadata={
            "next_intended_action": "Run tests",
            "verify_status": "passed",
            "workflow_status": "completed",
            "attempt_status": "succeeded",
            "failure_reason": "none",
        },
    )

    assert extracted == {
        "next_intended_action": "Run tests",
        "verify_status": "passed",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "failure_reason": "none",
    }


def test_workflow_memory_bridge_weighted_similarity_without_shared_fields_is_zero() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    assert (
        bridge._weighted_closeout_similarity(
            current_fields={"completion_summary": "alpha"},
            prior_fields={"latest_checkpoint_summary": "beta"},
        )
        == 0.0
    )


def test_workflow_memory_bridge_normalized_token_set_none_for_non_text() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    assert bridge._normalized_token_set(None) is None


def test_workflow_memory_bridge_build_completion_summary_uses_checkpoint_summary_when_completion_missing() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    summary = bridge._build_completion_summary(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="CHECKPOINT-FALLBACK",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="checkpoint_only",
            summary="Checkpoint-only summary",
            checkpoint_json={},
        ),
        verify_report=None,
        summary=None,
        failure_reason=None,
    )

    assert summary == (
        "Workflow completed with status `completed`.\n"
        "Latest checkpoint summary: Checkpoint-only summary\n"
        "Workflow status: completed"
    )


def test_workflow_memory_bridge_build_completion_summary_includes_failure_reason_for_failed_workflow() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    summary = bridge._build_completion_summary(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="FAILED-SUMMARY",
            status=WorkflowInstanceStatus.FAILED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="failed_step",
            summary="Failure checkpoint summary",
            checkpoint_json={},
        ),
        verify_report=None,
        summary="Explicit failure closeout",
        failure_reason="database unavailable",
    )

    assert summary == (
        "Workflow completed with status `failed`.\n"
        "Completion summary: Explicit failure closeout\n"
        "Latest checkpoint summary: Failure checkpoint summary\n"
        "Workflow status: failed\n"
        "Failure reason: database unavailable"
    )


def test_workflow_memory_bridge_build_completion_metadata_includes_optional_fields() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    attempt_id = uuid4()
    verify_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt_id,
        status=VerifyStatus.FAILED,
        report_json={},
    )
    checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow_id,
        attempt_id=attempt_id,
        step_name="checkpoint_step",
        summary="summary",
        checkpoint_json={"next_intended_action": "Investigate failure"},
    )

    metadata = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )._build_completion_metadata(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="FAILED-METADATA",
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=4,
            status=WorkflowAttemptStatus.FAILED,
        ),
        latest_checkpoint=checkpoint,
        verify_report=verify_report,
        failure_reason="database unavailable",
    )

    assert metadata == {
        "auto_generated": True,
        "memory_origin": "workflow_complete_auto",
        "workflow_status": "failed",
        "attempt_status": "failed",
        "attempt_number": 4,
        "verify_status": "failed",
        "step_name": "checkpoint_step",
        "next_intended_action": "Investigate failure",
        "failure_reason": "database unavailable",
    }


def test_workflow_memory_bridge_gating_allows_failed_and_auto_memory_paths() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    failed_should_record, failed_reason = bridge._auto_memory_gating_decision(
        workflow=WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="FAILED-GATING",
            status=WorkflowInstanceStatus.FAILED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=uuid4(),
            attempt_id=uuid4(),
            step_name="failed_step",
            summary="summary",
            checkpoint_json={},
        ),
        verify_report=None,
    )
    auto_memory_should_record, auto_memory_reason = bridge._auto_memory_gating_decision(
        workflow=WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="AUTO-GATING",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=uuid4(),
            attempt_id=uuid4(),
            step_name="auto_step",
            summary="summary",
            checkpoint_json={"auto_memory": True},
        ),
        verify_report=None,
    )

    assert failed_should_record is True
    assert failed_reason == ""
    assert auto_memory_should_record is True
    assert auto_memory_reason == ""


def test_workflow_memory_bridge_duplicate_closeout_checks_old_episode_and_non_auto_memory_paths() -> (
    None
):
    from ctxledger.workflow.memory_bridge import (
        AutoMemoryDuplicateCheckResult,
        WorkflowMemoryBridge,
    )

    workflow_id = uuid4()
    workspace_id = uuid4()
    now = datetime.now(UTC)
    old_duplicate_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Completion summary: Same summary\nLatest checkpoint summary: Same checkpoint",
        metadata={
            "memory_origin": "workflow_complete_auto",
            "step_name": "checkpoint_step",
            "next_intended_action": "Run tests",
            "verify_status": "passed",
            "workflow_status": "completed",
            "attempt_status": "succeeded",
        },
        created_at=now.replace(year=now.year - 1),
        updated_at=now.replace(year=now.year - 1),
    )
    non_auto_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Completion summary: Same summary",
        metadata={
            "memory_origin": "episode",
            "step_name": "checkpoint_step",
        },
        created_at=now,
        updated_at=now,
    )

    class EpisodeRepository:
        def list_by_workflow_id(
            self,
            workflow_instance_id: UUID,
            *,
            limit: int,
        ) -> tuple[EpisodeRecord, ...]:
            return (old_duplicate_episode, non_auto_episode)

    bridge = WorkflowMemoryBridge(
        episode_repository=EpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    result = bridge._duplicate_closeout_memory_decision(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="DUPLICATE-CHECK",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="checkpoint_step",
            summary="Same checkpoint",
            checkpoint_json={},
        ),
        memory_summary="Completion summary: Same summary\nLatest checkpoint summary: Same checkpoint",
        episode_metadata={
            "next_intended_action": "Run tests",
            "verify_status": "passed",
            "workflow_status": "completed",
            "attempt_status": "succeeded",
        },
    )

    assert result == AutoMemoryDuplicateCheckResult(
        should_record=False,
        skipped_reason="duplicate_closeout_auto_memory",
    )


def test_workflow_memory_bridge_recent_memory_filters_non_auto_memory_entries() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    auto_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="auto",
        metadata={"memory_origin": "workflow_complete_auto"},
    )
    other_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="other",
        metadata={"memory_origin": "episode"},
    )

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(
            list_by_workflow_id=lambda workflow_instance_id, limit: (
                auto_episode,
                other_episode,
            )
        ),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="FILTER-AUTO",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == (auto_episode,)


def test_workflow_memory_bridge_maybe_store_embedding_skips_without_dependencies() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=None,
        embedding_generator=None,
    )

    details = bridge._maybe_store_embedding(
        MemoryItemRecord(
            memory_id=uuid4(),
            content="skip embedding",
            metadata={"kind": "episode"},
        )
    )

    assert details == {
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }


def test_workflow_memory_bridge_checkpoint_next_action_handles_non_string_value() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        step_name="non_string_next_action",
        summary="summary",
        checkpoint_json={"next_intended_action": 123},
    )

    assert WorkflowMemoryBridge._checkpoint_next_intended_action(checkpoint) is None


def test_workflow_memory_bridge_verify_status_none_without_report() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    assert WorkflowMemoryBridge._verify_status_value(None) is None


def test_memory_service_resolve_workspace_id_and_has_text_helpers() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()
    service = MemoryService(
        workspace_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                }
            }
        )
    )

    assert service._resolve_workspace_id(workflow_id) == workspace_id
    assert service._has_text(" value ") is True
    assert service._has_text("   ") is False
    assert service._has_text(None) is False


def test_memory_service_get_context_uses_workspace_and_ticket_lookup_paths() -> None:
    matching_workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=matching_workflow_id,
        summary="Workspace and ticket lookup match",
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    episode_repository.create(matching_episode)

    class RecordingLookup:
        def __init__(self) -> None:
            self.workspace_calls: list[tuple[str, int]] = []
            self.ticket_calls: list[tuple[str, int]] = []

        def workflow_exists(self, workflow_instance_id: UUID) -> bool:
            return workflow_instance_id == matching_workflow_id

        def workflow_ids_by_workspace_id(
            self,
            workspace_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.workspace_calls.append((workspace_id, limit))
            return (matching_workflow_id,)

        def workflow_ids_by_ticket_id(
            self,
            ticket_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.ticket_calls.append((ticket_id, limit))
            return (matching_workflow_id,)

        def workflow_ids_by_workspace_id_raw_order(
            self,
            workspace_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.workspace_calls.append((workspace_id, limit))
            return (matching_workflow_id,)

        def workflow_ids_by_ticket_id_raw_order(
            self,
            ticket_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            self.ticket_calls.append((ticket_id, limit))
            return (matching_workflow_id,)

        def workflow_freshness_by_id(
            self,
            workflow_instance_id: UUID,
        ) -> dict[str, datetime | int | str | bool | None]:
            return {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "workflow_updated_at": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": False,
                "latest_attempt_verify_status": None,
                "latest_attempt_started_at": None,
                "has_latest_checkpoint": False,
                "latest_checkpoint_created_at": None,
                "latest_verify_report_created_at": None,
            }

    lookup = RecordingLookup()
    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=lookup,
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="workspace-lookup",
            ticket_id="ticket-lookup",
            limit=3,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert lookup.workspace_calls == [("workspace-lookup", 3)]
    assert lookup.ticket_calls == [("ticket-lookup", 3)]
    assert response.details["lookup_scope"] == "workspace_and_ticket"
    assert response.details["resolved_workflow_ids"] == [str(matching_workflow_id)]
    assert [episode.summary for episode in response.episodes] == [
        "Workspace and ticket lookup match"
    ]


def test_memory_get_context_includes_episode_explanations_without_query_filter() -> None:
    workflow_id = uuid4()
    created_at = datetime(2024, 9, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Recent unfiltered episode",
        metadata={"kind": "recent"},
        created_at=created_at.replace(day=3),
        updated_at=created_at.replace(day=3),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Older unfiltered episode",
        metadata={"kind": "older"},
        created_at=created_at.replace(day=2),
        updated_at=created_at.replace(day=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=5,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(first_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
        {
            "episode_id": str(second_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    ]


def test_memory_get_context_includes_episode_explanations_for_query_matches() -> None:
    workflow_id = uuid4()
    created_at = datetime(2024, 9, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    summary_match_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Investigate postgres startup ordering",
        metadata={"kind": "summary-match"},
        created_at=created_at.replace(day=2),
        updated_at=created_at.replace(day=2),
    )
    metadata_match_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Capture workflow evidence",
        metadata={"service": "postgres primary", "kind": "metadata-match"},
        created_at=created_at.replace(day=3),
        updated_at=created_at.replace(day=3),
    )
    no_match_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Document release checklist",
        metadata={"service": "release automation", "kind": "no-match"},
        created_at=created_at.replace(day=4),
        updated_at=created_at.replace(day=4),
    )
    episode_repository.create(summary_match_episode)
    episode_repository.create(metadata_match_episode)
    episode_repository.create(no_match_episode)

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="postgres ordering",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Investigate postgres startup ordering",
    ]
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(summary_match_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": [],
        },
    ]
