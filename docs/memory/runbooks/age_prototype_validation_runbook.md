# AGE Prototype Validation Runbook for the Constrained `supports` Path

For a concrete validation note that records one realistic local validation pass, see:

- `docs/memory/validation/age_prototype_validation_observation_template.md`

For the planned optional AGE-capable local/dev environment path, see:

- `docs/memory/design/age_docker_provisioning_plan.md`

## Purpose

This runbook describes how to validate the current constrained Apache AGE
prototype in a practical, operator-facing way.

It is intended for the current `0.8.0`-oriented prototype state where:

- relational PostgreSQL tables remain canonical
- AGE-backed graph usage is optional
- the graph-backed path is constrained to one-hop `supports` lookup
- relational fallback remains mandatory
- the visible `memory_get_context` contract is still intended to remain
  unchanged

This runbook is intentionally narrow.

It stays within the current `0.8.0` constrained prototype boundary.

It does **not** define a full production graph operations model.

It does **not** define broad graph lifecycle administration.

It does **not** change the current constrained prototype boundary.

---

## When to Use This Runbook

Use this runbook when you want to validate one or more of the following:

- AGE is installed and loadable in the current environment
- the named prototype graph exists
- the constrained graph bootstrap path ran successfully
- the runtime/debug surface reports the expected prototype state
- the CLI readiness path reports the expected prototype state
- the graph-backed prototype can be treated as ready enough for constrained
  experimentation
- fallback expectations remain understandable when the graph is unavailable or
  unready

This runbook is especially useful after:

- provisioning a new local or shared development environment
- enabling the prototype with `CTXLEDGER_DB_AGE_ENABLED=true`
- changing the configured graph name
- running `ctxledger bootstrap-age-graph`
- troubleshooting a graph-enabled environment that still appears to be using
  relational fallback

---

## Current Prototype Boundary Reminder

Before validating, keep the current prototype boundary in mind.

The current AGE work should be read as:

- constrained
- optional
- rebuild-first
- relationally recoverable
- behavior-preserving at the visible retrieval-contract boundary

Current prototype scope:

- `memory_item` graph nodes
- `supports` graph edges
- `memory_summary` graph nodes
- `summarizes` graph edges for derived summary mirroring
- one-hop relation lookup only
- narrow auxiliary summary-member traversal for explainability/readiness work

Current prototype non-goals:

- broad graph adoption
- canonical graph storage
- incremental synchronization
- multi-hop traversal
- graph-first ranking
- visible grouped-response redesign

---

## Validation Goals

A successful validation pass should answer these questions clearly:

1. Is the environment configured to allow the prototype?
2. Is AGE actually available?
3. Does the configured graph name match what operators expect?
4. Has the graph been bootstrapped and populated?
5. Does the system report graph readiness clearly?
6. Does the readiness surface expose the same summary-graph explainability shape
   that operators see elsewhere?
7. If graph readiness is missing, is relational fallback still the expected safe
   interpretation?

---

## Preconditions

Before you start, confirm the following:

### Required
- PostgreSQL is reachable
- canonical relational schema has been applied
- the environment has canonical `memory_items` and `memory_relations` available
  if you want bootstrap counts to be meaningful

### Recommended
- `CTXLEDGER_DB_AGE_ENABLED` is set intentionally for the environment you are
  validating
- `CTXLEDGER_DB_AGE_GRAPH_NAME` is set intentionally, or you are using the
  default graph name:
  - `ctxledger_memory`

### For Docker-oriented local validation
Recommended current assumptions in this repository:

- PostgreSQL container name:
  - `ctxledger-postgres`
- in-network PostgreSQL hostname from service containers:
  - `postgres`
- published host port:
  - `55432`

---

## High-Level Validation Sequence

Use this sequence for a clean prototype validation pass:

1. confirm canonical relational setup
2. confirm prototype configuration
3. run the CLI readiness check before bootstrap
4. run the bootstrap command
5. inspect bootstrap success counts
6. run the CLI readiness check again
7. inspect runtime introspection output
8. interpret the combined signals
9. record any mismatch as either:
   - config/setup issue
   - graph readiness issue
   - bootstrap/population issue
   - or runtime/reporting issue

