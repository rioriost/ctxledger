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

- `docs/deployment.md`
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

## 15.3 Permission denied on `public` objects

This can be expected if a dashboard or query accidentally hits raw tables instead of views.

Fix:

- update dashboard query to use `observability.*`
- do not weaken the Grafana role just to “make it work”

---

## 15.4 SQL errors in dashboard panels

Possible causes:

- edited panel query references non-existent columns
- observability view definition drifted from current schema
- dashboard JSON was changed but not validated

Fix:

- inspect panel query
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