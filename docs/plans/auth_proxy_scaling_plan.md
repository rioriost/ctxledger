# Auth Proxy Scaling Plan for `ctxledger`

## 1. Purpose

This document defines a phased authentication and authorization strategy for `ctxledger` as a remote HTTP MCP server.

The goal is to support two distinct deployment patterns without pushing authentication and authorization logic into the `ctxledger` application itself:

1. **Small pattern**
   - a single engineer
   - local or small private environment
   - MCP-capable IDE such as Zed or VS Code
   - fixed bearer-token style access is acceptable

2. **Large pattern**
   - a cloud deployment
   - multiple engineers in the same organization
   - multiple MCP-capable IDE clients
   - shared static bearer tokens are no longer operationally acceptable

This plan adopts one governing rule:

> `ctxledger` should remain focused on MCP, workflow, memory, and persistence behavior, while authentication and authorization should be handled at the reverse-proxy/auth-gateway layer.

It also records the current product posture explicitly:

- current `ctxledger` design is best understood as a **single-operator or shared-trust** deployment model
- current durable workflow and MCP surfaces are not yet designed around per-user ownership, per-user authorization, or tenant isolation
- the **small pattern** is the immediate implementation target
- the **large pattern** is intentionally deferred and should be treated as a later roadmap item, expected only **after roadmap `0.4`**, and possibly later depending on product priorities

---

## 2. Design Goal

The target architecture should make the following possible:

- `ctxledger` runs as a private backend service
- all external client access goes through a proxy/auth layer
- the **small** deployment uses a lightweight fixed-token gate
- the **large** deployment uses organization-aware identity and access control
- the transition from small to large changes the auth layer, not the `ctxledger` core

The practical implication is:

- `ctxledger` should not become an identity provider
- `ctxledger` should not own end-user login flows
- `ctxledger` should remain deployable behind a replaceable proxy/auth front door

---

## 3. Scope

This plan covers:

- reverse-proxy-centered authentication architecture
- phased small-to-large rollout
- deployment layering
- operator workflow
- future authorization extension points

This plan does **not** yet implement:

- per-workspace authorization inside `ctxledger`
- user ownership models in workflow state
- RBAC/ABAC rules inside the application
- browser-based login UX details for individual IDE vendors

Those may become future work once the proxy-centered authentication strategy is in place.

---

## 4. Current Constraints and Assumptions

Current repository direction and evidence suggest:

- `ctxledger` is an HTTP-only remote MCP server
- the primary MCP surface is exposed at `/mcp`
- the service is already validated through Docker Compose
- clients such as Zed and VS Code can send HTTP headers
- a fixed bearer token works well for small/private use
- the long-term deployment pattern may need to scale to multiple users

Current application-level posture should be stated clearly:

- `ctxledger` currently behaves like a **single-operator** system or a system used by a **shared-trust small group**
- workflow and workspace operations are not yet modeled around distinct end-user identity
- there is not yet a first-class concept of:
  - `user_id`
  - `organization_id`
  - `team_id`
  - tenant-scoped authorization
  - per-user workspace ownership
- this means large-pattern authentication may be introduced at the proxy boundary first, while true multi-user authorization inside the application remains future work

This means the current system is a strong fit for a proxy-first strategy.

---

## 5. Architecture Principle

The intended architecture is:

```/dev/null/txt#L1-6
MCP client (Zed / VS Code)
  -> reverse proxy
  -> auth service / auth gateway
  -> ctxledger
  -> PostgreSQL
```

The `ctxledger` process itself should ideally be:

- reachable only on a private network
- not directly internet-exposed
- not responsible for authenticating end users
- insulated from auth-strategy changes

This lets authentication evolve independently from MCP and workflow behavior.

---

## 6. Why Proxy-Centered Auth Is Preferred

## 6.1 Keeps `ctxledger` focused

`ctxledger` should own:

- MCP endpoint behavior
- workflow tools
- workflow resources
- persistence
- runtime assembly
- operational diagnostics

It should not need to own:

- login pages
- OAuth redirect flows
- token exchange
- IdP integration details
- organization membership lookups

---

## 6.2 Supports small and large with the same backend

If the auth boundary is outside the app, the backend can stay constant while the front-door auth strategy changes.

