# Connection Pooling 0.5.1 Plan

## 1. Purpose

This document defines the implementation plan for the `0.5.1` milestone.

The goal of `0.5.1` is to introduce **PostgreSQL connection pooling** into `ctxledger` using `psycopg-pool` as a targeted internal refactoring and reliability improvement.

This milestone intentionally prioritizes:

- replacing per-request direct PostgreSQL connection creation with pooled acquisition
- improving runtime stability for repeated workflow and memory operations
- reducing connection setup overhead
- bringing implementation behavior closer to the architecture documentation
- preserving current external behavior while improving internal database access discipline

This milestone does **not** change the canonical storage model.

PostgreSQL remains the canonical system of record.

---

## 2. Why this milestone exists

The current implementation path opens a fresh PostgreSQL connection for each unit of work.

That model is simple, but it has clear drawbacks:

- repeated connection setup overhead
- higher sensitivity to bursty request patterns
- weaker control over connection reuse
- more exposure to transient connection latency during request handling
- mismatch with the repository architecture documentation, which already describes a PostgreSQL connection pool

Recent investigation triggered by a `workflow_resume` timeout reinforced that this area deserves focused attention before starting broader `0.6.0` work.

Even if connection creation is not the only possible cause of timeout behavior, pooling is still a high-value hardening step because it:

- improves operational efficiency
- reduces avoidable connection churn
- creates a better foundation for future observability and performance debugging
- aligns the runtime with the intended process model

`0.5.1` therefore exists as a small, explicit follow-up refactoring milestone between `0.5.0` and `0.6.0`.

---

## 3. Milestone intent

## 3.1 Primary objective

Introduce `psycopg-pool` so that a running `ctxledger` process owns a shared PostgreSQL connection pool and each request or command obtains a transaction-scoped connection from that pool.

## 3.2 Secondary objectives

- make connection lifecycle behavior more explicit and testable
- preserve the existing unit-of-work pattern
- avoid broad service-layer rewrites
- prepare the runtime for better timeout handling and future query instrumentation
- eliminate the current docs/implementation mismatch around connection pooling

## 3.3 Non-objectives

`0.5.1` should **not** become:

- a broad database abstraction rewrite
- a migration away from `psycopg`
- an async database migration
- a general performance milestone with many unrelated optimizations
- a pretext for changing workflow or memory semantics
- a graph/AGE preparation milestone
- a redesign of canonical schemas or query semantics

---

## 4. Scope of 0.5.1

## 4.1 In scope

### PostgreSQL connection pooling
Adopt `psycopg-pool` for PostgreSQL-backed runtime/database access.

### Unit-of-work integration
Update the PostgreSQL unit-of-work implementation so it borrows a connection from a shared pool and returns it correctly.

### Runtime lifecycle integration
Ensure long-lived process entry points initialize and own the pool appropriately.

### CLI compatibility
Ensure CLI operations that use PostgreSQL-backed services can use the same pooling-aware construction path without changing user-facing command behavior.

### Configuration support
Add explicit configuration for connection pool sizing and pool-related waits/timeouts as needed.

### Validation and regression coverage
Add tests that prove pooled acquisition works and that existing workflow/memory operations still behave correctly.

### Documentation alignment
Update architecture and operational docs so they accurately describe what is implemented.

## 4.2 Out of scope

The following should remain outside `0.5.1` unless needed for correctness:

- SQL query redesign unrelated to pooling
- large-scale query batching
- schema redesign
- HTTP transport redesign
- MCP protocol redesign
- workflow feature expansion
- memory retrieval feature expansion
- hierarchical memory work
- Apache AGE introduction
- broad observability feature expansion

---

## 5. Current-state summary

## 5.1 Current implementation shape

The current PostgreSQL path is effectively:

1. settings are loaded
2. a PostgreSQL unit-of-work factory is built
3. each unit of work opens a fresh connection
4. repository objects are bound to that connection
5. the transaction is committed or rolled back
6. the connection is closed

This is functionally correct for small loads, but it means connection setup is repeatedly paid during normal operation.

## 5.2 Current documented intent

The architecture documentation already describes a running process as owning:

- validated runtime configuration
- PostgreSQL connection pool
- transport adapter initialization
- startup/shutdown lifecycle management

