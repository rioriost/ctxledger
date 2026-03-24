from __future__ import annotations

from ctxledger.memory.service import (
    BuildEpisodeSummaryRequest,
    GetMemoryContextRequest,
    MemoryFeature,
    MemoryService,
    RememberEpisodeRequest,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkMemorySummaryMembershipRepository,
    UnitOfWorkMemorySummaryRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    RegisterWorkspaceInput,
    StartWorkflowInput,
    WorkflowInstanceStatus,
    WorkflowService,
)


def _build_postgres_summary_memory_service(uow_factory) -> MemoryService:
    return MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_summary_repository=UnitOfWorkMemorySummaryRepository(uow_factory),
        memory_summary_membership_repository=UnitOfWorkMemorySummaryMembershipRepository(
            uow_factory
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )


def test_postgres_memory_get_context_returns_multiple_workflow_episodes(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context.git",
            canonical_path="/tmp/integration-repo-memory-context",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-001",
        )
    )

    first_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Investigated root cause",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "investigation"},
        )
    )
    second_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Applied durable fix",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "implementation"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert first_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert second_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert len(context.episodes) == 2
    assert [episode.summary for episode in context.episodes] == [
        "Applied durable fix",
        "Investigated root cause",
    ]
    assert context.details["query"] is None
    assert context.details["normalized_query"] is None
    assert context.details["lookup_scope"] == "workflow_instance"
    assert context.details["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert context.details["resolved_workflow_ids"] == [
        str(started.workflow_instance.workflow_instance_id)
    ]
    assert context.details["resolved_workflow_count"] == 1
    assert context.details["query_filter_applied"] is False
    assert context.details["episodes_before_query_filter"] == 2
    assert context.details["matched_episode_count"] == 2
    assert context.details["episodes_returned"] == 2


def test_postgres_memory_get_context_returns_workspace_episodes(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-workspace.git",
            canonical_path="/tmp/integration-repo-memory-context-workspace",
            default_branch="main",
        )
    )
    first_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-WS-001",
        )
    )
    workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=first_started.workflow_instance.workflow_instance_id,
            attempt_id=first_started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )
    second_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-WS-002",
        )
    )

    older_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(first_started.workflow_instance.workflow_instance_id),
            summary="Workspace episode from older workflow",
            attempt_id=str(first_started.attempt.attempt_id),
            metadata={"kind": "investigation"},
        )
    )
    newer_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(second_started.workflow_instance.workflow_instance_id),
            summary="Workspace episode from newer workflow",
            attempt_id=str(second_started.attempt.attempt_id),
            metadata={"kind": "implementation"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workspace_id=str(workspace.workspace_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert older_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert newer_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert [episode.summary for episode in context.episodes] == [
        "Workspace episode from newer workflow",
        "Workspace episode from older workflow",
    ]
    assert context.details["query"] is None
    assert context.details["normalized_query"] is None
    assert context.details["lookup_scope"] == "workspace"
    assert context.details["workspace_id"] == str(workspace.workspace_id)
    assert context.details["workflow_instance_id"] is None
    assert context.details["ticket_id"] is None
    assert sorted(context.details["resolved_workflow_ids"]) == sorted(
        [
            str(first_started.workflow_instance.workflow_instance_id),
            str(second_started.workflow_instance.workflow_instance_id),
        ]
    )
    assert context.details["resolved_workflow_count"] == 2
    assert context.details["query_filter_applied"] is False
    assert context.details["episodes_before_query_filter"] == 2
    assert context.details["matched_episode_count"] == 2
    assert context.details["episodes_returned"] == 2


def test_postgres_memory_get_context_returns_ticket_episodes(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
    )

    first_workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-ticket-a.git",
            canonical_path="/tmp/integration-repo-memory-context-ticket-a",
            default_branch="main",
        )
    )
    second_workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-ticket-b.git",
            canonical_path="/tmp/integration-repo-memory-context-ticket-b",
            default_branch="main",
        )
    )

    first_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-TICKET-001",
        )
    )
    second_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=second_workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-TICKET-001",
        )
    )

    older_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(first_started.workflow_instance.workflow_instance_id),
            summary="Ticket episode from first workspace",
            attempt_id=str(first_started.attempt.attempt_id),
            metadata={"kind": "investigation"},
        )
    )
    newer_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(second_started.workflow_instance.workflow_instance_id),
            summary="Ticket episode from second workspace",
            attempt_id=str(second_started.attempt.attempt_id),
            metadata={"kind": "implementation"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            ticket_id="INTEG-MEMCTX-TICKET-001",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert older_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert newer_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert [episode.summary for episode in context.episodes] == [
        "Ticket episode from second workspace",
        "Ticket episode from first workspace",
    ]
    assert context.details["query"] is None
    assert context.details["normalized_query"] is None
    assert context.details["lookup_scope"] == "ticket"
    assert context.details["workspace_id"] is None
    assert context.details["workflow_instance_id"] is None
    assert context.details["ticket_id"] == "INTEG-MEMCTX-TICKET-001"
    assert sorted(context.details["resolved_workflow_ids"]) == sorted(
        [
            str(first_started.workflow_instance.workflow_instance_id),
            str(second_started.workflow_instance.workflow_instance_id),
        ]
    )
    assert context.details["resolved_workflow_count"] == 2
    assert context.details["query_filter_applied"] is False
    assert context.details["episodes_before_query_filter"] == 2
    assert context.details["matched_episode_count"] == 2
    assert context.details["episodes_returned"] == 2


def test_postgres_memory_get_context_applies_initial_query_filtering(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-query.git",
            canonical_path="/tmp/integration-repo-memory-context-query",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-QUERY-001",
        )
    )

    memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Fix flaky postgres startup ordering",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "stabilization", "component": "postgres"},
        )
    )
    memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Document release checklist",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "docs", "component": "release"},
        )
    )
    memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Track filtering semantics decision",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "analysis", "component": "metadata-filter"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            query="postgres",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert [episode.summary for episode in context.episodes] == [
        "Fix flaky postgres startup ordering",
    ]
    assert context.details["query"] == "postgres"
    assert context.details["normalized_query"] == "postgres"
    assert context.details["lookup_scope"] == "workflow_instance"
    assert context.details["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert context.details["resolved_workflow_ids"] == [
        str(started.workflow_instance.workflow_instance_id)
    ]
    assert context.details["resolved_workflow_count"] == 1
    assert context.details["query_filter_applied"] is True
    assert context.details["episodes_before_query_filter"] == 3
    assert context.details["matched_episode_count"] == 1
    assert context.details["episodes_returned"] == 1

    metadata_context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            query="metadata-filter",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert metadata_context.feature == MemoryFeature.GET_CONTEXT
    assert metadata_context.implemented is True
    assert [episode.summary for episode in metadata_context.episodes] == [
        "Track filtering semantics decision",
    ]
    assert metadata_context.details["query"] == "metadata-filter"
    assert metadata_context.details["normalized_query"] == "metadata-filter"
    assert metadata_context.details["lookup_scope"] == "workflow_instance"
    assert metadata_context.details["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert metadata_context.details["resolved_workflow_ids"] == [
        str(started.workflow_instance.workflow_instance_id)
    ]
    assert metadata_context.details["resolved_workflow_count"] == 1
    assert metadata_context.details["query_filter_applied"] is True
    assert metadata_context.details["episodes_before_query_filter"] == 3
    assert metadata_context.details["matched_episode_count"] == 1
    assert metadata_context.details["episodes_returned"] == 1


