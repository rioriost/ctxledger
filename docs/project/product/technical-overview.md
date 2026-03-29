# ctxledger Technical Overview

This document is based on current repository documentation, but implementation-facing claims must remain aligned with the code and schema.

When documentation and implementation diverge, the code and `schemas/postgres.sql` take precedence.

## 1. Purpose

`ctxledger` is a durable workflow runtime and multi-layer memory system for AI agents.

It is designed to:

- persist exact workflow state across sessions and process restarts
- recover resumable operational state safely
- accumulate reusable memory from prior work
- retrieve bounded historical and contextual knowledge
- expose those capabilities through an MCP-compatible HTTP interface

The system separates:

- canonical operational truth
- canonical durable memory
- derived retrieval structures
- auxiliary retrieval outputs

That boundary is central to understanding both the schema and the runtime behavior.

---

## 2. Design Principles

### 2.1 Canonical state lives in PostgreSQL

PostgreSQL is the canonical system of record for workflow state and durable memory.

Canonical records include workflow entities such as:

- `workspaces`
- `workflow_instances`
- `workflow_attempts`
- `workflow_checkpoints`
- `verify_reports`

Canonical memory entities also live in PostgreSQL, including:

- `episodes`
- `memory_items`
- `memory_relations`
- `memory_summaries`
- `memory_summary_memberships`

### 2.2 Repository files are projections only

Repository-facing artifacts and local files are not the source of truth.

They may be useful as:

- projections
- operator aids
- local continuation material
- review artifacts

but they must not be confused with canonical workflow or memory state.

### 2.3 Workflow control and memory retrieval are separate

`ctxledger` intentionally separates operational workflow control from memory retrieval.

In particular:

- `workflow_resume` returns canonical operational state
- `memory_get_context` returns support context
- `memory_search` returns bounded search-oriented memory retrieval

This distinction prevents approximate retrieval behavior from redefining workflow truth.

### 2.4 Durable execution is prioritized over convenience

The system favors:

- restart-safe execution
- explicit lifecycle transitions
- persistent checkpoints
- canonical identifiers
- explicit status boundaries

over thin convenience behavior.

### 2.5 MCP is the public interface

The public runtime surface is MCP-compatible HTTP at `/mcp`.

That interface exposes workflow and memory capabilities without making the transport layer itself the source of truth.

---

## 3. System Context

At a high level, `ctxledger` sits between MCP-capable clients and a PostgreSQL-backed durable state layer.

The current system context is:

- MCP-compatible client or AI agent
- authenticated HTTP MCP endpoint at `/mcp`
- application runtime and service layer
- PostgreSQL as canonical store
- optional embedding generation providers
- bounded vector and graph-backed retrieval support
- operator-facing CLI and observability surfaces

In practice:

- clients send MCP requests to the HTTP runtime
- the runtime delegates to application services
- services load or mutate canonical PostgreSQL state
- memory retrieval may use relational lookup, vector similarity, and bounded derived graph support
- operators inspect runtime and memory posture through CLI stats and supported observability surfaces

The primary serving shape is:

- FastAPI application wrapper
- `uvicorn` process
- authenticated HTTP MCP path at `/mcp`

Recommended deployment posture includes:

- reverse proxy
- bearer token authentication
- TLS
- `ctxledger` runtime
- PostgreSQL

### 3.1 System context diagram

```/dev/null/technical-overview-system-context.mmd#L1-18
flowchart TD
    Client["MCP client / AI agent"]
    Proxy["Reverse proxy / auth / TLS"]
    MCP["ctxledger HTTP MCP runtime (/mcp)"]
    App["Application services"]
    DB["PostgreSQL canonical store"]
    Vec["pgvector embedding support"]
    AGE["Apache AGE derived graph support"]
    Embed["Optional embedding providers"]
    Ops["CLI / Grafana / operator surfaces"]

    Client --> Proxy --> MCP --> App --> DB
    App --> Vec
    App --> AGE
    App --> Embed
    Ops --> MCP
    Ops --> DB
```

---

## 4. Layered Internal Architecture

The internal design follows a layered architecture:

### 4.1 Transport layer

The transport layer is responsible for:

