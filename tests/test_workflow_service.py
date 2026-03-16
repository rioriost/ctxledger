from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
from ctxledger.workflow.memory_bridge import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    WorkflowMemoryBridge,
)
from ctxledger.workflow.service import (
    ActiveWorkflowExistsError,
    AttemptNotFoundError,
    CompleteWorkflowInput,
    CreateCheckpointInput,
    InvalidStateTransitionError,
    ProjectionArtifactType,
    ProjectionFailureInfo,
    ProjectionInfo,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeIssue,
    ResumeWorkflowInput,
    StartWorkflowInput,
    ValidationError,
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptMismatchError,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowCompleteResult,
    WorkflowError,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowNotFoundError,
    WorkflowResume,
    WorkflowService,
    Workspace,
    WorkspaceNotFoundError,
    WorkspaceRegistrationConflictError,
    utc_now,
)


class RecordingEpisodeRepository:
    def __init__(self) -> None:
        self.episodes: list[EpisodeRecord] = []

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        self.episodes.append(episode)
        return episode

    def list_by_workflow_id(
        self,
        workflow_instance_id,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        episodes = [
            episode
            for episode in self.episodes
            if episode.workflow_instance_id == workflow_instance_id
        ]
        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])


class RecordingMemoryItemRepository:
    def __init__(self) -> None:
        self.memory_items: list[MemoryItemRecord] = []

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        self.memory_items.append(memory_item)
        return memory_item


class RecordingMemoryEmbeddingRepository:
    def __init__(self) -> None:
        self.embeddings: list[MemoryEmbeddingRecord] = []

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        self.embeddings.append(embedding)
        return embedding


def make_service_and_uow(
    *,
    workflow_memory_bridge: WorkflowMemoryBridge | None = None,
) -> tuple[WorkflowService, object]:
    store = InMemoryStore.create()
    uow_factory = build_in_memory_uow_factory(store)
    service = WorkflowService(
        uow_factory,
        workflow_memory_bridge=workflow_memory_bridge,
    )
    return service, store


def register_workspace(service: WorkflowService) -> Workspace:
    return service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
        )
    )


def test_register_workspace_creates_workspace() -> None:
    service, uow = make_service_and_uow()

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
            metadata={"language": "python"},
        )
    )

    assert workspace.workspace_id in uow.workspaces_by_id
    assert workspace.repo_url == "https://example.com/org/repo.git"
    assert workspace.canonical_path == "/tmp/repo"
    assert workspace.default_branch == "main"
    assert workspace.metadata == {"language": "python"}


def test_register_workspace_rejects_canonical_path_conflict_without_workspace_id() -> (
    None
):
    service, _ = make_service_and_uow()
    register_workspace(service)

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/other.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "canonical_path" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_start_workflow_creates_running_workflow_and_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)

    result = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-123",
            metadata={"priority": "high"},
        )
    )

    assert result.workflow_instance.workspace_id == workspace.workspace_id
    assert result.workflow_instance.ticket_id == "TICKET-123"
    assert result.workflow_instance.status == WorkflowInstanceStatus.RUNNING

    assert (
        result.attempt.workflow_instance_id
        == result.workflow_instance.workflow_instance_id
    )
    assert result.attempt.attempt_number == 1
    assert result.attempt.status == WorkflowAttemptStatus.RUNNING

    assert result.workflow_instance.workflow_instance_id in uow.workflows_by_id
    assert result.attempt.attempt_id in uow.attempts_by_id


def test_start_workflow_rejects_second_running_workflow_in_same_workspace() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-1",
        )
    )

    try:
        service.start_workflow(
            StartWorkflowInput(
                workspace_id=workspace.workspace_id,
                ticket_id="TICKET-2",
            )
        )
    except ActiveWorkflowExistsError as exc:
        assert exc.code == "active_workflow_exists"
    else:
        raise AssertionError("Expected ActiveWorkflowExistsError")


def test_create_checkpoint_persists_snapshot_and_verify_report() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-123",
        )
    )

    result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="edit_files",
            summary="Updated workflow docs",
            checkpoint_json={
                "current_objective": "Expand architecture and workflow docs",
                "next_intended_action": "Implement repositories",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["lint"], "status": "passed"},
        )
    )

    assert result.checkpoint.step_name == "edit_files"
    assert result.checkpoint.summary == "Updated workflow docs"
    assert (
        result.checkpoint.checkpoint_json["next_intended_action"]
        == "Implement repositories"
    )

    assert result.verify_report is not None
    assert result.verify_report.status == VerifyStatus.PASSED
    assert result.attempt.verify_status == VerifyStatus.PASSED

    stored_attempt = uow.attempts_by_id.get(started.attempt.attempt_id)
    assert stored_attempt is not None
    assert stored_attempt.verify_status == VerifyStatus.PASSED


def test_create_checkpoint_rejects_attempt_from_another_workflow() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    first = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="A")
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=first.workflow_instance.workflow_instance_id,
            attempt_id=first.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    second = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="B")
    )

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=second.workflow_instance.workflow_instance_id,
                attempt_id=first.attempt.attempt_id,
                step_name="bad_linkage",
            )
        )
    except WorkflowAttemptMismatchError as exc:
        assert exc.code == "workflow_attempt_mismatch"
    else:
        raise AssertionError("Expected WorkflowAttemptMismatchError")


def test_complete_workflow_moves_workflow_and_attempt_to_terminal_states() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-456",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["tests"], "status": "passed"},
        )
    )

    assert isinstance(result, WorkflowCompleteResult)
    assert result.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert result.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert result.attempt.finished_at is not None
    assert result.verify_report is not None
    assert result.verify_report.status == VerifyStatus.PASSED


def test_complete_workflow_rejects_terminal_workflow_recompletion() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="T-1")
    )

    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.CANCELLED,
        )
    )

    try:
        service.complete_workflow(
            CompleteWorkflowInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                workflow_status=WorkflowInstanceStatus.COMPLETED,
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_complete_workflow_auto_memory_records_when_checkpoint_has_next_action() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    service, _ = make_service_and_uow(
        workflow_memory_bridge=WorkflowMemoryBridge(
            episode_repository=episode_repository,
            memory_item_repository=memory_item_repository,
            memory_embedding_repository=memory_embedding_repository,
            embedding_generator=None,
        )
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-1",
        )
    )

    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Planned checkpoint auto-memory heuristic",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["planning"], "status": "passed"},
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed heuristic planning pass",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["planning"], "status": "passed"},
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert result.warnings == ()
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 0
    assert (
        episode_repository.episodes[0].metadata["memory_origin"]
        == "workflow_complete_auto"
    )
    assert (
        episode_repository.episodes[0].metadata["next_intended_action"]
        == "Implement the minimum heuristic path"
    )
    assert (
        "Last planned next action: Implement the minimum heuristic path"
        in episode_repository.episodes[0].summary
    )


def test_complete_workflow_auto_memory_skips_without_checkpoint_signal() -> None:
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    service, _ = make_service_and_uow(
        workflow_memory_bridge=WorkflowMemoryBridge(
            episode_repository=episode_repository,
            memory_item_repository=memory_item_repository,
            memory_embedding_repository=memory_embedding_repository,
            embedding_generator=None,
        )
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-2",
        )
    )

    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="minor_note",
            summary="Tiny progress note",
            checkpoint_json={},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["planning"], "status": "passed"},
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed a low-signal pass",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["planning"], "status": "passed"},
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "low_signal_checkpoint_closeout",
    }
    assert result.warnings == ()
    assert episode_repository.episodes == []
    assert memory_item_repository.memory_items == []
    assert memory_embedding_repository.embeddings == []


def test_complete_workflow_auto_memory_records_when_verify_failed() -> None:
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    service, _ = make_service_and_uow(
        workflow_memory_bridge=WorkflowMemoryBridge(
            episode_repository=episode_repository,
            memory_item_repository=memory_item_repository,
            memory_embedding_repository=memory_embedding_repository,
            embedding_generator=None,
        )
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-3",
        )
    )

    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="validation_pass",
            summary="Validation exposed a risky edge case",
            checkpoint_json={},
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Closed the loop with failing verification captured",
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 1
    assert episode_repository.episodes[0].metadata["verify_status"] == "failed"
    assert "Verify status: failed" in episode_repository.episodes[0].summary


def test_complete_workflow_auto_memory_skips_duplicate_closeout_summary() -> None:
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()
    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-DUPE-1",
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
            step_name="design_phase2",
            summary="Checkpoint summary for duplicate suppression",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Completed heuristic planning pass",
        failure_reason=None,
    )

    assert result is not None
    assert result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }

    duplicate_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-DUPE-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Checkpoint summary for duplicate suppression",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Completed heuristic planning pass",
        failure_reason=None,
    )

    assert duplicate_result is not None
    assert duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "duplicate_closeout_auto_memory",
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_skips_near_duplicate_checkpoint_closeout() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()
    result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-NEAR-DUPE-1",
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
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="First completion summary",
        failure_reason=None,
    )

    assert result is not None
    assert result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }

    near_duplicate_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-NEAR-DUPE-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Second checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Second completion summary",
        failure_reason=None,
    )

    assert near_duplicate_result is not None
    assert near_duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_does_not_treat_old_closeout_as_near_duplicate() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()
    original_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-OLD-NEAR-DUPE-1",
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
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="First completion summary",
        failure_reason=None,
    )

    assert original_result is not None
    assert original_result.episode is not None
    aged_episode = EpisodeRecord(
        episode_id=original_result.episode.episode_id,
        workflow_instance_id=original_result.episode.workflow_instance_id,
        summary=original_result.episode.summary,
        attempt_id=original_result.episode.attempt_id,
        metadata=dict(original_result.episode.metadata),
        status=original_result.episode.status,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    episode_repository.episodes[0] = aged_episode

    later_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-OLD-NEAR-DUPE-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Second checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Second completion summary",
        failure_reason=None,
    )

    assert later_result is not None
    assert later_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 2


