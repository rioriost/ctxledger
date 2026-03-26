from __future__ import annotations

from uuid import uuid4

from ctxledger.memory.service import (
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryWorkflowLookupRepository,
    MemoryService,
    SearchMemoryRequest,
)
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    StartWorkflowInput,
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstance,
    WorkflowInstanceStatus,
)

from .conftest import (
    build_recording_workflow_memory_bridge,
    make_aged_episode_copy,
    make_service_and_uow,
    register_workspace,
)


def test_checkpoint_auto_memory_records_promoted_memory_and_relations() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
    service, _ = make_service_and_uow(workflow_memory_bridge=bridge)
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="CHECKPOINT-AUTO-MEMORY-1",
        )
    )

    result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpoint_memory_promotion",
            summary="Captured a high-signal checkpoint for the remember path",
            checkpoint_json={
                "current_objective": "Make checkpoint memory promotion automatic",
                "next_intended_action": "Add service-level checkpoint auto-memory coverage",
                "what_remains": "Validate the promoted memory payloads end to end",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    assert result.auto_memory_details is not None
    assert result.auto_memory_details["auto_memory_recorded"] is True
    assert result.auto_memory_details["promoted_memory_item_count"] == 4
    assert result.auto_memory_details["memory_relation_count"] == 2
    assert result.auto_memory_details["embedding_persistence_status"] == "skipped"
    assert (
        result.auto_memory_details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert result.auto_memory_details["stage_details"]["gating"]["status"] == "passed"
    assert result.auto_memory_details["stage_details"]["summary_selection"]["status"] == "built"
    assert result.auto_memory_details["stage_details"]["promoted_memory_items"]["status"] == (
        "recorded"
    )
    assert result.auto_memory_details["stage_details"]["relations"]["status"] == "recorded"
    assert result.warnings == ()

    assert len(episode_repository.episodes) == 1
    assert episode_repository.episodes[0].metadata["memory_origin"] == "workflow_checkpoint_auto"
    assert (
        episode_repository.episodes[0].metadata["current_objective"]
        == "Make checkpoint memory promotion automatic"
    )
    assert (
        episode_repository.episodes[0].metadata["next_intended_action"]
        == "Add service-level checkpoint auto-memory coverage"
    )
    assert (
        episode_repository.episodes[0].metadata["what_remains"]
        == "Validate the promoted memory payloads end to end"
    )
    assert episode_repository.episodes[0].metadata["verify_status"] == "passed"

    assert len(memory_item_repository.memory_items) == 5
    assert {item.provenance for item in memory_item_repository.memory_items} == {
        "workflow_checkpoint_auto"
    }
    assert {item.type for item in memory_item_repository.memory_items} == {
        "workflow_checkpoint_note",
        "workflow_objective",
        "workflow_next_action",
        "workflow_what_remains",
        "workflow_verification_outcome",
    }

    assert len(memory_embedding_repository.embeddings) == 0
    assert len(memory_relation_repository.relations) == 2
    assert {relation.relation_type for relation in memory_relation_repository.relations} == {
        "supports"
    }
    assert {
        relation.metadata["relation_reason"] for relation in memory_relation_repository.relations
    } == {
        "next_action_supports_objective",
        "verification_supports_completion_note",
    }


def test_checkpoint_auto_memory_records_root_cause_and_recovery_pattern() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
    service, _ = make_service_and_uow(workflow_memory_bridge=bridge)
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="CHECKPOINT-AUTO-MEMORY-2",
        )
    )

    result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpoint_root_cause_capture",
            summary="Captured failure analysis details before workflow completion",
            checkpoint_json={
                "current_objective": "Recover the remember-path validation flow",
                "root_cause": "Checkpoint promotion was not yet writing canonical memory items",
                "recovery_pattern": "Promote structured checkpoint fields into memory items and supports edges",
                "what_remains": "Add end-to-end tests for checkpoint-derived memory",
            },
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
        )
    )

    assert result.auto_memory_details is not None
    assert result.auto_memory_details["auto_memory_recorded"] is True
    assert result.auto_memory_details["promoted_memory_item_count"] == 5
    assert result.auto_memory_details["memory_relation_count"] == 2
    assert (
        result.auto_memory_details["stage_details"]["promoted_memory_items"]["created_count"] == 5
    )
    assert result.auto_memory_details["stage_details"]["relations"]["relation_type_counts"] == {
        "supports": 2
    }
    assert result.warnings == ()

    assert len(episode_repository.episodes) == 1
    assert episode_repository.episodes[0].metadata["root_cause"] == (
        "Checkpoint promotion was not yet writing canonical memory items"
    )
    assert episode_repository.episodes[0].metadata["recovery_pattern"] == (
        "Promote structured checkpoint fields into memory items and supports edges"
    )
    assert episode_repository.episodes[0].metadata["verify_status"] == "failed"
    assert "Root cause: Checkpoint promotion was not yet writing canonical memory items" in (
        episode_repository.episodes[0].summary
    )
    assert (
        "Recovery pattern: Promote structured checkpoint fields into memory items and supports edges"
        in episode_repository.episodes[0].summary
    )

    assert len(memory_item_repository.memory_items) == 6
    assert {item.type for item in memory_item_repository.memory_items} == {
        "workflow_checkpoint_note",
        "workflow_objective",
        "workflow_root_cause",
        "workflow_recovery_pattern",
        "workflow_what_remains",
        "workflow_verification_outcome",
    }

    assert len(memory_embedding_repository.embeddings) == 0
    assert len(memory_relation_repository.relations) == 2
    assert {
        relation.metadata["relation_reason"] for relation in memory_relation_repository.relations
    } == {
        "verification_supports_completion_note",
        "recovery_pattern_supports_root_cause",
    }


