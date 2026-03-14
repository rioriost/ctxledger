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
  - still-stubbed `memory_search`
- `memory_search` does not need to be implemented for `0.2.0`
  - semantic retrieval remains a `0.3` concern
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

Planned focus:

- pgvector semantic search
- reusable semantic/procedural memory retrieval
- stronger relevance ranking for context assembly

Expected primary tool fit:

- `memory_search`
- richer `memory_get_context` relevance-based retrieval

Current note:

- `memory_search` is still stubbed

## 0.4

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

- finish the remaining memory-focused `0.2` closeout work first
- keep the documented `memory_get_context` details contract aligned with the implemented episode-oriented `0.2.0` scope
- clarify the intended meaning difference between `matched_episode_count` and `episodes_returned`
- shift the lightweight query filter toward explicit field-based matching over summary text plus metadata keys/values
- refresh README and API docs to reflect the current memory tool reality
- add HTTPS / TLS planning and implementation work for the proxy-facing MCP endpoint after the memory workstream
- keep `0.1.0` as the current version until explicit `0.2.0` criteria are met

## 0.0

Foundation themes:

- stable runtime
- durable persistence
- explicit operational state