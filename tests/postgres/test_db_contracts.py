from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from ctxledger.db import (
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryStore,
    InMemoryUnitOfWork,
    InMemoryVerifyReportRepository,
    InMemoryWorkflowAttemptRepository,
    InMemoryWorkflowCheckpointRepository,
    InMemoryWorkflowInstanceRepository,
    InMemoryWorkspaceRepository,
    build_in_memory_uow_factory,
)
from ctxledger.workflow.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryItemRecord,
    MemoryItemRepository,
    PersistenceError,
    UnitOfWork,
    VerifyReport,
    VerifyReportRepository,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptRepository,
    WorkflowCheckpointRepository,
    WorkflowInstance,
    WorkflowInstanceRepository,
    Workspace,
    WorkspaceRepository,
)

from .conftest import (
    FakeConnection,
    FakeConnectionFactory,
    MemoryEmbeddingRepoStub,
    MemoryItemRepoStub,
    VerifyReportRepoStub,
    WorkflowAttemptRepoStub,
    WorkflowCheckpointRepoStub,
    WorkflowInstanceRepoStub,
    WorkspaceRepoStub,
    sample_attempt,
    sample_checkpoint,
    sample_verify_report,
    sample_workflow,
    sample_workspace,
)


def test_schema_file_exists() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "postgres.sql"

    assert schema_path.exists()
    assert (
        schema_path.read_text(encoding="utf-8")
        .strip()
        .startswith("-- ctxledger PostgreSQL schema")
    )


def test_schema_contains_core_workflow_tables() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "postgres.sql"
    schema = schema_path.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS workspaces" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_instances" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_attempts" in schema
    assert "CREATE TABLE IF NOT EXISTS workflow_checkpoints" in schema
    assert "CREATE TABLE IF NOT EXISTS verify_reports" in schema


def test_unit_of_work_contract_shape_can_be_satisfied_by_postgres_impl() -> None:
    class PostgresStyleUnitOfWork(UnitOfWork):
        def __init__(self) -> None:
            self.workspaces = WorkspaceRepoStub()
            self.workflow_instances = WorkflowInstanceRepoStub()
            self.workflow_attempts = WorkflowAttemptRepoStub()
            self.workflow_checkpoints = WorkflowCheckpointRepoStub()
            self.verify_reports = VerifyReportRepoStub()
            self.memory_items = MemoryItemRepoStub()
            self.memory_embeddings = MemoryEmbeddingRepoStub()
            self.committed = False
            self.rolled_back = False

        def commit(self) -> None:
            self.committed = True

        def rollback(self) -> None:
            self.rolled_back = True

    uow = PostgresStyleUnitOfWork()

    assert isinstance(uow.workspaces, WorkspaceRepository)
    assert isinstance(uow.workflow_instances, WorkflowInstanceRepository)
    assert isinstance(uow.workflow_attempts, WorkflowAttemptRepository)
    assert isinstance(uow.workflow_checkpoints, WorkflowCheckpointRepository)
    assert isinstance(uow.verify_reports, VerifyReportRepository)
    assert isinstance(uow.memory_items, MemoryItemRepository)
    assert isinstance(uow.memory_embeddings, MemoryEmbeddingRepository)

    uow.commit()
    uow.rollback()

    assert uow.committed is True
    assert uow.rolled_back is True


def test_memory_embedding_repository_contract_exposes_similarity_query() -> None:
    repo = MemoryEmbeddingRepoStub()
    first_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="first",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0, 0.0),
        content_hash="second",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    repo.create(first_embedding)
    repo.create(second_embedding)

    matches = repo.find_similar((1.0, 0.0, 0.0), limit=3)

    assert matches == ()


def test_workspace_repository_contract_can_round_trip_entity() -> None:
    repo = WorkspaceRepoStub()
    workspace = sample_workspace()

    created = repo.create(workspace)

    assert created == workspace
    assert repo.get_by_id(workspace.workspace_id) == workspace
    assert repo.get_by_canonical_path(workspace.canonical_path) == workspace
    assert repo.get_by_repo_url(workspace.repo_url) == [workspace]


