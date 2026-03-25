# Large-Pattern Auth Gateway Decision Record Template for `ctxledger`

## 1. Purpose

This document is a template for recording the final decision about the **large-pattern authentication gateway** for `ctxledger`.

It is intended to be used only when the project is ready to move beyond design preparation and actually choose a gateway direction for a future multi-user deployment.

This template should be completed after the relevant roadmap and readiness gates are satisfied.

Related documents:

- `docs/project/releases/plans/auth_proxy_scaling_plan.md`
- `docs/project/releases/plans/auth_large_gateway_evaluation_memo.md`
- `docs/project/product/roadmap.md`

---

## 2. Decision Status

Choose one:

- proposed
- accepted
- rejected
- superseded

**Status:** `<fill here>`

**Decision date:** `<fill here>`

**Authors / approvers:** `<fill here>`

---

## 3. Decision Summary

Provide a short summary of the decision.

Suggested structure:

- selected gateway:
- deployment scope:
- key reason for selection:
- whether app-layer authorization is included now or deferred:

**Summary:**

`<fill here>`

---

## 4. Context

Describe the context in which this decision is being made.

Recommended points to cover:

- current `ctxledger` posture
- current small-pattern auth model
- why a large-pattern gateway is now needed
- roadmap phase / milestone that made this timely
- which environments are in scope
- what risks or constraints forced a decision now

**Context:**

`<fill here>`

---

## 5. Phase Gate Confirmation

Record the gating conditions that justified active large-pattern selection work.

Checklist:

- [ ] roadmap `0.4` or later has been reached, or an explicit exception was approved
- [ ] proxy-layer authentication alone was re-evaluated against current product needs
- [ ] MCP client compatibility requirements were reviewed
- [ ] downstream identity propagation needs were reviewed
- [ ] app-layer authorization needs were reviewed
- [ ] operator/team ownership for the chosen gateway is understood

Notes:

`<fill here>`

---

## 6. Decision Drivers

List the most important drivers behind the decision.

Typical drivers may include:

- MCP IDE compatibility
- non-browser auth flow support
- organization identity requirements
- revocation / rotation needs
- operator complexity
- auditability
- identity propagation needs
- alignment with organization standards
- future authorization extensibility
- deployment portability

**Decision drivers:**

1. `<fill here>`
2. `<fill here>`
3. `<fill here>`
4. `<fill here>`

---

## 7. Candidate Options Considered

List the concrete options that were considered.

Typical candidates may include:

- `Pomerium`
- `oauth2-proxy`
- another OIDC-aware gateway
- organization-standard identity gateway

**Options considered:**

1. `<fill here>`
2. `<fill here>`
3. `<fill here>`
4. `<fill here>`

---

## 8. Candidate Comparison Matrix

Use a short matrix to summarize the practical comparison.

| Candidate | IDE compatibility | Identity posture | Operational complexity | Identity propagation | Authorization extensibility | Overall fit |
| --- | --- | --- | --- | --- | --- | --- |
| `<candidate 1>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` |
| `<candidate 2>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` |
| `<candidate 3>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` |
| `<candidate 4>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` | `<fill here>` |

---

## 9. Chosen Option

State the final chosen option clearly.

**Chosen option:**

`<fill here>`

### Why this option was selected

Answer briefly:

- why it fits the actual MCP client set
- why it fits the operator/team environment
- why it is preferable to the alternatives
- what tradeoffs were accepted

**Selection rationale:**

`<fill here>`

---

## 10. MCP Client Compatibility Notes

This section is mandatory.

Document the actual client expectations that influenced the decision.

Suggested prompts:

- which MCP clients must work
- whether browser-assisted login is acceptable
- whether bearer headers are required
- whether device-code or token-exchange flows are acceptable
- whether the gateway changes request/response behavior in a way that could break MCP traffic
- whether `/mcp` behavior was validated under the chosen gateway model

**Client compatibility notes:**

`<fill here>`

---

## 11. Identity Propagation Decision

