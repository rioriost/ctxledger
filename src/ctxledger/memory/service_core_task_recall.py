from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ..runtime.task_recall import build_detour_like_signal_details


class TaskRecallMixin:
    """Task-recall helper methods for ``MemoryService``.

    This mixin extracts narrow task-recall glue that converts workflow freshness
    signal maps into the shape expected by the lower-level runtime helpers.

    The consuming class is expected to provide workflow signal dictionaries with
    keys such as:

    - ``ticket_id``
    - ``latest_checkpoint_step_name``
    - ``latest_checkpoint_summary``
    - ``latest_checkpoint_current_objective``
    - ``latest_checkpoint_next_intended_action``
    """

    @staticmethod
    def _task_recall_detour_like(signal_map: dict[str, Any]) -> tuple[bool, bool, bool]:
        workflow = SimpleNamespace(ticket_id=signal_map.get("ticket_id"))
        checkpoint = SimpleNamespace(
            step_name=signal_map.get("latest_checkpoint_step_name"),
            summary=signal_map.get("latest_checkpoint_summary"),
            checkpoint_json={
                "current_objective": signal_map.get("latest_checkpoint_current_objective"),
                "next_intended_action": signal_map.get("latest_checkpoint_next_intended_action"),
            },
        )
        return build_detour_like_signal_details(
            workflow=workflow,
            checkpoint=checkpoint,
        )

    def _task_recall_search_detour_details(
        self,
        signal_map: dict[str, Any],
    ) -> tuple[bool, bool, bool]:
        return self._task_recall_detour_like(signal_map)


__all__ = ["TaskRecallMixin"]
