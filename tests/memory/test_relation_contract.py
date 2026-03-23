from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.memory.service import MemoryRelationRecord
from ctxledger.workflow.service import MemoryRelationRepository


class InMemoryMemoryRelationRepository(MemoryRelationRepository):
    def __init__(self) -> None:
        self._relations: list[MemoryRelationRecord] = []

    @property
    def relations(self) -> tuple[MemoryRelationRecord, ...]:
        return tuple(self._relations)

    def create(self, relation: MemoryRelationRecord) -> MemoryRelationRecord:
        self._relations.append(relation)
        return relation

    def list_by_source_memory_id(
        self,
        source_memory_id,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        matches = [
            relation
            for relation in self._relations
            if relation.source_memory_id == source_memory_id
        ]
        matches.sort(key=lambda relation: relation.created_at, reverse=True)
        return tuple(matches[:limit])

    def list_by_source_memory_ids(
        self,
        source_memory_ids,
    ) -> tuple[MemoryRelationRecord, ...]:
        if not source_memory_ids:
            return ()

        matches = [
            relation
            for relation in self._relations
            if relation.source_memory_id in source_memory_ids
        ]
        matches.sort(key=lambda relation: relation.created_at, reverse=True)
        return tuple(matches)

    def list_by_target_memory_id(
        self,
        target_memory_id,
        *,
        limit: int,
    ) -> tuple[MemoryRelationRecord, ...]:
        matches = [
            relation
            for relation in self._relations
            if relation.target_memory_id == target_memory_id
        ]
        matches.sort(key=lambda relation: relation.created_at, reverse=True)
        return tuple(matches[:limit])


def test_memory_relation_repository_contract_supports_create_and_directional_reads() -> None:
    source_memory_id = uuid4()
    target_memory_id = uuid4()
    other_memory_id = uuid4()
    created_at = datetime(2024, 10, 15, tzinfo=UTC)

    repository = InMemoryMemoryRelationRepository()

    older_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        metadata={"kind": "older"},
        created_at=created_at.replace(hour=1),
    )
    newer_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=other_memory_id,
        relation_type="related_to",
        metadata={"kind": "newer"},
        created_at=created_at.replace(hour=2),
    )
    incoming_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=other_memory_id,
        target_memory_id=target_memory_id,
        relation_type="references",
        metadata={"kind": "incoming"},
        created_at=created_at.replace(hour=3),
    )

    assert repository.create(older_relation) is older_relation
    assert repository.create(newer_relation) is newer_relation
    assert repository.create(incoming_relation) is incoming_relation

    assert repository.relations == (
        older_relation,
        newer_relation,
        incoming_relation,
    )

    assert repository.list_by_source_memory_id(
        source_memory_id,
        limit=10,
    ) == (
        newer_relation,
        older_relation,
    )
    assert repository.list_by_target_memory_id(
        target_memory_id,
        limit=10,
    ) == (
        incoming_relation,
        older_relation,
    )

    assert repository.list_by_source_memory_id(source_memory_id, limit=1) == (newer_relation,)
    assert repository.list_by_source_memory_ids(
        (
            source_memory_id,
            other_memory_id,
        )
    ) == (
        incoming_relation,
        newer_relation,
        older_relation,
    )
    assert repository.list_by_source_memory_ids(()) == ()
    assert repository.list_by_target_memory_id(target_memory_id, limit=1) == (incoming_relation,)
