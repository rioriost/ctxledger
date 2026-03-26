from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .types import EpisodeRecord


class WorkflowResolutionMixin:
    """Workflow/workspace/ticket resolution helpers for ``MemoryService``.

    This mixin extracts workflow freshness ordering and signal shaping without
    changing the existing ``MemoryService`` state contract. The consuming class
    is expected to provide:

    - ``self._workflow_lookup``
    - ``self._workspace_lookup``
    - ``self._episode_repository``
    """

    def _order_workflow_ids_by_freshness_signals(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
        limit: int,
    ) -> tuple[UUID, ...]:
        if not workflow_ids:
            return ()

        workflow_recencies: list[
            tuple[
                bool,
                bool,
                bool,
                bool,
                bool,
                bool,
                datetime,
                datetime,
                datetime,
                datetime,
                int,
                UUID,
            ]
        ] = []

        for index, workflow_id in enumerate(workflow_ids):
            freshness = (
                self._workflow_lookup.workflow_freshness_by_id(workflow_id)
                if self._workflow_lookup is not None
                else {}
            )
            latest_episode = self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=1,
            )
            workflow_is_terminal = bool(freshness.get("workflow_is_terminal") or False)
            latest_attempt_is_terminal = bool(freshness.get("latest_attempt_is_terminal") or False)
            has_latest_attempt = bool(freshness.get("has_latest_attempt") or False)
            has_latest_checkpoint = bool(freshness.get("has_latest_checkpoint") or False)
            checkpoint_has_current_objective = bool(
                freshness.get("latest_checkpoint_current_objective")
            )
            checkpoint_has_next_intended_action = bool(
                freshness.get("latest_checkpoint_next_intended_action")
            )
            latest_checkpoint_created_at = freshness.get(
                "latest_checkpoint_created_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_verify_report_created_at = freshness.get(
                "latest_verify_report_created_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            latest_episode_created_at = (
                latest_episode[0].created_at
                if latest_episode
                else datetime.min.replace(tzinfo=timezone.utc)
            )
            latest_attempt_started_at = freshness.get(
                "latest_attempt_started_at"
            ) or datetime.min.replace(tzinfo=timezone.utc)
            workflow_recencies.append(
                (
                    not workflow_is_terminal,
                    not latest_attempt_is_terminal,
                    checkpoint_has_current_objective,
                    checkpoint_has_next_intended_action,
                    has_latest_attempt,
                    has_latest_checkpoint,
                    latest_checkpoint_created_at,
                    latest_verify_report_created_at,
                    latest_episode_created_at,
                    latest_attempt_started_at,
                    -index,
                    workflow_id,
                )
            )

        workflow_recencies.sort(reverse=True)
        return tuple(workflow_id for *_, workflow_id in workflow_recencies[:limit])

    def _workflow_ordering_signals(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
    ) -> dict[str, dict[str, str | bool | None]]:
        signals: dict[str, dict[str, str | bool | None]] = {}

        for workflow_id in workflow_ids:
            freshness = (
                self._workflow_lookup.workflow_freshness_by_id(workflow_id)
                if self._workflow_lookup is not None
                else {}
            )
            latest_episode = self._episode_repository.list_by_workflow_id(
                workflow_id,
                limit=1,
            )
            latest_checkpoint_current_objective = freshness.get(
                "latest_checkpoint_current_objective"
            )
            latest_checkpoint_next_intended_action = freshness.get(
                "latest_checkpoint_next_intended_action"
            )
            signals[str(workflow_id)] = {
                "workflow_status": (
                    str(freshness.get("workflow_status"))
                    if freshness.get("workflow_status") is not None
                    else None
                ),
                "workflow_is_terminal": (
                    bool(freshness.get("workflow_is_terminal"))
                    if freshness.get("workflow_is_terminal") is not None
                    else None
                ),
                "latest_attempt_status": (
                    str(freshness.get("latest_attempt_status"))
                    if freshness.get("latest_attempt_status") is not None
                    else None
                ),
                "latest_attempt_is_terminal": (
                    bool(freshness.get("latest_attempt_is_terminal"))
                    if freshness.get("latest_attempt_is_terminal") is not None
                    else None
                ),
                "has_latest_attempt": (
                    bool(freshness.get("has_latest_attempt"))
                    if freshness.get("has_latest_attempt") is not None
                    else None
                ),
                "latest_attempt_verify_status": (
                    str(freshness.get("latest_attempt_verify_status"))
                    if freshness.get("latest_attempt_verify_status") is not None
                    else None
                ),
                "latest_attempt_started_at": (
                    freshness.get("latest_attempt_started_at").isoformat()
                    if freshness.get("latest_attempt_started_at") is not None
                    else None
                ),
                "has_latest_checkpoint": (
                    bool(freshness.get("has_latest_checkpoint"))
                    if freshness.get("has_latest_checkpoint") is not None
                    else None
                ),
                "latest_checkpoint_created_at": (
                    freshness.get("latest_checkpoint_created_at").isoformat()
                    if freshness.get("latest_checkpoint_created_at") is not None
                    else None
                ),
                "latest_checkpoint_step_name": (
                    str(freshness.get("latest_checkpoint_step_name"))
                    if freshness.get("latest_checkpoint_step_name") is not None
                    else None
                ),
                "latest_checkpoint_summary": (
                    str(freshness.get("latest_checkpoint_summary"))
                    if freshness.get("latest_checkpoint_summary") is not None
                    else None
                ),
                "latest_checkpoint_current_objective": (
                    str(latest_checkpoint_current_objective)
                    if latest_checkpoint_current_objective is not None
                    else None
                ),
                "latest_checkpoint_next_intended_action": (
                    str(latest_checkpoint_next_intended_action)
                    if latest_checkpoint_next_intended_action is not None
                    else None
                ),
                "latest_checkpoint_has_current_objective": (
                    bool(str(latest_checkpoint_current_objective).strip())
                    if latest_checkpoint_current_objective is not None
                    else False
                ),
                "latest_checkpoint_has_next_intended_action": (
                    bool(str(latest_checkpoint_next_intended_action).strip())
                    if latest_checkpoint_next_intended_action is not None
                    else False
                ),
                "latest_verify_report_created_at": (
                    freshness.get("latest_verify_report_created_at").isoformat()
                    if freshness.get("latest_verify_report_created_at") is not None
                    else None
                ),
                "latest_episode_created_at": (
                    latest_episode[0].created_at.isoformat() if latest_episode else None
                ),
                "workflow_updated_at": (
                    freshness.get("workflow_updated_at").isoformat()
                    if freshness.get("workflow_updated_at") is not None
                    else None
                ),
            }

        return signals

    def _task_recall_search_context(
        self,
        *,
        workspace_id: UUID | None,
        limit: int,
    ) -> tuple[
        str | None,
        str | None,
        dict[str, Any],
        dict[str, Any],
        bool,
    ]:
        if workspace_id is None or self._workflow_lookup is None:
            return (None, None, {}, {}, False)

        raw_workspace_lookup = getattr(
            self._workflow_lookup,
            "workflow_ids_by_workspace_id_raw_order",
            None,
        )
        if callable(raw_workspace_lookup):
            workspace_workflow_ids = raw_workspace_lookup(
                str(workspace_id),
                limit=limit,
            )
        else:
            workspace_workflow_ids = self._workflow_lookup.workflow_ids_by_workspace_id(
                str(workspace_id),
                limit=limit,
            )

        if not workspace_workflow_ids:
            return (None, None, {}, {}, False)

        signal_ordered_workflow_ids = self._order_workflow_ids_by_freshness_signals(
            workflow_ids=workspace_workflow_ids,
            limit=limit,
        )
        raw_ordering_signals = self._workflow_ordering_signals(
            workflow_ids=workspace_workflow_ids,
        )
        ordering_signals = self._workflow_ordering_signals(
            workflow_ids=signal_ordered_workflow_ids,
        )

        latest_task_recall_workflow_id = str(workspace_workflow_ids[0])
        selected_task_recall_workflow_id = str(signal_ordered_workflow_ids[0])
        task_recall_selected_equals_latest = (
            latest_task_recall_workflow_id == selected_task_recall_workflow_id
        )
        latest_task_recall_signals = raw_ordering_signals.get(
            latest_task_recall_workflow_id,
            {},
        )
        selected_task_recall_signals = ordering_signals.get(
            selected_task_recall_workflow_id,
            {},
        )

        return (
            latest_task_recall_workflow_id,
            selected_task_recall_workflow_id,
            latest_task_recall_signals,
            selected_task_recall_signals,
            task_recall_selected_equals_latest,
        )

    def _resolve_workspace_id(self, workflow_instance_id: UUID) -> UUID | None:
        if self._workspace_lookup is None:
            return None
        return self._workspace_lookup.workspace_id_by_workflow_id(workflow_instance_id)

    def _interleave_workflow_episodes(
        self,
        *,
        workflow_ids: tuple[UUID, ...],
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        if not workflow_ids or limit <= 0:
            return ()

        workflow_episode_lists = [
            self._episode_repository.list_by_workflow_id(workflow_id, limit=limit)
            for workflow_id in workflow_ids
        ]

        episodes: list[EpisodeRecord] = []
        seen_episode_ids: set[UUID] = set()
        round_index = 0

        while len(episodes) < limit:
            added_in_round = False

            for workflow_episodes in workflow_episode_lists:
                if round_index >= len(workflow_episodes):
                    continue

                episode = workflow_episodes[round_index]
                if episode.episode_id in seen_episode_ids:
                    continue

                seen_episode_ids.add(episode.episode_id)
                episodes.append(episode)
                added_in_round = True

                if len(episodes) >= limit:
                    break

            if not added_in_round:
                break

            round_index += 1

        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])


__all__ = ["WorkflowResolutionMixin"]