def test_complete_workflow_auto_memory_does_not_treat_different_verify_status_as_near_duplicate() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()
    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-VERIFY-DIFF-1",
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
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="First completion summary",
        failure_reason=None,
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-VERIFY-DIFF-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Second checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.FAILED,
            report_json={"checks": ["planning"], "status": "failed"},
        ),
        summary="Second completion summary",
        failure_reason=None,
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 2
    assert episode_repository.episodes[1].metadata["verify_status"] == "failed"


def test_complete_workflow_auto_memory_skips_near_duplicate_with_high_summary_similarity() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()

    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-SUMMARY-SIMILAR-1",
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
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Implemented summary similarity gating for duplicate suppression",
        failure_reason=None,
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-SUMMARY-SIMILAR-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior again",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Implemented gating for summary similarity in duplicate suppression",
        failure_reason=None,
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_skips_near_duplicate_when_similarity_is_only_boilerplate_driven() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()

    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-SUMMARY-BOILERPLATE-1",
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
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Implemented summary similarity gating for duplicate suppression",
        failure_reason=None,
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-SUMMARY-BOILERPLATE-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior for another path",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Implemented summary similarity gating for duplicate suppression",
        failure_reason=None,
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_records_when_summary_similarity_is_below_threshold() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()

    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-SUMMARY-DISSIMILAR-1",
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
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Implemented summary similarity gating for duplicate suppression",
        failure_reason=None,
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-SUMMARY-DISSIMILAR-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Documented operator-facing rollout guidance for the refined suppression logic",
            checkpoint_json={
                "next_intended_action": "Publish operator-facing duplicate suppression notes",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Documented rollout notes for operators after validation",
        failure_reason=None,
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 2
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_extracts_semantic_fields_from_summary_lines() -> (
    None
):
    bridge = WorkflowMemoryBridge(
        episode_repository=RecordingEpisodeRepository(),
        memory_item_repository=RecordingMemoryItemRepository(),
        memory_embedding_repository=RecordingMemoryEmbeddingRepository(),
        embedding_generator=None,
    )

    extracted = bridge._extract_closeout_fields(
        "\n".join(
            [
                "Workflow completed with status `completed`.",
                "Completion summary: Completed summary extraction refinement",
                "Latest checkpoint summary: Compared extracted summary fields",
                "Last planned next action: Add metadata-aware duplicate matching",
                "Verify status: passed",
                "Workflow status: completed",
                "Attempt status: succeeded",
                "Failure reason: none",
            ]
        ),
        fallback_metadata=None,
    )

    assert extracted == {
        "completion_summary": "Completed summary extraction refinement",
        "latest_checkpoint_summary": "Compared extracted summary fields",
        "next_intended_action": "Add metadata-aware duplicate matching",
        "verify_status": "passed",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "failure_reason": "none",
    }


def test_complete_workflow_auto_memory_uses_extracted_and_metadata_fields_for_near_duplicate_matching() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()

    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-METADATA-AWARE-1",
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
            step_name="design_phase2",
            summary="Compared extracted closeout fields",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Refined metadata-aware closeout duplicate detection",
        failure_reason=None,
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-METADATA-AWARE-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.SUCCEEDED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Compared extracted closeout fields again",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Refined duplicate detection with metadata-aware closeout matching",
        failure_reason=None,
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 1
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_does_not_treat_different_attempt_status_as_near_duplicate() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()

    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-ATTEMPT-STATUS-DIFF-1",
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
            step_name="design_phase2",
            summary="Compared weighted closeout fields",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Completed weighted duplicate matching refinement",
        failure_reason=None,
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-ATTEMPT-STATUS-DIFF-1",
            status=WorkflowInstanceStatus.COMPLETED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.FAILED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Compared weighted closeout fields again",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.PASSED,
            report_json={"checks": ["planning"], "status": "passed"},
        ),
        summary="Completed weighted closeout duplicate matching refinement",
        failure_reason=None,
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 2
    assert episode_repository.episodes[1].metadata["attempt_status"] == "failed"


def test_complete_workflow_auto_memory_does_not_treat_different_failure_reason_as_near_duplicate() -> (
    None
):
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    workflow_id = uuid4()
    attempt_id = uuid4()

    first_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-FAILURE-REASON-DIFF-1",
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_id,
            attempt_number=1,
            status=WorkflowAttemptStatus.FAILED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=attempt_id,
            status=VerifyStatus.FAILED,
            report_json={"checks": ["planning"], "status": "failed"},
        ),
        summary="Failed while refining metadata-aware duplicate matching",
        failure_reason="first failure path",
    )

    assert first_result is not None

    second_result = bridge.record_workflow_completion_memory(
        workflow=WorkflowInstance(
            workflow_instance_id=workflow_id,
            workspace_id=uuid4(),
            ticket_id="AUTO-MEMORY-FAILURE-REASON-DIFF-1",
            status=WorkflowInstanceStatus.FAILED,
        ),
        attempt=WorkflowAttempt(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.FAILED,
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_id,
            attempt_id=uuid4(),
            step_name="design_phase2",
            summary="Compared weighted closeout fields again",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching",
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=uuid4(),
            status=VerifyStatus.FAILED,
            report_json={"checks": ["planning"], "status": "failed"},
        ),
        summary="Failed while refining duplicate matching with metadata-aware fields",
        failure_reason="second failure path",
    )

    assert second_result is not None
    assert second_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "skipped",
        "embedding_generation_skipped_reason": "embedding_persistence_not_configured",
    }
    assert len(episode_repository.episodes) == 2
    assert (
        episode_repository.episodes[1].metadata["failure_reason"]
        == "second failure path"
    )


def test_resume_workflow_returns_resumable_with_projection_warning() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-789",
        )
    )
    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            summary="Checkpoint stored",
            checkpoint_json={"next_intended_action": "Resume implementation"},
        )
    )

    uow.projection_states_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        )
    ] = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.STALE,
        target_path=".agent/resume.json",
        open_failure_count=0,
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert isinstance(resume, WorkflowResume)
    assert resume.workspace.workspace_id == workspace.workspace_id
    assert (
        resume.workflow_instance.workflow_instance_id
        == started.workflow_instance.workflow_instance_id
    )
    assert resume.attempt is not None
    assert resume.attempt.attempt_id == started.attempt.attempt_id
    assert resume.latest_checkpoint is not None
    assert (
        resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.STALE
    assert any(warning.code == "stale_projection" for warning in resume.warnings)
    stale_warning = next(
        warning for warning in resume.warnings if warning.code == "stale_projection"
    )
    assert stale_warning.details["projection_type"] == "resume_json"
    assert resume.next_hint == "Resume implementation"


def test_record_resume_projection_persists_projection_state() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-PROJECTION",
        )
    )

    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert recorded.projection_type == ProjectionArtifactType.RESUME_JSON
    assert recorded.status == ProjectionStatus.FRESH
    assert recorded.target_path == ".agent/resume.json"
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"


def test_record_resume_projection_rejects_empty_target_path() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-PROJECTION-EMPTY",
        )
    )

    try:
        service.record_resume_projection(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path="   ",
            )
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "validation_error"
    else:
        raise AssertionError("Expected validation_error for empty target_path")


def test_record_resume_projection_rejects_workflow_from_another_workspace() -> None:
    service, _ = make_service_and_uow()
    first_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="TICKET-PROJECTION-MISMATCH",
        )
    )

    try:
        service.record_resume_projection(
            RecordProjectionStateInput(
                workspace_id=second_workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.STALE,
                target_path=".agent/resume.json",
            )
        )
    except WorkflowAttemptMismatchError as exc:
        assert exc.code == "workflow_attempt_mismatch"
    else:
        raise AssertionError("Expected WorkflowAttemptMismatchError")


def test_resume_workflow_returns_blocked_when_running_attempt_has_no_checkpoint() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-RESUME-2",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
        )
    )

    assert resume.resumable_status == ResumableStatus.BLOCKED
    assert resume.latest_checkpoint is None
    assert any(
        warning.code == "running_attempt_without_checkpoint"
        for warning in resume.warnings
    )
    assert (
        resume.next_hint == "Create an initial checkpoint to establish resumable state."
    )