- HTTP MCP handling
- request parsing
- response serialization
- protocol-visible error normalization
- authentication boundary behavior

This layer exposes the MCP interface but does not own workflow or memory truth.

### 4.2 Application layer

The application layer is responsible for:

- tool handling
- resource handling
- orchestration of use cases
- transaction demarcation
- read-model assembly

It coordinates workflow and memory operations while remaining above storage details.

### 4.3 Domain layer

The domain layer is responsible for:

- workflow lifecycle rules
- attempt and checkpoint semantics
- resume semantics
- memory contracts
- invariant enforcement

This layer defines what the system means, not how it is physically stored.

### 4.4 Infrastructure layer

The infrastructure layer is responsible for:

- PostgreSQL repositories
- SQL execution
- pooled connection usage
- filesystem interactions where needed
- embedding integration points
- bounded graph-support implementation

This layer implements technical mechanics in support of the higher layers.

### 4.5 Cross-cutting concerns

Cross-cutting concerns include:

- configuration
- logging
- error taxonomy
- runtime readiness
- request correlation
- lifecycle management

### 4.6 Dependency direction

The intended dependency direction is:

- Transport → Application → Domain
- Infrastructure supports Application and Domain-facing use cases
- Cross-cutting concerns are shared without erasing layer boundaries

---

## 5. Canonical, Derived, and Auxiliary Boundaries

A useful way to understand `ctxledger` is to split system data into three categories.

This section is especially important because many implementation details only make sense if these boundaries stay explicit.

## 5.1 Canonical data

Canonical data is the authoritative durable state.

It includes:

- workflow records
- attempt records
- checkpoints
- verification records
- episodes
- memory items
- memory relations
- summaries
- summary memberships
- structured failure records
- artifact metadata

Canonical data is persisted relationally in PostgreSQL.

## 5.2 Derived data

Derived data exists to support retrieval, explainability, indexing, or projection.

It includes:

- repository projections
- ranked retrieval views
- grouped read models
- vector similarity support
- optional graph-backed support
- summary-first retrieval shaping
- compatibility-oriented flattened response surfaces

Derived data can matter operationally, but it is not the canonical truth source.

## 5.3 Auxiliary outputs

Auxiliary outputs are returned to help reasoning and recall, but they are not workflow truth.

The most important example is `memory_get_context`, which returns support context assembled from canonical and derived layers.

Auxiliary context may be:

- grouped
- filtered
- route-aware
- summary-first
- relation-assisted
- bounded by flags such as `primary_only`

but it must not be read as the same thing as an exact workflow resume.

## 5.4 Resume is not recall

This distinction is central.

### `workflow_resume`
Use when the caller needs exact current operational state.

Typical concerns:

- current workflow identity
- current attempt
- latest checkpoint
- latest verify state
- resumability status
- next hint for safe continuation

### `memory_get_context`
Use when the caller needs support context.

Typical concerns:

- what happened before
- what was learned
- what related memory might help
- which summaries or memory groups should be surfaced first

### `memory_search`
Use when the caller needs bounded lexical and semantic retrieval over persisted memory.

Typical concerns:

- similar prior work
- failure reuse
- interaction memory
- file-work signals
- reusable patterns

---

## 6. Workflow Architecture

The workflow subsystem is the operational core of `ctxledger`.

## 6.1 Identity layers

The workflow model distinguishes multiple identity layers.

### Plan-layer identity
User-facing or external planning identity, such as:

- `ticket_id`

### Execution-layer identity
Durable workflow execution identity:

- `workflow_instance_id`

### Operational identity
Concrete execution and resumability identities:

- `attempt_id`
- `checkpoint_id`

This separation allows the system to distinguish a user task reference from the durable runtime record and the concrete progress snapshots within it.

## 6.2 Core workflow entities

### `workspaces`
A workspace defines the repository scope in which workflows run.

Key fields include:

- `workspace_id`
- `repo_url`
- `canonical_path`
- `default_branch`
- `metadata_json`

### `workflow_instances`
A workflow instance is the top-level durable execution record for a task in a workspace.

Key fields include:

- `workflow_instance_id`
- `workspace_id`
- `ticket_id`
- `status`
- `metadata_json`

The schema enforces at most one running workflow per workspace through a partial unique index.

### `workflow_attempts`
A workflow may have one or more concrete attempts.

Key fields include:

- `attempt_id`
- `workflow_instance_id`
- `attempt_number`
- `status`
- `failure_reason`
- `verify_status`

The schema also enforces at most one running attempt per workflow instance.

### `workflow_checkpoints`
Checkpoints are resumable execution snapshots.

Key fields include:

- `checkpoint_id`
- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `summary`
- `checkpoint_json`

`checkpoint_json` is important because it carries structured state such as current objective and next intended action.

### `verify_reports`
Verify reports capture canonical verification evidence.

Key fields include:

- `verify_id`
- `attempt_id`
- `status`
- `report_json`

## 6.3 Workflow lifecycle

The normal lifecycle is:

1. workspace registration
2. workflow start
3. attempt creation
4. execution
5. checkpoint creation
6. optional verification
7. further execution
8. terminal completion, failure, or cancellation
9. optional memory formation

`workflow_complete` is terminal.  
It is not a generic save-progress operation.

## 6.4 Resume behavior

`WorkflowService.resume_workflow(...)` reconstructs operational resume state from canonical records.

The current implementation shape includes lookup and assembly over:

- workflow instance
- workspace
- running or latest attempt
- latest checkpoint
- latest verify report
- resumability classification
- next-hint derivation

The resume path also includes timing-aware instrumentation for stage-by-stage diagnosis.

That is an implementation detail, but it matters because resume is treated as a real operational path, not just a convenience lookup.

---

## 7. Multi-Layer Memory Architecture

`ctxledger` uses a layered memory model so that durable workflow history and reusable knowledge are connected without being conflated.

The current model is best understood as four conceptual layers.

## 7.1 Layer 1 — Workflow state

This is the exact operational truth layer.

It answers questions such as:

- what workflow is active?
- what was the latest checkpoint?
- what verify state exists?
- can work be safely resumed?

Representative records:

- `workspaces`
- `workflow_instances`
- `workflow_attempts`
- `workflow_checkpoints`
- `verify_reports`

This is not merely “metadata about work.”  
It is the core durable control state.

## 7.2 Layer 2 — Episodic memory

This layer captures memorable units of experience linked to work.

An episode is a durable, reusable memory unit rather than just a raw event.

Representative records:

- `episodes`
- `episode_events`
- `episode_summaries`
- `episode_failures`
- `episode_artifacts`

Important schema facts:

- episodes are linked to `workflow_instances`
- episodes may also link to `attempt_id`
- episodes have append-only recording semantics at the service level
- multiple episodes per workflow are supported

This layer captures things such as:

- meaningful debugging lessons
- non-obvious root causes
- design decisions
- recoveries from failure

## 7.3 Layer 3 — Semantic / procedural memory

This layer captures reusable knowledge in a more retrieval-oriented form.

Representative records:

- `memory_items`
- `memory_embeddings`
- `memory_relations`

### `memory_items`
A memory item is a durable reusable record linked to a workspace and optionally an episode.

Key fields include:

- `memory_id`
- `workspace_id`
- `episode_id`
- `type`
- `provenance`
- `content`
- `metadata_json`

The current provenance model includes values such as:

- `episode`
- `explicit`
- `derived`
- `imported`
- `workflow_checkpoint_auto`
- `workflow_complete_auto`
- `interaction`

This makes the memory layer broad enough to include:

- episode-derived memory
- auto-promoted workflow memory
- interaction memory

### `memory_embeddings`
Embeddings support vector-based retrieval over memory items.

Key fields include:

- `memory_embedding_id`
- `memory_id`
- `embedding_model`
- `embedding`
- `content_hash`

Embeddings are persisted in PostgreSQL using `VECTOR(1536)`.

### `memory_relations`
Relations capture directional semantic links between memory items.

Key fields include:

- `memory_relation_id`
- `source_memory_id`
- `target_memory_id`
- `relation_type`
- `metadata_json`

These relations are distinct from summary membership.  
That distinction is important.

