# Grafana Operator Runbook

## 1. Purpose

This runbook explains how to deploy and operate the optional Grafana observability surface for `ctxledger`.

Grafana is intended to provide **read-only operator visibility** into canonical PostgreSQL state for:

- workflow activity
- memory activity
- projection failure activity

It is **not**:

- the canonical source of truth
- a workflow mutation interface
- a replacement for MCP
- a substitute for PostgreSQL access control

Canonical state remains in PostgreSQL.  
Grafana is a dashboard layer on top of read-only observability views.

---

## 2. Scope

This runbook covers:

- preparing the observability SQL views
- creating a read-only PostgreSQL role for Grafana
- starting Grafana with the Compose overlay
- verifying datasource connectivity
- confirming dashboard provisioning
- understanding AGE refresh-after-restart behavior for derived summary graph state
- understanding startup auto-refresh and operator fallback for the derived AGE summary graph
- understanding automatic file-work recording behavior in normal MCP tool flows
- understanding the derived memory state model so operators can distinguish normal absence from degraded observability
- basic operational and security guidance

This runbook assumes you are working in a local or internal operator environment.

---

## 3. Preconditions

Before you begin, ensure:

- the base `ctxledger` Docker deployment is already working
- PostgreSQL is healthy
- `ctxledger` itself is healthy
- the observability CLI commands already work as expected:
  - `ctxledger stats`
  - `ctxledger workflows`
  - `ctxledger memory-stats`
  - `ctxledger failures`

You should also have:

- Docker and Docker Compose available
- a shell with access to the repository root
- PostgreSQL access as an operator/admin user that can:
  - create schema
  - create views
  - create roles
  - grant privileges

---

## 4. Files introduced for Grafana support

Relevant files:

- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`
- `docker/grafana/provisioning/datasources/postgres.yml`
- `docker/grafana/provisioning/dashboards/dashboards.yml`
- `docker/grafana/dashboards/runtime_overview.json`
- `docs/sql/observability_views.sql`
- `scripts/setup_grafana_observability.py`

Related documentation:

- `docs/operations/deployment/deployment.md`
- `docs/project/releases/plans/observability_0_4_0_plan.md`

---

## 5. Security model

## 5.1 Core principle

Grafana must use a **read-only PostgreSQL role**.

Do not point Grafana at the main application database credentials.

## 5.2 Why

Grafana can issue SQL queries.  
Even in a dashboarding context, that means unsafe privilege choices can create risk.

The main protections are:

1. read-only DB role
2. observability-specific schema/views
3. limited dashboard editing permissions
4. careful datasource secret handling

## 5.3 Minimum safe posture

Grafana should have:

- `CONNECT` on the database
- `USAGE` on the `observability` schema
- `SELECT` on observability views only

Grafana should **not** have:

- `INSERT`
- `UPDATE`
- `DELETE`
- `TRUNCATE`
- `CREATE`
- `ALTER`
- `DROP`

---

## 6. Step 1 — Start the default `small` deployment

From the repository root, start the default `small` deployment:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

If you use `envrcctl`, use the equivalent wrapped command instead.

Confirm containers are healthy before continuing.

Recommended checks:

- PostgreSQL is healthy
- `ctxledger-server-private` is healthy
- `ctxledger-auth-small` is healthy
- `ctxledger-grafana` is running normally
- `ctxledger-traefik` is running normally

---

## 7. Step 2 — Understand the default automatic setup

In the default `small` deployment, Grafana-related observability database setup is now intended to happen automatically during application startup.

The startup path runs:

- `scripts/setup_grafana_observability.py`

That helper is intended to:

- apply `docs/sql/observability_views.sql`
- ensure the Grafana read-only PostgreSQL role exists
- ensure the Grafana role password matches the configured value
- grant the required observability read privileges
- revoke broad access from the `public` schema for the Grafana role

### Manual fallback

If you need to re-run the setup manually against the current environment, use:

```/dev/null/sh#L1-1
python scripts/setup_grafana_observability.py
```

### Expected result

The helper should complete without SQL errors and leave Grafana able to read from the `observability` schema.

---

## 8. Step 3 — Choose Grafana credentials up front

The default `small` deployment expects Grafana-related credentials to be provided before startup.

Required values:

- `CTXLEDGER_GRAFANA_ADMIN_USER`
- `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`
- `CTXLEDGER_GRAFANA_POSTGRES_USER`
- `CTXLEDGER_GRAFANA_POSTGRES_PASSWORD`

You can provide these through:

- a repository-root `.env` file
- or `envrcctl exec`

The automatic setup helper uses the configured PostgreSQL role name and password when preparing observability access.

### Verification

A useful verification is to connect with the Grafana role and confirm:

- `SELECT * FROM observability.workflow_overview;` works
- `SELECT * FROM workflow_instances;` does **not** work

---

## 9. Step 4 — Start the default stack and let Grafana come up with it

Grafana is now part of the default authenticated `small` deployment.

Start the stack with:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

If you use `envrcctl`, use the equivalent wrapped command instead.

### Exposed port

Grafana is exposed on:

```/dev/null/txt#L1-1
http://localhost:3000
```

---

## 10. Step 5 — Verify Grafana health

### Container health

Check container status:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps
```

