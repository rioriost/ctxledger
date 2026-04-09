from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.version import get_app_version
from ctxledger.workflow.service import (
    FailureListEntry,
    MemoryStats,
    WorkflowListEntry,
    WorkflowStats,
)

from .conftest import make_settings


def test_format_stats_text_uses_zero_defaults_for_missing_fields() -> None:
    rendered = cli_module._format_stats_text(object())

    assert "ctxledger stats" in rendered
    assert "- total: 0" in rendered
    assert "- running: 0" in rendered
    assert "- completed: 0" in rendered
    assert "- failed: 0" in rendered
    assert "- cancelled: 0" in rendered
    assert "- episodes: 0" in rendered
    assert "- memory_items: 0" in rendered
    assert "- memory_embeddings: 0" in rendered
    assert "- interaction_memory_items: 0" in rendered
    assert "- file_work_memory_items: 0" in rendered
    assert "- derived_memory_items: 0" in rendered
    assert "- checkpoint_auto_memory_recorded: 0" in rendered
    assert "- checkpoint_auto_memory_skipped: 0" in rendered
    assert "- workflow_completion_auto_memory_recorded: 0" in rendered
    assert "- workflow_completion_auto_memory_skipped: 0" in rendered
    assert "- derived_memory_item_state: unknown" in rendered
    assert "- derived_memory_item_reason: None" in rendered
    assert "- derived_memory_graph_status: None" in rendered
    assert "Structured checkpoint coverage:" in rendered
    assert "- current_objective: 0" in rendered
    assert "- next_intended_action: 0" in rendered
    assert "- verify_target: 0" in rendered
    assert "- resume_hint: 0" in rendered
    assert "- blocker_or_risk: 0" in rendered
    assert "- failure_guard: 0" in rendered
    assert "- root_cause: 0" in rendered
    assert "- recovery_pattern: 0" in rendered
    assert "- what_remains: 0" in rendered
    assert "- checkpoints: 0" in rendered
    assert "- workflow_updated_at: None" in rendered
    assert "- checkpoint_created_at: None" in rendered
    assert "- verify_report_created_at: None" in rendered
    assert "- episode_created_at: None" in rendered
    assert "- memory_item_created_at: None" in rendered
    assert "- memory_embedding_created_at: None" in rendered


def test_format_workflows_text_renders_none_fallbacks() -> None:
    workflow = WorkflowListEntry(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        canonical_path=None,
        ticket_id="CLI-WF-NONE",
        workflow_status="running",
        latest_step_name=None,
        latest_verify_status=None,
        updated_at=datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC),
    )

    rendered = cli_module._format_workflows_text((workflow,))

    assert f"workspace={workflow.workspace_id}" in rendered
    assert "latest_step=none" in rendered
    assert "verify_status=none" in rendered
    assert "updated_at=2026-03-17 12:00:00+00:00" in rendered


def test_format_failures_text_renders_none_fallbacks() -> None:
    failure = FailureListEntry(
        failure_scope="workflow",
        failure_type="runtime",
        failure_status="open",
        target_path=None,
        error_code=None,
        error_message="failed",
        attempt_id=None,
        occurred_at=datetime(2026, 3, 17, 13, 0, 0, tzinfo=UTC),
        resolved_at=None,
        open_failure_count=0,
        retry_count=0,
    )

    rendered = cli_module._format_failures_text((failure,))

    assert "path=none" in rendered
    assert "error_code=none" in rendered
    assert "resolved_at=None" in rendered
    assert "retry_count=0" in rendered
    assert "open_failures=0" in rendered


def test_format_memory_stats_text_renders_none_when_provenance_missing() -> None:
    stats = SimpleNamespace(
        episode_count=0,
        memory_item_count=0,
        memory_embedding_count=0,
        memory_relation_count=0,
        memory_item_provenance_counts={},
        checkpoint_auto_memory_recorded_count=0,
        checkpoint_auto_memory_skipped_count=0,
        workflow_completion_auto_memory_recorded_count=0,
        workflow_completion_auto_memory_skipped_count=0,
        latest_episode_created_at=None,
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
        latest_memory_relation_created_at=None,
    )

    rendered = cli_module._format_memory_stats_text(stats)

    assert "ctxledger memory-stats" in rendered
    assert "Remember-path observability:" in rendered
    assert "- checkpoint_auto_memory_recorded: 0" in rendered
    assert "- checkpoint_auto_memory_skipped: 0" in rendered
    assert "- workflow_completion_auto_memory_recorded: 0" in rendered
    assert "- workflow_completion_auto_memory_skipped: 0" in rendered
    assert "Memory item provenance:" in rendered
    assert "- none" in rendered
    assert "- memory_relation_created_at: None" in rendered


