# AGE Graph Population and Bootstrap Approach for the Constrained `supports` Prototype

For a practical step-by-step validation flow for this prototype, see:

- `docs/memory/age_prototype_validation_runbook.md`

## Purpose

This note documents the recommended **bootstrap and graph population approach**
for the currently constrained Apache AGE-backed `supports` prototype in `0.6.0`.

Its purpose is to make the remaining operational boundary explicit now that the
prototype has moved beyond planning and into a partially implemented state.

In particular, this note clarifies:

- what still counts as canonical
- what graph state is expected to contain
- who is responsible for creating and populating the graph
- how bootstrap should be approached in local/dev/test environments
- what should happen when the graph is absent or incomplete
- what remains intentionally out of scope

This note is still intentionally narrow.

It does **not** define broad graph lifecycle automation.

It does **not** make graph state canonical.

It does **not** widen visible `memory_get_context` behavior.

---

## Current Prototype Context

The repository now already contains a partially implemented constrained AGE
prototype with the following characteristics:

- a narrow `supports` target lookup boundary exists
- a relational baseline exists
- AGE availability and graph-readiness checks exist
- a PostgreSQL AGE-backed one-hop `supports` lookup path exists
- explicit relational fallback exists
- config-gated prototype controls exist:
  - `CTXLEDGER_DB_AGE_ENABLED`
  - `CTXLEDGER_DB_AGE_GRAPH_NAME`
- the memory service can use the narrow lookup boundary without changing the
  visible retrieval contract
- an explicit CLI bootstrap path now exists:
  - `ctxledger bootstrap-age-graph`
- runtime introspection now also exposes constrained AGE prototype details,
  including:
  - whether the prototype is enabled
  - the configured graph name
  - AGE availability
  - current graph-readiness status
- an explicit CLI readiness check now exists:
  - `ctxledger age-graph-readiness`

That means the main remaining ambiguity is no longer whether the first graph
prototype should exist.

The main remaining ambiguity is:

- how the graph should be created and populated
- when it should be treated as ready enough to use
- how graph state relates to canonical relational state

This note addresses that ambiguity.

---

## Core Decision

For the current constrained prototype, the recommended approach is:

- **relational state remains canonical**
- **graph state is derived**
- **bootstrap is explicit**
- **population is explicit**
- **fallback remains mandatory**
- **readiness means usable for the constrained lookup, not globally complete**

In practice, that means:

1. canonical memory items and memory relations remain in PostgreSQL tables
2. AGE graph state mirrors only the subset needed for the constrained prototype
3. graph creation/population should not happen as a hidden side effect of
   ordinary memory retrieval
4. the graph-backed path should only be used when the prototype graph is
   explicitly present and considered ready
5. missing or stale graph state must not break relational behavior

---

## Canonical Boundary

The canonical system of record remains:

- `memory_items`
- `memory_relations`

The graph layer should be treated as:

- supplementary
- derived
- rebuildable
- non-authoritative for truth

This means:

- graph nodes should reference canonical `memory_items.memory_id`
- graph edges should reference canonical `memory_relations.memory_relation_id`
  where practical
- graph absence does not imply canonical data absence
- graph incompleteness does not justify changing user-visible retrieval
  semantics

For the current prototype, the graph exists to support one narrow traversal
shape, not to redefine the memory model.

---

## Prototype Graph Scope

The constrained prototype only needs graph state for:

- memory item nodes
- `supports` edges between memory items

It does **not** need graph representations yet for:

- summaries
- episodes
- workspaces
- workflows
- hierarchy nodes
- ranking metadata
- multi-hop traversal aids

Recommended first graph shape:

- node label: `memory_item`
- edge label: `supports`

Recommended node properties:

- `memory_id`
- optionally lightweight identifying fields useful for diagnostics

Recommended edge properties:

- `memory_relation_id`
- `source_memory_id`
- `target_memory_id`
- optionally `created_at`

The exact property set may remain minimal as long as canonical relational IDs
remain traceable.

---

## Bootstrap Responsibility

Bootstrap responsibility should remain explicit and split across concerns.

### 1. Extension provisioning
Responsibility:

- operator/setup tooling
- schema/setup command path
- environment provisioning

The AGE extension itself should be treated as an environment prerequisite for
graph-enabled prototype use.

It should **not** be implicitly installed by ordinary retrieval code.

### 2. Graph creation
Responsibility:

- explicit setup/bootstrap step

The named AGE graph for the prototype should be created explicitly.

It should **not** be created lazily during ordinary request handling.

### 3. Graph population
Responsibility:

- explicit bootstrap or refresh step

Initial graph population should be done explicitly from canonical relational
state.

A first constrained CLI path now exists for this responsibility:

- `ctxledger bootstrap-age-graph`

That path should be read as:

- a prototype bootstrap/population entry point
- explicit operational setup
- still constrained in scope
- not a broad graph lifecycle framework

It should **not** first appear through hidden best-effort mutation inside
read-path code.

### 4. Runtime usage
Responsibility:

- repository/runtime capability checks

Runtime code may determine whether the graph is ready and whether it should use
the graph-backed lookup or the relational fallback.

Runtime code should **not** assume graph existence merely because AGE is
enabled.

---

## Recommended Operational Rule

Use this rule for the current prototype:

- **setup creates graph capability**
- **bootstrap populates graph contents**
- **runtime checks readiness**
- **reads fall back when readiness is not satisfied**

This keeps responsibilities understandable and makes failures easier to reason
about.

---

## Recommended Bootstrap Model

The preferred current model is:

- **explicit bootstrap, not implicit bootstrap**

That means the current prototype should prefer something like:

1. schema/setup applies canonical relational schema
2. AGE is provisioned in environments that want to exercise the prototype
3. an explicit bootstrap step creates the named graph if needed
4. the same bootstrap step populates graph nodes and edges from canonical
   relational tables
5. runtime health/readiness checks decide whether the graph-backed read may run

The repository now partially implements this model through an explicit CLI path:

- `ctxledger bootstrap-age-graph`

In its current form, that CLI path should be read as:

- the first real bootstrap entry point for the constrained prototype
- explicit graph creation/population intent
- still a prototype-grade path rather than a fully operationalized graph
  administration flow

This is preferable to app-start mutation because it avoids:

- hidden side effects during startup
- ambiguous partial initialization
- accidental graph drift caused by normal request traffic
- harder-to-debug environment differences

---

## Why Not Bootstrap During Retrieval

The constrained prototype should not bootstrap graph state during ordinary
retrieval because that would blur too many boundaries at once.

It would make retrieval responsible for:

- graph creation
- graph repair
- graph synchronization
- graph readiness decisions
- error recovery from setup failures

That is too much responsibility for the first graph-backed slice.

It would also make it harder to distinguish:

- graph unavailable
- graph not yet populated
- graph stale
- graph query failure
- retrieval logic bug

The current prototype should keep those concerns separate.

---

## Recommended Readiness Meaning

For the current prototype, graph readiness should mean:

- AGE is available
- the named graph exists
- the graph has been populated in the expected constrained shape
- the graph-backed one-hop `supports` lookup can run successfully

Readiness does **not** need to mean:

- globally synchronized for all future graph use cases
- complete for all memory-related concepts
- production-grade graph administration maturity
- support for future hierarchy/summary semantics

This is a prototype readiness definition, not a platform readiness definition.

---

## Recommended Degradation Rule

If any of the following are true:

- AGE is disabled
- AGE is unavailable
- the named graph does not exist
- graph population has not been performed
- graph-backed lookup raises for graph-specific reasons

then the system should:

- use the relational baseline path
- preserve current constrained behavior
- avoid widening visible retrieval semantics
- treat the graph path as unavailable rather than treating the request as a
  generic memory retrieval failure

This remains one of the most important operational safeguards in the prototype.

---

## Graph Population Strategy

The graph population process should be explicit and relationally derived.

### Source of truth

Populate from:

- `memory_items`
- `memory_relations`

### Population scope

Populate only:

- nodes for memory items relevant to the prototype
- edges for `memory_relations` rows where `relation_type = 'supports'`

### Recommended first population behavior

For the first prototype, population should be read as a simple
**rebuild-oriented** process:

1. ensure the target graph exists
2. clear the currently managed prototype graph contents owned by this prototype
3. repopulate `memory_item` nodes from canonical relational state
4. repopulate `supports` edges from canonical relational state
5. verify the resulting constrained graph counts at the end of the run
6. do not attempt sophisticated incremental sync at first

The current CLI bootstrap path is aligned with that rebuild-first reading and
should be interpreted as a constrained prototype population mechanism rather
than an incremental synchronization design.

Operationally, this means a successful bootstrap run should be read as:

- replacement of the currently managed constrained prototype graph contents
- repopulation from canonical relational tables
- lightweight verification of the rebuilt constrained graph contents through
  summary counts
- not preservation of prior graph-only state
- not an incremental merge/update procedure

This is the simplest approach that matches the prototype’s constrained scope.

### Why rebuild-first is acceptable now

A rebuild-oriented first pass is appropriate because:

- the prototype is narrow
- graph state is derived
- operational clarity is more valuable than early cleverness
- incremental sync logic would add complexity before the graph path is proven

For the current stage, correctness and explicitness matter more than sync
efficiency.

---

## Recommended First Population Semantics

The first bootstrap/population pass should aim for these semantics:

### Nodes
Create one graph node per canonical memory item intended for prototype use.