def test_workflow_instance_repository_contract_tracks_running_and_latest() -> None:
    repo = WorkflowInstanceRepoStub()
    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)

    created = repo.create(workflow)

    assert created == workflow
    assert repo.get_by_id(workflow.workflow_instance_id) == workflow
    assert repo.get_running_by_workspace_id(workspace.workspace_id) == workflow
    assert repo.get_latest_by_workspace_id(workspace.workspace_id) == workflow


def test_workflow_attempt_repository_contract_tracks_next_attempt_number() -> None:
    repo = WorkflowAttemptRepoStub()
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)

    created = repo.create(attempt)

    assert created == attempt
    assert repo.get_by_id(attempt.attempt_id) == attempt
    assert repo.get_running_by_workflow_id(workflow.workflow_instance_id) == attempt
    assert repo.get_latest_by_workflow_id(workflow.workflow_instance_id) == attempt
    assert repo.get_next_attempt_number(workflow.workflow_instance_id) == 2


def test_checkpoint_repository_contract_returns_latest_for_workflow_and_attempt() -> (
    None
):
    repo = WorkflowCheckpointRepoStub()
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)
    checkpoint = sample_checkpoint(workflow.workflow_instance_id, attempt.attempt_id)

    created = repo.create(checkpoint)

    assert created == checkpoint
    assert repo.get_latest_by_workflow_id(workflow.workflow_instance_id) == checkpoint
    assert repo.get_latest_by_attempt_id(attempt.attempt_id) == checkpoint


def test_verify_report_repository_contract_returns_latest_by_attempt() -> None:
    repo = VerifyReportRepoStub()
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)
    verify_report = sample_verify_report(attempt.attempt_id)

    created = repo.create(verify_report)

    assert created == verify_report
    assert repo.get_latest_by_attempt_id(attempt.attempt_id) == verify_report


def test_memory_item_repository_contract_tracks_workspace_and_episode_items() -> None:
    repo = MemoryItemRepoStub()
    workspace = sample_workspace()
    older_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Older memory item",
        metadata={"kind": "investigation"},
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    newer_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=older_item.episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer memory item",
        metadata={"kind": "implementation"},
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
        updated_at=datetime(2024, 1, 9, tzinfo=UTC),
    )
    unrelated_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Unrelated memory item",
        metadata={"kind": "other"},
        created_at=datetime(2024, 1, 10, tzinfo=UTC),
        updated_at=datetime(2024, 1, 10, tzinfo=UTC),
    )

    assert repo.create(older_item) == older_item
    assert repo.create(newer_item) == newer_item
    assert repo.create(unrelated_item) == unrelated_item
    assert repo.list_by_workspace_id(workspace.workspace_id, limit=10) == (
        newer_item,
        older_item,
    )
    assert repo.list_by_episode_id(older_item.episode_id, limit=10) == (
        newer_item,
        older_item,
    )


def test_memory_embedding_repository_contract_tracks_embeddings_by_memory_item() -> (
    None
):
    repo = MemoryEmbeddingRepoStub()
    memory_id = uuid4()
    older_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-model",
        embedding=(0.1, 0.2, 0.3),
        content_hash="older-hash",
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    newer_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-model-v2",
        embedding=(0.4, 0.5, 0.6),
        content_hash="newer-hash",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )
    unrelated_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="other-model",
        embedding=(0.7, 0.8, 0.9),
        content_hash="other-hash",
        created_at=datetime(2024, 1, 10, tzinfo=UTC),
    )

    assert repo.create(older_embedding) == older_embedding
    assert repo.create(newer_embedding) == newer_embedding
    assert repo.create(unrelated_embedding) == unrelated_embedding
    assert repo.list_by_memory_id(memory_id, limit=10) == (
        newer_embedding,
        older_embedding,
    )


@pytest.mark.parametrize(
    ("query", "expected_fragment"),
    [
        ("SELECT 1", "SELECT 1"),
        ("SELECT to_regclass('workspaces')", "to_regclass"),
    ],
)
def test_fake_connection_records_executed_queries(
    query: str,
    expected_fragment: str,
) -> None:
    connection = FakeConnection()

    with connection.cursor() as cursor:
        cursor.execute(query)

    assert len(connection.executed) == 1
    assert expected_fragment in connection.executed[0][0]


