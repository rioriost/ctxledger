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
- close out the refactoring wave with a stable foundation for hierarchical memory work in `0.6.0`

Expected themes:

- identify duplicate logic within individual files first
- extract or reorganize repeated code paths inside the same module before broader moves
- identify duplication across modules only after file-local cleanup is stable
- improve internal boundaries, naming, helper placement, and reuse
- preserve current behavior through incremental, test-backed refactoring
- avoid release claims that depend on new product features rather than structural cleanup
- prepare the codebase and persistence layer for graph-assisted hierarchical retrieval in `0.6.0`

## 0.5.1

Planned focus:

- PostgreSQL connection pooling with `psycopg-pool`
- runtime hardening for PostgreSQL-backed workflow and memory operations
- reduction of per-request connection churn without changing canonical behavior
- alignment of implementation with the documented process model
- a safer database access foundation before beginning broader `0.6.0` work

Current progress already landed toward `0.5.1`:

- PostgreSQL unit-of-work construction now requires an explicit shared connection pool instead of silently creating ad hoc pools
- `PostgresUnitOfWork` is pool-backed and borrows connections from a shared pool for transaction-scoped use
- server bootstrap, CLI bootstrap, and runtime factory paths have been refactored toward explicit shared-pool ownership
- CLI PostgreSQL command paths now create and close shared pools explicitly
- server/runtime bootstrap wiring was corrected so the HTTP/runtime path initializes a real workflow service again instead of remaining `server_not_ready`
- debug-level stage timing was added to `WorkflowService.resume_workflow()` for workflow, workspace, attempt, checkpoint, verify-report, projection, and projection-failure lookup stages
- targeted PostgreSQL indexes were added for resume-related verify-report and projection-failure lookup patterns
- helper, CLI, server, and coverage-target tests were updated to reflect the new pool ownership rules

Current `0.5.1` positioning:

- the current local CLI and HTTP/runtime resume paths both succeed for the latest inspected workflow
- the original `workflow_resume` timeout that motivated this milestone is not currently reproduced in the latest local checks
- the latest investigation suggests at least one earlier failure mode was bootstrap/runtime wiring related rather than purely query complexity
- connection pooling and runtime hardening still remain valid `0.5.1` work because they improve ownership clarity, reduce hidden pool churn, and provide a better base for future timeout diagnosis

Remaining work to close out `0.5.1` more confidently:

- ensure the latest schema/index changes are applied on the actual target databases, not just captured in `schemas/postgres.sql`
- continue validating pool lifecycle discipline across server, CLI, and any remaining runtime/bootstrap paths
- decide whether any remaining factory-created pools need more explicit ownership or shutdown coordination
- investigate whether the original timeout depends on:
  - a different workflow instance
  - a different database state
  - a different transport or context-server timeout budget
  - a cold-start/bootstrap path rather than steady-state resume lookup behavior
- keep focused workflow and PostgreSQL integration validation green after any further runtime or schema adjustments

Expected themes:

- shared PostgreSQL pool ownership for long-lived runtime processes
- pooled connection acquisition through the existing unit-of-work boundary
- explicit pool-related configuration and validation
- preservation of current workflow and memory semantics
- focused validation for transaction behavior, cleanup, and regression safety
- runtime/bootstrap correctness for both CLI and HTTP-driven resume behavior

## 0.5.2

Planned focus:

- `workflow_resume` timeout hardening and root-cause reduction
- safer resume/recovery behavior for AI agents that follow repository `.rules`
- stronger distinction between `workspace_id` and `workflow_instance_id` at tool and docs boundaries
- operational diagnosis for resume-path stalls, blocking queries, and transport timeout mismatches
- close the gap between canonical workflow guidance and practical agent/tool usage

Expected themes:

- make `workflow_resume` fail fast and clearly when the wrong identifier type is supplied
- reduce the chance that resume-related requests block long enough to hit context-server timeouts
- improve observability around resume-stage timing, pool waits, and query hotspots
- review whether `.rules` wording unintentionally nudges agents toward incorrect `workflow_resume` usage
- document a safer agent workflow that prefers the correct identifier source and fallback path when resumption is ambiguous
- preserve canonical workflow semantics while making misuse and degraded states easier to diagnose
- keep this as a targeted hardening release rather than a broad feature expansion

