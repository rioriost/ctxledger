# Architecture

## 1. Purpose

`ctxledger` is a durable workflow runtime and multi-layer memory system for AI agents.

The system is designed to provide:

- durable workflow control
- PostgreSQL-backed canonical state
- MCP-compatible remote access
- repository projections as derived artifacts
- future multi-layer memory and retrieval capabilities

In `v0.1.0`, the primary implementation target is the workflow control subsystem.  
The memory subsystem is architecturally defined from the beginning, but only partially implemented in the initial release.

---

## 2. Architectural Principles

The architecture follows these governing principles:

1. **Canonical state lives in PostgreSQL**
2. **Repository files are projections only**
3. **Planning identity and execution identity are separate**
4. **Workflow control and memory retrieval are separate layers**
5. **MCP is the public interface**
6. **Durable execution is prioritized over convenience**

In addition, the system distinguishes clearly between:

- **truth**
  - canonical workflow and memory state in PostgreSQL
- **projections**
  - repository-facing derived artifacts generated from canonical state when explicitly supported
- **indexes / read accelerators**
  - embeddings, summaries, and other derived retrieval structures

These categories must not be conflated.

---

## 3. System Context

`ctxledger` serves MCP-compatible clients such as Zed and other AI-agent development tools.

Primary interfaces:

- HTTP MCP at `/mcp`

Primary canonical dependency:

- PostgreSQL

Recommended deployment topology:

- reverse proxy
- bearer token authentication
- TLS
- MCP server
- PostgreSQL

Future optional dependencies may include:

- embedding generation providers
- background workers
- indexing pipelines
- summary generation pipelines

---

## 4. Runtime Architecture

### 4.1 MCP Integration Strategy

`ctxledger` adopts a **hybrid MCP integration strategy**.

The system prefers using existing MCP protocol/runtime libraries for:

- transport handling
- protocol framing
- tool/resource exposure mechanics

However, the following concerns remain application-owned:

- workflow domain logic
- persistence
- transaction boundaries
- projection generation
- authentication boundary behavior
- resource assembly
- error taxonomy and error normalization

This keeps MCP as an interface layer rather than the core of the system.

### 4.2 Shared Core and Separate Adapters

The runtime is organized around a **shared application core** with separate transport adapters.

Adapter:

- HTTP MCP adapter for `/mcp`

Shared core responsibilities:

- application services
- repositories
- domain logic
- resume assembly
- projection logic
- configuration usage

Transport-specific code must remain thin.  
HTTP transport concerns must not alter business semantics.

For `v0.1.0`, the primary acceptance surface is the minimal HTTP MCP path at `/mcp`, where the repository now evidences:

- `initialize`
- `tools/list`
- `tools/call`

Broader protocol-scope claims should be treated separately from this currently evidenced minimal path.

### 4.3 Process Model

Current process model for the `0.5.1` connection-pooling hardening work:

- validated runtime configuration
- process-scoped PostgreSQL connection pool ownership
- transport adapter initialization
- startup/shutdown lifecycle management
- transaction-scoped unit-of-work execution over pooled connections

The current implementation direction is that a running `ctxledger` process should own a shared PostgreSQL connection pool, and each request or tool invocation should obtain a transaction-scoped database session from that pool.

Current implementation notes:

- PostgreSQL-backed unit-of-work construction is now expected to receive an explicit shared pool
- CLI and server/bootstrap paths are being aligned around explicit pool ownership instead of ad hoc pool creation
- HTTP/runtime bootstrap must initialize a real workflow service before serving resume-oriented routes
- recent resume-path hardening added targeted timing instrumentation for stage-by-stage workflow resume lookup diagnosis

---

## 5. Layered Internal Architecture

The system follows an explicit layered architecture.

### 5.1 Transport Layer

Responsibilities:

- MCP HTTP transport handling
- authentication entrypoint
- request parsing
- response serialization
- protocol-visible error mapping

This layer does not implement workflow rules.

### 5.2 Application Layer

Responsibilities:

- tool handlers
- resource handlers
- use case orchestration
- transaction demarcation
- read model assembly coordination
- invocation of repositories and domain services

This layer coordinates operations but should not embed low-level storage concerns.

### 5.3 Domain Layer

Responsibilities:

- workflow state machine rules
- attempt lifecycle rules
- retry and cancellation semantics
- checkpoint semantics
- resume semantics
- invariant definitions
- memory model contracts

This layer defines what is allowed, what is terminal, and what is inconsistent.

### 5.4 Infrastructure Layer

Responsibilities:

- PostgreSQL repositories
- SQL execution
- projection file writing
- file system interaction
- future embedding backends
- future background processing integration

This layer implements technical details but does not define business truth.

### 5.5 Cross-Cutting Concerns

Shared concerns include:

- typed configuration
- structured logging
- error taxonomy
- request correlation
- health/readiness handling

### 5.6 Dependency Direction

Dependencies flow in the following conceptual direction:

- Transport → Application → Domain
- Infrastructure is used by Application and supports Domain-oriented use cases
- Cross-cutting concerns are shared, but must not dissolve responsibility boundaries

---

## 6. Persistence Architecture

### 6.1 PostgreSQL as Canonical Store

PostgreSQL is the canonical system of record for:

- workspaces
- workflow instances
- workflow attempts
- workflow checkpoints
- verify reports
- projection failure tracking
- future episodes
- future semantic memory
- future relation graph
- future artifact metadata
- future structured failure records

Repository files are never canonical.

### 6.2 Repository Pattern

Persistence access is mediated through a repository abstraction.

Representative repositories include:

- `WorkspaceRepository`
- `WorkflowInstanceRepository`
- `WorkflowAttemptRepository`
- `WorkflowCheckpointRepository`
- `VerifyReportRepository`

Future repositories may include:

- `EpisodeRepository`
- `MemoryItemRepository`
- `MemoryEmbeddingRepository`
- `MemoryRelationRepository`
- `ArtifactRepository`
- `FailureRepository`

Repositories are responsible for:

- SQL encapsulation
- persistence operations
- query construction
- row-to-application model mapping

Application services are responsible for:

- orchestration
- validation
- state transitions
- consistency rules

### 6.3 Transaction Boundary

The default transactional policy is:

- **one use case / one tool invocation / one transaction**

Canonical workflow state changes occur inside the transaction.

These operations are transaction-internal:

- workflow instance creation/update
- workflow attempt creation/update
- checkpoint creation
- verify report persistence
- future episode persistence
- future memory persistence
- projection failure record persistence

These operations are transaction-external and best-effort:

- projection file writes
- metrics emission
- non-critical log export
- future asynchronous embedding generation

Projection generation occurs after successful commit.  
Projection failure must not roll back canonical workflow persistence.

### 6.4 Schema Bootstrap and Migration Policy

Database initialization and schema migration are explicit operational steps.

The server must not implicitly apply schema changes during normal startup.

Startup may verify:

- database connectivity
- presence of required tables/schema
- compatibility of runtime assumptions

This keeps schema evolution separate from request-serving behavior.

---

## 7. Identity and Entity Model

### 7.1 Identity Layers

The architecture distinguishes multiple layers of identity.

Plan layer:

- `ticket_id`
- future `plan_id`

Execution layer:

- `workflow_instance_id`

Operational layer:

- `attempt_id`
- future `event_seq`

The separation is intentional.  
Planning identity and execution identity must not be collapsed into one field.

### 7.2 Identifier Generation Policy

Primary identifiers are generated by the application as UUIDs.

This applies to entities such as:

- `workspace_id`
- `workflow_instance_id`
- `attempt_id`
- `checkpoint_id`
- `verify_id`
- `episode_id`
- `memory_id`

This allows IDs to exist before persistence succeeds, which improves:

- structured logging
- error reporting
- projection generation
- orchestration consistency

### 7.3 Workspace Identity Model

The canonical identity of a workspace is `workspace_id`.

The following are attributes, not identity:

- `repo_url`
- `canonical_path`
- `default_branch`

This allows future flexibility for:

- path changes
- repository URL changes
- multiple checkouts
- more advanced workspace mapping

### 7.4 Workspace Registration and Conflict Policy

Workspace registration follows a **quasi-strict** policy.

Rules:

- `workspace_register` primarily creates a new workspace
- updates are allowed only when an explicit `workspace_id` is provided
- path/URL ambiguity without explicit identity is treated as an error
- automatic identity merge is not performed

This prevents accidental workspace conflation.

---

## 8. Workflow Control Architecture

### 8.1 Separate State Machines

`workflow_instance` and `workflow_attempt` use separate state machines.

#### Workflow Instance Status

- `running`
- `completed`
- `failed`
- `cancelled`

A workflow instance represents the execution as a whole.

#### Workflow Attempt Status

- `running`
- `succeeded`
- `failed`
- `cancelled`

An attempt represents one execution trial under the workflow instance.

This separation is necessary for retry-capable design.

### 8.2 Active Workflow Concurrency Policy

In `v0.1.0`, at most one `running` workflow instance may exist per workspace.

This rule is enforced primarily by the database, with application-side checks used to improve error clarity.

This choice keeps:

- `workspace://{workspace_id}/resume` unambiguous
- repository-facing derived artifact handling simple
- operational behavior predictable

### 8.3 Retry Model

The architecture is retry-capable, but retry remains minimal in `v0.1.0`.

Rules:

- a workflow may own multiple attempts over time
- at most one active attempt exists at a time
- new attempts are created only after previous active attempts become terminal
- `attempt_number` should be used to track attempt order

A future `workflow_retry` operation can be added without redesigning the core model.

### 8.4 Cancellation Semantics

`cancelled` is a terminal state.

A cancelled workflow or attempt is not resumed as-is.

If work should continue after cancellation, the system must create:

- a new attempt, or
- a new workflow instance

Cancellation is treated as an explicit external decision, not a temporary pause.

### 8.5 Completion and Termination Semantics

`workflow_complete` is treated architecturally as a **termination operation**.

It may terminate a workflow in one of these states:

- `completed`
- `failed`
- `cancelled`

Typical mapping:

- workflow `completed` ↔ attempt `succeeded`
- workflow `failed` ↔ attempt `failed`
- workflow `cancelled` ↔ attempt `cancelled`

The external tool name remains `workflow_complete`, but the architectural meaning is broader than success-only completion.

`workflow_complete` should not be treated as a general-purpose progress-save operation.

If more work may still occur in the current work loop, the system should prefer another checkpoint and delay `workflow_complete` until the work is truly done.

Once a workflow becomes terminal, it should be inspected rather than continued as active work. If additional work is needed after terminal closure, the system should create a new workflow instance or other explicit continuation path rather than appending new checkpoints to the closed workflow.

---

## 9. Checkpoint and Resume Architecture

### 9.1 Checkpoint as Resume Snapshot

A checkpoint is not merely a lightweight event record.

A checkpoint is a **resume snapshot** that captures enough structured state for safe continuation.

Checkpoint creation applies only to operationally open workflow and attempt state. Once the workflow or active attempt is terminal, the system should reject additional checkpoint creation for that closed execution path.

Checkpoint data should include:

- workflow and attempt identity
- `step_name`
- summary
- structured `checkpoint_json`
- creation timestamp

The structured payload may include:

- current objective
- completed work summary
- next intended action
- relevant files/artifacts
- branch or commit context
- verification context
- unresolved issues
- agent-facing resume instructions

### 9.2 Composite Resume View

`workflow_resume` returns a **composite resume view**, not a raw single-table record.

It may include:

- workspace information
- workflow instance information
- active or latest attempt
- latest checkpoint
- latest verify report
- projection status
- warnings/issues
- closed projection failure history
- resumable classification
- derived hints for next action

The same assembled read model may also be exposed through concrete server-specific HTTP read surfaces for operational inspection.

This read model is the primary recovery interface.

### 9.3 Partial Resume and Inconsistency Reporting

`workflow_resume` should return as much useful information as possible, even when canonical state is imperfect.