## 7.4 Layer 4 — Hierarchical memory

This layer provides compressed and hierarchy-aware memory structure.

Representative records:

- `memory_summaries`
- `memory_summary_memberships`

### `memory_summaries`
Canonical summary records above memory items.

Key fields include:

- `memory_summary_id`
- `workspace_id`
- `episode_id`
- `summary_text`
- `summary_kind`
- `metadata_json`

### `memory_summary_memberships`
Canonical parent-child membership edges from a summary to member memory items.

Key fields include:

- `memory_summary_membership_id`
- `memory_summary_id`
- `memory_id`
- `membership_order`
- `metadata_json`

The minimal implemented hierarchy is best understood as:

- `summary -> memory_item`

This is a canonical relational hierarchy, not a graph-native truth model.

## 7.5 Layer flow

The current system can be read as a flow across layers:

- workflow and checkpoint activity is recorded canonically
- meaningful work can produce episodes
- episodes and workflow automation can produce memory items
- memory items may receive embeddings
- memory items may be linked through relations
- memory items may be grouped under summaries
- retrieval can surface grouped context through summary-first or episode-oriented assembly

That layered model is one of the defining technical features of `ctxledger`.

### 7.6 Multi-layer memory diagram

```/dev/null/technical-overview-memory-layers.mmd#L1-14
flowchart TD
    L1["Layer 1: Workflow state"]
    L2["Layer 2: Episodic memory"]
    L3["Layer 3: Semantic / procedural memory"]
    L4["Layer 4: Hierarchical memory"]

    W["workflow / checkpoint activity"]
    E["episodes"]
    M["memory_items / memory_relations / memory_embeddings"]
    S["memory_summaries / memory_summary_memberships"]
    R["grouped retrieval surfaces"]

    W --> L1 --> E --> L2 --> M --> L3 --> S --> L4 --> R
```

---

## 8. Retrieval Architecture

The retrieval model is intentionally split across operational and memory-oriented entry points.

This is a core part of the design rather than a naming preference.

## 8.1 `workflow_resume`

`workflow_resume` is the operational resume path.

It should be used for:

- exact continuation
- current workflow status
- current attempt status
- latest checkpoint
- latest verify status

It returns canonical workflow truth, not ranked support context.

## 8.2 `memory_get_context`

`memory_get_context` is a support-context retrieval surface.

It is currently:

- workflow-linked
- hierarchy-aware
- relation-aware in a bounded way
- explicit about primary vs auxiliary outputs
- explainable through additive `details`

The request supports lookup inputs such as:

- `query`
- `workspace_id`
- `workflow_instance_id`
- `ticket_id`

and shaping flags such as:

- `limit`
- `include_episodes`
- `include_memory_items`
- `include_summaries`
- `primary_only`

### `primary_only`
`primary_only = true` is a response-shaping preference.

It should be read as:

- preserve the grouped primary surface
- preserve route and selection metadata needed to interpret that surface
- omit flatter compatibility-oriented fields where appropriate

It is not a different retrieval algorithm.

## 8.3 Current grouped scopes

The current grouped output model distinguishes scopes such as:

- `summary`
- `episode`
- `workspace`
- `relation`

These scopes help explain where surfaced context came from.

## 8.4 Current retrieval routes

The current retrieval model distinguishes routes including:

- `summary_first`
- `episode_direct`
- `workspace_inherited_auxiliary`
- `relation_supports_auxiliary`
- `graph_summary_auxiliary`

These route names matter because `ctxledger` does not treat all returned context as equivalent.

The grouped output is intended to help readers understand:

- what was returned
- why it was returned
- what was primary
- what was auxiliary

## 8.5 Summary-first retrieval

The current hierarchy-aware retrieval posture is summary-first where summaries are available and enabled.

At a high level, the current bounded path is:

1. resolve candidate workflows
2. collect workflow-linked episodes
3. apply lightweight query filtering when requested
4. choose the primary visible path
5. include direct episode memory where appropriate
6. optionally add inherited workspace memory
7. optionally add bounded relation-supported memory
8. expose grouped and route-aware details

This gives `ctxledger` a retrieval model that is more structured than flat episode listing, while still preserving boundedness and explainability.