The `grafana` container should be healthy or running normally.

### HTTP health

Grafana provides a health endpoint. A simple local check is:

```/dev/null/sh#L1-1
curl -fsS http://localhost:3000/api/health
```

Expected result includes `"database":"ok"` or equivalent healthy status.

### If health fails

Check logs:

```/dev/null/sh#L1-1
docker logs ctxledger-grafana
```

Common causes:

- bad admin password env values
- bad datasource env values
- PostgreSQL not reachable from Grafana
- provisioning file syntax issues

### Important zero-state reading before UI inspection

A healthy Grafana container and a healthy datasource do **not** imply that every
panel should be non-zero.

In the current `ctxledger` posture, some zero or `No data` readings can be
expected and should be interpreted carefully.

Read the dashboards in this order:

1. datasource and panel SQL health
2. canonical workflow and memory counts
3. canonical summary counts
4. derived-layer readings

Keep these boundaries explicit:

- Grafana is a read-only observability surface
- PostgreSQL canonical state remains the source of truth
- summary rows and summary memberships are canonical relational artifacts when
  they exist
- graph-backed or otherwise derived readings remain auxiliary and degradable

That means a zero-state panel is not automatically a Grafana failure.

Representative examples:

- `Canonical Summaries = 0`
  - can be expected when no explicit summary build ran and no checkpoint-gated
    workflow-completion summary build was requested
- `Summary Memberships = 0`
  - can be expected when no canonical summaries have been built yet
- derived or auxiliary summary-related panels showing `No data`
  - can be expected downstream of an empty canonical summary layer
- `File-Work Memory Items = 0`
  - should be read differently:
    this may indicate that interaction capture is present but bounded file-work
    metadata capture is not yet operationally visible in current data

The key operator rule is:

- do **not** treat derived-layer thinness as canonical-state loss
- do **not** treat every zero as a Docker, Grafana, or datasource problem
- first confirm whether the zero reflects actual bounded product state

---

## 12. Step 7 — Log in and verify provisioning

Open Grafana:

```/dev/null/txt#L1-1
http://localhost:3000
```

Log in with:

- user: `CTXLEDGER_GRAFANA_ADMIN_USER`
- password: `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`

### Confirm datasource

In Grafana UI, confirm there is a datasource named:

- `ctxledger-postgres`

It should be:

- provisioned automatically
- marked as default
- not editable by default

### Confirm dashboard provider

A dashboard folder named `ctxledger` should appear.

### Confirm dashboard

The initial dashboard should appear:

- `ctxledger Runtime Overview`

---

## 13. Step 8 — Validate dashboard data

Check that the runtime overview panels show plausible values.

Examples:

- workspace count
- workflow instance count
- workflow attempt count
- checkpoint count
- workflow status distribution
- recent workflows table
- latest workflow activity markers

Cross-check values against CLI:

```/dev/null/sh#L1-3
ctxledger stats
ctxledger workflows --limit 10
ctxledger failures --limit 10
```

The exact presentation differs, but the underlying counts and states should be consistent with canonical PostgreSQL state.

### Additional checks for memory and summary panels

When validating the memory dashboard, check both the raw counts and the meaning
of low or empty readings.

Recommended spot checks:

- `interaction_memory_item_count`
- `file_work_memory_item_count`
- `memory_summary_count`
- `memory_summary_membership_count`

