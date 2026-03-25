# MCP PR Sequence Overview

## 1. Purpose

This document provides a PR-by-PR overview for the MCP transport rewrite workstream in `ctxledger`.

It is intended to answer one practical planning question:

> In what order should the MCP rewrite be implemented and reviewed so that the repository moves from a custom `/mcp` endpoint toward a real MCP `2025-03-26` Streamable HTTP server?

This overview is a coordination artifact for implementation sequencing, review sizing, and risk control.

It is downstream of:

- `docs/project/product/specification.md`
- `docs/project/releases/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/project/releases/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/project/releases/plans/mcp_transport_rewrite_execution_plan.md`
- `docs/project/releases/plans/mcp_transport_cutover_checklist.md`
- `docs/project/releases/plans/mcp_module_split_proposal.md`
- `docs/project/releases/plans/mcp_first_patch_plan.md`
- `docs/project/releases/plans/mcp_second_patch_plan.md`
- `docs/project/releases/plans/mcp_third_patch_plan.md`

---

## 2. Guiding Rule

The PR sequence follows one non-negotiable rule:

> Do not evolve the current custom `/mcp` endpoint into the final solution. Extract reusable business logic, introduce a new protocol authority, bind features into the new transport, then harden and cut over.

In practical terms:

- early PRs should reduce coupling
- middle PRs should establish protocol ownership
- later PRs should establish compliant behavior
- final PRs should remove obsolete custom transport assumptions

---

## 3. High-Level Sequence

The recommended PR sequence is:

1. **PR 1 — MCP package bootstrap extraction**
2. **PR 2 — Lifecycle and Streamable HTTP scaffold**
3. **PR 3 — Result mapping and required feature binding**
4. **PR 4 — Transport hardening and `/mcp` cutover**
5. **PR 5 — Post-cutover cleanup and documentation convergence**

This is the preferred order because it minimizes risk while preserving momentum.

---

## 4. PR 1 — MCP Package Bootstrap Extraction

## Objective

Create the MCP package and extract stable, low-risk reusable assets from `src/ctxledger/server.py`.

## Primary goals

- reduce `server.py` responsibility
- preserve behavior
- prepare for later transport replacement
- avoid changing `/mcp` semantics yet

## Expected scope

Create:

- `src/ctxledger/mcp/__init__.py`
- `src/ctxledger/mcp/tool_schemas.py`
- `src/ctxledger/mcp/tool_handlers.py`
- `src/ctxledger/mcp/resource_handlers.py`

Modify:

- `src/ctxledger/server.py`
- possibly tests only for import stability

## Expected changes

- move tool schema definitions
- move transport-neutral tool handler builders
- move transport-neutral resource URI / handler helpers
- keep existing behavior stable

## Review expectation

- small to medium PR
- mostly extraction and import rewiring
- low protocol risk
- high structural value

## Success condition

After PR 1:

- `server.py` is smaller
- MCP business assets are reusable
- transport rewrite can begin without dragging schema/handler noise along

## Failure mode to avoid

- turning PR 1 into a transport rewrite
- changing acceptance semantics too early
- adding lifecycle or SSE work prematurely

---

## 5. PR 2 — Lifecycle and Streamable HTTP Scaffold

## Objective

Introduce the first new protocol-facing MCP transport authority.

## Primary goals

- establish lifecycle ownership outside `server.py`
- establish a new Streamable HTTP transport scaffold
- begin representing `/mcp` as a real MCP endpoint rather than a generic route

## Expected scope

Create:

- `src/ctxledger/mcp/lifecycle.py`
- `src/ctxledger/mcp/streamable_http.py`

Optionally:
- small protocol helper/type modules if truly needed

Modify:

- `src/ctxledger/server.py`
- minimal test coverage for scaffold existence and wiring

## Expected changes

- introduce `initialize` validation scaffold
- introduce protocol version negotiation scaffold
- introduce correct `notifications/initialized` naming authority
- introduce GET/POST transport structure
- keep SSE/session behavior mostly scaffolded, not complete

## Review expectation

- medium PR
- first protocol-facing change
- architectural review important
- should still avoid deep feature binding

## Success condition

After PR 2:

- `/mcp` has a new protocol-oriented ownership path
- lifecycle correctness begins to live outside the old custom dispatcher
- the repository is pointed at the right transport model

## Failure mode to avoid

- creating new files while leaving all real authority in `server.py`
- pretending the scaffold itself is compliance
- mixing feature binding too early into the transport foundation patch

---

## 6. PR 3 — Result Mapping and Required Feature Binding

## Objective

Make the new transport actually useful for MCP feature traffic.

## Primary goals

- introduce MCP-compliant result mapping
- bind required workflow tools into the new transport
- optionally bind initial workflow resources
- begin serious protocol-oriented feature tests

## Expected scope

Create:

- `src/ctxledger/mcp/result_mapping.py`

Possibly:
- `feature_registry.py`
- small protocol error/type modules if needed now

Modify:

- `src/ctxledger/mcp/streamable_http.py`
- `src/ctxledger/mcp/lifecycle.py`
- extracted handler modules
- `src/ctxledger/server.py`
- `tests/test_server.py`

## Expected changes

- separate protocol errors from execution errors
- stop using local `ok/result/error` envelope as final transport authority
- support new transport:
  - `tools/list`
  - `tools/call`
- bind required workflow tools:
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `workflow_complete`
- optionally bind workflow resources if patch size allows

## Review expectation

- medium to large PR
- strong protocol review required
- tests become more semantically important here

## Success condition

After PR 3:

- the new `/mcp` transport is no longer just scaffolding
- required workflow tools are discoverable and invokable through the new path
- result semantics are noticeably closer to MCP expectations

## Failure mode to avoid