Minimum identity requirement:

- `memory_id` property must match canonical relational ID

### Edges
Create one graph edge per canonical `supports` relation.

Minimum identity requirement:

- edge must remain traceable to canonical `memory_relation_id` or at least the
  canonical source/target pair plus relation type

### Duplicate handling
Population should be idempotent enough that rerunning bootstrap does not create
semantically duplicated graph state for the same canonical objects.

How that is achieved may vary, but the note’s recommendation is:

- explicit rebuild or explicit upsert-style population
- not silent duplicate accumulation

---

## Recommended Environment Expectations

### Local development

Recommended default:

- relational workflows remain usable without AGE
- developers opt into graph prototype work explicitly
- graph population is run manually or through an explicit setup flow when needed

This keeps local development friction low.

### Shared development / CI-like environments

Recommended default:

- graph-enabled prototype environments should provision AGE explicitly
- graph population should be part of the explicit environment setup for graph
  tests
- non-graph suites should not accidentally depend on graph state

### Test environments

Recommended default:

- broad suites remain relational-first
- graph-specific tests explicitly arrange graph availability and graph
  population/readiness
- fallback behavior is always testable independently of graph availability

### Production-like environments

Recommended default for the current stage:

- only enable the prototype when operators intentionally provision AGE and the
  prototype graph
- do not treat graph enablement as a silent default
- keep fallback behavior available until graph-backed use is operationally
  mature

## Operator Guidance for the Current Prototype

The current constrained AGE prototype should be operated with explicit steps and
conservative expectations.

### Recommended operator sequence

For graph-enabled environments, the recommended sequence is:

1. provision PostgreSQL with the AGE extension available
2. apply the canonical relational schema first
3. enable the prototype explicitly through configuration
4. run the explicit bootstrap/population path for the named graph
5. only then treat the graph-backed lookup as eligible to run
6. retain relational fallback as the safe default when readiness is uncertain

### Recommended operator checks

Before treating the prototype as graph-ready, operators should confirm:

- the database instance is reachable
- AGE is installed and loadable
- the expected graph name is configured
- the bootstrap/population step has been run successfully
- canonical relational tables already contain the memory items and `supports`
  relations the graph is expected to mirror

### Recommended recovery reading

If the graph-backed prototype path appears unavailable, operators should prefer
this interpretation order:

1. AGE may be disabled in configuration
2. AGE may not be installed or loadable in the current environment
3. the named graph may not exist yet
4. the graph may not have been populated yet
5. the graph-backed read may have failed and fallen back to the relational path

That ordering is useful because it keeps setup and graph-readiness problems from
being misread too quickly as generic retrieval bugs.

### Recommended current operational stance

For the present stage, operators should treat the prototype as:

- optional
- explicit
- rebuild-first
- relationally recoverable
- suitable for constrained experimentation rather than broad graph dependency

---

## Recommended Configuration Reading

Current prototype controls already include:

- `CTXLEDGER_DB_AGE_ENABLED`
- `CTXLEDGER_DB_AGE_GRAPH_NAME`

Current runtime introspection now also exposes a constrained AGE prototype
payload through the runtime debug surface.

An explicit CLI readiness check also now exists:

- `ctxledger age-graph-readiness`

Operationally, the runtime payload and readiness command should be read as:

- a diagnostic view of current prototype configuration and readiness
- a lightweight operator-facing explanation aid
- a quick way to check current AGE availability and graph-readiness state
- not a guarantee that the prototype graph contents are correct for every
  future graph use case

Operationally, the configuration controls themselves should be read as:

### `CTXLEDGER_DB_AGE_ENABLED`
Meaning:

- the environment intends to allow graph-backed prototype use

It should **not** be read as:

- a guarantee that AGE is installed
- a guarantee that the graph exists
- a guarantee that graph population has been completed

### `CTXLEDGER_DB_AGE_GRAPH_NAME`
Meaning:

- the explicit named graph the prototype expects to use

It should help keep the graph boundary explicit and diagnosable.

It should **not** be treated as proof that the graph is ready.

---

## What Bootstrap Should Not Do Yet

The current prototype bootstrap should **not** attempt to become a full graph
administration framework.

Avoid introducing all of the following in the same slice:

- automatic graph repair during request handling
- background graph synchronization daemons
- multi-entity graph model rollout
- graph-based write canonicalization
- graph-first query planning
- broad hierarchy traversal population
- summary graph population
- multi-hop optimization machinery
- generalized graph abstraction layers with no immediate constrained use

Those may become later questions, but they are not justified for the current
prototype boundary.

---

## Recommended Near-Term Implementation Shape

The next implementation slice after the current prototype substrate should
likely add one explicit graph bootstrap/population path with the following
characteristics:

1. explicit command, script, or setup entry point
2. create graph if needed
3. populate `memory_item` nodes from canonical `memory_items`
4. populate `supports` edges from canonical `memory_relations`
5. keep reruns safe enough for local/dev/test usage
6. leave ordinary retrieval paths side-effect free
7. preserve relational fallback when bootstrap has not been run

That path now exists in initial CLI form as:

- `ctxledger bootstrap-age-graph`

The remaining work is therefore no longer inventing the bootstrap entry point
itself, but hardening and validating that entry point so it more clearly
matches the constrained operational model described in this note.

In particular, rerun semantics should currently be read as:

- rerunning bootstrap is expected to rebuild the currently managed constrained
  graph contents
- rerunning bootstrap is not intended to accumulate duplicate prototype-owned
  graph state
- rerunning bootstrap should be treated as a refresh-from-canonical-state step
- rerunning bootstrap should also produce lightweight verification counts for:
  - rebuilt `memory_item` nodes
  - rebuilt `supports` edges

Operator-facing hardening for that path should focus on:

- clearer rerun expectations
- clearer success/failure interpretation
- explicit environment guidance for local/dev/test and Docker-oriented use
- confirmation that bootstrap remains separate from ordinary retrieval behavior
- clearer use of runtime introspection details to distinguish:
  - AGE disabled
  - AGE unavailable
  - graph unavailable
  - graph-ready states

This would close the most important remaining operational gap without broadening
prototype scope.

---

## Validation Expectations

The bootstrap/population slice should be considered successful when it proves
all of the following:

- graph creation responsibility is explicit
- graph population responsibility is explicit
- graph-enabled environments can intentionally populate the prototype graph
- graph-disabled environments remain healthy on relational fallback
- graph-unready environments degrade clearly
- the visible retrieval contract remains unchanged

Recommended validation areas:

### 1. Bootstrap success
Confirm that explicit setup can create/populate the constrained graph.

### 2. Idempotent rerun behavior
Confirm that rerunning bootstrap does not produce uncontrolled duplicate graph
state for the constrained prototype.

### 3. Graph-ready runtime path
Confirm that runtime code can recognize the graph as ready enough for the
prototype lookup.

### 4. Graph-unready fallback path
Confirm that relational fallback still preserves constrained behavior when the
graph is absent or not populated.

### 5. Contract preservation
Confirm that user-visible `memory_get_context` behavior remains within the
current constrained contract.

---

## Non-Goals

This note does **not** define:

- a full AGE platform architecture
- canonical graph storage
- incremental graph synchronization design
- background reconciliation processes
- summary/hierarchy graph population
- multi-hop graph traversal rollout
- graph-first retrieval semantics
- broader visible API or MCP changes

It only defines the recommended bootstrap and graph population approach for the
current constrained one-hop `supports` prototype.

---

## Working Rule

Use this rule for the next AGE bootstrap/population slice:

- **canonical data stays relational**
- **graph state is derived**
- **bootstrap is explicit**
- **population is explicit**
- **runtime must verify readiness**
- **fallback remains mandatory**
- **visible retrieval behavior must remain unchanged**

This keeps the prototype operationally clear and prevents graph mechanics from
quietly becoming user-visible semantic drift.

---

## Decision Summary

For the current constrained AGE `supports` prototype, the recommended bootstrap
and graph population approach is:

- keep relational tables canonical
- treat AGE graph state as derived and rebuildable
- create and populate the graph through an explicit bootstrap path
- avoid retrieval-time bootstrap side effects
- use graph-readiness checks before graph-backed reads
- preserve relational fallback whenever readiness is not satisfied
- expose enough runtime introspection detail that operators can see the current
  constrained AGE prototype state without inferring it indirectly

That explicit bootstrap path now exists in initial CLI form through:

- `ctxledger bootstrap-age-graph`

And current runtime introspection now also exposes:

- enablement state
- configured graph name
- AGE availability
- graph-readiness status

Together with the bootstrap command's success summary counts, this gives
operators two complementary lightweight signals:

- bootstrap-time counts showing what the latest constrained rebuild populated
- runtime-time status showing whether the current environment appears eligible
  for graph-backed prototype reads

That combination should be read together with the bootstrap model as follows:

- bootstrap is rebuild-oriented for the constrained prototype
- readiness indicates whether the graph-backed path is eligible to run
- readiness does not imply incremental synchronization semantics
- fallback remains the required safe path whenever readiness is not satisfied

The next useful slice is therefore not broad graph expansion.

It is to harden, validate, and clarify that explicit constrained
bootstrap/population path so it makes the current prototype more executable in
real graph-enabled environments without changing the visible retrieval contract.

For a practical validation sequence that combines readiness checks, bootstrap
counts, and runtime introspection, see:

- `docs/memory/age_prototype_validation_runbook.md`