from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

from ctxledger.memory.service import (
    GetContextResponse,
    MemoryErrorCode,
    MemoryFeature,
    MemoryServiceError,
    RememberEpisodeResponse,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)
from ctxledger.runtime.types import WorkflowResumeResponse
from ctxledger.workflow.service import WorkflowError


@dataclass
class FakeWorkflowService:
    register_result: object | None = None
    start_result: object | None = None
    checkpoint_result: object | None = None
    complete_result: object | None = None
    register_exc: Exception | None = None
    start_exc: Exception | None = None
    checkpoint_exc: Exception | None = None
    complete_exc: Exception | None = None
    register_calls: list[object] | None = None
    start_calls: list[object] | None = None
    checkpoint_calls: list[object] | None = None
    complete_calls: list[object] | None = None

    def __post_init__(self) -> None:
        self.register_calls = []
        self.start_calls = []
        self.checkpoint_calls = []
        self.complete_calls = []

    def register_workspace(self, data: object) -> object:
        assert self.register_calls is not None
        self.register_calls.append(data)
        if self.register_exc is not None:
            raise self.register_exc
        assert self.register_result is not None
        return self.register_result

    def start_workflow(self, data: object) -> object:
        assert self.start_calls is not None
        self.start_calls.append(data)
        if self.start_exc is not None:
            raise self.start_exc
        assert self.start_result is not None
        return self.start_result

    def create_checkpoint(self, data: object) -> object:
        assert self.checkpoint_calls is not None
        self.checkpoint_calls.append(data)
        if self.checkpoint_exc is not None:
            raise self.checkpoint_exc
        assert self.checkpoint_result is not None
        return self.checkpoint_result

    def complete_workflow(self, data: object) -> object:
        assert self.complete_calls is not None
        self.complete_calls.append(data)
        if self.complete_exc is not None:
            raise self.complete_exc
        assert self.complete_result is not None
        return self.complete_result


@dataclass
class FakeMemoryService:
    remember_result: object | None = None
    search_result: object | None = None
    context_result: object | None = None
    remember_exc: Exception | None = None
    search_exc: Exception | None = None
    context_exc: Exception | None = None
    remember_calls: list[object] | None = None
    search_calls: list[object] | None = None
    context_calls: list[object] | None = None

    def __post_init__(self) -> None:
        self.remember_calls = []
        self.search_calls = []
        self.context_calls = []

    def remember_episode(self, request: object) -> object:
        assert self.remember_calls is not None
        self.remember_calls.append(request)
        if self.remember_exc is not None:
            raise self.remember_exc
        assert self.remember_result is not None
        return self.remember_result

    def search(self, request: object) -> object:
        assert self.search_calls is not None
        self.search_calls.append(request)
        if self.search_exc is not None:
            raise self.search_exc
        assert self.search_result is not None
        return self.search_result

    def get_context(self, request: object) -> object:
        assert self.context_calls is not None
        self.context_calls.append(request)
        if self.context_exc is not None:
            raise self.context_exc
        assert self.context_result is not None
        return self.context_result


def make_server(
    *,
    workflow_service: object | None = None,
    workflow_resume_response: WorkflowResumeResponse | None = None,
) -> object:
    if workflow_resume_response is None:
        workflow_resume_response = WorkflowResumeResponse(
            status_code=200,
            payload={"workflow": {"status": "ok"}},
            headers={"content-type": "application/json"},
        )

    class FakeServer:
        def __init__(self) -> None:
            self.workflow_service = workflow_service
            self.resume_calls: list[object] = []

        def build_workflow_resume_response(
            self,
            workflow_instance_id: object,
        ) -> WorkflowResumeResponse:
            self.resume_calls.append(workflow_instance_id)
            return workflow_resume_response

    return FakeServer()


def make_stub_response() -> StubResponse:
    return StubResponse(
        feature=MemoryFeature.REMEMBER_EPISODE,
        implemented=False,
        message="ok",
        status="not_implemented",
        available_in_version="0.1.0",
        details={"value": 1, "source": "test"},
    )


def make_remember_episode_response() -> RememberEpisodeResponse:
    from ctxledger.memory.service import EpisodeRecord

    workflow_instance_id = __import__("uuid").uuid4()
    attempt_id = __import__("uuid").uuid4()
    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)

    return RememberEpisodeResponse(
        feature=MemoryFeature.REMEMBER_EPISODE,
        implemented=True,
        message="Episode recorded successfully.",
        status="recorded",
        available_in_version="0.2.0",
        timestamp=created_at,
        episode=EpisodeRecord(
            episode_id=__import__("uuid").uuid4(),
            workflow_instance_id=workflow_instance_id,
            summary="remember this",
            attempt_id=attempt_id,
            metadata={"kind": "checkpoint"},
            status="recorded",
            created_at=created_at,
            updated_at=created_at,
        ),
        details={
            "workflow_instance_id": str(workflow_instance_id),
            "attempt_id": str(attempt_id),
        },
    )