That means the implementation should move toward this documented process model rather than forcing docs to regress to the current non-pooled behavior.

## 5.3 Relevant operational concern

The recent `workflow_resume` timeout does not, by itself, prove that fresh connection creation is the sole root cause.

However, the current implementation has characteristics that make timeout analysis harder:

- no pooled reuse
- no explicit pool wait visibility
- statement timeout currently may be unbounded by default
- request timing is not yet richly instrumented

Connection pooling is therefore justified both as an efficiency improvement and as a prerequisite for clearer operational behavior.

---

## 6. Design principles

## 6.1 Preserve behavior at the service boundary

The service layer should continue to see a unit-of-work abstraction.

Pooling should improve internals without forcing broad service API changes.

## 6.2 One shared pool per long-lived process

For server/runtime usage, a process should own a shared pool rather than constructing ad hoc pools per request.

## 6.3 Transaction scope remains explicit

Borrowing a pooled connection must not blur transaction boundaries.

Each unit of work should still clearly define:

- connection acquisition
- session setting application
- transaction commit/rollback
- connection return to the pool

## 6.4 Keep in-memory and PostgreSQL paths conceptually parallel

The in-memory unit-of-work path should not be distorted by pooling concerns.

Pooling is a PostgreSQL implementation detail, not a global architectural rule.

## 6.5 Make failure modes observable

Pool exhaustion, acquisition timeout, and connection initialization problems should be diagnosable.

## 6.6 Prefer minimal invasive change

Do not redesign repository interfaces unless pooling truly requires it.

---

## 7. Proposed architecture

## 7.1 High-level target model

The target process model should be:

1. application settings are loaded
2. PostgreSQL pool configuration is derived
3. a shared pool is created for the process
4. services receive a unit-of-work factory that acquires from the shared pool
5. each unit of work:
   - acquires a connection from the pool
   - applies session settings
   - creates repositories bound to that connection
   - commits or rolls back
   - returns the connection to the pool
6. process shutdown closes the pool cleanly

## 7.2 Pool ownership

Pool ownership should live at the runtime/bootstrap boundary, not inside individual repositories.

Likely ownership candidates:

- top-level server bootstrap
- CLI/service construction helper layer
- dedicated database runtime helper module

The key rule is that repository calls must not create or own the pool themselves.

## 7.3 Unit-of-work role after refactor

`PostgresUnitOfWork` should continue to be the transaction boundary.

Its role changes from:

- “open a brand-new connection”

to:

- “borrow a connection from the shared pool and manage the transaction over it”

## 7.4 Session settings

Session settings already applied today should continue to be applied for each borrowed connection as needed, including:

- `statement_timeout`
- `search_path`

Implementation should consider whether these settings should be:

- applied on every acquisition, or
- partially enforced at pool connection-configuration time

The default should favor correctness and predictability over micro-optimization.

---

## 8. Configuration plan

## 8.1 New likely settings

Add explicit pool-related settings, likely including:

- `CTXLEDGER_DB_POOL_MIN_SIZE`
- `CTXLEDGER_DB_POOL_MAX_SIZE`
- `CTXLEDGER_DB_POOL_TIMEOUT_SECONDS`

Optional additional settings may include:

- connection max lifetime
- max idle time
- pool open/warmup policy

## 8.2 Configuration principles

- defaults should be safe for local development
- defaults should not create excessive idle connections
- configuration should remain simple for small deployments
- settings validation should reject nonsensical values cleanly

## 8.3 Initial default direction

A reasonable starting point is a conservative pool profile suitable for local/internal deployments.

Example direction:

- min size small
- max size modest
- acquisition timeout explicit and finite

Exact default values should be chosen during implementation review, but they should be documented and validated.

---

## 9. Implementation phases

## 9.1 Phase 1: Inventory and design confirmation

### Goals
- confirm the current bootstrap and unit-of-work call graph
- identify all process entry points that build PostgreSQL-backed services
- decide where pool ownership belongs
- define exact configuration additions

### Tasks
- trace server bootstrap path
- trace CLI PostgreSQL service construction path
- identify any tests that assume direct connection creation
- define pool lifecycle expectations for runtime and CLI contexts

