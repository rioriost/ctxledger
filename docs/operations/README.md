# Operations Documentation Index

This directory contains **operations-oriented documentation** for `ctxledger`.

The operations docs are organized by practical operational role so that
deployment guidance, security posture, and runbook-style procedures are easier
to distinguish and navigate.

## Directory layout

### `deployment/`

Use this directory for **deployment-model and runtime-operations guidance**.

Typical contents include:

- deployment architecture and topology guidance
- runtime mode expectations
- database/bootstrap operational assumptions
- local versus production-like deployment notes
- environment and infrastructure guidance

Current files include:

- `deployment/deployment.md`

### `security/`

Use this directory for **security-boundary and security-posture documentation**.

Typical contents include:

- current security model
- trust and authorization boundaries
- operator-facing security expectations
- security limitations and non-goals
- references to related auth/deployment planning

Current files include:

- `security/SECURITY.md`

### `runbooks/`

Use this directory for **operator/developer procedural guidance**.

Typical contents include:

- step-by-step operator runbooks
- local stack bring-up guidance
- auth/proxy operation workflows
- observability/Grafana procedures
- repeatable operational verification and troubleshooting steps

Current files include:

- `runbooks/small_auth_operator_runbook.md`
- `runbooks/grafana_operator_runbook.md`

---

## How to choose the right operations docs

### If you want deployment or runtime topology guidance
Start with:

- `deployment/deployment.md`

Use this when you need:

- deployment assumptions
- topology guidance
- runtime mode expectations
- database and startup/bootstrap context
- local versus production-like deployment framing

### If you want the current security boundary
Start with:

- `security/SECURITY.md`

Use this when you need:

- the present security posture
- auth boundary interpretation
- security constraints and limitations
- proxy/gateway-related security framing

### If you want operator procedures
Start with:

- `runbooks/small_auth_operator_runbook.md`
- `runbooks/grafana_operator_runbook.md`

Use these when you need:

- concrete operator steps
- local/proxy-auth flows
- Grafana-related operational procedures
- practical runbook-style setup and troubleshooting guidance

---

## Current reading of the structure

A practical shorthand for the operations docs is:

- **How is the system deployed or operated at runtime?**
  - `deployment/`
- **What is the current security boundary and posture?**
  - `security/`
- **How do I actually perform operator tasks?**
  - `runbooks/`

---

## Scope note

This `docs/operations/` directory is intended for **operations-facing
documentation**.

It is narrower than:

- `docs/project/product/`
- `docs/project/releases/`
- `docs/project/history/`

and different from:

- `docs/memory/`

Use `docs/project/` for broader repository-wide product, release, and historical
planning material.

Use `docs/memory/` for memory-topic design, decisions, runbooks, and validation
material.

Use `docs/operations/` when the document is primarily about:

- deployment
- runtime operation
- security posture
- operator procedures
- operational setup, inspection, or troubleshooting

---

## Relationship to other docs

Operations docs often connect to broader project and planning material.

Common companion references include:

- `docs/project/product/architecture.md`
- `docs/project/product/specification.md`
- `docs/project/product/roadmap.md`
- `docs/project/releases/plans/domains/auth/auth_planning_index.md`

Use the operations docs for the operational reading.
Use the project/release docs for broader architectural or milestone context.

---

## Editing guidance

When adding new operations docs:

- put deployment-model and runtime environment guidance in `deployment/`
- put security-boundary or security-posture docs in `security/`
- put step-by-step operator procedures in `runbooks/`

Avoid putting all new operations docs directly under `docs/` when one of these
subdirectories is a better fit.