Representative SQL checks:

```/dev/null/sql#L1-4
SELECT
  interaction_memory_item_count,
  file_work_memory_item_count,
  memory_summary_count,
  memory_summary_membership_count
FROM observability.memory_overview;
```

Operator reading guidance:

- non-zero interaction memory with zero file-work memory
  - usually means durable interaction capture is visible but file-work-tagged
    memory is absent in current data
- zero summaries and zero memberships
  - can be expected when no explicit or checkpoint-gated summary build has been
    requested yet
- derived-layer thinness or `No data`
  - should be read as downstream of canonical summary absence unless other
    canonical counters suggest broader problems
- after a Docker restart, canonical summary rows and memberships can still exist
  while the derived AGE summary graph is not yet rebuilt
  - in that case, readiness can temporarily read as graph unavailable or
    degraded until the AGE summary graph is refreshed
  - this is a derived-layer rebuild issue, not canonical summary loss

Use these checks to distinguish:

- broken datasource or broken SQL
- quiet but valid product state
- bounded feature gap that still needs implementation work
- derived graph state that simply needs post-restart refresh

---

## 14. Operational checks after deployment

After Grafana is live, an operator should verify:

1. datasource connects successfully
2. dashboard loads without SQL errors
3. recent workflows table populates
4. activity timeline renders
5. values align with CLI and/or direct SQL spot checks
6. Grafana credentials are not left at placeholder defaults

---

## 15. Common problems and fixes

## 15.1 Grafana starts but dashboard is empty

Possible causes:

- observability SQL views were not applied
- Grafana role cannot read `observability` schema
- database user/password mismatch
- database contains little or no data

Checks:

- verify views exist
- verify role grants
- verify datasource settings
- run direct SQL manually

Representative check:

```/dev/null/sql#L1-2
SELECT * FROM observability.workflow_overview;
SELECT * FROM observability.workflow_recent LIMIT 5;
```

If dashboards load but some tiles remain `0` or `No data`, do not collapse that
into “dashboard is empty”.

Instead separate the problem into:

1. dashboard plumbing failure
   - panel SQL errors
   - permission errors
   - missing views
   - datasource connectivity problems

2. valid current-state zero
   - no summaries built yet
   - no summary memberships yet
   - no derived-layer signal because canonical summary inputs are absent

3. bounded product-surface gap
   - interaction capture visible, but file-work-aware memory capture still absent

This distinction matters because the corrective action differs:

- plumbing failure
  - fix SQL, role grants, or connectivity
- valid current-state zero
  - explain and verify against canonical state
- bounded product-surface gap
  - inspect capture semantics and implementation, not Grafana health alone

---

## 15.2 Datasource test fails

Possible causes:

- wrong hostname
- wrong DB user/password
- Grafana role missing `CONNECT`
- PostgreSQL container/network issue

Checks:

- confirm PostgreSQL is healthy
- confirm host is `postgres:5432` in Compose context
- confirm username/password env variables are correct
- inspect Grafana logs

---

## 15.3 AGE derived graph reads look unavailable after restart

This can be expected after `docker compose down` / `up` or other restart-style
stack recreation flows.

Current operator reading:

- canonical PostgreSQL summary rows remain the source of truth
- the AGE summary graph is derived and rebuildable
- after restart, canonical summary counts can remain non-zero while AGE derived
  readiness temporarily reports:
  - `graph_unavailable`
  - degraded summary-graph mirroring status
- this does **not** mean canonical summaries were lost

Typical reading pattern:

1. `observability.memory_overview` still shows:
   - `memory_summary_count > 0`
   - `memory_summary_membership_count > 0`
2. AGE readiness is not yet `graph_ready`
3. Grafana derived-layer panels may remain thin until refresh

Updated runtime reading:

- the default startup path now attempts an automatic AGE summary-graph refresh
  when readiness indicates derived graph state is missing, stale, or otherwise
  needs rebuild help
- the automatic refresh is meant to cover the normal restart case so operators do
  not have to run a manual repair step every time
- canonical relational summary state remains authoritative even when the derived
  graph has not caught up yet

Operator fallback still matters when:

- startup refresh fails
- AGE extension availability changes
- operators want to force a rebuild after investigation
- the graph was rebuilt from an older or partially broken runtime state

