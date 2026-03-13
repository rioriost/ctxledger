# Large-Pattern Auth Gateway Evaluation Memo for `ctxledger`

## 1. Purpose

This memo records a **design-preparation evaluation** for the large-pattern authentication gateway that may eventually sit in front of `ctxledger`.

It is intentionally **not** an implementation plan.

Its purpose is to:

- compare realistic gateway candidates for a future multi-user deployment
- make the current evaluation criteria explicit
- capture the constraints that matter for MCP-capable IDE clients
- avoid premature implementation before the project reaches the right roadmap phase

This memo is downstream of:

- `docs/plans/auth_proxy_scaling_plan.md`
- `docs/roadmap.md`
- the current small-pattern proxy-only authentication model

When the project is ready to move from design preparation to an actual large-pattern gateway selection, the follow-on decision should be recorded using:

- `docs/plans/auth_large_gateway_decision_record_template.md`

---

## 2. Current Recommendation

## Recommendation summary

At the current stage, `ctxledger` should:

1. keep the **small pattern** as the active and supported auth deployment model
2. treat large-pattern work as **post-`0.4` design-gated work**
3. evaluate large-pattern gateways against **IDE compatibility first**, not only generic web SSO convenience
4. prefer a gateway that preserves the core architecture rule:

> authentication should be handled at the proxy or gateway layer, while `ctxledger` remains focused on MCP, workflow, memory, and persistence behavior

## Current preferred evaluation stance

At this point:

- **Pomerium** looks like a strong strategic candidate for a future multi-user internal deployment
- **oauth2-proxy** remains a valid candidate, especially where it is already an organizational standard
- an **organization-standard identity gateway** may be the best final answer if it already satisfies MCP-client constraints
- no gateway should be selected yet without validating the expected non-browser or semi-browser MCP client flows

This is a **comparison memo**, not a final decision record.

---

## 3. Context

`ctxledger` already has a clear small-pattern direction:

- Traefik as the front door
- a lightweight ForwardAuth-compatible auth service
- static bearer-token validation at the proxy layer
- `ctxledger` as a private backend
- no application-layer bearer-auth requirement inside `ctxledger`

That shape is a good fit for:

- a single operator
- a local or tightly controlled private environment
- low operational overhead
- IDE clients that can send bearer headers directly

The large pattern is different.

It is intended for a future environment with:

- multiple engineers
- shared organizational access
- distinct user identity
- revocation and rotation expectations
- eventual auditability and policy pressure
- possible future need for downstream identity propagation

That means the gateway decision must be made with more care than a normal browser-only internal web app choice.

---

## 4. Phase Gate

Large-pattern gateway work should remain gated by roadmap phase.

## Current gate

Large-pattern implementation should not start before:

- roadmap `0.4`, or later
- a fresh check of actual product priorities
- a re-evaluation of whether proxy-layer authentication alone is still sufficient
- a confirmation of which MCP-capable clients must be supported in practice

## Why the gate matters

Choosing and wiring a large identity gateway too early would risk:

- overfitting to a web-browser login model
- introducing operational complexity before it is needed
- forcing identity assumptions into the architecture prematurely
- obscuring the distinction between authentication and future authorization work

The project already has a workable proxy boundary through the small pattern. That means the immediate architectural unknown is no longer “should auth live in front of the app?” but rather “which future gateway best fits the client and operator reality?”

---

## 5. Evaluation Criteria

The large-pattern gateway should be evaluated primarily on the following criteria.

## 5.1 MCP IDE compatibility

This is the most important criterion.

The gateway must be compatible with remote MCP usage from clients such as:

- VS Code
- Zed
- similar MCP-capable IDE tools

Important questions include:

- can the client authenticate without a browser-only assumption
- can the client attach required headers or bearer credentials
- does the gateway require redirect-heavy cookie flows that are awkward for IDE integration
- is there a workable device-code, token, service-account, or delegated-access story if needed
- can the gateway protect `/mcp` without breaking expected HTTP transport behavior

A gateway that is excellent for browser apps but awkward for MCP IDE clients is not a strong fit.

---

## 5.2 Identity quality

The gateway should be able to support:

- distinct user identity
- revocation and rotation
- organization-managed authentication
- traceable user context
- stable downstream identity representation when needed

Useful downstream identity forms may include:

