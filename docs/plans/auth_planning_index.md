# Auth and Deployment Planning Index

## 1. Purpose

This document provides a single index and recommended reading order for the **authentication, proxy, and deployment-planning materials** in `ctxledger`.

It is intended to help a new contributor, reviewer, or future session quickly answer:

1. What is the current authentication model?
2. What deployment patterns are currently supported?
3. What is the difference between the small and large auth patterns?
4. Which documents describe actual operator procedure versus future design prep?
5. Where should the final large-pattern gateway decision be recorded?

This index does **not** redefine repository policy.
The source posture remains in the main repository docs and the auth-planning documents themselves.

Current repository direction assumed by this index:

- `ctxledger` is an HTTP-only remote MCP server
- the documented current security boundary is **proxy-layer authentication**
- the currently implemented deployment pattern is the **small pattern**
- the large pattern remains **deferred design-prep work**
- `ctxledger` itself should remain focused on MCP, workflow, memory, and persistence behavior rather than end-user login logic

---

## 2. Recommended Reading Order

Read the documents in this order.

### Step 1 — Current User-Facing Entry Point
1. `README.md`

Read this first to understand the current practical repository posture:

- how the local stack is started
- what `/mcp` currently exposes
- how proxy-protected deployment is described
- where the main deployment and security docs are linked

This is the best document for answering:

- “How do I run this today?”
- “What is the currently documented path?”

---

### Step 2 — Current Security Posture
2. `docs/SECURITY.md`

Read this next to understand the current security model:

- proxy-only authentication model
- debug route exposure policy
- operator HTTP action route cautions
- current limitations of the auth boundary
- local vs shared vs internet-exposed deployment posture

This is the best document for answering:

- “Where is auth enforced?”
- “What is the real security boundary today?”
- “What is still intentionally not solved?”

---

### Step 3 — Current Deployment Model
3. `docs/deployment.md`

Read this for the deployment-oriented interpretation of the system:

- runtime topology
- environment guidance
- debug endpoint exposure expectations
- reverse-proxy and TLS posture
- Docker-based local serving evidence
- operator HTTP route handling expectations

This is the best document for answering:

- “How should this be deployed?”
- “What does production-like posture mean here?”
- “How should the proxy/private-backend split be understood?”

---

### Step 4 — Auth Strategy Across Phases
4. `docs/plans/auth_proxy_scaling_plan.md`

Read this to understand the overall auth strategy:

- why auth should stay outside `ctxledger`
- what the small pattern is
- what the large pattern is
- why the large pattern is deferred
- how the project expects to evolve from one to the other

This is the best document for answering:

- “What is the official phased auth plan?”
- “Why is proxy-centered auth preferred?”
- “When is large-pattern work supposed to happen?”

---

### Step 5 — Current Small-Pattern Operator Procedure
5. `docs/small_auth_operator_runbook.md`

Read this when you need the actual small-pattern operating procedure.

It covers:

- startup
- service/health verification
- missing-token rejection validation
- invalid-token rejection validation
- valid-token workflow/resource smoke validation
- MCP client targeting
- shutdown
- common failure modes

This is the best document for answering:

- “How do I actually operate the small auth pattern?”
- “What commands should I run?”
- “How do I verify reject/allow behavior?”

---

### Step 6 — Large-Pattern Evaluation Prep
6. `docs/plans/auth_large_gateway_evaluation_memo.md`

Read this when you need the current design-prep comparison frame for future large-pattern gateway work.

It captures:

- why the work is deferred
- what criteria matter most
- why MCP IDE compatibility is first-class
- candidate categories such as:
  - `Pomerium`
  - `oauth2-proxy`
  - other OIDC-aware gateways
  - organization-standard gateways
- readiness questions that must be answered before final selection

This is the best document for answering:

- “How are we supposed to compare large-pattern gateway options?”
- “Why has no gateway been chosen yet?”
- “What must be validated before selection?”

---

### Step 7 — Future Large-Pattern Decision Record
7. `docs/plans/auth_large_gateway_decision_record_template.md`

Read this only when the project is actually ready to choose a large-pattern gateway.

It is a template for the follow-on decision record and includes sections for:

- phase-gate confirmation
- decision drivers
- candidate comparison matrix
- client compatibility notes
- identity propagation
- app-layer authorization decision
- trust boundary
- validation requirements
- migration notes
- final decision statement

This is the best document for answering:

- “Where do we record the final large-pattern gateway choice?”
- “What evidence should that decision include?”
- “What questions must be answered before adoption?”

---

## 3. Quick Reference by Question

Use this section if you do not want to read everything in order.

### “How do I run the current system?”
- `README.md`

### “What is the current security boundary?”
- `docs/SECURITY.md`

### “How should this be deployed today?”
- `docs/deployment.md`

### “What is the official small-vs-large auth plan?”
- `docs/plans/auth_proxy_scaling_plan.md`

### “How do I actually operate the small auth pattern?”
- `docs/small_auth_operator_runbook.md`

### “How are future large-pattern gateways being compared?”
- `docs/plans/auth_large_gateway_evaluation_memo.md`

### “Where should the final large-pattern gateway choice be recorded?”
- `docs/plans/auth_large_gateway_decision_record_template.md`

---

## 4. Current Recommended Reading Paths by Role

### New contributor
Read:

1. `README.md`
2. `docs/SECURITY.md`
3. `docs/deployment.md`
4. `docs/plans/auth_proxy_scaling_plan.md`

### Operator working on the current small pattern
Read:

1. `README.md`
2. `docs/small_auth_operator_runbook.md`
3. `docs/SECURITY.md`
4. `docs/deployment.md`

### Reviewer validating auth/deployment consistency
Read:

1. `docs/SECURITY.md`
2. `docs/deployment.md`
3. `docs/plans/auth_proxy_scaling_plan.md`
4. `docs/small_auth_operator_runbook.md`

### Planner preparing future large-pattern work
Read:

1. `docs/plans/auth_proxy_scaling_plan.md`
2. `docs/plans/auth_large_gateway_evaluation_memo.md`
3. `docs/plans/auth_large_gateway_decision_record_template.md`
4. `docs/roadmap.md`

---

## 5. Scope Boundaries

This planning set is meant to clarify **authentication and deployment posture**.
It does **not** by itself define:

- MCP transport rewrite planning
- full protocol compliance closeout
- detailed workflow-domain authorization semantics
- tenant isolation design
- final identity propagation schema inside `ctxledger`

For adjacent topics, see:

- `docs/mcp-api.md`
- `docs/workflow-model.md`
- `docs/specification.md`
- `docs/roadmap.md`
- `docs/plans/mcp_planning_index.md`

---

## 6. Current Practical Summary

At the current repository stage:

- the active implemented deployment path is the **small auth pattern**
- authentication is expected at the **proxy layer**
- the backend application is intended to remain **private**
- `ctxledger` no longer relies on documented app-layer bearer auth
- large-pattern work remains a **future design stream**
- any final large-pattern gateway selection should be recorded through a structured decision record rather than informally introduced

In short:

> use the small-pattern runbook for current operation, use the scaling plan and evaluation memo for future planning, and use the decision-record template only when the project is truly ready to choose a large-pattern gateway.