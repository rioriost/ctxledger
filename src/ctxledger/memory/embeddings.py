from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from ..config import EmbeddingProvider, EmbeddingSettings


class EmbeddingGenerationError(RuntimeError):
    """Raised when embedding generation fails."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.details = details or {}


@dataclass(slots=True, frozen=True)
class EmbeddingRequest:
    """Input payload for embedding generation."""

    text: str
    model: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class EmbeddingResult:
    """Generated embedding payload."""

    provider: str
    model: str
    vector: tuple[float, ...]
    content_hash: str


class EmbeddingGenerator(Protocol):
    """Provider-agnostic embedding generation contract."""

    def generate(self, request: EmbeddingRequest) -> EmbeddingResult: ...


def build_embedding_generator(settings: EmbeddingSettings) -> EmbeddingGenerator:
    """Build an embedding generator from application settings."""

    if not settings.enabled or settings.provider is EmbeddingProvider.DISABLED:
        return DisabledEmbeddingGenerator()

    if settings.provider is EmbeddingProvider.LOCAL_STUB:
        return LocalStubEmbeddingGenerator(
            model=settings.model,
            dimensions=settings.dimensions or 16,
        )

    if settings.provider is EmbeddingProvider.OPENAI:
        return ExternalAPIEmbeddingGenerator(
            provider=settings.provider,
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url or "https://api.openai.com/v1",
        )

    if settings.provider is EmbeddingProvider.VOYAGEAI:
        return ExternalAPIEmbeddingGenerator(
            provider=settings.provider,
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url or "https://api.voyageai.com/v1",
        )

    if settings.provider is EmbeddingProvider.COHERE:
        return ExternalAPIEmbeddingGenerator(
            provider=settings.provider,
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url or "https://api.cohere.com/v1",
        )

    if settings.provider is EmbeddingProvider.CUSTOM_HTTP:
        return ExternalAPIEmbeddingGenerator(
            provider=settings.provider,
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url or "",
        )

    raise EmbeddingGenerationError(
        "Unsupported embedding provider configuration.",
        provider=str(settings.provider),
        details={"provider": str(settings.provider)},
    )


class DisabledEmbeddingGenerator:
    """Embedding generator used when embedding generation is disabled."""

    def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
        raise EmbeddingGenerationError(
            "Embedding generation is disabled.",
            provider=EmbeddingProvider.DISABLED.value,
            details={"text_length": len(request.text)},
        )


@dataclass(slots=True)
class LocalStubEmbeddingGenerator:
    """Deterministic local embedding generator for development and tests."""

    model: str
    dimensions: int = 16

    def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
        normalized_text = _normalize_text(request.text)
        if not normalized_text:
            raise EmbeddingGenerationError(
                "Embedding text must be a non-empty string.",
                provider=EmbeddingProvider.LOCAL_STUB.value,
                details={"field": "text"},
            )

        content_hash = compute_content_hash(normalized_text, request.metadata)
        vector = _hash_to_vector(content_hash, dimensions=self.dimensions)
        return EmbeddingResult(
            provider=EmbeddingProvider.LOCAL_STUB.value,
            model=request.model or self.model,
            vector=vector,
            content_hash=content_hash,
        )


@dataclass(slots=True)
class ExternalAPIEmbeddingGenerator:
    """HTTP-backed embedding generator for external providers."""

    provider: EmbeddingProvider
    model: str
    api_key: str | None
    base_url: str

    def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
        normalized_text = _normalize_text(request.text)
        if not normalized_text:
            raise EmbeddingGenerationError(
                "Embedding text must be a non-empty string.",
                provider=self.provider.value,
                details={"field": "text"},
            )

        if not self.api_key:
            raise EmbeddingGenerationError(
                "Embedding API key is not configured.",
                provider=self.provider.value,
                details={"field": "api_key"},
            )

        target_model = request.model or self.model
        content_hash = compute_content_hash(normalized_text, request.metadata)

        if self.provider is EmbeddingProvider.CUSTOM_HTTP:
            return self._generate_custom_http(
                text=normalized_text,
                model=target_model,
                metadata=request.metadata,
                content_hash=content_hash,
            )

        raise EmbeddingGenerationError(
            (
                "External embedding provider integration is not implemented yet. "
                "Use the local stub provider for now or configure the custom_http "
                "provider for a generic HTTP embedding endpoint."
            ),
            provider=self.provider.value,
            details={
                "provider": self.provider.value,
                "model": target_model,
                "base_url": self.base_url,
            },
        )

    def _generate_custom_http(
        self,
        *,
        text: str,
        model: str,
        metadata: dict[str, Any] | None,
        content_hash: str,
    ) -> EmbeddingResult:
        payload = {
            "text": text,
            "model": model,
            "metadata": _stable_metadata(metadata),
        }

        raw_response = self._post_json(
            url=self.base_url,
            payload=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        embedding = _extract_embedding_vector(raw_response)

        return EmbeddingResult(
            provider=self.provider.value,
            model=_extract_response_model(raw_response, default=model),
            vector=embedding,
            content_hash=content_hash,
        )

    def _post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> Any:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        request_obj = urllib_request.Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib_request.urlopen(request_obj) as response:
                raw_body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise EmbeddingGenerationError(
                "Embedding provider request failed.",
                provider=self.provider.value,
                details={
                    "status_code": exc.code,
                    "base_url": self.base_url,
                    "response_body": response_body,
                },
            ) from exc
        except urllib_error.URLError as exc:
            raise EmbeddingGenerationError(
                "Embedding provider request could not be completed.",
                provider=self.provider.value,
                details={
                    "base_url": self.base_url,
                    "reason": str(exc.reason),
                },
            ) from exc

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise EmbeddingGenerationError(
                "Embedding provider returned invalid JSON.",
                provider=self.provider.value,
                details={
                    "base_url": self.base_url,
                    "response_body": raw_body,
                },
            ) from exc


def _extract_embedding_vector(payload: Any) -> tuple[float, ...]:
    if not isinstance(payload, dict):
        raise EmbeddingGenerationError(
            "Embedding provider returned an invalid response payload.",
            provider=EmbeddingProvider.CUSTOM_HTTP.value,
            details={"field": "response"},
        )

    candidates = [
        payload.get("embedding"),
        payload.get("vector"),
    ]

    data = payload.get("data")
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict):
            candidates.extend(
                [
                    first_item.get("embedding"),
                    first_item.get("vector"),
                ]
            )

    for candidate in candidates:
        vector = _normalize_embedding_vector(candidate)
        if vector is not None:
            return vector

    raise EmbeddingGenerationError(
        "Embedding provider response did not contain a usable embedding vector.",
        provider=EmbeddingProvider.CUSTOM_HTTP.value,
        details={"field": "embedding"},
    )


def _extract_response_model(payload: Any, *, default: str) -> str:
    if not isinstance(payload, dict):
        return default

    direct_model = payload.get("model")
    if isinstance(direct_model, str) and direct_model.strip():
        return direct_model.strip()

    data = payload.get("data")
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict):
            nested_model = first_item.get("model")
            if isinstance(nested_model, str) and nested_model.strip():
                return nested_model.strip()

    return default


def _normalize_embedding_vector(value: Any) -> tuple[float, ...] | None:
    if not isinstance(value, list) or not value:
        return None

    normalized: list[float] = []
    for item in value:
        if not isinstance(item, int | float):
            return None
        normalized.append(float(item))

    return tuple(normalized)


def compute_content_hash(text: str, metadata: dict[str, Any] | None = None) -> str:
    """Compute a stable content hash for embedding deduplication."""

    normalized_text = _normalize_text(text)
    payload = {
        "text": normalized_text,
        "metadata": _stable_metadata(metadata),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _stable_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    return dict(metadata)


def _hash_to_vector(content_hash: str, *, dimensions: int) -> tuple[float, ...]:
    if dimensions <= 0:
        raise EmbeddingGenerationError(
            "Embedding dimensions must be greater than 0.",
            provider=EmbeddingProvider.LOCAL_STUB.value,
            details={"dimensions": dimensions},
        )

    raw_bytes = bytes.fromhex(content_hash)
    values: list[float] = []
    index = 0

    while len(values) < dimensions:
        current = raw_bytes[index % len(raw_bytes)]
        values.append((current / 255.0) * 2.0 - 1.0)
        index += 1

    return tuple(values)


__all__ = [
    "DisabledEmbeddingGenerator",
    "EmbeddingGenerationError",
    "EmbeddingGenerator",
    "EmbeddingRequest",
    "EmbeddingResult",
    "ExternalAPIEmbeddingGenerator",
    "LocalStubEmbeddingGenerator",
    "build_embedding_generator",
    "compute_content_hash",
]
