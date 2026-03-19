# MCP API

## 1. Purpose

`ctxledger` exposes its workflow control and memory capabilities through an MCP-compatible interface.

The MCP API is the public interface of the system, but it is not the canonical state store.  
Canonical state lives in PostgreSQL.  
MCP tools and resources expose mutation and read access to that canonical state.

For `v0.1.0`, the currently evidenced primary MCP surface is a **minimal HTTP MCP path** at:

- `/mcp`

The repository now evidences the following HTTP MCP operations on that path:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`

In `v0.1.0`, the primary implemented surface is still the workflow control subsystem.  
Memory-related operations are no longer purely architectural, but they remain uneven in maturity:

- `memory_remember_episode` is implemented, including canonical persistence of `attempt_id` when provided
- `memory_get_context` is partially implemented in an episode-oriented form, including initial query-aware filtering and richer context details about lookup scope, resolved workflows, and returned episode counts
- `memory_search` remains stubbed

The currently evidenced remote serving shape is:

- FastAPI application wrapper
- `uvicorn` process
- Docker-based local runtime
- MCP HTTP access through `/mcp`

Broader compatibility wording beyond this currently evidenced HTTP MCP path should be treated as a closeout decision, not as a stronger claim already proven by the current repository evidence.

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
- `memory_remember_episode`
- `memory_get_context`

Tool argument discovery is implemented through `tools/list`, which now returns concrete `inputSchema` payloads for the visible tool surface.

The strongest current repository evidence is for this discovery flow over the primary HTTP MCP path at `/mcp`, including live Docker-based smoke validation through the FastAPI/`uvicorn` runtime.

Representative `tools/list` response fragment:

```/dev/null/json#L1-33
{
  "tools": [
    {
      "name": "workspace_register",
      "description": "workspace_register tool",
      "inputSchema": {
        "type": "object",
        "properties": {
          "repo_url": { "type": "string", "minLength": 1 },
          "canonical_path": { "type": "string", "minLength": 1 },
          "default_branch": { "type": "string", "minLength": 1 },
          "workspace_id": { "type": "string", "format": "uuid" },
          "metadata": { "type": "object" }
        },
        "required": ["repo_url", "canonical_path", "default_branch"],
        "additionalProperties": false
      }
    },
    {
      "name": "workflow_start",
      "description": "workflow_start tool",
      "inputSchema": {
        "type": "object",
        "properties": {
          "workspace_id": { "type": "string", "format": "uuid" },
          "ticket_id": { "type": "string", "minLength": 1 },
          "metadata": { "type": "object" }
        },
        "required": ["workspace_id", "ticket_id"],
        "additionalProperties": false
      }
    }
  ]
}
```

This matters because MCP clients can now discover required arguments before calling tools such as `workspace_register`, instead of inferring them only from validation failures.

Future examples:

- `workflow_retry`
- richer `memory_search`

## 3.2 Resources

Resources represent read-only assembled views.

Typical resource responsibilities:

- expose current workflow state
- expose exact workflow detail
- expose episode records
- expose memory-derived context views
- later expose hierarchical summaries once the post-`0.4.0` retrieval layers are implemented
- near-term dashboard observability may use an optional Grafana-based surface in the `0.4.0` workstream

Examples:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`
- future operator-observability resources or Grafana-backed dashboard views introduced alongside the `0.4.0` observability workstream

Implemented in the current repository runtime surface as supporting MCP resources:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

These resources are currently implemented as workflow-oriented read surfaces alongside the primary HTTP MCP path, and the repository now includes live remote evidence for both `resources/list` and `resources/read` over `/mcp`.

Not yet implemented and still future-facing/stubbed as resources:

- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

This distinction matters because the current memory progress is tool-oriented first:
episodic recording and initial episode-oriented context retrieval are available
through MCP tools, while dedicated memory resources remain future work.

It also matters for roadmap alignment:
the near-term `0.4.0` emphasis is shifting toward operator observability surfaces,
including CLI inspection and optionally deployable Grafana-based dashboard support,
while broader hierarchical retrieval and summary-layer resource expansion move later.

The current episode-oriented retrieval path is also intentionally conservative:
it is still driven by canonical workflow linkage first, with only a light initial
query filter layered on top of that canonical lookup path.

Within that current response shape, `memory_context_groups` should be treated as
the primary grouped hierarchy-aware surface of `memory_get_context`.
Other flatter fields remain useful and supported, but they should currently be
interpreted as derived, compatibility-oriented, or convenience views over that
grouped surface rather than as the canonical hierarchy model.

In its current implemented form, the response `details` are intended to provide
light observability into how context assembly occurred. That currently includes:

- the original `query`
- the normalized query form used for lightweight matching
- `lookup_scope`
- the requested `workspace_id`
- the resolved `workflow_instance_id` when direct workflow lookup is used
- the requested `ticket_id`
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

The current lightweight query filter is still intentionally simple, but it is no
longer described best as opaque metadata stringification alone.
Its current intended behavior is:

- always check the episode `summary`
- also check lightweight field-based metadata text derived from metadata keys and values
- perform case-insensitive matching
- remain bounded to workflow-linked episode retrieval rather than semantic search

These fields are meant to explain the current episode-oriented assembly behavior.
At the current implementation stage, `matched_episode_count` and
`episodes_returned` may be the same value, but they are kept separate so the
details surface can remain useful if later `0.2.x` behavior adds post-match
truncation, ranking, or other assembly steps.
They should not yet be interpreted as a stable semantic-retrieval contract, since
broader ranking, relevance, and relation-aware retrieval remain future work, and
hierarchical summary assembly is now intended for a later milestone than `0.4.0`
while `0.4.0` focuses on observability-oriented operator surfaces, with Grafana
as the named near-term optional dashboard deployment path.

