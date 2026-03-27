from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.config import (
    EmbeddingProvider,
    EmbeddingSettings,
)
from ctxledger.memory.embeddings import build_embedding_generator
from ctxledger.memory.service import (
    GetMemoryContextRequest,
    MemoryFeature,
    MemoryService,
    SearchMemoryRequest,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkMemorySummaryMembershipRepository,
    UnitOfWorkMemorySummaryRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstanceStatus,
    WorkflowService,
)


def _build_local_stub_workflow_service(
    uow_factory,
    *,
    enable_summary_builder: bool = False,
) -> WorkflowService:
    summary_builder = (
        MemoryService(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_summary_repository=UnitOfWorkMemorySummaryRepository(uow_factory),
            memory_summary_membership_repository=UnitOfWorkMemorySummaryMembershipRepository(
                uow_factory
            ),
            workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
            workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
        )
        if enable_summary_builder
        else None
    )

    return WorkflowService(
        uow_factory,
        workflow_memory_bridge=WorkflowMemoryBridge(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
            summary_builder=summary_builder,
            embedding_generator=build_embedding_generator(
                EmbeddingSettings(
                    provider=EmbeddingProvider.LOCAL_STUB,
                    model="local-stub-v1",
                    api_key=None,
                    base_url=None,
                    dimensions=1536,
                    enabled=True,
                )
            ),
        ),
    )


def _build_local_stub_memory_service(uow_factory) -> MemoryService:
    return MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=build_embedding_generator(
            EmbeddingSettings(
                provider=EmbeddingProvider.LOCAL_STUB,
                model="local-stub-v1",
                api_key=None,
                base_url=None,
                dimensions=1536,
                enabled=True,
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )


def test_postgres_workflow_complete_auto_records_memory_and_embedding(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-memory.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-memory",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-COMPLETE-001",
        )
    )
    checkpoint_result = workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="validate_openai",
            summary="Broader targeted regression is green",
            checkpoint_json={"next_intended_action": "Review diff and commit"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Validated OpenAI embedding integration end to end",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )

        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1
        auto_episode = auto_episodes[0]

        episode_memory_items = uow.memory_items.list_by_episode_id(
            auto_episode.episode_id,
            limit=10,
        )
        assert len(episode_memory_items) == 3
        auto_memory_item = next(
            memory_item
            for memory_item in episode_memory_items
            if memory_item.type == "workflow_completion_note"
        )

        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            auto_memory_item.memory_id,
            limit=10,
        )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert checkpoint_result.verify_report is not None
    assert checkpoint_result.verify_report.status == VerifyStatus.PASSED

    assert auto_episode.workflow_instance_id == (started.workflow_instance.workflow_instance_id)
    assert auto_episode.attempt_id == started.attempt.attempt_id
    assert auto_episode.metadata == {
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
        auto_episode.summary
    )
    assert "Latest checkpoint summary: Broader targeted regression is green" in (
        auto_episode.summary
    )
    assert "Last planned next action: Review diff and commit" in auto_episode.summary
    assert "Verify status: passed" in auto_episode.summary
    assert "Workflow status: completed" in auto_episode.summary
    assert "Workflow status: completed" in auto_episode.summary

    assert auto_memory_item.workspace_id == workspace.workspace_id
    assert auto_memory_item.episode_id == auto_episode.episode_id
    assert auto_memory_item.type == "workflow_completion_note"
    assert auto_memory_item.provenance == "workflow_complete_auto"
    assert auto_memory_item.content == auto_episode.summary
    assert auto_memory_item.metadata == auto_episode.metadata
    assert {memory_item.type for memory_item in episode_memory_items} == {
        "workflow_completion_note",
        "workflow_next_action",
        "workflow_verification_outcome",
    }
    assert {memory_item.type for memory_item in episode_memory_items} == {
        "workflow_completion_note",
        "workflow_next_action",
        "workflow_verification_outcome",
    }

    assert len(memory_embeddings) == 1
    assert memory_embeddings[0].memory_id == auto_memory_item.memory_id
    assert memory_embeddings[0].embedding_model == "local-stub-v1"
    assert len(memory_embeddings[0].embedding) == 1536
    assert memory_embeddings[0].content_hash is not None


