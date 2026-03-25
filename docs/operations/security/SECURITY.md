# Security

## 1. Purpose

This document describes the current security posture of `ctxledger` in `v0.1.0`, including:

- authentication expectations
- transport exposure guidance
- secret-handling guidance
- operational considerations for `/debug/*`
- operational cautions for HTTP action routes
- current limitations that operators should understand before deployment

`ctxledger` is still in an early implementation phase.  
The goal of this document is to make the present security boundary explicit, not to claim a fully mature security model.

This document should be read together with the phased auth strategy in `docs/project/releases/plans/auth_proxy_scaling_plan.md`, especially when comparing the current proxy-first small pattern with the deferred large-pattern direction.

For current deployment guidance, use:

- `docs/operations/deployment/deployment.md`
- `docs/operations/runbooks/small_auth_operator_runbook.md`

---

## 2. Current Security Model

In `v0.1.0`, the primary formal security boundary is:

- proxy-layer authentication in front of protected HTTP endpoints

This means the current model is centered on **coarse-grained transport access control**, not fine-grained authorization.

At a high level:

- authentication is expected at the reverse-proxy or auth-gateway boundary
- debug endpoint exposure is configurable
- secrets are expected to be supplied through environment-based configuration
- production deployments are expected to rely on reverse proxies and TLS

The repository now also has a documented **proxy-first small pattern** in which:

- Traefik is the externally exposed entrypoint
- a lightweight forward-auth service validates a shared bearer token
- the `ctxledger` backend remains private behind the proxy

This is the currently implemented proxy-first deployment pattern.

A future **large pattern** is still planned as a later phase. In that phase:

- the reverse-proxy/auth-gateway layer should remain the primary authentication boundary
- a more identity-aware auth layer should replace the small shared-token gate
- application-level authorization requirements should be re-evaluated before claiming true multi-user safety

---

## 3. Authentication

## 3.1 Proxy-Only Authentication Model

`ctxledger` should now be understood as operating under a **proxy-only authentication model**.

In this model:

- authentication is enforced at the reverse-proxy/auth-gateway layer
- the application backend is kept private behind that proxy
- external clients authenticate to the proxy, not directly to `ctxledger`
- the backend focuses on MCP, workflow, memory, and persistence behavior rather than end-user auth flows

For the currently implemented small pattern, this means:

- Traefik is the externally exposed entrypoint
- a lightweight forward-auth service validates a shared bearer token
- requests without a valid token are rejected before they reach `ctxledger`
- the backend itself does not own the bearer-token gate

## 3.2 Configuration Expectations

Recommended configuration rules:

1. treat the reverse proxy as the primary authentication boundary for any non-private deployment
2. supply proxy-layer secrets through environment variables or secret-management tooling
3. do not store real tokens or gateway credentials in tracked repository files
4. rotate proxy-layer secrets using normal operational secret-rotation processes
5. keep the `ctxledger` backend private and avoid direct public exposure

This keeps the authentication boundary replaceable and avoids coupling the application core to a single auth mechanism.

## 3.3 Scope of the Current Auth Boundary

The current authentication model should still be understood as a **single shared access boundary**.

What has changed is **where** that boundary is enforced:

- previously, an operator might think about bearer auth at the application layer
- now, the intended enforcement point is the proxy/auth layer in front of the application

This model still does **not** imply:

- per-user identity inside the application domain
- per-workspace access control
- role-based authorization
- tenant isolation
- audit-grade session management

Operators should therefore treat the current model as:

- strong enough for proxy-gated operator or shared-trust use
- not yet a complete multi-user authorization architecture

In the implemented small pattern, the shared bearer token is enforced entirely at the proxy/auth layer, but the security semantics are still fundamentally:

- a shared operator boundary
- not a distinct-user identity model
- not full multi-user authorization

For the future large pattern, the security goal should be to improve the **identity layer at the proxy boundary first**, while avoiding premature claims that the application itself already enforces per-user ownership or authorization semantics.

---

## 4. Debug Endpoint Exposure

`ctxledger` exposes operational debug endpoints under `/debug/*`.

Current debug surfaces include:

- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`

Representative HTTP route names exposed by these debug surfaces may include:

- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`

These endpoints are useful for diagnostics, but they can reveal operational metadata such as:

- registered HTTP routes such as:
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
- runtime wiring state

Because of this, `/debug/*` should be treated as operationally sensitive.

## 4.1 Exposure Policy

Recommended policy:

1. use `/debug/*` for operator visibility, not for general client access
2. disable `/debug/*` in internet-exposed production deployments unless there is a clear operational need
3. if `/debug/*` must remain enabled, keep it behind the same authentication boundary as other protected HTTP routes
4. prefer additional network restriction through reverse proxy policy, VPN, private networking, or IP allowlisting where appropriate

## 4.2 Configuration Control

Relevant configuration:

- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`

Current behavior:

- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=true` or unset
  - `/debug/*` routes are registered
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`
  - `/debug/*` routes are not registered at all

This is intentional.  
The preferred posture for disabled debug endpoints is to remove them from the exposed route surface rather than leave them registered and rely only on handler behavior.

## 4.3 Interaction with Authentication

Under the proxy-only authentication model:

- `/debug/*` should follow the same proxy-layer authentication boundary as other protected HTTP routes
- these routes should not be exposed by bypassing the reverse proxy
- operators should think of `/debug/*` as protected operational surfaces, not as client-facing endpoints

Recommended production posture:

- keep `/debug/*` disabled unless there is a clear operator need
- keep the backend private
- place the service behind TLS and a reverse proxy
- ensure `/debug/*` remains behind the same proxy auth gate as `/mcp` when enabled

If an operator has a strong reason to keep `/debug/*` enabled in production, then those endpoints should remain:

- behind proxy-layer authentication
- behind TLS
- behind a reverse proxy
- restricted to trusted operators

This recommendation is especially important for the documented proxy-first deployment patterns:

- in the small pattern, `/debug/*` should remain behind the same Traefik + forward-auth gate as `/mcp`
- in a future large pattern, `/debug/*` should remain behind the identity-aware proxy/gateway layer and should not become a casually exposed multi-user surface



- successful operator-triggered ignore/resolve actions
- rejected requests caused by proxy-auth failure
- invalid-path `404 not_found` responses caused by proxy or caller path mismatch
- validation-driven `400 invalid_request` responses caused by malformed or missing selector fields

Representative operational risks include:

- hiding active failure visibility too early by marking failures as `ignored`
- asserting successful recovery semantics too early by marking failures as `resolved`
- allowing broad callers to mutate workflow-related operational state without sufficient operator intent
- confusing projection artifact state with failure lifecycle state
- allowing alternate proxy path conventions to drift away from the implemented application contract
- losing enough request context that manual closure activity becomes difficult to audit during later investigation

Recommended production posture:

- require authentication for HTTP access
- expose mutation routes only to trusted operators
- place the service behind TLS and a reverse proxy
- treat these routes as operational control surfaces rather than public integration endpoints

For the current proxy-first direction, this should be read as:

- small pattern: keep these routes behind the same shared-token proxy gate used for `/mcp`
- large pattern: keep these routes behind the future identity-aware proxy layer unless and until application-level authorization semantics are explicitly designed and implemented

---

## 5. Transport Security

## 5.1 TLS

For production-like deployment, do not rely on plaintext public HTTP exposure.

Recommended approach:

- place `ctxledger` behind a reverse proxy
- terminate TLS at the proxy or an equivalent secure boundary
- forward only the required HTTP surface to the application

## 5.2 Reverse Proxy

A reverse proxy is recommended for:

- TLS termination
- access restriction
- request logging
- header policy enforcement
- network segmentation
- future rate-limiting or WAF-style controls

`ctxledger` should generally not be treated as a directly internet-facing service without additional infrastructure controls.

---

## 6. Secret Handling

Secrets may include:

- proxy-layer bearer tokens or gateway credentials
- IdP client credentials for future large-pattern deployments
- database credentials embedded in `CTXLEDGER_DATABASE_URL`

Recommended handling:

- inject secrets through environment variables or secret-management tooling
- avoid committing secrets to the repository
- avoid hardcoding secrets in sample configs intended for version control
- prefer secret injection at deploy time
- rotate secrets using normal operational procedures

Do not place real secrets in:

- `README.md`
- example `.env` files committed to the repository
- Dockerfiles
- source code
- test fixtures intended for non-local use

---

## 7. Deployment Recommendations

## 7.1 Local Development

A reasonable local posture is:

- the documented local operator-facing path should use the HTTPS-terminated proxy-first small pattern
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=true` can remain useful for local operator visibility when kept behind the same proxy boundary
- once the deployment is shared or exposed beyond a single trusted operator, keep the backend private and use the documented HTTPS proxy entrypoint rather than any direct host-exposed HTTP path

This is acceptable only when the environment is controlled, the backend remains private, and operator-facing access is still routed through the HTTPS proxy entrypoint.

## 7.2 Shared Internal Environments

For shared internal environments, prefer:

- proxy-layer authentication in front of the backend
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=true` only if operators need it
- reverse proxy access controls where practical
- private backend networking

## 7.3 Internet-Exposed Production

For internet-exposed production deployments, prefer:

- proxy/gateway-enforced authentication
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`
- TLS termination
- reverse proxy enforcement
- secret-management-based configuration
- minimal network exposure
- private backend networking for `ctxledger`

---

## 8. Current Limitations

Operators should understand the current limits of `v0.1.0`.

Not yet provided as a complete security model:

- fine-grained authorization
- RBAC
- multi-tenant isolation
- per-user identity and session management
- audit logging guarantees
- policy-driven access control
- rate limiting as an application-native feature

This means deployment architecture still matters significantly.  
A secure production posture depends not only on `ctxledger` configuration, but also on:

- proxy configuration
- network topology
- secret handling
- operator access controls

---

## 9. Security Review Guidance

Before deploying `ctxledger` beyond local development, verify at least the following:

1. proxy-layer authentication is enabled where appropriate
2. proxy-layer secrets or gateway credentials are provided securely and not committed to source control
3. `/debug/*` exposure matches the intended environment
4. production deployments disable unnecessary debug routes
5. HTTP traffic is protected by TLS
6. the service is placed behind a reverse proxy or equivalent boundary
7. database credentials are handled as secrets
8. only required ports are exposed
9. logs do not unintentionally leak secrets

---

## 10. Summary

The core security guidance for `ctxledger` `v0.1.0` is:

- use proxy-layer authentication for non-private HTTP deployments
- treat `/debug/*` as operationally sensitive
- disable debug routes in internet-exposed production by default
- use TLS and a reverse proxy
- manage proxy credentials and database credentials as secrets
- understand that the current model is authentication-first, not full authorization

As the project evolves, this document should be extended to cover:

- stronger authorization boundaries
- auditability
- tenant isolation
- rate limiting
- broader production hardening guidance