- still flattening execution failures into protocol errors
- binding too many optional features and bloating the patch
- keeping old `/mcp` as the real path while the new path remains cosmetic

---

## 7. PR 4 — Transport Hardening and `/mcp` Cutover

## Objective

Finish the transport-level compliance work needed to make the new `/mcp` path the real primary MCP endpoint.

## Primary goals

- harden Streamable HTTP behavior
- complete transport semantics
- retire or quarantine the old custom `/mcp` path
- shift acceptance to the new transport

## Expected scope

Modify:

- `src/ctxledger/mcp/streamable_http.py`
- possibly:
  - `src/ctxledger/mcp/session.py`
  - `src/ctxledger/mcp/sse.py`
  - `src/ctxledger/mcp/security.py`
- `src/ctxledger/server.py`
- transport-focused tests

## Expected changes

- GET behavior expansion
- SSE behavior
- request category handling
- 202 handling where required
- `Origin` validation
- session behavior if adopted
- stronger resource support if still pending
- old custom `/mcp` handler retirement or quarantine

## Review expectation

- large PR unless split further
- transport compliance review mandatory
- likely the highest-risk PR in the sequence

## Success condition

After PR 4:

- the new `/mcp` transport is the real primary path
- the old custom MCP HTTP handler is no longer release-authoritative
- transport behavior is much closer to spec-compliant Streamable HTTP

## Failure mode to avoid

- declaring victory before GET/SSE/request-category semantics are actually aligned
- leaving the old handler active in a confusing way
- skipping security requirements like `Origin` validation

---

## 8. PR 5 — Post-Cutover Cleanup and Documentation Convergence

## Objective

Clean up obsolete assumptions and align repository docs/evidence with the actual implementation state.

## Primary goals

- remove residual custom transport assumptions
- reconcile stdio’s place in the repository
- align docs outside `specification.md`
- finalize acceptance framing

## Expected scope

Modify or review:

- `src/ctxledger/server.py`
- any remaining transitional MCP code
- `README.md`
- `docs/project/product/mcp-api.md`
- `docs/project/product/architecture.md`
- `docs/operations/deployment/deployment.md`
- `docs/project/releases/CHANGELOG.md`
- `docs/project/history/imple_plan_review_0.1.0.md`
- `docs/v0.1.0_acceptance_evidence.md`
- relevant tests

## Expected changes

- remove “minimal path” framing
- remove obsolete custom `/mcp` implementation references
- ensure docs point to MCP `2025-03-26` + Streamable HTTP target
- decide and document stdio release role clearly
- tighten acceptance evidence around the real compliant path

## Review expectation

- medium PR
- lower protocol risk
- high correctness/documentation importance

## Success condition

After PR 5:

- docs and code point at the same target
- no major misleading framing remains
- acceptance evidence reflects the actual new transport

## Failure mode to avoid

- leaving old acceptance language in place
- treating docs as secondary when they influence future implementation direction
- reintroducing weakened wording that conflicts with `specification.md`

---

## 9. Recommended Review Boundaries

To keep reviews effective, each PR should answer one dominant review question.

### PR 1
**Did we extract stable reusable MCP assets without changing behavior?**

### PR 2
**Did we introduce the correct transport/lifecycle ownership structure?**

### PR 3
**Did we bind required MCP features with correct result semantics?**

### PR 4
**Did we harden transport semantics enough to make `/mcp` a real compliant primary path?**

### PR 5
**Did we remove drift and make the repository honest about its implementation state?**

---

## 10. Optional Split If PR 4 Is Too Large

If PR 4 becomes too large, split it into:

### PR 4A — Stream semantics hardening
- GET behavior
- SSE behavior
- request category behavior
- 202 handling

### PR 4B — Security/session/cutover
- `Origin` validation
- session model if adopted
- old custom `/mcp` retirement
- final transport cutover tests

This is preferable to allowing one oversized hardening PR to become unreviewable.

---

## 11. Dependency Chain

The practical dependency chain is:

- PR 1 enables PR 2
- PR 2 enables PR 3
- PR 3 enables PR 4
- PR 4 enables PR 5

This chain should generally not be reordered.

What can happen in parallel:
- test planning
- interoperability research
- doc draft preparation

What should not happen out of order:
- old `/mcp` removal before the new transport is feature-capable
- broad docs closeout before transport hardening is done
- lifecycle hardening after feature binding has already assumed the wrong transport model

---

## 12. Sequence Risk Summary

### Main risk if order is violated

If the team skips ahead and starts polishing the old `/mcp` path, it may create:

- more custom transport debt
- more misleading local tests
- more cleanup work later
- false confidence around “working MCP” behavior

### Main benefit of the proposed order

This sequence ensures:

- business logic is preserved early
- protocol authority is introduced before deep feature growth
- feature binding happens on the new transport, not the old one
- hardening happens after there is something real to harden
- docs are corrected after implementation reality stabilizes

---

## 13. Milestone Mapping

The PR sequence maps cleanly onto the milestone model from the broader execution plan.

- **Milestone 1** → PR 1
- **Milestone 2–3** → PR 2
- **Milestone 4–5** → PR 3
- **Milestone 6–7** → PR 4
- **Milestone 8** → PR 5

This makes the sequence easy to track during implementation.

---

## 14. Final Recommendation

The recommended implementation/review order is:

1. **PR 1 — MCP package bootstrap extraction**
2. **PR 2 — Lifecycle and Streamable HTTP scaffold**
3. **PR 3 — Result mapping and required feature binding**
4. **PR 4 — Transport hardening and `/mcp` cutover**
5. **PR 5 — Post-cutover cleanup and documentation convergence**

This is the safest, clearest path from the current custom `/mcp` implementation toward a real MCP `2025-03-26` Streamable HTTP server.