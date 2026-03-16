# Changelog

All notable changes to `ctxledger` are documented in this file.

The project currently follows a lightweight, human-maintained changelog style.

---

## [Unreleased]

- planned `0.5.4` follow-up hardening work for `workflow_resume` timeout diagnosis and mitigation
- roadmap/docs updates are being prepared for:
  - timeout-aware resume-path hardening
  - clearer workflow-versus-workspace identifier guidance
  - AI-agent-facing `.rules` guidance improvements to reduce incorrect `workflow_resume` usage
  - validation of whether rule/guidance changes can prevent a meaningful share of observed timeout-triggering misuse

## [0.4.0] - 2026-03-16

### Added

- operator-facing observability CLI commands:
  - `ctxledger stats`
  - `ctxledger workflows`
  - `ctxledger memory-stats`
  - `ctxledger failures`
- text and `--format json` output support for the observability CLI surfaces
- canonical workflow aggregation and listing support for observability reporting across in-memory and PostgreSQL repositories
- canonical memory statistics reporting, including:
  - episode count
  - memory item count
  - memory embedding count
  - memory relation count
  - provenance breakdown
  - latest activity timestamps
- canonical failure inspection reporting, including:
  - failure scope/type
  - lifecycle state
  - target path
  - error code and message
  - occurred/resolved timestamps
  - retry count
  - open failure count
  - attempt id when present
- optional Grafana deployment support for runtime observability, including:
  - Compose overlay support
  - datasource provisioning
  - dashboard provisioning
  - initial runtime, memory, and failure dashboards
- observability SQL bootstrap views for PostgreSQL-backed dashboarding
- Grafana operator runbook and expanded deployment guidance for read-only PostgreSQL observability access

### Changed

- the `0.4.0` milestone is now defined around observability rather than hierarchical retrieval
- README quick start was rewritten to be more user-first and self-contained for local startup, MCP access, and Grafana bring-up
- user-facing quick-start guidance now consistently favors `localhost` examples
- stale test expectations were aligned to the active `0.4.0` version across CLI, config, and server validation paths
- Grafana dashboards were polished with clearer operator-facing labels, improved legends, and timestamp-only field overrides to prevent `NaN` and epoch-like misrendering in mixed-value tables

### Validation

- focused coverage-target suite passed:
  - `python -m pytest tests/test_coverage_targets.py -q`
  - `237 passed`
- full test suite passed:
  - `python -m pytest -q`
  - `799 passed, 1 skipped`

### Notes

- the single skipped test remains expected because real OpenAI integration requires `OPENAI_API_KEY`
- `memory_search` is now reported as available in `0.4.0` in the current runtime-visible payloads
- the strongest validated embedding/runtime paths remain:
  - `openai`
  - `local_stub`
  - `custom_http`
- `voyageai` and `cohere` configuration surfaces still exist, but full provider-specific runtime support remains incomplete
- hierarchical memory retrieval remains deferred to `0.5.0`

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
- the roadmap now treats `0.4.0` as the observability milestone for operator-facing CLI inspection and optional deployable Grafana-based dashboard support
- hierarchical memory retrieval and summary-layer expansion are planned later in `0.5.0`

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
- `memory_get_context` remains intentionally partial and episode-oriented in `0.2.0`; broader semantic, relation-aware, and later hierarchical retrieval remain future work
- `0.2.0` closes out the episodic memory milestone and establishes an HTTPS-enabled MCP deployment path after that memory closeout work