---

## Step 1: Confirm Canonical Relational Setup

If you are unsure whether the canonical schema is present, start there first.

Useful command:

```/dev/null/sh#L1-1
ctxledger apply-schema
```

If using a direct database URL override:

```/dev/null/sh#L1-2
ctxledger apply-schema \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger
```

Expected reading:

- this prepares canonical relational structures
- this does **not** bootstrap the AGE graph
- this does **not** by itself make the graph-backed prototype ready

---

## Step 2: Confirm Prototype Configuration

Check the intended prototype controls in the environment.

Relevant settings:

- `CTXLEDGER_DB_AGE_ENABLED`
- `CTXLEDGER_DB_AGE_GRAPH_NAME`

Representative shell setup:

```/dev/null/sh#L1-2
export CTXLEDGER_DB_AGE_ENABLED=true
export CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory
```

Interpretation:

### If `CTXLEDGER_DB_AGE_ENABLED=false`
Expect:

- the prototype is disabled by configuration
- graph-backed use is not intended for the current environment
- relational behavior remains the expected path

### If `CTXLEDGER_DB_AGE_ENABLED=true`
Expect:

- the environment intends to allow the prototype
- but this still does **not** guarantee:
  - AGE is installed
  - the graph exists
  - bootstrap has been run
  - the graph is ready

---

## Step 3: Run the CLI Readiness Check Before Bootstrap

Use the dedicated readiness command before bootstrap to see the current state.

Default:

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

With explicit overrides:

```/dev/null/sh#L1-3
ctxledger age-graph-readiness \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory
```