When consumers need the most hierarchy-aware current reading of the response,
they should prefer `memory_context_groups` first.
Top-level flat fields remain important for compatibility and convenience, but the
grouped surface is now the intended primary structured interpretation for
hierarchy-aware context assembly.

## 3.3 Special Case: `workflow_resume`

`workflow_resume` is semantically a read operation, because it assembles a composite resume view from canonical state.

However, it is also exposed as a Tool for client compatibility and ergonomic agent usage.

Internally, it should reuse the same read-model assembly logic used by resume resources.

## 3.4 Dedicated HTTP Read Surface

In addition to MCP tools and resources, `ctxledger` also exposes selected HTTP read surfaces for operational and integration use cases.

One such surface is a dedicated closed projection failure history endpoint:

- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

This route is a read-only HTTP surface over canonical workflow resume assembly data.  
It is intended to expose closed projection failure lifecycle history without requiring consumers to fetch the entire workflow resume payload.

Representative response contents:

- `workflow_instance_id`
- `closed_projection_failures`

Representative closed failure fields include:

- `projection_type`
- `target_path`
- `attempt_id`
- `error_code`
- `error_message`
- `occurred_at`
- `resolved_at`
- `open_failure_count`
- `retry_count`
- `status`

Concrete server surfaces also expose operator action endpoints for projection failure lifecycle handling.

Implemented HTTP operator action routes:

- `projection_failures_ignore`
- `projection_failures_resolve`

Representative operator action intents include:

- mark matching open projection failures as `ignored`
- mark matching open projection failures as `resolved`
- scope the action to a single projection type or all workflow projection failures

Implemented request shape for these HTTP action routes:

- existing `path: str` HTTP handler contract is preserved
- selector values are provided via query parameters
- strict path shape is also required:
  - `projection_failures_ignore` requires `/projection_failures_ignore`
  - `projection_failures_resolve` requires `/projection_failures_resolve`
- representative query parameters:
  - `workspace_id`
  - `workflow_instance_id`
  - `projection_type` (optional)
- when these routes are exposed through the documented deployment path, authentication is expected at the reverse-proxy/auth-gateway boundary
- requests using the wrong path shape should be treated as `404 not_found` rather than as valid action requests with only query validation

Representative HTTP request examples through a proxy-protected deployment:

```/dev/null/http#L1-2
GET /projection_failures_ignore?workspace_id=11111111-1111-1111-1111-111111111111&workflow_instance_id=22222222-2222-2222-2222-222222222222&projection_type=resume_json
Authorization: Bearer example-token
```

```/dev/null/http#L1-2
GET /projection_failures_resolve?workspace_id=11111111-1111-1111-1111-111111111111&workflow_instance_id=22222222-2222-2222-2222-222222222222
Authorization: Bearer example-token
```

Representative HTTP request examples should be understood in the context of the documented proxy-protected deployment path above.  The current operator-facing path is the HTTPS-terminated proxy entrypoint rather than a direct host-exposed local HTTP endpoint.

Representative `404 not_found` response examples for invalid path shapes:

```/dev/null/http#L1-6
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "error": {
    "code": "not_found",
    "message": "projection failure ignore endpoint requires /projection_failures_ignore"
  }
}
```

```/dev/null/http#L1-6
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "error": {
    "code": "not_found",
    "message": "projection failure resolve endpoint requires /projection_failures_resolve"
  }
}
```

Representative design constraints for such action surfaces include:

- they mutate canonical projection failure lifecycle state, not projection file contents directly
- they preserve failure history rather than deleting records
- they distinguish operator visibility closure (`ignored`) from successful reconciliation (`resolved`)
- they remain separate from narrow read-only history endpoints such as `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

This HTTP surface does not change the MCP responsibility split:

- MCP Tools remain the primary command interface
- MCP Resources remain the primary read-model interface
- dedicated HTTP operational surfaces may exist where a narrower concrete server contract is useful

It is also important to distinguish:

- the primary MCP protocol path at `/mcp`
- workflow-specific HTTP routes
- operator/action HTTP routes
- debug/runtime HTTP routes

The latter HTTP routes are useful and implemented, but they should not be treated as equivalent to MCP protocol evidence by themselves.

The implemented endpoints reuse the same projection failure lifecycle semantics as `workflow_resume` and other resume-oriented surfaces.

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

## 5. Primary HTTP MCP Path

The primary deployment and acceptance path for `v0.1.0` remains an HTTP MCP server exposed at `/mcp`, but the documented operator-facing public path is now the HTTPS-terminated proxy entrypoint rather than a direct host-exposed backend port.

The currently evidenced runtime shape is:

- FastAPI application wrapper in `src/ctxledger/http_app.py`
- `uvicorn` process startup for the private backend
- Docker Compose startup through `docker/docker-compose.yml` plus `docker/docker-compose.small-auth.yml`
- Traefik TLS termination on the public entrypoint

This means the HTTP MCP surface is no longer only an internal dispatch/testing concern.  
It is also exercised as a live remote endpoint in the repository’s local deployment flow, with the public/operator-facing path now going through HTTPS at the proxy boundary.

### 5.1 Confirmed HTTP MCP Operations

The currently evidenced HTTP MCP operations on `/mcp` are:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`

### 5.2 Minimum Remote Validation Path

A repository-provided smoke client exists at:

- `scripts/mcp_http_smoke.py`

