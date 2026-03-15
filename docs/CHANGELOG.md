# Changelog

All notable changes to `ctxledger` are documented in this file.

The project currently follows a lightweight, human-maintained changelog style.

---

## [Unreleased]

- No unreleased entries yet.

## [0.3.0] - 2026-03-14

### Added

- implemented `memory_search` as an initial hybrid lexical and embedding-backed retrieval surface over stored memory items
- hybrid ranking that combines lexical matches with embedding similarity for memory item search results
- ranking explanation details in `memory_search` results, including lexical component, semantic component, score mode, and semantic-only discount reporting
- embedding configuration and generation scaffolding for `disabled`, `local_stub`, `openai`, `voyageai`, `cohere`, and `custom_http` provider modes
- PostgreSQL-backed memory embedding persistence and pgvector-backed similarity lookup for memory item retrieval
- MCP handler, schema, and serialization support for `memory_search`
- unit, server, MCP handler, and PostgreSQL integration coverage for the implemented `0.3.0` memory search path

### Notes

- `memory_search` now uses the active hybrid lexical and embedding-backed retrieval path over stored memory items
- validated embedding execution paths now include `openai` in addition to `local_stub` and `custom_http`
- OpenAI embedding generation was validated end-to-end against PostgreSQL persistence and semantic retrieval
- `voyageai` and `cohere` configuration surfaces exist, but their full provider-specific runtime support remains incomplete
- `memory_get_context` remains primarily episode-oriented in `0.3.0`; richer multi-layer and relation-aware context assembly remain future work

## [0.2.0] - 2026-03-14

### Added

- episodic memory capture through `memory_remember_episode`, including:
  - append-only episode recording
  - `workflow_instance_id` validation
  - optional `attempt_id` validation
  - workflow existence validation
  - canonical persistence of `attempt_id` when provided
- initial episode-oriented auxiliary context retrieval through `memory_get_context`, including:
  - direct retrieval by `workflow_instance_id`
  - workflow-linked expansion by `workspace_id`
  - workflow-linked expansion by `ticket_id`
  - `limit`
  - `include_episodes`
  - initial lightweight query-aware filtering over episode summary text and explicit metadata fields
  - explicit response details covering:
    - `query`
    - `normalized_query`
    - `lookup_scope`
    - `workspace_id`
    - `workflow_instance_id`
    - `ticket_id`
    - `limit`
    - `include_episodes`
    - `include_memory_items`
    - `include_summaries`
    - `resolved_workflow_count`
    - `resolved_workflow_ids`
    - `query_filter_applied`
    - `episodes_before_query_filter`
    - `matched_episode_count`
    - `episodes_returned`
- PostgreSQL-backed episodic memory persistence and episode-oriented context retrieval
- PostgreSQL integration coverage for episodic memory and `memory_get_context`
- local/operator-facing HTTPS deployment paths for MCP access, including:
  - authenticated HTTPS proxy path on `https://localhost:8443/mcp`
  - no-auth HTTPS proxy path on `https://localhost:8444/mcp`
  - local certificate setup guidance for Traefik-based TLS termination
  - HTTPS smoke validation support for local self-signed or untrusted certificates
- verified local Zed startup guidance for both no-auth and auth HTTPS MCP configurations

### Changed

- local/operator-facing guidance now treats HTTPS proxy access as the recommended public MCP path
- the backend application service is no longer documented as a host-exposed direct local MCP endpoint
- small-auth public access now uses HTTPS on `8443`, replacing the older public HTTP path
- the base compose backend is now private to the compose network instead of being host-exposed on `8080`
- README, deployment guidance, security guidance, MCP API docs, contributing guidance, and runbooks now align with the `0.2.0` episodic-memory and HTTPS-first operator posture

### Notes

- `memory_search` remained intentionally stubbed in `0.2.0` and was deferred to later semantic retrieval work
- `memory_get_context` remains intentionally partial and episode-oriented in `0.2.0`; broader semantic, hierarchical, and relation-aware retrieval remain future work
- `0.2.0` closes out the episodic memory milestone and establishes an HTTPS-enabled MCP deployment path after that memory closeout work