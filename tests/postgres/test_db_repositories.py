from __future__ import annotations

import importlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    PersistenceError,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowInstance,
    WorkflowInstanceStatus,
    Workspace,
)
from tests.postgres.conftest import (
    FakeConnection,
    sample_attempt,
    sample_checkpoint,
    sample_verify_report,
    sample_workflow,
    sample_workspace,
)


def test_postgres_workspace_repository_create_update_and_queries() -> None:
    from ctxledger.db.postgres import PostgresWorkspaceRepository

    connection = FakeConnection()
    repo = PostgresWorkspaceRepository(connection)
    workspace = sample_workspace()

    connection.fetchone_results.append(
        {
            "workspace_id": workspace.workspace_id,
            "repo_url": workspace.repo_url,
            "canonical_path": workspace.canonical_path,
            "default_branch": workspace.default_branch,
            "metadata_json": workspace.metadata,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }
    )
    created = repo.create(workspace)
    assert created == workspace

    updated_workspace = Workspace(
        workspace_id=workspace.workspace_id,
        repo_url=workspace.repo_url,
        canonical_path="/tmp/updated-repo",
        default_branch="develop",
        metadata={"language": "python", "team": "platform"},
        created_at=workspace.created_at,
        updated_at=datetime(2024, 1, 3, tzinfo=UTC),
    )
    connection.fetchone_results.append(
        {
            "workspace_id": updated_workspace.workspace_id,
            "repo_url": updated_workspace.repo_url,
            "canonical_path": updated_workspace.canonical_path,
            "default_branch": updated_workspace.default_branch,
            "metadata_json": updated_workspace.metadata,
            "created_at": updated_workspace.created_at,
            "updated_at": updated_workspace.updated_at,
        }
    )
    updated = repo.update(updated_workspace)
    assert updated == updated_workspace

    connection.fetchone_results.append(
        {
            "workspace_id": workspace.workspace_id,
            "repo_url": workspace.repo_url,
            "canonical_path": workspace.canonical_path,
            "default_branch": workspace.default_branch,
            "metadata_json": workspace.metadata,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }
    )
    assert repo.get_by_id(workspace.workspace_id) == workspace

    connection.fetchone_results.append(None)
    assert repo.get_by_id(uuid4()) is None

    connection.fetchone_results.append(
        {
            "workspace_id": workspace.workspace_id,
            "repo_url": workspace.repo_url,
            "canonical_path": workspace.canonical_path,
            "default_branch": workspace.default_branch,
            "metadata_json": workspace.metadata,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
        }
    )
    assert repo.get_by_canonical_path(workspace.canonical_path) == workspace

    connection.fetchall_results.append(
        [
            {
                "workspace_id": workspace.workspace_id,
                "repo_url": workspace.repo_url,
                "canonical_path": workspace.canonical_path,
                "default_branch": workspace.default_branch,
                "metadata_json": workspace.metadata,
                "created_at": workspace.created_at,
                "updated_at": workspace.updated_at,
            },
            {
                "workspace_id": updated_workspace.workspace_id,
                "repo_url": updated_workspace.repo_url,
                "canonical_path": updated_workspace.canonical_path,
                "default_branch": updated_workspace.default_branch,
                "metadata_json": updated_workspace.metadata,
                "created_at": updated_workspace.created_at,
                "updated_at": updated_workspace.updated_at,
            },
        ]
    )
    by_repo = repo.get_by_repo_url(workspace.repo_url)
    assert by_repo == [workspace, updated_workspace]

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to insert workspace"):
        repo.create(workspace)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to update workspace"):
        repo.update(workspace)