def test_resume_helper_branches_cover_terminal_and_warning_paths() -> None:
    service = WorkflowService(lambda: None)

    running_workspace = Workspace(
        workspace_id=uuid4(),
        repo_url="https://example.com/repo.git",
        canonical_path="/tmp/repo",
        default_branch="main",
        metadata={},
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 1, tzinfo=UTC),
    )
    running_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=running_workspace.workspace_id,
        ticket_id="resume-helpers-running",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={},
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 1, tzinfo=UTC),
    )
    running_attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=running_workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        failure_reason=None,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 10, 1, tzinfo=UTC),
        finished_at=None,
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 1, tzinfo=UTC),
    )

    assert (
        service._classify_resumable_status(
            running_workflow,
            None,
            None,
            [ResumeIssue(code="running_workflow_without_attempt", message="missing")],
        )
        == ResumableStatus.INCONSISTENT
    )
    assert (
        service._classify_resumable_status(
            running_workflow,
            None,
            None,
            [],
        )
        == ResumableStatus.BLOCKED
    )
    assert (
        service._classify_resumable_status(
            running_workflow,
            WorkflowAttempt(
                attempt_id=running_attempt.attempt_id,
                workflow_instance_id=running_attempt.workflow_instance_id,
                attempt_number=running_attempt.attempt_number,
                status=WorkflowAttemptStatus.SUCCEEDED,
                failure_reason=None,
                verify_status=running_attempt.verify_status,
                started_at=running_attempt.started_at,
                finished_at=datetime(2024, 10, 2, tzinfo=UTC),
                created_at=running_attempt.created_at,
                updated_at=datetime(2024, 10, 2, tzinfo=UTC),
            ),
            None,
            [],
        )
        == ResumableStatus.BLOCKED
    )
    assert (
        service._classify_resumable_status(
            running_workflow,
            running_attempt,
            None,
            [],
        )
        == ResumableStatus.BLOCKED
    )

    terminal_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=running_workspace.workspace_id,
        ticket_id="resume-helpers-terminal",
        status=WorkflowInstanceStatus.COMPLETED,
        metadata={},
        created_at=datetime(2024, 10, 1, tzinfo=UTC),
        updated_at=datetime(2024, 10, 2, tzinfo=UTC),
    )
    assert (
        service._classify_resumable_status(
            terminal_workflow,
            running_attempt,
            None,
            [],
        )
        == ResumableStatus.TERMINAL
    )

    checkpoint_without_summary = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=running_workflow.workflow_instance_id,
        attempt_id=running_attempt.attempt_id,
        step_name="investigate",
        summary=None,
        checkpoint_json={},
        created_at=datetime(2024, 10, 2, tzinfo=UTC),
    )
    assert (
        service._derive_next_hint(
            terminal_workflow,
            running_attempt,
            checkpoint_without_summary,
            ResumableStatus.TERMINAL,
        )
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            None,
            None,
            ResumableStatus.BLOCKED,
        )
        == "No attempt is available. Inspect workflow consistency before continuing."
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            running_attempt,
            None,
            ResumableStatus.BLOCKED,
        )
        == "Create an initial checkpoint to establish resumable state."
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            running_attempt,
            checkpoint_without_summary,
            ResumableStatus.RESUMABLE,
        )
        == "Resume from step 'investigate'."
    )

    checkpoint_with_summary = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=running_workflow.workflow_instance_id,
        attempt_id=running_attempt.attempt_id,
        step_name="implement",
        summary="Added the missing branch",
        checkpoint_json={},
        created_at=datetime(2024, 10, 2, tzinfo=UTC),
    )
    assert (
        service._derive_next_hint(
            running_workflow,
            running_attempt,
            checkpoint_with_summary,
            ResumableStatus.RESUMABLE,
        )
        == "Resume from step 'implement' using the latest checkpoint summary."
    )

    failed_projection = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FAILED,
        target_path=".ctx/resume.json",
        last_successful_write_at=None,
        last_canonical_update_at=None,
        open_failure_count=0,
    )
    missing_projection = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.MISSING,
        target_path=".ctx/resume.md",
        last_successful_write_at=None,
        last_canonical_update_at=None,
        open_failure_count=0,
    )
    resolved_failure = ProjectionFailureInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        error_code="resolved_error",
        error_message="resolved once",
        target_path=".ctx/resume.json",
        attempt_id=running_attempt.attempt_id,
        occurred_at=datetime(2024, 10, 2, tzinfo=UTC),
        resolved_at=datetime(2024, 10, 3, tzinfo=UTC),
        open_failure_count=0,
        retry_count=1,
        status="resolved",
    )

    warnings = service._build_resume_warnings(
        running_workflow,
        running_attempt,
        checkpoint_with_summary,
        None,
        (failed_projection, missing_projection),
        [],
        [resolved_failure],
    )
    warning_codes = {warning.code for warning in warnings}
    assert "missing_verify_report" in warning_codes
    assert "resolved_projection_failure" in warning_codes
    assert "missing_projection" in warning_codes


def test_resume_workflow_returns_terminal_for_completed_workflow() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="TICKET-DONE",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="done_step",
            checkpoint_json={"next_intended_action": "Nothing"},
        )
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.TERMINAL
    assert (
        resume.next_hint
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )


def test_resume_workflow_terminal_result_is_for_inspection_not_continuation() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INSPECT-ONLY",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="finalize",
            checkpoint_json={"next_intended_action": "No further execution"},
        )
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.TERMINAL
    assert resume.attempt is not None
    assert resume.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert resume.latest_checkpoint is not None
    assert resume.latest_checkpoint.step_name == "finalize"
    assert (
        resume.next_hint
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )


def test_resume_workflow_raises_for_unknown_workflow() -> None:
    service, _ = make_service_and_uow()

    try:
        service.resume_workflow(ResumeWorkflowInput(workflow_instance_id=uuid4()))
    except WorkflowNotFoundError as exc:
        assert exc.code == "workflow_not_found"
    else:
        raise AssertionError("Expected WorkflowNotFoundError")


def test_resume_workflow_rejects_workspace_id_misuse() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    try:
        service.resume_workflow(
            ResumeWorkflowInput(workflow_instance_id=workspace.workspace_id)
        )
    except ValidationError as exc:
        assert exc.code == "validation_error"
        assert (
            str(exc)
            == "provided workflow_instance_id appears to be a workspace_id; use "
            "workspace://{workspace_id}/resume or provide a real "
            "workflow_instance_id"
        )
        assert exc.details == {
            "workflow_instance_id": str(workspace.workspace_id),
            "workspace_id": str(workspace.workspace_id),
        }
    else:
        raise AssertionError("Expected ValidationError")


def test_start_workflow_raises_for_unknown_workspace() -> None:
    service, _ = make_service_and_uow()

    try:
        service.start_workflow(
            StartWorkflowInput(workspace_id=uuid4(), ticket_id="MISSING")
        )
    except WorkspaceNotFoundError as exc:
        assert exc.code == "workspace_not_found"
    else:
        raise AssertionError("Expected WorkspaceNotFoundError")


def test_create_checkpoint_raises_for_unknown_attempt() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="KNOWN")
    )

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=uuid4(),
                step_name="missing_attempt",
            )
        )
    except AttemptNotFoundError as exc:
        assert exc.code == "attempt_not_found"
    else:
        raise AssertionError("Expected AttemptNotFoundError")


def test_complete_workflow_rejects_non_terminal_target_status() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="OPEN")
    )

    try:
        service.complete_workflow(
            CompleteWorkflowInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                workflow_status=WorkflowInstanceStatus.RUNNING,
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
        assert "non-terminal state" in str(exc)
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_resume_workflow_returns_inconsistent_without_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NO-ATTEMPT",
        )
    )

    uow.attempts_by_id.pop(started.attempt.attempt_id, None)

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.attempt is None
    assert resume.resumable_status == ResumableStatus.INCONSISTENT
    assert any(
        warning.code == "running_workflow_without_attempt"
        for warning in resume.warnings
    )
    assert (
        resume.next_hint
        == "No attempt is available. Inspect workflow consistency before continuing."
    )


def test_resume_workflow_returns_blocked_for_non_running_latest_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="STOPPED-ATTEMPT",
        )
    )

    stopped_attempt = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=WorkflowAttemptStatus.FAILED,
        failure_reason="stopped",
        verify_status=started.attempt.verify_status,
        started_at=started.attempt.started_at,
        finished_at=datetime(2024, 1, 1, tzinfo=UTC),
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[stopped_attempt.attempt_id] = stopped_attempt

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.attempt is not None
    assert resume.attempt.status == WorkflowAttemptStatus.FAILED
    assert resume.resumable_status == ResumableStatus.BLOCKED


def test_resume_workflow_adds_missing_verify_report_warning() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="VERIFY-WARNING",
        )
    )

    attempt_with_verify = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=started.attempt.status,
        failure_reason=started.attempt.failure_reason,
        verify_status=VerifyStatus.PASSED,
        started_at=started.attempt.started_at,
        finished_at=started.attempt.finished_at,
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[attempt_with_verify.attempt_id] = attempt_with_verify

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    missing_verify_warning = next(
        warning
        for warning in resume.warnings
        if warning.code == "missing_verify_report"
    )
    assert missing_verify_warning.details == {
        "attempt_id": str(started.attempt.attempt_id)
    }


def test_resume_workflow_adds_open_projection_failure_warning_details() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="OPEN-PROJECTION",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
        )
    )

    uow.projection_states_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        )
    ] = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FAILED,
        target_path=".agent/resume.json",
        open_failure_count=2,
    )
    uow.projection_failures_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        )
    ] = [
        ProjectionFailureInfo(
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_code="io_error",
            error_message="write failed",
            occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
            resolved_at=None,
            open_failure_count=2,
            retry_count=1,
            status="open",
        )
    ]

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    warning = next(
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    )
    assert warning.details["projection_type"] == "resume_json"
    assert warning.details["target_path"] == ".agent/resume.json"
    assert warning.details["open_failure_count"] == 2
    assert warning.details["failures"] == [
        {
            "projection_type": "resume_json",
            "target_path": ".agent/resume.json",
            "attempt_id": str(started.attempt.attempt_id),
            "error_code": "io_error",
            "error_message": "write failed",
            "occurred_at": "2024-01-01T00:00:00+00:00",
            "resolved_at": None,
            "open_failure_count": 2,
            "retry_count": 1,
            "status": "open",
        }
    ]