Representative validation command shapes include:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --tool-name memory_get_context --insecure
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --scenario workflow --insecure
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --scenario workflow --workflow-resource-read --insecure
```

These validations now cover:

- MCP lifecycle setup through `initialize`
- tool discovery through `tools/list`
- tool invocation through `tools/call`
- resource discovery through `resources/list`
- resource reading through `resources/read`
- workflow-tool mutation flows against a live PostgreSQL-backed deployment

For memory closeout interpretation, this should be read together with the current
memory behavior boundary:

- `memory_remember_episode` is implemented
- `memory_get_context` is real but still partial
- `memory_get_context` currently exposes episode-oriented assembly details rather
  than a mature relevance-ranked retrieval contract
- `memory_search` remains stubbed

### 5.3 Confirmed Workflow Tool Validation Over Remote HTTP MCP

The workflow smoke scenario now confirms successful remote invocation of:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

This matters because it proves that the repository’s documented remote HTTP MCP deployment path can perform real canonical workflow mutations and reads against the live Dockerized PostgreSQL instance, rather than only returning stub or static responses.

### 5.4 Confirmed Workflow Resource Validation Over Remote HTTP MCP

The workflow resource-read validation now confirms successful remote reads for:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

This matters because it proves that resource-oriented workflow reads are not only implemented internally, but are also reachable and functioning over the actual `/mcp` protocol surface in the live deployment path.

## 6. Error Model and Boundary Behavior

For `v0.1.0`, the currently evidenced primary HTTP MCP path is:

- `/mcp`

The repository now evidences the following minimal MCP protocol behavior over HTTP:

- `initialize`
- `tools/list`
- `tools/call`

### Practical interpretation

This means a remote MCP client can, at minimum:

1. connect to `/mcp`
2. initialize an MCP session
3. list visible tools
4. inspect tool input schemas through `tools/list`
5. invoke tools through `tools/call`

This is the main acceptance surface for `v0.1.0`.

### Acceptance boundary note

At the current repository-evidence level, the confirmed HTTP MCP surface should be read as:

- `initialize`
- `tools/list`
- `tools/call`

This should be treated as the strongest current `v0.1.0` HTTP acceptance evidence.

Broader HTTP MCP proof, such as explicit closeout evidence for:

- `resources/list`
- `resources/read`

should be treated as a separate release-framing question rather than as behavior already implied by the minimal confirmed path.

### Supporting scope note

The primary release evidence surface is the HTTP MCP path at `/mcp`.  
Any broader MCP coverage should be evaluated as additional HTTP acceptance evidence rather than as a separate transport story.

---

## 6. Tool Catalog

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
Implemented MCP `inputSchema` fields:

Required:
- `repo_url` (`string`)
- `canonical_path` (`string`)
- `default_branch` (`string`)

Optional:
- `workspace_id` (`string`, UUID format, for explicit update semantics)
- `metadata` (`object`)

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
Implemented MCP `inputSchema` fields:

Required:
- `workspace_id` (`string`, UUID format)
- `ticket_id` (`string`)

Optional:
- `metadata` (`object`)

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
Implemented MCP `inputSchema` fields:

Required:
- `workflow_instance_id` (`string`, UUID format)
- `attempt_id` (`string`, UUID format)
- `step_name` (`string`)

Optional:
- `summary` (`string`)
- `checkpoint_json` (`object`)
- `verify_status` (`string`, enum: `pending | passed | failed | skipped`)
- `verify_report` (`object`)

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
Implemented MCP `inputSchema` fields:

Required:
- `workflow_instance_id` (`string`, UUID format)

The current MCP schema does not expose additional optional arguments for this tool.

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
- `closed_projection_failures`
- `next_hint`

Representative projection-related response details may include:

- `projection_type`
- `target_path`
- `attempt_id`
- `open_failure_count`
- `retry_count`
- `status`
- `occurred_at`
- `resolved_at`
- `error_code`
- `error_message`

When closed projection failure history is included, `closed_projection_failures` should expose representative failure records for lifecycle inspection.

Representative closed failure fields include:

- `projection_type`
- `target_path`
- `attempt_id`
- `error_code`
- `error_message`
- `occurred_at`
- `resolved_at`
- `open_failure_count`
- `retry_count`
- `status`

The same closed failure history may also be exposed through the dedicated HTTP read route:

- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

That route should return a narrower payload focused on:

- `workflow_instance_id`
- `closed_projection_failures`

### Projection Failure Lifecycle Semantics
Projection failure lifecycle is distinct from projection freshness status.

Representative lifecycle states:

- `open`
- `resolved`
- `ignored`

Meaning:

- `open`
  - a projection write failed and the failure is still operationally active
  - `resolved_at` should be `null`
- `resolved`
  - the failure is no longer open because successful reconciliation or explicit resolution occurred
  - `resolved_at` should be set to the timestamp when the failure stopped being open
- `ignored`
  - the failure is no longer open because the system or operator decided to stop treating it as an active unresolved issue
  - `resolved_at` should be set to the timestamp when the failure was ignored and closed

Important distinctions:

- projection status such as `failed` describes the projection artifact state
- failure lifecycle state describes whether projection failure records are still open
- `ignored` is not the same as successful projection recovery
- `resolved_at` is the canonical closure timestamp for both `resolved` and `ignored`
- `resolved_at` does not by itself imply successful projection recovery; lifecycle status must still be checked
- repeated failures should remain visible as repeated operational events rather than as a single boolean flag

Representative retry behavior:

- first open failure for a projection stream: `retry_count = 0`
- second consecutive open failure for the same projection stream: `retry_count = 1`

### Representative Operator Action Surfaces

Projection failure lifecycle handling may also require explicit mutation surfaces in addition to read-side resume access.

Representative action surfaces are modeled primarily as MCP tools because they perform canonical state mutation, and equivalent HTTP route surfaces are also implemented for operational integration use cases.

Implemented MCP tools:

- `projection_failures_ignore`
- `projection_failures_resolve`

Implemented HTTP action routes:

- `projection_failures_ignore`
- `projection_failures_resolve`

Implemented path requirements:

- `projection_failures_ignore` requires `/projection_failures_ignore`
- `projection_failures_resolve` requires `/projection_failures_resolve`
- unexpected path shapes should return `404 not_found`

Representative intended behavior:

- `projection_failures_ignore`
  - close matching `open` projection failure records as `ignored`
  - preserve closed history for later inspection
  - stop surfacing those failures as `open projection failure` warnings
  - do not claim successful projection repair
- `projection_failures_resolve`
  - close matching `open` projection failure records as `resolved`
  - preserve closed history for later inspection
  - record successful reconciliation or equivalent recovery-oriented closure semantics
  - stop surfacing those failures as `open projection failure` warnings

Representative selector fields for either tool may include:

- `workspace_id`
- `workflow_instance_id`
- `projection_type`

Representative response contents include:

- `workspace_id`
- `workflow_instance_id`
- `projection_type`
- `updated_failure_count`
- `status`

Implemented response status values:

- `ignored`
- `resolved`

Implemented validation and error handling include:

- required UUID validation for `workspace_id`
- required UUID validation for `workflow_instance_id`
- optional `projection_type` validation
- `server_not_ready` when the workflow service is not initialized
- normalized MCP error mapping for representative service failures:
  - `not_found`
  - `invalid_request`
  - `server_error`

Representative error cases include:

- workspace not found
- workflow not found
- workflow/workspace mismatch
- authentication failure
- persistence failure

Implemented HTTP action behavior also includes:

- query-string argument parsing from the incoming request path
- `400` with `error.code = "invalid_request"` for request validation failures
- `404` with `error.code = "not_found"` for unexpected route path shapes
- `503` with `error.code = "server_not_ready"` when the workflow service is not initialized
- normalized service exception mapping to representative HTTP errors:
  - `404` / `not_found`
  - `400` / `invalid_request`
  - `500` / `server_error`
- reuse of the existing proxy-auth rejection shape for `401` responses when these routes are exposed through the documented proxy-protected deployment path

Representative HTTP success response example:

```/dev/null/json#L1-7
{
  "workspace_id": "11111111-1111-1111-1111-111111111111",
  "workflow_instance_id": "22222222-2222-2222-2222-222222222222",
  "projection_type": "resume_json",
  "updated_failure_count": 1,
  "status": "ignored"
}
```

Representative HTTP `404 not_found` response examples for invalid action paths:

```/dev/null/json#L1-6
{
  "error": {
    "code": "not_found",
    "message": "projection failure ignore endpoint requires /projection_failures_ignore"
  }
}
```

```/dev/null/json#L1-6
{
  "error": {
    "code": "not_found",
    "message": "projection failure resolve endpoint requires /projection_failures_resolve"
  }
}
```

Representative HTTP validation error example:

```/dev/null/json#L1-9
{
  "error": {
    "code": "invalid_request",
    "message": "workflow_instance_id must be a valid UUID",
    "details": {
      "field": "workflow_instance_id"
    }
  }
}
```

Design note:

- these action surfaces should operate on canonical projection failure lifecycle state
- they should not delete failure history
- they should not be treated as projection write or reconciliation mechanisms by themselves
- the distinction between `ignored` and `resolved` should remain visible in later resume views and closed history reads

### Projection Warning Visibility Rules
Projection-related warnings should distinguish artifact status from failure lifecycle state.

Representative rules:

- emit `open projection failure` only when open projection failures exist
- `projection.status = failed` by itself does not necessarily imply an unresolved open failure
- a projection may remain `failed` even when `open_failure_count = 0`
- when `projection.status = failed` and `open_failure_count = 0`, the response may emit `ignored projection failure` or `resolved projection failure` to indicate closed historical failures without treating them as currently open
- if failure-level details are included, `resolved_at` should be present only for closed failures and should remain `null` for open ones
- closed failure history may also be returned separately in `closed_projection_failures` so clients can inspect lifecycle records directly without parsing warnings alone

Representative behavior:

- `projection.status = failed` and `open_failure_count > 0`
  - emit `open projection failure`
  - failure detail entries should remain in `status = open`
  - failure detail entries should expose `resolved_at = null`
- `projection.status = failed` and `open_failure_count = 0`
  - do not emit `open projection failure`
  - may emit `ignored projection failure`
  - may emit `resolved projection failure`
  - retain failed projection state for diagnosis
  - expose closed lifecycle records through warning details and/or `closed_projection_failures`
- `projection.status = fresh`
  - open projection failure warnings should not remain after successful reconciliation
  - previously closed lifecycle records may still remain visible in `closed_projection_failures`

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
- ignored projection failure
- resolved projection failure
- missing projection
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
Implemented MCP `inputSchema` fields:

Required:
- `workflow_instance_id` (`string`, UUID format)
- `attempt_id` (`string`, UUID format)
- `workflow_status` (`string`, enum: `running | completed | failed | cancelled`)

Optional:
- `summary` (`string`)
- `verify_status` (`string`, enum: `pending | passed | failed | skipped`)
- `verify_report` (`object`)
- `failure_reason` (`string`)
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

### Projection Failure Interaction
`workflow_complete` does not redefine projection failure lifecycle, but implementations may still record projection-related operational failures if projection regeneration or projection state updates fail during terminalization flows.

Projection failure metadata remains canonical operational state even when the projection files themselves are derived artifacts.

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
Implemented in the current repository state.

### Current Behavior
- validates `workflow_instance_id`
- validates `attempt_id` when provided
- verifies workflow existence before recording
- persists append-only episodic records
- returns the recorded episode payload on success

### Current Canonical Persistence
Writes to:

- `episodes`
- future related episode detail tables

The canonical `episodes` record now includes:

- `episode_id`
- `workflow_instance_id`
- `attempt_id` (optional, but canonically persisted when provided)
- `summary`
- `status`
- `metadata_json`
- timestamps

### Intended Further Evolution
- store richer episode-derived structures
- support stronger provenance and recall behavior
- act as a durable input into later semantic and hierarchical memory layers

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

For the current service-layer retrieval-contract snapshot, see:
- `docs/memory/memory_get_context_service_contract.md`

### Category
Tool with read semantics

### Status in `v0.1.0`
Partially implemented in the current repository state.

### Current Behavior
The current implementation is still primarily episode-oriented, but it now includes
a first minimal hierarchy-aware response shape for `0.6.0`.

It currently supports:

- canonical workflow-linked retrieval by `workflow_instance_id`
- canonical workflow expansion by `workspace_id`
- canonical workflow expansion by `ticket_id`
- `limit`
- `include_episodes`
- `include_memory_items`
- `include_summaries`
- initial query-aware filtering against episode summary and lightweight field-based metadata text
- richer `details` describing how the context was assembled
- a minimal hierarchy-aware grouping that distinguishes:
  - direct episode-scoped memory items
  - inherited workspace-scoped memory items

Representative current response details may include:

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
- `hierarchy_applied`
- `inherited_context_is_auxiliary`
- `inherited_context_returned_without_episode_matches`
- `memory_context_groups`
- `inherited_memory_items`
- `related_memory_items`
- `related_memory_items_by_episode`
- `related_context_is_auxiliary`
- `related_context_relation_types`
- `relation_memory_context_groups_are_primary_output`
- `flat_related_memory_items_is_compatibility_field`
- `related_memory_items_by_episode_are_compatibility_output`
- `group_related_memory_items_are_convenience_output`
- `summary_selection_applied`
- `summary_selection_kind`

When summaries are enabled and returned, grouped consumers may also observe a
minimal summary-oriented entry in `memory_context_groups`:
- `scope = "summary"`
- `scope_id = null`
- `parent_scope = "workflow_instance"`
- `parent_scope_id = {workflow_instance_id}` when exactly one workflow instance is resolved for the response
- `parent_scope_id = null` when the response is not anchored to a single resolved workflow instance
  - including multi-workflow workspace / ticket resolution cases
- `selection_kind = "episode_summary_first"`
- `summaries = [...]`

### Minimal Hierarchy-Aware Contract
The current `0.6.0` slice introduces a small but explicit hierarchy-aware contract.

When `include_memory_items=true`, the response may now distinguish:

1. **direct episode memory**
   - memory items attached to a returned episode
   - exposed through the existing per-episode `memory_items` structure
   - also exposed in `memory_context_groups` with:
     - `scope = "episode"`
     - `scope_id = {episode_id}`
     - `parent_scope = "workflow_instance"`
     - `parent_scope_id = {workflow_instance_id}`
     - `selection_kind = "direct_episode"`

2. **inherited workspace memory**
   - memory items in the resolved workspace whose `episode_id` is `null`
   - exposed through `inherited_memory_items`
   - also exposed in `memory_context_groups` with:
     - `scope = "workspace"`
     - `scope_id = {workspace_id}`
     - `parent_scope = null`
     - `parent_scope_id = null`
     - `selection_kind = "inherited_workspace"`

3. **supports-related memory**
   - target memory items reached from returned episode memory items
   - traversed through one outgoing relation hop only
   - currently limited to `relation_type = "supports"`
   - exposed through the flat compatibility field `related_memory_items`
   - also exposed through `related_memory_items_by_episode`
   - may also be exposed in episode-scoped `memory_context_groups` entries as group-local related context
   - workspace-scoped groups are not widened by this slice

`hierarchy_applied` is currently `true` when inherited workspace-scoped items are
present in the returned context details, and `false` otherwise.

The details payload now also makes current auxiliary-context behavior explicit through:

- `inherited_context_is_auxiliary`
- `inherited_context_returned_without_episode_matches`
- `related_context_is_auxiliary`
- `related_context_relation_types`
- `relation_memory_context_groups_are_primary_output`
- `flat_related_memory_items_is_compatibility_field`
- `related_memory_items_by_episode_are_compatibility_output`
- `group_related_memory_items_are_convenience_output`

At the current implementation stage, relation-aware context is also treated as
auxiliary support context rather than as part of episode selection or group-local
hierarchical output.

That means:

- `related_context_is_auxiliary = true` when `related_memory_items` are returned
- `related_context_relation_types = ["supports"]` for the current constrained relation-aware slice
- `relation_memory_context_groups_are_primary_output = true` when relation-scoped grouped output is present
- `flat_related_memory_items_is_compatibility_field = true` while the flat top-level field is retained
- `related_memory_items_by_episode_are_compatibility_output = true` while the per-episode compatibility mapping is retained
- `group_related_memory_items_are_convenience_output = true` when episode-group embedded related items are present as a convenience surface
- `related_context_is_auxiliary = false` when no related memory items are returned
- `related_context_relation_types = []` when no related memory items are returned

At the current implementation stage, inherited workspace-scoped memory is treated
as intentional auxiliary support context rather than as part of the
episode-selection filter.

Lightweight query filtering still applies to episode summary and metadata text.
Inherited workspace-scoped memory does not participate in that episode-matching
step.

That means inherited workspace-scoped memory may still appear in
`inherited_memory_items` and workspace-scoped entries in `memory_context_groups`
even when the lightweight query filter removes all episodes from the returned
`episodes` list.

When inherited workspace-scoped memory is present but no episodes survive
query filtering, representative details currently include:

- `matched_episode_count = 0`
- `episodes_returned = 0`
- `all_episodes_filtered_out_by_query = true`
- `episode_explanations` still preserve the pre-filter episode-level diagnostics
- non-matching episode explanation entries are marked with `explanation_basis = "query_filtered_out"`
- `inherited_context_is_auxiliary = true`
- `inherited_context_returned_without_episode_matches = true`
- `inherited_context_returned_as_auxiliary_without_episode_matches = true`

This should currently be interpreted as intentional auxiliary-context behavior,
not as evidence that inherited workspace items participate in episode matching.

When inherited workspace-scoped memory is present alongside matching episodes:

- `matched_episode_count > 0`
- `inherited_context_is_auxiliary = true`
- `inherited_context_returned_without_episode_matches = false`

### Current Retrieval Semantics
The current path remains intentionally conservative:

1. resolve the relevant workflow set from canonical workflow state
2. collect related episodes
3. optionally apply a lightweight case-insensitive query filter over:
   - episode `summary`
   - lightweight field-based metadata text derived from metadata keys and values
4. collect direct episode-scoped memory items for returned episodes
5. if memory items are enabled, collect inherited workspace-scoped memory items as auxiliary context
6. if memory items are enabled, traverse one outgoing `supports` relation hop from returned episode memory items and collect matching target memory items
7. return auxiliary support context with explicit grouping details

At the current implementation stage, query filtering is still centered on episode
selection rather than full multi-layer reasoning.

That means:

- direct episode selection is query-aware
- when summaries are enabled and returned, the response may explicitly mark summary-first assembly through:
  - `summary_selection_applied = true`
  - `summary_selection_kind = "episode_summary_first"`
  - additive summary-first sub-mode explanation metadata:
    - `summary_first_has_episode_groups = true` when the primary grouped chain includes episode-scoped groups under the summary-first path
    - `summary_first_is_summary_only = true` when summary-first selection is active but the grouped output contains only the summary-scoped group and no episode-scoped groups
  - a minimal grouped summary marker in `memory_context_groups` with:
    - `scope = "summary"`
    - `parent_scope = "workflow_instance"`
    - `parent_scope_id = {workflow_instance_id}` when exactly one workflow instance is resolved, otherwise `null`
    - in multi-workflow workspace / ticket resolution cases, that grouped summary `parent_scope_id` remains `null`
    - `selection_kind = "episode_summary_first"`
    - `child_episode_ids = [...]`
    - `child_episode_count = {number of child episode ids represented by the summary group}`
    - `child_episode_ordering = "returned_episode_order"`
    - `child_episode_groups_emitted = {true|false}`
    - `child_episode_groups_emission_reason = "memory_items_enabled" | "memory_items_disabled"`
    - `summaries = [...]`
  - `summary_first_child_episode_count = {number of child episode ids represented by the current summary-first grouped reading}`
  - `summary_first_child_episode_ids = [{episode ids represented by the current summary-first grouped reading}]`
  - `child_episode_count` should currently be read as explicit summary-group child cardinality metadata for grouped consumers, so they do not need to infer child count only by measuring `child_episode_ids`
  - `summary_first_child_episode_count` should currently be read as the top-level details counterpart of current summary-first child cardinality, so consumers do not need to derive that count only from grouped summary entries
  - `summary_first_child_episode_ids` should currently be read as the top-level details counterpart of the current summary-group child episode references, so consumers do not need to inspect grouped summary entries just to recover which child episodes the current summary-first reading represents
  - in query-filtered summary-first cases, both the top-level `summary_first_child_episode_*` fields and the grouped summary `child_episode_*` fields should currently be read from the surviving post-filter primary episode set rather than from the broader pre-filter candidate set
  - `child_episode_ordering = "returned_episode_order"` should currently be read as explicit summary-group ordering metadata for grouped consumers, so they do not need to infer whether `child_episode_ids` follows returned episode ordering
  - `child_episode_groups_emitted = true` should currently be read as explicit summary-group emittedness metadata for grouped consumers, so they do not need to infer whether corresponding episode-scoped groups were emitted only from broader response-shaping clues
  - `child_episode_groups_emission_reason` should currently be read as explicit summary-group emittedness-reason metadata for grouped consumers, so they do not need to infer the current emittedness reason only from broader response-shaping clues
  - when `summary_first_has_episode_groups = true`, grouped consumers should read the current primary grouped chain as `summary -> episode`
  - when `summary_first_is_summary_only = true`, grouped consumers should read the current primary grouped chain as summary-only for that response shape
  - the summary-only case is expected in narrow shaping scenarios such as `include_memory_items = false`
  - `child_episode_count` remains meaningful in both summary-only and summary-plus-episode cases because it describes selected child episode cardinality, not whether episode-scoped grouped entries were emitted
  - `child_episode_ordering = "returned_episode_order"` remains meaningful in both summary-only and summary-plus-episode cases because it describes the ordering semantics of the summary group's child episode references, not whether episode-scoped grouped entries were emitted
  - `child_episode_groups_emitted` remains meaningful in both summary-only and summary-plus-episode cases because it describes whether corresponding episode-scoped grouped entries were emitted for the current response shape, not how many child episodes the summary group represents
  - `child_episode_groups_emission_reason` remains meaningful in both summary-only and summary-plus-episode cases because it describes the current reason for emittedness or non-emittedness, not child cardinality or child ordering semantics
  - at the current stage, grouped consumers should read:
    - `child_episode_groups_emission_reason = "memory_items_enabled"` when corresponding episode-scoped grouped entries are emitted because memory items are enabled for the current response shape
    - `child_episode_groups_emission_reason = "memory_items_disabled"` when corresponding episode-scoped grouped entries are not emitted because memory items are disabled for the current response shape
  - the current primary summary/episode explainability surface should now be treated as explicit enough for the current stage; the next slices should prefer real behavior choices or higher-level contract consolidation over continuing to add more narrow summary-group explanation fields
  - when grouped output is present in this current stage, ordering should be treated as a small compatibility commitment for grouped consumers rather than as incidental formatting:
    - the summary-oriented group appears first when present
    - episode-scoped groups follow in the same order as returned `episodes`
    - the workspace-scoped inherited group appears last when present
  - when some group classes are absent, this ordering degrades naturally without placeholder groups:
    - summary-only grouped output returns only the summary-oriented group
    - workspace-only grouped output returns only the workspace-scoped inherited group
    - no empty summary, episode, or workspace placeholders are inserted just to preserve positional shape
- when summaries are disabled or no summaries are returned:
  - `summary_selection_applied = false`
  - `summary_selection_kind = null`
  - no summary-scoped grouped marker is returned
- inherited workspace-scoped memory may still be returned as auxiliary context when memory items are enabled
- inherited workspace-scoped memory may also be returned even when no episode survives query filtering
- in that no-episode-match case, grouped consumers should currently read the remaining workspace-scoped auxiliary visibility as preservation of auxiliary support context rather than as revival of filtered primary episode selection
- `all_episodes_filtered_out_by_query` explicitly marks the all-filtered case
- `episode_explanations` can still retain filtered-out episode diagnostics even when `episodes` becomes empty after filtering
- `inherited_context_is_auxiliary` makes that support-role explicit
- `inherited_context_returned_without_episode_matches` makes the no-matching-episodes case explicit
- `inherited_context_returned_as_auxiliary_without_episode_matches` explicitly states that the inherited workspace context remained visible in that no-matching-episodes case because it is auxiliary
- this should currently be interpreted as intentional auxiliary-context behavior rather than as evidence that inherited workspace items participate in episode matching
- in other words, the current contract should treat the workspace auxiliary path as surviving query-filter loss of episode matches without reclassifying that auxiliary context as newly matched primary episode context
- top-level details consumers should currently read `primary_episode_groups_present_after_query_filter` as:
  - `false` when no primary episode-scoped grouped output remains after query filtering
  - `true` when primary episode-scoped grouped output still remains after query filtering
- `auxiliary_only_after_query_filter` should currently be read as:
  - `true` when query filtering leaves no primary episode-scoped grouped output but at least one auxiliary route remains visible
  - `false` otherwise
- this field should currently be read as a direct top-level indication that the post-filter response became auxiliary-only, rather than requiring consumers to infer that only from grouped routes, grouped scope counts, primary-path absence, and surviving auxiliary visibility
- this field is intentionally narrower than a general "response empty/non-empty" indicator:
  - it does not mean nothing was returned
  - it means the primary episode path is gone while auxiliary context is still present
- this field should currently be read alongside `primary_episode_groups_present_after_query_filter`:
  - `primary_episode_groups_present_after_query_filter = false` and `auxiliary_only_after_query_filter = true` means auxiliary-only survival after query filtering
  - `primary_episode_groups_present_after_query_filter = false` and `auxiliary_only_after_query_filter = false` means neither the primary episode path nor any auxiliary grouped path remained visible
- top-level details consumers should currently read `summary_first_child_episode_count` as:
  - `0` when summary-first selection is not active
  - `{N}` when summary-first selection is active and the current summary-first grouped reading represents `N` child episodes
- top-level details consumers should currently read `summary_first_child_episode_ids` as:
  - `[]` when summary-first selection is not active
  - `[{episode ids}]` when summary-first selection is active and the current summary-first grouped reading represents those child episodes
- in query-filtered summary-first cases, those top-level child count/id fields should currently be interpreted from the surviving post-filter primary episode set
- in multi-workflow workspace- or ticket-resolved summary-first cases, grouped consumers should not infer a stronger summary parentage claim only because the surviving post-filter set narrows to one episode; the grouped summary `parent_scope_id` currently remains `null`
- `related_memory_items` is currently narrower than general relation-aware retrieval:
  - it starts from returned episode memory items only
  - it follows one outgoing hop only
  - it includes only `supports` relations
  - it ignores other relation types in this slice
- relation-scoped `memory_context_groups` entries are the current primary structured grouped relation-aware surface
- relation-scoped grouped output should currently be read as relation-derived auxiliary support context that was surfaced from returned episode-side memory context rather than as an independent primary selection path
- grouped consumers should currently expect the relation auxiliary surface to remain top-level and sibling-positioned rather than nested into the primary summary/episode chain
- the current relation auxiliary reading is still anchored in returned episode-side context even though the relation-scoped group itself remains top-level
- relation-scoped grouped entries may now also expose:
  - `source_episode_ids`
  - `source_memory_ids`
- top-level details may now also expose:
  - `relation_supports_source_episode_count = {number of returned episode ids that surfaced the current constrained relation auxiliary reading}`
- these source-linkage fields should currently be read as additive grouped/details explainability metadata that makes the constrained source-side linkage easier to inspect directly
- `relation_supports_source_episode_count` should currently be read as the top-level details counterpart of relation-group source episode linkage cardinality, so consumers do not need to derive that count only from relation-group-local source episode ids
- this relation auxiliary surface should now be treated as explicit enough for the current stage:
  - relation support context is auxiliary
  - relation support context is still one-hop and `supports`-only
  - relation-group linkage back to returned episode-side context is now directly readable enough without broadening traversal semantics
- the next slices should therefore prefer either:
  - a higher-level contract / interpretation step
  - or a genuinely new small behavior choice
  - rather than continuing to add narrowly incremental relation-group metadata without a clearer behavior need
- `related_memory_items_by_episode` remains a compatibility-oriented per-episode surface in the current stage
- group-local `memory_context_groups[*]["related_memory_items"]` remains a convenience view for grouped consumers
- when per-group related context is present, it should be understood as a compatibility- and convenience-preserving refinement of the same constrained `supports`-only behavior rather than as broader graph traversal
- the flat `related_memory_items` field remains the compatibility surface during this stage
- `related_context_is_auxiliary` makes the current support-role of related context explicit
- `related_context_relation_types` makes the currently constrained relation contract explicit without widening traversal behavior
- `relation_memory_context_groups_are_primary_output` makes the current primary grouped relation-aware surface explicit
- grouped consumers should currently correlate relation-scoped grouped output back to returned episode-side context through:
  - `source_episode_ids`
  - `source_memory_ids`
  - `relation_supports_source_episode_count`
  - the existing per-episode related-item convenience and compatibility surfaces
- the current constrained linkage reading is therefore:
  - returned episode-side memory items surface constrained supports-related targets
  - those same targets may appear in the top-level relation-scoped auxiliary group
  - the relation-scoped group is a grouped auxiliary aggregation of that returned episode-side relation context
  - when multiple returned source episodes or source memory items surface multiple `supports` targets, the current relation-group `memory_items` ordering should be read as first-seen target order in the current constrained aggregation flow
- `flat_related_memory_items_is_compatibility_field` makes the compatibility status of the flat top-level field explicit
- `related_memory_items_by_episode_are_compatibility_output` makes the compatibility status of the per-episode mapping explicit
- `group_related_memory_items_are_convenience_output` makes the convenience status of group-local embedded related items explicit

This is still not a full semantic, relation-aware, or graph-backed hierarchical
retriever.  
It remains a workflow-linked episodic context assembler with a first explicit
hierarchy-aware details layer and a very small constrained relation-aware extension.

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
        "routes": ["runtime_introspection", "runtime_routes", "runtime_tools", "workflow_resume", "workflow_closed_projection_failures", "projection_failures_ignore", "projection_failures_resolve"],
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
    "workflow_service_initialized": true,
    "runtime": [
      {
        "transport": "http",
        "routes": ["runtime_introspection", "runtime_routes", "runtime_tools", "workflow_resume", "workflow_closed_projection_failures", "projection_failures_ignore", "projection_failures_resolve"],
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
        "workflow_resume",
        "workflow_closed_projection_failures",
        "projection_failures_ignore",
        "projection_failures_resolve"
      ],
      "tools": []
    }
  ]
}
```