### Deliverable
A confirmed implementation sketch with ownership and lifecycle boundaries.

---

## 9.2 Phase 2: Introduce pooling primitives

### Goals
- add `psycopg-pool` dependency
- define a pooling-aware PostgreSQL configuration/runtime helper
- construct a reusable pool abstraction

### Tasks
- update dependency configuration
- add a small pooling helper or builder
- define pool configuration data structure(s)
- add validation for pool-related settings
- keep direct connection code isolated long enough for an incremental migration

### Deliverable
A compilable/testable pooling foundation with no broad behavior changes yet.

---

## 9.3 Phase 3: Refactor unit-of-work to acquire from the pool

### Goals
- make `PostgresUnitOfWork` use pooled connections
- preserve existing repository behavior
- preserve transaction semantics

### Tasks
- replace direct connection creation in the PostgreSQL unit of work
- ensure commit/rollback behavior remains explicit
- ensure connection return happens reliably on both success and failure
- confirm session settings are still applied correctly

### Deliverable
A pooling-backed unit-of-work implementation.

---

## 9.4 Phase 4: Integrate process lifecycle

### Goals
- ensure long-lived runtime processes own and close the pool correctly
- ensure CLI code paths do not create redundant pools unnecessarily

### Tasks
- wire pool creation into server bootstrap
- wire pool-aware service construction into CLI helpers
- define close/shutdown behavior for server processes
- make sure tests can construct lightweight pool-backed services cleanly

### Deliverable
Shared pool ownership across real runtime entry points.

---

## 9.5 Phase 5: Validation and failure-path hardening

### Goals
- prove behavior preservation
- validate pooled acquisition and cleanup
- improve diagnosability of pool-related failures

### Tasks
- add unit tests for configuration validation
- add tests for unit-of-work acquisition/release behavior
- add integration coverage for representative workflow operations
- add failure-path coverage for pool acquisition or initialization errors
- consider targeted logging around pool acquisition timing and failures

### Deliverable
Confidence that pooling improves internals without breaking existing behavior.

---

## 10. Detailed design questions to resolve

## 10.1 Pool ownership for CLI

A CLI invocation is short-lived, so the benefit profile differs from a long-lived server.

Questions:

- should the CLI still use a pool for consistency?
- should the CLI create a small ephemeral pool per invocation?
- should there be a shared helper that can support both server and CLI lifecycles cleanly?

Current leaning:

- prefer one implementation model if it remains simple
- do not introduce a separate parallel connection strategy unless necessary

## 10.2 Pool initialization strategy

Questions:

- should the pool be eagerly opened at startup?
- should it open lazily on first use?
- how should startup failures surface?

Current leaning:

- server/runtime paths may benefit from eager validation
- CLI paths may tolerate simpler lazy usage if behavior remains clear

## 10.3 Session settings application

Questions:

- should `statement_timeout` and `search_path` be re-applied on every acquisition?
- can any of them safely be pushed into pool connection setup hooks?
- what behavior is safest if connections are reused?

Current leaning:

- re-apply required session settings when the unit of work starts unless a safer initialization hook is clearly preferable

## 10.4 Pool exhaustion behavior

Questions:

- what error should surface if no connection becomes available in time?
- how should this be distinguished from general database unavailability?
- should pool wait timeout messages be operator-facing?

Current leaning:

- surface a distinct, diagnosable error path
- keep operator-visible messaging explicit and not overly generic

---

## 11. Validation plan

## 11.1 Unit coverage

Add or update tests covering:

- pool-related configuration parsing and validation
- pool builder behavior
- unit-of-work lifecycle under success
- unit-of-work lifecycle under exception/rollback
- session settings application with borrowed connections

## 11.2 Integration coverage

Representative PostgreSQL integration tests should continue to pass for:

- workspace registration
- workflow start
- workflow checkpoint
- workflow resume
- workflow complete
- projection failure flows
- memory operations already covered by existing integration suites

## 11.3 Regression focus

Special attention should be paid to:

- transaction commit behavior
- rollback behavior
- connection leakage
- reuse safety after failures
- runtime startup/shutdown correctness

## 11.4 Manual verification suggestions