Possible `resumable_status` values include:

- `resumable`
- `terminal`
- `blocked`
- `inconsistent`

When `resumable_status = terminal`, clients should interpret the result as “inspect final state” rather than “continue execution”.

Possible warnings/issues include:

- running workflow without active attempt
- running attempt without checkpoint
- stale projection
- open projection failure
- ignored projection failure
- resolved projection failure
- missing verify context
- unavailable workspace path

Hard failures such as missing workflow or unauthorized access remain protocol errors.  
Operational inconsistencies should be surfaced as diagnostic state in the assembled view whenever possible.

### 9.4 Workspace Resume Resource

`workspace://{workspace_id}/resume` is defined as a workspace-scoped current operational resume view.

Selection rule:

1. if a running workflow exists, return that workflow’s composite resume view
2. otherwise return the latest workflow instance for the workspace
3. if none exists, return empty/not-found semantics

Exact workflow inspection is handled separately via:

- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

---

## 10. MCP Interface Architecture

### 10.1 Tool and Resource Responsibility Split

Tools represent explicit operations and state mutations.

Examples:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`
- future `workflow_retry`
- future memory write operations

Resources represent read-only assembled views.

Examples:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- future episode and summary resources

`workflow_resume` is semantically a read operation, but is also exposed as a Tool for MCP client compatibility.

### 10.2 Read and Write Model Separation

The architecture uses a lightweight separation between write and read concerns.

Write path:

- use case orchestration
- transaction handling
- canonical persistence

Read path:

- assembled views
- selection logic
- warnings/issues classification
- resource projection

Repository projection files are derived from read models, not canonical inputs.

### 10.3 Error Mapping

Internal errors are categorized by application/domain meaning and mapped at the transport boundary to MCP-visible errors.

Raw exceptions are not exposed directly.

---

## 11. Verification Architecture

### 11.1 Verification as Canonical Operational Evidence

Verification is a lightweight but official canonical component.

`verify_reports` are stored durably and may appear in resume views, but verification is not yet a hard completion gate in `v0.1.0`.

Typical statuses may include:

- `pending`
- `passed`
- `failed`
- `skipped`

### 11.2 Recording Timing

Verification records may be written at:

- checkpoint time
- workflow termination time

This supports both intermediate and final verification evidence.

### 11.3 Resume Integration

Resume views include the latest verify report for the relevant attempt when available.

Future versions may add richer verification history views and policy-based verification gating.

---


- `status`

This dedicated surface is a read-only convenience endpoint over canonical projection failure history.  
It does not change the rule that PostgreSQL remains canonical and repository projections remain derived.

This separation allows the system to preserve diagnostic state without overstating currently active failure conditions.

### 12.7 Projection Freshness Model

Projection status should reflect freshness, not only failure.

Representative statuses:

- `fresh`
- `stale`
- `missing`
- `failed`

Freshness should be derived by comparing the latest relevant canonical update against the latest successful projection write.

Resume views may include projection freshness diagnostics.

---

## 13. Memory Subsystem Architecture

### 13.1 Separate Memory Subsystem

The memory system is architecturally distinct from the workflow control subsystem.

Workflow control manages operational truth.  
Memory manages reusable knowledge and retrieval.

The two subsystems may reference each other, but they must not be collapsed into one model.

### 13.2 Episodic Memory Formation

An `episode` is formed primarily when a workflow instance reaches completion.

An episode represents a summarized execution record, not a checkpoint.

Episodes may incorporate:

- workflow metadata
- attempt history
- meaningful checkpoints
- verification evidence
- failures and resolutions
- produced artifacts

### 13.3 Semantic and Procedural Memory Ingestion

`memory_items` may arise from multiple ingestion paths:

- episode-derived extraction
- explicit/manual recording

This supports both learned knowledge and intentionally curated knowledge.

### 13.4 Auxiliary Retrieval Model

`memory_get_context` is an auxiliary retrieval operation.

It must remain distinct from `workflow_resume`.

`workflow_resume` returns canonical operational state.  
`memory_get_context` returns relevance-based support context.

A client may combine them, but the architecture keeps them separate.

### 13.5 Hierarchical Summaries

Hierarchical summaries are a derived, read-optimized layer.

They are used for:

- abstraction
- compression
- retrieval acceleration
- long-context support

They are not replacements for canonical raw memory.

For the current `0.6.0` hierarchical memory slice, the canonical summary source
remains relational PostgreSQL state, especially:

- `memory_summaries`
- `memory_summary_memberships`

Any graph-backed summary structure should be read as derived support state rather
than canonical hierarchy truth.

That means:

- summary absence in derived graph state does not imply canonical summary loss
- summary staleness in derived graph state affects enrichment quality rather than
  canonical correctness
- ordinary summary retrieval correctness should still be interpreted from the
  canonical relational path

### 13.6 Memory Relation Graph

`memory_relations` form a canonical relation store across memory entities.

The relation graph may link:

- episode to memory item
- memory item to memory item
- summary to source item
- failure to resolution knowledge
- artifact to episode

Retrieval may use both relation traversal and semantic similarity.

### 13.7 Embedding Index Model

Embeddings are derived index data.

Canonical memory content remains the truth source.  
Embeddings exist to accelerate retrieval and may be regenerated.

Embedding staleness or generation failure affects retrieval quality, not canonical memory truth.

### 13.8 Asynchronous Embedding Pipeline

Embedding generation is designed as an asynchronous or deferrable process.

Canonical memory persistence must not depend on synchronous embedding success.

This allows:

- lower write latency
- retryable indexing
- model version migration
- index rebuilds

---

## 14. Artifact and Failure Knowledge Architecture

### 14.1 Artifact Metadata Model

Artifact content may exist in the repository, file system, or external storage.

`ctxledger` stores canonical artifact metadata rather than treating the artifact bytes themselves as canonical state.

Artifact metadata may include:

- owner references
- artifact type
- role
- path or locator
- MIME type
- provenance
- creation time

Artifacts support:

- execution traceability
- episode evidence
- memory provenance
- retrieval enrichment

### 14.2 Structured Failure Model

Failures are treated as structured records, not only free-form notes.

A failure record may include:

- scope
- type
- summary
- details
- resolution
- status
- timestamps
- owner references

This supports:

- debugging
- retry analysis
- episode generation
- future semantic memory extraction
- recurring failure pattern discovery

Error handling and durable failure recording are related but not identical.  
Not every runtime error becomes a canonical failure record.

---

## 15. Security Architecture

### 15.1 Authentication Boundary

In `v0.1.0`, authentication is the primary formal security control.

Bearer token authentication is handled at the transport boundary.

Authenticated caller context may be propagated inward for:

- logging
- future audit compatibility
- future authorization expansion

### 15.2 Authorization Deferral

Fine-grained authorization is deferred beyond `v0.1.0`.

This includes:

- per-workspace access control
- role-based policy
- tenant-aware restrictions

The architecture should remain compatible with later addition of these controls.

### 15.3 Production Topology

Production deployments should use:

- reverse proxy
- TLS
- secret-managed bearer tokens
- PostgreSQL persistence with durable volume backing

---

## 16. Observability and Diagnostics

### 16.1 Structured Logging

Structured logging is the standard observability mechanism in `v0.1.0`.

Important log events include:

- workspace registration
- workflow start
- checkpoint creation
- workflow termination
- verification persistence
- projection generation success/failure
- projection stale detection
- resume inconsistency detection
- authentication failure
- DB conflict and invariant violation
- startup and shutdown events

### 16.2 Correlation Identifier Policy

Request or correlation identifiers are primarily observability concerns.

They belong in:

- logs
- tracing contexts
- future audit/event systems

They are not mandatory canonical workflow fields in `v0.1.0`.

### 16.3 Metrics and Tracing as Extensions

Metrics and tracing are expected future extensions.

Useful future metrics may include:

- workflow starts/completions/failures
- checkpoint count
- projection failure count
- stale projection count
- resume inconsistency count

Tracing may later cover:

- transport-to-service call flow
- repository spans
- projection write spans

---

## 17. Health, Readiness, and Deployment Semantics

### 17.1 Liveness and Readiness

Liveness and readiness are separate concerns.

Liveness indicates the process is up.

Readiness indicates the service can safely process workflow requests and should include at least:

- PostgreSQL connectivity
- required schema/table availability
- valid critical configuration

### 17.2 Degraded Operation

The system may be degraded but still ready.

Examples of degraded-but-ready conditions:

- stale projection
- missing projection file
- projection write failure
- embedding lag
- memory indexing lag
- derived AGE summary graph mirroring is absent, stale, or not yet refreshed
- narrow graph-backed summary-member traversal is unavailable and the system falls back to non-graph behavior
- summary-graph readiness/observability checks report derived graph degradation while canonical relational summaries remain available

These do not necessarily invalidate the workflow control subsystem.

For `0.6.0`, this distinction should be read explicitly as:

- relational PostgreSQL summary state remains canonical
- derived summary graph state remains supporting and rebuildable
- ordinary summary-first retrieval must remain correct even when derived summary graph state is unavailable or degraded
- graph-backed summary traversal may improve auxiliary context assembly when ready, but should not become a hard readiness dependency

### 17.3 Local Deployment

Local deployment is expected to use Docker Compose with:

- PostgreSQL
- MCP server
- persistent PostgreSQL volume

---

## 18. Configuration Architecture

### 18.1 Typed Configuration Boundary

Configuration is managed through a single typed settings boundary.

This boundary validates:

- database configuration
- transport settings
- HTTP bind settings
- authentication configuration
- projection behavior
- logging behavior
- future indexing and worker settings

Invalid critical configuration should fail startup early.

### 18.2 Configuration Propagation

Downstream layers receive validated settings objects rather than directly reading environment variables.

This keeps configuration centralized and predictable.

### 18.3 Environment Profiles

The architecture should support documentation and operation across multiple profiles, such as:

- local development
- local Docker
- production-like deployment

---

## 19. Error Taxonomy

The system maintains an internal error taxonomy and maps it to MCP-visible errors at the transport boundary.

Representative internal categories include:

- validation errors
- authentication errors
- not found errors
- conflict/invariant errors
- persistence errors
- projection errors
- resume inconsistency issues

The architecture distinguishes between:

- **hard errors**
  - operation fails
- **soft operational issues**
  - operation returns useful data with warnings/issues

This distinction is especially important for `workflow_resume`.

---

## 20. Test Architecture

Testing is treated as part of the architectural validation strategy.

### 20.1 Domain and Service Tests

These validate:

- state transitions
- retry rules
- cancellation rules
- completion semantics
- resume assembly
- inconsistency classification
- projection freshness logic

### 20.2 Repository and Persistence Integration Tests

These validate:

- schema assumptions
- transaction boundaries
- uniqueness constraints
- active workflow enforcement
- latest checkpoint retrieval
- latest verify retrieval

Persistence integration tests should also preserve operator and development history already stored in PostgreSQL.

Current repository testing direction:

- integration tests should not truncate or mutate long-lived working tables in the shared/default schema
- each PostgreSQL integration test run should use an isolated temporary schema
- the test schema should be created before schema bootstrap is applied
- session behavior should set the PostgreSQL search path so unqualified repository queries resolve into the temporary test schema first
- the temporary schema should be dropped after the test run completes

This keeps persistence integration coverage realistic while preventing test cleanup from deleting or overwriting existing local workflow and memory history stored for normal repository use.

### 20.3 Transport and Adapter Tests

These validate:

- MCP tool binding
- resource exposure
- authentication boundary
- error mapping
### 20.4 End-to-End and Smoke Tests

These validate:

- startup and readiness
- workspace registration
- workflow start
- checkpoint creation
- restart-safe resume
- workflow termination
- projection generation
- local Docker boot path

Because `ctxledger` is a durable workflow system, restart, recovery, and resumability are architectural test priorities rather than optional implementation details.