The current runtime surface returns the active HTTP runtime entry.

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
        "workflow_resume",
        "workflow_closed_projection_failures",
        "projection_failures_ignore",
        "projection_failures_resolve"
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
  "tools": []
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
### Error behavior

For invalid debug endpoint paths, the HTTP handler returns a normalized `404` payload with:

- `error.code = "not_found"`
- a path-specific explanatory message

---

## 6. Resource Catalog

## 6.1 `workspace://{workspace_id}/resume`

### Purpose
Return the workspace-scoped current operational resume view.

### Implementation Status
Implemented as a workflow-oriented read surface in the current `v0.1.0` repository state.

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

### Current response shape
The implemented resource currently returns:

- `uri`
- `resource`

Where `resource` is the same composite payload shape produced by `workflow_resume` / workflow resume serialization, including representative sections such as:

- `workspace`
- `workflow`
- `attempt`
- `latest_checkpoint`
- `latest_verify_report`
- `projections`
- `resumable_status`
- `next_hint`
- `warnings`
- `closed_projection_failures`

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

### Implementation Status
Implemented as a workflow-oriented read surface in the current `v0.1.0` repository state.

### Category
Resource

### Semantics
This resource is identity-specific.  
Unlike the workspace resume resource, it does not perform current-workflow selection.

