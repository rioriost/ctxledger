# MCP API

## 1. Purpose

`ctxledger` exposes its workflow control and memory capabilities through an MCP-compatible interface.

The MCP API is the public interface of the system, but it is not the canonical state store.  
Canonical state lives in PostgreSQL.  
MCP tools and resources expose mutation and read access to that canonical state.

The target protocol version is:

- `MCP 2025-03-26`

In `v0.1.0`, the primary implemented surface is the workflow control subsystem.  
Memory-related operations are defined architecturally but may remain stubbed or partially implemented.

---

## 2. API Design Principles

The MCP API follows these principles:

1. **Tools perform explicit operations**
2. **Resources expose read-only assembled views**
3. **Canonical state is stored in PostgreSQL**
4. **Repository files are projections only**
5. **Workflow control and memory retrieval remain separate**
6. **Errors are normalized at the protocol boundary**

This means:

- Tools are command-oriented
- Resources are query-oriented
- Some read-like operations may still be exposed as Tools for MCP client compatibility
- Projection files such as `.agent/resume.json` are not part of the MCP truth model

---

## 3. Tool and Resource Responsibility Split

## 3.1 Tools

Tools represent explicit operational actions.

Typical tool responsibilities:

- create or mutate canonical state
- initiate workflow lifecycle transitions
- persist checkpoints
- finalize workflows
- record memory or verification evidence
- trigger operational behavior

Examples:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

Future examples:

- `workflow_retry`
- `memory_remember_episode`

## 3.2 Resources

Resources represent read-only assembled views.

Typical resource responsibilities:

- expose current workflow state
- expose exact workflow detail
- expose episode records
- expose hierarchical summaries
- expose memory-derived context views

Examples:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

## 3.3 Special Case: `workflow_resume`

`workflow_resume` is semantically a read operation, because it assembles a composite resume view from canonical state.

However, it is also exposed as a Tool for client compatibility and ergonomic agent usage.

Internally, it should reuse the same read-model assembly logic used by resume resources.

---

## 4. Read and Write Model Separation

The API follows a lightweight separation between write and read concerns.

### Write Path
Write-oriented operations use:

- tool invocation
- application use case orchestration
- transaction-scoped persistence
- canonical PostgreSQL updates

### Read Path
Read-oriented operations use:

- resource resolution
- composite view assembly
- warning and inconsistency classification
- derived state calculation

### Projection Files
Projection files such as:

- `.agent/resume.json`
- `.agent/resume.md`

are derived artifacts.  
They do not replace Tools or Resources and are not canonical inputs to the API.

---

## 5. Tool Catalog

## 5.1 `workspace_register`

### Purpose
Register a repository workspace as a durable execution target.

### Category
Tool

### Primary Behavior
- create a new workspace record
- optionally update an existing workspace only when explicit workspace identity is provided
- reject ambiguous path or repository URL conflicts

### Expected Inputs
Recommended fields:

- `workspace_id` (optional for explicit update semantics)
- `repo_url`
- `canonical_path`
- `default_branch`

Optional future fields:

- `metadata`
- `workspace_name`

### Canonical Persistence
Writes to:

- `workspaces`

### Response Intent
Return the registered workspace identity and metadata.

Typical response content:

- `workspace_id`
- `repo_url`
- `canonical_path`
- `default_branch`
- `created_at`

### Error Cases
- invalid input
- path conflict
- repository URL conflict
- ambiguous workspace registration
- authentication failure
- persistence failure

---

## 5.2 `workflow_start`

### Purpose
Create a new workflow instance and initial execution attempt.

### Category
Tool

### Primary Behavior
- validate workspace existence
- enforce active workflow uniqueness per workspace
- create workflow instance
- create initial attempt

### Expected Inputs
Recommended fields:

- `workspace_id`
- `ticket_id`

Optional future fields:

- `metadata`
- `operator_notes`
- `initial_context`

### Canonical Persistence
Writes to:

- `workflow_instances`
- `workflow_attempts`

