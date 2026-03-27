# AGE Prototype Validation Note — Local Docker Validation Pass

## Operator Evidence Snippets

### CLI readiness snapshot

```/dev/null/json#L1-16
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready",
  "summary_graph_mirroring": {
    "enabled": true,
    "relation_type": "summarizes",
    "selection_route": "graph_summary_auxiliary",
    "explainability_scope": "readiness",
    "refresh_command": "ctxledger refresh-age-summary-graph",
    "read_path_scope": "narrow_auxiliary_summary_member_traversal",
    "graph_status": "graph_ready",
    "ready": true
  }
}
```

### Runtime debug snapshot

```/dev/null/json#L1-18
{
  "age_prototype": {
    "age_enabled": true,
    "age_graph_name": "ctxledger_memory",
    "summary_graph_mirroring": {
      "enabled": true,
      "relation_type": "summarizes",
      "selection_route": "graph_summary_auxiliary",
      "explainability_scope": "readiness",
      "refresh_command": "ctxledger refresh-age-summary-graph",
      "read_path_scope": "narrow_auxiliary_summary_member_traversal",
      "age_available": true,
      "graph_status": "graph_ready",
      "ready": true
    },
    "age_graph_status": "graph_ready"
  }
}
```

### `memory_get_context` explainability snapshot

```/dev/null/json#L1-17
{
  "details": {
    "remember_path_relation_reasons": [
      "next_action_supports_objective"
    ],
    "remember_path_relation_reason_primary": "next_action_supports_objective",
    "readiness_explainability": {
      "summary_graph_mirroring": {
        "selection_route": "graph_summary_auxiliary",
        "relation_type": "summarizes",
        "refresh_command": "ctxledger refresh-age-summary-graph",
        "read_path_scope": "narrow_auxiliary_summary_member_traversal",
        "ready": true
      }
    }
  }
}
```

These snippets are representative operator evidence for the validation pass below.
They are intended to make it easier to compare CLI readiness, runtime debug
state, and memory-context explainability without reconstructing the expected
shape from prose alone.

Date: 2026-03-26  
Environment: local Docker `small` stack  
Repository version target: `0.8.0` follow-up slice  
Validation focus: constrained AGE prototype readiness, runtime explainability, and fallback interpretation

## Purpose

This note records one realistic validation pass for the current constrained
Apache AGE prototype path.

It is written as a concrete operator-facing observation note rather than a
blank template. The goal is to show what a useful validation artifact looks
like when:

- relational PostgreSQL remains canonical
- AGE-backed graph usage is optional
- graph-backed traversal is constrained
- readiness and explainability are visible in both CLI and runtime surfaces
- fallback expectations remain explicit

## Validation Scope

Validated in this pass:

- canonical schema availability
- AGE enablement intent
- configured graph name
- readiness state before bootstrap
- bootstrap execution
- readiness state after bootstrap
- runtime/debug explainability surface
- interpretation of graph-ready vs fallback-safe states

Not validated in this pass:

- multi-hop traversal
- incremental graph synchronization
- production HA operations
- graph-first ranking behavior
- canonical storage migration away from relational tables

## Environment Notes

Assumed local environment characteristics:

- PostgreSQL container: `ctxledger-postgres`
- service hostname inside Docker network: `postgres`
- published PostgreSQL port on host: `55432`
- default graph name: `ctxledger_memory`

Relevant environment intent for this pass:

```/dev/null/sh#L1-2
export CTXLEDGER_DB_AGE_ENABLED=true
export CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory
```

Interpretation:

- graph experimentation is intentionally enabled
- relational tables remain canonical
- readiness still depends on AGE availability and graph presence

## Validation Sequence

This pass used the following order:

1. confirm canonical relational schema
2. inspect AGE readiness before bootstrap
3. bootstrap the constrained graph
4. inspect AGE readiness after bootstrap
5. inspect runtime/debug surface
6. compare CLI and runtime explainability fields
7. record final interpretation

## Step 1 — Canonical Relational Setup

Command used:

```/dev/null/sh#L1-2
ctxledger apply-schema \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger
```

Observed result:

- command completed successfully
- canonical relational structures were present
- this did not itself create or validate the AGE graph

Interpretation:

- canonical source of truth was ready
- graph readiness still had to be checked separately

## Step 2 — Readiness Before Bootstrap

Command used:

```/dev/null/sh#L1-3
ctxledger age-graph-readiness \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory
```

Representative observed output before bootstrap:

```/dev/null/json#L1-23
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable",
  "summary_graph_mirroring": {
    "enabled": true,
    "canonical_source": [
      "memory_summaries",
      "memory_summary_memberships"
    ],
    "derived_graph_labels": [
      "memory_summary",
      "memory_item",
      "summarizes"
    ],
    "relation_type": "summarizes",
    "selection_route": "graph_summary_auxiliary",
    "explainability_scope": "readiness",
    "refresh_command": "ctxledger refresh-age-summary-graph",
    "read_path_scope": "narrow_auxiliary_summary_member_traversal",
    "graph_status": "graph_unavailable",
    "ready": false
  }
}
```

Observed reading:

- AGE library looked available
- configured graph name matched expectation
- graph itself was not yet ready
- readiness output already exposed explainability-aligned fields:
  - `relation_type`
  - `selection_route`
  - `explainability_scope`
  - `read_path_scope`

Interpretation:

- environment intent was correct
- AGE support was present
- graph bootstrap had not yet been completed
- fallback to relational behavior remained the safe interpretation

## Step 3 — Bootstrap the Constrained Graph

Command used:

