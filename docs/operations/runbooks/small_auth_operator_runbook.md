# Small-Pattern Auth Operator Runbook

## 1. Purpose

This runbook describes how to operate the documented **small auth pattern** for `ctxledger`.

The small pattern is the current proxy-first deployment shape for:

- one trusted operator
- local development
- tightly controlled private environments
- MCP-capable IDE clients that can send bearer headers

It is intended to keep the `ctxledger` backend private while enforcing authentication at the proxy boundary.

---

## 2. Topology Summary

The small pattern uses this request path:

```/dev/null/txt#L1-5
IDE client or smoke client
  -> Traefik
  -> auth-small
  -> private ctxledger backend
  -> PostgreSQL
```

Operationally, that means:

- `traefik` is the only host-exposed HTTPS entrypoint
- `auth-small` validates `Authorization: Bearer <token>`
- `ctxledger` runs as a private backend service with no direct host port exposure in this mode
- PostgreSQL remains internal to the compose network

---

## 3. Files and Ports

Primary files for this mode:

- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`
- `docker/traefik/dynamic.yml`
- `docker/auth_small/src/auth_small_app.py`
- `scripts/mcp_http_smoke.py`

Note:

- the compose files no longer carry deprecated direct-backend auth environment variables for `ctxledger`
- proxy-layer authentication for this mode is owned by `auth-small` and Traefik

Primary externally used port:

- `8443` for the Traefik HTTPS entrypoint

Important environment variable:

- `CTXLEDGER_SMALL_AUTH_TOKEN`

---

## 4. Preconditions

Before starting the small pattern, ensure:

1. Docker and Docker Compose are available
2. port `8443` is free on the host
3. PostgreSQL local port usage from other stacks will not conflict with the base compose setup
4. local certificate files exist for Traefik at:
   - `docker/traefik/certs/localhost.crt`
   - `docker/traefik/certs/localhost.key`
5. you have chosen a bearer token value for:
   - `CTXLEDGER_SMALL_AUTH_TOKEN`

Representative token shape:

```/dev/null/txt#L1-1
replace-me-with-a-strong-secret
```

For real shared or long-lived environments, use a strong random secret rather than a memorable placeholder.

---

## 5. Start Procedure

Start the small-pattern stack with the base compose file plus the auth overlay.

For a **first start** or an intentional clean rebuild of the stack, use:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate
```

For a **normal restart** after the stack has already been created, you usually do **not** need `--force-recreate`:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d
```

If you changed code or image inputs and want a normal rebuild without forcibly replacing every container, use:

```/dev/null/sh#L1-1
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

Use `--force-recreate` only when you intentionally want to replace existing containers, such as after a major compose/config change or when you want a known-fresh container set.

Expected high-level outcome:

- PostgreSQL starts
- `auth-small` starts
- private `ctxledger` backend starts
- Traefik starts on `8443`

---

## 6. Health Verification

After startup, verify that the services are up.

A representative container status check is:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps
```

You should expect the stack to show the core services as running and healthy where healthchecks are defined.

The intended service roles are:

- `ctxledger-postgres`
- `ctxledger-auth-small`
- private `ctxledger` backend service
- `ctxledger-traefik`

---

## 7. Authentication Verification

The first operator task after startup should be to verify both rejection and allow paths.

### 7.1 Missing token must fail

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

Expected result:

- HTTP status `401`
- request rejected before reaching the private backend

### 7.2 Invalid token must fail

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token wrong-token --expect-http-status 401 --expect-auth-failure --insecure
```

Expected result:

- HTTP status `401`
- request rejected before reaching the private backend

### 7.3 Valid token must pass

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token replace-me-with-a-strong-secret --scenario workflow --workflow-resource-read --insecure
```

Expected result:

- authenticated request passes through Traefik and `auth-small`
- MCP workflow and resource smoke succeeds

---

## 8. Functional Verification Scope

The recommended happy-path smoke verifies the proxy-protected deployment still supports:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`

It also verifies workflow-oriented operations, including:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

and workflow resource reads for:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

---

## 9. MCP Client Configuration

Point the client at the Traefik endpoint, not the private backend.

Representative endpoint:

```/dev/null/txt#L1-1
https://localhost:8443/mcp
```

The client should send the same bearer token configured through `CTXLEDGER_SMALL_AUTH_TOKEN`.

Representative request header:

```/dev/null/http#L1-1
Authorization: Bearer replace-me-with-a-strong-secret
```

Operational rule:

- if the client is configured for `http://127.0.0.1:8080/mcp`, that is a stale direct-local path and not the small-pattern proxy path
- for this runbook, the intended operator path is `https://localhost:8443/mcp`

---

## 10. Shutdown Procedure

To stop the base stack only:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml down
```

To stop the small-pattern stack cleanly, use the same compose layering that was used for startup:

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans
```

This is the safer shutdown command for this mode because it tears down the overlay-defined services as well.

---

## 11. Common Failure Modes

## 11.1 `401` for every request, including the supposed valid token

Likely causes:

- `CTXLEDGER_SMALL_AUTH_TOKEN` at startup does not match the token used by the client
- shell history or copied command still uses an old token
- client is sending the wrong header value format

Check:

- the startup command token value
- the client header value
- that the header format is exactly `Authorization: Bearer <token>`

---

## 11.2 Connection or routing failure through `8443`

Likely causes:

- Traefik did not start correctly
- dynamic proxy configuration was not loaded as expected
- the request path is wrong
- the stack was started without the auth overlay
- certificate files are missing or unreadable

Check:

- that the stack was started with both compose files
- that the request target is `https://localhost:8443/mcp`
- that `docker/traefik/certs/localhost.crt` and `docker/traefik/certs/localhost.key` exist
- container logs if needed

---

## 11.3 Backend reachable directly on host port when it should be private

Likely causes:

- wrong compose command was used
- the base stack is still running separately from a previous direct-local session
- the operator is accidentally testing a stale direct local deployment path instead of the small pattern

Check:

- whether you started with:
  - `docker/docker-compose.yml`
  - and `docker/docker-compose.small-auth.yml`
- whether the test target is `8443` instead of a stale direct port such as `8080`

Also confirm the compose files themselves are in the cleaned-up shape:

- the backend service should not rely on deprecated direct auth environment variables
- proxy enforcement in this mode should come from Traefik plus `auth-small`

Operational intent for the small pattern is:

- Traefik exposed
- backend private

---

## 11.4 Smoke fails after auth succeeds

Likely causes:

- database/schema issue
- backend startup issue
- regression in MCP routes or workflow paths
- stale containers from an older stack state

Recommended operator response:

1. confirm the auth rejection path still works
2. confirm the valid-token request is passing auth
3. recreate the stack with `--force-recreate`
4. re-run the workflow smoke
5. inspect service logs if the failure persists

---

## 11.5 Wrong path used for operator HTTP action routes

Projection failure action routes require strict path shapes:

- `/projection_failures_ignore`
- `/projection_failures_resolve`

Unexpected path shapes should return `404 not_found`.

If a proxy or caller uses an alternate path, treat that as a routing/configuration problem rather than an application-state problem.

---

## 12. Operational Notes

Important current design notes:

- authentication is expected at the proxy boundary, not inside `ctxledger`
- `ctxledger` no longer relies on app-layer bearer authentication in the documented deployment path
- the compose configuration for this mode has also been cleaned up to remove deprecated direct-backend auth environment variables
- the small pattern is intentionally a shared-token model
- this is acceptable for one trusted operator or a tightly controlled small environment
- this is not yet a distinct-user or full multi-user authorization model

That means this pattern is suitable as:

- a local secure default
- a private shared-trust deployment step
- a bridge toward later large-pattern gateway evaluation

but not as a final multi-user identity architecture.

---

## 13. Recommended Operator Checklist

Use this quick checklist for a normal work loop.

### Startup
- choose `CTXLEDGER_SMALL_AUTH_TOKEN`
- start the stack with both compose files
- verify service status

### Auth verification
- run missing-token smoke and confirm `401`
- run invalid-token smoke and confirm `401`
- run valid-token workflow/resource smoke and confirm success

### Client setup
- point the client to `https://localhost:8443/mcp`
- send `Authorization: Bearer <token>`
- trust the local certificate chain or use a local-only insecure/testing mode when appropriate

### Shutdown
- stop the layered stack with the same compose files
- remove orphans if needed

---

## 14. Escalation Notes

If the small pattern is no longer sufficient, the next step should not be to reintroduce app-layer auth into `ctxledger`.

Instead, the follow-on direction is:

- keep `ctxledger` private
- keep auth at the proxy/gateway boundary
- evaluate large-pattern identity-aware gateway options as a later design phase

That later phase is documented separately in:

- `docs/plans/auth_proxy_scaling_plan.md`
- `docs/plans/auth_large_gateway_evaluation_memo.md`
