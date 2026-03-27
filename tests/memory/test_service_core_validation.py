from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
)
from ctxledger.memory.service import (
    BuildEpisodeSummaryRequest,
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
)


def test_memory_service_raises_validation_errors_for_invalid_requests() -> None:
    workflow_id = uuid4()
    service = MemoryService(
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    with pytest.raises(MemoryServiceError) as remember_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id="   ",
                summary="Episode summary",
            )
        )
    assert remember_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert remember_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert remember_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as invalid_uuid_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id="not-a-uuid",
                summary="Episode summary",
            )
        )
    assert invalid_uuid_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert invalid_uuid_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert invalid_uuid_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as missing_workflow_error:
        service.remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(uuid4()),
                summary="Episode summary",
            )
        )
    assert missing_workflow_error.value.code == MemoryErrorCode.WORKFLOW_NOT_FOUND
    assert missing_workflow_error.value.feature == MemoryFeature.REMEMBER_EPISODE

    with pytest.raises(MemoryServiceError) as interaction_content_error:
        service.persist_interaction_memory(
            content="   ",
            interaction_role="user",
            interaction_kind="interaction_request",
        )
    assert interaction_content_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert interaction_content_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert interaction_content_error.value.details == {"field": "content"}

    with pytest.raises(MemoryServiceError) as interaction_role_error:
        service.persist_interaction_memory(
            content="resume the current work",
            interaction_role="   ",
            interaction_kind="interaction_request",
        )
    assert interaction_role_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert interaction_role_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert interaction_role_error.value.details == {"field": "interaction_role"}

    with pytest.raises(MemoryServiceError) as interaction_kind_error:
        service.persist_interaction_memory(
            content="resume the current work",
            interaction_role="user",
            interaction_kind="   ",
        )
    assert interaction_kind_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert interaction_kind_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert interaction_kind_error.value.details == {"field": "interaction_kind"}

    with pytest.raises(MemoryServiceError) as interaction_workspace_error:
        service.persist_interaction_memory(
            content="resume the current work",
            interaction_role="user",
            interaction_kind="interaction_request",
            workspace_id="not-a-uuid",
        )
    assert interaction_workspace_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert interaction_workspace_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert interaction_workspace_error.value.details == {"field": "workspace_id"}

    with pytest.raises(MemoryServiceError) as interaction_workflow_error:
        service.persist_interaction_memory(
            content="resume the current work",
            interaction_role="user",
            interaction_kind="interaction_request",
            workflow_instance_id="not-a-uuid",
        )
    assert interaction_workflow_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert interaction_workflow_error.value.feature == MemoryFeature.REMEMBER_EPISODE
    assert interaction_workflow_error.value.details == {"field": "workflow_instance_id"}

    with pytest.raises(MemoryServiceError) as search_error:
        service.search(
            SearchMemoryRequest(
                query="valid query",
                limit=0,
            )
        )
    assert search_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert search_error.value.feature == MemoryFeature.SEARCH
    assert search_error.value.details == {"field": "limit", "value": 0}

    with pytest.raises(MemoryServiceError) as context_error:
        service.get_context(
            GetMemoryContextRequest(
                query=None,
                workspace_id=None,
                workflow_instance_id=None,
                ticket_id=None,
                limit=1,
            )
        )
    assert context_error.value.code == MemoryErrorCode.INVALID_REQUEST
    assert context_error.value.feature == MemoryFeature.GET_CONTEXT
    assert (
        context_error.value.message
        == "At least one of query, workspace_id, workflow_instance_id, or ticket_id must be provided."
    )


def test_memory_service_persist_interaction_memory_creates_interaction_item() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()
    memory_item_repository = InMemoryMemoryItemRepository()

    service = MemoryService(
        memory_item_repository=memory_item_repository,
        workspace_lookup=InMemoryWorkflowLookupRepository(
            {workflow_id},
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                }
            },
        ),
    )

    memory_item = service.persist_interaction_memory(
        content="resume the 0.9.0 implementation work",
        interaction_role="user",
        interaction_kind="interaction_request",
        workflow_instance_id=str(workflow_id),
        metadata={
            "transport": "http_runtime",
            "tool_name": "memory_search",
            "file_name": "interaction_memory_contract.md",
            "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
            "file_operation": "modify",
            "purpose": "capture interaction-memory contract updates",
        },
    )

    assert memory_item.type == "interaction_request"
    assert memory_item.provenance == "interaction"
    assert memory_item.workspace_id == workspace_id
    assert memory_item.episode_id is None
    assert memory_item.content == "resume the 0.9.0 implementation work"
    assert memory_item.metadata == {
        "interaction_role": "user",
        "interaction_kind": "interaction_request",
        "transport": "http_runtime",
        "tool_name": "memory_search",
        "file_name": "interaction_memory_contract.md",
        "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
        "file_operation": "modify",
        "purpose": "capture interaction-memory contract updates",
    }
    assert memory_item_repository.memory_items == (memory_item,)