## 8.6 `memory_search`

`memory_search` provides bounded lexical and embedding-backed retrieval over memory items.

The current implementation includes:

- lexical scoring over content
- lexical scoring over metadata keys and values
- optional embedding-based scoring when configured
- hybrid ranking across persisted memory items
- workspace-scoped retrieval
- bounded task-recall integration
- interaction-aware and file-work-aware filtering behavior

This means `memory_search` is not just a thin vector-search wrapper.  
It is a bounded retrieval service over canonical memory with explicit explanation surfaces.

### 8.7 Retrieval architecture diagram

```/dev/null/technical-overview-retrieval-flow.mmd#L1-18
flowchart TD
    Input["Client request"]
    Resume["workflow_resume"]
    Context["memory_get_context"]
    Search["memory_search"]

    Canonical["Canonical workflow + memory state"]
    Grouped["Grouped primary / auxiliary context"]
    Hybrid["Hybrid lexical + embedding ranking"]
    Output["Client-visible response"]

    Input --> Resume --> Canonical --> Output
    Input --> Context --> Canonical --> Grouped --> Output
    Input --> Search --> Canonical --> Hybrid --> Output
```

---

## 9. PostgreSQL Technology Map

One of the most important aspects of `ctxledger` is how it uses PostgreSQL across layers.

The system is not just "PostgreSQL-backed" in a generic sense. Relational constraints, `JSONB`, vector support, and pooled runtime access all materially shape the architecture.

## 9.1 Relational tables and foreign keys

Canonical workflow and memory ownership is relational.

The schema relies on:

- primary keys
- foreign keys
- unique constraints
- ordinary indexes
- partial indexes
- timestamps and update triggers

This is the backbone of the system.

## 9.2 `JSONB`

`JSONB` is used extensively for structured metadata and evolving payloads.

Representative uses include:

- `workspaces.metadata_json`
- `workflow_instances.metadata_json`
- `workflow_checkpoints.checkpoint_json`
- `verify_reports.report_json`
- `artifacts.metadata_json`
- `failures.details_json`
- `episodes.metadata_json`
- `memory_items.metadata_json`
- `memory_relations.metadata_json`
- `memory_summaries.metadata_json`
- `memory_summary_memberships.metadata_json`

`JSONB` is an important part of the design because it preserves extensibility without flattening every concept into columns too early.

## 9.3 Unique and partial indexes

The schema uses indexing not only for performance but also for business rules.

Examples include:

- one running workflow per workspace
- one running attempt per workflow
- unique embedding per memory item and model
- unique summary membership per summary and memory item
- unique relation per source, target, and type

This makes PostgreSQL part of the invariant-enforcement story, not just a passive store.

## 9.4 `pgvector`

The schema enables the `vector` extension and stores embeddings in:

- `memory_embeddings.embedding VECTOR(1536)`

It also defines an HNSW index:

- `idx_memory_embeddings_embedding_hnsw`

This makes `pgvector` the vector-similarity support layer for bounded semantic retrieval.

## 9.5 Apache AGE posture

The repository design documents treat Apache AGE as:

- optional
- derived
- rebuildable
- non-canonical

That posture matches the intended architecture.

AGE-backed support should be understood as graph-oriented retrieval assistance layered over canonical relational records, especially summaries and memory relations.

It should not be described as the canonical owner of hierarchy.

## 9.6 Shared pool and unit-of-work posture

The runtime uses a shared pooled PostgreSQL posture.

The current implementation direction includes:

- process-scoped shared pool ownership
- transaction-scoped unit-of-work usage
- explicit pooled connection borrowing
- bootstrap paths aligned around explicit pool ownership

This is an important technical characteristic because `ctxledger` is designed as a real durable runtime, not just a stateless facade.

---

## 10. Relational Data Model Summary

The current relational model can be grouped into several clusters.

This grouping is intended to make the architecture easier to read; the actual schema remains the source of truth for exact columns, constraints, and indexes.

## 10.1 Workflow cluster

Core entities:

- `workspaces`
- `workflow_instances`
- `workflow_attempts`
- `workflow_checkpoints`
- `verify_reports`