def test_resume_workflow_adds_missing_projection_warning() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="MISSING-PROJECTION",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
        )
    )

    uow.projection_states_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_MD,
        )
    ] = ProjectionInfo(
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.MISSING,
        target_path=".agent/resume.md",
        open_failure_count=0,
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    warning = next(
        warning for warning in resume.warnings if warning.code == "missing_projection"
    )
    assert warning.details == {
        "projection_type": "resume_md",
        "target_path": ".agent/resume.md",
    }


def test_build_resume_warnings_returns_resolved_projection_failure_warning() -> None:
    service, _ = make_service_and_uow()

    workflow = SimpleNamespace(status=WorkflowInstanceStatus.RUNNING)
    attempt = SimpleNamespace(
        attempt_id=uuid4(),
        status=WorkflowAttemptStatus.RUNNING,
        verify_status=None,
    )
    latest_checkpoint = SimpleNamespace()
    projections = (
        ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
            open_failure_count=0,
        ),
    )
    closed_projection_failures = [
        ProjectionFailureInfo(
            attempt_id=uuid4(),
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_code="io_error",
            error_message="resolved write failure",
            occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
            resolved_at=datetime(2024, 1, 2, tzinfo=UTC),
            open_failure_count=0,
            retry_count=1,
            status="resolved",
        )
    ]

    warnings = service._build_resume_warnings(
        workflow,
        attempt,
        latest_checkpoint,
        None,
        projections,
        [],
        closed_projection_failures,
    )

    warning = next(
        item for item in warnings if item.code == "resolved_projection_failure"
    )
    assert warning.message == "resume projection has previously resolved write failures"
    assert warning.details["projection_type"] == "resume_json"
    assert warning.details["target_path"] == ".agent/resume.json"
    assert warning.details["open_failure_count"] == 0
    assert warning.details["failures"][0]["status"] == "resolved"


def test_derive_next_hint_uses_summary_when_next_action_missing() -> None:
    service, _ = make_service_and_uow()

    hint = service._derive_next_hint(
        SimpleNamespace(is_terminal=False),
        SimpleNamespace(),
        SimpleNamespace(
            step_name="implement_feature",
            summary="Continue implementation",
            checkpoint_json={},
        ),
        ResumableStatus.RESUMABLE,
    )

    assert (
        hint
        == "Resume from step 'implement_feature' using the latest checkpoint summary."
    )


def test_derive_next_hint_uses_step_name_when_summary_missing() -> None:
    service, _ = make_service_and_uow()

    hint = service._derive_next_hint(
        SimpleNamespace(is_terminal=False),
        SimpleNamespace(),
        SimpleNamespace(
            step_name="implement_feature",
            summary=None,
            checkpoint_json={},
        ),
        ResumableStatus.RESUMABLE,
    )

    assert hint == "Resume from step 'implement_feature'."


def test_validate_helpers_reject_empty_values() -> None:
    service, _ = make_service_and_uow()

    with pytest.raises(Exception, match="repo_url must not be empty"):
        service._validate_workspace_input(
            RegisterWorkspaceInput(
                repo_url="   ",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )

    with pytest.raises(Exception, match="canonical_path must not be empty"):
        service._validate_workspace_input(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/repo.git",
                canonical_path="   ",
                default_branch="main",
            )
        )

    with pytest.raises(Exception, match="default_branch must not be empty"):
        service._validate_workspace_input(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/repo.git",
                canonical_path="/tmp/repo",
                default_branch="   ",
            )
        )

    with pytest.raises(Exception, match="ticket_id must not be empty"):
        service._validate_ticket_id("   ")

    with pytest.raises(Exception, match="step_name must not be empty"):
        service._validate_step_name("   ")


def test_register_workspace_updates_existing_workspace_with_explicit_workspace_id() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    updated = service.register_workspace(
        RegisterWorkspaceInput(
            workspace_id=workspace.workspace_id,
            repo_url=workspace.repo_url,
            canonical_path=workspace.canonical_path,
            default_branch="develop",
            metadata={"team": "platform"},
        )
    )

    assert updated.workspace_id == workspace.workspace_id
    assert updated.repo_url == workspace.repo_url
    assert updated.canonical_path == workspace.canonical_path
    assert updated.default_branch == "develop"
    assert updated.metadata == {"team": "platform"}
    assert updated.created_at == workspace.created_at
    assert updated.updated_at >= workspace.updated_at


def test_register_workspace_rejects_repo_url_conflict_without_workspace_id() -> None:
    service, _ = make_service_and_uow()
    register_workspace(service)

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/repo.git",
                canonical_path="/tmp/another-repo",
                default_branch="main",
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "repo_url" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_register_workspace_raises_when_explicit_workspace_id_is_unknown() -> None:
    service, _ = make_service_and_uow()

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                workspace_id=uuid4(),
                repo_url="https://example.com/org/repo.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )
    except WorkspaceNotFoundError as exc:
        assert exc.code == "workspace_not_found"
    else:
        raise AssertionError("Expected WorkspaceNotFoundError")


def test_register_workspace_rejects_canonical_path_belonging_to_another_workspace() -> (
    None
):
    service, _ = make_service_and_uow()
    first = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                workspace_id=second.workspace_id,
                repo_url=second.repo_url,
                canonical_path=first.canonical_path,
                default_branch=second.default_branch,
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "canonical_path belongs to another workspace" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_register_workspace_rejects_repo_url_belonging_to_another_workspace() -> None:
    service, _ = make_service_and_uow()
    first = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                workspace_id=second.workspace_id,
                repo_url=first.repo_url,
                canonical_path=second.canonical_path,
                default_branch=second.default_branch,
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "repo_url belongs to another workspace" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_create_checkpoint_rejects_terminal_workflow() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="DONE")
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="after_terminal",
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
        assert "terminal workflow" in str(exc)
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_create_checkpoint_rejects_terminal_attempt() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="MANUAL")
    )

    terminal_attempt = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=WorkflowAttemptStatus.FAILED,
        failure_reason="manual override",
        verify_status=started.attempt.verify_status,
        started_at=started.attempt.started_at,
        finished_at=datetime(2024, 1, 1, tzinfo=UTC),
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[terminal_attempt.attempt_id] = terminal_attempt

    try:
        service.create_checkpoint(
            CreateCheckpointInput(
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="after_failed_attempt",
            )
        )
    except InvalidStateTransitionError as exc:
        assert exc.code == "invalid_state_transition"
        assert "terminal attempt" in str(exc)
    else:
        raise AssertionError("Expected InvalidStateTransitionError")


def test_completed_workflow_requires_new_workflow_for_additional_work() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    first = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="CLOSED-1")
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=first.workflow_instance.workflow_instance_id,
            attempt_id=first.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    second = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="CLOSED-2")
    )

    assert (
        second.workflow_instance.workflow_instance_id
        != first.workflow_instance.workflow_instance_id
    )
    assert second.workflow_instance.status == WorkflowInstanceStatus.RUNNING
    assert second.attempt.status == WorkflowAttemptStatus.RUNNING
    assert second.attempt.attempt_number == 1


def test_record_resume_projection_raises_when_projection_repository_is_unavailable() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NO-PROJECTION-REPO",
        )
    )

    class MissingProjectionStateUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda workspace_id: (
                    workspace if workspace_id == workspace.workspace_id else None
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda workflow_instance_id: (
                    started.workflow_instance
                    if workflow_instance_id
                    == started.workflow_instance.workflow_instance_id
                    else None
                )
            )
            self.projection_states = None

        def __enter__(self) -> "MissingProjectionStateUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    unavailable_service = WorkflowService(lambda: MissingProjectionStateUow())

    try:
        unavailable_service.record_resume_projection(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
            )
        )
    except Exception as exc:
        assert "projection state repository is not available" in str(exc)
    else:
        raise AssertionError("Expected PersistenceError")


def test_record_resume_projection_failure_raises_when_projection_repository_is_unavailable() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NO-FAILURE-REPO",
        )
    )

    class MissingProjectionFailureUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda workspace_id: (
                    workspace if workspace_id == workspace.workspace_id else None
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda workflow_instance_id: (
                    started.workflow_instance
                    if workflow_instance_id
                    == started.workflow_instance.workflow_instance_id
                    else None
                )
            )
            self.projection_failures = None

        def __enter__(self) -> "MissingProjectionFailureUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    unavailable_service = WorkflowService(lambda: MissingProjectionFailureUow())

    try:
        unavailable_service.record_resume_projection_failure(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path=".agent/resume.json",
                error_message="write failed",
            )
        )
    except Exception as exc:
        assert "projection failure repository is not available" in str(exc)
    else:
        raise AssertionError("Expected PersistenceError")


def test_record_resume_projection_failure_rejects_empty_error_message() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="EMPTY-ERROR",
        )
    )

    try:
        service.record_resume_projection_failure(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path=".agent/resume.json",
                error_message="   ",
            )
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "validation_error"
    else:
        raise AssertionError("Expected validation_error for empty error_message")


def test_resolve_resume_projection_failures_raises_when_projection_repository_is_unavailable() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NO-RESOLVE-REPO",
        )
    )

    class MissingProjectionFailureUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda workspace_id: (
                    workspace if workspace_id == workspace.workspace_id else None
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda workflow_instance_id: (
                    started.workflow_instance
                    if workflow_instance_id
                    == started.workflow_instance.workflow_instance_id
                    else None
                )
            )
            self.projection_failures = None

        def __enter__(self) -> "MissingProjectionFailureUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    unavailable_service = WorkflowService(lambda: MissingProjectionFailureUow())

    try:
        unavailable_service.resolve_resume_projection_failures(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
        )
    except Exception as exc:
        assert "projection failure repository is not available" in str(exc)
    else:
        raise AssertionError("Expected PersistenceError")