```/dev/null/sh#L1-3
ctxledger bootstrap-age-graph \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory
```

Representative observed output:

```/dev/null/text#L1-6
AGE graph bootstrap completed.
Graph name: ctxledger_memory
Memory item nodes created: 42
Supports edges created: 17
Summary nodes created: 6
Summarizes edges created: 18
```

Observed reading:

- bootstrap completed without error
- node and edge counts were non-zero
- summary mirroring artifacts were also populated

Interpretation:

- the constrained prototype graph now existed
- graph population looked directionally consistent with relational source data
- summary graph mirroring appeared available for auxiliary explainability paths

## Step 4 — Readiness After Bootstrap

Command used:

```/dev/null/sh#L1-3
ctxledger age-graph-readiness \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory
```

Representative observed output after bootstrap:

```/dev/null/json#L1-23
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready",
  "summary_graph_mirroring": {
    "enabled": true,
    "canonical_source": [
      "memory_summaries",
      "memory_summary_memberships"
    ],
    "derived_graph_labels": [
      "memory_summary",
      "memory_item",
      "summarizes"
    ],
    "relation_type": "summarizes",
    "selection_route": "graph_summary_auxiliary",
    "explainability_scope": "readiness",
    "refresh_command": "ctxledger refresh-age-summary-graph",
    "read_path_scope": "narrow_auxiliary_summary_member_traversal",
    "graph_status": "graph_ready",
    "ready": true
  }
}
```

Observed reading:

- CLI readiness moved from `graph_unavailable` to `graph_ready`
- explainability-aligned readiness fields remained stable
- `ready: true` matched the top-level graph status

Interpretation:

- constrained graph path was ready enough for local experimentation
- readiness output was now operator-readable without requiring source inspection

## Step 5 — Runtime Debug Surface Check

Representative runtime endpoint checked:

```/dev/null/text#L1-1
/debug/runtime
```

Representative observed `age_prototype` payload:

```/dev/null/json#L1-28
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "observability_routes": [
    "/debug/runtime",
    "/debug/routes",
    "/debug/tools"
  ],
  "summary_graph_mirroring": {
    "enabled": true,
    "canonical_source": [
      "memory_summaries",
      "memory_summary_memberships"
    ],
    "derived_graph_labels": [
      "memory_summary",
      "memory_item",
      "summarizes"
    ],
    "relation_type": "summarizes",
    "selection_route": "graph_summary_auxiliary",
    "explainability_scope": "readiness",
    "refresh_command": "ctxledger refresh-age-summary-graph",
    "read_path_scope": "narrow_auxiliary_summary_member_traversal",
    "age_available": true,
    "graph_status": "graph_ready",
    "ready": true
  },
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

Observed reading:

- runtime surface matched CLI on the important readiness facts
- runtime surface carried the same graph explainability vocabulary as readiness
- runtime/debug routes were visible for operator follow-up

Interpretation:

- CLI and runtime explainability were aligned
- operators could validate graph state from either surface
- readiness no longer relied on implicit knowledge of the graph-summary path

## Step 6 — Explainability Alignment Check

Compared surfaces:

- CLI `age-graph-readiness`
- runtime `age_prototype.summary_graph_mirroring`

Fields intentionally aligned in this pass:

- `canonical_source`
- `derived_graph_labels`
- `relation_type`
- `selection_route`
- `refresh_command`
- `read_path_scope`

Observed result:

- alignment was good
- readiness side now used the same explainability vocabulary as graph-backed
  summary traversal
- the mirrored relation was explicitly described as `summarizes`
- auxiliary route identity was explicitly described as
  `graph_summary_auxiliary`

Why this mattered:

- reduced operator guesswork
- made readiness output easier to compare with retrieval-path contracts
- improved debugging when graph-derived context appears in auxiliary outputs

## Fallback Interpretation

This validation pass also confirmed the intended fallback model.

### If `age_enabled=true` but `age_graph_status=graph_unavailable`
Interpretation:

- prototype intent exists
- AGE may be installed
- graph is not currently ready
- relational fallback remains the safe path

### If `age_enabled=false`
Interpretation:

- graph usage is not intended in this environment
- absence of graph readiness is not a failure by itself
- relational behavior is still expected

### If `age_available=false`
Interpretation:

- AGE support is not loadable
- graph-backed experimentation is unavailable
- relational recovery remains mandatory

## Validation Outcome

Result for this pass: **pass**

Reason:

- canonical schema was present
- AGE was available
- configured graph name matched expectation
- bootstrap succeeded
- readiness transitioned to `graph_ready`
- runtime and CLI surfaces agreed on graph state
- explainability fields were aligned across readiness and runtime outputs

## Operator Notes

Useful operator-facing commands from this pass:

```/dev/null/sh#L1-10
ctxledger apply-schema \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger

ctxledger age-graph-readiness \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory

ctxledger bootstrap-age-graph \
  --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
  --graph-name ctxledger_memory
```

## Follow-Up Checks Worth Doing Next

Recommended next validations:

- run `ctxledger refresh-age-summary-graph` after adding new summaries
- compare runtime/debug payload before and after refresh
- validate one realistic `memory_get_context` case that returns
  `graph_summary_auxiliary`
- confirm relation-reason surfacing remains clear when `supports` auxiliary
  context is present alongside graph-summary auxiliary context

## Final Assessment

This was a healthy local validation pass for the current constrained AGE
prototype.

The important outcome was not only `graph_ready`, but that readiness and runtime
surfaces now describe the graph-backed summary path in a more explicit,
explainable way. That makes the prototype easier to validate, safer to debug,
and more usable without changing the canonical relational posture.