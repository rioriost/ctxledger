# Contributing

## 1. Purpose

This guide helps you contribute to `ctxledger` with a shared understanding of:

- development setup
- coding guidelines
- pull request process
- commit conventions
- documentation paths that matter for MCP, auth, and deployment work

`ctxledger` is an HTTP-first remote MCP server with PostgreSQL-backed workflow state.
Recent repository direction also assumes a **proxy-first authentication model** for documented non-private deployments.

---

## 2. Development Setup

Before contributing, make sure you have:

- Python `3.14+`
- Docker and Docker Compose
- PostgreSQL access through the provided Docker setup, or an equivalent local environment
- the ability to run the project test suite

PostgreSQL integration tests are expected to avoid mutating or truncating any pre-existing working history in the default database schema. The current repository direction is to run persistence integration tests in an isolated temporary PostgreSQL schema and drop that schema after the test completes.

Typical local startup path:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml up -d --build
```

Typical test command:

```/dev/null/sh#L1-1
pytest -q
```

If you are working on the proxy-protected small auth pattern, also review:

- `docs/operations/runbooks/small_auth_operator_runbook.md`
- `docs/project/releases/plans/auth_proxy_scaling_plan.md`

---

## 3. Recommended Reading Before You Change Things

The right docs to read depend on the kind of change you are making.

### Core repository context
Read these first when you are new to the repo:

- `README.md`
- `docs/project/product/specification.md`
- `docs/project/product/architecture.md`
- `docs/project/product/workflow-model.md`
- `docs/project/product/mcp-api.md`
- `docs/operations/deployment/deployment.md`
- `docs/operations/security/SECURITY.md`

### MCP transport or protocol work
If your change affects MCP behavior, HTTP transport, or protocol claims, also read:

- `docs/project/releases/plans/domains/mcp/mcp_planning_index.md`

Then follow the linked planning documents from there.

### Auth, proxy, or deployment-boundary work
If your change affects authentication, reverse proxy behavior, protected routes, or deployment guidance, read:

- `docs/project/releases/plans/domains/auth/auth_planning_index.md`
- `docs/operations/runbooks/small_auth_operator_runbook.md`
- `docs/project/releases/plans/domains/auth/auth_proxy_scaling_plan.md`
- `docs/project/releases/plans/domains/auth/auth_large_gateway_evaluation_memo.md`
- `docs/project/releases/plans/domains/auth/auth_large_gateway_shortlist_example.md`

If you are preparing a future large-pattern gateway selection record, also review:

- `docs/project/releases/plans/domains/auth/auth_large_gateway_decision_record_template.md`

### Why these auth docs matter
The current documented posture is:

- `ctxledger` should stay focused on MCP, workflow, memory, and persistence behavior
- authentication for documented shared or internet-exposed paths should be enforced at the proxy or gateway boundary
- the current implemented small pattern is proxy-only auth
- the large pattern is still design-prep, not active implementation

Do not reintroduce app-layer auth assumptions casually in code, docs, examples, or Compose files.

---

## 4. Coding Guidelines

### 4.1 Preserve architectural direction
Prefer changes that keep these boundaries clear:

- canonical state in PostgreSQL
- projections as derived artifacts
- MCP as the public interface
- HTTP runtime behavior separated from workflow business logic
- authentication externalized to the proxy/gateway layer where documented

### 4.2 Keep changes scoped
A good contribution should usually do one of the following:

- fix a specific bug
- add a focused feature
- improve tests
- improve docs
- perform a bounded cleanup

Avoid mixing unrelated refactors into a feature PR unless the cleanup is truly necessary for correctness.

### 4.3 Prefer explicitness
When changing behavior, keep these visible:

- public entrypoints
- response shapes
- route expectations
- configuration effects
- deployment assumptions

### 4.4 Be careful with current-state wording
Some documents are historical planning artifacts.
When editing docs, distinguish between:

- current implemented repository shape
- future design intent
- historical plan language

Do not silently upgrade a plan or aspiration into a claim of implemented behavior.

### 4.5 Auth-specific caution
If you touch:

- Docker Compose files
- reverse proxy configuration
- auth-related docs
- MCP examples with headers
- debug/operator route protection guidance

make sure your change still matches the current proxy-first model.

In particular:

- do not add deprecated direct-backend auth environment variables back into Compose
- do not describe protected access as if `ctxledger` itself is the documented auth boundary
- do not imply large-pattern identity-aware gateway selection has already been finalized

### 4.6 PostgreSQL integration test isolation
If you touch:

- PostgreSQL integration tests
- PostgreSQL persistence setup
- schema bootstrap behavior
- repository-level persistence assumptions

preserve isolation from any pre-existing operator or development history stored in PostgreSQL.

In particular:

- do not truncate or delete rows from the default working schema just to prepare tests
- prefer creating a dedicated temporary schema for each PostgreSQL integration test scope
- apply the repository schema into that temporary schema
- ensure the test connection/session uses that schema explicitly
- drop the temporary schema after the test completes
- keep persistence integration tests safe to run even when the local PostgreSQL instance already contains useful workflow history

---

## 5. Testing Expectations

Run the most relevant tests for your change.

### Minimum expectation
For normal Python or doc-adjacent code changes, run:

```/dev/null/sh#L1-1
pytest -q
```

### For PostgreSQL persistence or integration-test changes
If your change affects PostgreSQL persistence behavior or repository integration tests, verify not only that the tests pass, but also that they preserve local working history outside the temporary test schema.

Expected behavior for PostgreSQL integration tests:

- each test scope creates its own temporary schema
- schema bootstrap is applied inside that temporary schema
- the test session uses that schema through connection/session configuration
- the temporary schema is dropped after the test completes
- the default working schema and any existing workflow history remain untouched

### For MCP or workflow behavior changes
You should strongly consider running the full suite.

### For small auth / proxy work
You should also validate the default small pattern operationally when your change affects:

- Compose topology
- Traefik config
- `auth-small`
- Grafana integration in the default stack
- AGE-enabled PostgreSQL behavior in the default stack
- auth-related docs that describe actual operator steps
- smoke-script expectations
- local HTTPS proxy guidance or certificate-handling steps

Representative small-pattern validation flow:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans
```