Current investigation framing:

- recent timeout reports show `workspace_register` responding while `workflow_resume` times out, which suggests the server is reachable but the resume path can still block
- at least one observed client call appears to have passed a `workspace_id` to `workflow_resume`, even though the tool expects a `workflow_instance_id`
- because `ctxledger` tools are commonly invoked by AI agents that read repository `.rules`, guidance quality in `.rules` is part of the problem space and should be treated as potentially causal rather than merely advisory
- the current resume path performs synchronous, multi-step PostgreSQL-backed resume assembly, so pool waits, blocking queries, or transport timeout budget mismatches remain relevant suspects even when agent misuse is also present

Likely workstreams for `0.5.2`:

- tool-surface and service hardening for incorrect identifier usage
- `.rules` guidance refinement for resume/start decision-making and identifier selection
- targeted resume-path observability and timeout-budget diagnosis
- selective query/index/runtime review for resume-related lookup stages
- documentation updates that make the correct operational flow obvious for both humans and agent-driven tool callers

Success shape for `0.5.2`:

- AI agents following `.rules` are less likely to call `workflow_resume` with a `workspace_id`
- incorrect resume calls produce clearer, faster failure behavior instead of opaque timeouts where possible
- resume-path diagnostics are explicit enough to distinguish:
  - wrong identifier usage
  - bootstrap/runtime readiness issues
  - connection-pool acquisition delays
  - slow or blocking database lookups
  - upstream context-server timeout limits
- docs and roadmap guidance reflect that reliability can depend on both implementation hardening and better agent-facing operational instructions

## 0.6

Planned focus:

- hierarchical memory retrieval
- summary layers
- relation-aware context assembly
- more multi-layer `memory_get_context` behavior
- PostgreSQL + Apache AGE as a foundation for graph-assisted hierarchical memory
- Cypher-assisted traversal and retrieval support where it improves hierarchical memory implementation

Expected themes:

- hierarchical summaries
- memory item relations
- cross-episode recall
- project-level knowledge compression
- graph-backed relation modeling while PostgreSQL remains canonical
- incremental introduction of Apache AGE without turning the milestone into a broad architecture rewrite

## Cross-version guiding rules

- PostgreSQL remains the canonical system of record
- repository projections remain derived artifacts
- workflow control and memory retrieval stay separate
- resumability and recoverability are prioritized over thin feature claims
- version should not be bumped until implementation and docs meaningfully match the claimed scope
- graph capabilities should be introduced to support memory behavior, not to replace PostgreSQL as the canonical source of truth

## Immediate next steps

- finish `0.5.1` closeout work for PostgreSQL connection pooling and runtime hardening
- confirm that the latest resume-related schema/index additions are applied in the intended runtime databases
- keep refining pool ownership boundaries for server and CLI bootstrap paths where lifecycle ambiguity remains
- continue validating behavior preservation across workflow and memory paths, especially HTTP/runtime resume behavior
- investigate any remaining `workflow_resume` timeout only if it can be reproduced under a specific workflow, database state, or transport budget
- resume `0.6.0` hierarchical memory implementation after the pooling hardening step is considered sufficiently closed
- keep Mnemis-alignment work out of `0.6.0`

## 0.7

Planned focus:

- evaluate whether ctxledger should move closer to a Mnemis-style hierarchical graph memory design
- compare ctxledger’s `0.6.0` implementation against Mnemis-style dual-route retrieval ideas
- decide whether any architectural alignment is justified after `0.6.0` is working

Expected themes:

- review Mnemis as a design input, not a `0.6.0` implementation constraint
- compare relation modeling, hierarchy construction, and retrieval strategy
- evaluate whether dual-route retrieval concepts should influence later ctxledger versions
- keep any Mnemis-driven redesign scoped to explicit post-`0.6.0` work

## 0.0

Foundation themes:

- stable runtime
- durable persistence
- explicit operational state