def test_ignore_resume_projection_failures_raises_when_projection_repository_is_unavailable() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NO-IGNORE-REPO",
        )
    )

    class MissingProjectionFailureUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda workspace_id: (
                    workspace if workspace_id == workspace.workspace_id else None
                )
            )
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda workflow_instance_id: (
                    started.workflow_instance
                    if workflow_instance_id
                    == started.workflow_instance.workflow_instance_id
                    else None
                )
            )
            self.projection_failures = None

        def __enter__(self) -> "MissingProjectionFailureUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    unavailable_service = WorkflowService(lambda: MissingProjectionFailureUow())

    try:
        unavailable_service.ignore_resume_projection_failures(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
        )
    except Exception as exc:
        assert "projection failure repository is not available" in str(exc)
    else:
        raise AssertionError("Expected PersistenceError")


def test_record_resume_projection_normalizes_input_before_persisting() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="NORMALIZE-PROJECTION",
        )
    )

    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path="  .agent/resume.json  ",
            last_successful_write_at=datetime(2024, 1, 1, tzinfo=UTC),
            last_canonical_update_at=datetime(2024, 1, 2, tzinfo=UTC),
        )
    )

    assert recorded.target_path == "  .agent/resume.json  "
    assert recorded.last_successful_write_at == datetime(2024, 1, 1, tzinfo=UTC)
    assert recorded.last_canonical_update_at == datetime(2024, 1, 2, tzinfo=UTC)


def test_record_resume_projection_failure_rejects_empty_target_path() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="EMPTY-TARGET-PATH",
        )
    )

    with pytest.raises(ValidationError, match="target_path must not be empty"):
        service.record_resume_projection_failure(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path="   ",
                error_message="write failed",
            )
        )


def test_record_resume_projection_failure_rejects_workflow_from_another_workspace() -> (
    None
):
    service, _ = make_service_and_uow()
    first_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="FAILURE-MISMATCH",
        )
    )

    with pytest.raises(
        WorkflowAttemptMismatchError,
        match="workflow does not belong to workspace",
    ):
        service.record_resume_projection_failure(
            RecordProjectionFailureInput(
                workspace_id=second_workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path=".agent/resume.json",
                error_message="write failed",
            )
        )


def test_resolve_resume_projection_failures_rejects_workflow_from_another_workspace() -> (
    None
):
    service, _ = make_service_and_uow()
    first_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="RESOLVE-MISMATCH",
        )
    )

    with pytest.raises(
        WorkflowAttemptMismatchError,
        match="workflow does not belong to workspace",
    ):
        service.resolve_resume_projection_failures(
            workspace_id=second_workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
        )


def test_ignore_resume_projection_failures_rejects_workflow_from_another_workspace() -> (
    None
):
    service, _ = make_service_and_uow()
    first_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second_workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="IGNORE-MISMATCH",
        )
    )

    with pytest.raises(
        WorkflowAttemptMismatchError,
        match="workflow does not belong to workspace",
    ):
        service.ignore_resume_projection_failures(
            workspace_id=second_workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
        )


def test_reconcile_resume_projection_resolves_each_projection_once_and_records_failures() -> (
    None
):
    resolve_calls: list[tuple[object, object, object]] = []
    record_calls: list[RecordProjectionStateInput] = []
    failure_calls: list[RecordProjectionFailureInput] = []

    success_json = RecordProjectionStateInput(
        workspace_id=uuid4(),
        workflow_instance_id=uuid4(),
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.json",
    )
    success_md_first = RecordProjectionStateInput(
        workspace_id=success_json.workspace_id,
        workflow_instance_id=success_json.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.STALE,
        target_path=".agent/resume.md",
    )
    success_md_second = RecordProjectionStateInput(
        workspace_id=success_json.workspace_id,
        workflow_instance_id=success_json.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.md",
    )
    failure = RecordProjectionFailureInput(
        workspace_id=success_json.workspace_id,
        workflow_instance_id=success_json.workflow_instance_id,
        attempt_id=uuid4(),
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        error_message="write failed",
    )

    service = WorkflowService(lambda: None)

    def fake_resolve_resume_projection_failures(
        *,
        workspace_id,
        workflow_instance_id,
        projection_type=None,
    ) -> int:
        resolve_calls.append((workspace_id, workflow_instance_id, projection_type))
        return 1

    def fake_record_resume_projection(
        data: RecordProjectionStateInput,
    ) -> ProjectionInfo:
        record_calls.append(data)
        return ProjectionInfo(
            projection_type=data.projection_type,
            status=data.status,
            target_path=data.target_path,
            last_successful_write_at=data.last_successful_write_at,
            last_canonical_update_at=data.last_canonical_update_at,
            open_failure_count=0,
        )

    def fake_record_resume_projection_failure(
        data: RecordProjectionFailureInput,
    ) -> ProjectionFailureInfo:
        failure_calls.append(data)
        return ProjectionFailureInfo(
            projection_type=data.projection_type,
            error_code=data.error_code,
            error_message=data.error_message,
            target_path=data.target_path,
            attempt_id=data.attempt_id,
            open_failure_count=1,
            retry_count=0,
            status="open",
        )

    service.resolve_resume_projection_failures = (  # type: ignore[method-assign]
        fake_resolve_resume_projection_failures
    )
    service.record_resume_projection = fake_record_resume_projection  # type: ignore[method-assign]
    service.record_resume_projection_failure = (  # type: ignore[method-assign]
        fake_record_resume_projection_failure
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(success_json, success_md_first, success_md_second),
        failure_updates=(failure,),
    )

    assert [projection.projection_type for projection in reconciled] == [
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
        ProjectionArtifactType.RESUME_MD,
    ]
    assert resolve_calls == [
        (
            success_json.workspace_id,
            success_json.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        ),
        (
            success_md_first.workspace_id,
            success_md_first.workflow_instance_id,
            ProjectionArtifactType.RESUME_MD,
        ),
    ]
    assert record_calls == [success_json, success_md_first, success_md_second]
    assert failure_calls == [failure]


def test_complete_workflow_without_verify_status_preserves_attempt_verify_status() -> (
    None
):
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(workspace_id=workspace.workspace_id, ticket_id="KEEP-VERIFY")
    )

    attempt_with_verify = WorkflowAttempt(
        attempt_id=started.attempt.attempt_id,
        workflow_instance_id=started.attempt.workflow_instance_id,
        attempt_number=started.attempt.attempt_number,
        status=started.attempt.status,
        failure_reason=started.attempt.failure_reason,
        verify_status=VerifyStatus.SKIPPED,
        started_at=started.attempt.started_at,
        finished_at=started.attempt.finished_at,
        created_at=started.attempt.created_at,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    uow.attempts_by_id[attempt_with_verify.attempt_id] = attempt_with_verify

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.FAILED,
            failure_reason="tests failed",
        )
    )

    assert result.attempt.verify_status == VerifyStatus.SKIPPED
    assert result.attempt.failure_reason == "tests failed"
    assert result.verify_report is None


def test_build_resume_warnings_adds_open_and_ignored_projection_failure_variants() -> (
    None
):
    service, _ = make_service_and_uow()

    workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="WARN-1",
        status=WorkflowInstanceStatus.RUNNING,
    )
    attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_id=attempt.attempt_id,
        step_name="resume",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    latest_verify_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt.attempt_id,
        status=VerifyStatus.PASSED,
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    projections = (
        ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
            open_failure_count=2,
        ),
    )
    open_projection_failures = [
        ProjectionFailureInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            error_code="io_error",
            error_message="open failure",
            target_path=".agent/resume.json",
            attempt_id=attempt.attempt_id,
            occurred_at=datetime(2024, 1, 4, tzinfo=UTC),
            open_failure_count=2,
            retry_count=1,
            status="open",
        )
    ]
    closed_projection_failures = [
        ProjectionFailureInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            error_code="ignore_error",
            error_message="ignored failure",
            target_path=".agent/resume.json",
            attempt_id=attempt.attempt_id,
            occurred_at=datetime(2024, 1, 5, tzinfo=UTC),
            resolved_at=datetime(2024, 1, 6, tzinfo=UTC),
            open_failure_count=0,
            retry_count=2,
            status="ignored",
        )
    ]

    warnings = service._build_resume_warnings(
        workflow,
        attempt,
        latest_checkpoint,
        latest_verify_report,
        projections,
        open_projection_failures,
        closed_projection_failures,
    )

    open_warning = next(
        warning for warning in warnings if warning.code == "open_projection_failure"
    )

    assert open_warning.details["projection_type"] == "resume_json"
    assert open_warning.details["open_failure_count"] == 2
    assert open_warning.details["failures"][0]["status"] == "open"


def test_build_resume_warnings_adds_ignored_projection_failure_variant() -> None:
    service, _ = make_service_and_uow()

    workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="WARN-IGNORED-1",
        status=WorkflowInstanceStatus.RUNNING,
    )
    attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_id=attempt.attempt_id,
        step_name="resume",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    latest_verify_report = VerifyReport(
        verify_id=uuid4(),
        attempt_id=attempt.attempt_id,
        status=VerifyStatus.PASSED,
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    projections = (
        ProjectionInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
            open_failure_count=0,
        ),
    )
    closed_projection_failures = [
        ProjectionFailureInfo(
            projection_type=ProjectionArtifactType.RESUME_JSON,
            error_code="ignore_error",
            error_message="ignored failure",
            target_path=".agent/resume.json",
            attempt_id=attempt.attempt_id,
            occurred_at=datetime(2024, 1, 5, tzinfo=UTC),
            resolved_at=datetime(2024, 1, 6, tzinfo=UTC),
            open_failure_count=0,
            retry_count=2,
            status="ignored",
        )
    ]

    warnings = service._build_resume_warnings(
        workflow,
        attempt,
        latest_checkpoint,
        latest_verify_report,
        projections,
        [],
        closed_projection_failures,
    )

    ignored_warning = next(
        warning for warning in warnings if warning.code == "ignored_projection_failure"
    )

    assert ignored_warning.details["projection_type"] == "resume_json"
    assert ignored_warning.details["open_failure_count"] == 0
    assert ignored_warning.details["failures"][0]["status"] == "ignored"


