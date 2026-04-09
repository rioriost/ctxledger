from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ctxledger.memory.service import (
    MemoryRelationRecord,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)
from ctxledger.workflow.service import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryEmbeddingRepository,
    MemoryEpisodeRepository,
    MemoryItemRecord,
    MemoryItemRepository,
    PersistenceError,
)

from .postgres_common import (
    AgeGraphStatus,
    Connection,
    PostgresConfig,
    PostgresDatabaseHealthChecker,
    _episode_status,
    _json_dumps,
    _json_loads,
    _memory_embedding_row_to_record,
    _memory_item_row_to_record,
    _memory_summary_membership_row_to_record,
    _memory_summary_row_to_record,
    _optional_datetime,
    _pgvector_literal,
    _to_datetime,
    _to_uuid,
)


class PostgresMemoryEpisodeRepository(MemoryEpisodeRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM episodes")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"created_at", "updated_at"}:
            raise PersistenceError(f"Unsupported datetime field '{field_name}' for episodes")
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM episodes")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO episodes (
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    episode.episode_id,
                    episode.workflow_instance_id,
                    episode.attempt_id,
                    episode.summary,
                    episode.status,
                    _json_dumps(episode.metadata),
                    episode.created_at,
                    episode.updated_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create episode")

        return self._row_to_episode(row)

    def get_by_episode_id(
        self,
        episode_id: UUID,
    ) -> EpisodeRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM episodes
                WHERE episode_id = %s
                LIMIT 1
                """,
                (episode_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return self._row_to_episode(row)

    def list_by_workflow_id(
        self,
        workflow_instance_id: UUID,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    episode_id,
                    workflow_instance_id,
                    attempt_id,
                    summary,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                FROM episodes
                WHERE workflow_instance_id = %s
                ORDER BY created_at DESC, episode_id DESC
                LIMIT %s
                """,
                (workflow_instance_id, limit),
            )
            rows = cur.fetchall()

        return tuple(self._row_to_episode(row) for row in rows)

    def _row_to_episode(
        self,
        row: dict[str, Any],
    ) -> EpisodeRecord:
        return EpisodeRecord(
            episode_id=_to_uuid(row["episode_id"]),
            workflow_instance_id=_to_uuid(row["workflow_instance_id"]),
            summary=str(row["summary"]),
            attempt_id=(_to_uuid(row["attempt_id"]) if row.get("attempt_id") is not None else None),
            metadata=_json_loads(row["metadata_json"]),
            status=_episode_status(row.get("status")),
            created_at=_to_datetime(row["created_at"]),
            updated_at=_to_datetime(row["updated_at"]),
        )