def test_fake_connection_supports_fetchone_and_fetchall() -> None:
    connection = FakeConnection()
    connection.fetchone_results.append((1,))
    connection.fetchall_results.append([("a",), ("b",)])

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        one = cursor.fetchone()
        many = cursor.fetchall()

    assert one == (1,)
    assert many == [("a",), ("b",)]


def test_fake_connection_factory_returns_shared_connection() -> None:
    connection = FakeConnection()
    factory = FakeConnectionFactory(connection)

    first = factory()
    second = factory()

    assert first is connection
    assert second is connection


def test_postgres_low_level_helpers_and_pool_builder() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    assert postgres._json_dumps({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert postgres._json_loads(None) == {}
    assert postgres._json_loads('{"a": 1}') == {"a": 1}
    assert postgres._json_object_or_none(None) is None
    assert postgres._json_object_or_none({"a": 1}) == {"a": 1}
    assert postgres._json_object_or_none('{"a": 1}') == {"a": 1}
    assert postgres._json_object_or_none("[1,2]") is None
    assert postgres._json_object_or_none([("a", 1)]) == {"a": 1}

    aware = datetime(2024, 1, 1, tzinfo=UTC)
    naive = datetime(2024, 1, 1)
    assert postgres._to_datetime(aware) == aware
    assert postgres._to_datetime(naive).tzinfo == UTC
    with pytest.raises(PersistenceError, match="Expected datetime, got str"):
        postgres._to_datetime("bad")

    value_uuid = uuid4()
    assert postgres._to_uuid(value_uuid) == value_uuid
    assert postgres._to_uuid(str(value_uuid)) == value_uuid
    assert postgres._optional_datetime(None) is None
    assert postgres._optional_datetime(aware) == aware
    assert postgres._optional_str_enum(VerifyStatus, None) is None
    assert postgres._optional_str_enum(VerifyStatus, "passed") == VerifyStatus.PASSED
    assert postgres._normalized_schema_name(None) == "public"
    assert postgres._normalized_schema_name("  ") == "public"
    assert postgres._normalized_schema_name(" custom ") == "custom"
    assert postgres._parse_embedding_values(None) == ()
    assert postgres._parse_embedding_values("") == ()
    assert postgres._parse_embedding_values("[1, 2.5]") == (1.0, 2.5)
    assert postgres._parse_embedding_values((1, "2.5")) == (1.0, 2.5)
    assert postgres._quote_ident('a"b') == '"a""b"'
    assert postgres._episode_status(None) == "recorded"
    assert postgres._episode_status("ignored") == "ignored"
    assert postgres._pgvector_literal((1.0, 2.5)) == "[1,2.5]"

    class FakePool:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    original_pool = postgres.ConnectionPool
    try:
        postgres.ConnectionPool = FakePool
        config = postgres.PostgresConfig(
            database_url="postgresql://example/db",
            pool_min_size=2,
            pool_max_size=7,
            pool_timeout_seconds=9,
        )
        pool = postgres.build_connection_pool(config)
    finally:
        postgres.ConnectionPool = original_pool

    assert isinstance(pool, FakePool)
    assert pool.kwargs["conninfo"] == "postgresql://example/db"
    assert pool.kwargs["min_size"] == 2
    assert pool.kwargs["max_size"] == 7
    assert pool.kwargs["timeout"] == 9
    assert pool.kwargs["open"] is True


def test_postgres_config_from_settings_and_schema_loader() -> None:
    postgres = importlib.import_module("ctxledger.db.postgres")

    from types import SimpleNamespace

    settings = SimpleNamespace(
        database=SimpleNamespace(
            url="postgresql://example/db",
            connect_timeout_seconds=11,
            statement_timeout_ms=222,
            schema_name="  custom  ",
            pool_min_size=3,
            pool_max_size=6,
            pool_timeout_seconds=12,
        )
    )

    config = postgres.PostgresConfig.from_settings(settings)

    assert config.database_url == "postgresql://example/db"
    assert config.connect_timeout_seconds == 11
    assert config.statement_timeout_ms == 222
    assert config.schema_name == "custom"
    assert config.pool_min_size == 3
    assert config.pool_max_size == 6
    assert config.pool_timeout_seconds == 12

    schema_sql = postgres.load_postgres_schema_sql()
    assert "-- ctxledger PostgreSQL schema" in schema_sql


def test_in_memory_sort_helpers_cover_empty_and_limited_paths() -> None:
    from ctxledger.db import _latest_or_none, _sorted_limited

    assert _latest_or_none((), key=lambda item: item) is None
    assert _sorted_limited((3, 1, 2), key=lambda item: item, limit=2) == (3, 2)


def test_in_memory_workspace_repository_queries_create_and_update() -> None:
    workspace = sample_workspace()
    renamed_workspace = Workspace(
        workspace_id=workspace.workspace_id,
        repo_url=workspace.repo_url,
        canonical_path=f"{workspace.canonical_path}-renamed",
        default_branch="develop",
        metadata={"team": "platform", "language": "python"},
        created_at=workspace.created_at,
        updated_at=datetime(2024, 1, 3, tzinfo=UTC),
    )

    repo = InMemoryWorkspaceRepository({}, {})

    assert repo.get_by_id(workspace.workspace_id) is None
    assert repo.get_by_canonical_path(workspace.canonical_path) is None
    assert repo.get_by_repo_url("https://example.com/missing.git") == []

    assert repo.create(workspace) == workspace
    assert repo.get_by_id(workspace.workspace_id) == workspace
    assert repo.get_by_canonical_path(workspace.canonical_path) == workspace
    assert repo.get_by_repo_url(workspace.repo_url) == [workspace]

    assert repo.update(renamed_workspace) == renamed_workspace
    assert repo.get_by_canonical_path(workspace.canonical_path) is None
    assert (
        repo.get_by_canonical_path(renamed_workspace.canonical_path)
        == renamed_workspace
    )


def test_in_memory_workflow_instance_repository_filters_and_lists() -> None:
    workspace = sample_workspace()
    repo = InMemoryWorkflowInstanceRepository({})
    running_workflow = sample_workflow(workspace.workspace_id)
    completed_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace.workspace_id,
        ticket_id=running_workflow.ticket_id,
        status=running_workflow.status.COMPLETED,
        metadata={"priority": "low"},
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    other_ticket_workflow = WorkflowInstance(
        workflow_instance_id=uuid4(),
        workspace_id=workspace.workspace_id,
        ticket_id="OTHER-TICKET",
        status=running_workflow.status.RUNNING,
        metadata={},
        created_at=datetime(2024, 1, 6, tzinfo=UTC),
        updated_at=datetime(2024, 1, 7, tzinfo=UTC),
    )

    assert repo.get_by_id(running_workflow.workflow_instance_id) is None
    assert repo.get_running_by_workspace_id(workspace.workspace_id) is None
    assert repo.get_latest_by_workspace_id(workspace.workspace_id) is None
    assert repo.list_by_workspace_id(workspace.workspace_id, limit=5) == ()

    assert repo.create(running_workflow) == running_workflow
    assert repo.create(completed_workflow) == completed_workflow
    assert repo.update(other_ticket_workflow) == other_ticket_workflow

    assert repo.get_by_id(running_workflow.workflow_instance_id) == running_workflow
    assert (
        repo.get_running_by_workspace_id(workspace.workspace_id)
        == other_ticket_workflow
    )
    assert (
        repo.get_latest_by_workspace_id(workspace.workspace_id) == other_ticket_workflow
    )
    assert repo.list_by_workspace_id(workspace.workspace_id, limit=2) == (
        other_ticket_workflow,
        completed_workflow,
    )
    assert repo.list_by_ticket_id(running_workflow.ticket_id, limit=5) == (
        completed_workflow,
        running_workflow,
    )
    assert repo.list_recent(limit=5, status="running") == (
        other_ticket_workflow,
        running_workflow,
    )
    assert repo.list_recent(
        limit=5,
        status="running",
        workspace_id=workspace.workspace_id,
        ticket_id="OTHER-TICKET",
    ) == (other_ticket_workflow,)


def test_in_memory_workflow_attempt_repository_queries_and_next_number() -> None:
    workflow = sample_workflow(sample_workspace().workspace_id)
    repo = InMemoryWorkflowAttemptRepository({})
    running_attempt = sample_attempt(workflow.workflow_instance_id)
    newer_finished_attempt = WorkflowAttempt(
        attempt_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        attempt_number=2,
        status=running_attempt.status.SUCCEEDED,
        failure_reason=None,
        verify_status=VerifyStatus.PASSED,
        started_at=datetime(2024, 1, 4, tzinfo=UTC),
        finished_at=datetime(2024, 1, 5, tzinfo=UTC),
        created_at=datetime(2024, 1, 4, tzinfo=UTC),
        updated_at=datetime(2024, 1, 5, tzinfo=UTC),
    )

    assert repo.get_by_id(running_attempt.attempt_id) is None
    assert repo.get_running_by_workflow_id(workflow.workflow_instance_id) is None
    assert repo.get_latest_by_workflow_id(workflow.workflow_instance_id) is None
    assert repo.get_next_attempt_number(workflow.workflow_instance_id) == 1

    assert repo.create(running_attempt) == running_attempt
    assert repo.update(newer_finished_attempt) == newer_finished_attempt

    assert repo.get_by_id(running_attempt.attempt_id) == running_attempt
    assert (
        repo.get_running_by_workflow_id(workflow.workflow_instance_id)
        == running_attempt
    )
    assert (
        repo.get_latest_by_workflow_id(workflow.workflow_instance_id)
        == newer_finished_attempt
    )
    assert repo.get_next_attempt_number(workflow.workflow_instance_id) == 3


def test_in_memory_checkpoint_and_verify_report_repositories_return_latest() -> None:
    workflow = sample_workflow(sample_workspace().workspace_id)
    attempt = sample_attempt(workflow.workflow_instance_id)
    checkpoint_repo = InMemoryWorkflowCheckpointRepository({})
    verify_repo = InMemoryVerifyReportRepository({})

    older_checkpoint = sample_checkpoint(
        workflow.workflow_instance_id, attempt.attempt_id
    )
    newer_checkpoint = sample_checkpoint(
        workflow.workflow_instance_id, attempt.attempt_id
    )
    newer_checkpoint = newer_checkpoint.__class__(
        checkpoint_id=newer_checkpoint.checkpoint_id,
        workflow_instance_id=newer_checkpoint.workflow_instance_id,
        attempt_id=newer_checkpoint.attempt_id,
        step_name="later_step",
        summary="later summary",
        checkpoint_json=newer_checkpoint.checkpoint_json,
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    older_verify = sample_verify_report(attempt.attempt_id)
    newer_verify = sample_verify_report(attempt.attempt_id)
    newer_verify = VerifyReport(
        verify_id=newer_verify.verify_id,
        attempt_id=newer_verify.attempt_id,
        status=newer_verify.status,
        report_json=newer_verify.report_json,
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    assert (
        checkpoint_repo.get_latest_by_workflow_id(workflow.workflow_instance_id) is None
    )
    assert checkpoint_repo.get_latest_by_attempt_id(attempt.attempt_id) is None
    assert verify_repo.get_latest_by_attempt_id(attempt.attempt_id) is None

    assert checkpoint_repo.create(older_checkpoint) == older_checkpoint
    assert checkpoint_repo.create(newer_checkpoint) == newer_checkpoint
    assert verify_repo.create(older_verify) == older_verify
    assert verify_repo.create(newer_verify) == newer_verify

    assert (
        checkpoint_repo.get_latest_by_workflow_id(workflow.workflow_instance_id)
        == newer_checkpoint
    )
    assert (
        checkpoint_repo.get_latest_by_attempt_id(attempt.attempt_id) == newer_checkpoint
    )
    assert verify_repo.get_latest_by_attempt_id(attempt.attempt_id) == newer_verify


def test_in_memory_memory_repositories_cover_listing_and_provenance_counting() -> None:
    workspace = sample_workspace()
    workflow = sample_workflow(workspace.workspace_id)
    episode_repo = InMemoryMemoryEpisodeRepository({})
    item_repo = InMemoryMemoryItemRepository({})
    embedding_repo = InMemoryMemoryEmbeddingRepository({})

    episode_record = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        summary="current episode",
        attempt_id=None,
        metadata={"kind": "episode"},
        created_at=datetime(2024, 1, 10, tzinfo=UTC),
        updated_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    older_episode_record = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow.workflow_instance_id,
        summary="older episode",
        attempt_id=None,
        metadata={"kind": "episode"},
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
        updated_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    older_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=episode_record.episode_id,
        type="episode_note",
        provenance="episode",
        content="older",
        metadata={"kind": "investigation"},
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
        updated_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    newer_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=episode_record.episode_id,
        type="episode_note",
        provenance="derived",
        content="newer",
        metadata={"kind": "implementation"},
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
        updated_at=datetime(2024, 1, 9, tzinfo=UTC),
    )
    older_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=newer_item.memory_id,
        embedding_model="local-stub-v1",
        embedding=(0.1, 0.2),
        content_hash="older-hash",
        created_at=datetime(2024, 1, 8, tzinfo=UTC),
    )
    newer_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=newer_item.memory_id,
        embedding_model="local-stub-v1",
        embedding=(0.3, 0.4),
        content_hash="newer-hash",
        created_at=datetime(2024, 1, 9, tzinfo=UTC),
    )

    assert episode_repo.create(older_episode_record) == older_episode_record
    assert episode_repo.create(episode_record) == episode_record
    assert item_repo.create(older_item) == older_item
    assert item_repo.create(newer_item) == newer_item
    assert embedding_repo.create(older_embedding) == older_embedding
    assert embedding_repo.create(newer_embedding) == newer_embedding

    assert episode_repo.list_by_workflow_id(workflow.workflow_instance_id, limit=5) == (
        episode_record,
        older_episode_record,
    )
    assert item_repo.list_by_workspace_id(workspace.workspace_id, limit=5) == (
        newer_item,
        older_item,
    )
    assert item_repo.list_by_episode_id(episode_record.episode_id, limit=5) == (
        newer_item,
        older_item,
    )
    assert item_repo.count_by_provenance() == {"episode": 1, "derived": 1}
    assert embedding_repo.list_by_memory_id(newer_item.memory_id, limit=5) == (
        newer_embedding,
        older_embedding,
    )


def test_in_memory_unit_of_work_lifecycle_store_and_factory() -> None:
    store = InMemoryStore.create()
    assert store.workspaces_by_id == {}
    assert store.workspaces_by_canonical_path == {}
    assert store.workflows_by_id == {}
    assert store.attempts_by_id == {}
    assert store.checkpoints_by_id == {}
    assert store.verify_reports_by_id == {}
    assert store.episodes_by_id == {}
    assert store.memory_items_by_id == {}
    assert store.memory_embeddings_by_id == {}

    workspace = sample_workspace()
    store.workspaces_by_id[workspace.workspace_id] = workspace
    store.workspaces_by_canonical_path[workspace.canonical_path] = (
        workspace.workspace_id
    )

    snapshot = store.snapshot()
    assert snapshot is not store
    assert snapshot.workspaces_by_id == store.workspaces_by_id
    assert snapshot.workspaces_by_canonical_path == store.workspaces_by_canonical_path

    uow = InMemoryUnitOfWork(
        workspaces_by_id=store.workspaces_by_id,
        workspaces_by_canonical_path=store.workspaces_by_canonical_path,
    )
    assert uow.__enter__() is uow
    assert uow.workspaces.get_by_id(workspace.workspace_id) == workspace

    uow.commit()
    assert uow._committed is True
    assert uow._rolled_back is False

    uow.__exit__(None, None, None)
    assert uow._rolled_back is False

    uncommitted_uow = InMemoryUnitOfWork()
    assert uncommitted_uow._committed is False
    assert uncommitted_uow._rolled_back is False
    uncommitted_uow.__exit__(RuntimeError, RuntimeError("boom"), None)
    assert uncommitted_uow._rolled_back is True

    factory = build_in_memory_uow_factory(store)
    first = factory()
    second = factory()
    assert isinstance(first, InMemoryUnitOfWork)
    assert isinstance(second, InMemoryUnitOfWork)
    assert first is not second

    new_workspace = sample_workspace()
    first.workspaces.create(new_workspace)
    assert second.workspaces.get_by_id(new_workspace.workspace_id) == new_workspace