Expected output shape:

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable"
}
```

### How to read the output

#### `age_enabled`
- tells you whether the prototype is intended to be active for this environment

#### `age_graph_name`
- tells you which graph name the prototype expects

#### `age_available`
- tells you whether AGE appears available/loadable

#### `age_graph_status`
Current expected values include:

- `age_unavailable`
- `graph_unavailable`
- `graph_ready`

### Common pre-bootstrap readings

#### Case A: disabled
```/dev/null/json#L1-6
{
  "age_enabled": false,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

Interpretation:
- the environment can see AGE/graph capability
- but the prototype is not intended to use it right now

#### Case B: AGE unavailable
```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": false,
  "age_graph_status": "age_unavailable"
}
```

Interpretation:
- setup/provisioning issue, not a retrieval logic issue

#### Case C: graph unavailable
```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable"
}
```

Interpretation:
- AGE is present
- the expected graph is not yet ready or not yet created/populated
- this is the most common expected state before bootstrap

---

## Step 4: Run the Explicit Bootstrap Command

Once the environment is intentionally configured and canonical schema is present,
run the explicit bootstrap path.

Default:

```/dev/null/sh#L1-1
ctxledger bootstrap-age-graph
```

With explicit overrides:

```/dev/null/sh#L1-3
ctxledger bootstrap-age-graph \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory
```

### Current bootstrap behavior

The current bootstrap path is intentionally prototype-grade and rebuild-first.

A run should be read as:

- create the named graph if needed
- clear the currently managed constrained prototype graph contents
- repopulate:
  - `memory_item` nodes from canonical `memory_items`
  - `supports` edges from canonical `memory_relations`

It should **not** be read as:

- incremental graph synchronization
- a graph merge/update procedure
- a broad graph lifecycle system

---

## Step 5: Inspect Bootstrap Success Counts

On success, the command now reports lightweight verification counts.

Representative success message:

```/dev/null/txt#L1-1
AGE graph bootstrap completed for 'ctxledger_memory' (memory_item nodes repopulated=123, supports edges repopulated=45).
```

### How to interpret the counts

#### `memory_item nodes repopulated`
- count of constrained prototype node population from canonical `memory_items`

#### `supports edges repopulated`
- count of constrained prototype edge population from canonical `memory_relations`
  where `relation_type = 'supports'`

### What the counts do mean
- the bootstrap run completed
- the constrained graph contents were rebuilt
- the run produced a lightweight verification summary

### What the counts do not mean
- broad graph correctness for future use cases
- incremental sync success
- proof that every possible runtime graph use case is valid
- proof that graph-backed retrieval has replaced relational fallback globally

### Suspicious count patterns

#### Zero nodes, zero edges
Possible readings:
- canonical memory data may not exist yet
- you may have bootstrapped the wrong database
- you may have bootstrapped the wrong graph name
- canonical schema/data may not be present where expected

#### Many nodes, zero supports edges
Possible readings:
- canonical `memory_items` exist
- but canonical `memory_relations` may have no `supports` edges yet
- or the environment may not contain the expected constrained relation data

#### Unexpectedly low counts
Possible readings:
- wrong database URL
- wrong graph name
- incomplete canonical data
- setup order issue

---

## Step 6: Run the CLI Readiness Check Again

After bootstrap, rerun the readiness command.

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

Expected post-bootstrap reading in a successful graph-enabled environment:

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

### If status is still `graph_unavailable`
Interpretation order:

1. bootstrap may have targeted the wrong graph name
2. bootstrap may have targeted the wrong database
3. AGE may be present but the graph creation step failed
4. readiness interpretation may not match the environment state as expected
5. the environment may not actually preserve the graph state where you expect it

At this stage, prefer treating the issue as:
- setup/readiness drift
not:
- generic retrieval failure

---

## Step 7: Inspect Runtime Introspection

If the server is running, inspect the runtime debug surface too.

Current runtime introspection now includes an `age_prototype` payload.

Representative endpoint:

```/dev/null/txt#L1-1
/debug/runtime
```

Representative reading:

```/dev/null/json#L1-10
{
  "runtime": [
    {
      "transport": "http",
      "routes": ["runtime_introspection", "runtime_routes", "runtime_tools", "workflow_resume"],
      "tools": []
    }
  ],
  "age_prototype": {
    "age_enabled": true,
    "age_graph_name": "ctxledger_memory",
    "age_available": true,
    "age_graph_status": "graph_ready"
  }
}
```

### How to use this together with the CLI readiness check

The readiness command gives:
- a direct CLI check of the current graph state

Runtime introspection gives:
- the running server’s current view of the constrained prototype state

These two should usually agree on:
- configured graph name
- AGE availability
- graph readiness state

If they do not agree, suspect:
- environment mismatch
- different config surfaces
- different database targets
- or startup/runtime context drift

---

## Step 8: Docker-Oriented Validation Patterns

### Host-driven validation against published PostgreSQL port

```/dev/null/sh#L1-4
export CTXLEDGER_DB_AGE_ENABLED=true
export CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory
ctxledger age-graph-readiness --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger
ctxledger bootstrap-age-graph --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger
```

### In-container validation from the running service container

```/dev/null/sh#L1-6
docker exec -it ctxledger-server sh -lc '
  export CTXLEDGER_DB_AGE_ENABLED=true
  export CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory
  ctxledger age-graph-readiness --database-url postgresql://ctxledger:ctxledger@postgres:5432/ctxledger
  ctxledger bootstrap-age-graph --database-url postgresql://ctxledger:ctxledger@postgres:5432/ctxledger
'
```

### Recommended Docker validation sequence

1. start the stack
2. apply canonical schema if needed
3. run `ctxledger age-graph-readiness`
4. run `ctxledger bootstrap-age-graph`
5. inspect the bootstrap counts
6. run `ctxledger age-graph-readiness` again
7. inspect `/debug/runtime` if the server is running

---

## Step 9: Troubleshooting Interpretation Order

If the graph-backed prototype appears not to be working, use this interpretation
order before assuming a retrieval bug.

### 1. Prototype disabled
Check:
- `age_enabled`

If false:
- the prototype is not intended to be active

### 2. AGE unavailable
Check:
- `age_available`
- `age_graph_status == "age_unavailable"`

Interpretation:
- environment provisioning issue

### 3. Graph unavailable
Check:
- `age_available == true`
- `age_graph_status == "graph_unavailable"`

Interpretation:
- graph creation/bootstrap issue
- not yet a reason to assume retrieval logic is broken

### 4. Bootstrap not run or bootstrapped against wrong target
Check:
- bootstrap success message
- bootstrap counts
- database URL used
- graph name used

Interpretation:
- operator/setup targeting issue

### 5. Runtime/readiness mismatch
Check:
- CLI readiness output
- runtime introspection output

Interpretation:
- config/runtime mismatch
- startup context mismatch
- database target mismatch

---

## Validation Outcomes and Recommended Interpretation

### Outcome: graph-ready after bootstrap
Meaning:
- environment is in the best currently supported constrained prototype state

Recommended next reading:
- graph-backed experimentation may proceed
- relational fallback should still remain the safe assumption if later graph
  issues appear

### Outcome: graph unavailable before bootstrap, graph ready after bootstrap
Meaning:
- expected happy-path constrained prototype setup

Recommended next reading:
- this is the normal lifecycle for a graph-enabled environment

### Outcome: graph unavailable both before and after bootstrap
Meaning:
- bootstrap did not make the graph ready in the expected target environment

Recommended next reading:
- investigate setup target mismatch or bootstrap failure mode first

### Outcome: AGE unavailable
Meaning:
- environment is not graph-capable right now

Recommended next reading:
- relational fallback remains the expected safe behavior

### Outcome: prototype disabled
Meaning:
- graph path is intentionally not in use

Recommended next reading:
- this is not a problem by itself

---

## What to Record After Validation

For a reusable fill-in template for this record, see:

- `docs/memory/validation/age_prototype_validation_observation_template.md`

A useful validation note should include:

- environment name
- whether `CTXLEDGER_DB_AGE_ENABLED` was true or false
- graph name used
- readiness result before bootstrap
- bootstrap command used
- bootstrap success counts
- readiness result after bootstrap
- whether runtime introspection matched the CLI readiness result
- whether any mismatch remained unresolved

Representative note shape:

```/dev/null/md#L1-10
- environment: local docker
- age_enabled: true
- age_graph_name: ctxledger_memory
- readiness_before_bootstrap: graph_unavailable
- bootstrap_run: yes
- bootstrap_counts:
  - memory_item_nodes: 123
  - supports_edges: 45
- readiness_after_bootstrap: graph_ready
- runtime_introspection_matches_cli: yes
- unresolved_issues: none
```

---

## Non-Goals of This Runbook

This runbook does **not** validate:

- full graph correctness for future hierarchy work
- incremental synchronization
- multi-hop traversal semantics
- broad graph performance characteristics
- production-grade graph administration guarantees
- broad user-visible retrieval changes

It validates only the current constrained, one-hop, optional AGE prototype.

---

## Working Rule

Use this rule when validating the current prototype:

- **check config first**
- **check readiness before bootstrap**
- **bootstrap explicitly**
- **read bootstrap counts as lightweight verification**
- **check readiness again**
- **compare CLI readiness with runtime introspection**
- **treat fallback as expected safety behavior when readiness is not satisfied**

This keeps validation aligned with the current constrained prototype boundary.

---

## Decision Summary

The current constrained AGE prototype should be validated as:

- an optional graph-backed path over canonical relational memory state
- a rebuild-first bootstrap model
- a readiness-gated execution path
- a fallback-preserving prototype

The most useful validation signals currently available are:

- `ctxledger age-graph-readiness`
- `ctxledger bootstrap-age-graph` success counts
- runtime introspection `age_prototype` details

For a concrete observation note shape that records those signals together, see:

- `docs/memory/validation/age_prototype_validation_observation_template.md`

For the planned optional AGE-capable Docker/dev path needed to move from
conceptual prototype work toward real graph-enabled local validation, see:

- `docs/memory/design/age_docker_provisioning_plan.md`

Together, those are enough to support practical constrained validation without
pretending the prototype is already a broad graph platform.