def test_postgres_workflow_instance_repository_create_update_and_list_recent() -> None:
    from ctxledger.db.postgres import PostgresWorkflowInstanceRepository

    connection = FakeConnection()
    repo = PostgresWorkflowInstanceRepository(connection)
    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)

    connection.fetchone_results.append(
        {
            "workflow_instance_id": workflow.workflow_instance_id,
            "workspace_id": workflow.workspace_id,
            "ticket_id": workflow.ticket_id,
            "status": workflow.status.value,
            "metadata_json": workflow.metadata,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )
    created = repo.create(workflow)
    assert created == workflow

    updated_workflow = WorkflowInstance(
        workflow_instance_id=workflow.workflow_instance_id,
        workspace_id=workflow.workspace_id,
        ticket_id="TICKET-456",
        status=WorkflowInstanceStatus.COMPLETED,
        metadata={"priority": "low"},
        created_at=workflow.created_at,
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    connection.fetchone_results.append(
        {
            "workflow_instance_id": updated_workflow.workflow_instance_id,
            "workspace_id": updated_workflow.workspace_id,
            "ticket_id": updated_workflow.ticket_id,
            "status": updated_workflow.status.value,
            "metadata_json": updated_workflow.metadata,
            "created_at": updated_workflow.created_at,
            "updated_at": updated_workflow.updated_at,
        }
    )
    updated = repo.update(updated_workflow)
    assert updated == updated_workflow

    connection.fetchone_results.append(
        {
            "workflow_instance_id": workflow.workflow_instance_id,
            "workspace_id": workflow.workspace_id,
            "ticket_id": workflow.ticket_id,
            "status": workflow.status.value,
            "metadata_json": workflow.metadata,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )
    assert repo.get_by_id(workflow.workflow_instance_id) == workflow

    connection.fetchone_results.append(
        {
            "workflow_instance_id": workflow.workflow_instance_id,
            "workspace_id": workflow.workspace_id,
            "ticket_id": workflow.ticket_id,
            "status": workflow.status.value,
            "metadata_json": workflow.metadata,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )
    assert repo.get_running_by_workspace_id(workflow.workspace_id) == workflow

    connection.fetchone_results.append(
        {
            "workflow_instance_id": updated_workflow.workflow_instance_id,
            "workspace_id": updated_workflow.workspace_id,
            "ticket_id": updated_workflow.ticket_id,
            "status": updated_workflow.status.value,
            "metadata_json": updated_workflow.metadata,
            "created_at": updated_workflow.created_at,
            "updated_at": updated_workflow.updated_at,
        }
    )
    assert repo.get_latest_by_workspace_id(workflow.workspace_id) == updated_workflow

    another_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workflow.workspace_id,
        ticket_id="TICKET-789",
        status=WorkflowInstanceStatus.RUNNING,
        metadata={},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
        updated_at=datetime(2024, 1, 7, tzinfo=UTC),
    )
    connection.fetchall_results.append(
        [
            {
                "workflow_instance_id": updated_workflow.workflow_instance_id,
                "workspace_id": updated_workflow.workspace_id,
                "ticket_id": updated_workflow.ticket_id,
                "status": updated_workflow.status.value,
                "metadata_json": updated_workflow.metadata,
                "created_at": updated_workflow.created_at,
                "updated_at": updated_workflow.updated_at,
            },
            {
                "workflow_instance_id": another_workflow.workflow_instance_id,
                "workspace_id": another_workflow.workspace_id,
                "ticket_id": another_workflow.ticket_id,
                "status": another_workflow.status.value,
                "metadata_json": another_workflow.metadata,
                "created_at": another_workflow.created_at,
                "updated_at": another_workflow.updated_at,
            },
        ]
    )
    recent = repo.list_recent(
        limit=5,
        status=WorkflowInstanceStatus.RUNNING.value,
        workspace_id=workflow.workspace_id,
        ticket_id="TICKET",
    )
    assert recent == (updated_workflow, another_workflow)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to insert workflow instance"):
        repo.create(workflow)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to update workflow instance"):
        repo.update(workflow)


def test_postgres_workflow_attempt_repository_create_update_and_next_number() -> None:
    from ctxledger.db.postgres import PostgresWorkflowAttemptRepository

    connection = FakeConnection()
    repo = PostgresWorkflowAttemptRepository(connection)
    attempt = sample_attempt(uuid4())

    connection.fetchone_results.append(
        {
            "attempt_id": attempt.attempt_id,
            "workflow_instance_id": attempt.workflow_instance_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status.value,
            "failure_reason": attempt.failure_reason,
            "verify_status": attempt.verify_status.value,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
    )
    created = repo.create(attempt)
    assert created == attempt

    updated_attempt = WorkflowAttempt(
        attempt_id=attempt.attempt_id,
        workflow_instance_id=attempt.workflow_instance_id,
        attempt_number=attempt.attempt_number,
        status=WorkflowAttemptStatus.SUCCEEDED,
        failure_reason=None,
        verify_status=VerifyStatus.PASSED,
        started_at=attempt.started_at,
        finished_at=datetime(2024, 1, 6, tzinfo=UTC),
        created_at=attempt.created_at,
        updated_at=datetime(2024, 1, 6, tzinfo=UTC),
    )
    connection.fetchone_results.append(
        {
            "attempt_id": updated_attempt.attempt_id,
            "workflow_instance_id": updated_attempt.workflow_instance_id,
            "attempt_number": updated_attempt.attempt_number,
            "status": updated_attempt.status.value,
            "failure_reason": updated_attempt.failure_reason,
            "verify_status": updated_attempt.verify_status.value,
            "started_at": updated_attempt.started_at,
            "finished_at": updated_attempt.finished_at,
            "created_at": updated_attempt.created_at,
            "updated_at": updated_attempt.updated_at,
        }
    )
    updated = repo.update(updated_attempt)
    assert updated == updated_attempt

    connection.fetchone_results.append(
        {
            "attempt_id": attempt.attempt_id,
            "workflow_instance_id": attempt.workflow_instance_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status.value,
            "failure_reason": attempt.failure_reason,
            "verify_status": attempt.verify_status.value,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
    )
    assert repo.get_by_id(attempt.attempt_id) == attempt

    connection.fetchone_results.append(
        {
            "attempt_id": attempt.attempt_id,
            "workflow_instance_id": attempt.workflow_instance_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status.value,
            "failure_reason": attempt.failure_reason,
            "verify_status": attempt.verify_status.value,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
    )
    assert repo.get_running_by_workflow_id(attempt.workflow_instance_id) == attempt

    connection.fetchone_results.append(
        {
            "attempt_id": updated_attempt.attempt_id,
            "workflow_instance_id": updated_attempt.workflow_instance_id,
            "attempt_number": updated_attempt.attempt_number,
            "status": updated_attempt.status.value,
            "failure_reason": updated_attempt.failure_reason,
            "verify_status": updated_attempt.verify_status.value,
            "started_at": updated_attempt.started_at,
            "finished_at": updated_attempt.finished_at,
            "created_at": updated_attempt.created_at,
            "updated_at": updated_attempt.updated_at,
        }
    )
    assert (
        repo.get_latest_by_workflow_id(attempt.workflow_instance_id) == updated_attempt
    )

    connection.fetchone_results.append({"max_attempt_number": 3})
    assert repo.get_next_attempt_number(attempt.workflow_instance_id) == 4

    connection.fetchone_results.append(None)
    assert repo.get_next_attempt_number(attempt.workflow_instance_id) == 1

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to insert workflow attempt"):
        repo.create(attempt)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to update workflow attempt"):
        repo.update(attempt)


def test_postgres_checkpoint_verify_episode_repositories_create_and_lookup() -> None:
    from ctxledger.db.postgres import (
        PostgresMemoryEpisodeRepository,
        PostgresVerifyReportRepository,
        PostgresWorkflowCheckpointRepository,
    )

    connection = FakeConnection()
    checkpoint_repo = PostgresWorkflowCheckpointRepository(connection)
    verify_repo = PostgresVerifyReportRepository(connection)
    episode_repo = PostgresMemoryEpisodeRepository(connection)

    workflow = sample_workflow(uuid4())
    attempt = sample_attempt(workflow.workflow_instance_id)
    checkpoint = sample_checkpoint(workflow.workflow_instance_id, attempt.attempt_id)
    verify_report = sample_verify_report(attempt.attempt_id)
    episode = importlib.import_module("ctxledger.workflow.service").EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        summary="Episode summary",
        attempt_id=attempt.attempt_id,
        metadata={"kind": "checkpoint"},
        status="recorded",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
        updated_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    connection.fetchone_results.append(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workflow_instance_id": checkpoint.workflow_instance_id,
            "attempt_id": checkpoint.attempt_id,
            "step_name": checkpoint.step_name,
            "summary": checkpoint.summary,
            "checkpoint_json": checkpoint.checkpoint_json,
            "created_at": checkpoint.created_at,
        }
    )
    assert checkpoint_repo.create(checkpoint) == checkpoint

    connection.fetchone_results.append(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workflow_instance_id": checkpoint.workflow_instance_id,
            "attempt_id": checkpoint.attempt_id,
            "step_name": checkpoint.step_name,
            "summary": checkpoint.summary,
            "checkpoint_json": checkpoint.checkpoint_json,
            "created_at": checkpoint.created_at,
        }
    )
    assert (
        checkpoint_repo.get_latest_by_workflow_id(workflow.workflow_instance_id)
        == checkpoint
    )

    connection.fetchone_results.append(
        {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workflow_instance_id": checkpoint.workflow_instance_id,
            "attempt_id": checkpoint.attempt_id,
            "step_name": checkpoint.step_name,
            "summary": checkpoint.summary,
            "checkpoint_json": checkpoint.checkpoint_json,
            "created_at": checkpoint.created_at,
        }
    )
    assert checkpoint_repo.get_latest_by_attempt_id(attempt.attempt_id) == checkpoint

    connection.fetchone_results.append(
        {
            "verify_id": verify_report.verify_id,
            "attempt_id": verify_report.attempt_id,
            "status": verify_report.status.value,
            "report_json": verify_report.report_json,
            "created_at": verify_report.created_at,
        }
    )
    assert verify_repo.create(verify_report) == verify_report

    connection.fetchone_results.append(
        {
            "verify_id": verify_report.verify_id,
            "attempt_id": verify_report.attempt_id,
            "status": verify_report.status.value,
            "report_json": verify_report.report_json,
            "created_at": verify_report.created_at,
        }
    )
    assert verify_repo.get_latest_by_attempt_id(attempt.attempt_id) == verify_report

    connection.fetchone_results.append(
        {
            "episode_id": episode.episode_id,
            "workflow_instance_id": episode.workflow_instance_id,
            "summary": episode.summary,
            "attempt_id": episode.attempt_id,
            "metadata_json": episode.metadata,
            "status": episode.status,
            "created_at": episode.created_at,
            "updated_at": episode.updated_at,
        }
    )
    assert episode_repo.create(episode) == episode

    connection.fetchall_results.append(
        [
            {
                "episode_id": episode.episode_id,
                "workflow_instance_id": episode.workflow_instance_id,
                "summary": episode.summary,
                "attempt_id": episode.attempt_id,
                "metadata_json": episode.metadata,
                "status": episode.status,
                "created_at": episode.created_at,
                "updated_at": episode.updated_at,
            }
        ]
    )
    assert episode_repo.list_by_workflow_id(workflow.workflow_instance_id, limit=5) == (
        episode,
    )


def test_postgres_memory_item_and_embedding_repositories_create_and_list() -> None:
    from ctxledger.db.postgres import (
        PostgresMemoryEmbeddingRepository,
        PostgresMemoryItemRepository,
    )

    connection = FakeConnection()
    item_repo = PostgresMemoryItemRepository(connection)
    embedding_repo = PostgresMemoryEmbeddingRepository(connection)

    workspace_id = uuid4()
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Stored memory item",
        metadata={"kind": "note"},
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    workspace_root_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=datetime(2024, 1, 10, tzinfo=UTC),
        updated_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    relation_target_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Relation target memory item",
        metadata={"kind": "relation-target"},
        created_at=datetime(2024, 1, 11, tzinfo=UTC),
        updated_at=datetime(2024, 1, 11, tzinfo=UTC),
    )
    embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_item.memory_id,
        embedding_model="test-model",
        embedding=(0.1, 0.2, 0.3),
        content_hash="hash-123",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    connection.fetchone_results.append(
        {
            "memory_id": memory_item.memory_id,
            "workspace_id": memory_item.workspace_id,
            "episode_id": memory_item.episode_id,
            "type": memory_item.type,
            "provenance": memory_item.provenance,
            "content": memory_item.content,
            "metadata_json": memory_item.metadata,
            "created_at": memory_item.created_at,
            "updated_at": memory_item.updated_at,
        }
    )
    assert item_repo.create(memory_item) == memory_item

    connection.fetchone_results.append(
        {
            "memory_id": workspace_root_memory_item.memory_id,
            "workspace_id": workspace_root_memory_item.workspace_id,
            "episode_id": workspace_root_memory_item.episode_id,
            "type": workspace_root_memory_item.type,
            "provenance": workspace_root_memory_item.provenance,
            "content": workspace_root_memory_item.content,
            "metadata_json": workspace_root_memory_item.metadata,
            "created_at": workspace_root_memory_item.created_at,
            "updated_at": workspace_root_memory_item.updated_at,
        }
    )
    assert item_repo.create(workspace_root_memory_item) == workspace_root_memory_item

    connection.fetchone_results.append(
        {
            "memory_id": relation_target_memory_item.memory_id,
            "workspace_id": relation_target_memory_item.workspace_id,
            "episode_id": relation_target_memory_item.episode_id,
            "type": relation_target_memory_item.type,
            "provenance": relation_target_memory_item.provenance,
            "content": relation_target_memory_item.content,
            "metadata_json": relation_target_memory_item.metadata,
            "created_at": relation_target_memory_item.created_at,
            "updated_at": relation_target_memory_item.updated_at,
        }
    )
    assert item_repo.create(relation_target_memory_item) == relation_target_memory_item

    connection.fetchall_results.append(
        [
            {
                "memory_id": memory_item.memory_id,
                "workspace_id": memory_item.workspace_id,
                "episode_id": memory_item.episode_id,
                "type": memory_item.type,
                "provenance": memory_item.provenance,
                "content": memory_item.content,
                "metadata_json": memory_item.metadata,
                "created_at": memory_item.created_at,
                "updated_at": memory_item.updated_at,
            }
        ]
    )
    assert item_repo.list_by_workspace_id(memory_item.workspace_id, limit=5) == (
        memory_item,
    )

    connection.fetchall_results.append(
        [
            {
                "memory_id": relation_target_memory_item.memory_id,
                "workspace_id": relation_target_memory_item.workspace_id,
                "episode_id": relation_target_memory_item.episode_id,
                "type": relation_target_memory_item.type,
                "provenance": relation_target_memory_item.provenance,
                "content": relation_target_memory_item.content,
                "metadata_json": relation_target_memory_item.metadata,
                "created_at": relation_target_memory_item.created_at,
                "updated_at": relation_target_memory_item.updated_at,
            },
            {
                "memory_id": workspace_root_memory_item.memory_id,
                "workspace_id": workspace_root_memory_item.workspace_id,
                "episode_id": workspace_root_memory_item.episode_id,
                "type": workspace_root_memory_item.type,
                "provenance": workspace_root_memory_item.provenance,
                "content": workspace_root_memory_item.content,
                "metadata_json": workspace_root_memory_item.metadata,
                "created_at": workspace_root_memory_item.created_at,
                "updated_at": workspace_root_memory_item.updated_at,
            },
        ]
    )
    assert item_repo.list_workspace_root_items(workspace_id, limit=5) == (
        relation_target_memory_item,
        workspace_root_memory_item,
    )

    connection.fetchall_results.append(
        [
            {
                "memory_id": relation_target_memory_item.memory_id,
                "workspace_id": relation_target_memory_item.workspace_id,
                "episode_id": relation_target_memory_item.episode_id,
                "type": relation_target_memory_item.type,
                "provenance": relation_target_memory_item.provenance,
                "content": relation_target_memory_item.content,
                "metadata_json": relation_target_memory_item.metadata,
                "created_at": relation_target_memory_item.created_at,
                "updated_at": relation_target_memory_item.updated_at,
            }
        ]
    )
    assert item_repo.list_by_memory_ids(
        (relation_target_memory_item.memory_id,),
    ) == (relation_target_memory_item,)

    connection.fetchall_results.append(
        [
            {
                "memory_id": relation_target_memory_item.memory_id,
                "workspace_id": relation_target_memory_item.workspace_id,
                "episode_id": relation_target_memory_item.episode_id,
                "type": relation_target_memory_item.type,
                "provenance": relation_target_memory_item.provenance,
                "content": relation_target_memory_item.content,
                "metadata_json": relation_target_memory_item.metadata,
                "created_at": relation_target_memory_item.created_at,
                "updated_at": relation_target_memory_item.updated_at,
            },
            {
                "memory_id": workspace_root_memory_item.memory_id,
                "workspace_id": workspace_root_memory_item.workspace_id,
                "episode_id": workspace_root_memory_item.episode_id,
                "type": workspace_root_memory_item.type,
                "provenance": workspace_root_memory_item.provenance,
                "content": workspace_root_memory_item.content,
                "metadata_json": workspace_root_memory_item.metadata,
                "created_at": workspace_root_memory_item.created_at,
                "updated_at": workspace_root_memory_item.updated_at,
            },
        ]
    )
    assert item_repo.list_by_memory_ids(
        (
            workspace_root_memory_item.memory_id,
            relation_target_memory_item.memory_id,
        ),
    ) == (
        relation_target_memory_item,
        workspace_root_memory_item,
    )

    assert item_repo.list_by_memory_ids(()) == ()

    connection.fetchall_results.append(
        [
            {
                "memory_id": memory_item.memory_id,
                "workspace_id": memory_item.workspace_id,
                "episode_id": memory_item.episode_id,
                "type": memory_item.type,
                "provenance": memory_item.provenance,
                "content": memory_item.content,
                "metadata_json": memory_item.metadata,
                "created_at": memory_item.created_at,
                "updated_at": memory_item.updated_at,
            }
        ]
    )
    assert item_repo.list_by_episode_id(memory_item.episode_id, limit=5) == (
        memory_item,
    )

    connection.fetchone_results.append(
        {
            "memory_embedding_id": embedding.memory_embedding_id,
            "memory_id": embedding.memory_id,
            "embedding_model": embedding.embedding_model,
            "embedding": "[0.1,0.2,0.3]",
            "content_hash": embedding.content_hash,
            "created_at": embedding.created_at,
        }
    )
    created_embedding = embedding_repo.create(embedding)
    assert created_embedding.embedding == (0.1, 0.2, 0.3)

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding.memory_embedding_id,
                "memory_id": embedding.memory_id,
                "embedding_model": embedding.embedding_model,
                "embedding": [0.1, 0.2, 0.3],
                "content_hash": embedding.content_hash,
                "created_at": embedding.created_at,
            }
        ]
    )
    listed = embedding_repo.list_by_memory_id(memory_item.memory_id, limit=5)
    assert len(listed) == 1
    assert listed[0].embedding == (0.1, 0.2, 0.3)

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding.memory_embedding_id,
                "memory_id": embedding.memory_id,
                "embedding_model": embedding.embedding_model,
                "embedding": "[0.1,0.2,0.3]",
                "content_hash": embedding.content_hash,
                "created_at": embedding.created_at,
            }
        ]
    )
    similar = embedding_repo.find_similar((0.1, 0.2, 0.3), limit=3)
    assert len(similar) == 1
    assert similar[0].memory_id == memory_item.memory_id

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding.memory_embedding_id,
                "memory_id": embedding.memory_id,
                "embedding_model": embedding.embedding_model,
                "embedding": "[0.1,0.2,0.3]",
                "content_hash": embedding.content_hash,
                "created_at": embedding.created_at,
            }
        ]
    )
    similar_with_workspace = embedding_repo.find_similar(
        (0.1, 0.2, 0.3),
        limit=3,
        workspace_id=memory_item.workspace_id,
    )
    assert len(similar_with_workspace) == 1

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to create memory item"):
        item_repo.create(memory_item)

    connection.fetchone_results.append(None)
    with pytest.raises(PersistenceError, match="Failed to create memory embedding"):
        embedding_repo.create(embedding)
