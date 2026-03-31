# ctxledger roadmap

Release-facing review artifacts exist for the completed milestone records where relevant.
For `0.8.0`, read the release-facing assessment together with:

- `docs/project/releases/0.8.0_acceptance_review.md`
- `docs/project/releases/0.8.0_closeout.md`

For `0.9.0`, read the bounded contract and acceptance references together:

- `docs/project/releases/plans/versioned/0.9.0_acceptance_checklist.md`
- `docs/project/releases/plans/versioned/0.9.0_ctxledger_rules_strengthening_plan.md`
- `docs/memory/design/historical_progress_query_contract.md`
- `docs/memory/design/interaction_memory_contract.md`
- `docs/memory/design/failure_reuse_contract.md`

## 1.0.0

Delivery focus:

- Azure deployment support
- large deployment pattern validation
- Azure-facing infrastructure and operational acceptance
- repository-supported remote deployment path beyond the local-only posture

Status notes:

- `1.0.0` should be read as the Azure milestone for `ctxledger`
- the large deployment pattern and Azure-facing release work belong to `1.0.0`, not to `1.0.1`
- `1.0.1` should therefore be read as a follow-on stabilization and observability patch on top of the Azure release, not as the Azure milestone itself

For `1.0.1`, read the release-facing closeout as an operations-and-observability stabilization slice on top of the completed `1.0.0` Azure milestone rather than as a new architectural milestone.

Release-facing closeout artifact:

- `docs/project/releases/1.0.1_closeout.md`

## Completed milestones through `1.0.1`

## 0.1.0

Delivery focus:

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

## 0.2.0

Delivery focus:

- episodic memory
- initial reusable memory capture
- early auxiliary context retrieval
- TLS-enabled MCP deployment path after memory closeout

Status notes:

- `memory_remember_episode` is implemented with append-only recording, workflow validation, optional `attempt_id` validation, and canonical PostgreSQL persistence
- `memory_get_context` supports the bounded `0.2.0` slice for direct workflow retrieval, workspace- and ticket-linked expansion, `limit`, `include_episodes`, and lightweight query-aware filtering
- `memory_get_context` response details and supporting docs are aligned with the bounded `0.2.0` contract
- PostgreSQL-backed episode persistence, episode-oriented context retrieval, and integration coverage are in place
- the intended `0.2.0` episodic-memory slice is complete

## 0.3.0

Delivery focus:

- initial pgvector-backed semantic search
- reusable semantic/procedural memory retrieval foundations
- stronger relevance ranking for context assembly

Status notes:

- `memory_search` is implemented with hybrid lexical and embedding-backed ranking over persisted memory items
- embedding configuration and generator scaffolding exist for `disabled`, `local_stub`, `openai`, `voyageai`, `cohere`, and `custom_http`
- PostgreSQL-backed memory embedding persistence and similarity lookup are implemented
- MCP schema, handler wiring, serialization, and integration coverage include `memory_search`
- the intended `0.3.0` semantic-search slice is complete

## 0.4.0

Delivery focus:

- workflow and memory observability
- operator-facing CLI inspection tools
- optional deployable Grafana-based dashboard support
- better runtime visibility into canonical workflow and memory state

Status notes:

- operator-facing CLI status and stats views are in place for workflow activity
- CLI inspection coverage exists for memory, embedding, and failure state
- dashboard-oriented Grafana support has been established as an optional surface
- runtime visibility into canonical workflow and memory health is materially stronger than in earlier milestones

## 0.5.0

Delivery focus:

- targeted refactoring across `src/` and `tests/`
- file-by-file consolidation of duplicated logic and overlapping responsibilities
- cross-file consolidation of duplicated logic, helper behavior, and reusable patterns
- reduction of maintenance overhead without changing externally expected behavior
- safer internal structure to support later feature work
- close out the refactoring wave with a stable foundation for hierarchical memory work in `0.6.0`

Status notes:

- the targeted refactoring wave for the bounded `0.5` scope is complete
- duplicated logic and overlapping responsibilities were reduced across the intended `src/` and `tests/` areas
- internal boundaries, helper placement, naming, and reuse posture were improved without changing expected external behavior
- the resulting structure is considered a sufficient foundation for later hierarchical memory work

## 0.5.1

Delivery focus:

- PostgreSQL connection pooling with `psycopg-pool`
- runtime hardening for PostgreSQL-backed workflow and memory operations
- reduction of per-request connection churn without changing canonical behavior
- alignment of implementation with the documented process model
- a safer database access foundation before broader `0.6.0` work

Status notes:

