from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.config import (
    EmbeddingExecutionMode,
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
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
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


@pytest.fixture(autouse=True)
def patch_embedding_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ctxledger.workflow.memory_bridge.get_settings",
        lambda: SimpleNamespace(
            embedding=SimpleNamespace(
                enabled=True,
                provider=EmbeddingProvider.LOCAL_STUB,
                execution_mode=EmbeddingExecutionMode.APP_GENERATED,
                azure_openai_embedding_deployment=None,
                dimensions=8,
                model="local-stub-v1",
                azure_openai_auth_mode=SimpleNamespace(value="auto"),
            )
        ),
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
        checkpoint_json={
            "current_objective": "Ship OpenAI embedding integration safely",
            "next_intended_action": "Review diff and commit",
        },
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
        "current_objective": "Ship OpenAI embedding integration safely",
        "next_intended_action": "Review diff and commit",
        "summary_build_requested": False,
        "summary_build_attempted": False,
        "summary_build_succeeded": False,
        "summary_build_skipped_reason": "summary_builder_not_configured",
    }
    assert "Completion summary: Validated OpenAI embedding integration end to end" in (
        result.episode.summary
    )
    assert "Latest checkpoint summary: Broader targeted regression is green" in (
        result.episode.summary
    )
    assert (
        "Current objective: Ship OpenAI embedding integration safely"
        in result.episode.summary
    )
    assert "Last planned next action: Review diff and commit" in result.episode.summary
    assert "Verify status: passed" in result.episode.summary
    assert "Workflow status: completed" in result.episode.summary

    assert result.memory_item.workspace_id == workspace_id
    assert result.memory_item.episode_id == result.episode.episode_id
    assert result.memory_item.type == "workflow_completion_note"
    assert result.memory_item.provenance == "workflow_complete_auto"
    assert result.memory_item.metadata == result.episode.metadata
    assert result.memory_item.content == result.episode.summary

    assert len(result.promoted_memory_items) == 3
    assert {item.type for item in result.promoted_memory_items} == {
        "workflow_objective",
        "workflow_next_action",
        "workflow_verification_outcome",
    }
    assert {
        item.metadata["promotion_field"] for item in result.promoted_memory_items
    } == {
        "current_objective",
        "next_intended_action",
        "verify_status",
    }

    objective_item = next(
        item
        for item in result.promoted_memory_items
        if item.type == "workflow_objective"
    )
    next_action_item = next(
        item
        for item in result.promoted_memory_items
        if item.type == "workflow_next_action"
    )
    verify_item = next(
        item
        for item in result.promoted_memory_items
        if item.type == "workflow_verification_outcome"
    )

    assert objective_item.content == "Ship OpenAI embedding integration safely"
    assert next_action_item.content == "Review diff and commit"
    assert verify_item.content == "Workflow verification outcome: passed"

    assert len(result.relations) == 2
    assert {relation.relation_type for relation in result.relations} == {"supports"}
    assert {relation.metadata["relation_reason"] for relation in result.relations} == {
        "next_action_supports_objective",
        "verification_supports_completion_note",
    }

    assert result.details["embedding_persistence_status"] == "stored"
    assert result.details["embedding_generation_skipped_reason"] is None
    assert result.details["embedding_provider"] == "local_stub"
    assert result.details["embedding_model"] == "local-stub-v1"
    assert result.details["embedding_vector_dimensions"] == 8
    assert result.details["embedding_content_hash"] == compute_content_hash(
        result.memory_item.content,
        {
            "auto_generated": True,
            "memory_origin": "workflow_complete_auto",
            "workflow_status": "completed",
            "attempt_status": "succeeded",
            "attempt_number": 1,
            "verify_status": "passed",
            "step_name": "validate_openai",
            "current_objective": "Ship OpenAI embedding integration safely",
            "next_intended_action": "Review diff and commit",
        },
    )
    assert result.details["promoted_memory_item_count"] == 3
    assert result.details["memory_relation_count"] == 2
    assert result.details["stage_details"]["gating"]["status"] == "passed"
    assert result.details["stage_details"]["summary_selection"]["status"] == "built"
    assert (
        result.details["stage_details"]["promoted_memory_items"]["status"] == "recorded"
    )
    assert (
        result.details["stage_details"]["promoted_memory_items"]["created_count"] == 3
    )
    assert result.details["stage_details"]["relations"]["status"] == "recorded"
    assert result.details["stage_details"]["relations"]["created_count"] == 2
    assert result.details["stage_details"]["relations"]["relation_type_counts"] == {
        "supports": 2
    }
    assert result.details["stage_details"]["embedding"]["status"] == "stored"
    assert result.details["stage_details"]["summary_build"] == {
        "summary_build_attempted": False,
        "summary_build_succeeded": False,
        "summary_build_requested": False,
        "summary_build_status": None,
        "summary_build_skipped_reason": "summary_builder_not_configured",
    }

    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 4
    assert len(memory_embedding_repository.embeddings) == 1
    assert len(memory_relation_repository.relations) == 2
    assert (
        memory_embedding_repository.embeddings[0].memory_id
        == result.memory_item.memory_id
    )