Relationship shape:

- a workspace owns workflows
- a workflow owns attempts
- a workflow and attempt own checkpoints
- an attempt owns verify reports

## 10.2 Support and operational metadata cluster

Support entities:

- `artifacts`
- `failures`

These record durable metadata about:

- external artifacts
- structured failures
- workflow, attempt, checkpoint, episode, or memory-linked failure state

They are not the same thing as workflow progression or semantic memory, but they are part of the durable technical model.

## 10.3 Episodic memory cluster

Core entities:

- `episodes`
- `episode_events`
- `episode_summaries`
- `episode_failures`
- `episode_artifacts`

Relationship shape:

- a workflow owns episodes
- an episode may link to an attempt
- an episode owns events, summaries, failures, and artifact links

## 10.4 Semantic memory cluster

Core entities:

- `memory_items`
- `memory_embeddings`
- `memory_relations`

Relationship shape:

- a workspace may own memory items directly
- an episode may own memory items
- a memory item may have embeddings
- memory items may link to one another through typed relations

## 10.5 Hierarchical memory cluster

Core entities:

- `memory_summaries`
- `memory_summary_memberships`

Relationship shape:

- a workspace owns summaries
- a summary may link to an episode
- a summary owns memberships
- a membership points to a `memory_item`

The design intentionally keeps:

- summary membership
- semantic memory relations

as separate concepts.

That separation is one of the cleanest architectural choices in the memory model.

### 10.6 Relational structure diagrams

#### Workflow ER view

```/dev/null/technical-overview-workflow-er.mmd#L1-13
erDiagram
    workspaces ||--o{ workflow_instances : owns
    workflow_instances ||--o{ workflow_attempts : has
    workflow_instances ||--o{ workflow_checkpoints : has
    workflow_attempts ||--o{ workflow_checkpoints : owns
    workflow_attempts ||--o{ verify_reports : has
```

#### Memory ER view

```/dev/null/technical-overview-memory-er.mmd#L1-20
erDiagram
    workflow_instances ||--o{ episodes : owns
    workflow_attempts o|--o{ episodes : may_link
    episodes ||--o{ episode_events : has
    episodes ||--o{ episode_summaries : has
    episodes ||--o{ episode_failures : has
    episodes ||--o{ episode_artifacts : has
    workspaces ||--o{ memory_items : owns
    episodes o|--o{ memory_items : may_link
    memory_items ||--o{ memory_embeddings : has
    memory_items ||--o{ memory_relations : source
    memory_items ||--o{ memory_relations : target
    workspaces ||--o{ memory_summaries : owns
    episodes o|--o{ memory_summaries : may_link
    memory_summaries ||--o{ memory_summary_memberships : has
    memory_items ||--o{ memory_summary_memberships : member
```

---

## 11. Graph Posture and AGE-Backed Support

Graph support in `ctxledger` should be read carefully.

## 11.1 What graph support is for

Graph-backed support is intended to help with bounded traversal and retrieval assistance where relational lookup alone becomes awkward.

In particular, graph support is relevant to:

- summary mirroring
- bounded hierarchy traversal
- auxiliary graph-backed retrieval signals

## 11.2 What graph support is not

Graph support is not:

- canonical hierarchy ownership
- the primary truth source
- required for ordinary relational retrieval correctness

If graph state is missing, stale, or degraded, canonical relational state still remains authoritative.

## 11.3 Minimal graph shape

The most meaningful bounded graph shape to describe is:

- summary nodes
- memory item nodes
- membership edges from summary to memory item
- semantic relation edges where implemented and useful

In conceptual terms:

- `memory_summary` node
- `memory_item` node
- `summarizes`-like membership edge
- relation edges such as bounded `supports`-style semantic links where surfaced

## 11.4 Why this posture matters

This posture keeps `ctxledger` PostgreSQL-first.

It avoids the common mistake of treating graph capability as equivalent to graph-owned truth.

### 11.5 Graph posture diagram