Manual corrective action:

```/dev/null/sh#L1-1
docker exec ctxledger-server-private sh -lc "cd /app && python -m ctxledger.__init__ refresh-age-summary-graph --database-url postgresql://ctxledger:ctxledger@postgres:5432/ctxledger --graph-name ctxledger_memory && python -m ctxledger.__init__ age-graph-readiness --database-url postgresql://ctxledger:ctxledger@postgres:5432/ctxledger --graph-name ctxledger_memory"
```

Expected result after refresh:

- `refresh-age-summary-graph` reports rebuilt summary nodes and `summarizes` edges
- `age-graph-readiness` reports:
  - `age_graph_status = graph_ready`
  - `readiness_state = ready`
  - `operator_action = no_action_required`

Use this interpretation rule:

- restart-time AGE thinness is a derived rebuild concern
- canonical summary absence is a different issue and should be diagnosed separately

---

## 15.4 Natural file-work recording during normal MCP work

The default runtime now treats file-touching work as something that should
naturally leave a durable file-work trail in the active work loop.

Operator reading:

- explicit `file_work_record` calls still remain valid
- normal MCP tool flows that touch files should also be read with file-work
  recording in mind, not as a separate optional cleanup step
- this includes MCP RPC tool-call flows, where bounded file-touching metadata can
  now be turned into a durable file-work record when workflow context is present
- if the visible ctxledger MCP tool surface returns `tool_not_found`, the
  attempted file-touch can still be useful resumability context for an AI agent
  when the bounded file-touch metadata is present
- this is meant to reduce the chance that real file edits happen while the
  durable resumability trail stays empty

What operators should expect from the flow:

1. a file-touching tool call happens in an active workflow context
2. the runtime already sees bounded file-work metadata such as:
   - `file_path`
   - `file_name`
   - `file_operation`
   - optional `purpose`
3. this should work not only for direct runtime dispatch paths but also for MCP
   RPC `tools/call` flows that carry the same bounded file-touching context
4. when the exposed tool surface returns `tool_not_found`, operators should
   still read the attempted bounded file-touch as potentially meaningful file-work
   context rather than as worthless noise
5. the work loop should naturally produce a durable file-work record linked to
   the workflow rather than relying only on local recollection later

Operational implication:

- if file-touching work occurred but file-work memory remains absent, read that
  as a resumability gap and inspect the runtime flow, not as a harmless
  observability-only miss

Recommended operator verification:

- confirm the active work loop has a workflow identifier
- run a bounded file-touching MCP action in that workflow
- if the client uses MCP RPC, verify the same behavior through a `tools/call`
  path rather than checking only direct runtime dispatch
- if the visible tool surface returns `tool_not_found`, confirm whether the
  attempted bounded file-touch still produced durable file-work memory
- check that file-work memory becomes visible in the expected observability
  surfaces
- keep using explicit `file_work_record` when operators want a deliberate,
  human-chosen summary or when diagnosing automation gaps

## 15.5 Permission denied on `public` objects

This can be expected if a dashboard or query accidentally hits raw tables instead of views.

Fix:

- update dashboard query to use `observability.*`
- do not weaken the Grafana role just to “make it work”

---

## 15.6 Derived Memory Items panel shows `No data`

This should be read carefully.

Preferred operator reading:

- `0` with an explicit derived state is better than ambiguous `No data`
- derived memory state should be interpreted together with:
  - canonical summary count
  - canonical summary membership count
  - AGE graph readiness
- the main operator question is not only “how many derived items exist?” but also
  “why are they absent?”

Recommended state model:

- `ready`
  - derived memory items are present
- `not_materialized`
  - no canonical summary memberships exist yet, so there is nothing useful to derive
- `canonical_only`
  - canonical summary state exists, the derived graph layer is readable, but
    derived memory items themselves are not materialized
- `degraded`
  - derivation should exist, but the supporting derived layer is unavailable,
    stale, or otherwise unhealthy
- `unknown`
  - observability cannot currently explain the state confidently

Recommended derived graph status reading:

- `graph_ready`
  - the derived graph layer is readable
- `graph_stale`
  - the derived graph exists but does not match canonical summary state closely enough
- `graph_degraded`
  - the derived graph layer should be treated as unhealthy