### Response Intent
Return exact workflow detail, including:

### Current response shape
The implemented resource currently returns:

- `uri`
- `resource`

Where `resource` is the same composite workflow resume payload shape used by the current workflow read model assembly, but selected by exact workflow identity instead of workspace-level current/latest selection.

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

- missing proxy-layer bearer token
- invalid proxy-layer bearer token
- unsupported proxy/auth-gateway mode

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
Memory APIs now span a mixed maturity level:

- some are implemented (`memory_remember_episode`)
- some are partially implemented (`memory_get_context`)
- some remain stubbed (`memory_search`)

This should be described explicitly rather than collapsed into a single “memory is stubbed” statement.

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

### Implemented Optional Surface

- `projection_failures_ignore`
- `projection_failures_resolve`
- HTTP route surface for `projection_failures_ignore`
- HTTP route surface for `projection_failures_resolve`

### Allowed Stub / Partial Surface

- `memory_search`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

### Implemented / Partially Implemented Memory Surface

- `memory_remember_episode`
- `memory_get_context`

### Acceptance Evidence Note for Tool Schema Discoverability

In the current repository state, tool schema discoverability should be treated as part of the practical public-surface evidence for HTTP MCP interoperability.

Representative evidence includes:

- HTTP `tools/list` returns non-empty `inputSchema` payloads
- `workspace_register` exposes required fields:
  - `repo_url`
  - `canonical_path`
  - `default_branch`
- `workspace_register` exposes optional fields:
  - `workspace_id`
  - `metadata`
- the same schema-publication pattern is also applied to:
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `workflow_complete`
  - projection failure tools
  - implemented and partial memory tools

This means `workspace_register` argument discovery is no longer dependent on runtime validation errors alone and should be counted as visible acceptance evidence for MCP server/client compatibility on the confirmed HTTP MCP path.

### Core Expectations
A compliant `v0.1.0` implementation should ensure:

- durable PostgreSQL-backed workflow state
- one active workflow per workspace
- checkpoint-based resumability
- composite resume assembly
- normalized MCP-visible errors
- projection-aware but projection-independent reads
- machine-readable HTTP MCP tool argument discovery through `tools/list`
- a minimally confirmed HTTP MCP path consisting of:
  - `initialize`
  - `tools/list`
  - `tools/call`