def test_end_to_end_remember_path_across_checkpoint_completion_and_retrieval() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
    service, _ = make_service_and_uow(workflow_memory_bridge=bridge)
    workspace = register_workspace(service)
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="REMEMBER-PATH-E2E-1",
        )
    )

    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="remember_path_checkpoint",
            summary="Captured a checkpoint with objective, next action, and recovery guidance",
            checkpoint_json={
                "current_objective": "Strengthen checkpoint-driven remember-path accumulation",
                "next_intended_action": "Complete the end-to-end remember-path validation",
                "root_cause": "Checkpoint promotion had not yet been validated end to end",
                "recovery_pattern": "Promote structured checkpoint fields into canonical memory and relations",
                "what_remains": "Validate retrieval and AGE-bootstrap inputs after completion",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["checkpoint"], "status": "passed"},
        )
    )

    completion_result = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed the remember-path end-to-end validation flow",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["checkpoint", "completion"], "status": "passed"},
        )
    )

    assert checkpoint_result.auto_memory_details is not None
    assert checkpoint_result.auto_memory_details["auto_memory_recorded"] is True
    assert checkpoint_result.auto_memory_details["promoted_memory_item_count"] == 6
    assert checkpoint_result.auto_memory_details["memory_relation_count"] == 3

    assert completion_result.auto_memory_details is not None
    assert completion_result.auto_memory_details["auto_memory_recorded"] is True
    assert completion_result.auto_memory_details["promoted_memory_item_count"] == 5
    assert completion_result.auto_memory_details["memory_relation_count"] == 3

    assert len(episode_repository.episodes) == 2
    assert episode_repository.episodes[0].metadata["memory_origin"] == "workflow_checkpoint_auto"
    assert episode_repository.episodes[1].metadata["memory_origin"] == "workflow_complete_auto"

    assert len(memory_item_repository.memory_items) == 13
    assert len(memory_embedding_repository.embeddings) == 0
    assert len(memory_relation_repository.relations) == 6
    assert {relation.relation_type for relation in memory_relation_repository.relations} == {
        "supports"
    }
    assert {
        relation.metadata["relation_reason"] for relation in memory_relation_repository.relations
    } == {
        "next_action_supports_objective",
        "recovery_pattern_supports_root_cause",
        "verification_supports_completion_note",
    }

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            started.workflow_instance.workflow_instance_id: {
                "workspace_id": str(workspace.workspace_id),
                "ticket_id": "REMEMBER-PATH-E2E-1",
                "workflow_status": "completed",
                "workflow_is_terminal": True,
                "latest_attempt_status": "succeeded",
                "latest_attempt_is_terminal": True,
                "latest_attempt_verify_status": "passed",
                "has_latest_attempt": True,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": checkpoint_result.checkpoint.created_at,
                "latest_checkpoint_step_name": checkpoint_result.checkpoint.step_name,
                "latest_checkpoint_summary": checkpoint_result.checkpoint.summary,
                "latest_checkpoint_current_objective": checkpoint_result.checkpoint.checkpoint_json[
                    "current_objective"
                ],
                "latest_checkpoint_next_intended_action": checkpoint_result.checkpoint.checkpoint_json[
                    "next_intended_action"
                ],
                "latest_verify_report_created_at": checkpoint_result.verify_report.created_at,
                "workflow_updated_at": completion_result.workflow_instance.updated_at,
            }
        }
    )
    retrieval_episode_repository = InMemoryEpisodeRepository()
    for episode in episode_repository.episodes:
        retrieval_episode_repository.create(episode)

    retrieval_memory_item_repository = InMemoryMemoryItemRepository()
    for memory_item in memory_item_repository.memory_items:
        retrieval_memory_item_repository.create(memory_item)

    retrieval_memory_relation_repository = InMemoryMemoryRelationRepository()
    for relation in memory_relation_repository.relations:
        retrieval_memory_relation_repository.create(relation)

    memory_service = MemoryService(
        episode_repository=retrieval_episode_repository,
        memory_item_repository=retrieval_memory_item_repository,
        memory_embedding_repository=InMemoryMemoryEmbeddingRepository(),
        memory_relation_repository=retrieval_memory_relation_repository,
        workflow_lookup=workflow_lookup,
    )

    context_response = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            query="remember-path validation recovery",
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    search_response = memory_service.search(
        SearchMemoryRequest(
            query="Promote structured checkpoint fields into canonical memory and relations",
            workspace_id=str(workspace.workspace_id),
            limit=10,
        )
    )

    assert context_response.details["episodes_returned"] >= 1
    assert context_response.details["memory_items"]
    assert context_response.details["related_memory_items"]
    assert "supports" in context_response.details["related_context_relation_types"]

    assert len(search_response.results) >= 1
    assert any(
        result.metadata.get("promotion_field") == "recovery_pattern"
        or result.metadata.get("promotion_field") == "root_cause"
        for result in search_response.results
    )

    supports_source_ids = tuple(
        item.memory_id
        for item in memory_item_repository.memory_items
        if item.metadata.get("promotion_field") in {"next_intended_action", "recovery_pattern"}
    )
    assert supports_source_ids
    assert (
        retrieval_memory_relation_repository.list_distinct_support_target_memory_ids_by_source_memory_ids(
            supports_source_ids
        )
        != ()
    )