def test_postgres_memory_get_context_uses_built_canonical_episode_summary(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = _build_postgres_summary_memory_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-built-summary.git",
            canonical_path="/tmp/integration-repo-memory-context-built-summary",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-SUMMARY-BUILD-001",
        )
    )

    first_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Captured the initial hierarchy design direction",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "design"},
        )
    )
    second_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Confirmed retrieval contract behavior for canonical summaries",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "validation"},
        )
    )

    assert first_episode.episode is not None
    built_summary = memory_service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(first_episode.episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )

    assert second_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert built_summary.summary is not None
    assert built_summary.summary_built is True
    assert built_summary.status == "built"
    assert built_summary.replaced_existing_summary is False

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
    assert context.implemented is True
    assert context.details["summary_selection_applied"] is True
    assert context.details["summary_selection_kind"] == "memory_summary_first"
    assert context.details["retrieval_routes_present"][0] == "summary_first"
    assert context.details["primary_retrieval_routes_present"][0] == "summary_first"
    assert context.details["summaries"][0]["memory_summary_id"] == str(
        built_summary.summary.memory_summary_id
    )
    assert context.details["summaries"][0]["episode_id"] == str(first_episode.episode.episode_id)
    assert context.details["summaries"][0]["summary_kind"] == "episode_summary"
    assert context.details["summaries"][0]["metadata"]["builder"] == (
        "minimal_episode_summary_builder"
    )
    assert context.details["summaries"][0]["member_memory_count"] == 1
    assert context.details["summaries"][0]["summary_text"] == (
        "Captured the initial hierarchy design direction\n\nIncluded memory items:\n- "
        "Captured the initial hierarchy design direction"
    )
    assert context.details["memory_context_groups"][0]["selection_kind"] == ("memory_summary_first")
    assert context.details["memory_context_groups"][0]["selection_route"] == "summary_first"


def test_postgres_memory_get_context_uses_rebuilt_canonical_summary_after_replace_existing(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = _build_postgres_summary_memory_service(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-rebuilt-summary.git",
            canonical_path="/tmp/integration-repo-memory-context-rebuilt-summary",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-SUMMARY-BUILD-002",
        )
    )

    remembered = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Initial episode text before rebuild",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "design"},
        )
    )
    assert remembered.episode is not None

    first_build = memory_service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(remembered.episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )
    assert first_build.summary is not None

    remember_followup = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Additional follow-up note that should appear after rebuild",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "followup"},
        )
    )

    rebuilt = memory_service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(remembered.episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )

    assert remember_followup.feature == MemoryFeature.REMEMBER_EPISODE
    assert rebuilt.summary is not None
    assert rebuilt.summary_built is True
    assert rebuilt.replaced_existing_summary is True

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
    assert context.implemented is True
    assert context.details["summary_selection_applied"] is True
    assert context.details["summary_selection_kind"] == "memory_summary_first"
    assert len(context.details["summaries"]) == 1
    rebuilt_summary_entry = context.details["summaries"][0]
    assert rebuilt_summary_entry["memory_summary_id"] == str(rebuilt.summary.memory_summary_id)
    assert rebuilt_summary_entry["summary_text"] == (
        "Initial episode text before rebuild\n\nIncluded memory items:\n- "
        "Initial episode text before rebuild"
    )
    assert rebuilt_summary_entry["member_memory_count"] == 1

    first_build_ids = {
        str(first_build.summary.memory_summary_id),
    }
    assert rebuilt_summary_entry["memory_summary_id"] not in first_build_ids