That gives a clean progression:

- **small**
  - fixed token
- **large**
  - identity-aware gateway

without reworking the application core.

---

## 6.3 Better operational separation

The proxy/auth layer can own:

- TLS termination
- identity verification
- audit points
- request filtering
- optional rate limiting
- network exposure policy

This is a more natural place for security policy than the MCP application layer.

---

## 7. Phased Strategy Overview

This plan is intentionally phased.

## Phase 1 — Small deployment auth
Use:

- Traefik as the public entrypoint
- a lightweight custom auth service
- a fixed bearer token shared by the single user and the auth service
- `ctxledger` behind the proxy

## Phase 2 — Large deployment auth
Replace the lightweight auth service with:

- an identity-aware auth gateway or forward-auth service
- organization login and identity verification
- token/session validation tied to an IdP
- a path toward user-level authorization metadata

The key rule is:

> The Phase 2 migration should mainly replace the auth service and its proxy wiring, not require a major rewrite of `ctxledger`.

---

## 8. Reverse Proxy Choice

## Recommendation: Traefik

For this repository and current Docker Compose workflow, Traefik is the preferred proxy for the phased rollout.

### Why Traefik
- strong Docker Compose ergonomics
- label-based route configuration
- straightforward ForwardAuth model
- easy to place in front of `ctxledger`
- good fit for replacing one auth layer with another later
- natural path from local compose to larger orchestrated environments

### Alternative options
Possible alternatives include:
- nginx
- Caddy
- Envoy
- managed cloud ingress or access gateways

But for this repository’s current stage, Traefik is the best fit for an incremental auth rollout.

---

## 9. Small Pattern Plan

## 9.1 Intended Use Case

This mode is for:

- one developer
- local machine or tightly controlled private environment
- one MCP client operator
- simple secret distribution
- low operational overhead

This is the first implementation target.

---

## 9.2 Small Pattern Requirements

The small pattern should provide:

- a simple bearer-token gate
- no browser login flow
- no IdP dependency
- a predictable Docker Compose setup
- a clean path for IDE configuration
- no authentication logic added to `ctxledger`

---

## 9.3 Small Pattern Target Topology

```/dev/null/txt#L1-6
IDE client
  -> Traefik
  -> lightweight auth service
  -> ctxledger
  -> PostgreSQL
```

### Behavioral expectation
- the client sends `Authorization: Bearer <token>`
- Traefik calls the auth service
- the auth service validates the token
- if valid, the request is forwarded to `ctxledger`
- if invalid, the request is rejected before reaching `ctxledger`

---

## 9.4 Small Pattern Auth Service

## Recommendation
Implement a **small custom auth service** specifically for Traefik ForwardAuth.

### Why custom is preferred here
The small pattern requirements are so limited that full-featured auth products are unnecessarily heavy.

The service only needs to:
- receive the forwarded request metadata from Traefik
- inspect the `Authorization` header
- compare against a configured expected token
- return:
  - `200` if valid
  - `401` if invalid or missing

Optionally it may also return identity headers such as:
- `X-Auth-User: local-dev`
- `X-Auth-Mode: static-token`

These can be useful in future phases, even if `ctxledger` does not consume them initially.

---

## 9.5 Small Pattern Security Properties

This mode is acceptable when:

- there is one trusted operator
- the environment is local or tightly controlled
- token sharing is not a practical concern
- individual-user audit is not required

This mode is **not** sufficient for a true shared organizational deployment because:
- the token is shared
- user identity is not distinct
- revocation is coarse
- auditability is poor

That is expected. It is a stepping stone, not the final enterprise shape.

---

## 9.6 Small Pattern Deployment Model

Recommended configuration principles:

- Traefik is the only public entrypoint
- `ctxledger` is not exposed directly to the host/public network
- the auth service is internal to the compose network
- the bearer token is configured as an environment variable or compose secret
- the IDE points to the Traefik-exposed `/mcp` URL

Recommended operator shape:
- `ctxledger`: private backend service
- `postgres`: private database service
- `auth-small`: internal auth gate
- `traefik`: only externally exposed HTTP service

---

## 9.7 Small Pattern Deliverables

### Deliverable A — Auth service implementation
A minimal service that supports Traefik ForwardAuth token validation.