- `unknown`
  - the operator surface cannot explain the graph condition confidently
- `none`
  - no graph status should be inferred for this row yet

Operational guidance:

- if canonical summary and membership counts are both zero, treat missing derived
  items as normal `not_materialized` behavior
- if canonical summary state exists but the derived item count is still zero,
  prefer an explicit state such as `canonical_only` over leaving the panel at
  `No data`
- if derived state is `canonical_only` and derived graph status is `graph_ready`,
  read that as “canonical summary state is healthy, but derived memory items are
  not materialized”
- if derived state is `degraded` and derived graph status is `graph_stale` or
  `graph_degraded`, read that as a derived-layer problem, not as canonical
  summary loss
- if derived state is `unknown`, inspect the SQL view, dashboard query, and
  runtime readiness surfaces before assuming the product state itself is unknown
- if the panel truly has no returned row, inspect the underlying SQL view or
  dashboard query before assuming the product state itself is unknown

Recommended dashboard posture:

- show:
  - derived item count
  - derived state
  - derived graph status
  - derived reason
- avoid a panel design where the operator only sees `No data` with no explanation

---

## 15.7 SQL errors in dashboard panels

Possible causes:

- edited panel query references non-existent columns
- observability view definition drifted from current schema
- dashboard JSON was changed but not validated

Fix:

- inspect panel query
- validate against psql
- update the view or query conservatively

---

## 15.8 Placeholder secrets accidentally used

If you started Grafana with placeholder passwords:

- rotate the Grafana admin password
- rotate the Grafana PostgreSQL role password
- restart the stack with correct env values
- validate against psql
- update the view or query conservatively

---

## 15.5 Placeholder secrets accidentally used

If you started Grafana with placeholder passwords:

- rotate the Grafana admin password
- rotate the Grafana PostgreSQL role password
- restart the stack with correct env values

---

## 16. Safe query guidance for operators

When editing or adding dashboards, prefer:

- simple aggregates
- explicit grouping
- clear aliases
- observability views over raw tables

Good query patterns:

```/dev/null/sql#L1-3
SELECT status, workflow_count
FROM observability.workflow_status_counts
ORDER BY status;
```

```/dev/null/sql#L1-3
SELECT provenance, memory_item_count
FROM observability.memory_item_provenance_counts
ORDER BY provenance;
```

Avoid:

- complex ad hoc joins against raw canonical tables in Grafana
- free-text variable interpolation when bounded choices are possible
- mutation-capable SQL assumptions

---

## 17. Change management guidance

If schema changes affect dashboards:

1. update observability views first
2. keep view column names stable where possible
3. only then update dashboards if necessary
4. re-validate against real data
5. update documentation if operator-visible behavior changed

This keeps Grafana more stable across internal schema evolution.

---

## 18. Recommended next dashboard additions

The repository currently includes a runtime overview dashboard definition.

Recommended next additions:

- `memory_overview.json`
- `failure_overview.json`
- `workflow_activity.json`

Suggested content:

### Memory overview
- episodes total
- memory items total
- memory embeddings total
- memory relations total
- provenance breakdown
- recent memory activity timestamps

### Failure overview
- failures by status
- recent projection failures
- open failures table
- retry-count visibility
- recent resolved/ignored failures

### Workflow activity
- recent workflows table
- workflow status trends
- checkpoint activity over time
- verify report activity over time

---

## 19. Shutdown and cleanup

To stop the Grafana overlay while keeping the base stack:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml stop grafana
```

To stop the full stack:
To fully remove the observability overlay resources:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down
```

To remove Grafana data volume as well:
If you also want to remove Grafana persisted state volume:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down -v
```

Be aware that removing the Grafana volume deletes local dashboard/UI state stored in Grafana.

---

## 20. Operator summary

The intended Grafana operational model is:

- PostgreSQL remains canonical
- CLI remains terminal/operator-friendly inspection
- Grafana is optional visual read-only observability
- Grafana uses:
  - dedicated read-only DB credentials
  - `observability` schema
  - stable SQL views
- dashboard issues should be debugged without relaxing write protections

If something seems inconsistent, trust order should be:

1. canonical PostgreSQL state
2. CLI commands that summarize canonical state
3. Grafana dashboards built on observability views