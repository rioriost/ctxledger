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

## 0.5.3

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

## 0.6.0

Planned focus:

- hierarchical memory retrieval foundations
- canonical summary hierarchy and summary-membership persistence
- constrained Apache AGE-backed graph support under a derived, rebuildable boundary
- summary-first context assembly improvements in `memory_get_context`
- explicit summary build and validation flows for milestone closeout

Current progress already landed toward `0.6.0`:

- canonical relational summary persistence is implemented through:
  - `memory_summaries`
  - `memory_summary_memberships`
- in-memory and PostgreSQL summary and summary-membership repository paths are implemented
- `memory_get_context` now supports a first constrained summary-first retrieval path
  - canonical summaries are preferred when present and summaries are enabled
  - direct summary-member memory-item expansion is supported
  - episode-derived summary fallback remains available when canonical summaries are absent
  - grouped hierarchy-aware output remains the primary response surface
  - additive retrieval-route metadata explains primary and auxiliary context assembly
- constrained graph-backed support has been added for the current `0.6.0` slice
  - PostgreSQL remains the canonical system of record
  - Apache AGE state is treated as derived, supplementary, and rebuildable
  - graph usage is gated by capability and readiness checks
  - graph-backed summary-member lookup degrades to the relational path when unavailable or failing
- explicit summary build paths are implemented through:
  - `MemoryService.build_episode_summary(...)`
  - `ctxledger build-episode-summary`
- replace-or-rebuild behavior for matching episode summaries is implemented
- workflow-completion-oriented summary automation is implemented in a gated, non-fatal form
- focused service, transport, and PostgreSQL integration coverage already exists for:
  - summary-first retrieval
  - summary-member expansion
  - narrowed `include_episodes = false` shaping
  - derived graph-summary auxiliary behavior
- the current broad repository validation state for this slice is green

Current `0.6.0` positioning:

- the current milestone should be read as a bounded hierarchical memory slice rather than broad graph-first memory redesign
- the minimal implemented hierarchy remains:
  - `summary -> memory_item`
- summary ownership and summary-membership ownership remain canonical and relational
- Apache AGE currently serves as a constrained derived support layer, not canonical hierarchy truth
- `memory_get_context` is now hierarchy-aware in a narrow, explainable, behavior-preserving way
- the current request shape now includes a `primary_only` narrowing flag for clients that want the grouped primary surface without flatter compatibility-oriented explainability fields
- explicit bootstrap, refresh, readiness, and degraded-operation expectations matter as much as the retrieval behavior itself
- operator-facing stats now also surface canonical summary volume and derived graph-posture metrics, including:
  - `memory_summary_count`
  - `memory_summary_membership_count`
  - `age_summary_graph_ready_count`
  - `age_summary_graph_stale_count`
  - `age_summary_graph_degraded_count`
  - `age_summary_graph_unknown_count`

Remaining work to close out `0.6.0` more confidently:

- keep the roadmap, closeout notes, and operator-facing docs aligned with the now-implemented `0.6.0` boundary
- continue verifying that summary-first contract details remain stable across service, MCP, HTTP, and PostgreSQL-backed paths
- continue verifying that the `primary_only` client path remains a response-shaping mode over the same retrieval behavior rather than drifting into a separate retrieval contract
- confirm that operator metrics continue to reflect their intended current reading:
  - canonical summary volume first
  - derived graph posture second
- confirm that deliverables and validation notes consistently describe the current milestone as:
  - canonical relational summary ownership
  - constrained summary-first retrieval
  - direct member expansion
  - derived and degradable graph support
  - optional primary-surface-only client shaping through `primary_only`
- avoid broadening the milestone into recursive hierarchy, graph-owned truth, or Mnemis-alignment work before `0.7.0`

Expected themes:

- canonical-relational hierarchy ownership first
- compressed-then-expand retrieval through summary-first selection
- explicit and testable grouped response behavior
- derived graph support only where concretely justified
- operational clarity around bootstrap, readiness, refresh, and degraded fallback
- milestone closeout through validation and documentation consistency
- because `ctxledger` tools are commonly invoked by AI agents that read repository `.rules`, guidance quality in `.rules` is part of the problem space and should be treated as potentially causal rather than merely advisory
- the current resume path performs synchronous, multi-step PostgreSQL-backed resume assembly, so pool waits, blocking queries, or transport timeout budget mismatches remain relevant suspects even when agent misuse is also present

Likely workstreams for `0.5.3`:

- tool-surface and service hardening for incorrect identifier usage
- `.rules` guidance refinement for resume/start decision-making and identifier selection
- targeted resume-path observability and timeout-budget diagnosis
- selective query/index/runtime review for resume-related lookup stages
- documentation updates that make the correct operational flow obvious for both humans and agent-driven tool callers

Success shape for `0.5.3`:

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
- clearer separation between:
  - primary grouped retrieval surfaces
  - compatibility-oriented flat projections
  - convenience-oriented additive explainability views
- stronger operator visibility into canonical summary state versus derived graph readiness state

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

- strengthen the task-recall and return-to-main-task experience after interruptions or detours
- make the canonical workflow and memory model surface the current primary objective more reliably
- improve retrieval and resume behavior so agents can recover “what was I doing before this side task?” from canonical state without relying on auxiliary local notes

Expected themes:

- introduce an explicit distinction between:
  - primary objective / main line of work
  - temporary detour work
  - return target after detour completion
- improve retrieval contracts for questions such as:
  - what is the current main objective for this workspace?
  - what was the active task before the most recent detour?
  - which workflow should be re-foregrounded as the primary continuation target?
- improve workflow prioritization and recovery rules so recent-but-secondary work does not eclipse the main active objective
- strengthen summary, checkpoint, and memory selection logic so canonical state is better surfaced through agent-facing recall paths
- keep PostgreSQL as the canonical source of truth while improving the recall path that sits on top of it
- treat this as resumability and durable-memory product work, not merely observability or docs cleanup

Current status note:

- the current `0.7.0` slice now has a materially richer task-recall explanation surface in `memory_get_context`, including:
  - return-target details
  - primary-objective details
  - task-thread details
  - selected-versus-latest continuation comparison details
  - candidate-level comparison details for checkpoint, detour, basis, and resumability signals
- `memory_search` now also has a bounded task-recall integration for workspace-scoped searches, including:
  - latest considered workflow identity
  - selected continuation workflow identity
  - selected-versus-latest comparison details in divergent multi-candidate contexts
  - a small selected-continuation-target bonus in bounded divergent contexts
- this means the milestone is no longer only at the heuristic-ranking stage; it now has a more explicit explanation and inspection surface for continuation selection and a first bounded concept-to-task recovery bridge in `memory_search`
- the intended `0.7.0` boundary should now be read as:
  - keep concept-to-task recovery centered on:
    - `memory_get_context`
    - workspace-scoped `memory_search`
  - treat workspace-resume-facing reasoning as an adjacent explanation surface, not as a separate concept-routing authority
  - defer broader retrieval-surface rollout unless a later narrow slice shows it is still necessary and explainable
- the main remaining gaps are:
  - release-facing closeout alignment so the bounded `0.7.0` slice has an explicit behavior summary and acceptance reading
  - explicit recording that broader concept-to-task expansion beyond the bounded current surfaces is deferred past `0.7.0`
  - explicit recording that broader task-recall rollout into other retrieval surfaces is deferred past `0.7.0` unless later justified
  - closeout recording for the now-complete maintainability hardening stream for oversized task-recall-related `src/` and `tests/` files, with:
    - the runtime task-recall test split already landed
    - the oversized visibility-focused memory-context test split already landed
    - the oversized grouping-focused memory-context test split already landed
    - the oversized task-recall-focused memory-context test split already landed
    - the final oversized grouping-summary-routes memory-context test split now also landed into:
      - `tests/memory/test_service_context_details_grouping_summary_routes_multiflow.py`
      - `tests/memory/test_service_context_details_grouping_summary_routes_ordering.py`