Useful manual checks include:

- repeated `resume-workflow` invocations under the same running server
- repeated tool calls under HTTP runtime
- confirmation that connections are reused rather than constantly re-created
- observation of pool behavior under small bursts of requests

---

## 11.5 Execution checklist

The following checklist is intended to turn the `0.5.1` plan into a concrete implementation sequence.

### Dependency and packaging
- add `psycopg-pool` to project dependencies
- verify dependency lock/update flow remains clean
- confirm runtime and test environments can import the pool package

### Configuration
- add pool-related settings to typed configuration
- validate:
  - minimum size
  - maximum size
  - acquisition timeout
- ensure invalid values fail early and clearly
- document default values and intended usage

### Pool construction
- add a small PostgreSQL pool builder/helper
- keep pool ownership outside repositories
- define whether pool startup is eager or lazy for:
  - server/runtime paths
  - CLI paths
- define clean shutdown behavior

### Unit-of-work refactor
- change PostgreSQL unit-of-work construction to borrow a pooled connection
- preserve explicit:
  - session setting application
  - commit behavior
  - rollback behavior
  - connection return behavior
- confirm repository binding remains unchanged from the service layer perspective

### Bootstrap integration
- update server bootstrap to own and reuse a shared pool
- update CLI PostgreSQL-backed service construction to use the pooling-aware path
- avoid accidental creation of multiple redundant pools inside one process

### Failure handling
- define how pool acquisition timeout surfaces
- distinguish pool exhaustion from generic database connectivity failure where practical
- keep error messages diagnosable without changing user-facing semantics unnecessarily

### Validation
- add focused unit coverage for pool configuration and acquisition lifecycle
- run PostgreSQL integration coverage for:
  - workspace registration
  - workflow start
  - workflow checkpoint
  - workflow resume
  - workflow complete
  - projection failure flows
- manually verify repeated PostgreSQL-backed operations reuse pooled connections as expected

### Documentation closeout
- update any remaining docs that describe connection lifecycle
- ensure docs no longer imply pooled behavior is already implemented unless it truly is
- keep roadmap, architecture, and implementation-plan language consistent

## 11.6 Code-level design sketch

This section turns the implementation checklist into a minimal code-shape proposal so the next work loop can start with fewer architectural ambiguities.

### Design goals

The code-level refactor should:

- preserve the current service and repository APIs as much as possible
- keep connection-pool ownership outside repository classes
- preserve the current unit-of-work transaction boundary
- minimize branching between server and CLI paths
- allow pool-aware construction to be introduced incrementally

### Proposed touched files

Primary implementation files likely include:

- `pyproject.toml`
- `src/ctxledger/config.py`
- `src/ctxledger/db/postgres.py`
- `src/ctxledger/runtime/server_factory.py`
- `src/ctxledger/server.py`
- `src/ctxledger/__init__.py`

Representative validation files likely include:

- PostgreSQL integration tests
- workflow service tests that depend on PostgreSQL-backed construction
- server/bootstrap tests that validate startup and shutdown behavior

### Proposed configuration shape

Extend the database settings model with explicit pool configuration.

Likely direction:

- `DatabaseSettings`
  - `url`
  - `connect_timeout_seconds`
  - `statement_timeout_ms`
  - `schema_name`
  - `pool_min_size`
  - `pool_max_size`
  - `pool_timeout_seconds`

Likely environment variables:

- `CTXLEDGER_DB_POOL_MIN_SIZE`
- `CTXLEDGER_DB_POOL_MAX_SIZE`
- `CTXLEDGER_DB_POOL_TIMEOUT_SECONDS`

Validation rules should likely include:

- minimum size must be greater than or equal to zero
- maximum size must be greater than zero
- maximum size must be greater than or equal to minimum size
- pool timeout must be greater than zero

### Proposed PostgreSQL config shape

Extend `PostgresConfig` so it can carry both existing session settings and new pool settings.

Likely direction:

- keep:
  - `database_url`
  - `connect_timeout_seconds`
  - `statement_timeout_ms`
  - `schema_name`
- add:
  - `pool_min_size`
  - `pool_max_size`
  - `pool_timeout_seconds`