def test_postgres_workflow_complete_auto_memory_is_searchable(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)
    memory_service = _build_local_stub_memory_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-search.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-search",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SEARCH-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="investigate_projection_drift",
            summary="Investigated projection drift root cause in deployment workflow",
            checkpoint_json={"next_intended_action": "Write fix and validate semantic retrieval"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Validated projection drift fix and semantic retrieval",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert completed.auto_memory_details is not None
    assert completed.auto_memory_details["auto_memory_recorded"] is True
    assert completed.auto_memory_details["embedding_persistence_status"] == "stored"
    assert completed.warnings == ()

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "hybrid_memory_item_search"
    assert search.details["semantic_candidates_considered"] >= 1
    assert search.details["semantic_query_generated"] is True
    assert search.details["memory_items_considered"] >= 1
    assert search.details["results_returned"] >= 1
    assert len(search.results) >= 1

    top_result = search.results[0]
    assert top_result.summary in {
        "Workflow completed with status `completed`.\n"
        "Completion summary: Validated projection drift fix and semantic retrieval\n"
        "Latest checkpoint summary: Investigated projection drift root cause in deployment workflow\n"
        "Last planned next action: Write fix and validate semantic retrieval\n"
        "Verify status: passed\n"
        "Workflow status: completed",
        "Checkpoint recorded for workflow status `running`.\n"
        "Checkpoint summary: Investigated projection drift root cause in deployment workflow\n"
        "Next intended action: Write fix and validate semantic retrieval\n"
        "Verify status: passed",
        "Checkpoint recorded for workflow status `running`.\n"
        "Checkpoint summary: Investigated projection drift root cause in deployment workflow\n"
        "Next action: Write fix and validate semantic retrieval\n"
        "Verify status: passed",
    }
    assert top_result.semantic_score >= 0.0
    assert top_result.score > 0.0
    assert top_result.ranking_details["semantic_component"] >= 0.0
    assert top_result.metadata["memory_origin"] in {
        "workflow_checkpoint_auto",
        "workflow_complete_auto",
    }
    assert top_result.metadata["verify_status"] == "passed"
    assert top_result.metadata["step_name"] == "investigate_projection_drift"
    assert (
        top_result.metadata.get("next_intended_action")
        == "Write fix and validate semantic retrieval"
    )
    assert (
        "embedding_similarity" in top_result.matched_fields
        or "content" in top_result.matched_fields
    )


def test_postgres_workflow_complete_auto_memory_skips_low_signal_closeout(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-low-signal.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-low-signal",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-LOW-SIGNAL-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="minor_note",
            summary="Tiny progress note",
            checkpoint_json={},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed a low-signal pass",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        assert uow.memory_items is not None

        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert completed.auto_memory_details == {
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
    assert completed.warnings == ()
    assert auto_episodes == []
    assert [item.metadata.get("memory_origin") for item in workspace_items] == [
        "workflow_checkpoint_auto",
        "workflow_checkpoint_auto",
    ]


def test_postgres_workflow_complete_auto_memory_builds_summary_when_gated_builder_is_enabled(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(
        uow_factory,
        enable_summary_builder=True,
    )
    memory_service = _build_local_stub_memory_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-build.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-build",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-BUILD-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="summarize_completion",
            summary="Checkpoint summary for gated summary build",
            checkpoint_json={
                "auto_memory": True,
                "build_episode_summary": True,
                "next_intended_action": "Inspect the built summary and retrieval path",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed workflow with explicit gated summary build",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        assert uow.memory_summaries is not None
        assert uow.memory_summary_memberships is not None

        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1
        auto_episode = auto_episodes[0]

        built_summaries = uow.memory_summaries.list_by_episode_id(
            auto_episode.episode_id,
            limit=10,
        )
        assert len(built_summaries) == 1
        built_summary = built_summaries[0]

        memberships = uow.memory_summary_memberships.list_by_summary_id(
            built_summary.memory_summary_id,
            limit=10,
        )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert completed.auto_memory_details is not None
    assert completed.auto_memory_details["auto_memory_recorded"] is True
    summary_build_details = completed.auto_memory_details["summary_build"]
    assert summary_build_details["summary_build_attempted"] is True
    assert summary_build_details["summary_build_succeeded"] is True
    assert summary_build_details["summary_build_status"] == "built"
    assert summary_build_details["summary_build_skipped_reason"] is None
    assert summary_build_details["summary_build_replaced_existing_summary"] is False
    assert summary_build_details["built_memory_summary_id"] == str(built_summary.memory_summary_id)
    assert summary_build_details["built_summary_kind"] == "episode_summary"
    assert summary_build_details["built_summary_membership_count"] == 3
    assert completed.warnings == ()
    assert built_summary.summary_kind == "episode_summary"
    assert built_summary.metadata["builder"] == "minimal_episode_summary_builder"
    assert built_summary.metadata["source"] == "workflow_completion_auto_memory"
    assert built_summary.metadata["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert built_summary.metadata["auto_memory_episode_id"] == str(auto_episode.episode_id)
    assert built_summary.metadata["remember_path_memory_origins"] == ["workflow_complete_auto"]
    assert built_summary.metadata["remember_path_promotion_fields"] == [
        "next_intended_action",
        "verify_status",
    ]
    assert built_summary.metadata["remember_path_promotion_sources"] == [
        "latest_checkpoint.next_intended_action",
        "verify_report.status",
    ]
    assert built_summary.metadata["remember_path_memory_origins"] == ["workflow_complete_auto"]
    assert built_summary.metadata["remember_path_promotion_fields"] == [
        "next_intended_action",
        "verify_status",
    ]
    assert built_summary.metadata["remember_path_promotion_sources"] == [
        "latest_checkpoint.next_intended_action",
        "verify_report.status",
    ]
    assert len(memberships) == 3

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.details["summary_selection_applied"] is True
    assert context.details["summary_selection_kind"] == "episode_summary_first"
    matching_summaries = [
        summary
        for summary in context.details["summaries"]
        if summary["episode_id"] == str(auto_episode.episode_id)
    ]
    assert len(matching_summaries) == 1
    auto_summary = matching_summaries[0]
    assert auto_summary["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert auto_summary["memory_item_count"] == 3
    assert set(auto_summary["memory_item_types"]) == {
        "workflow_completion_note",
        "workflow_next_action",
        "workflow_verification_outcome",
    }
    assert auto_summary["memory_item_provenance"] == [
        "workflow_complete_auto",
        "workflow_complete_auto",
        "workflow_complete_auto",
    ]
    assert auto_summary["remember_path_explainability"] == {
        "memory_origins": ["workflow_complete_auto"],
        "promotion_fields": [
            "next_intended_action",
            "verify_status",
        ],
        "promotion_sources": [
            "latest_checkpoint.next_intended_action",
            "verify_report.status",
        ],
        "relation_reasons": [],
        "relation_reason_primary": None,
        "relation_reasons_frontloaded": False,
        "relation_reason_count": 0,
        "relation_reason_counts": {},
        "relation_origins": [],
    }


def test_postgres_workflow_complete_auto_memory_skips_summary_build_when_trigger_is_absent(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(
        uow_factory,
        enable_summary_builder=True,
    )
    memory_service = _build_local_stub_memory_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-build-skip.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-build-skip",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-BUILD-TRIGGER-ABSENT-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="summarize_completion",
            summary="Checkpoint summary without summary-build trigger",
            checkpoint_json={
                "auto_memory": True,
                "next_intended_action": "Inspect the retrieval path without explicit summary build",
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed workflow without requesting gated summary build",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        assert uow.memory_summaries is not None
        assert uow.memory_summary_memberships is not None

        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1
        auto_episode = auto_episodes[0]

        built_summaries = uow.memory_summaries.list_by_episode_id(
            auto_episode.episode_id,
            limit=10,
        )
        memberships = (
            uow.memory_summary_memberships.list_by_summary_id(
                built_summaries[0].memory_summary_id,
                limit=10,
            )
            if built_summaries
            else ()
        )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert completed.auto_memory_details is not None
    assert completed.auto_memory_details["auto_memory_recorded"] is True
    summary_build_details = completed.auto_memory_details["summary_build"]
    assert summary_build_details["summary_build_attempted"] is False
    assert summary_build_details["summary_build_succeeded"] is False
    assert summary_build_details["summary_build_status"] is None
    assert (
        summary_build_details["summary_build_skipped_reason"]
        == "workflow_summary_build_not_requested"
    )
    assert summary_build_details["summary_build_replaced_existing_summary"] is False
    assert summary_build_details["built_memory_summary_id"] is None
    assert summary_build_details["built_summary_kind"] == "episode_summary"
    assert summary_build_details["built_summary_membership_count"] == 0
    assert completed.warnings == ()
    assert built_summaries == ()
    assert memberships == ()

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.details["summary_selection_applied"] is True
    assert context.details["summary_selection_kind"] == "episode_summary_first"
    matching_summaries = [
        summary
        for summary in context.details["summaries"]
        if summary["episode_id"] == str(auto_episode.episode_id)
    ]
    assert len(matching_summaries) == 1
    auto_summary = matching_summaries[0]
    assert auto_summary["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert auto_summary["memory_item_count"] == 3
    assert set(auto_summary["memory_item_types"]) == {
        "workflow_completion_note",
        "workflow_next_action",
        "workflow_verification_outcome",
    }
    assert auto_summary["memory_item_provenance"] == [
        "workflow_complete_auto",
        "workflow_complete_auto",
        "workflow_complete_auto",
    ]
    assert auto_summary["remember_path_explainability"] == {
        "memory_origins": ["workflow_complete_auto"],
        "promotion_fields": [
            "next_intended_action",
            "verify_status",
        ],
        "promotion_sources": [
            "latest_checkpoint.next_intended_action",
            "verify_report.status",
        ],
        "relation_reasons": [],
        "relation_reason_primary": None,
        "relation_reasons_frontloaded": False,
        "relation_reason_count": 0,
        "relation_reason_counts": {},
        "relation_origins": [],
    }


def test_postgres_workflow_complete_auto_memory_suppresses_duplicate_closeout(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-duplicate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-duplicate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-DUPE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Checkpoint summary for duplicate suppression",
            checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed heuristic planning pass",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    reopened_attempt = workflow_service.resume_workflow(
        ResumeWorkflowInput(workflow_instance_id=started.workflow_instance.workflow_instance_id)
    )
    assert reopened_attempt.resumable_status == ResumableStatus.TERMINAL

    duplicate_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=first_completed.attempt,
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Checkpoint summary for duplicate suppression",
            checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Completed heuristic planning pass",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert first_completed.auto_memory_details["embedding_persistence_status"] == "stored"
    assert first_completed.auto_memory_details["embedding_generation_skipped_reason"] is None
    assert first_completed.auto_memory_details["embedding_provider"] == "local_stub"
    assert first_completed.auto_memory_details["embedding_model"] == "local-stub-v1"
    assert first_completed.auto_memory_details["embedding_vector_dimensions"] == 1536
    assert first_completed.auto_memory_details["embedding_content_hash"] is not None
    assert duplicate_result is not None
    assert duplicate_result.details["auto_memory_recorded"] is False
    assert duplicate_result.details["auto_memory_skipped_reason"] == (
        "duplicate_closeout_auto_memory"
    )
    assert duplicate_result.details["stage_details"] == {
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
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_suppresses_near_duplicate_closeout(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-near-duplicate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-near-duplicate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-NEAR-DUPE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="First completion summary",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Second checkpoint summary",
                checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Second completion summary",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details["auto_memory_recorded"] is False
    assert near_duplicate_result.details["auto_memory_skipped_reason"] == (
        "near_duplicate_checkpoint_closeout"
    )
    assert near_duplicate_result.details["stage_details"] == {
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
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_skips_near_duplicate_with_high_summary_similarity(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-similar.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-similar",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-SIMILAR-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={"next_intended_action": "Implement summary similarity gating"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Implemented summary similarity gating for duplicate suppression",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Investigated duplicate suppression behavior again",
                checkpoint_json={"next_intended_action": "Implement summary similarity gating"},
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Implemented gating for summary similarity in duplicate suppression",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details["auto_memory_recorded"] is False
    assert near_duplicate_result.details["auto_memory_skipped_reason"] == (
        "near_duplicate_checkpoint_closeout"
    )
    assert near_duplicate_result.details["stage_details"] == {
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
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_skips_near_duplicate_when_similarity_is_only_boilerplate_driven(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-boilerplate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-boilerplate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-BOILERPLATE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={"next_intended_action": "Implement summary similarity gating"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Implemented summary similarity gating for duplicate suppression",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Investigated duplicate suppression behavior for another path",
                checkpoint_json={"next_intended_action": "Implement summary similarity gating"},
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Implemented summary similarity gating for duplicate suppression",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details["auto_memory_recorded"] is False
    assert near_duplicate_result.details["auto_memory_skipped_reason"] == (
        "near_duplicate_checkpoint_closeout"
    )
    assert near_duplicate_result.details["stage_details"] == {
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
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_does_not_treat_old_closeout_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-old-near-duplicate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-old-near-duplicate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-OLD-NEAR-DUPE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="First completion summary",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        existing_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in existing_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        existing_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in existing_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1

        aged_episode = auto_episodes[0]
        assert hasattr(uow, "_conn")
        with uow._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE episodes
                SET created_at = %s, updated_at = %s
                WHERE episode_id = %s
                """,
                (
                    datetime(2024, 1, 1, tzinfo=UTC),
                    datetime(2024, 1, 1, tzinfo=UTC),
                    str(aged_episode.episode_id),
                ),
            )
        uow.commit()

    later_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=first_completed.attempt,
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Second checkpoint summary",
            checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Second completion summary",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        refreshed_auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert later_result is not None
    assert later_result.details["auto_memory_recorded"] is True
    assert later_result.details["embedding_persistence_status"] == "stored"
    assert later_result.details["embedding_generation_skipped_reason"] is None
    assert later_result.details["embedding_provider"] == "local_stub"
    assert later_result.details["embedding_model"] == "local-stub-v1"
    assert later_result.details["embedding_vector_dimensions"] == 1536
    assert later_result.details["embedding_content_hash"] is not None
    assert len(refreshed_auto_episodes) == 2


def test_postgres_workflow_complete_auto_memory_records_when_summary_similarity_is_below_threshold(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-dissimilar.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-dissimilar",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-DISSIMILAR-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={"next_intended_action": "Implement summary similarity gating"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Implemented summary similarity gating for duplicate suppression",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    different_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=first_completed.attempt,
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Documented operator-facing rollout guidance for the refined suppression logic",
            checkpoint_json={
                "next_intended_action": "Publish operator-facing duplicate suppression notes"
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Documented rollout notes for operators after validation",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert different_result is not None
    assert different_result.details["auto_memory_recorded"] is True
    assert different_result.details["embedding_persistence_status"] == "stored"
    assert different_result.details["embedding_generation_skipped_reason"] is None
    assert different_result.details["embedding_provider"] == "local_stub"
    assert different_result.details["embedding_model"] == "local-stub-v1"
    assert different_result.details["embedding_vector_dimensions"] == 1536
    assert different_result.details["embedding_content_hash"] is not None
    assert len(auto_episodes) == 2


def test_postgres_workflow_complete_auto_memory_uses_extracted_and_metadata_fields_for_near_duplicate_matching(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-metadata-aware.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-metadata-aware",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-METADATA-AWARE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared extracted closeout fields",
            checkpoint_json={"next_intended_action": "Implement metadata-aware duplicate matching"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Refined metadata-aware closeout duplicate detection",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Compared extracted closeout fields again",
                checkpoint_json={
                    "next_intended_action": "Implement metadata-aware duplicate matching"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Refined duplicate detection with metadata-aware closeout matching",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details["auto_memory_recorded"] is False
    assert near_duplicate_result.details["auto_memory_skipped_reason"] == (
        "near_duplicate_checkpoint_closeout"
    )
    assert near_duplicate_result.details["stage_details"] == {
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
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_does_not_treat_different_attempt_status_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-attempt-status-diff.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-attempt-status-diff",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-ATTEMPT-STATUS-DIFF-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields",
            checkpoint_json={"next_intended_action": "Implement metadata-aware duplicate matching"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed weighted duplicate matching refinement",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    attempt_different_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=WorkflowAttempt(
                attempt_id=started.attempt.attempt_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_number=2,
                status=WorkflowAttemptStatus.FAILED,
                verify_status=VerifyStatus.PASSED,
                started_at=started.attempt.started_at,
                finished_at=datetime.now(UTC),
                created_at=started.attempt.created_at,
                updated_at=datetime.now(UTC),
            ),
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Compared weighted closeout fields again",
                checkpoint_json={
                    "next_intended_action": "Implement metadata-aware duplicate matching"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Completed weighted closeout duplicate matching refinement",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert attempt_different_result is not None
    assert attempt_different_result.details["auto_memory_recorded"] is True
    assert attempt_different_result.details["embedding_persistence_status"] == "stored"
    assert attempt_different_result.details["embedding_generation_skipped_reason"] is None
    assert attempt_different_result.details["embedding_provider"] == "local_stub"
    assert attempt_different_result.details["embedding_model"] == "local-stub-v1"
    assert attempt_different_result.details["embedding_vector_dimensions"] == 1536
    assert attempt_different_result.details["embedding_content_hash"] is not None
    assert len(auto_episodes) == 2
    assert any(episode.metadata.get("attempt_status") == "failed" for episode in auto_episodes)


def test_postgres_workflow_complete_auto_memory_does_not_treat_different_failure_reason_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-failure-reason-diff.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-failure-reason-diff",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-FAILURE-REASON-DIFF-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields",
            checkpoint_json={"next_intended_action": "Implement metadata-aware duplicate matching"},
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.FAILED,
            summary="Failed while refining metadata-aware duplicate matching",
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
            failure_reason="first failure path",
        )
    )

    failure_reason_different_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=WorkflowAttempt(
                attempt_id=started.attempt.attempt_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_number=2,
                status=WorkflowAttemptStatus.FAILED,
                verify_status=VerifyStatus.FAILED,
                failure_reason="second failure path",
                started_at=started.attempt.started_at,
                finished_at=datetime.now(UTC),
                created_at=started.attempt.created_at,
                updated_at=datetime.now(UTC),
            ),
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Compared weighted closeout fields again",
                checkpoint_json={
                    "next_intended_action": "Implement metadata-aware duplicate matching"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.FAILED,
                report_json={"checks": ["pytest"], "status": "failed"},
            ),
            summary="Failed while refining duplicate matching with metadata-aware fields",
            failure_reason="second failure path",
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert failure_reason_different_result is not None
    assert failure_reason_different_result.details["auto_memory_recorded"] is True
    assert failure_reason_different_result.details["embedding_persistence_status"] == "stored"
    assert failure_reason_different_result.details["embedding_generation_skipped_reason"] is None
    assert failure_reason_different_result.details["embedding_provider"] == "local_stub"
    assert failure_reason_different_result.details["embedding_model"] == "local-stub-v1"
    assert failure_reason_different_result.details["embedding_vector_dimensions"] == 1536
    assert failure_reason_different_result.details["embedding_content_hash"] is not None
    assert len(auto_episodes) == 2
    assert any(
        episode.metadata.get("failure_reason") == "second failure path" for episode in auto_episodes
    )


def test_postgres_workflow_complete_auto_memory_does_not_treat_different_verify_status_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = _build_local_stub_workflow_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-verify-diff.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-verify-diff",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-VERIFY-DIFF-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="First completion summary",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    verify_different_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=WorkflowAttempt(
                attempt_id=started.attempt.attempt_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_number=started.attempt.attempt_number,
                status=WorkflowAttemptStatus.SUCCEEDED,
                verify_status=VerifyStatus.FAILED,
                started_at=started.attempt.started_at,
                finished_at=datetime.now(UTC),
                created_at=started.attempt.created_at,
                updated_at=datetime.now(UTC),
            ),
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Second checkpoint summary",
                checkpoint_json={"next_intended_action": "Implement the minimum heuristic path"},
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.FAILED,
                report_json={"checks": ["pytest"], "status": "failed"},
            ),
            summary="Second completion summary",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert verify_different_result is not None
    assert verify_different_result.details["auto_memory_recorded"] is True
    assert verify_different_result.details["embedding_persistence_status"] == "stored"
    assert verify_different_result.details["embedding_generation_skipped_reason"] is None
    assert verify_different_result.details["embedding_provider"] == "local_stub"
    assert verify_different_result.details["embedding_model"] == "local-stub-v1"
    assert verify_different_result.details["embedding_vector_dimensions"] == 1536
    assert verify_different_result.details["embedding_content_hash"] is not None
    assert len(auto_episodes) == 2
    assert any(episode.metadata.get("verify_status") == "failed" for episode in auto_episodes)