def test_format_workflows_text_renders_empty_result() -> None:
    rendered = cli_module._format_workflows_text(())

    assert rendered == "ctxledger workflows\n\n- none"


def test_format_failures_text_renders_empty_result() -> None:
    rendered = cli_module._format_failures_text(())

    assert rendered == "ctxledger failures\n\n- none"


def test_stats_reports_unexpected_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("stats exploded")),
    )

    exit_code = cli_module._stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load stats: stats exploded" in captured.err


def test_format_memory_stats_text_renders_values() -> None:
    stats = MemoryStats(
        episode_count=2,
        memory_item_count=3,
        memory_embedding_count=4,
        memory_relation_count=5,
        memory_item_provenance_counts={
            "checkpoint": 1,
            "episode": 2,
        },
        checkpoint_auto_memory_recorded_count=7,
        checkpoint_auto_memory_skipped_count=3,
        workflow_completion_auto_memory_recorded_count=5,
        workflow_completion_auto_memory_skipped_count=2,
        latest_episode_created_at=datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2026, 3, 17, 12, 1, 0, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2026, 3, 17, 12, 2, 0, tzinfo=UTC),
        latest_memory_relation_created_at=datetime(2026, 3, 17, 12, 3, 0, tzinfo=UTC),
    )

    rendered = cli_module._format_memory_stats_text(stats)

    assert "- episodes: 2" in rendered
    assert "- memory_items: 3" in rendered
    assert "- memory_embeddings: 4" in rendered
    assert "- memory_relations: 5" in rendered
    assert "- checkpoint_auto_memory_recorded: 7" in rendered
    assert "- checkpoint_auto_memory_skipped: 3" in rendered
    assert "- workflow_completion_auto_memory_recorded: 5" in rendered
    assert "- workflow_completion_auto_memory_skipped: 2" in rendered
    assert "- checkpoint: 1" in rendered
    assert "- episode: 2" in rendered
    assert "- episode_created_at: 2026-03-17 12:00:00+00:00" in rendered
    assert "- memory_relation_created_at: 2026-03-17 12:03:00+00:00" in rendered


def test_format_stats_text_renders_structured_checkpoint_coverage() -> None:
    stats = WorkflowStats(
        workspace_count=1,
        workflow_status_counts={
            "running": 1,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        },
        attempt_status_counts={
            "running": 1,
            "succeeded": 0,
            "failed": 0,
            "cancelled": 0,
        },
        verify_status_counts={
            "pending": 0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
        },
        checkpoint_count=9,
        episode_count=0,
        memory_item_count=0,
        memory_embedding_count=0,
        structured_checkpoint_coverage={
            "current_objective": 7,
            "next_intended_action": 6,
            "verify_target": 5,
            "resume_hint": 4,
            "blocker_or_risk": 3,
            "failure_guard": 2,
            "root_cause": 8,
            "recovery_pattern": 6,
            "what_remains": 5,
        },
    )

    rendered = cli_module._format_stats_text(stats)

    assert "Structured checkpoint coverage:" in rendered
    assert "- current_objective: 7" in rendered
    assert "- next_intended_action: 6" in rendered
    assert "- verify_target: 5" in rendered
    assert "- resume_hint: 4" in rendered
    assert "- blocker_or_risk: 3" in rendered
    assert "- failure_guard: 2" in rendered
    assert "- root_cause: 8" in rendered
    assert "- recovery_pattern: 6" in rendered
    assert "- what_remains: 5" in rendered


def test_format_failures_text_renders_values() -> None:
    failure = FailureListEntry(
        failure_scope="workflow",
        failure_type="runtime",
        failure_status="open",
        target_path="/tmp/workflow",
        error_code="runtime_failed",
        error_message="workflow crashed",
        attempt_id=uuid4(),
        occurred_at=datetime(2026, 3, 17, 13, 0, 0, tzinfo=UTC),
        resolved_at=datetime(2026, 3, 17, 14, 0, 0, tzinfo=UTC),
        open_failure_count=2,
        retry_count=3,
    )

    rendered = cli_module._format_failures_text((failure,))

    assert "- open: runtime" in rendered
    assert "scope=workflow" in rendered
    assert "path=/tmp/workflow" in rendered
    assert "error_code=runtime_failed" in rendered
    assert "message=workflow crashed" in rendered
    assert "occurred_at=2026-03-17 13:00:00+00:00" in rendered
    assert "resolved_at=2026-03-17 14:00:00+00:00" in rendered
    assert "retry_count=3" in rendered
    assert "open_failures=2" in rendered
