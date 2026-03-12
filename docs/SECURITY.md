# Security

## 1. Purpose

This document describes the current security posture of `ctxledger` in `v0.1.0`, including:

- authentication expectations
- transport exposure guidance
- secret-handling guidance
- operational considerations for `/debug/*`
- current limitations that operators should understand before deployment

`ctxledger` is still in an early implementation phase.  
The goal of this document is to make the present security boundary explicit, not to claim a fully mature security model.

---

## 2. Current Security Model

In `v0.1.0`, the primary formal security boundary is:

- bearer token authentication for protected HTTP endpoints

This means the current model is centered on **coarse-grained transport access control**, not fine-grained authorization.

At a high level:

- authentication is available at the HTTP boundary
- debug endpoint exposure is configurable
- secrets are expected to be supplied through environment-based configuration
- production deployments are expected to rely on reverse proxies and TLS

---

## 3. Authentication

## 3.1 Bearer Token Authentication

When HTTP authentication is enabled, `ctxledger` expects a configured bearer token.

Relevant configuration:

- `CTXLEDGER_REQUIRE_AUTH`
- `CTXLEDGER_AUTH_BEARER_TOKEN`

Expected behavior:

- if `CTXLEDGER_REQUIRE_AUTH=true`, a bearer token must be configured
- if authentication is enabled, protected HTTP endpoints require a valid bearer token
- requests without a token should be rejected
- requests with an invalid token should be rejected

This is intended to provide a simple deployment-ready protection layer for operator-controlled environments.

## 3.2 Configuration Expectations

Recommended configuration rules:

1. set `CTXLEDGER_REQUIRE_AUTH=true` for any HTTP deployment that is not fully private
2. set `CTXLEDGER_AUTH_BEARER_TOKEN` through environment or secret-management tooling
3. do not store bearer tokens in tracked repository files
4. rotate bearer tokens using your normal operational secret-rotation process

If `CTXLEDGER_REQUIRE_AUTH=true` but `CTXLEDGER_AUTH_BEARER_TOKEN` is missing, startup validation should fail.

## 3.3 Scope of the Current Auth Boundary

The current authentication model should be understood as a **single shared access boundary** for protected HTTP routes.

It does **not** currently imply:

- per-user identity
- per-workspace access control
- role-based authorization
- tenant isolation
- audit-grade session management

Operators should treat bearer auth as a basic gate in front of the service, not as a complete security architecture.

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
- `workflow_closed_projection_failures`

These endpoints are useful for diagnostics, but they can reveal operational metadata such as:

- enabled transports
- registered HTTP routes such as:
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`
- registered stdio tools
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

When HTTP bearer authentication is enabled:

- `/debug/*` should follow the same authentication boundary as other protected HTTP endpoints

Recommended production posture:

- `CTXLEDGER_REQUIRE_AUTH=true`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`

If an operator has a strong reason to keep `/debug/*` enabled in production, then those endpoints should remain:

- behind bearer authentication
- behind TLS
- behind a reverse proxy
- restricted to trusted operators

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

- `CTXLEDGER_AUTH_BEARER_TOKEN`
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

- `CTXLEDGER_REQUIRE_AUTH=false`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=true`

This is acceptable only when the environment is controlled and not broadly exposed.

## 7.2 Shared Internal Environments

For shared internal environments, prefer:

- `CTXLEDGER_REQUIRE_AUTH=true`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=true` only if operators need it
- reverse proxy access controls where practical

## 7.3 Internet-Exposed Production

For internet-exposed production deployments, prefer:

- `CTXLEDGER_REQUIRE_AUTH=true`
- a strong `CTXLEDGER_AUTH_BEARER_TOKEN`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false`
- TLS termination
- reverse proxy enforcement
- secret-management-based configuration
- minimal network exposure

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

1. bearer auth is enabled where appropriate
2. bearer token is provided securely and not committed to source control
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

- use bearer authentication for non-private HTTP deployments
- treat `/debug/*` as operationally sensitive
- disable debug routes in internet-exposed production by default
- use TLS and a reverse proxy
- manage bearer tokens and database credentials as secrets
- understand that the current model is authentication-first, not full authorization

As the project evolves, this document should be extended to cover:

- stronger authorization boundaries
- auditability
- tenant isolation
- rate limiting
- broader production hardening guidance