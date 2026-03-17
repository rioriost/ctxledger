"""Pure helper functions used by the memory subsystem.

These helpers are intentionally side-effect free and independent from repository
implementations or service orchestration logic so they can be reused across
memory service slices and tested in isolation.
"""

from __future__ import annotations

from typing import Any


def normalize_query_text(value: str | None) -> str | None:
    """Normalize optional query text for case-insensitive matching."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized.casefold() if normalized else None


def query_tokens(normalized_query: str | None) -> tuple[str, ...]:
    """Split normalized query text into non-empty tokens."""
    if normalized_query is None:
        return ()

    return tuple(token for token in normalized_query.split() if token)


def text_matches_query(
    *,
    text: str,
    normalized_query: str,
    query_tokens_value: tuple[str, ...],
) -> bool:
    """Return whether text matches the normalized query or all query tokens."""
    normalized_text = text.casefold()
    if normalized_query in normalized_text:
        return True
    return bool(query_tokens_value) and all(
        token in normalized_text for token in query_tokens_value
    )


def metadata_query_strings(metadata: dict[str, Any]) -> tuple[str, ...]:
    """Flatten metadata into casefolded key/value strings for lightweight matching."""
    query_strings: list[str] = []

    for key, value in metadata.items():
        query_strings.append(str(key).casefold())
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value:
                query_strings.append(normalized_value.casefold())
        else:
            query_strings.append(str(value).casefold())

    return tuple(query_strings)


def embedding_dot_product(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    """Return a safe dot product for equal-length embedding vectors."""
    if len(left) != len(right):
        return 0.0

    return sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=False)
    )