- trusted headers
- JWT claims
- signed identity assertions
- gateway-managed session identity

This does not mean `ctxledger` must consume identity immediately, only that the gateway should not block that future path.

---

## 5.3 Operational fit

The gateway should be evaluated for:

- deployment complexity
- Compose-to-production migration shape
- secret management requirements
- certificate and TLS posture
- observability and audit ergonomics
- operator familiarity
- expected day-2 maintenance burden

The best technical choice on paper is still a poor choice if it becomes too heavy for the team operating it.

---

## 5.4 Authorization extensibility

Even if `ctxledger` remains auth-agnostic at the application layer for some time, the gateway decision should consider whether it can later support:

- stable identity propagation
- policy attachment
- coarse path-level controls
- future service-to-service trust boundaries
- a clean path toward app-layer authorization if product needs emerge

This is not a reason to overbuild now. It is just a reason to avoid locking into a gateway that collapses future options.

---

## 5.5 Architecture alignment

The gateway should preserve the current architectural rule:

- Traefik or an equivalent front door remains the public boundary
- `ctxledger` remains private
- authentication is externalized
- app-layer login logic is not reintroduced into `ctxledger`

If a gateway choice would pressure the project into embedding end-user login behavior inside the application, it is a poor architectural fit.

---

## 6. Candidate Set

This memo evaluates four practical candidate categories:

1. `Pomerium`
2. `oauth2-proxy`
3. another OIDC-aware gateway
4. an organization-standard identity gateway

These categories reflect the direction already captured in the scaling plan.

---

## 7. Candidate Evaluation

## 7.1 Pomerium

### Summary

`Pomerium` looks like a strong candidate for a future multi-user internal-tool deployment where identity, policy posture, and gateway-centered control matter.

### Strengths

- built around identity-aware access to internal services
- strong policy-oriented posture
- good conceptual fit for internal engineering tools
- clearer long-term story for user-aware access than a static-token gate
- naturally aligned with a proxy-centered security boundary
- likely to be a good fit when the organization wants stronger access control without pushing auth into `ctxledger`

### Risks or cautions

- heavier than the small-pattern auth layer
- likely more operationally involved than a lightweight bearer check
- may be unnecessary if the real future need remains modest
- still requires validation for MCP IDE client ergonomics and non-browser flow behavior

### Current assessment

`Pomerium` is a **strategically strong candidate** and may be the best fit if:

- multi-user internal access becomes important
- the operator team accepts the additional gateway complexity
- client compatibility checks succeed
- the organization does not already have a superior standard gateway in place

---

## 7.2 `oauth2-proxy`

### Summary

`oauth2-proxy` is a valid and credible candidate, especially in environments where it is already known, deployed, or standardized.

### Strengths

- mature and widely used
- broad OIDC and OAuth support
- common reverse-proxy integration patterns
- relatively familiar to many platform teams
- reasonable fit when the surrounding organization already understands its operational model

### Risks or cautions

- often most natural in browser, redirect, and cookie-centric flows
- may create friction for IDE clients if the expected interaction model assumes web login behavior
- could be operationally acceptable yet ergonomically weak for remote MCP usage
- may require more client-specific workaround design than a more explicitly identity-gateway-oriented option

### Current assessment

`oauth2-proxy` is a **serious candidate**, but not an automatic winner.

It is especially attractive if:

- the organization already runs it successfully
- the identity provider integration is already solved
- the intended MCP client set can be shown to work cleanly with its auth flow shape

Without that compatibility evidence, it should remain a candidate rather than a default choice.

---

## 7.3 Another OIDC-aware gateway

### Summary

A broader OIDC-aware gateway category should remain open.

This could include gateways or access products that provide:

- OIDC integration
- identity-bearing reverse proxy behavior
- forward-auth patterns
- policy controls
- stronger non-browser client stories than browser-centric web tooling

### Strengths

- keeps the project from prematurely narrowing to two named products
- allows better fit with actual operator constraints
- may surface a gateway with better IDE compatibility or easier operational posture
- preserves optionality if ecosystem offerings change

### Risks or cautions

- broad categories can delay decisions if not narrowed with concrete criteria
- more options can mean more evaluation overhead
- unfamiliar products raise operational risk if the team lacks experience with them

### Current assessment

This category should stay open during design prep, but should be narrowed later using a concrete decision matrix rather than open-ended discussion.