### Response Intent
Return the created workflow and attempt identities.

Typical response content:

- `workflow_instance_id`
- `attempt_id`
- `workspace_id`
- `ticket_id`
- `workflow_status`
- `attempt_status`
- `created_at`

### Error Cases
- workspace not found
- active workflow conflict
- invalid input
- authentication failure
- persistence failure

---

## 5.3 `workflow_checkpoint`

### Purpose
Persist resumable workflow state as a checkpoint snapshot.

### Category
Tool

### Primary Behavior
- validate workflow and attempt relationship
- reject invalid terminal-state updates
- persist checkpoint snapshot
- optionally persist verification evidence
- optionally trigger repository projection regeneration after commit

### Expected Inputs
Recommended fields:

- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `summary`
- `checkpoint_json`

Optional fields:

- `verify_status`
- `verify_report`
- `artifacts`

### Canonical Persistence
Writes to:

- `workflow_checkpoints`
- `verify_reports` (optional)
- future artifact tables
- projection failure records on projection write failure

### Response Intent
Return the created checkpoint and current execution state.

Typical response content:

- `checkpoint_id`
- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `created_at`
- `projection_status` (optional)
- `latest_verify_status` (optional)

### Error Cases
- workflow not found
- attempt not found
- workflow/attempt mismatch
- invalid checkpoint payload
- invalid state transition
- authentication failure
- persistence failure

---

## 5.4 `workflow_resume`

### Purpose
Return the latest assembled resumable view for a workflow instance.

### Category
Tool with read semantics

### Primary Behavior
- load canonical workflow data
- assemble active or latest attempt
- load latest checkpoint
- load latest verify report
- derive projection freshness/failure state
- detect recoverable inconsistencies
- return composite resume view

### Expected Inputs
Recommended fields:

- `workflow_instance_id`

Optional fields:

- `workspace_id`
- `include_projection_status`
- `include_verify_report`

### Canonical Persistence
Read-only operation on:

- `workspaces`
- `workflow_instances`
- `workflow_attempts`
- `workflow_checkpoints`
- `verify_reports`
- projection status/failure records

### Response Intent
Return a composite resume view, not a single row.

Typical response content:

- `workspace`
- `workflow_instance`
- `attempt`
- `latest_checkpoint`
- `latest_verify_report`
- `projection_status`
- `resumable_status`
- `warnings`
- `next_hint`

### `resumable_status` Examples
- `resumable`
- `terminal`
- `blocked`
- `inconsistent`

### Error Cases
Hard errors:
- workflow not found
- workspace not found
- authentication failure
- persistence failure

Soft issues returned inside response:
- running workflow without active attempt
- missing checkpoint
- stale projection
- open projection failure
- missing verify evidence
- unavailable workspace path

---

## 5.5 `workflow_complete`

### Purpose
Terminate a workflow instance and its active/latest attempt.

### Category
Tool

### Primary Behavior
`workflow_complete` is a termination operation, not only a success operation.

It may move the workflow to one of these terminal states:

- `completed`
- `failed`
- `cancelled`

It may also:

- record final summary
- record final verification evidence
- attach failure or cancellation context

### Expected Inputs
Recommended fields:

- `workflow_instance_id`
- `attempt_id`
- `workflow_status`

Optional fields:

- `summary`
- `verify_status`
- `verify_report`
- `failure_summary`
- `cancellation_reason`

### Canonical Persistence
Writes to:

- `workflow_instances`
- `workflow_attempts`
- `verify_reports` (optional)
- future failure records
- projection failure records on projection update failure

### Response Intent
Return terminal workflow state.

Typical response content:

- `workflow_instance_id`
- `attempt_id`
- `workflow_status`
- `attempt_status`
- `finished_at`
- `latest_verify_status` (optional)

### Error Cases
- workflow not found
- attempt not found
- workflow/attempt mismatch
- invalid terminal transition
- authentication failure
- persistence failure

---

## 5.6 `memory_remember_episode`

### Purpose
Persist an episode summary into the episodic memory subsystem.