### Deliverable B — Compose topology
A compose configuration that includes:
- Traefik
- `auth-small`
- `ctxledger`
- PostgreSQL

### Deliverable C — Documentation
README or deployment docs should show:
- how to generate a token
- how to configure the token
- how to point Zed / VS Code to the proxied MCP endpoint
- how to validate the deployment

### Deliverable D — Smoke validation
A small validation path should prove:
- proxy rejects missing/invalid token
- proxy allows valid token
- MCP initialize/list/call works through the proxy

---

## 9.8 Small Pattern Exit Criteria

Phase 1 is complete when:

- `ctxledger` is only reachable through Traefik in the documented setup
- the custom auth service correctly protects `/mcp`
- Zed / VS Code style clients can connect using a bearer token in headers
- workflow-oriented MCP smoke passes through the proxy
- the implementation requires no application-level auth logic inside `ctxledger`

---

## 10. Large Pattern Plan

## 10.1 Intended Use Case

This mode is for:

- cloud-hosted deployment
- multiple engineers
- shared organizational usage
- individual user identity
- future policy or authorization needs
- proper security operations

This is the **second** implementation target.

Timeline note:

- this large-pattern work is **not** the current implementation target
- it should be scheduled **after roadmap `0.4`**, or later if product priorities shift
- before beginning this phase, the project should re-check whether application-level user ownership and authorization semantics are needed in addition to proxy-layer authentication

---

## 10.2 Large Pattern Requirements

The large pattern should provide:

- distinct user identity
- organization-managed login
- revocation and rotation support
- traceable user access
- no shared static token for all engineers
- compatibility with MCP-capable IDEs
- minimal or no auth logic in `ctxledger`

---

## 10.3 Large Pattern Target Topology

```/dev/null/txt#L1-6
IDE client
  -> Traefik
  -> identity-aware auth gateway
  -> ctxledger
  -> PostgreSQL / DBaaS
```

In this phase, the small custom auth service is replaced by a more capable auth layer.

---

## 10.4 Large Pattern Auth Layer Recommendation

### Preferred direction
Use an identity-aware ForwardAuth-compatible service behind Traefik.

Candidate directions include:
- Pomerium
- oauth2-proxy
- another OIDC-aware auth gateway
- an organization-standard identity gateway if one already exists

### Most important requirement
The selected auth layer must support:
- organization identity verification
- user-level access context
- operational compatibility with non-browser MCP clients

---

## 10.5 `oauth2-proxy` as a candidate

`oauth2-proxy` is a valid candidate for the large pattern, but it should not be treated as the only choice.

### Strengths
- widely used
- mature
- OIDC/OAuth integration support
- workable in reverse-proxy deployments

### Caveat
It is often most natural in browser/cookie/redirect-heavy environments.

Because MCP IDE clients are not pure browser apps, the practical client experience must be evaluated carefully.

That means `oauth2-proxy` is:
- a strong candidate
- not automatically the final answer
- especially attractive if the organization already uses it

---

## 10.6 Pomerium as a candidate

Pomerium is also a strong candidate.

### Strengths
- identity-aware proxy orientation
- policy-friendly model
- strong fit for multi-user internal tools
- good long-term scaling posture

### Caveat
It is somewhat heavier than the small auth layer and may be more than needed for a solo-developer setup.

That is acceptable, because it is intended for Phase 2, not Phase 1.

---

## 10.7 Large Pattern Authorization Outlook

This plan intentionally keeps **authentication** outside `ctxledger`.

However, a multi-user deployment may later require **authorization** such as:
- workspace scoping
- team scoping
- read vs write behavior
- organization-level access boundaries

Current state reminder:

- `ctxledger` is not yet documented as a true multi-user application
- introducing large-pattern auth at the proxy boundary does **not** by itself make the application fully multi-user-safe
- large-pattern rollout may therefore need a second design pass for:
  - identity propagation
  - workspace ownership
  - audit attribution
  - authorization rules inside the workflow domain

The best path is:

1. establish user identity at the proxy layer first
2. pass stable identity metadata downstream if needed
3. only add app-layer authorization once real product requirements demand it

This avoids prematurely over-designing authorization inside `ctxledger`.

---

## 10.8 Large Pattern Deployment Model