Describe whether identity information must cross the proxy boundary.

Possible outcomes:

- no downstream identity propagation needed yet
- trusted headers required
- JWT claims required
- both trusted headers and claims required
- future-only requirement, not immediate

Suggested fields:

- required now:
- expected form:
- consuming subsystem:
- deferred or immediate:

**Identity propagation decision:**

`<fill here>`

---

## 12. Application-Layer Authorization Decision

Record whether the project is still staying proxy-only, or whether application-layer authorization is being introduced.

Possible outcomes:

- proxy-only authentication remains sufficient for this phase
- proxy-layer identity is added now, app-layer authorization deferred
- app-layer authorization is introduced in this phase
- ownership / audit attribution is added without full authorization
- tenant isolation is required now

Suggested prompts:

- do workflows need owner identity now
- do workspaces need team/org scoping now
- do mutation routes need stronger authorization than read access
- is audit attribution required at named-user level

**Authorization decision:**

`<fill here>`

---

## 13. Trust Boundary

Describe the intended security boundary after this decision.

Suggested points:

- public entrypoint
- private backend expectation
- TLS termination point
- authentication enforcement point
- where secrets or gateway credentials live
- whether debug/operator surfaces remain behind the same boundary

**Trust boundary:**

`<fill here>`

---

## 14. Operational Model

Describe how the chosen option will be operated.

Suggested prompts:

- who owns the gateway operationally
- where the gateway runs
- how secrets are managed
- how logs and audit signals are handled
- expected maintenance burden
- migration shape from current small pattern

**Operational model:**

`<fill here>`

---

## 15. Consequences

Record both positive and negative consequences.

### Positive consequences

- `<fill here>`
- `<fill here>`
- `<fill here>`

### Negative consequences

- `<fill here>`
- `<fill here>`
- `<fill here>`

### Deferred consequences / follow-up risks

- `<fill here>`
- `<fill here>`

---

## 16. Validation Requirements

List the minimum validation steps required before the decision can be treated as operationally complete.

Checklist template:

- [ ] authenticated MCP client can reach `/mcp`
- [ ] unauthorized client cannot reach `/mcp`
- [ ] `initialize` works through the chosen gateway
- [ ] `tools/list` works through the chosen gateway
- [ ] `tools/call` works through the chosen gateway
- [ ] `resources/list` works through the chosen gateway
- [ ] `resources/read` works through the chosen gateway
- [ ] workflow smoke passes through the chosen gateway
- [ ] debug/operator route protection is validated
- [ ] identity propagation behavior is validated if required
- [ ] failure-mode behavior is documented
- [ ] operator handoff/runbook is documented

Additional validation notes:

`<fill here>`

---

## 17. Implementation Scope

Clarify what this decision does and does not authorize.

### In scope now

- `<fill here>`
- `<fill here>`
- `<fill here>`

### Explicitly not in scope now

- `<fill here>`
- `<fill here>`
- `<fill here>`

---

## 18. Migration Notes

Describe how the system is expected to move from the current small pattern to the chosen large-pattern direction.

Suggested prompts:

- what remains the same
- what gets replaced
- what gets added
- whether compose-only migration is enough
- whether runtime/app changes are required
- whether identity headers or claims need downstream support

**Migration notes:**

`<fill here>`

---

## 19. Follow-Up Work

List the concrete follow-up tasks implied by the decision.

1. `<fill here>`
2. `<fill here>`
3. `<fill here>`
4. `<fill here>`
5. `<fill here>`

---

## 20. Open Questions

List any questions that remain unresolved even after the gateway selection.

- `<fill here>`
- `<fill here>`
- `<fill here>`

---

## 21. Final Decision Statement

End with a short statement that can be quoted elsewhere.

Suggested format:

> `ctxledger` will use `<gateway>` as the large-pattern authentication gateway for `<scope>`. Authentication will remain enforced at the proxy/gateway boundary, while `<authorization decision>`.

**Final decision statement:**

> `<fill here>`