### Category
Tool

### Status in `v0.1.0`
Defined architecturally, but may be stubbed or unavailable.

### Intended Future Behavior
- store summarized episode records
- support episode-derived memory extraction
- provide future recall inputs

### Future Canonical Persistence
- `episodes`
- related episode detail tables

### Current Expected Behavior
Either:

- return a clear unimplemented error, or
- expose a documented non-production stub

---

## 5.7 `memory_search`

### Purpose
Search reusable memory using retrieval mechanisms such as embeddings, relations, and summaries.

### Category
Tool

### Status in `v0.1.0`
Defined architecturally, but may be stubbed or unavailable.

### Intended Future Behavior
- semantic retrieval
- relation-aware retrieval
- summary-assisted retrieval

### Current Expected Behavior
Either:

- return a clear unimplemented error, or
- expose a documented non-production stub

---

## 5.8 `memory_get_context`

### Purpose
Return auxiliary memory context relevant to a task or workflow.

### Category
Tool with read semantics

### Status in `v0.1.0`
Defined architecturally, but may be stubbed or unavailable.

### Intended Future Behavior
Return support context such as:

- relevant episodes
- memory items
- repository-specific guidance
- hierarchical summaries
- related artifacts and relations

### Design Note
`memory_get_context` is intentionally separate from `workflow_resume`.

- `workflow_resume` returns canonical operational state
- `memory_get_context` returns relevance-based support context

---

## 5.9 Operational Status and Debug Endpoints

These operational endpoints are HTTP debug surfaces intended for deployment verification, runtime inspection, and bootstrap diagnostics.

They are not canonical workflow resources and do not replace MCP Tools or Resources.

### Purpose

They provide a thin inspection layer for:

- process liveness visibility
- service readiness visibility
- runtime transport wiring visibility
- registered HTTP route visibility
- registered MCP tool visibility

### Status Surface Summary

The current operational status surface includes:

- startup stderr summary
- `health()`
- `readiness()`
- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`

### `health()`

#### Purpose
Return liveness-oriented process status.

#### Typical response content
- `service`
- `version`
- `started`
- `workflow_service_initialized`
- `runtime`

#### Typical response shape

```/dev/null/json#L1-14
{
  "ok": true,
  "status": "ok",
  "details": {
    "service": "ctxledger",
    "version": "0.1.0",
    "started": true,
    "workflow_service_initialized": true,
    "runtime": [
      {
        "transport": "http",
        "routes": ["runtime_introspection", "runtime_routes", "runtime_tools", "workflow_resume"],
        "tools": []
      }
    ]
  }
}
```

### `readiness()`

#### Purpose
Return dependency-aware service readiness.

#### Typical response content
- `service`
- `version`
- `started`
- `database_configured`
- `http_enabled`
- `stdio_enabled`
- `workflow_service_initialized`
- `runtime`
- `database_reachable` (when checked)
- `schema_ready` (when checked)
- `error` (when applicable)

#### Typical statuses
- `not_started`
- `ready`
- `database_unavailable`
- `schema_check_failed`
- `schema_not_ready`

#### Typical response shape

```/dev/null/json#L1-18
{
  "ready": true,
  "status": "ready",
  "details": {
    "service": "ctxledger",
    "version": "0.1.0",
    "started": true,
    "database_configured": true,
    "http_enabled": true,
    "stdio_enabled": false,
    "workflow_service_initialized": true,
    "runtime": [
      {
        "transport": "http",
        "routes": ["runtime_introspection", "runtime_routes", "runtime_tools", "workflow_resume"],
        "tools": []
      }
    ],
    "database_reachable": true,
    "schema_ready": true
  }
}
```

### `/debug/runtime`

#### Purpose
Return runtime wiring grouped by transport.

#### Response intent
Expose both registered HTTP routes and registered MCP tools for each active transport.

#### Typical response shape

```/dev/null/json#L1-18
{
  "runtime": [
    {
      "transport": "http",
      "routes": [
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_resume"
      ],
      "tools": []
    }
  ]
}
```

If both HTTP and stdio are enabled, a stdio entry is also returned.

### `/debug/routes`

#### Purpose
Return registered HTTP route wiring only.

#### Response intent
Filter runtime introspection down to route registrations.

#### Typical response shape

```/dev/null/json#L1-14
{
  "routes": [
    {
      "transport": "http",
      "routes": [
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_resume"
      ]
    }
  ]
}
```

Transports without routes are omitted.

### `/debug/tools`

#### Purpose
Return registered MCP tool wiring only.

#### Response intent
Filter runtime introspection down to tool registrations.

#### Typical response shape

```/dev/null/json#L1-14
{
  "tools": [
    {
      "transport": "stdio",
      "tools": [
        "memory_get_context",
        "memory_remember_episode",
        "memory_search",
        "resume_workflow"
      ]
    }
  ]
}
```

Transports without tools are omitted.

### Startup stderr summary

On successful startup, the service also emits a short operational summary to stderr.

Typical content includes:

- `{app_name} {app_version} started`
- `health=...`
- `readiness=...`
- `runtime=[...]`
- `mcp_endpoint=...` when HTTP is enabled
- `stdio_transport=enabled` when stdio is enabled

### Error behavior

For invalid debug endpoint paths, the HTTP handler returns a normalized `404` payload with:

- `error.code = "not_found"`
- a path-specific explanatory message

---

## 6. Resource Catalog

## 6.1 `workspace://{workspace_id}/resume`