Recommended principles:

- Traefik remains the public entrypoint
- `ctxledger` remains private behind the proxy
- PostgreSQL may move to DBaaS
- auth is handled by the identity-aware auth layer
- clients connect to the proxy URL, not directly to `ctxledger`

The ideal migration path is:
- same `ctxledger`
- same MCP endpoint behavior
- different auth service
- different operator secrets and identity configuration

---

## 10.9 Large Pattern Deliverables

### Deliverable A — Replaceable auth layer
A documented swap from `auth-small` to `auth-large`.

### Deliverable B — Identity-bearing request path
A reverse-proxy path that can carry stable user identity semantics.

### Deliverable C — Deployment documentation
Docs should explain:
- which IdP is expected
- where auth is enforced
- how clients should be configured
- what the trust boundary is

### Deliverable D — Validation
A shared deployment validation path should prove:
- authenticated users can reach `/mcp`
- unauthorized users cannot
- workflow/resource MCP flows remain correct through the proxy
- identity-aware auth does not break MCP transport behavior

---

## 10.10 Large Pattern Exit Criteria

Phase 2 is complete when:

- the system supports distinct organization users
- shared static credentials are no longer required for routine access
- all client traffic still goes through Traefik
- `ctxledger` remains private and auth-agnostic
- the auth layer can be operated independently of backend workflow logic

---

## 11. Implementation Sequence

The recommended implementation order is:

1. implement Traefik front-door topology
2. implement small custom auth service
3. validate small pattern end-to-end
4. document IDE client configuration for proxied MCP access
5. prepare a replaceable auth-service boundary in compose and docs
6. evaluate large-pattern auth gateway candidates
7. implement the chosen large-pattern auth layer
8. validate multi-user deployment behavior

This sequence reduces risk because the small pattern proves the proxy architecture before organizational auth complexity is introduced.

---

## 12. Validation Strategy

## Small pattern validation
- request without token is rejected
- request with wrong token is rejected
- request with correct token reaches `/mcp`
- MCP initialize/list/call succeeds through Traefik
- workflow/resource smoke succeeds through Traefik

## Large pattern validation
- authenticated organization user can reach `/mcp`
- non-member or unauthorized identity cannot
- auth layer does not break non-browser MCP usage
- workflow/resource smoke succeeds through Traefik
- deployment and operational model remain understandable

---

## 13. Risks and Mitigations

## Risk 1 — Trying to solve large-pattern auth too early
This can overcomplicate the current implementation.

### Mitigation
Deliver the small pattern first and prove the proxy boundary.

---

## Risk 2 — Client UX mismatch with OAuth-style auth
Some auth products are more browser-centric than IDE-centric.

### Mitigation
Treat IDE compatibility as a first-class validation criterion before standardizing on a large-pattern auth gateway.

---

## Risk 3 — Bypassing the proxy
If `ctxledger` is directly exposed, the auth design is weakened.

### Mitigation
Expose only Traefik publicly. Keep `ctxledger` private.

---

## Risk 4 — Authorization needs emerge later
Identity alone may not be enough for shared deployments.

### Mitigation
Keep the current plan focused on auth layering first, but leave room for future identity-aware authorization inside the app only when product requirements become concrete.

---

## 14. Recommended Immediate Next Step

Implement **Phase 1 / small pattern** first:

- add Traefik to the compose topology
- add a tiny custom ForwardAuth token service
- route external MCP traffic through Traefik
- keep `ctxledger` private behind the proxy
- validate Zed / VS Code style header-based bearer access
- validate MCP workflow/resource smoke through the proxy

Only after that is stable should work begin on the large-pattern identity-aware auth gateway.

Large-pattern follow-up should be treated as a later roadmap stream:

- do not start it during the current small-pattern implementation
- revisit it only after roadmap `0.4`, or later
- when revisiting it, confirm whether proxy-only authentication is sufficient or whether `ctxledger` itself must grow explicit multi-user authorization semantics

---

## 15. Expected End State

After both phases are complete, `ctxledger` should have:

- a stable MCP backend architecture
- no app-level dependence on a single auth style
- a low-friction solo-developer path
- a scalable organization deployment path
- a clean security boundary at the proxy/auth layer
- a future-friendly path toward richer authorization if needed