def test_classify_resumable_status_returns_resumable_for_projection_warnings() -> None:
    service, _ = make_service_and_uow()

    workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="CLASSIFY-1",
        status=WorkflowInstanceStatus.RUNNING,
    )
    attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    latest_checkpoint = WorkflowCheckpoint(
        checkpoint_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_id=attempt.attempt_id,
        step_name="resume",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    stale_status = service._classify_resumable_status(
        workflow,
        attempt,
        latest_checkpoint,
        [ResumeIssue(code="stale_projection", message="stale")],
    )
    open_failure_status = service._classify_resumable_status(
        workflow,
        attempt,
        latest_checkpoint,
        [ResumeIssue(code="open_projection_failure", message="open failure")],
    )

    assert stale_status == ResumableStatus.RESUMABLE
    assert open_failure_status == ResumableStatus.RESUMABLE


def test_derive_next_hint_covers_inconsistent_and_blocked_without_checkpoint() -> None:
    service, _ = make_service_and_uow()

    workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        ticket_id="HINT-1",
        status=WorkflowInstanceStatus.RUNNING,
    )
    running_attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_number=1,
        status=WorkflowAttemptStatus.RUNNING,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    inconsistent_hint = service._derive_next_hint(
        workflow,
        None,
        None,
        ResumableStatus.INCONSISTENT,
    )
    blocked_without_checkpoint_hint = service._derive_next_hint(
        workflow,
        running_attempt,
        None,
        ResumableStatus.BLOCKED,
    )

    assert (
        inconsistent_hint
        == "No attempt is available. Inspect workflow consistency before continuing."
    )
    assert (
        blocked_without_checkpoint_hint
        == "Create an initial checkpoint to establish resumable state."
    )


def test_workflow_error_hierarchy_exposes_expected_codes_and_details() -> None:
    validation_error = ValidationError(
        "validation failed",
        details={"field": "ticket_id"},
    )
    workspace_not_found = WorkspaceNotFoundError(
        "workspace not found",
        details={"workspace_id": "abc"},
    )
    workflow_not_found = WorkflowNotFoundError(
        "workflow not found",
        details={"workflow_instance_id": "wf-1"},
    )
    attempt_not_found = AttemptNotFoundError(
        "attempt not found",
        details={"attempt_id": "att-1"},
    )
    active_workflow_exists = ActiveWorkflowExistsError(
        "workspace already has a running workflow",
        details={"workspace_id": "ws-1"},
    )
    workspace_conflict = WorkspaceRegistrationConflictError(
        "repo_url belongs to another workspace",
        details={"repo_url": "https://example.com/repo.git"},
    )
    invalid_transition = InvalidStateTransitionError(
        "workflow is already terminal",
        details={"status": "completed"},
    )
    workflow_attempt_mismatch = WorkflowAttemptMismatchError(
        "attempt does not belong to workflow",
        details={"attempt_id": "att-2"},
    )

    assert isinstance(validation_error, WorkflowError)
    assert validation_error.code == "validation_error"
    assert validation_error.details == {"field": "ticket_id"}

    assert workspace_not_found.code == "workspace_not_found"
    assert workspace_not_found.details == {"workspace_id": "abc"}

    assert workflow_not_found.code == "workflow_not_found"
    assert workflow_not_found.details == {"workflow_instance_id": "wf-1"}

    assert attempt_not_found.code == "attempt_not_found"
    assert attempt_not_found.details == {"attempt_id": "att-1"}

    assert active_workflow_exists.code == "active_workflow_exists"
    assert active_workflow_exists.details == {"workspace_id": "ws-1"}

    assert workspace_conflict.code == "workspace_registration_conflict"
    assert workspace_conflict.details == {"repo_url": "https://example.com/repo.git"}

    assert invalid_transition.code == "invalid_state_transition"
    assert invalid_transition.details == {"status": "completed"}

    assert workflow_attempt_mismatch.code == "workflow_attempt_mismatch"
    assert workflow_attempt_mismatch.details == {"attempt_id": "att-2"}


def test_repository_contract_base_classes_raise_not_implemented() -> None:
    from ctxledger.workflow.service import (
        ProjectionFailureRepository,
        ProjectionStateRepository,
        UnitOfWork,
        VerifyReportRepository,
        WorkflowAttemptRepository,
        WorkflowCheckpointRepository,
        WorkflowInstanceRepository,
        WorkspaceRepository,
    )

    workspace_repo = WorkspaceRepository()
    workflow_repo = WorkflowInstanceRepository()
    attempt_repo = WorkflowAttemptRepository()
    checkpoint_repo = WorkflowCheckpointRepository()
    verify_repo = VerifyReportRepository()
    projection_state_repo = ProjectionStateRepository()
    projection_failure_repo = ProjectionFailureRepository()
    uow = UnitOfWork()

    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    attempt_id = uuid4()
    projection = RecordProjectionStateInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.json",
    )
    failure = RecordProjectionFailureInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        attempt_id=attempt_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        error_message="write failed",
    )

    with pytest.raises(NotImplementedError):
        workspace_repo.get_by_id(workspace_id)
    with pytest.raises(NotImplementedError):
        workspace_repo.get_by_canonical_path("/tmp/repo")
    with pytest.raises(NotImplementedError):
        workspace_repo.get_by_repo_url("https://example.com/repo.git")
    with pytest.raises(NotImplementedError):
        workspace_repo.create(
            Workspace(
                workspace_id=workspace_id,
                repo_url="https://example.com/repo.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )
    with pytest.raises(NotImplementedError):
        workspace_repo.update(
            Workspace(
                workspace_id=workspace_id,
                repo_url="https://example.com/repo.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )

    with pytest.raises(NotImplementedError):
        workflow_repo.get_by_id(workflow_instance_id)
    with pytest.raises(NotImplementedError):
        workflow_repo.get_running_by_workspace_id(workspace_id)
    with pytest.raises(NotImplementedError):
        workflow_repo.get_latest_by_workspace_id(workspace_id)
    with pytest.raises(NotImplementedError):
        workflow_repo.create(
            WorkflowInstance(
                workflow_instance_id=workflow_instance_id,
                workspace_id=workspace_id,
                ticket_id="WF-1",
                status=WorkflowInstanceStatus.RUNNING,
            )
        )
    with pytest.raises(NotImplementedError):
        workflow_repo.update(
            WorkflowInstance(
                workflow_instance_id=workflow_instance_id,
                workspace_id=workspace_id,
                ticket_id="WF-1",
                status=WorkflowInstanceStatus.RUNNING,
            )
        )

    with pytest.raises(NotImplementedError):
        attempt_repo.get_by_id(attempt_id)
    with pytest.raises(NotImplementedError):
        attempt_repo.get_running_by_workflow_id(workflow_instance_id)
    with pytest.raises(NotImplementedError):
        attempt_repo.get_latest_by_workflow_id(workflow_instance_id)
    with pytest.raises(NotImplementedError):
        attempt_repo.get_next_attempt_number(workflow_instance_id)
    with pytest.raises(NotImplementedError):
        attempt_repo.create(
            WorkflowAttempt(
                attempt_id=attempt_id,
                workflow_instance_id=workflow_instance_id,
                attempt_number=1,
                status=WorkflowAttemptStatus.RUNNING,
                started_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
    with pytest.raises(NotImplementedError):
        attempt_repo.update(
            WorkflowAttempt(
                attempt_id=attempt_id,
                workflow_instance_id=workflow_instance_id,
                attempt_number=1,
                status=WorkflowAttemptStatus.RUNNING,
                started_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )

    with pytest.raises(NotImplementedError):
        checkpoint_repo.get_latest_by_workflow_id(workflow_instance_id)
    with pytest.raises(NotImplementedError):
        checkpoint_repo.get_latest_by_attempt_id(attempt_id)
    with pytest.raises(NotImplementedError):
        checkpoint_repo.create(
            WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=workflow_instance_id,
                attempt_id=attempt_id,
                step_name="checkpoint",
            )
        )

    with pytest.raises(NotImplementedError):
        verify_repo.get_latest_by_attempt_id(attempt_id)
    with pytest.raises(NotImplementedError):
        verify_repo.create(
            VerifyReport(
                verify_id=uuid4(),
                attempt_id=attempt_id,
                status=VerifyStatus.PASSED,
            )
        )

    with pytest.raises(NotImplementedError):
        projection_state_repo.get_resume_projections(workspace_id, workflow_instance_id)
    with pytest.raises(NotImplementedError):
        projection_state_repo.record_resume_projection(projection)

    with pytest.raises(NotImplementedError):
        projection_failure_repo.get_open_failures_by_workflow_id(
            workspace_id, workflow_instance_id
        )
    with pytest.raises(NotImplementedError):
        projection_failure_repo.get_closed_failures_by_workflow_id(
            workspace_id, workflow_instance_id
        )
    with pytest.raises(NotImplementedError):
        projection_failure_repo.record_resume_projection_failure(failure)
    with pytest.raises(NotImplementedError):
        projection_failure_repo.resolve_resume_projection_failures(
            workspace_id,
            workflow_instance_id,
        )
    with pytest.raises(NotImplementedError):
        projection_failure_repo.ignore_resume_projection_failures(
            workspace_id,
            workflow_instance_id,
        )

    assert uow.__enter__() is uow
    assert uow.__exit__(None, None, None) is None
    with pytest.raises(NotImplementedError):
        uow.commit()
    with pytest.raises(NotImplementedError):
        uow.rollback()


def test_complete_workflow_writes_verify_report_when_requested() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="VERIFY-REPORT-ON-COMPLETE",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.CANCELLED,
            verify_status=VerifyStatus.SKIPPED,
            verify_report={"reason": "manual-stop"},
        )
    )

    assert result.workflow_instance.status == WorkflowInstanceStatus.CANCELLED
    assert result.attempt.status == WorkflowAttemptStatus.CANCELLED
    assert result.attempt.verify_status == VerifyStatus.SKIPPED
    assert result.verify_report is not None
    assert result.verify_report.status == VerifyStatus.SKIPPED
    assert result.verify_report.report_json == {"reason": "manual-stop"}


def test_record_resume_projection_fresh_status_fills_missing_timestamps() -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="FRESH-TIMESTAMPS",
        )
    )

    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
            last_successful_write_at=None,
            last_canonical_update_at=None,
        )
    )

    assert recorded.last_successful_write_at is not None
    assert recorded.last_canonical_update_at is not None
    assert recorded.last_canonical_update_at == recorded.last_successful_write_at
    assert recorded.open_failure_count == 0


