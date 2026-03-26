from __future__ import annotations

from typing import Any
from uuid import UUID

from .protocols import (
    MemoryRelationMemoryItemLookupRepository,
    MemoryRelationSupportsTargetLookupRepository,
)
from .types import MemoryItemRecord, MemoryRelationRecord


class RelationContextMixin:
    """Relation and graph context helpers for ``MemoryService``.

    This mixin extracts relation-focused helper methods without changing the
    existing ``MemoryService`` state contract. The consuming class is expected
    to provide:

    - ``self._memory_item_repository``
    - ``self._memory_relation_repository``
    - ``self._serialize_memory_item``
    """

    def _collect_graph_summary_related_memory_items(
        self,
        *,
        memory_item_details: tuple[dict[str, Any], ...],
        limit: int,
    ) -> tuple[MemoryItemRecord, ...]:
        relation_repository = self._memory_relation_repository
        if relation_repository is None:
            return ()

        graph_lookup = getattr(
            relation_repository,
            "list_distinct_summary_member_memory_ids_by_source_memory_ids",
            None,
        )
        if not callable(graph_lookup):
            return ()

        source_memory_ids: list[UUID] = []
        seen_source_memory_ids: set[UUID] = set()
        for detail in memory_item_details:
            for memory_item in detail.get("memory_items", ()):
                memory_id = getattr(memory_item, "memory_id", None)
                if memory_id is None or memory_id in seen_source_memory_ids:
                    continue
                seen_source_memory_ids.add(memory_id)
                source_memory_ids.append(memory_id)

        if not source_memory_ids:
            return ()

        try:
            graph_summary_member_memory_ids = graph_lookup(tuple(source_memory_ids))
        except Exception:
            return ()

        if not graph_summary_member_memory_ids:
            return ()

        direct_episode_memory_ids = {
            memory_item.memory_id
            for detail in memory_item_details
            for memory_item in detail.get("memory_items", ())
        }

        graph_summary_related_memory_items: list[MemoryItemRecord] = []
        seen_memory_ids = set(direct_episode_memory_ids)

        for member_memory_id in graph_summary_member_memory_ids:
            if member_memory_id in seen_memory_ids:
                continue

            member_memory_items = self._memory_item_repository.list_by_memory_ids(
                (member_memory_id,),
                limit=limit,
            )
            if not member_memory_items:
                continue

            for memory_item in member_memory_items:
                if memory_item.memory_id in seen_memory_ids:
                    continue
                seen_memory_ids.add(memory_item.memory_id)
                graph_summary_related_memory_items.append(memory_item)
                if len(graph_summary_related_memory_items) >= limit:
                    return tuple(graph_summary_related_memory_items)

        return tuple(graph_summary_related_memory_items)

    def _collect_supports_related_memory_items(
        self,
        *,
        memory_item_details: tuple[dict[str, Any], ...],
        limit: int,
        include_relation_metadata: bool = False,
    ) -> (
        tuple[MemoryItemRecord, ...]
        | tuple[tuple[MemoryItemRecord, ...], tuple[MemoryRelationRecord, ...]]
    ):
        if limit <= 0:
            if include_relation_metadata:
                return (), ()
            return ()

        if not isinstance(self._memory_item_repository, MemoryRelationMemoryItemLookupRepository):
            if include_relation_metadata:
                return (), ()
            return ()

        related_memory_items: list[MemoryItemRecord] = []
        related_relations: list[MemoryRelationRecord] = []
        seen_memory_ids: set[UUID] = set()
        source_memory_ids: list[UUID] = []

        for detail in memory_item_details:
            raw_memory_items = detail.get("memory_items")
            if not isinstance(raw_memory_items, list):
                continue

            for raw_memory_item in raw_memory_items:
                if not isinstance(raw_memory_item, dict):
                    continue

                raw_memory_id = raw_memory_item.get("memory_id")
                if not isinstance(raw_memory_id, str):
                    continue

                try:
                    source_memory_id = UUID(raw_memory_id)
                except ValueError:
                    continue

                source_memory_ids.append(source_memory_id)

        relations_by_source_memory_id: dict[UUID, tuple[MemoryRelationRecord, ...]] = {
            source_memory_id: () for source_memory_id in source_memory_ids
        }
        bulk_relations = self._memory_relation_repository.list_by_source_memory_ids(
            tuple(source_memory_ids)
        )
        for relation in bulk_relations:
            source_memory_id = relation.source_memory_id
            if source_memory_id not in relations_by_source_memory_id:
                continue
            relations_by_source_memory_id[source_memory_id] = relations_by_source_memory_id[
                source_memory_id
            ] + (relation,)

        supports_target_memory_ids: tuple[UUID, ...] = ()
        if isinstance(
            self._memory_relation_repository,
            MemoryRelationSupportsTargetLookupRepository,
        ):
            supports_target_memory_ids = self._memory_relation_repository.list_distinct_support_target_memory_ids_by_source_memory_ids(
                tuple(source_memory_ids)
            )

        if supports_target_memory_ids:
            for target_memory_id in supports_target_memory_ids:
                if target_memory_id in seen_memory_ids:
                    continue

                target_memory_items = self._memory_item_repository.list_by_memory_ids(
                    (target_memory_id,),
                    limit=limit,
                )
                if not target_memory_items:
                    continue

                target_memory_item = target_memory_items[0]
                seen_memory_ids.add(target_memory_item.memory_id)
                related_memory_items.append(target_memory_item)

                if include_relation_metadata:
                    matched_relation: MemoryRelationRecord | None = None
                    for source_memory_id in source_memory_ids:
                        relations = relations_by_source_memory_id.get(source_memory_id, ())
                        for relation in relations:
                            if relation.relation_type != "supports":
                                continue
                            if relation.target_memory_id != target_memory_item.memory_id:
                                continue
                            matched_relation = relation
                            break
                        if matched_relation is not None:
                            break

                    if matched_relation is not None:
                        related_relations.append(matched_relation)

                if len(related_memory_items) >= limit:
                    if include_relation_metadata:
                        return (
                            tuple(related_memory_items),
                            tuple(related_relations),
                        )
                    return tuple(related_memory_items)

            if include_relation_metadata:
                return tuple(related_memory_items), tuple(related_relations)
            return tuple(related_memory_items)

        for source_memory_id in source_memory_ids:
            relations = relations_by_source_memory_id.get(source_memory_id, ())

            for relation in relations:
                if relation.relation_type != "supports":
                    continue
                if relation.target_memory_id in seen_memory_ids:
                    continue

                target_memory_items = self._memory_item_repository.list_by_memory_ids(
                    (relation.target_memory_id,),
                    limit=limit,
                )
                if not target_memory_items:
                    continue

                target_memory_item = target_memory_items[0]

                seen_memory_ids.add(target_memory_item.memory_id)
                related_memory_items.append(target_memory_item)
                related_relations.append(relation)

                if len(related_memory_items) >= limit:
                    if include_relation_metadata:
                        return (
                            tuple(related_memory_items),
                            tuple(related_relations),
                        )
                    return tuple(related_memory_items)

        if include_relation_metadata:
            return tuple(related_memory_items), tuple(related_relations)
        return tuple(related_memory_items)


__all__ = ["RelationContextMixin"]