def make_search_memory_response() -> SearchMemoryResponse:
    workspace_id = __import__("uuid").uuid4()
    attempt_id = __import__("uuid").uuid4()
    episode_id = __import__("uuid").uuid4()
    memory_id = __import__("uuid").uuid4()
    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)

    return SearchMemoryResponse(
        feature=MemoryFeature.SEARCH,
        implemented=True,
        message="Hybrid lexical and semantic memory search completed successfully.",
        status="ok",
        available_in_version="0.3.0",
        timestamp=created_at,
        results=(
            SearchResultRecord(
                memory_id=memory_id,
                workspace_id=workspace_id,
                episode_id=episode_id,
                workflow_instance_id=None,
                summary="needle found in summary",
                attempt_id=attempt_id,
                metadata={"kind": "checkpoint"},
                score=3.0,
                matched_fields=("content",),
                lexical_score=3.0,
                semantic_score=0.0,
                ranking_details={
                    "lexical_component": 3.0,
                    "semantic_component": 0.0,
                    "score_mode": "lexical_only",
                    "semantic_only_discount_applied": False,
                    "reason_list": [
                        {
                            "code": "lexical_signal_present",
                            "message": "lexical overlap contributed to the ranking score",
                            "value": 3.0,
                        },
                        {
                            "code": "semantic_signal_absent",
                            "message": "no semantic similarity contributed to the ranking score",
                            "value": 0.0,
                        },
                        {
                            "code": "lexical_only_score_mode",
                            "message": "the result ranked using lexical evidence only",
                        },
                    ],
                    "task_recall_detail": {
                        "matched_fields": ["content"],
                        "memory_item_type": "episode_note",
                        "memory_item_provenance": "episode",
                        "metadata_match_candidates": ["kind checkpoint", "checkpoint"],
                        "workspace_constrained": True,
                    },
                },
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": "needle",
            "normalized_query": "needle",
            "workspace_id": str(workspace_id),
            "limit": 10,
            "filters": {},
            "search_mode": "hybrid_memory_item_search",
            "memory_items_considered": 1,
            "semantic_candidates_considered": 1,
            "semantic_query_generated": True,
            "hybrid_scoring": {
                "lexical_weight": 1.0,
                "semantic_weight": 1.0,
                "semantic_only_discount": 0.75,
            },
            "result_mode_counts": {
                "hybrid": 0,
                "lexical_only": 1,
                "semantic_only_discounted": 0,
            },
            "result_composition": {
                "with_lexical_signal": 1,
                "with_semantic_signal": 0,
                "with_both_signals": 0,
            },
            "results_returned": 1,
        },
    )


def make_get_context_response() -> GetContextResponse:
    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    return GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(),
        details={
            "episodes_returned": 0,
            "memory_items": [],
            "memory_item_counts_by_episode": {},
            "remember_path_relation_reasons": [],
            "remember_path_relation_reason_primary": None,
            "readiness_explainability": {
                "graph_summary_auxiliary": {},
                "summary_graph_mirroring": {},
            },
            "summaries": [],
            "task_recall_selection_present": False,
            "task_recall_selected_workflow_instance_id": None,
            "task_recall_latest_workflow_instance_id": None,
            "task_recall_running_workflow_instance_id": None,
            "task_recall_return_target_present": False,
            "task_recall_return_target_workflow_instance_id": None,
            "task_recall_return_target_basis": None,
            "task_recall_return_target_source": None,
            "task_recall_task_thread_present": False,
            "task_recall_task_thread_basis": None,
            "task_recall_task_thread_source": None,
            "task_recall_selected_checkpoint_step_name": None,
            "task_recall_selected_checkpoint_summary": None,
            "task_recall_latest_considered_checkpoint_step_name": None,
            "task_recall_latest_considered_checkpoint_summary": None,
            "task_recall_latest_vs_selected_candidate_details_present": False,
            "task_recall_latest_vs_selected_candidate_details": {
                "latest_workflow_instance_id": None,
                "selected_workflow_instance_id": None,
                "latest_considered": {
                    "workflow_instance_id": None,
                    "checkpoint_step_name": None,
                    "checkpoint_summary": None,
                    "primary_objective_text": None,
                    "next_intended_action_text": None,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "workflow_terminal": False,
                    "has_attempt_signal": False,
                    "attempt_terminal": False,
                    "has_checkpoint_signal": False,
                    "return_target_basis": None,
                    "task_thread_basis": None,
                },
                "selected": {
                    "workflow_instance_id": None,
                    "checkpoint_step_name": None,
                    "checkpoint_summary": None,
                    "primary_objective_text": None,
                    "next_intended_action_text": None,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "workflow_terminal": False,
                    "has_attempt_signal": False,
                    "attempt_terminal": False,
                    "has_checkpoint_signal": False,
                    "return_target_basis": None,
                    "task_thread_basis": None,
                },
                "same_checkpoint_details": True,
                "comparison_source": "task_recall_checkpoint_comparison",
            },
            "task_recall_latest_vs_selected_checkpoint_details_present": False,
            "task_recall_latest_vs_selected_checkpoint_details": {
                "latest_workflow_instance_id": None,
                "selected_workflow_instance_id": None,
                "latest_considered": {
                    "workflow_instance_id": None,
                    "checkpoint_step_name": None,
                    "checkpoint_summary": None,
                    "primary_objective_text": None,
                    "next_intended_action_text": None,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "workflow_terminal": False,
                    "has_attempt_signal": False,
                    "attempt_terminal": False,
                    "has_checkpoint_signal": False,
                    "return_target_basis": None,
                    "task_thread_basis": None,
                },
                "selected": {
                    "workflow_instance_id": None,
                    "checkpoint_step_name": None,
                    "checkpoint_summary": None,
                    "primary_objective_text": None,
                    "next_intended_action_text": None,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "workflow_terminal": False,
                    "has_attempt_signal": False,
                    "attempt_terminal": False,
                    "has_checkpoint_signal": False,
                    "return_target_basis": None,
                    "task_thread_basis": None,
                },
                "same_checkpoint_details": True,
                "comparison_source": "task_recall_checkpoint_comparison",
            },
            "task_recall_latest_vs_selected_primary_block": "candidate_details",
            "task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias": True,
            "task_recall_prior_mainline_present": False,
            "task_recall_prior_mainline_workflow_instance_id": None,
            "task_recall_primary_objective_present": False,
            "task_recall_primary_objective_text": None,
            "task_recall_primary_objective_source": None,
            "task_recall_latest_vs_selected_explanations_present": False,
            "task_recall_latest_vs_selected_explanations": [],
            "task_recall_comparison_summary_explanations_present": False,
            "task_recall_comparison_summary_explanations": [],
            "task_recall_selected_equals_latest": False,
            "task_recall_selected_equals_running": False,
            "task_recall_latest_workflow_terminal": False,
            "task_recall_latest_ticket_detour_like": False,
            "task_recall_latest_checkpoint_detour_like": False,
            "task_recall_selected_ticket_detour_like": False,
            "task_recall_selected_checkpoint_detour_like": False,
            "task_recall_detour_override_applied": False,
            "task_recall_explanations_present": False,
            "task_recall_explanations": [],
            "task_recall_ranking_details_present": False,
            "task_recall_ranking_details": [],
            "task_recall_selected_workflow_terminal": False,
            "memory_context_groups_are_primary_output": True,
            "memory_context_groups_are_primary_explainability_surface": True,
            "top_level_explainability_prefers_grouped_routes": True,
            "readiness_explainability_is_compatibility_output": False,
            "remember_path_explainability_by_episode_is_compatibility_output": False,
            "remember_path_relation_reasons_is_compatibility_output": False,
            "remember_path_relation_reason_primary_is_compatibility_output": False,
        },
    )


def make_workflow_error(
    message: str,
    *,
    code: str = "unexpected",
    details: dict[str, object] | None = None,
) -> WorkflowError:
    exc = WorkflowError(message, details=details or {})
    exc.code = code
    return exc


def make_memory_error(
    message: str,
    *,
    feature: str,
    details: dict[str, object] | None = None,
    code: MemoryErrorCode = MemoryErrorCode.INVALID_REQUEST,
) -> MemoryServiceError:
    return MemoryServiceError(
        code,
        message,
        feature=feature,
        details=details or {},
    )


def make_workspace_namespace(
    *,
    workspace_id,
    repo_url: str = "https://example.com/repo.git",
    canonical_path: str = "/tmp/repo",
    default_branch: str = "main",
    metadata: dict[str, object] | None = None,
    now: datetime | None = None,
) -> object:
    timestamp = now or datetime(2024, 1, 1, tzinfo=UTC)
    return SimpleNamespace(
        workspace_id=workspace_id,
        repo_url=repo_url,
        canonical_path=canonical_path,
        default_branch=default_branch,
        metadata=metadata or {},
        created_at=timestamp,
        updated_at=timestamp,
    )