def test_repository_contract_base_methods_cover_remaining_not_implemented_branches() -> (
    None
):
    from ctxledger.workflow.service import (
        MemoryEmbeddingRepository,
        MemoryEpisodeRepository,
        MemoryItemRepository,
        ProjectionFailureRepository,
        WorkflowInstanceRepository,
    )

    episode_repo = MemoryEpisodeRepository()
    workflow_repo = WorkflowInstanceRepository()
    projection_failure_repo = ProjectionFailureRepository()
    memory_item_repo = MemoryItemRepository()
    memory_embedding_repo = MemoryEmbeddingRepository()

    with pytest.raises(NotImplementedError):
        episode_repo.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=uuid4(),
                summary="episode",
            )
        )

    with pytest.raises(NotImplementedError):
        episode_repo.list_by_workflow_id(uuid4(), limit=1)

    with pytest.raises(NotImplementedError):
        workflow_repo.list_by_workspace_id(uuid4(), limit=1)

    with pytest.raises(NotImplementedError):
        workflow_repo.list_by_ticket_id("TICKET-1", limit=1)

    with pytest.raises(NotImplementedError):
        workflow_repo.list_recent(limit=1)

    with pytest.raises(NotImplementedError):
        projection_failure_repo.list_failures(limit=1)

    with pytest.raises(NotImplementedError):
        memory_item_repo.count_by_provenance()

    with pytest.raises(NotImplementedError):
        memory_embedding_repo.list_by_memory_id(uuid4(), limit=1)


def test_status_count_dict_and_grouped_status_zero_fill_behavior() -> None:
    from ctxledger.workflow.service import _status_count_dict

    counts = _status_count_dict(
        ("running", "completed", "failed"),
        {"running": 2, "failed": 1, "ignored": 99},
    )

    assert counts == {
        "running": 2,
        "completed": 0,
        "failed": 1,
    }


def test_resume_workflow_debug_logging_path_executes_without_changing_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME",
        )
    )
    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume",
            summary="Checkpoint for debug logging coverage",
            checkpoint_json={"next_intended_action": "Resume with debug enabled"},
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.workspace.workspace_id == workspace.workspace_id
    assert resume.attempt is not None
    assert resume.latest_checkpoint is not None
    assert (
        resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert len(debug_messages) >= 6
    assert debug_messages[0][0] == "resume_workflow started"
    assert any(message == "resume_workflow complete" for message, _ in debug_messages)


def test_resume_workflow_debug_logging_includes_stage_duration_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-DURATIONS",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_durations",
            summary="Checkpoint for duration metadata coverage",
            checkpoint_json={"next_intended_action": "Inspect duration metadata"},
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    expected_messages = {
        "resume_workflow workflow lookup complete",
        "resume_workflow workspace lookup complete",
        "resume_workflow attempt lookup complete",
        "resume_workflow checkpoint lookup complete",
        "resume_workflow verify report lookup complete",
        "resume_workflow projection lookup complete",
        "resume_workflow projection failure lookup complete",
        "resume_workflow response assembly complete",
        "resume_workflow complete",
    }

    seen_messages = {message for message, _ in debug_messages}
    assert expected_messages.issubset(seen_messages)

    for message, extra in debug_messages:
        if message not in expected_messages:
            continue
        assert isinstance(extra, dict)
        assert "duration_ms" in extra
        assert isinstance(extra["duration_ms"], int)
        assert extra["duration_ms"] >= 0


def test_resume_workflow_complete_debug_logging_includes_response_assembly_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-ASSEMBLY-METADATA",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_response_assembly_metadata",
            summary="Checkpoint for response assembly metadata coverage",
            checkpoint_json={
                "next_intended_action": "Inspect response assembly metadata"
            },
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    response_assembly_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow response assembly complete"
    ]

    assert len(response_assembly_extras) == 1
    extra = response_assembly_extras[0]
    assert isinstance(extra, dict)
    assert extra["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert extra["workspace_id"] == str(workspace.workspace_id)
    assert extra["attempt_id"] == str(started.attempt.attempt_id)
    assert extra["projection_count"] == 0
    assert extra["warning_count"] == 0
    assert extra["resumable_status"] == "resumable"
    assert "duration_ms" in extra
    assert isinstance(extra["duration_ms"], int)
    assert extra["duration_ms"] >= 0


def test_resume_workflow_complete_debug_logging_includes_stage_breakdown_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-STAGE-BREAKDOWN",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_stage_breakdown_metadata",
            summary="Checkpoint for stage breakdown metadata coverage",
            checkpoint_json={
                "next_intended_action": "Inspect stage breakdown metadata"
            },
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    complete_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow complete"
    ]

    assert len(complete_extras) == 1
    extra = complete_extras[0]
    assert isinstance(extra, dict)
    assert extra["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert extra["workspace_id"] == str(workspace.workspace_id)
    assert extra["attempt_id"] == str(started.attempt.attempt_id)
    assert extra["checkpoint_id"] is not None
    assert extra["projection_count"] == 0
    assert extra["open_projection_failure_count"] == 0
    assert extra["closed_projection_failure_count"] == 0
    assert extra["warning_count"] == 0
    assert extra["resumable_status"] == "resumable"

    duration_keys = (
        "workflow_lookup_duration_ms",
        "workspace_lookup_duration_ms",
        "attempt_lookup_duration_ms",
        "checkpoint_lookup_duration_ms",
        "verify_report_lookup_duration_ms",
        "projection_lookup_duration_ms",
        "projection_failure_lookup_duration_ms",
        "response_assembly_duration_ms",
        "duration_ms",
    )
    for key in duration_keys:
        assert key in extra
        assert isinstance(extra[key], int)
        assert extra[key] >= 0


def test_resume_workflow_skips_closed_projection_failure_lookup_by_default() -> None:
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="RESUME-SKIP-CLOSED-FAILURES-DEFAULT",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="resume_skip_closed_projection_failures_default",
            summary="Checkpoint for default closed failure lookup behavior",
            checkpoint_json={
                "next_intended_action": "Observe default projection failure lookup"
            },
        )
    )

    closed_failure = ProjectionFailureInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        error_code="io_error",
        error_message="historical projection failure",
        target_path=".agent/resume.json",
        attempt_id=started.attempt.attempt_id,
        occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
        resolved_at=datetime(2024, 1, 2, tzinfo=UTC),
        open_failure_count=1,
        retry_count=1,
        status="resolved",
    )
    uow.projection_failures_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        )
    ] = [closed_failure]

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.closed_projection_failures == ()
    assert resume.resumable_status == ResumableStatus.RESUMABLE


def test_resume_workflow_can_include_closed_projection_failures_when_requested() -> (
    None
):
    service, uow = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="RESUME-INCLUDE-CLOSED-FAILURES-OPT-IN",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="resume_include_closed_projection_failures_opt_in",
            summary="Checkpoint for opt-in closed failure lookup behavior",
            checkpoint_json={
                "next_intended_action": "Observe opt-in projection failure lookup"
            },
        )
    )

    closed_failure = ProjectionFailureInfo(
        projection_type=ProjectionArtifactType.RESUME_JSON,
        error_code="io_error",
        error_message="historical projection failure",
        target_path=".agent/resume.json",
        attempt_id=started.attempt.attempt_id,
        occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
        resolved_at=datetime(2024, 1, 2, tzinfo=UTC),
        open_failure_count=1,
        retry_count=1,
        status="resolved",
    )
    uow.projection_failures_by_key[
        (
            workspace.workspace_id,
            started.workflow_instance.workflow_instance_id,
            ProjectionArtifactType.RESUME_JSON,
        )
    ] = [closed_failure]

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            include_closed_projection_failures=True,
        )
    )

    assert len(resume.closed_projection_failures) == 1
    assert resume.closed_projection_failures[0] == closed_failure
    assert resume.resumable_status == ResumableStatus.RESUMABLE


def test_resume_workflow_debug_logging_includes_attempt_lookup_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="DEBUG-RESUME-ATTEMPT-STRATEGY",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="debug_resume_attempt_strategy",
            summary="Checkpoint for attempt lookup strategy coverage",
            checkpoint_json={"next_intended_action": "Inspect attempt lookup strategy"},
        )
    )

    logger = importlib.import_module("ctxledger.workflow.service").logger
    monkeypatch.setattr(logger, "isEnabledFor", lambda level: level == logging.DEBUG)

    debug_messages: list[tuple[str, dict[str, object] | None]] = []

    def fake_debug(message: str, *args: object, **kwargs: object) -> None:
        debug_messages.append((message, kwargs.get("extra")))

    monkeypatch.setattr(logger, "debug", fake_debug)

    service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    attempt_lookup_extras = [
        extra
        for message, extra in debug_messages
        if message == "resume_workflow attempt lookup complete"
    ]

    assert len(attempt_lookup_extras) == 1
    extra = attempt_lookup_extras[0]
    assert isinstance(extra, dict)
    assert extra["attempt_lookup_strategy"] == "running"
    assert extra["attempt_id"] == str(started.attempt.attempt_id)


