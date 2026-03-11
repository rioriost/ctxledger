"""Memory service stubs aligned with the ctxledger architecture.

This module intentionally provides architectural placeholders for the memory
subsystem in v0.1.0.

The current release focuses on durable workflow control. Memory features are
defined at the API and architecture level, but may remain stubbed until the
episodic, semantic, and hierarchical retrieval layers are implemented.

Design goals of this module:
- preserve a stable application-facing surface
- keep workflow control and memory retrieval separate
- return explicit "not implemented" style failures instead of pretending that
  retrieval or persistence is production-ready
- provide typed request/response shapes that future implementations can extend
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class MemoryFeature(StrEnum):
    """Memory capabilities exposed by the service layer."""

    REMEMBER_EPISODE = "memory_remember_episode"
    SEARCH = "memory_search"
    GET_CONTEXT = "memory_get_context"


class MemoryErrorCode(StrEnum):
    """Machine-readable error codes for memory service failures."""

    NOT_IMPLEMENTED = "memory_not_implemented"
    INVALID_REQUEST = "memory_invalid_request"


@dataclass(slots=True, frozen=True)
class MemoryServiceError(Exception):
    """Typed exception used by the memory service.

    This is intended to be caught by the application / transport layer and
    mapped into protocol-visible errors.
    """

    code: MemoryErrorCode
    message: str
    feature: MemoryFeature
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True, frozen=True)
class RememberEpisodeRequest:
    """Request shape for future episodic memory persistence."""

    workflow_instance_id: str
    summary: str
    attempt_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SearchMemoryRequest:
    """Request shape for future semantic/procedural memory search."""

    query: str
    workspace_id: str | None = None
    limit: int = 10
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class GetMemoryContextRequest:
    """Request shape for future auxiliary memory context retrieval."""

    query: str | None = None
    workspace_id: str | None = None
    workflow_instance_id: str | None = None
    ticket_id: str | None = None
    limit: int = 10
    include_episodes: bool = True
    include_memory_items: bool = True
    include_summaries: bool = True


@dataclass(slots=True, frozen=True)
class StubResponse:
    """Standard response returned by stubbed memory operations.

    This shape is suitable for application-layer adaptation into MCP tool
    responses while keeping the service layer transport-agnostic.
    """

    feature: MemoryFeature
    implemented: bool
    message: str
    status: str = "not_implemented"
    available_in_version: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


class MemoryService:
    """Architectural placeholder for the ctxledger memory subsystem.

    The workflow subsystem is the primary functional target in v0.1.0.
    This service exists to preserve a clean boundary for future memory work:

    - episodic memory persistence
    - semantic/procedural memory search
    - hierarchical summary retrieval
    - relation-aware context assembly

    The service currently validates a minimal subset of inputs and returns
    explicit stub responses.
    """

    def remember_episode(self, request: RememberEpisodeRequest) -> StubResponse:
        """Stub for future episodic memory persistence."""
        self._require_non_empty(
            request.workflow_instance_id,
            field_name="workflow_instance_id",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )
        self._require_non_empty(
            request.summary,
            field_name="summary",
            feature=MemoryFeature.REMEMBER_EPISODE,
        )

        return self._not_implemented(
            feature=MemoryFeature.REMEMBER_EPISODE,
            message=(
                "Episode persistence is defined architecturally but is not "
                "implemented in v0.1.0."
            ),
            details={
                "workflow_instance_id": request.workflow_instance_id,
                "attempt_id": request.attempt_id,
            },
        )

    def search(self, request: SearchMemoryRequest) -> StubResponse:
        """Stub for future semantic/procedural memory retrieval."""
        self._require_non_empty(
            request.query,
            field_name="query",
            feature=MemoryFeature.SEARCH,
        )
        self._require_positive_limit(
            request.limit,
            feature=MemoryFeature.SEARCH,
        )

        return self._not_implemented(
            feature=MemoryFeature.SEARCH,
            message=(
                "Semantic memory search is defined architecturally but is not "
                "implemented in v0.1.0."
            ),
            details={
                "workspace_id": request.workspace_id,
                "limit": request.limit,
                "filters": request.filters,
            },
        )

    def get_context(self, request: GetMemoryContextRequest) -> StubResponse:
        """Stub for future auxiliary memory context retrieval.

        This operation is intentionally separate from workflow resume. It is
        meant to return relevance-based support context rather than canonical
        operational state.
        """
        if not any(
            [
                self._has_text(request.query),
                self._has_text(request.workspace_id),
                self._has_text(request.workflow_instance_id),
                self._has_text(request.ticket_id),
            ]
        ):
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=MemoryFeature.GET_CONTEXT,
                message=(
                    "At least one of query, workspace_id, workflow_instance_id, "
                    "or ticket_id must be provided."
                ),
                details={},
            )

        self._require_positive_limit(
            request.limit,
            feature=MemoryFeature.GET_CONTEXT,
        )

        return self._not_implemented(
            feature=MemoryFeature.GET_CONTEXT,
            message=(
                "Memory context retrieval is defined architecturally but is not "
                "implemented in v0.1.0."
            ),
            details={
                "workspace_id": request.workspace_id,
                "workflow_instance_id": request.workflow_instance_id,
                "ticket_id": request.ticket_id,
                "limit": request.limit,
                "include_episodes": request.include_episodes,
                "include_memory_items": request.include_memory_items,
                "include_summaries": request.include_summaries,
            },
        )

    def _not_implemented(
        self,
        *,
        feature: MemoryFeature,
        message: str,
        details: dict[str, Any],
    ) -> StubResponse:
        return StubResponse(
            feature=feature,
            implemented=False,
            message=message,
            available_in_version=None,
            details=details,
        )

    def _require_non_empty(
        self,
        value: str,
        *,
        field_name: str,
        feature: MemoryFeature,
    ) -> None:
        if not self._has_text(value):
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message=f"{field_name} must be a non-empty string.",
                details={"field": field_name},
            )

    def _require_positive_limit(
        self,
        value: int,
        *,
        feature: MemoryFeature,
    ) -> None:
        if value <= 0:
            raise MemoryServiceError(
                code=MemoryErrorCode.INVALID_REQUEST,
                feature=feature,
                message="limit must be greater than 0.",
                details={"field": "limit", "value": value},
            )

    @staticmethod
    def _has_text(value: str | None) -> bool:
        return bool(value and value.strip())