class PostgresMemoryItemRepository(MemoryItemRepository):
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_items")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def count_by_provenance(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT provenance, COUNT(*) AS count
                FROM memory_items
                GROUP BY provenance
                ORDER BY provenance ASC
                """
            )
            rows = cur.fetchall()
        return {str(row["provenance"]): int(row["count"]) for row in rows}

    def count_with_any_file_work_metadata(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM memory_items
                WHERE
                    (
                        metadata_json ? 'file_name'
                        AND btrim(COALESCE(metadata_json->>'file_name', '')) <> ''
                    )
                    OR (
                        metadata_json ? 'file_path'
                        AND btrim(COALESCE(metadata_json->>'file_path', '')) <> ''
                    )
                    OR (
                        metadata_json ? 'file_operation'
                        AND btrim(COALESCE(metadata_json->>'file_operation', '')) <> ''
                    )
                    OR (
                        metadata_json ? 'purpose'
                        AND btrim(COALESCE(metadata_json->>'purpose', '')) <> ''
                    )
                """
            )
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name not in {"created_at", "updated_at"}:
            raise PersistenceError(f"Unsupported datetime field '{field_name}' for memory_items")
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM memory_items")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def max_datetime_for_provenance(self, provenance: str) -> datetime | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(created_at) AS value
                FROM memory_items
                WHERE provenance = %s
                """,
                (provenance,),
            )
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_items (
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    memory_item.memory_id,
                    memory_item.workspace_id,
                    memory_item.episode_id,
                    memory_item.type,
                    memory_item.provenance,
                    memory_item.content,
                    _json_dumps(memory_item.metadata),
                    memory_item.created_at,
                    memory_item.updated_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory item")

        return _memory_item_row_to_record(row)

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE workspace_id = %s
                ORDER BY created_at DESC, memory_id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_workspace_root_items(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE workspace_id = %s
                  AND episode_id IS NULL
                ORDER BY created_at DESC, memory_id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_by_memory_ids(
        self,
        memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]:
        if not memory_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(memory_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE memory_id IN ({placeholders})
                ORDER BY created_at DESC, memory_id DESC
                """,
                memory_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_by_episode_ids(
        self,
        episode_ids: tuple[UUID, ...],
    ) -> tuple[MemoryItemRecord, ...]:
        if not episode_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(episode_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE episode_id IN ({placeholders})
                ORDER BY created_at DESC, memory_id DESC
                """,
                episode_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    workspace_id,
                    episode_id,
                    type,
                    provenance,
                    content,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_items
                WHERE episode_id = %s
                ORDER BY created_at DESC, memory_id DESC
                LIMIT %s
                """,
                (episode_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_item_row_to_record(row) for row in rows)


class PostgresMemorySummaryRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_summaries")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def create(self, summary: MemorySummaryRecord) -> MemorySummaryRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_summaries (
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                """,
                (
                    summary.memory_summary_id,
                    summary.workspace_id,
                    summary.episode_id,
                    summary.summary_text,
                    summary.summary_kind,
                    _json_dumps(summary.metadata),
                    summary.created_at,
                    summary.updated_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory summary")

        return _memory_summary_row_to_record(row)

    def delete_by_summary_id(
        self,
        memory_summary_id: UUID,
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM memory_summaries
                WHERE memory_summary_id = %s
                """,
                (memory_summary_id,),
            )

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_summaries
                WHERE workspace_id = %s
                ORDER BY created_at DESC, memory_summary_id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_row_to_record(row) for row in rows)

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_summaries
                WHERE episode_id = %s
                ORDER BY created_at DESC, memory_summary_id DESC
                LIMIT %s
                """,
                (episode_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_row_to_record(row) for row in rows)

    def list_by_summary_ids(
        self,
        summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryRecord, ...]:
        if not summary_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(summary_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_text,
                    summary_kind,
                    metadata_json,
                    created_at,
                    updated_at
                FROM memory_summaries
                WHERE memory_summary_id IN ({placeholders})
                ORDER BY created_at DESC, memory_summary_id DESC
                """,
                summary_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_row_to_record(row) for row in rows)


class PostgresMemorySummaryMembershipRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_summary_memberships")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def create(
        self,
        membership: MemorySummaryMembershipRecord,
    ) -> MemorySummaryMembershipRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_summary_memberships (
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                """,
                (
                    membership.memory_summary_membership_id,
                    membership.memory_summary_id,
                    membership.memory_id,
                    membership.membership_order,
                    _json_dumps(membership.metadata),
                    membership.created_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory summary membership")

        return _memory_summary_membership_row_to_record(row)

    def delete_by_summary_id(
        self,
        memory_summary_id: UUID,
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM memory_summary_memberships
                WHERE memory_summary_id = %s
                """,
                (memory_summary_id,),
            )

    def list_by_summary_id(
        self,
        memory_summary_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                FROM memory_summary_memberships
                WHERE memory_summary_id = %s
                ORDER BY
                    membership_order ASC NULLS LAST,
                    created_at ASC,
                    memory_summary_membership_id ASC
                LIMIT %s
                """,
                (memory_summary_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_membership_row_to_record(row) for row in rows)

    def list_by_summary_ids(
        self,
        memory_summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryMembershipRecord, ...]:
        if not memory_summary_ids:
            return ()

        placeholders = ", ".join(["%s"] * len(memory_summary_ids))
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order,
                    metadata_json,
                    created_at
                FROM memory_summary_memberships
                WHERE memory_summary_id IN ({placeholders})
                ORDER BY
                    memory_summary_id ASC,
                    membership_order ASC NULLS LAST,
                    created_at ASC,
                    memory_summary_membership_id ASC
                """,
                memory_summary_ids,
            )
            rows = cur.fetchall()

        return tuple(_memory_summary_membership_row_to_record(row) for row in rows)


