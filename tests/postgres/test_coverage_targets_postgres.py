from __future__ import annotations

import importlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.db.postgres import (
    PostgresMemoryEmbeddingRepository,
    PostgresMemoryEpisodeRepository,
    PostgresMemoryItemRepository,
    PostgresMemoryRelationRepository,
    PostgresVerifyReportRepository,
    PostgresWorkflowAttemptRepository,
    PostgresWorkflowCheckpointRepository,
    PostgresWorkflowInstanceRepository,
    PostgresWorkspaceRepository,
)
from ctxledger.workflow.service import (
    PersistenceError,
    VerifyStatus,
    WorkflowInstanceStatus,
)


def test_postgres_repository_count_and_max_helpers_cover_success_and_errors() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self._fetchone_result = None
            self._fetchall_result = []

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            return None

        def fetchone(self):
            return self._fetchone_result

        def fetchall(self):
            return self._fetchall_result

    class FakeConnection:
        def __init__(self, cursor: FakeCursor) -> None:
            self._cursor = cursor

        def cursor(self) -> FakeCursor:
            return self._cursor

    connection = FakeConnection(FakeCursor())
    attempt_repo = PostgresWorkflowAttemptRepository(connection)
    memory_item_repo = PostgresMemoryItemRepository(connection)

    connection._cursor._fetchone_result = {"count": 7}
    assert attempt_repo.count_all() == 7

    connection._cursor._fetchall_result = [
        {"status": "running", "count": 2},
        {"status": "succeeded", "count": 3},
    ]
    assert attempt_repo.count_by_status() == {
        "running": 2,
        "succeeded": 3,
    }

    now = datetime(2024, 10, 1, tzinfo=UTC)
    connection._cursor._fetchone_result = {"value": now}
    assert attempt_repo.max_datetime("started_at") == now

    connection._cursor._fetchall_result = [
        {"provenance": "episode", "count": 5},
        {"provenance": "workflow_complete_auto", "count": 2},
    ]
    assert memory_item_repo.count_by_provenance() == {
        "episode": 5,
        "workflow_complete_auto": 2,
    }

    workspace_repo = PostgresWorkspaceRepository(connection)
    workflow_repo = PostgresWorkflowInstanceRepository(connection)
    checkpoint_repo = PostgresWorkflowCheckpointRepository(connection)
    verify_repo = PostgresVerifyReportRepository(connection)
    episode_repo = PostgresMemoryEpisodeRepository(connection)
    embedding_repo = PostgresMemoryEmbeddingRepository(connection)
    relation_repo = PostgresMemoryRelationRepository(connection)

    connection._cursor._fetchone_result = {"count": 9}
    assert workspace_repo.count_all() == 9
    connection._cursor._fetchone_result = {"value": now}
    assert workspace_repo.max_datetime("updated_at") == now

    connection._cursor._fetchone_result = {"count": 12}
    assert workflow_repo.count_all() == 12
    connection._cursor._fetchall_result = [
        {"status": "running", "count": 4},
        {"status": "completed", "count": 8},
    ]
    assert workflow_repo.count_by_status() == {
        "running": 4,
        "completed": 8,
    }
    connection._cursor._fetchone_result = {"value": now}
    assert workflow_repo.max_datetime("created_at") == now

    connection._cursor._fetchall_result = [
        {
            "workflow_instance_id": uuid4(),
            "workspace_id": uuid4(),
            "ticket_id": "ticket-1",
            "status": "running",
            "metadata_json": {"kind": "recent"},
            "created_at": now,
            "updated_at": now,
        },
        {
            "workflow_instance_id": uuid4(),
            "workspace_id": uuid4(),
            "ticket_id": "ticket-2",
            "status": "completed",
            "metadata_json": {},
            "created_at": now,
            "updated_at": now,
        },
    ]
    recent = workflow_repo.list_recent(limit=5)
    assert len(recent) == 2
    assert recent[0].ticket_id == "ticket-1"
    assert recent[1].status == WorkflowInstanceStatus.COMPLETED

    connection._cursor._fetchone_result = {"count": 3}
    assert checkpoint_repo.count_all() == 3
    connection._cursor._fetchone_result = {"value": now}
    assert checkpoint_repo.max_datetime("created_at") == now

    connection._cursor._fetchone_result = {"count": 6}
    assert verify_repo.count_all() == 6
    connection._cursor._fetchall_result = [
        {"status": "pending", "count": 1},
        {"status": "passed", "count": 5},
    ]
    assert verify_repo.count_by_status() == {
        "pending": 1,
        "passed": 5,
    }
    connection._cursor._fetchone_result = {"value": now}
    assert verify_repo.max_datetime("created_at") == now

    connection._cursor._fetchone_result = {"count": 8}
    assert episode_repo.count_all() == 8
    connection._cursor._fetchone_result = {"value": now}
    assert episode_repo.max_datetime("created_at") == now

    connection._cursor._fetchone_result = {"count": 10}
    assert embedding_repo.count_all() == 10
    connection._cursor._fetchone_result = {"value": now}
    assert embedding_repo.max_datetime("created_at") == now

    connection._cursor._fetchone_result = {"count": 2}
    assert relation_repo.count_all() == 2
    connection._cursor._fetchone_result = {"value": now}
    assert relation_repo.max_datetime("created_at") == now

    with pytest.raises(
        Exception,
        match="Unsupported datetime field 'bad_field' for workflow_attempts",
    ):
        attempt_repo.max_datetime("bad_field")

    with pytest.raises(
        Exception,
        match="Unsupported datetime field 'bad_field' for memory_items",
    ):
        memory_item_repo.max_datetime("bad_field")


def test_postgres_low_level_helpers_cover_additional_branches() -> None:
    from ctxledger.db.postgres import (
        _json_object_or_none,
        _normalized_schema_name,
        _optional_datetime,
        _optional_str_enum,
        _parse_embedding_values,
        _require_connection_pool,
        _to_datetime,
        _to_uuid,
    )

    assert _parse_embedding_values(None) == ()
    assert _parse_embedding_values("  ") == ()
    assert _parse_embedding_values("[1.5, 2.5]") == (1.5, 2.5)
    assert _parse_embedding_values((1, "2.5")) == (1.0, 2.5)

    assert _normalized_schema_name(None) == "public"
    assert _normalized_schema_name("  ") == "public"
    assert _normalized_schema_name(" custom ") == "custom"

    assert _json_object_or_none(None) is None
    assert _json_object_or_none('{"alpha": 1}') == {"alpha": 1}
    assert _json_object_or_none("[1, 2, 3]") is None
    assert _json_object_or_none([("key", "value")]) == {"key": "value"}

    aware = datetime(2024, 10, 4, tzinfo=UTC)
    naive = datetime(2024, 10, 4)
    assert _to_datetime(aware) == aware
    assert _to_datetime(naive).tzinfo == UTC

    sample_uuid = uuid4()
    assert _to_uuid(str(sample_uuid)) == sample_uuid
    assert _optional_datetime(None) is None
    assert _optional_datetime(aware) == aware
    assert _optional_str_enum(VerifyStatus, None) is None
    assert _optional_str_enum(VerifyStatus, "passed") == VerifyStatus.PASSED

    with pytest.raises(PersistenceError, match="Expected datetime, got str"):
        _to_datetime("bad-datetime")

    postgres_module = importlib.import_module("ctxledger.db.postgres")
    if postgres_module.psycopg is None or postgres_module.dict_row is None:
        with pytest.raises(RuntimeError, match="psycopg-pool is required"):
            _require_connection_pool()