def test_workflow_memory_bridge_skips_completion_memory_without_summary_sources() -> (
    None
):
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
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


def test_workflow_memory_bridge_returns_failed_embedding_details_when_generation_fails() -> (
    None
):
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
    assert result.details["embedding_generation_skipped_reason"] == (
        "embedding_generation_failed:openai"
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


def test_workflow_memory_bridge_records_failure_reason_memory_and_relation() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    workflow_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    relation_repository = InMemoryMemoryRelationRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    bridge = WorkflowMemoryBridge(
        episode_repository=InMemoryEpisodeRepository(),
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=relation_repository,
        embedding_generator=LocalStubEmbeddingGenerator(
            model="local-stub-v1",
            dimensions=8,
        ),
    )

    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=workspace_id,
            ticket_id="TICKET-AUTO-MEM-4",
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.FAILED,
            verify_status=VerifyStatus.FAILED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="validate_failure_path",
            summary="Validation failed after dependency mismatch investigation",
            checkpoint_json={
                "current_objective": "Restore a passing test baseline",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.FAILED,
            report_json={"checks": ["pytest"]},
        ),
        summary="Workflow failed during validation",
        failure_reason="Dependency versions drifted and broke the integration path",
    )

    assert result is not None
    assert len(result.promoted_memory_items) == 3
    assert {
        item.metadata["promotion_field"] for item in result.promoted_memory_items
    } == {
        "current_objective",
        "verify_status",
        "failure_reason",
    }
    failure_item = next(
        item
        for item in result.promoted_memory_items
        if item.type == "workflow_failure_reason"
    )
    assert (
        failure_item.content
        == "Dependency versions drifted and broke the integration path"
    )

    assert len(result.relations) == 2
    assert {relation.metadata["relation_reason"] for relation in result.relations} == {
        "verification_supports_completion_note",
        "failure_reason_supports_completion_note",
    }
    assert result.details["memory_relation_count"] == 2
    assert result.details["stage_details"]["relations"]["status"] == "recorded"

    assert len(memory_item_repository.memory_items) == 4
    assert len(relation_repository.relations) == 2


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
                execution_mode=EmbeddingExecutionMode.APP_GENERATED,
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
                execution_mode=EmbeddingExecutionMode.APP_GENERATED,
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


def test_workflow_memory_bridge_returns_skip_result_when_summary_sources_are_absent() -> (
    None
):
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


def test_workflow_memory_bridge_recent_memory_handles_listing_error() -> None:
    from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge

    def explode(*args: object, **kwargs: object) -> tuple[()]:
        raise RuntimeError("listing exploded")

    bridge = WorkflowMemoryBridge(
        episode_repository=SimpleNamespace(list_by_workflow_id=explode),
        memory_item_repository=InMemoryMemoryItemRepository(),
        embedding_generator=None,
    )

    episodes = bridge._recent_workflow_completion_memory(
        WorkflowInstance(
            workflow_instance_id=uuid4(),
            workspace_id=uuid4(),
            ticket_id="LISTING-ERROR",
            status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert episodes == ()