def test_complete_workflow_returns_default_auto_memory_details_when_bridge_returns_none() -> (
    None
):
    class NoneReturningBridge:
        embedding_generator = None

        def record_workflow_completion_memory(self, **kwargs: object) -> None:
            return None

    service, _ = make_service_and_uow(
        workflow_memory_bridge=NoneReturningBridge()  # type: ignore[arg-type]
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-NONE",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "no_completion_summary_source",
    }
    assert result.warnings == ()


def test_complete_workflow_adds_embedding_warning_when_auto_memory_embedding_fails() -> (
    None
):
    class EmbeddingFailureBridge:
        embedding_generator = None

        def record_workflow_completion_memory(self, **kwargs: object):
            return SimpleNamespace(
                details={
                    "auto_memory_recorded": True,
                    "embedding_persistence_status": "failed",
                    "embedding_generation_skipped_reason": "embedding_generation_failed:test",
                    "embedding_generation_failure": {
                        "provider": "test",
                        "message": "boom",
                    },
                }
            )

    service, _ = make_service_and_uow(
        workflow_memory_bridge=EmbeddingFailureBridge()  # type: ignore[arg-type]
    )
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="AUTO-MEMORY-EMBEDDING-FAIL",
        )
    )

    result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    assert result.auto_memory_details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "failed",
        "embedding_generation_skipped_reason": "embedding_generation_failed:test",
        "embedding_generation_failure": {
            "provider": "test",
            "message": "boom",
        },
    }
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "auto_memory_embedding_failed"
    assert result.warnings[0].details == {
        "embedding_generation_skipped_reason": "embedding_generation_failed:test",
        "embedding_generation_failure": {
            "provider": "test",
            "message": "boom",
        },
    }


def test_reconcile_resume_projection_records_failures_without_success_updates() -> None:
    service = WorkflowService(lambda: None)

    recorded_failures: list[RecordProjectionFailureInput] = []

    def fake_record_resume_projection_failure(
        data: RecordProjectionFailureInput,
    ) -> ProjectionFailureInfo:
        recorded_failures.append(data)
        return ProjectionFailureInfo(
            projection_type=data.projection_type,
            error_code=data.error_code,
            error_message=data.error_message,
            target_path=data.target_path,
            attempt_id=data.attempt_id,
            open_failure_count=1,
            retry_count=0,
            status="open",
        )

    service.record_resume_projection_failure = (  # type: ignore[method-assign]
        fake_record_resume_projection_failure
    )

    failure = RecordProjectionFailureInput(
        workspace_id=uuid4(),
        workflow_instance_id=uuid4(),
        attempt_id=uuid4(),
        projection_type=ProjectionArtifactType.RESUME_JSON,
        target_path=".agent/resume.json",
        error_message="write failed",
        error_code="io_error",
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(),
        failure_updates=(failure,),
    )

    assert reconciled == ()
    assert recorded_failures == [failure]


def test_reconcile_resume_projection_resolves_each_key_once_across_duplicate_success_updates() -> (
    None
):
    service = WorkflowService(lambda: None)

    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    first_json = RecordProjectionStateInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.STALE,
        target_path=".agent/resume.json",
    )
    second_json = RecordProjectionStateInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.json",
    )
    markdown = RecordProjectionStateInput(
        workspace_id=workspace_id,
        workflow_instance_id=workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_MD,
        status=ProjectionStatus.FRESH,
        target_path=".agent/resume.md",
    )

    resolved_calls: list[tuple[UUID, UUID, ProjectionArtifactType | None]] = []
    recorded_states: list[RecordProjectionStateInput] = []

    def fake_resolve_resume_projection_failures(
        *,
        workspace_id: UUID,
        workflow_instance_id: UUID,
        projection_type: ProjectionArtifactType | None = None,
    ) -> int:
        resolved_calls.append((workspace_id, workflow_instance_id, projection_type))
        return 1

    def fake_record_resume_projection(
        data: RecordProjectionStateInput,
    ) -> ProjectionInfo:
        recorded_states.append(data)
        return ProjectionInfo(
            projection_type=data.projection_type,
            status=data.status,
            target_path=data.target_path,
            last_successful_write_at=data.last_successful_write_at,
            last_canonical_update_at=data.last_canonical_update_at,
            open_failure_count=0,
        )

    service.resolve_resume_projection_failures = (  # type: ignore[method-assign]
        fake_resolve_resume_projection_failures
    )
    service.record_resume_projection = fake_record_resume_projection  # type: ignore[method-assign]

    reconciled = service.reconcile_resume_projection(
        success_updates=(first_json, second_json, markdown),
        failure_updates=(),
    )

    assert [projection.projection_type for projection in reconciled] == [
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    ]
    assert resolved_calls == [
        (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_JSON),
        (workspace_id, workflow_instance_id, ProjectionArtifactType.RESUME_MD),
    ]
    assert recorded_states == [first_json, second_json, markdown]


def test_stats_helpers_cover_records_by_id_and_values_by_id_paths() -> None:
    service = WorkflowService(lambda: None)
    now = datetime(2024, 1, 10, tzinfo=UTC)

    records_repo = SimpleNamespace(
        _records_by_id={
            uuid4(): SimpleNamespace(
                status=WorkflowInstanceStatus.RUNNING,
                updated_at=now,
            ),
            uuid4(): SimpleNamespace(
                status=WorkflowInstanceStatus.COMPLETED,
                updated_at=now.replace(day=11),
            ),
        }
    )
    values_repo = SimpleNamespace(
        _values_by_id={
            uuid4(): SimpleNamespace(
                status=VerifyStatus.PASSED,
                created_at=now,
            ),
            uuid4(): SimpleNamespace(
                status=VerifyStatus.FAILED,
                created_at=now.replace(day=12),
            ),
        }
    )

    records_count = service._count_rows(
        SimpleNamespace(workflow_instances=records_repo),
        "workflow_instances",
    )
    values_count = service._count_rows(
        SimpleNamespace(verify_reports=values_repo),
        "verify_reports",
    )
    grouped_records = service._count_grouped_statuses(
        SimpleNamespace(workflow_instances=records_repo),
        repository_name="workflow_instances",
        allowed_statuses=(
            WorkflowInstanceStatus.RUNNING.value,
            WorkflowInstanceStatus.COMPLETED.value,
            WorkflowInstanceStatus.FAILED.value,
        ),
    )
    grouped_values = service._count_grouped_statuses(
        SimpleNamespace(verify_reports=values_repo),
        repository_name="verify_reports",
        allowed_statuses=(
            VerifyStatus.PASSED.value,
            VerifyStatus.FAILED.value,
            VerifyStatus.SKIPPED.value,
        ),
    )
    max_records = service._max_datetime_field(
        SimpleNamespace(workflow_instances=records_repo),
        repository_name="workflow_instances",
        field_name="updated_at",
    )
    max_values = service._max_datetime_field(
        SimpleNamespace(verify_reports=values_repo),
        repository_name="verify_reports",
        field_name="created_at",
    )

    assert records_count == 2
    assert values_count == 2
    assert grouped_records == {
        "running": 1,
        "completed": 1,
        "failed": 0,
    }
    assert grouped_values == {
        "passed": 1,
        "failed": 1,
        "skipped": 0,
    }
    assert max_records == now.replace(day=11)
    assert max_values == now.replace(day=12)


def test_stats_helpers_cover_projection_state_and_failure_backing_dict_paths() -> None:
    service = WorkflowService(lambda: None)

    projection_states_repo = SimpleNamespace(
        _projection_states_by_key={
            (uuid4(), uuid4(), ProjectionArtifactType.RESUME_JSON): ProjectionInfo(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
            ),
            (uuid4(), uuid4(), ProjectionArtifactType.RESUME_MD): ProjectionInfo(
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.STALE,
                target_path=".agent/resume.md",
            ),
        }
    )
    projection_failures_repo = SimpleNamespace(
        _failures_by_key={
            (uuid4(), uuid4(), ProjectionArtifactType.RESUME_JSON): [
                ProjectionFailureInfo(
                    projection_type=ProjectionArtifactType.RESUME_JSON,
                    error_code="io_error",
                    error_message="open failure",
                    target_path=".agent/resume.json",
                    status="open",
                ),
                ProjectionFailureInfo(
                    projection_type=ProjectionArtifactType.RESUME_JSON,
                    error_code="resolved_error",
                    error_message="resolved failure",
                    target_path=".agent/resume.json",
                    status="resolved",
                ),
            ],
            (uuid4(), uuid4(), ProjectionArtifactType.RESUME_MD): [
                ProjectionFailureInfo(
                    projection_type=ProjectionArtifactType.RESUME_MD,
                    error_code="open_md",
                    error_message="another open failure",
                    target_path=".agent/resume.md",
                    status="open",
                )
            ],
        }
    )

    projection_state_count = service._count_rows(
        SimpleNamespace(projection_states=projection_states_repo),
        "projection_states",
    )
    projection_failure_count = service._count_rows(
        SimpleNamespace(projection_failures=projection_failures_repo),
        "projection_failures",
    )
    open_projection_failure_count = service._count_open_projection_failures(
        SimpleNamespace(projection_failures=projection_failures_repo)
    )

    assert projection_state_count == 2
    assert projection_failure_count == 3
    assert open_projection_failure_count == 2