class PostgresMemoryEmbeddingRepository(MemoryEmbeddingRepository):
    """PostgreSQL-backed repository for persisted embedding records.

    Execution-boundary note:

    - This repository exists for persistence-oriented embedding work.
    - Its responsibility is to store and query derived embedding records that
      support durable retrieval behavior over already stored memory items.
    - In large Azure deployments, this can include PostgreSQL-side embedding
      generation through the `azure_ai` / `azure_openai` path.
    - This repository is not intended to be the execution boundary for
      interactive AI responses whose result should be returned directly to an
      MCP client without first being materialized into PostgreSQL.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_embeddings")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name != "created_at":
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for memory_embeddings"
            )
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT MAX({field_name}) AS value FROM memory_embeddings")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        # Small / app-generated persistence path:
        # the application process has already produced the embedding vector, and
        # this repository is only responsible for storing that derived value as
        # durable retrieval-support state.
        embedding_literal = _pgvector_literal(embedding.embedding)

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_embeddings (
                    memory_embedding_id,
                    memory_id,
                    embedding_model,
                    embedding,
                    content_hash,
                    created_at
                )
                VALUES (%s, %s, %s, %s::vector, %s, %s)
                RETURNING
                    memory_embedding_id,
                    memory_id,
                    embedding_model,
                    embedding::text AS embedding,
                    content_hash,
                    created_at
                """,
                (
                    embedding.memory_embedding_id,
                    embedding.memory_id,
                    embedding.embedding_model,
                    embedding_literal,
                    embedding.content_hash,
                    embedding.created_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory embedding")

        return _memory_embedding_row_to_record(row)

    def create_via_postgres_azure_ai(
        self,
        *,
        memory_id: UUID,
        content: str,
        embedding_model: str,
        content_hash: str | None,
        created_at: datetime,
        azure_openai_deployment: str,
        azure_openai_dimensions: int | None = None,
    ) -> MemoryEmbeddingRecord:
        # Large Azure persistence path:
        # the source record already exists in durable storage, and PostgreSQL is
        # being asked to materialize a derived embedding record through
        # `azure_openai.create_embeddings(...)`.
        #
        # This remains persistence-oriented work because the output is inserted
        # into `memory_embeddings` as stored retrieval support state.
        normalized_content = content.strip()
        if not normalized_content:
            raise PersistenceError("Cannot create PostgreSQL azure_ai embedding for empty content")

        resolved_content_hash = (
            content_hash or hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
        )
        memory_embedding_id = uuid4()

        with self._conn.cursor() as cur:
            if azure_openai_dimensions is None:
                cur.execute(
                    """
                    INSERT INTO memory_embeddings (
                        memory_embedding_id,
                        memory_id,
                        embedding_model,
                        embedding,
                        content_hash,
                        created_at
                    )
                    SELECT
                        %s,
                        %s,
                        %s,
                        azure_openai.create_embeddings(%s, %s)::vector,
                        %s,
                        %s
                    RETURNING
                        memory_embedding_id,
                        memory_id,
                        embedding_model,
                        embedding::text AS embedding,
                        content_hash,
                        created_at
                    """,
                    (
                        memory_embedding_id,
                        memory_id,
                        embedding_model,
                        azure_openai_deployment,
                        normalized_content,
                        resolved_content_hash,
                        created_at,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO memory_embeddings (
                        memory_embedding_id,
                        memory_id,
                        embedding_model,
                        embedding,
                        content_hash,
                        created_at
                    )
                    SELECT
                        %s,
                        %s,
                        %s,
                        azure_openai.create_embeddings(
                            %s,
                            %s,
                            dimensions => %s
                        )::vector,
                        %s,
                        %s
                    RETURNING
                        memory_embedding_id,
                        memory_id,
                        embedding_model,
                        embedding::text AS embedding,
                        content_hash,
                        created_at
                    """,
                    (
                        memory_embedding_id,
                        memory_id,
                        embedding_model,
                        azure_openai_deployment,
                        normalized_content,
                        azure_openai_dimensions,
                        resolved_content_hash,
                        created_at,
                    ),
                )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create PostgreSQL azure_ai memory embedding")

        return _memory_embedding_row_to_record(row)

    def list_by_memory_id(
        self,
        memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_embedding_id,
                    memory_id,
                    embedding_model,
                    embedding::text AS embedding,
                    content_hash,
                    created_at
                FROM memory_embeddings
                WHERE memory_id = %s
                ORDER BY created_at DESC, memory_embedding_id DESC
                LIMIT %s
                """,
                (memory_id, limit),
            )
            rows = cur.fetchall()

        return tuple(_memory_embedding_row_to_record(row) for row in rows)

    def find_similar(
        self,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
        workspace_id: UUID | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        # Stored-embedding retrieval path:
        # the query embedding is already available to the application, and this
        # repository uses PostgreSQL to rank against previously materialized
        # embedding rows.
        workspace_filter_sql = ""
        if workspace_id is None:
            params: tuple[Any, ...] = (
                _pgvector_literal(query_embedding),
                limit,
            )
        else:
            workspace_filter_sql = "AND mi.workspace_id = %s"
            params = (
                workspace_id,
                _pgvector_literal(query_embedding),
                limit,
            )

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    me.memory_embedding_id,
                    me.memory_id,
                    me.embedding_model,
                    me.embedding,
                    me.content_hash,
                    me.created_at
                FROM memory_embeddings AS me
                INNER JOIN memory_items AS mi
                    ON mi.memory_id = me.memory_id
                WHERE me.embedding IS NOT NULL
                  {workspace_filter_sql}
                ORDER BY
                    me.embedding <-> %s::vector ASC,
                    me.created_at DESC,
                    me.memory_embedding_id DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

        return tuple(_memory_embedding_row_to_record(row) for row in rows)

    def find_similar_by_query_via_postgres_azure_ai(
        self,
        query_text: str,
        *,
        azure_openai_deployment: str,
        limit: int,
        workspace_id: UUID | None = None,
        azure_openai_dimensions: int | None = None,
    ) -> tuple[MemoryEmbeddingRecord, ...]:
        # PostgreSQL-side query-embedding retrieval path:
        #
        # - the user query is transient
        # - PostgreSQL generates an embedding for ranking purposes through
        #   `azure_openai.create_embeddings(...)`
        # - the query embedding itself is not being materialized into durable
        #   state here
        #
        # Even so, this helper still belongs to the persistence-oriented memory
        # retrieval boundary, not to a direct client-facing interactive AI
        # response path. Its purpose is to rank over stored embedding records and
        # return durable memory matches, not to return raw model output to the
        # client.
        normalized_query = query_text.strip()
        if not normalized_query:
            return ()

        workspace_filter_sql = ""
        if workspace_id is None:
            if azure_openai_dimensions is None:
                params: tuple[Any, ...] = (
                    azure_openai_deployment,
                    normalized_query,
                    limit,
                )
            else:
                params = (
                    azure_openai_deployment,
                    normalized_query,
                    azure_openai_dimensions,
                    limit,
                )
        else:
            workspace_filter_sql = "AND mi.workspace_id = %s"
            if azure_openai_dimensions is None:
                params = (
                    workspace_id,
                    azure_openai_deployment,
                    normalized_query,
                    limit,
                )
            else:
                params = (
                    workspace_id,
                    azure_openai_deployment,
                    normalized_query,
                    azure_openai_dimensions,
                    limit,
                )

        with self._conn.cursor() as cur:
            if azure_openai_dimensions is None:
                cur.execute(
                    f"""
                    SELECT
                        me.memory_embedding_id,
                        me.memory_id,
                        me.embedding_model,
                        me.embedding::text AS embedding,
                        me.content_hash,
                        me.created_at
                    FROM memory_embeddings AS me
                    INNER JOIN memory_items AS mi
                        ON mi.memory_id = me.memory_id
                    WHERE me.embedding IS NOT NULL
                      {workspace_filter_sql}
                    ORDER BY
                        me.embedding <-> azure_openai.create_embeddings(%s, %s)::vector ASC,
                        me.created_at DESC,
                        me.memory_embedding_id DESC
                    LIMIT %s
                    """,
                    params,
                )
            else:
                cur.execute(
                    f"""
                    SELECT
                        me.memory_embedding_id,
                        me.memory_id,
                        me.embedding_model,
                        me.embedding::text AS embedding,
                        me.content_hash,
                        me.created_at
                    FROM memory_embeddings AS me
                    INNER JOIN memory_items AS mi
                        ON mi.memory_id = me.memory_id
                    WHERE me.embedding IS NOT NULL
                      {workspace_filter_sql}
                    ORDER BY
                        me.embedding <-> azure_openai.create_embeddings(
                            %s,
                            %s,
                            dimensions => %s
                        )::vector ASC,
                        me.created_at DESC,
                        me.memory_embedding_id DESC
                    LIMIT %s
                    """,
                    params,
                )
            rows = cur.fetchall()

        return tuple(_memory_embedding_row_to_record(row) for row in rows)


class PostgresMemoryRelationRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def list_distinct_support_target_memory_ids_by_source_memory_ids_via_age(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        graph_name: str,
    ) -> tuple[UUID, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute("LOAD 'age'")
            cur.execute('SET search_path = ag_catalog, "$user", public')
            cur.execute(
                """
                SELECT target_memory_id
                FROM cypher(
                    %s,
                    $$
                    MATCH (source:memory_item)-[relation:supports]->(target:memory_item)
                    WHERE source.memory_id IN $source_memory_ids
                    RETURN DISTINCT target.memory_id AS target_memory_id
                    $$
                ) AS (
                    target_memory_id agtype
                )
                """,
                (
                    graph_name,
                    json.dumps(
                        {
                            "source_memory_ids": [
                                str(source_memory_id) for source_memory_id in source_memory_ids
                            ]
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
            rows = cur.fetchall()

        target_memory_ids: list[UUID] = []
        for row in rows:
            raw_target_memory_id = row["target_memory_id"]
            if isinstance(raw_target_memory_id, str):
                normalized_target_memory_id = raw_target_memory_id.strip('"')
            else:
                normalized_target_memory_id = str(raw_target_memory_id)
            target_memory_ids.append(_to_uuid(normalized_target_memory_id))

        return tuple(target_memory_ids)

    def list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        graph_name: str,
        graph_status: AgeGraphStatus,
    ) -> tuple[UUID, ...]:
        if graph_status is not AgeGraphStatus.GRAPH_READY:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids(
                source_memory_ids
            )

        try:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids_via_age(
                source_memory_ids,
                graph_name=graph_name,
            )
        except Exception:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids(
                source_memory_ids
            )

    def list_distinct_support_target_memory_ids_by_source_memory_ids_for_config(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        config: PostgresConfig,
        health_checker: PostgresDatabaseHealthChecker | None = None,
    ) -> tuple[UUID, ...]:
        if not config.age_enabled:
            return self.list_distinct_support_target_memory_ids_by_source_memory_ids(
                source_memory_ids
            )

        checker = health_checker or PostgresDatabaseHealthChecker(config)
        graph_status = checker.age_graph_status(config.age_graph_name)

        return self.list_distinct_support_target_memory_ids_by_source_memory_ids_with_fallback(
            source_memory_ids,
            graph_name=config.age_graph_name,
            graph_status=graph_status,
        )

    def list_distinct_summary_member_memory_ids_by_source_memory_ids_via_age(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        graph_name: str,
    ) -> tuple[UUID, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute("LOAD 'age'")
            cur.execute('SET search_path = ag_catalog, "$user", public')
            cur.execute(
                """
                SELECT member_memory_id
                FROM cypher(
                    %s,
                    $$
                    MATCH (source:memory_item)<-[:summarizes]-(summary:memory_summary)
                          -[:summarizes]->(member:memory_item)
                    WHERE source.memory_id IN $source_memory_ids
                    RETURN DISTINCT member.memory_id AS member_memory_id
                    $$
                ) AS (
                    member_memory_id agtype
                )
                """,
                (
                    graph_name,
                    json.dumps(
                        {
                            "source_memory_ids": [
                                str(source_memory_id) for source_memory_id in source_memory_ids
                            ]
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
            rows = cur.fetchall()

        member_memory_ids: list[UUID] = []
        for row in rows:
            raw_member_memory_id = row["member_memory_id"]
            if isinstance(raw_member_memory_id, str):
                normalized_member_memory_id = raw_member_memory_id.strip('"')
            else:
                normalized_member_memory_id = str(raw_member_memory_id)
            member_memory_ids.append(_to_uuid(normalized_member_memory_id))

        return tuple(member_memory_ids)

    def list_distinct_summary_member_memory_ids_by_source_memory_ids_with_fallback(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        graph_name: str,
        graph_status: AgeGraphStatus,
    ) -> tuple[UUID, ...]:
        if graph_status is not AgeGraphStatus.GRAPH_READY:
            return ()

        try:
            return self.list_distinct_summary_member_memory_ids_by_source_memory_ids_via_age(
                source_memory_ids,
                graph_name=graph_name,
            )
        except Exception:
            return ()

    def list_distinct_summary_member_memory_ids_by_source_memory_ids_for_config(
        self,
        source_memory_ids: tuple[UUID, ...],
        *,
        config: PostgresConfig,
        health_checker: PostgresDatabaseHealthChecker | None = None,
    ) -> tuple[UUID, ...]:
        if not config.age_enabled:
            return ()

        checker = health_checker or PostgresDatabaseHealthChecker(config)
        graph_status = checker.age_graph_status(config.age_graph_name)

        return self.list_distinct_summary_member_memory_ids_by_source_memory_ids_with_fallback(
            source_memory_ids,
            graph_name=config.age_graph_name,
            graph_status=graph_status,
        )

    @staticmethod
    def workflow_completion_summary_build_requested(
        checkpoint_payload: object,
    ) -> bool:
        if not isinstance(checkpoint_payload, dict):
            return False
        return checkpoint_payload.get("build_episode_summary") is True

    @staticmethod
    def workflow_completion_summary_build_policy(
        checkpoint_payload: object,
    ) -> dict[str, object]:
        requested = PostgresMemoryRelationRepository.workflow_completion_summary_build_requested(
            checkpoint_payload
        )
        return {
            "summary_build_requested": requested,
            "summary_build_trigger": (
                "latest_checkpoint.build_episode_summary_true" if requested else None
            ),
            "summary_build_scope": "workflow_completion_auto_memory_episode",
            "summary_build_kind": "episode_summary",
            "summary_build_replace_existing": True,
            "summary_build_non_fatal": True,
        }

    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_relations (
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                """,
                (
                    relation.memory_relation_id,
                    relation.source_memory_id,
                    relation.target_memory_id,
                    relation.relation_type,
                    _json_dumps(relation.metadata),
                    relation.created_at,
                ),
            )
            row = cur.fetchone()

        if row is None:
            raise PersistenceError("Failed to create memory relation")

        return MemoryRelationRecord(
            memory_relation_id=_to_uuid(row["memory_relation_id"]),
            source_memory_id=_to_uuid(row["source_memory_id"]),
            target_memory_id=_to_uuid(row["target_memory_id"]),
            relation_type=str(row["relation_type"]),
            metadata=_json_loads(row["metadata_json"]),
            created_at=_to_datetime(row["created_at"]),
        )

    def list_by_source_memory_id(
        self,
        source_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                FROM memory_relations
                WHERE source_memory_id = %s
                ORDER BY created_at DESC, memory_relation_id DESC
                LIMIT %s
                """,
                (source_memory_id, limit),
            )
            rows = cur.fetchall()

        return tuple(
            MemoryRelationRecord(
                memory_relation_id=_to_uuid(row["memory_relation_id"]),
                source_memory_id=_to_uuid(row["source_memory_id"]),
                target_memory_id=_to_uuid(row["target_memory_id"]),
                relation_type=str(row["relation_type"]),
                metadata=_json_loads(row["metadata_json"]),
                created_at=_to_datetime(row["created_at"]),
            )
            for row in rows
        )

    def list_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[MemoryRelationRecord, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                FROM memory_relations
                WHERE source_memory_id = ANY(%s)
                ORDER BY created_at DESC, memory_relation_id DESC
                """,
                (list(source_memory_ids),),
            )
            rows = cur.fetchall()

        return tuple(
            MemoryRelationRecord(
                memory_relation_id=_to_uuid(row["memory_relation_id"]),
                source_memory_id=_to_uuid(row["source_memory_id"]),
                target_memory_id=_to_uuid(row["target_memory_id"]),
                relation_type=str(row["relation_type"]),
                metadata=_json_loads(row["metadata_json"]),
                created_at=_to_datetime(row["created_at"]),
            )
            for row in rows
        )

    def list_distinct_support_target_memory_ids_by_source_memory_ids(
        self,
        source_memory_ids: tuple[UUID, ...],
    ) -> tuple[UUID, ...]:
        if not source_memory_ids:
            return ()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked_support_relations AS (
                    SELECT
                        target_memory_id,
                        source_memory_id,
                        created_at,
                        memory_relation_id,
                        array_position(%s::uuid[], source_memory_id) AS source_position,
                        ROW_NUMBER() OVER (
                            PARTITION BY target_memory_id
                            ORDER BY
                                array_position(%s::uuid[], source_memory_id),
                                created_at DESC,
                                memory_relation_id DESC
                        ) AS target_rank
                    FROM memory_relations
                    WHERE source_memory_id = ANY(%s)
                      AND relation_type = 'supports'
                )
                SELECT target_memory_id
                FROM ranked_support_relations
                WHERE target_rank = 1
                ORDER BY source_position, created_at DESC, memory_relation_id DESC
                """,
                (
                    list(source_memory_ids),
                    list(source_memory_ids),
                    list(source_memory_ids),
                ),
            )
            rows = cur.fetchall()

        return tuple(_to_uuid(row["target_memory_id"]) for row in rows)

    def list_by_target_memory_id(
        self,
        target_memory_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_relation_id,
                    source_memory_id,
                    target_memory_id,
                    relation_type,
                    metadata_json,
                    created_at
                FROM memory_relations
                WHERE target_memory_id = %s
                ORDER BY created_at DESC, memory_relation_id DESC
                LIMIT %s
                """,
                (target_memory_id, limit),
            )
            rows = cur.fetchall()

        return tuple(
            MemoryRelationRecord(
                memory_relation_id=_to_uuid(row["memory_relation_id"]),
                source_memory_id=_to_uuid(row["source_memory_id"]),
                target_memory_id=_to_uuid(row["target_memory_id"]),
                relation_type=str(row["relation_type"]),
                metadata=_json_loads(row["metadata_json"]),
                created_at=_to_datetime(row["created_at"]),
            )
            for row in rows
        )

    def count_all(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM memory_relations")
            row = cur.fetchone()
        return int(row["count"]) if row is not None else 0

    def max_datetime(self, field_name: str) -> datetime | None:
        if field_name != "created_at":
            raise PersistenceError(
                f"Unsupported datetime field '{field_name}' for memory_relations"
            )
        with self._conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) AS value FROM memory_relations")
            row = cur.fetchone()
        return _optional_datetime(None if row is None else row["value"])


__all__ = [
    "PostgresMemoryEmbeddingRepository",
    "PostgresMemoryEpisodeRepository",
    "PostgresMemoryItemRepository",
    "PostgresMemoryRelationRepository",
    "PostgresMemorySummaryMembershipRepository",
    "PostgresMemorySummaryRepository",
]