def test_complete_workflow_auto_memory_records_when_checkpoint_has_next_action() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
    service, _ = make_service_and_uow(workflow_memory_bridge=bridge)
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

    assert result.auto_memory_details is not None
    assert result.auto_memory_details["auto_memory_recorded"] is True
    assert result.auto_memory_details["embedding_persistence_status"] == "skipped"
    assert (
        result.auto_memory_details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert result.auto_memory_details["promoted_memory_item_count"] == 2
    assert result.auto_memory_details["memory_relation_count"] == 1
    assert result.warnings == ()
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 6
    assert len(memory_embedding_repository.embeddings) == 0
    assert len(memory_relation_repository.relations) == 2
    assert episode_repository.episodes[1].metadata["memory_origin"] == "workflow_complete_auto"
    assert (
        episode_repository.episodes[1].metadata["next_intended_action"]
        == "Implement the minimum heuristic path"
    )
    assert (
        "Last planned next action: Implement the minimum heuristic path"
        in episode_repository.episodes[1].summary
    )


def test_complete_workflow_auto_memory_skips_without_checkpoint_signal() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
    service, _ = make_service_and_uow(workflow_memory_bridge=bridge)
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
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "low_signal_checkpoint_closeout",
            }
        },
    }
    assert result.warnings == ()
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 2
    assert memory_embedding_repository.embeddings == []
    assert len(memory_relation_repository.relations) == 1