def test_memory_service_persist_interaction_memory_prefers_explicit_workspace_id() -> None:
    explicit_workspace_id = uuid4()
    workflow_id = uuid4()
    derived_workspace_id = uuid4()
    memory_item_repository = InMemoryMemoryItemRepository()

    service = MemoryService(
        memory_item_repository=memory_item_repository,
        workspace_lookup=InMemoryWorkflowLookupRepository(
            {workflow_id},
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(derived_workspace_id),
                }
            },
        ),
    )

    memory_item = service.persist_interaction_memory(
        content="I will update the focused validation plan",
        interaction_role="agent",
        interaction_kind="interaction_response",
        workspace_id=str(explicit_workspace_id),
        workflow_instance_id=str(workflow_id),
        metadata={
            "transport": "http_runtime",
            "tool_name": "memory_search",
            "file_name": "0.9.0_focused_validation_plan.md",
            "file_path": "ctxledger/docs/project/releases/plans/versioned/0.9.0_focused_validation_plan.md",
            "file_operation": "create",
            "purpose": "add focused validation plan",
        },
    )

    assert memory_item.type == "interaction_response"
    assert memory_item.provenance == "interaction"
    assert memory_item.workspace_id == explicit_workspace_id
    assert memory_item.metadata == {
        "interaction_role": "agent",
        "interaction_kind": "interaction_response",
        "transport": "http_runtime",
        "tool_name": "memory_search",
        "file_name": "0.9.0_focused_validation_plan.md",
        "file_path": "ctxledger/docs/project/releases/plans/versioned/0.9.0_focused_validation_plan.md",
        "file_operation": "create",
        "purpose": "add focused validation plan",
    }
    assert memory_item_repository.memory_items == (memory_item,)


def test_memory_service_search_prioritizes_interaction_memory_for_interaction_filters() -> None:
    workspace_id = uuid4()
    created_at = datetime(2024, 3, 7, 8, 9, 10, tzinfo=UTC)
    interaction_memory = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="interaction_request",
        provenance="interaction",
        content="resume the interaction memory contract work",
        metadata={
            "interaction_role": "user",
            "interaction_kind": "interaction_request",
            "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
            "file_operation": "modify",
            "purpose": "capture interaction-memory contract updates",
        },
        created_at=created_at,
        updated_at=created_at,
    )
    episode_memory = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="episode_note",
        provenance="episode",
        content="resume the interaction memory contract work",
        metadata={
            "kind": "checkpoint",
        },
        created_at=created_at,
        updated_at=created_at,
    )
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_item_repository.create(episode_memory)
    memory_item_repository.create(interaction_memory)

    service = MemoryService(
        memory_item_repository=memory_item_repository,
    )

    response = service.search(
        SearchMemoryRequest(
            query="resume",
            workspace_id=str(workspace_id),
            filters={
                "provenance": ["interaction"],
                "interaction_roles": ["user"],
                "file_operation": "modify",
                "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
                "purpose": "contract updates",
            },
        )
    )

    assert isinstance(response, SearchMemoryResponse)
    assert len(response.results) == 1
    result = response.results[0]
    assert result.memory_id == interaction_memory.memory_id
    assert result.metadata["interaction_role"] == "user"
    assert result.metadata["file_operation"] == "modify"
    assert (
        result.metadata["file_path"]
        == "ctxledger/docs/memory/design/interaction_memory_contract.md"
    )
    assert result.ranking_details["remember_path_detail"]["provenance"] == "interaction"
    assert result.ranking_details["remember_path_detail"]["provenance_kind"] == "interaction"
    assert result.ranking_details["remember_path_detail"]["interaction_role"] == "user"
    assert result.ranking_details["remember_path_detail"]["interaction_kind"] == (
        "interaction_request"
    )
    assert result.ranking_details["remember_path_detail"]["file_operation"] == "modify"
    assert any(
        reason["code"] == "interaction_context_priority_bonus"
        for reason in result.ranking_details["reason_list"]
    )
    assert any(
        reason["code"] == "failure_reuse_file_work_signal"
        for reason in result.ranking_details["reason_list"]
    )
    assert result.ranking_details["remember_path_detail"]["failure_reuse_detail"] == {
        "failure_reuse_candidate": True,
        "failure_reuse_reason": (
            "interaction and file-work metadata can support bounded failure reuse lookup"
        ),
        "interaction_present": True,
        "interaction_role": "user",
        "interaction_kind": "interaction_request",
        "file_work_present": True,
        "file_name": None,
        "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
        "file_operation": "modify",
        "purpose": "capture interaction-memory contract updates",
    }