```/dev/null/technical-overview-graph-posture.mmd#L1-13
flowchart LR
    Canonical["Canonical relational state"]
    Summary["memory_summaries"]
    Membership["memory_summary_memberships"]
    Memory["memory_items"]
    Graph["Derived AGE graph support"]

    Canonical --> Summary
    Canonical --> Membership
    Canonical --> Memory
    Summary --> Graph
    Membership --> Graph
    Memory --> Graph
```

---

## 12. Interaction, File-Work, and Failure-Reuse Memory

The `0.9.0` strengthening work is not just about more memory volume.  
It broadens what counts as useful retrieval-ready memory.

## 12.1 Interaction memory

The memory layer supports interaction-oriented memory through `memory_items` with interaction-oriented metadata.

This allows user requests and agent responses to become retrieval-ready memory without competing with workflow truth.

## 12.2 File-work metadata

The service layer normalizes and filters metadata such as:

- `file_name`
- `file_path`
- `file_operation`
- `purpose`

This is important because `ctxledger` is not only tracking abstract lessons.  
It is also capturing bounded file-work context useful for later recall.

## 12.3 Failure reuse

Failure and recovery information is represented in multiple places:

- `failures`
- episode-linked failure records
- memory items
- memory relations
- retrieval-oriented support context

This supports bounded failure-pattern reuse and recovery recall.

## 12.4 Why these matter

These additions make the memory model more useful for:

- resumability
- bounded historical lookup
- failure avoidance
- repeated-work reduction

without turning memory into a competing workflow-truth system.

---

## 13. Operational Characteristics and Observability

Several technical characteristics matter for operators and contributors.

## 13.1 Shared connection-pool ownership

The current runtime posture uses:

- explicit shared PostgreSQL pool ownership
- transaction-scoped unit-of-work execution
- explicit bootstrap and shutdown handling

This matters for durability, throughput, and resume-path stability.

## 13.2 HTTP MCP runtime posture

The currently evidenced primary serving path is the authenticated HTTP MCP runtime at `/mcp`.

The repository evidences bounded support for:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`

## 13.3 Tool and resource posture

Implemented tools include:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`
- `memory_remember_episode`
- `memory_get_context`
- `memory_search`

Implemented workflow resources include:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

## 13.4 Observability posture

Operator-facing observability includes CLI surfaces and supported metrics.

Notable memory and hierarchy-related metrics include:

- `memory_summary_count`
- `memory_summary_membership_count`
- `age_summary_graph_ready_count`
- `age_summary_graph_stale_count`
- `age_summary_graph_degraded_count`
- `age_summary_graph_unknown_count`

These should be interpreted in this order:

1. canonical summary volume first
2. derived graph posture second

A degraded graph posture should not be read as canonical summary loss if relational summary metrics remain healthy.

---

## 14. Boundaries and Non-Goals

The following constraints are important to preserve when reading or extending the system.

### 14.1 Graph is not canonical truth

Graph-backed support may help retrieval, but canonical ownership remains relational.

### 14.2 Memory retrieval is not workflow execution

A strong memory result is not the same thing as exact resumable workflow state.

### 14.3 Repository files are not the source of truth

Files in the repository may be useful projections or review artifacts, but they are not canonical state.

### 14.4 `primary_only` is not a different retrieval algorithm

It is a response-shaping mode over the same retrieval behavior.

### 14.5 Bounded historical recall is not unconstrained QA

The memory subsystem is designed for bounded retrieval over durable workflow and memory records, not arbitrary universal question answering.

### 14.6 Hierarchy is not the same thing as generic relation graphs

Summary membership and semantic memory relations are intentionally distinct.

---

## 15. Summary

The most important technical characteristics of `ctxledger` are:

- PostgreSQL-first canonical workflow and memory ownership
- explicit separation between workflow control and memory retrieval
- a multi-layer memory model spanning workflow, episodic, semantic, and hierarchical layers
- bounded vector-backed retrieval through `pgvector`
- bounded, derived, non-canonical graph-backed support through AGE
- route-aware and grouped memory retrieval rather than flat retrieval only
- a durable MCP-facing runtime designed for resumability and operational continuity

Taken together, these choices make `ctxledger` more than a workflow tracker and more than a memory index.

It is a durable operational runtime whose memory system is layered, bounded, explainable, and anchored in canonical relational truth.