## 0.8

Planned focus:

- strengthen the remember path so `ctxledger` reliably records multi-layer memory rather than stopping at sparse episodic notes
- make completion-centered memory capture materially more automatic and structurally useful for AI-agent-driven workflows
- ensure the canonical relational memory model actually accumulates:
  - episodes
  - memory items
  - embeddings
  - memory relations
- make the AGE-backed graph layer operationally meaningful by ensuring its canonical relational inputs are recorded first

Expected themes:

- improve completion-to-memory capture so meaningful workflow closeout and checkpoint knowledge is consistently remembered
- define and implement a clearer multi-layer remember pipeline from:
  - workflow and checkpoint state
  - to episodes
  - to memory items
  - to embeddings
  - to relations
  - to derived graph and summary structures
- strengthen agent-facing operational guidance so MCP-capable agents following repository `.rules` are more likely to record memory automatically and correctly
- introduce explicit relation-generation behavior for the first useful canonical relation types, with `supports` as the likely first constrained target
- improve observability so operators can distinguish:
  - episodes created
  - memory items created
  - embeddings created
  - relations created
  - relation/summary/auto-memory skips and why they happened
- keep PostgreSQL canonical and treat vector indexes, relations, summaries, and AGE graph state as layered retrieval-support structures rather than competing sources of truth

Current problem statement for `0.8`:

- `ctxledger` already has canonical workflow state, episodic recording, initial semantic search, and constrained AGE read paths
- but the practical remember path is still too weak for the intended multi-layer memory model
- memory relations can remain at zero, which means the graph layer has little to mirror or retrieve
- completion-driven recording currently tends to stop at episode and memory-item creation instead of building richer linked memory structure
- AI-agent compliance with memory recording expectations depends too much on voluntary or ad hoc tool usage rather than a strong operational contract
- as a result, the system risks being able to persist work without accumulating enough structured memory to support later recall from concept, entity, or time anchors

Implementation direction for `0.8`:

- define the minimum acceptable remember pipeline for an agent-completed work loop
- decide which completion events should automatically create:
  - episodes
  - memory items
  - embeddings
  - relation candidates
- add the first constrained canonical relation-writing path so `memory_relations` is no longer structurally optional in normal usage
- make relation and summary generation visible, explainable, and diagnosable in operator-facing outputs
- improve memory-writing guidance and tool expectations so agent behavior aligns with the repository’s durable-memory goals

Success shape for `0.8`:

- a normal AI-agent work loop can leave behind useful canonical memory without depending on local notes
- completion and checkpoint information are more consistently transformed into reusable memory records
- memory relations are no longer usually empty in a healthy active deployment
- AGE graph bootstrap/refresh reads from a meaningfully populated canonical relational substrate
- operators can tell whether the system is failing to remember, skipping memory generation by policy, or succeeding end-to-end
- `ctxledger` is better positioned for later graph-memory architectural evaluation because the remember path is no longer the limiting factor

## 0.9

Planned focus:

- evaluate whether ctxledger should move closer to a Mnemis-style hierarchical graph memory design
- compare ctxledger’s `0.6.0`, `0.7.0`, and `0.8.0` implementation against Mnemis-style dual-route retrieval ideas
- decide whether any architectural alignment is justified after the remember-path and task-recall improvements are working

Expected themes:

- review Mnemis as a design input, not a constraint on the current remember-path or task-recall work
- compare relation modeling, hierarchy construction, remember-path structure, and retrieval strategy
- evaluate whether dual-route retrieval concepts should influence later ctxledger versions
- keep any Mnemis-driven redesign scoped to explicit post-`0.8.0` work

## 0.0

Foundation themes:

- stable runtime
- durable persistence
- explicit operational state