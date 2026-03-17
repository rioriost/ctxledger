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
        details={"episodes_returned": 0},
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