### Purpose
Return the workspace-scoped current operational resume view.

### Category
Resource

### Semantics
This is not a direct row lookup.  
It is a selected and assembled read model.

Selection rule:

1. if a running workflow exists for the workspace, return it
2. otherwise return the latest workflow for the workspace
3. if none exists, return empty/not-found semantics

### Response Intent
Return a composite workflow resume view suitable for agent recovery.

Typical content:

- workspace metadata
- selected workflow metadata
- selected attempt metadata
- latest checkpoint
- latest verify report
- projection status
- resumable status
- warnings/issues

---

## 6.2 `workspace://{workspace_id}/workflow/{workflow_instance_id}`

### Purpose
Return read-only detail for an exact workflow instance.

### Category
Resource

### Semantics
This resource is identity-specific.  
Unlike the workspace resume resource, it does not perform current-workflow selection.

### Response Intent
Return exact workflow detail, including:

- workflow instance
- attempts
- latest checkpoint
- verify information
- current or terminal status
- related projection diagnostics where applicable

---

## 6.3 `memory://episode/{episode_id}`

### Purpose
Return a read-only episodic memory record.

### Category
Resource

### Status in `v0.1.0`
Future-facing or stubbed.

### Intended Future Content
- episode summary
- execution outcome
- related failures
- related artifacts
- source workflow linkage

---

## 6.4 `memory://summary/{scope}`

### Purpose
Return a hierarchical summary for a memory scope.

### Category
Resource

### Status in `v0.1.0`
Future-facing or stubbed.

### Intended Future Content
- compressed summary view
- summary scope metadata
- source references
- optional relation or relevance hints

### Architectural Note
Summaries are derived, read-optimized structures.  
They are not canonical raw memory.

---

## 7. Response Model Guidelines

The exact MCP wire representation may depend on the runtime library and protocol conventions, but the logical response shape should remain consistent.

Responses should prefer including:

- stable identifiers
- status values
- timestamps
- structured payload sections
- human-readable summaries where useful
- warning or issue collections when relevant

### Example Logical Sections
Common response sections may include:

- `workspace`
- `workflow_instance`
- `attempt`
- `checkpoint`
- `verify`
- `projection`
- `warnings`
- `issues`
- `resumable_status`

---

## 8. Status Models

## 8.1 Workflow Instance Status

Supported architectural states:

- `running`
- `completed`
- `failed`
- `cancelled`

## 8.2 Workflow Attempt Status

Supported architectural states:

- `running`
- `succeeded`
- `failed`
- `cancelled`

## 8.3 Verification Status

Recommended statuses:

- `pending`
- `passed`
- `failed`
- `skipped`

## 8.4 Resume Classification Status

Recommended values:

- `resumable`
- `terminal`
- `blocked`
- `inconsistent`

## 8.5 Projection Status

Recommended values:

- `fresh`
- `stale`
- `missing`
- `failed`

---

## 9. Error Model

`ctxledger` uses an internal error taxonomy and maps those errors into MCP-visible failures.

The MCP API should return safe, structured, protocol-appropriate errors rather than raw internal exceptions.

## 9.1 Error Categories

### Validation Errors
Examples:

- missing required field
- malformed input
- invalid status value
- invalid checkpoint payload

### Authentication Errors
Examples:

- missing bearer token
- invalid bearer token
- unsupported auth mode

### Not Found Errors
Examples:

- workspace not found
- workflow instance not found
- attempt not found
- checkpoint not found

### Conflict and Invariant Errors
Examples:

- active workflow already exists
- workflow/attempt mismatch
- invalid state transition
- ambiguous workspace registration
- path conflict
- repository URL conflict

### Persistence Errors
Examples:

- database unavailable
- transaction failure
- lock failure
- unique constraint violation
- serialization failure

### Projection Errors
Examples:

- projection write failed
- projection target unavailable
- projection freshness degraded
- unresolved projection failure record exists

### Unimplemented Errors
Examples:

- memory feature not yet available
- stub-only API path invoked in unsupported mode

---

## 9.2 Hard Errors vs Soft Operational Issues

The API distinguishes between:

### Hard Errors
The operation fails and does not return the requested result.

Typical examples:

- authentication failure
- workflow not found
- invalid mutation transition
- database unavailable

### Soft Operational Issues
The operation succeeds sufficiently to return useful data, but warnings or issues are included.

Typical examples:

- resume returned without any checkpoint yet
- projection is stale
- projection write previously failed
- verify evidence is missing
- workspace path is unavailable

This distinction is especially important for `workflow_resume`.

---

## 9.3 Error Exposure Policy

The protocol layer should expose:

- stable error class
- safe message
- optional machine-readable code

It should avoid exposing:

- raw stack traces
- unsafe internal SQL detail
- secrets or token material
- low-level implementation internals not useful to clients

Detailed diagnostics should instead live in:

- structured logs
- durable failure records where applicable

---

## 10. Authentication Model

In `v0.1.0`, authentication is the primary enforced security boundary.

### Supported Approach
- bearer token authentication

### Enforcement Point
- transport boundary

### Future-Compatible Caller Context
The implementation may propagate caller context for:

- logging
- future audit trails
- future authorization models

Fine-grained authorization is out of scope for `v0.1.0`.

---

## 11. Projection and API Relationship

Projection files are not API resources, but they are closely related to API read models.

### Canonical Truth
- PostgreSQL

### MCP Read Surface
- tools with read semantics
- resources

### Repository Projection Surface
- `.agent/resume.json`
- `.agent/resume.md`

Projection freshness and failure may be reflected in API responses, especially resume-oriented ones.

---

## 12. Versioning and Compatibility Notes

The architectural target is:

- `MCP 2025-03-26`

`v0.1.0` prioritizes:

- stable workflow control semantics
- durable persistence
- consistent tool/resource roles
- future-safe extension points

The initial release does not attempt to provide complete memory retrieval behavior.  
Memory APIs may exist in documented stub form until the corresponding subsystems are implemented.

---

## 13. Initial `v0.1.0` Contract Summary

### Required Practical Surface

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`
- `health()`
- `readiness()`
- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

### Allowed Stub Surface
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

### Core Expectations
A compliant `v0.1.0` implementation should ensure:

- durable PostgreSQL-backed workflow state
- one active workflow per workspace
- checkpoint-based resumability
- composite resume assembly
- normalized MCP-visible errors
- projection-aware but projection-independent reads