---

## 7.4 Organization-standard identity gateway

### Summary

If the organization already has a sanctioned identity gateway, access proxy, or ingress policy layer, that may become the strongest practical choice.

### Strengths

- aligns with existing security and compliance posture
- reduces net-new operational burden
- reuses established identity integrations
- may improve supportability, ownership clarity, and audit posture
- often simplifies rollout compared with introducing a new standalone auth stack

### Risks or cautions

- an organization-standard solution may still be poorly suited to MCP IDE traffic
- “standard” does not automatically mean “compatible”
- platform constraints may bias the project toward a browser-only mental model
- the standard gateway may expose identity well but offer a poor developer experience for remote MCP clients

### Current assessment

This category may produce the best real-world outcome, but only if it passes the same MCP-client compatibility bar as any other candidate.

The project should not waive the IDE compatibility requirement just because a gateway is organizationally preferred.

---

## 8. Comparative Decision Matrix

The following matrix is intentionally qualitative.

| Candidate | IDE compatibility risk | Identity posture | Operational complexity | Policy / future extensibility | Current fit |
| --- | --- | --- | --- | --- | --- |
| `Pomerium` | Medium, must be validated | Strong | Medium to High | Strong | Strong candidate |
| `oauth2-proxy` | Medium to High, browser-flow risk | Strong | Medium | Medium to Strong | Valid candidate |
| Other OIDC-aware gateway | Unknown until narrowed | Varies | Varies | Varies | Keep open |
| Organization-standard gateway | Unknown until validated | Often strong | Often favorable in-context | Often strong | Potentially strong |

This matrix is not a final scorecard. It exists to structure the next round of evaluation.

---

## 9. Identity Propagation Considerations

Even if `ctxledger` remains application-auth-agnostic, the large-pattern gateway should be evaluated for what identity signal it can pass downstream.

Possible forms include:

- trusted user headers
- signed identity headers
- forwarded JWT claims
- gateway-generated identity context
- service-authenticated metadata on internal requests

Why this matters:

- future audit attribution may need named-user context
- future workspace ownership may need a stable identity key
- future authorization rules may need a subject identity even if the first rollout does not

Current posture:

- `ctxledger` does not yet require this
- large-pattern gateway selection should avoid blocking it
- identity propagation should remain optional until product requirements make it necessary

---

## 10. What This Memo Does Not Decide

This memo does **not** decide:

- the final large-pattern gateway
- whether app-layer authorization will be added to `ctxledger`
- whether workflows need ownership semantics
- whether workspaces need team or organization scoping
- whether tenant isolation is required
- the final production deployment topology
- the final IdP integration details

Those questions should be addressed later, closer to actual implementation.

---

## 11. Readiness Questions Before Final Selection

Before a final gateway is selected, the project should explicitly answer:

1. which MCP clients must be supported in practice
2. which authentication flows those clients can reliably support
3. whether browser-assisted auth is acceptable, optional, or unacceptable
4. whether stable downstream identity metadata is required in the next phase
5. whether audit attribution must identify individual users
6. whether mutation routes need different trust or policy handling from read-style access
7. whether the organization already has a gateway that satisfies the technical constraints
8. whether large-pattern rollout is still intended to remain proxy-only, or must coincide with application-level authorization work

These questions should gate any final decision.

---

## 12. Proposed Next Documentation Step

When large-pattern work becomes timely, the next documentation artifact should be a short decision matrix or ADR-style record that includes:

- final candidate shortlist
- concrete client compatibility notes
- operator constraints
- identity propagation expectations
- why the chosen gateway was selected
- whether app-layer authorization is intentionally deferred or explicitly introduced

The repository now includes a template for that follow-up artifact at:

- `docs/plans/auth_large_gateway_decision_record_template.md`

That follow-up artifact should be created only when the roadmap gate is actually reached.

---

## 13. Current Conclusion

The current conclusion is:

- `ctxledger` should continue using the implemented small-pattern proxy-only auth model for now
- large-pattern gateway work should remain a **deferred design stream**
- `Pomerium` appears strategically promising
- `oauth2-proxy` remains a valid candidate
- organization-standard gateways should be considered seriously
- no final large-pattern gateway should be selected until IDE and remote MCP client compatibility is validated explicitly

In short:

> the next correct step is not implementation, but disciplined evaluation at the right phase boundary