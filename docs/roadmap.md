# ctxledger roadmap

## 0.1

Primary delivery focus:

- workflow kernel
- workspace registry
- MCP tool surface basics
- PostgreSQL-backed canonical workflow state
- HTTP MCP serving at `/mcp`

Status notes:

- workflow lifecycle operations are implemented:
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `workflow_complete`
- projection failure tracking and resolution/ignore flows are implemented
- workflow resources are available for:
  - `workspace://{workspace_id}/resume`
  - `workspace://{workspace_id}/workflow/{workflow_instance_id}`

## 0.2

Primary delivery focus:

- episodic memory
- initial reusable memory capture
- early auxiliary context retrieval
- TLS-enabled MCP deployment path after memory closeout

Current progress already landed toward `0.2`:

- `memory_remember_episode` is implemented
  - append-only episode recording
  - `workflow_instance_id` validation
  - optional `attempt_id` validation
  - workflow existence validation
  - canonical persistence of `attempt_id` when provided
- `memory_get_context` is partially implemented
  - initial episode-oriented retrieval path
  - direct `workflow_instance_id` lookup
  - service-side workflow expansion paths for `workspace_id` and `ticket_id`
  - `limit` support
  - `include_episodes` support
  - initial query-aware filtering over episode summary / metadata text
  - richer response details for lookup and filtering observability
- PostgreSQL-backed episode persistence is implemented
- PostgreSQL-backed episode-oriented context retrieval is implemented
- multiple episodes per workflow are supported
- PostgreSQL integration coverage now includes episodic memory and episode-oriented context retrieval

Proposed `0.2.0` memory closeout criteria:

- `memory_remember_episode` remains implemented and stable for append-only episodic recording
  - `workflow_instance_id` validation is covered
  - optional `attempt_id` validation is covered
  - `attempt_id` persistence is canonical in PostgreSQL
- `memory_get_context` remains intentionally partial, but is considered sufficient for `0.2.0` when it reliably supports:
  - direct retrieval by `workflow_instance_id`
  - workflow-linked expansion by `workspace_id`
  - workflow-linked expansion by `ticket_id`
  - `limit`
  - `include_episodes`
  - initial query-aware filtering against episode summary / metadata text
- `memory_get_context` response details should be explicit enough to explain what the service actually did
  - the current working `0.2.0` detail contract should include:
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
- unit and PostgreSQL integration coverage should continue to prove the supported `0.2.0` memory behavior
- docs should continue to distinguish clearly between:
  - implemented episodic capture
  - partially implemented episode-oriented context retrieval
  - not-yet-required `0.3.0` semantic retrieval work beyond the initial `memory_search` surface
- `memory_search` did not need to be implemented for `0.2.0`
  - broader semantic retrieval remained a `0.3` concern
  - hierarchical memory remains a later concern

Remaining work to close out `0.2` more confidently:

- continue hardening `memory_get_context` response quality around the now-documented `0.2.0` details contract
- clarify the semantic distinction between:
  - `matched_episode_count`
  - `episodes_returned`
- move the current lightweight query filter away from whole-metadata stringification and toward a more explicit field-based behavior for:
  - episode summary text
  - metadata keys
  - metadata values
- document the exact `0.2.0` lightweight filtering boundary so it stays clearly distinct from later semantic retrieval work
- update docs and API descriptions so they match the actual implementation state
- add a TLS / HTTPS deployment workstream after the memory closeout work:
  - proxy-side TLS termination for the MCP endpoint
  - local operator guidance for certificate handling
  - authenticated MCP client compatibility over HTTPS
  - clear separation between local plain-HTTP development mode and HTTPS-oriented deployment mode

## 0.3

Primary delivery focus:

- initial pgvector-backed semantic search
- reusable semantic/procedural memory retrieval foundations
- stronger relevance ranking for context assembly

Current progress already landed toward `0.3`:

- `memory_search` is implemented
  - hybrid lexical and embedding-backed ranking over stored memory items
  - workspace-scoped retrieval over persisted memory items
  - explicit ranking details including lexical and semantic components
  - response metadata covering search mode, semantic candidate counts, and hybrid scoring configuration
- embedding configuration and generator scaffolding are implemented
  - provider selection for `disabled`, `local_stub`, `openai`, `voyageai`, `cohere`, and `custom_http`
  - deterministic local stub embeddings for development and test coverage
  - generic `custom_http` execution support for external embedding generation
- PostgreSQL-backed memory embedding persistence is implemented
- PostgreSQL-backed similarity lookup for memory embeddings is implemented
- MCP schema, handler wiring, serialization, and integration coverage now include `memory_search`

Current `0.3.0` positioning:

- validated embedding execution paths now include `openai` in addition to `local_stub` and `custom_http`
- `voyageai` and `cohere` configuration surfaces exist, but their full provider-specific runtime integrations remain incomplete
- `memory_get_context` remains primarily an episode-oriented retrieval surface from `0.2.0`, not yet a richer multi-layer relevance assembly path

Remaining work to close out `0.3` more confidently:

- align remaining operator-facing docs with the current `memory_search` and embedding-support surface
- decide the exact `0.3.0` release boundary for provider-specific embedding integrations beyond the already validated OpenAI path
- clarify which semantic retrieval behaviors are considered in-scope for `0.3.0` versus later iterative releases
- continue improving relevance tuning and explanation quality without overstating retrieval guarantees
- defer broader hierarchical and relation-aware retrieval expansion to later milestones

## 0.4

Planned focus:

- workflow and memory observability
- operator-facing CLI inspection tools
- optional deployable Grafana-based dashboard support
- better runtime visibility into canonical workflow and memory state

Expected themes:

- CLI status / stats views for workflow activity
- CLI views for memory, embedding, and failure state
- dashboard-oriented Grafana deployment as an optional surface
- stronger operator insight into durable runtime health and usage patterns

## 0.5

Planned focus:

- targeted refactoring across `src/` and `tests/`
- file-by-file consolidation of duplicated logic and overlapping responsibilities
- cross-file consolidation of duplicated logic, helper behavior, and reusable patterns
- reduction of maintenance overhead without changing externally expected behavior
- safer internal structure to support later feature work

Expected themes:

- identify duplicate logic within individual files first
- extract or reorganize repeated code paths inside the same module before broader moves
- identify duplication across modules only after file-local cleanup is stable
- improve internal boundaries, naming, helper placement, and reuse
- preserve current behavior through incremental, test-backed refactoring
- avoid release claims that depend on new product features rather than structural cleanup

## 0.6

Planned focus:

- hierarchical memory retrieval
- summary layers
- relation-aware context assembly
- more multi-layer `memory_get_context` behavior

Expected themes:

- hierarchical summaries
- memory item relations
- cross-episode recall
- project-level knowledge compression

## Cross-version guiding rules

- PostgreSQL remains the canonical system of record
- repository projections remain derived artifacts
- workflow control and memory retrieval stay separate
- resumability and recoverability are prioritized over thin feature claims
- version should not be bumped until implementation and docs meaningfully match the claimed scope

## Immediate next steps

- create and document a `0.5.0` refactoring plan focused on preserving current behavior while improving internal structure
- start with file-local duplication review across `src/` and `tests/`
- follow with cross-file duplication review only after file-local cleanup candidates are identified
- define refactoring sequencing, safety rules, and validation expectations before broad code movement
- keep the `0.6.0` hierarchical retrieval scope clearly deferred while `0.5.0` is dedicated to refactoring

## 0.0

Foundation themes:

- stable runtime
- durable persistence
- explicit operational state