def test_memory_service_search_applies_bounded_file_work_filters() -> None:
    workspace_id = uuid4()
    created_at = datetime(2024, 3, 8, 9, 10, 11, tzinfo=UTC)
    create_memory = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="interaction_response",
        provenance="interaction",
        content="I will add the focused validation plan file",
        metadata={
            "interaction_role": "agent",
            "interaction_kind": "interaction_response",
            "file_name": "0.9.0_focused_validation_plan.md",
            "file_path": "ctxledger/docs/project/releases/plans/versioned/0.9.0_focused_validation_plan.md",
            "file_operation": "create",
            "purpose": "add focused validation plan",
        },
        created_at=created_at,
        updated_at=created_at,
    )
    modify_memory = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="interaction_request",
        provenance="interaction",
        content="update the interaction memory contract",
        metadata={
            "interaction_role": "user",
            "interaction_kind": "interaction_request",
            "file_name": "interaction_memory_contract.md",
            "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
            "file_operation": "modify",
            "purpose": "capture interaction-memory contract updates",
        },
        created_at=created_at,
        updated_at=created_at,
    )
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_item_repository.create(create_memory)
    memory_item_repository.create(modify_memory)

    service = MemoryService(
        memory_item_repository=memory_item_repository,
    )

    response = service.search(
        SearchMemoryRequest(
            query="plan",
            workspace_id=str(workspace_id),
            filters={
                "file_name": "0.9.0_focused_validation_plan.md",
                "file_operation": "create",
                "purpose": "focused validation",
            },
        )
    )

    assert isinstance(response, SearchMemoryResponse)
    assert len(response.results) == 1
    result = response.results[0]
    assert result.memory_id == create_memory.memory_id
    assert result.metadata["file_name"] == "0.9.0_focused_validation_plan.md"
    assert result.metadata["file_operation"] == "create"
    assert result.metadata["purpose"] == "add focused validation plan"
    assert result.ranking_details["remember_path_detail"]["file_name"] == (
        "0.9.0_focused_validation_plan.md"
    )
    assert result.ranking_details["remember_path_detail"]["file_operation"] == "create"
    assert result.ranking_details["remember_path_detail"]["purpose"] == (
        "add focused validation plan"
    )
    assert any(
        reason["code"] == "interaction_context_priority_bonus"
        for reason in result.ranking_details["reason_list"]
    )
    assert any(
        reason["code"] == "failure_reuse_file_work_signal"
        for reason in result.ranking_details["reason_list"]
    )
    assert result.ranking_details["remember_path_detail"]["failure_reuse_detail"] == {
        "failure_reuse_candidate": True,
        "failure_reuse_reason": (
            "interaction and file-work metadata can support bounded failure reuse lookup"
        ),
        "interaction_present": True,
        "interaction_role": "agent",
        "interaction_kind": "interaction_response",
        "file_work_present": True,
        "file_name": "0.9.0_focused_validation_plan.md",
        "file_path": (
            "ctxledger/docs/project/releases/plans/versioned/0.9.0_focused_validation_plan.md"
        ),
        "file_operation": "create",
        "purpose": "add focused validation plan",
    }


def test_0_9_0_acceptance_inventory_is_explicitly_partial_for_current_slice() -> None:
    acceptance_inventory = {
        "minimal_prompt_resume_contract_doc": "pass",
        "resume_selection_explanation_tests": "pass",
        "historical_query_contract_doc": "pass",
        "interaction_capture_docs": "pass",
        "interaction_capture_http_runtime": "pass",
        "interaction_capture_mcp_runtime": "pass",
        "interaction_memory_search_visibility": "pass",
        "interaction_memory_context_group_visibility": "pass",
        "file_work_metadata_capture": "pass",
        "file_work_metadata_search_filters": "pass",
        "file_work_metadata_failure_reuse_explanation": "pass",
        "failure_reuse_representative_tests": "partial",
        "postgres_interaction_group_integration": "partial",
        "acceptance_review_document": "deferred",
        "closeout_document": "deferred",
    }

    assert acceptance_inventory["minimal_prompt_resume_contract_doc"] == "pass"
    assert acceptance_inventory["interaction_capture_docs"] == "pass"
    assert acceptance_inventory["interaction_capture_http_runtime"] == "pass"
    assert acceptance_inventory["interaction_capture_mcp_runtime"] == "pass"
    assert acceptance_inventory["interaction_memory_search_visibility"] == "pass"
    assert acceptance_inventory["interaction_memory_context_group_visibility"] == "pass"
    assert acceptance_inventory["file_work_metadata_capture"] == "pass"
    assert acceptance_inventory["file_work_metadata_search_filters"] == "pass"
    assert acceptance_inventory["file_work_metadata_failure_reuse_explanation"] == "pass"
    assert acceptance_inventory["failure_reuse_representative_tests"] == "partial"
    assert acceptance_inventory["postgres_interaction_group_integration"] == "partial"
    assert acceptance_inventory["acceptance_review_document"] == "deferred"
    assert acceptance_inventory["closeout_document"] == "deferred"