- PostgreSQL unit-of-work construction requires an explicit shared connection pool instead of silently creating ad hoc pools
- `PostgresUnitOfWork` is pool-backed and borrows connections from a shared pool for transaction-scoped use
- server bootstrap, CLI bootstrap, and runtime factory paths were refactored toward explicit shared-pool ownership
- CLI PostgreSQL command paths create and close shared pools explicitly
- server/runtime bootstrap wiring was corrected so the HTTP/runtime path initializes a real workflow service
- debug-level stage timing was added to `WorkflowService.resume_workflow()`
- targeted PostgreSQL indexes were added for resume-related verify-report and projection-failure lookup patterns
- helper, CLI, server, and coverage-target tests were updated to reflect the new pool ownership rules
- the intended connection-pooling and runtime-hardening slice is complete

## 0.5.3

Delivery focus:

- `workflow_resume` timeout hardening and root-cause reduction
- safer resume/recovery behavior for AI agents that follow repository `.rules`
- stronger distinction between `workspace_id` and `workflow_instance_id` at tool and docs boundaries
- operational diagnosis for resume-path stalls, blocking queries, and transport timeout mismatches
- close the gap between canonical workflow guidance and practical agent/tool usage

Status notes:

- `workflow_resume` identifier-discipline and timeout-hardening work for the bounded `0.5.3` scope is complete
- the repository `.rules` posture aligns explicitly with safe resume behavior
- misuse involving `workspace_id` versus `workflow_instance_id` is treated as a closed hardening concern for this milestone
- resume-path observability and diagnosis support were strengthened without expanding the release into a broader feature wave

## 0.6.0

Delivery focus:

- hierarchical memory retrieval foundations
- canonical summary hierarchy and summary-membership persistence
- constrained Apache AGE-backed graph support under a derived, rebuildable boundary
- summary-first context assembly improvements in `memory_get_context`
- explicit summary build and validation flows for milestone closeout

Status notes:

- canonical relational summary persistence is implemented through `memory_summaries` and `memory_summary_memberships`
- in-memory and PostgreSQL summary and summary-membership repository paths are implemented
- `memory_get_context` supports a constrained summary-first retrieval path with direct member expansion and episode-derived fallback
- constrained graph-backed support is present under a derived, degradable posture while PostgreSQL remains canonical
- explicit summary build paths are implemented through `MemoryService.build_episode_summary(...)` and `ctxledger build-episode-summary`
- workflow-completion-oriented summary automation is implemented in a gated, non-fatal form
- focused service, transport, and PostgreSQL integration coverage exists for the bounded hierarchical-memory slice
- operator-facing stats surface canonical summary volume and derived graph-posture metrics
- the intended `0.6.0` hierarchical-memory slice is complete

## 0.7.0

Delivery focus:

- task recall and return-to-main-task recovery
- continuation selection across mainline and detour work
- workspace-scoped task recall through bounded memory search
- stronger agent-facing explanation for continuation choice

Status notes:

- task-recall, return-to-main-task, and continuation-selection work intended for the bounded `0.7.0` slice is complete
- workspace-scoped `memory_search` support for the bounded task-recall slice is complete
- workspace-resume-facing reasoning remains an adjacent explanation surface rather than a separate concept-routing authority
- no remaining implementation work is tracked here for the `0.7.0` milestone

## 0.8.0

Delivery focus:

- remember-path strengthening
- completion-centered multi-layer memory capture
- canonical accumulation of episodes, memory items, embeddings, and relations
- derived graph support from canonical relational memory inputs

Status notes:

- the bounded `0.8.0` remember-path strengthening milestone is complete
- completion-centered memory capture is automatic and structurally useful for the intended AI-agent-driven workflows
- the canonical relational memory model accumulates episodes, memory items, embeddings, and memory relations for the bounded release scope
- the AGE-backed graph layer has the intended canonical relational inputs and remains a derived retrieval-support layer rather than a competing source of truth
- a normal AI-agent work loop can leave behind useful canonical memory without depending on local notes
- completion and checkpoint information are consistently transformed into reusable memory records
- memory relations are no longer usually empty in a healthy active deployment
- operators can tell whether the system is failing to remember, skipping memory generation by policy, or succeeding end-to-end
- no remaining implementation work is tracked here for the `0.8.0` milestone

## 0.9.0

Delivery focus:

- minimal-prompt resumability from workspace context
- bounded historical progress recall
- automatic interaction-memory capture
- failure-pattern reuse and avoidance
- file-work metadata capture without file-content indexing
- tighter alignment between `ctxledger` behavior and repository `.rules`

Status notes:

- the bounded `0.9.0` strengthening milestone is complete
- canonical workflow, checkpoint, and failure state remain PostgreSQL-first
- summaries, embeddings, ranking signals, interaction memory, and graph-linked structures remain derived support layers unless explicitly stated otherwise
- `.rules` is part of the operational acceptance surface where it materially shapes resumability, bounded historical recall, failure avoidance, interaction-memory discipline, and file-work metadata discipline
- the minimal-prompt `resume` contract was strengthened around workspace-context selection while keeping `workflow_resume` as the workflow-id-specific path
- the supported bounded historical-question class is defined in docs and contracts without implying broad unconstrained historical QA
- automatic interaction-memory capture posture was established for user requests and agent responses in a retrieval-ready, non-canonical-truth role
- the minimum file-work metadata schema was defined and made durably queryable without bringing Git-managed file-content indexing into scope
- focused validation scaffolds exist for resume, historical recall, interaction memory, failure reuse, and file-work metadata
- serializer and response-shaping coverage exists where contract details matter
- HTTP / MCP / service-layer validation exists where the bounded milestone changed behavior
- full repository validation remains green
- a user can say `resume` or `continue` and the system can recover the intended continuation target more reliably from durable state
- bounded historical progress questions can be answered from durable canonical and derived state
- user requests and agent responses are automatically remembered in a retrieval-ready form
- file-work metadata is durably queryable without indexing Git-managed file contents
- prior failure patterns and recoveries are easier to surface and reuse
- `ctxledger` and repository `.rules` behave as one coordinated operating model for the bounded milestone
- no remaining implementation work is tracked here for the `0.9.0` milestone

## 1.0.1

Delivery focus:

- startup and operator-path reliability hardening for the derived AGE layer
- natural file-work recording in bounded file-touching flows
- live validation of small-auth operational behavior
- CLI, SQL, Grafana, and runbook observability alignment
- replacement of ambiguous derived-layer `No data` readings with explicit operator state

Status notes:

- AGE summary graph refresh is automated on startup for bounded degraded states and remains available as an operator fallback path
- the shared AGE refresh path and the live small-auth startup path were repaired and validated against real restart behavior
- file-touching work now naturally produces durable file-work records in bounded runtime and MCP RPC flows when workflow context is available
- bounded file-touch attempts remain valid AI-agent recovery context even when the visible MCP tool surface returns `tool_not_found`, as long as the attempted file-touch metadata is present and explainable
- live validation proved:
  - derived AGE graph recovery to `graph_ready`
  - automatic file-work recording in the running small-auth stack
- PostgreSQL-backed memory summary repositories now support the counting paths needed for live `memory-stats`
- `memory-stats` and `stats` both expose explicit derived-memory-state fields instead of forcing operators to infer meaning from empty panels
- observability SQL and Grafana now surface:
  - `derived_memory_item_count`
  - `derived_memory_item_state`
  - `derived_memory_item_reason`
  - `derived_memory_graph_status`
  - `latest_derived_memory_item_created_at`
- current operator-facing derived-memory readings can distinguish:
  - `ready`
  - `not_materialized`
  - `canonical_only`
  - `degraded`
  - `unknown`
- the intended `1.0.1` closeout slice is complete

## Planned milestone `1.1.0`

Delivery focus:

- stronger truth-sourcing for derived-memory observability
- tighter linkage between derived-memory state and real AGE readiness signals
- possible formal materialization policy for derived memory items
- better operator verification paths and release-facing observability guidance
- follow-on refinement once the `1.0.1` stabilization slice is closed

Planned themes:

- replace remaining heuristic derived-state classification with a more direct readiness-backed source where practical
- refine how `degraded`, `stale`, and `unknown` are surfaced across SQL, CLI, Grafana, and runtime introspection
- decide whether derived memory items should remain an explicitly non-materialized support concept in some cases or become a more formal generated layer
- capture the live operator verification flow as a more formal release-facing and runbook-facing procedure
- continue improving operator clarity without weakening the canonical-truth boundary

## Cross-version guiding rules

- PostgreSQL remains the canonical system of record
- repository projections remain derived artifacts
- workflow control and memory retrieval stay separate
- resumability and recoverability are prioritized over thin feature claims
- version should not be bumped until implementation and docs meaningfully match the claimed scope
- graph capabilities should be introduced to support memory behavior, not to replace PostgreSQL as the canonical source of truth

## Immediate next steps

- no remaining implementation work is tracked in this roadmap for milestones up to and including `1.0.1`
- use future roadmap sections only for post-`1.0.1` planning
- treat the current derived-memory and observability follow-up themes as `1.1.0` planning work rather than `1.0.1` release debt