This preserves the existing `PostgresConfig.from_settings(...)` pattern and avoids introducing a parallel configuration translation path.

### Proposed new pool builder layer

Add a small helper in `src/ctxledger/db/postgres.py` responsible for constructing a PostgreSQL connection pool.

Likely responsibilities:

- import and validate `psycopg_pool`
- build a pool from `PostgresConfig`
- configure row factory compatibility
- apply connection-level defaults where safe
- expose explicit open and close semantics

A likely minimal helper shape is:

- `build_connection_pool(config: PostgresConfig) -> ConnectionPool`

If a thin wrapper improves lifecycle clarity, an alternative is:

- `class PostgresConnectionPoolHandle`
- `def build_connection_pool_handle(config: PostgresConfig) -> PostgresConnectionPoolHandle`

Current leaning:
- prefer the simpler direct-builder approach unless shutdown/lifecycle wiring becomes awkward

### Proposed unit-of-work constructor change

Today, `PostgresUnitOfWork` owns a `PostgresConfig` and opens a fresh connection in `__enter__()`.

The likely refactor is:

- constructor accepts:
  - `config`
  - shared pool
- `__enter__()` borrows a connection from the pool
- borrowed connection is used exactly like the current direct connection
- `__exit__()` rolls back if needed and returns the connection to the pool

Conceptually, the class changes from:

- configuration-owned connection creation

to:

- configuration-guided pooled connection borrowing

This should preserve the current repository binding logic:

- `self.workspaces = PostgresWorkspaceRepository(self._conn)`
- `self.workflow_instances = PostgresWorkflowInstanceRepository(self._conn)`
- and so on

### Proposed unit-of-work factory change

Today:

- `build_postgres_uow_factory(config)` returns a factory that builds `PostgresUnitOfWork(config)`

Likely new shape:

- `build_postgres_uow_factory(config, pool)` returns a factory that builds `PostgresUnitOfWork(config, pool)`

This is the smallest likely interface change and keeps all downstream service code stable.

### Proposed server bootstrap integration

The current server path builds a workflow service factory from settings, and that service factory internally builds a PostgreSQL unit-of-work factory.

The likely target shape is:

1. server bootstrap derives `PostgresConfig`
2. server bootstrap creates one shared pool
3. server bootstrap passes the pool into workflow service factory construction
4. `CtxLedgerServer.startup()` may explicitly open/validate the pool if eager startup is chosen
5. `CtxLedgerServer.shutdown()` closes the pool cleanly

This implies `build_workflow_service_factory(settings)` likely becomes something closer to:

- `build_workflow_service_factory(settings, pool=None)`

or a stricter variant:

- `build_workflow_service_factory(settings, *, connection_pool)`

Current leaning:
- prefer explicit pool injection once the pool exists
- avoid hidden pool creation inside the workflow service factory

### Proposed CLI integration

The CLI currently builds PostgreSQL-backed services through a helper that loads settings and constructs a workflow service directly.

The likely target shape is:

- create a small shared PostgreSQL bootstrap helper
- let both server and CLI use that helper
- allow the CLI to create a short-lived pool for the process lifetime of the command
- close the pool before process exit

This avoids maintaining:

- one direct-connection bootstrap path for CLI
- one pooled bootstrap path for server

A single construction model is preferable unless it becomes materially more complex.

### Proposed health-check handling

The database health checker currently uses direct connection creation.

This area needs an explicit decision.

Two reasonable options:

1. keep health checks on direct one-shot connections
2. allow health checks to use the same shared pool

Current leaning:
- keep the health checker simple unless pool lifecycle integration is straightforward
- do not block the main unit-of-work pooling refactor on fully unifying the health-check path

That means the first implementation may pool application work paths while leaving readiness checks as direct connections if that keeps the change safer and smaller.

### Proposed session-setting strategy

The current implementation applies:

- `statement_timeout`
- `search_path`

inside unit-of-work startup.

That behavior should likely remain in the unit of work even after pooling because it guarantees session normalization for every borrowed connection.

This reduces the risk that a reused connection carries stale session state from a prior operation.

### Proposed error-handling strategy

Likely new or clarified failure cases include:

- pool package unavailable
- pool initialization failure
- pool acquisition timeout
- borrowed connection failure during use
- pool shutdown failure