def test_complete_workflow_auto_memory_records_when_verify_failed() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
    service, _ = make_service_and_uow(workflow_memory_bridge=bridge)
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

    assert result.auto_memory_details is not None
    assert result.auto_memory_details["auto_memory_recorded"] is True
    assert result.auto_memory_details["embedding_persistence_status"] == "skipped"
    assert (
        result.auto_memory_details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert result.auto_memory_details["promoted_memory_item_count"] == 1
    assert result.auto_memory_details["memory_relation_count"] == 1
    assert len(episode_repository.episodes) == 2
    assert episode_repository.episodes[1].metadata["memory_origin"] == "workflow_complete_auto"
    assert episode_repository.episodes[1].metadata["verify_status"] == "failed"
    assert "Verify status: failed" in episode_repository.episodes[1].summary
    assert len(memory_relation_repository.relations) == 2
    assert {
        relation.metadata["relation_reason"] for relation in memory_relation_repository.relations
    } == {
        "verification_supports_completion_note",
        "verification_supports_completion_note",
    }


def test_complete_workflow_auto_memory_skips_duplicate_closeout_summary() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
    assert result.details["auto_memory_recorded"] is True
    assert result.details["embedding_persistence_status"] == "skipped"
    assert (
        result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )

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
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "passed",
                "skipped_reason": None,
            },
            "summary_selection": {
                "attempted": True,
                "status": "built",
                "skipped_reason": None,
            },
            "duplicate_check": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "duplicate_closeout_auto_memory",
            },
        },
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 3
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_skips_near_duplicate_checkpoint_closeout() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
    assert result.details["auto_memory_recorded"] is True
    assert result.details["embedding_persistence_status"] == "skipped"
    assert (
        result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )

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
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "passed",
                "skipped_reason": None,
            },
            "summary_selection": {
                "attempted": True,
                "status": "built",
                "skipped_reason": None,
            },
            "duplicate_check": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "near_duplicate_checkpoint_closeout",
            },
        },
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 3
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_does_not_treat_old_closeout_as_near_duplicate() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
    episode_repository.episodes[0] = make_aged_episode_copy(original_result.episode)

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
    assert later_result.details["auto_memory_recorded"] is True
    assert later_result.details["embedding_persistence_status"] == "skipped"
    assert (
        later_result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 6


def test_complete_workflow_auto_memory_does_not_treat_different_verify_status_as_near_duplicate() -> (
    None
):
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
    assert second_result.details["auto_memory_recorded"] is True
    assert second_result.details["embedding_persistence_status"] == "skipped"
    assert (
        second_result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 6
    assert episode_repository.episodes[1].metadata["verify_status"] == "failed"


def test_complete_workflow_auto_memory_skips_near_duplicate_with_high_summary_similarity() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "passed",
                "skipped_reason": None,
            },
            "summary_selection": {
                "attempted": True,
                "status": "built",
                "skipped_reason": None,
            },
            "duplicate_check": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "near_duplicate_checkpoint_closeout",
            },
        },
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 3
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_skips_near_duplicate_when_similarity_is_only_boilerplate_driven() -> (
    None
):
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "passed",
                "skipped_reason": None,
            },
            "summary_selection": {
                "attempted": True,
                "status": "built",
                "skipped_reason": None,
            },
            "duplicate_check": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "near_duplicate_checkpoint_closeout",
            },
        },
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 3
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_records_when_summary_similarity_is_below_threshold() -> None:
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
            summary=(
                "Documented operator-facing rollout guidance for the refined suppression logic"
            ),
            checkpoint_json={
                "next_intended_action": ("Publish operator-facing duplicate suppression notes"),
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
    assert second_result.details["auto_memory_recorded"] is True
    assert second_result.details["embedding_persistence_status"] == "skipped"
    assert (
        second_result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 6
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_extracts_semantic_fields_from_summary_lines() -> None:
    bridge, _, _, _, _ = build_recording_workflow_memory_bridge()

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
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
        "stage_details": {
            "gating": {
                "attempted": True,
                "status": "passed",
                "skipped_reason": None,
            },
            "summary_selection": {
                "attempted": True,
                "status": "built",
                "skipped_reason": None,
            },
            "duplicate_check": {
                "attempted": True,
                "status": "skipped",
                "skipped_reason": "near_duplicate_checkpoint_closeout",
            },
        },
    }
    assert len(episode_repository.episodes) == 1
    assert len(memory_item_repository.memory_items) == 3
    assert len(memory_embedding_repository.embeddings) == 0


def test_complete_workflow_auto_memory_does_not_treat_different_attempt_status_as_near_duplicate() -> (
    None
):
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
    assert second_result.details["auto_memory_recorded"] is True
    assert second_result.details["embedding_persistence_status"] == "skipped"
    assert (
        second_result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 6
    assert episode_repository.episodes[1].metadata["attempt_status"] == "failed"


def test_complete_workflow_auto_memory_does_not_treat_different_failure_reason_as_near_duplicate() -> (
    None
):
    (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
        _memory_relation_repository,
    ) = build_recording_workflow_memory_bridge()
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
    assert second_result.details["auto_memory_recorded"] is True
    assert second_result.details["embedding_persistence_status"] == "skipped"
    assert (
        second_result.details["embedding_generation_skipped_reason"]
        == "embedding_persistence_not_configured"
    )
    assert len(episode_repository.episodes) == 2
    assert len(memory_item_repository.memory_items) == 8
    assert episode_repository.episodes[1].metadata["failure_reason"] == "second failure path"