```/dev/null/sh#L1-2
mkdir -p docker/traefik/certs
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token wrong-token --expect-http-status 401 --expect-auth-failure --insecure
```

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token replace-me-with-a-strong-secret --insecure --scenario workflow --workflow-resource-read
```

Expected local HTTPS setup notes:

- local certificate files should exist at:
  - `docker/traefik/certs/localhost.crt`
  - `docker/traefik/certs/localhost.key`
- do not commit real certificate or key material
- use a trusted local certificate when possible, or use local-only insecure verification for self-signed testing
- the default local stack is HTTPS-only; do not validate or document a public `http://127.0.0.1:8091` entrypoint for this flow
- the default local stack should be treated as:
  - authenticated
  - AGE-enabled
  - Grafana-enabled

Use `--insecure` only for local self-signed or otherwise untrusted certificates. If the local certificate is trusted, prefer normal TLS verification.

If your auth-related change is docs-only and does not alter runtime behavior, note that in the PR.

---

## 6. Pull Request Process

A good PR should include:

1. a clear problem statement
2. the scope of the change
3. any architectural or deployment impact
4. test evidence
5. doc updates when behavior or operator expectations changed

### PR description checklist
Include, where relevant:

- what changed
- why it changed
- whether MCP behavior changed
- whether deployment behavior changed
- whether auth/proxy expectations changed
- what tests you ran
- whether docs were updated

### When docs are required
You should update docs if your change affects:

- user-visible behavior
- MCP surface
- route names or route expectations
- auth boundary expectations
- deployment steps
- operator runbooks
- release-acceptance framing

---

## 7. Commit Conventions

Use descriptive commit messages.

Good examples:

- `Remove app-layer HTTP auth in favor of proxy auth`
- `Add Traefik small auth deployment pattern`
- `Add small auth operator runbook`
- `Add large auth gateway decision template`

Avoid vague messages like:

- `fix stuff`
- `updates`
- `misc cleanup`

---

## 8. Auth and Deployment Docs Map

Use this quick map when contributing around auth or deployment topics.

### Small pattern, implemented
- `docs/operations/runbooks/small_auth_operator_runbook.md`
- `docs/project/releases/plans/domains/auth/auth_proxy_scaling_plan.md`
- `README.md`
- `docs/operations/deployment/deployment.md`
- `docs/operations/security/SECURITY.md`

### Large pattern, design-prep only
- `docs/project/releases/plans/domains/auth/auth_large_gateway_evaluation_memo.md`
- `docs/project/releases/plans/domains/auth/auth_large_gateway_shortlist_example.md`
- `docs/project/releases/plans/domains/auth/auth_large_gateway_decision_record_template.md`

### Current expectations
- small pattern is implemented and validated
- large pattern is deferred and should remain gated
- actual gateway selection should be recorded through the decision-record template when the phase gate is reached

---

## 9. Final Guidance

When in doubt, optimize for:

- correctness
- explicitness
- scoped changes
- accurate docs
- consistency with the repository’s current proxy-first auth model

If your change touches both runtime behavior and operator expectations, update both code and docs together.