Preferred behavior:

- keep low-level pool errors inside infrastructure/bootstrap layers
- translate them into existing runtime/bootstrap error categories where practical
- preserve enough detail for logs and diagnostics

### Proposed test strategy at code level

Add tests around the new construction seams rather than only broad end-to-end coverage.

High-value targets:

- config parsing and validation for pool settings
- pool builder behavior under valid and invalid config
- unit-of-work borrowing and release behavior
- rollback behavior after exceptions
- server startup/shutdown behavior with pool ownership
- CLI bootstrap behavior for short-lived pooled execution

### Preferred incremental implementation order

The smallest-risk coding sequence is likely:

1. add dependency
2. add typed config fields and validation
3. add `PostgresConfig` pool fields
4. add pool builder
5. update unit-of-work constructor and factory to accept a pool
6. wire workflow service factory to use pooled unit-of-work creation
7. wire server startup/shutdown ownership
8. unify or adapt CLI bootstrap
9. add/refresh tests
10. update any remaining docs

This order keeps each change reviewable and makes it easier to isolate regressions.

## 12. Observability considerations

## 12.1 Immediate observability minimum

At minimum, the implementation should make it easier to reason about:

- whether pool initialization succeeded
- whether acquisition timed out
- whether a borrowed connection was returned
- whether session settings were applied

## 12.2 Optional follow-up observability

If low-risk, consider lightweight logging or counters for:

- acquisition latency
- number of active/borrowed connections
- pool exhaustion events

These are useful, but should not delay the main refactor if they create disproportionate scope.

---

## 13. Risks and mitigations

## 13.1 Risk: connection lifecycle bugs

Pooling changes the ownership model of connections and can introduce subtle leaks.

### Mitigation
- keep lifecycle logic concentrated in one place
- add tests for success and exception paths
- prefer explicit cleanup over implicit assumptions

## 13.2 Risk: session contamination across reused connections

A reused connection may retain unexpected session state if settings are not normalized.

### Mitigation
- explicitly apply required session settings at unit-of-work start
- keep session customization minimal and deliberate

## 13.3 Risk: CLI complexity grows

A short-lived CLI may gain extra bootstrap complexity from pooling.

### Mitigation
- keep CLI integration thin
- share bootstrap helpers where possible
- avoid over-engineering CLI-specific pooling behavior

## 13.4 Risk: timeout root cause is only partially addressed

If the original `workflow_resume` timeout was caused by locks or slow queries, pooling alone will not fully solve it.

### Mitigation
- treat pooling as a reliability refactor, not as a guaranteed full cure
- keep timeout investigation open
- follow with query/lock instrumentation if needed

---

## 14. Success criteria

`0.5.1` should be considered successful when:

- `psycopg-pool` is adopted in the PostgreSQL runtime path
- long-lived runtime processes own a shared PostgreSQL pool
- PostgreSQL unit-of-work instances borrow and return pooled connections correctly
- existing behavior remains intact at the service/API level
- representative tests remain green
- architecture and related docs match the actual implementation
- the codebase is better positioned for future timeout analysis and runtime hardening

---

## 15. Deferred follow-up items

The following are good candidates after `0.5.1`, but should not block it:

- explicit query timing instrumentation
- richer pool metrics exposure
- default finite `statement_timeout` policy review
- lock/contention diagnostics for resume-related paths
- targeted optimization of multi-query read paths such as `workflow_resume`
- broader database performance and observability improvements

---

## 16. Immediate next steps

1. confirm the exact pool ownership boundary for server and CLI bootstrap
2. define the initial pool-related settings and validation rules
3. add `psycopg-pool` to dependencies
4. implement a pool builder/helper with clean lifecycle semantics
5. refactor `PostgresUnitOfWork` to borrow from the pool
6. run focused tests on workflow and PostgreSQL integration paths
7. update architecture and any operational docs that mention connection lifecycle

---

## 17. Version framing

`0.5.1` should be treated as a **targeted refactoring and runtime hardening release**.

It is not a product-surface expansion release.

Its value is:

- internal reliability
- lower connection churn
- better architectural consistency
- cleaner operational foundations before `0.6.0`
